"""Category CRUD. Public list, staff write, admin delete."""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_admin, require_staff
from app.core.errors import AppError
from app.models.entities import Category, User
from app.schemas.catalogue import CategoryIn, CategoryOut
from app.services.audit import write_audit

router = APIRouter(tags=["categories"])


@router.get("/api/categories", response_model=List[CategoryOut])
def list_categories(db: Session = Depends(get_db)) -> List[Category]:
    return db.query(Category).order_by(Category.sort_order, Category.name).all()


@router.post("/api/admin/categories", response_model=CategoryOut)
def create_category(
    body: CategoryIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> Category:
    exists = db.query(Category).filter(Category.slug == body.slug).one_or_none()
    if exists is not None:
        raise AppError("conflict", "That category slug is already used.", 409)
    row = Category(
        name=body.name,
        slug=body.slug,
        parent_id=body.parent_id,
        sort_order=body.sort_order,
    )
    db.add(row)
    db.flush()
    write_audit(db, user.id, "create", "category", str(row.id), "{}")
    db.commit()
    db.refresh(row)
    return row


@router.put("/api/admin/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    body: CategoryIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> Category:
    row = db.get(Category, category_id)
    if row is None:
        raise AppError("not_found", "Category was not found.", 404)
    row.name = body.name
    row.slug = body.slug
    row.parent_id = body.parent_id
    row.sort_order = body.sort_order
    write_audit(db, user.id, "update", "category", str(row.id), "{}")
    db.commit()
    db.refresh(row)
    return row


@router.delete("/api/admin/categories/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict[str, str]:
    row = db.get(Category, category_id)
    if row is None:
        raise AppError("not_found", "Category was not found.", 404)
    db.delete(row)
    write_audit(db, admin.id, "delete", "category", str(category_id), "{}")
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise AppError("conflict", "This category still has products. Deactivate products first.", 409)
    return {"message": "Category deleted."}
