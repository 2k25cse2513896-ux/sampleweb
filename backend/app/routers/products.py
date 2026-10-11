"""Product catalogue: public search plus staff/admin CRUD and image upload."""

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session, selectinload

from app.core.db import engine, get_db
from app.core.deps import require_admin, require_staff
from app.core.errors import AppError
from app.models.entities import Brand, Category, PriceHistory, Product, ProductImage, Review, User
from app.schemas.catalogue import ProductIn, ProductOut, ProductPromptIn, ProductUpdate
from app.schemas.common import Page
from app.services.audit import write_audit
from app.services.images import save_product_image
from app.services.stock import apply_stock_change
from app.services.product_ai import parse_product_prompt
from app.services.seed import product_image_url

router = APIRouter(tags=["products"])


def _to_out(product: Product) -> ProductOut:
    brand_name = None
    if product.brand is not None:
        brand_name = product.brand.name
    category_name = None
    if product.category is not None:
        category_name = product.category.name
    data = ProductOut.model_validate(product)
    data.brand_name = brand_name
    data.category_name = category_name
    return data


def _search_ids_fts(query: str) -> Optional[List[int]]:
    """Return matching product ids from FTS5, or None to fall back to LIKE."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT rowid FROM products_fts WHERE products_fts MATCH :q"),
                {"q": query},
            ).fetchall()
        ids: List[int] = []
        for row in rows:
            ids.append(int(row[0]))
        return ids
    except Exception:
        return None


def _record_zero_hit(db: Session, query: str) -> None:
    from app.models.entities import SearchZeroHit
    from app.models.base import utc_now

    existing = db.query(SearchZeroHit).filter(SearchZeroHit.query == query).one_or_none()
    if existing is None:
        db.add(SearchZeroHit(query=query, hit_count=1, last_seen=utc_now()))
    else:
        existing.hit_count = existing.hit_count + 1
        existing.last_seen = utc_now()


@router.get("/api/products", response_model=Page[ProductOut])
def list_products(
    db: Session = Depends(get_db),
    q: Optional[str] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    in_stock: Optional[bool] = None,
    warranty: Optional[bool] = None,
    featured: Optional[bool] = None,
    sort: str = "newest",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=60),
) -> Page[ProductOut]:
    query = db.query(Product).options(selectinload(Product.images), selectinload(Product.brand), selectinload(Product.category))
    query = query.filter(Product.is_active == True)  # noqa: E712

    if q is not None:
        text_q = q.strip()
        if text_q != "":
            # LIKE is the reliable baseline for SQLite builds where external-content FTS was copied empty.
            # The FTS table is still created for deployments that choose to optimize this query later.
            like = "%" + text_q + "%"
            query = query.join(Brand).join(Category).filter(
                or_(Product.name.ilike(like), Product.sku.ilike(like), Brand.name.ilike(like), Category.name.ilike(like))
            )

    if category is not None:
        cat = db.query(Category).filter(Category.slug == category).one_or_none()
        if cat is not None:
            query = query.filter(Product.category_id == cat.id)

    if brand is not None:
        br = db.query(Brand).filter(Brand.slug == brand).one_or_none()
        if br is not None:
            query = query.filter(Product.brand_id == br.id)

    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if in_stock is True:
        query = query.filter(Product.stock_qty > 0)
    if warranty is True:
        query = query.filter(Product.warranty_months > 0)
    if featured is True:
        query = query.filter(Product.is_featured == True)  # noqa: E712

    if sort == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc())
    elif sort == "name":
        query = query.order_by(Product.name.asc())
    else:
        query = query.order_by(Product.created_at.desc())

    total = query.count()
    if total == 0:
        if q is not None:
            if q.strip() != "":
                _record_zero_hit(db, q.strip().lower())
                db.commit()

    offset = (page - 1) * page_size
    rows = query.offset(offset).limit(page_size).all()
    items: List[ProductOut] = []
    for row in rows:
        items.append(_to_out(row))
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/api/products/{slug}", response_model=ProductOut)
def get_product(slug: str, db: Session = Depends(get_db)) -> ProductOut:
    product = (
        db.query(Product)
        .options(selectinload(Product.images), selectinload(Product.brand), selectinload(Product.category))
        .filter(Product.slug == slug)
        .one_or_none()
    )
    if product is None:
        raise AppError("not_found", "Product was not found.", 404)
    out = _to_out(product)
    avg = (
        db.query(func.avg(Review.rating))
        .filter(Review.product_id == product.id, Review.is_approved == True)  # noqa: E712
        .scalar()
    )
    if avg is not None:
        # Store tenths as integer so the API never sends a money-like float.
        from decimal import Decimal

        from app.core.money import round_rupees

        tenths = round_rupees(Decimal(str(avg)) * Decimal("10"))
        out.average_rating_tenths = tenths
    return out


@router.post("/api/admin/products", response_model=ProductOut)
def create_product(
    body: ProductIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> ProductOut:
    clash = db.query(Product).filter(or_(Product.sku == body.sku, Product.slug == body.slug)).one_or_none()
    if clash is not None:
        raise AppError("conflict", "SKU or slug already exists.", 409)
    try:
        json.loads(body.specs_json)
    except Exception:
        raise AppError("validation_error", "specs_json must be valid JSON.", 422)

    initial_stock = body.stock_qty
    product = Product(
        sku=body.sku,
        barcode=body.barcode,
        name=body.name,
        slug=body.slug,
        description=body.description,
        category_id=body.category_id,
        brand_id=body.brand_id,
        price=body.price,
        mrp=body.mrp,
        cost_price=body.cost_price,
        stock_qty=0,
        low_stock_threshold=body.low_stock_threshold,
        warranty_months=body.warranty_months,
        is_genuine_verified=body.is_genuine_verified,
        is_active=body.is_active,
        is_featured=body.is_featured,
        specs_json=body.specs_json,
    )
    db.add(product)
    db.flush()
    if initial_stock > 0:
        apply_stock_change(db, product.id, initial_stock, "restock", "create", user.id)
    write_audit(db, user.id, "create", "product", str(product.id), "{}")
    db.commit()
    db.refresh(product)
    product = (
        db.query(Product)
        .options(selectinload(Product.images), selectinload(Product.brand), selectinload(Product.category))
        .filter(Product.id == product.id)
        .one()
    )
    return _to_out(product)


@router.post("/api/admin/products/from-prompt", response_model=ProductOut)
def create_product_from_prompt(
    body: ProductPromptIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> ProductOut:
    """Create a real catalogue product from a short Hinglish quick-add prompt."""
    parsed = parse_product_prompt(db, body.prompt)
    slug = parsed.pop("slug")
    category_slug = parsed.pop("category_slug")
    product = Product(**parsed)
    product.slug = slug
    initial_stock = product.stock_qty
    product.stock_qty = 0
    db.add(product)
    db.flush()
    if initial_stock > 0:
        apply_stock_change(db, product.id, initial_stock, "restock", "ai_prompt", admin.id)
    db.add(ProductImage(product_id=product.id, url=product_image_url(category_slug, product.specs_json), sort_order=0))
    write_audit(db, admin.id, "ai_create", "product", str(product.id), json.dumps({"prompt": body.prompt[:200]}))
    db.commit()
    product = (
        db.query(Product)
        .options(selectinload(Product.images), selectinload(Product.brand), selectinload(Product.category))
        .filter(Product.id == product.id)
        .one()
    )
    return _to_out(product)


@router.put("/api/admin/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    body: ProductUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> ProductOut:
    product = db.get(Product, product_id)
    if product is None:
        raise AppError("not_found", "Product was not found.", 404)

    price_changing = False
    if body.price is not None:
        if body.price != product.price:
            price_changing = True
    if body.mrp is not None:
        if body.mrp != product.mrp:
            price_changing = True
    if body.cost_price is not None:
        if body.cost_price != product.cost_price:
            price_changing = True
    if price_changing is True:
        if user.role != "admin":
            raise AppError("forbidden", "Only admin can change prices.", 403)

    if body.price is not None:
        if body.price != product.price:
            db.add(
                PriceHistory(
                    product_id=product.id,
                    old_price=product.price,
                    new_price=body.price,
                )
            )
            product.price = body.price

    if body.sku is not None:
        product.sku = body.sku
    if body.barcode is not None:
        product.barcode = body.barcode
    if body.name is not None:
        product.name = body.name
    if body.slug is not None:
        product.slug = body.slug
    if body.description is not None:
        product.description = body.description
    if body.category_id is not None:
        product.category_id = body.category_id
    if body.brand_id is not None:
        product.brand_id = body.brand_id
    if body.mrp is not None:
        product.mrp = body.mrp
    if body.cost_price is not None:
        product.cost_price = body.cost_price
    if body.low_stock_threshold is not None:
        product.low_stock_threshold = body.low_stock_threshold
    if body.warranty_months is not None:
        product.warranty_months = body.warranty_months
    if body.is_genuine_verified is not None:
        product.is_genuine_verified = body.is_genuine_verified
    if body.is_active is not None:
        product.is_active = body.is_active
    if body.is_featured is not None:
        product.is_featured = body.is_featured
    if body.specs_json is not None:
        try:
            json.loads(body.specs_json)
        except Exception:
            raise AppError("validation_error", "specs_json must be valid JSON.", 422)
        product.specs_json = body.specs_json

    write_audit(db, user.id, "update", "product", str(product.id), "{}")
    db.commit()
    product = (
        db.query(Product)
        .options(selectinload(Product.images), selectinload(Product.brand), selectinload(Product.category))
        .filter(Product.id == product.id)
        .one()
    )
    return _to_out(product)


@router.delete("/api/admin/products/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict[str, str]:
    product = db.get(Product, product_id)
    if product is None:
        raise AppError("not_found", "Product was not found.", 404)
    # Soft delete so order history keeps a valid product_id.
    product.is_active = False
    write_audit(db, admin.id, "deactivate", "product", str(product_id), "{}")
    db.commit()
    return {"message": "Product deactivated."}


@router.post("/api/admin/products/{product_id}/images")
def upload_image(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> ProductOut:
    product = db.get(Product, product_id)
    if product is None:
        raise AppError("not_found", "Product was not found.", 404)
    url = save_product_image(product_id, file)
    max_sort = db.query(func.max(ProductImage.sort_order)).filter(ProductImage.product_id == product_id).scalar()
    next_sort = 0
    if max_sort is not None:
        next_sort = max_sort + 1
    db.add(ProductImage(product_id=product_id, url=url, sort_order=next_sort))
    write_audit(db, user.id, "upload_image", "product", str(product_id), "{}")
    db.commit()
    product = (
        db.query(Product)
        .options(selectinload(Product.images), selectinload(Product.brand), selectinload(Product.category))
        .filter(Product.id == product_id)
        .one()
    )
    return _to_out(product)
