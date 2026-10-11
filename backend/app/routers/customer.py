"""Signed-in customer features: repairs, warranty, wishlist, alerts, reviews and leads."""

from datetime import timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_customer, require_admin, require_staff
from app.core.errors import AppError
from app.models.base import utc_now
from app.models.entities import Alert, Claim, Customer, Enquiry, LoyaltyLedger, Product, RepairEvent, RepairRequest, Reservation, Review, TradeInRequest, TradeInRule, User, Warranty, WishlistItem
from app.schemas.commerce import EnquiryIn, RepairIn, ReviewIn, TradeInIn
from app.services.commerce import setting_int
from app.services.commerce import expire_reservations

router = APIRouter(tags=["customer-features"])


@router.get("/api/customer/me")
def customer_me(customer: Customer = Depends(get_current_customer)) -> Dict[str, Any]:
    """Return the customer profile used by the account page."""
    return {"id": customer.id, "name": customer.name, "phone": customer.phone, "email": customer.email, "loyalty_points": customer.loyalty_points}


@router.get("/api/customer/wishlist")
def wishlist(customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Return wishlist products with current server prices."""
    from app.services.commerce import product_card, product_price
    rows = db.query(WishlistItem).filter(WishlistItem.customer_id == customer.id).all()
    output: List[Dict[str, Any]] = []
    for row in rows:
        product = db.get(Product, row.product_id)
        if product is not None:
            output.append(product_card(product, product_price(db, product)))
    return output


@router.post("/api/customer/wishlist/{product_id}")
def add_wishlist(product_id: int, customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)) -> Dict[str, str]:
    """Idempotently add a product to the wishlist."""
    if db.get(Product, product_id) is None:
        raise AppError("not_found", "Product was not found.", 404)
    exists = db.query(WishlistItem).filter(WishlistItem.customer_id == customer.id, WishlistItem.product_id == product_id).one_or_none()
    if exists is None:
        db.add(WishlistItem(customer_id=customer.id, product_id=product_id))
        db.commit()
    return {"message": "Added to wishlist."}


@router.delete("/api/customer/wishlist/{product_id}")
def remove_wishlist(product_id: int, customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)) -> Dict[str, str]:
    """Remove a wishlist item."""
    row = db.query(WishlistItem).filter(WishlistItem.customer_id == customer.id, WishlistItem.product_id == product_id).one_or_none()
    if row is not None:
        db.delete(row)
        db.commit()
    return {"message": "Removed from wishlist."}


@router.post("/api/customer/alerts/{product_id}")
def add_alert(product_id: int, alert_type: str = "back_in_stock", target_price: int | None = None, customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Create a back-in-stock or price-drop alert."""
    if db.get(Product, product_id) is None:
        raise AppError("not_found", "Product was not found.", 404)
    row = Alert(customer_id=customer.id, product_id=product_id, type=alert_type, target_price=target_price, is_active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "message": "Alert saved."}


@router.get("/api/customer/reservations")
def reservations(customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List stock holds belonging to the signed-in customer."""
    expire_reservations(db)
    rows = db.query(Reservation).filter(Reservation.customer_id == customer.id).order_by(Reservation.id.desc()).all()
    return [{"id": row.id, "product_id": row.product_id, "qty": row.qty, "expires_at": row.expires_at, "status": row.status} for row in rows]


@router.get("/api/customer/alerts")
def alerts(customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List alert subscriptions and their trigger state."""
    rows = db.query(Alert).filter(Alert.customer_id == customer.id).order_by(Alert.id.desc()).all()
    return [{"id": row.id, "product_id": row.product_id, "type": row.type, "target_price": row.target_price, "is_active": row.is_active, "triggered_at": row.triggered_at} for row in rows]


@router.post("/api/customer/repairs")
def create_repair(body: RepairIn, customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Book a repair and create the first timeline event."""
    ticket = "RP-" + str(utc_now().strftime("%y%m%d%H%M%S")) + "-" + str(customer.id)
    row = RepairRequest(ticket_no=ticket, customer_id=customer.id, device_brand=body.device_brand, device_model=body.device_model, issue_type=body.issue_type, description=body.description, preferred_slot=body.preferred_slot, status="booked", estimate_amount=0)
    db.add(row)
    db.flush()
    db.add(RepairEvent(repair_id=row.id, status="booked", note="Repair request received."))
    db.commit()
    return {"ticket_no": row.ticket_no, "status": row.status, "created_at": row.created_at}


@router.get("/api/customer/repairs")
def repairs(customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List repair tickets with their status timeline."""
    rows = db.query(RepairRequest).filter(RepairRequest.customer_id == customer.id).order_by(RepairRequest.created_at.desc()).all()
    output: List[Dict[str, Any]] = []
    for row in rows:
        output.append({"ticket_no": row.ticket_no, "device_brand": row.device_brand, "device_model": row.device_model, "issue_type": row.issue_type, "status": row.status, "estimate_amount": row.estimate_amount, "events": [{"status": event.status, "note": event.note, "created_at": event.created_at} for event in row.events]})
    return output


@router.get("/api/customer/warranties")
def warranties(customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Return warranty vault rows and expiry dates."""
    rows = db.query(Warranty).filter(Warranty.customer_id == customer.id).all()
    output: List[Dict[str, Any]] = []
    for row in rows:
        product = db.get(Product, row.product_id)
        output.append({"id": row.id, "product_id": row.product_id, "product_name": product.name if product is not None else "Product", "serial_no": row.serial_no, "purchase_date": row.purchase_date, "expiry_date": row.expiry_date, "bill_image_url": row.bill_image_url, "reminder_sent": row.reminder_sent})
    return output


@router.post("/api/customer/warranties/{warranty_id}/claims")
def claim(warranty_id: int, issue: str, customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Open a warranty claim for a warranty owned by the signed-in customer."""
    warranty = db.query(Warranty).filter(Warranty.id == warranty_id, Warranty.customer_id == customer.id).one_or_none()
    if warranty is None:
        raise AppError("not_found", "Warranty was not found.", 404)
    row = Claim(warranty_id=warranty_id, issue=issue.strip(), status="open")
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "status": row.status, "created_at": row.created_at}


@router.post("/api/customer/trade-in")
def trade_in(body: TradeInIn, customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Estimate a trade-in from editable rules and save it as a lead."""
    rule = db.query(TradeInRule).filter(TradeInRule.brand.ilike(body.brand), TradeInRule.condition == body.condition).order_by(TradeInRule.id.asc()).first()
    if rule is None:
        minimum = 500
        maximum = 2500
    else:
        minimum = rule.min_rupees
        maximum = rule.max_rupees
    if body.has_box:
        minimum = minimum + 200
        maximum = maximum + 200
    if body.has_bill:
        minimum = minimum + 200
        maximum = maximum + 200
    row = TradeInRequest(customer_id=customer.id, brand=body.brand, model=body.model, storage=body.storage, condition=body.condition, has_box=body.has_box, has_bill=body.has_bill, estimated_min=minimum, estimated_max=maximum, status="new")
    db.add(row)
    db.commit()
    return {"estimated_min": minimum, "estimated_max": maximum, "status": row.status}


@router.post("/api/customer/reviews")
def create_review(body: ReviewIn, customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Save a review for admin moderation."""
    if db.get(Product, body.product_id) is None:
        raise AppError("not_found", "Product was not found.", 404)
    row = Review(product_id=body.product_id, customer_id=customer.id, rating=body.rating, comment=body.comment, is_approved=False)
    db.add(row)
    db.commit()
    return {"message": "Review submitted for approval."}


@router.post("/api/enquiries")
def enquiry(body: EnquiryIn, db: Session = Depends(get_db)) -> Dict[str, str]:
    """Save a contact enquiry for the admin inbox."""
    db.add(Enquiry(name=body.name, phone=body.phone, message=body.message, source=body.source, status="new"))
    db.commit()
    return {"message": "Thanks. The shop will contact you shortly."}


@router.get("/api/customer/loyalty")
def loyalty(customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Return balance plus the signed ledger."""
    rows = db.query(LoyaltyLedger).filter(LoyaltyLedger.customer_id == customer.id).order_by(LoyaltyLedger.created_at.desc()).all()
    return {"balance": customer.loyalty_points, "items": [{"points": row.points, "reason": row.reason, "created_at": row.created_at} for row in rows]}
