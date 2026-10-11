"""Stock never goes negative. Changes write a movement row."""

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.errors import AppError
from app.models.entities import Product, StockMovement
from app.services.stock import apply_stock_change


def test_negative_stock_is_rejected(client: object) -> None:
    db: Session = SessionLocal()
    try:
        product = db.query(Product).filter(Product.stock_qty == 0).first()
        assert product is not None
        raised = False
        try:
            apply_stock_change(db, product.id, -1, "sale", "test", None)
            db.commit()
        except AppError as exc:
            raised = True
            assert exc.code == "out_of_stock"
            db.rollback()
        assert raised is True
    finally:
        db.close()


def test_restock_writes_movement(client: object) -> None:
    db: Session = SessionLocal()
    try:
        product = db.query(Product).filter(Product.sku == "CB-001").one()
        before = product.stock_qty
        apply_stock_change(db, product.id, 2, "restock", "pytest", None)
        db.commit()
        db.refresh(product)
        assert product.stock_qty == before + 2
        move = (
            db.query(StockMovement)
            .filter(StockMovement.product_id == product.id, StockMovement.reference_id == "pytest")
            .one()
        )
        assert move.change_qty == 2
    finally:
        db.close()
