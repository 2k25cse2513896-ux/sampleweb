"""Brand CRUD. Names are plain text (boAt, Sony, ...). No logos."""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_admin, require_staff
from app.core.errors import AppError
from app.models.entities import Brand, User
from app.schemas.catalogue import BrandIn, BrandOut
from app.services.audit import write_audit

router = APIRouter(tags=["brands"])


@router.get("/api/brands", response_model=List[BrandOut])
def list_brands(db: Session = Depends(get_db)) -> List[Brand]:
    return db.query(Brand).order_by(Brand.name).all()


@router.post("/api/admin/brands", response_model=BrandOut)
def create_brand(
    body: BrandIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> Brand:
    exists = db.query(Brand).filter(Brand.slug == body.slug).one_or_none()
    if exists is not None:
        raise AppError("conflict", "That brand slug is already used.", 409)
    row = Brand(name=body.name, slug=body.slug)
    db.add(row)
    db.flush()
    write_audit(db, user.id, "create", "brand", str(row.id), "{}")
    db.commit()
    db.refresh(row)
    return row


@router.put("/api/admin/brands/{brand_id}", response_model=BrandOut)
def update_brand(
    brand_id: int,
    body: BrandIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> Brand:
    row = db.get(Brand, brand_id)
    if row is None:
        raise AppError("not_found", "Brand was not found.", 404)
    row.name = body.name
    row.slug = body.slug
    write_audit(db, user.id, "update", "brand", str(row.id), "{}")
    db.commit()
    db.refresh(row)
    return row


@router.delete("/api/admin/brands/{brand_id}")
def delete_brand(
    brand_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict[str, str]:
    row = db.get(Brand, brand_id)
    if row is None:
        raise AppError("not_found", "Brand was not found.", 404)
    db.delete(row)
    write_audit(db, admin.id, "delete", "brand", str(brand_id), "{}")
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise AppError("conflict", "This brand still has products. Remove them first.", 409)
    return {"message": "Brand deleted."}
