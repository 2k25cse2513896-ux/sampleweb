"""Public catalogue intelligence, quotes, checkout, orders and reservations."""

from datetime import timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.deps import get_current_customer, require_staff
from app.core.errors import AppError
from app.core.money import percent_of_rupees
from app.models.base import utc_now
from app.models.entities import Customer, LoyaltyLedger, Order, OrderEvent, OrderItem, PhoneModel, Product, ProductCompatibility, Reservation, User
from app.schemas.commerce import CartLine, OrderIn, QuoteIn, ReservationIn, StatusUpdate, UtrIn
from app.services.commerce import calculate_quote, expire_reservations, now_utc, parse_assistant_text, product_card, product_price, setting_int
from app.services.stock import apply_stock_change

router = APIRouter(tags=["commerce"])


def _order_dict(db: Session, order: Order) -> Dict[str, Any]:
    """Serialize an order with snapshots and timeline for both mobile and desktop clients."""
    return {"id": order.id, "order_no": order.order_no, "status": order.status, "fulfilment": order.fulfilment, "payment_method": order.payment_method, "payment_status": order.payment_status, "subtotal": order.subtotal, "discount": order.discount, "delivery_fee": order.delivery_fee, "total": order.total, "address": order.address, "note": order.note, "created_at": order.created_at, "items": [{"product_id": item.product_id, "name": item.name_snapshot, "price": item.price_snapshot, "qty": item.qty} for item in order.items], "events": [{"status": event.status, "note": event.note, "created_at": event.created_at} for event in order.events]}


