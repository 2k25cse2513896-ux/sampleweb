"""
Single door for stock changes.

Every increase or decrease writes a stock_movements row in the same transaction.
Stock is never allowed to go below zero.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.entities import Product, StockMovement


def apply_stock_change(
    db: Session,
    product_id: int,
    change_qty: int,
    reason: str,
    reference_id: Optional[str],
    created_by: Optional[int],
) -> Product:
    """
    change_qty is signed: +10 restock, -1 sale.

    Caller must already be inside a transaction (db.begin or the request session).
    """
    product = db.get(Product, product_id)
    if product is None:
        raise AppError("not_found", "Product was not found.", 404)

    new_qty = product.stock_qty + change_qty
    if new_qty < 0:
        raise AppError(
            "out_of_stock",
            "Not enough stock for " + product.name + ".",
            409,
        )

    product.stock_qty = new_qty
    movement = StockMovement(
        product_id=product_id,
        change_qty=change_qty,
        reason=reason,
        reference_id=reference_id,
        created_by=created_by,
    )
    db.add(movement)
    db.flush()
    return product
