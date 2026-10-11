"""Server-side pricing and stock-safe commerce helpers."""

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.money import percent_of_rupees
from app.models.entities import Coupon, FlashDeal, Product, Reservation, Setting


def now_utc() -> datetime:
    """Return an aware UTC timestamp for business rules."""
    return datetime.now(timezone.utc)


def active_deal(db: Session, product_id: int) -> Optional[FlashDeal]:
    """Return the currently active deal with the lowest price."""
    deals = db.query(FlashDeal).filter(FlashDeal.product_id == product_id, FlashDeal.is_active == True).all()  # noqa: E712
    selected: Optional[FlashDeal] = None
    current = now_utc()
    for deal in deals:
        starts = deal.starts_at
        ends = deal.ends_at
        if starts.tzinfo is None:
            starts = starts.replace(tzinfo=timezone.utc)
        if ends.tzinfo is None:
            ends = ends.replace(tzinfo=timezone.utc)
        if starts <= current and current <= ends:
            if selected is None or deal.deal_price < selected.deal_price:
                selected = deal
    return selected


def product_price(db: Session, product: Product) -> int:
    """Compute the effective server price for one product."""
    deal = active_deal(db, product.id)
    if deal is None:
        return product.price
    return deal.deal_price


def setting_int(db: Session, key: str, fallback: int) -> int:
    """Read an integer setting without allowing malformed admin input to crash checkout."""
    row = db.get(Setting, key)
    if row is None:
        return fallback
    try:
        return int(row.value)
    except ValueError:
        return fallback


def calculate_quote(
    db: Session,
    items: List[Dict[str, int]],
    coupon_code: Optional[str],
    loyalty_points: int,
    fulfilment: str,
) -> Dict[str, Any]:
    """Calculate every rupee on the server and return a JSON-safe quote."""
    lines: List[Dict[str, Any]] = []
    subtotal = 0
    for raw in items:
        product_id = int(raw["product_id"])
        qty = int(raw["qty"])
        product = db.get(Product, product_id)
        if product is None or product.is_active is False:
            raise AppError("not_found", "One product is no longer available.", 404)
        if qty <= 0:
            raise AppError("validation_error", "Quantity must be positive.", 422)
        if product.stock_qty < qty:
            raise AppError("out_of_stock", "Not enough stock for " + product.name + ".", 409)
        price = product_price(db, product)
        line_total = price * qty
        subtotal = subtotal + line_total
        lines.append({"product_id": product.id, "name": product.name, "qty": qty, "price": price, "line_total": line_total})

    discount = 0
    coupon_id: Optional[int] = None
    if coupon_code is not None and coupon_code.strip() != "":
        coupon = db.query(Coupon).filter(Coupon.code == coupon_code.strip().upper()).one_or_none()
        if coupon is None or coupon.is_active is False:
            raise AppError("invalid_coupon", "That coupon is not active.", 422)
        if coupon.expires_at is not None:
            expiry = coupon.expires_at
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if expiry < now_utc():
                raise AppError("invalid_coupon", "That coupon has expired.", 422)
        if coupon.max_uses > 0 and coupon.used_count >= coupon.max_uses:
            raise AppError("invalid_coupon", "That coupon has reached its usage limit.", 422)
        if subtotal < coupon.min_order:
            raise AppError("invalid_coupon", "This coupon needs a higher order value.", 422)
        if coupon.type == "percent":
            discount = percent_of_rupees(subtotal, coupon.value)
        else:
            discount = coupon.value
        if discount > subtotal:
            discount = subtotal
        coupon_id = coupon.id

    loyalty = loyalty_points
    if loyalty > subtotal - discount:
        loyalty = subtotal - discount
    if loyalty < 0:
        loyalty = 0
    discount = discount + loyalty

    delivery_fee = 0
    if fulfilment == "delivery_kanpur":
        threshold = setting_int(db, "free_delivery_threshold_rupees", 499)
        if subtotal - discount < threshold:
            delivery_fee = setting_int(db, "delivery_fee_rupees", 40)
    total = subtotal - discount + delivery_fee
    return {"items": lines, "subtotal": subtotal, "discount": discount, "delivery_fee": delivery_fee, "total": total, "coupon_id": coupon_id, "loyalty_redeemed": loyalty}


def parse_assistant_text(text: str) -> Dict[str, Any]:
    """Extract simple budget, category and phone-model hints from English or Hinglish."""
    lowered = text.lower()
    budget: Optional[int] = None
    matches = re.findall(r"(?:under|below|upto|up to)\s*₹?\s*(\d+)", lowered)
    if len(matches) == 0:
        matches = re.findall(r"₹?\s*(\d+)\s*(?:tak|rupaye tak|ke andar)", lowered)
    if len(matches) > 0:
        budget = int(matches[0])
    categories: List[str] = []
    for key, value in [("earbud", "earbuds"), ("headphone", "headphones"), ("neckband", "neckbands"), ("charger", "chargers"), ("cable", "cables"), ("power bank", "power-banks"), ("cover", "protection")]:
        if key in lowered:
            categories.append(value)
    return {"budget": budget, "categories": categories, "query": text.strip()}


def product_card(product: Product, price: int) -> Dict[str, Any]:
    """Build the public product shape used by finder and assistant cards."""
    specs: Dict[str, Any] = {}
    try:
        decoded = json.loads(product.specs_json)
        if isinstance(decoded, dict):
            specs = decoded
    except json.JSONDecodeError:
        specs = {}
    images: List[Dict[str, Any]] = []
    for image in product.images:
        images.append({"id": image.id, "url": image.url, "sort_order": image.sort_order})
    brand_name = product.brand.name if product.brand is not None else None
    category_name = product.category.name if product.category is not None else None
    return {"id": product.id, "sku": product.sku, "barcode": product.barcode, "name": product.name, "slug": product.slug, "description": product.description, "category_id": product.category_id, "brand_id": product.brand_id, "price": price, "mrp": product.mrp, "stock_qty": product.stock_qty, "low_stock_threshold": product.low_stock_threshold, "warranty_months": product.warranty_months, "is_genuine_verified": product.is_genuine_verified, "is_active": product.is_active, "is_featured": product.is_featured, "specs_json": product.specs_json, "specs": specs, "images": images, "brand_name": brand_name, "category_name": category_name}


def expire_reservations(db: Session) -> int:
    """Release expired holds once and record the stock restoration."""
    from app.services.stock import apply_stock_change

    rows = db.query(Reservation).filter(Reservation.status == "active").all()
    released = 0
    current = now_utc()
    for row in rows:
        expiry = row.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=current.tzinfo)
        if expiry < current:
            apply_stock_change(db, row.product_id, row.qty, "reservation", "expiry-" + str(row.id), None)
            row.status = "expired"
            released = released + 1
    if released > 0:
        db.commit()
    return released