@router.get("/api/phone-models")
def phone_models(q: str = "", db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Autocomplete phone models for compatibility search."""
    query = db.query(PhoneModel)
    clean = q.strip()
    if clean != "":
        like = "%" + clean + "%"
        query = query.filter(or_(PhoneModel.brand.ilike(like), PhoneModel.model_name.ilike(like)))
    rows = query.order_by(PhoneModel.brand.asc(), PhoneModel.model_name.asc()).limit(20).all()
    return [{"id": row.id, "brand": row.brand, "model_name": row.model_name, "slug": row.slug, "connector_type": row.connector_type} for row in rows]


@router.get("/api/compatible")
def compatible(model: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Return compatible protection and charging products grouped by type."""
    phone = db.query(PhoneModel).filter(or_(PhoneModel.slug == model, PhoneModel.model_name.ilike("%" + model + "%"))).first()
    if phone is None:
        raise AppError("not_found", "Phone model was not found.", 404)
    products = db.query(Product).join(ProductCompatibility, ProductCompatibility.product_id == Product.id).filter(ProductCompatibility.phone_model_id == phone.id, Product.is_active == True).options(selectinload(Product.category), selectinload(Product.brand), selectinload(Product.images)).all()  # noqa: E712
    grouped: Dict[str, List[Dict[str, Any]]] = {"covers": [], "glass": [], "chargers": [], "cables": [], "other": []}
    for product in products:
        category = product.category.name.lower() if product.category is not None else ""
        target = "other"
        if "cover" in category or "glass" in category:
            target = "covers"
        elif "charger" in category:
            target = "chargers"
        elif "cable" in category:
            target = "cables"
        grouped[target].append(product_card(product, product_price(db, product)))
    return {"phone": {"id": phone.id, "brand": phone.brand, "model_name": phone.model_name, "connector_type": phone.connector_type}, "groups": grouped}


@router.post("/api/bundles/suggest")
def suggest_bundle(model: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Suggest one in-stock cover/glass, charger and cable bundle."""
    data = compatible(model, db)
    chosen: List[Dict[str, Any]] = []
    for group in ["covers", "chargers", "cables"]:
        rows = data["groups"][group]
        if len(rows) > 0:
            chosen.append(rows[0])
    subtotal = 0
    for row in chosen:
        subtotal = subtotal + int(row["price"])
    discount_percent = setting_int(db, "bundle_discount_percent", 10)
    discount = percent_of_rupees(subtotal, discount_percent)
    return {"phone": data["phone"], "items": chosen, "subtotal": subtotal, "discount": discount, "total": subtotal - discount, "discount_percent": discount_percent}


@router.get("/api/compare")
def compare(ids: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Return products and normalized specs for a side-by-side comparison drawer."""
    parsed: List[int] = []
    for part in ids.split(","):
        try:
            parsed.append(int(part.strip()))
        except ValueError:
            continue
    products = db.query(Product).filter(Product.id.in_(parsed), Product.is_active == True).options(selectinload(Product.category), selectinload(Product.brand), selectinload(Product.images)).all()  # noqa: E712
    rows: List[Dict[str, Any]] = []
    for product in products:
        rows.append(product_card(product, product_price(db, product)))
    return {"items": rows}


@router.get("/api/flash-deals")
def flash_deals(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Expose only live deals and compute the effective price server-side."""
    from app.models.entities import FlashDeal
    rows = db.query(FlashDeal).filter(FlashDeal.is_active == True).all()  # noqa: E712
    output: List[Dict[str, Any]] = []
    current = now_utc()
    for deal in rows:
        starts = deal.starts_at.replace(tzinfo=deal.starts_at.tzinfo or current.tzinfo)
        ends = deal.ends_at.replace(tzinfo=deal.ends_at.tzinfo or current.tzinfo)
        if starts <= current and current <= ends:
            product = db.query(Product).options(selectinload(Product.category), selectinload(Product.brand), selectinload(Product.images)).filter(Product.id == deal.product_id).one_or_none()
            if product is not None and product.is_active:
                output.append({"id": deal.id, "product": product_card(product, deal.deal_price), "starts_at": deal.starts_at, "ends_at": deal.ends_at})
    return output


@router.post("/api/cart/quote")
def quote(body: QuoteIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Quote a client cart without trusting client prices."""
    items = [{"product_id": item.product_id, "qty": item.qty} for item in body.items]
    return calculate_quote(db, items, body.coupon_code, body.loyalty_points, body.fulfilment)


@router.post("/api/orders")
def create_order(body: OrderIn, customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Place an order atomically, decrement stock, and write one movement per line."""
    items = [{"product_id": item.product_id, "qty": item.qty} for item in body.items]
    quote_data = calculate_quote(db, items, body.coupon_code, body.loyalty_points, body.fulfilment)
    order_no = "TT-" + uuid4().hex[:8].upper()
    order = Order(order_no=order_no, customer_id=customer.id, status="new", fulfilment=body.fulfilment, payment_method=body.payment_method, payment_status="pending", subtotal=quote_data["subtotal"], discount=quote_data["discount"], delivery_fee=quote_data["delivery_fee"], total=quote_data["total"], coupon_id=quote_data["coupon_id"], address=body.address, note=body.note)
    db.add(order)
    db.flush()
    for line in quote_data["items"]:
        apply_stock_change(db, line["product_id"], -line["qty"], "sale", order_no, None)
        db.add(OrderItem(order_id=order.id, product_id=line["product_id"], name_snapshot=line["name"], price_snapshot=line["price"], qty=line["qty"]))
    db.add(OrderEvent(order_id=order.id, status="new", note="Order placed online."))
    if quote_data["coupon_id"] is not None:
        from app.models.entities import Coupon
        coupon = db.get(Coupon, quote_data["coupon_id"])
        if coupon is not None:
            coupon.used_count = coupon.used_count + 1
    db.commit()
    db.refresh(order)
    return _order_dict(db, order)


@router.get("/api/orders/{order_no}/track")
def track_order(order_no: str, phone: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Public order tracking protected by the order phone number."""
    order = db.query(Order).join(Customer).filter(Order.order_no == order_no, Customer.phone == phone.strip()).options(selectinload(Order.items), selectinload(Order.events)).one_or_none()
    if order is None:
        raise AppError("not_found", "Order number or phone did not match.", 404)
    return _order_dict(db, order)


@router.get("/api/customer/orders")
def customer_orders(customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List the signed-in customer's order history."""
    rows = db.query(Order).filter(Order.customer_id == customer.id).options(selectinload(Order.items), selectinload(Order.events)).order_by(Order.created_at.desc()).all()
    return [_order_dict(db, row) for row in rows]


@router.post("/api/customer/orders/{order_no}/cancel")
def cancel_order(order_no: str, customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Cancel only early orders and restore every reserved unit through the stock service."""
    order = db.query(Order).filter(Order.order_no == order_no, Order.customer_id == customer.id).options(selectinload(Order.items), selectinload(Order.events)).one_or_none()
    if order is None:
        raise AppError("not_found", "Order was not found.", 404)
    if order.status not in ["new", "confirmed"]:
        raise AppError("conflict", "This order can no longer be cancelled.", 409)
    for item in order.items:
        apply_stock_change(db, item.product_id, item.qty, "return", order.order_no, None)
    order.status = "cancelled"
    db.add(OrderEvent(order_id=order.id, status="cancelled", note="Cancelled by customer."))
    db.commit()
    return _order_dict(db, order)


@router.post("/api/customer/reservations")
def reserve(body: ReservationIn, customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Hold stock for the configured number of hours."""
    expire_reservations(db)
    product = db.get(Product, body.product_id)
    if product is None:
        raise AppError("not_found", "Product was not found.", 404)
    apply_stock_change(db, product.id, -body.qty, "reservation", str(customer.id), None)
    hours = setting_int(db, "reservation_hours", 24)
    row = Reservation(customer_id=customer.id, product_id=product.id, qty=body.qty, expires_at=utc_now() + timedelta(hours=hours), status="active")
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "product_id": row.product_id, "qty": row.qty, "expires_at": row.expires_at, "status": row.status}


@router.post("/api/admin/orders/{order_no}/status")
def update_order_status(order_no: str, body: StatusUpdate, user: User = Depends(require_staff), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Move an order through its timeline; cancellation restores stock exactly once."""
    order = db.query(Order).filter(Order.order_no == order_no).options(selectinload(Order.items), selectinload(Order.events)).one_or_none()
    if order is None:
        raise AppError("not_found", "Order was not found.", 404)
    previous_status = order.status
    if body.status == "cancelled" and order.status != "cancelled":
        for item in order.items:
            apply_stock_change(db, item.product_id, item.qty, "return", order.order_no, user.id)
    order.status = body.status
    db.add(OrderEvent(order_id=order.id, status=body.status, note=body.note))
    if body.status == "delivered" and previous_status != "delivered":
        customer = db.get(Customer, order.customer_id)
        if customer is not None:
            points = (order.total // 100) * setting_int(db, "loyalty_points_per_100_rupees", 1)
            if points > 0:
                customer.loyalty_points = customer.loyalty_points + points
                db.add(LoyaltyLedger(customer_id=customer.id, points=points, reason="delivered_order", order_id=order.id))
    db.commit()
    return _order_dict(db, order)


@router.post("/api/admin/orders/{order_no}/upi")
def verify_upi(order_no: str, body: UtrIn, user: User = Depends(require_staff), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Store a UTR and let staff verify payment from the admin screen."""
    order = db.query(Order).filter(Order.order_no == order_no).one_or_none()
    if order is None:
        raise AppError("not_found", "Order was not found.", 404)
    order.upi_utr = body.utr.strip()
    order.payment_status = "paid"
    db.add(OrderEvent(order_id=order.id, status=order.status, note="UPI payment verified by staff."))
    db.commit()
    return _order_dict(db, order)


@router.get("/api/orders/{order_no}/upi")
def upi_link(order_no: str, db: Session = Depends(get_db)) -> Dict[str, str]:
    """Return a standard UPI deep link for the order total."""
    order = db.query(Order).filter(Order.order_no == order_no).one_or_none()
    if order is None:
        raise AppError("not_found", "Order was not found.", 404)
    from app.models.entities import Setting
    upi = db.get(Setting, "upi_id")
    name = db.get(Setting, "upi_name")
    pa = upi.value if upi is not None else ""
    pn = name.value if name is not None else "TECH TOYS"
    link = "upi://pay?pa=" + quote(pa) + "&pn=" + quote(pn) + "&am=" + str(order.total) + "&tn=" + quote(order.order_no)
    return {"upi_link": link, "amount": str(order.total), "order_no": order.order_no}
