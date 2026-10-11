"""Admin dashboard and management endpoints used by the responsive admin shell."""

import csv
import hmac
import io
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.db import SessionLocal, get_db
from app.core.deps import require_admin, require_staff
from app.core.errors import AppError
from app.models.entities import AuditLog, Coupon, Enquiry, FlashDeal, Order, Product, RepairRequest, Reservation, Review, SearchZeroHit, StockMovement, User
from app.schemas.commerce import AssistantIn, CouponIn, FlashDealIn, StatusUpdate, StockIn, UserIn
from app.services.commerce import expire_reservations, parse_assistant_text, product_card, product_price
from app.core.security import hash_password
from app.core.config import get_settings
from app.core.startup_state import set_startup_state
from app.services.seed import reset_and_seed, seed_if_empty
from app.services.stock import apply_stock_change

router = APIRouter(tags=["admin"])


@router.post("/api/admin/seed")
def recover_seed(
    x_seed_token: str = Header(default="", alias="X-Seed-Token"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Safely recover an empty catalogue with a private token."""
    settings = get_settings()
    expected_token = settings.seed_token
    if expected_token == "":
        expected_token = settings.admin_password
    if expected_token == "" or not hmac.compare_digest(x_seed_token, expected_token):
        raise AppError("unauthorized", "A valid seed token is required.", 401)
    set_startup_state("seeding", "Recovery seed is in progress.")
    try:
        inserted = seed_if_empty(db, settings.admin_password)
        if inserted is None:
            set_startup_state("seeding", "Another seed is in progress.")
            raise AppError("seed_busy", "Another seed is already in progress.", 409)
        set_startup_state("ready", "Database is ready.")
        status = "seeded"
        if inserted == 0:
            status = "skipped"
        return {"status": status, "inserted_products": inserted}
    except AppError:
        raise
    except Exception:
        set_startup_state("failed", "Recovery seed failed.")
        raise


@router.get("/api/admin/dashboard")
def dashboard(_user: User = Depends(require_staff), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Return the headline metrics used by the admin dashboard."""
    today = datetime.now(timezone.utc).date()
    sales = db.query(func.coalesce(func.sum(Order.total), 0)).filter(Order.status != "cancelled").scalar()
    today_sales = db.query(func.coalesce(func.sum(Order.total), 0)).filter(Order.status != "cancelled", func.date(Order.created_at) == str(today)).scalar()
    low = db.query(Product).filter(Product.is_active == True, Product.stock_qty <= Product.low_stock_threshold).order_by(Product.stock_qty.asc()).limit(12).all()  # noqa: E712
    statuses = ["new", "confirmed", "packed", "ready_for_pickup", "out_for_delivery", "delivered", "cancelled"]
    status_counts: Dict[str, int] = {}
    for status in statuses:
        status_counts[status] = db.query(Order).filter(Order.status == status).count()
    return {"sales": int(sales or 0), "today_sales": int(today_sales or 0), "orders": db.query(Order).count(), "new_orders": db.query(Order).filter(Order.status == "new").count(), "pending_repairs": db.query(RepairRequest).filter(RepairRequest.status.in_(["booked", "received", "diagnosing", "in_repair"])).count(), "active_reservations": db.query(Reservation).filter(Reservation.status == "active").count(), "new_enquiries": db.query(Enquiry).filter(Enquiry.status == "new").count(), "status_counts": status_counts, "low_stock": [{"id": row.id, "name": row.name, "stock_qty": row.stock_qty, "threshold": row.low_stock_threshold} for row in low]}


@router.get("/api/admin/orders")
def admin_orders(_user: User = Depends(require_staff), db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Return orders for the desktop kanban and mobile list."""
    rows = db.query(Order).options(selectinload(Order.items), selectinload(Order.events)).order_by(Order.created_at.desc()).limit(200).all()
    return [{"order_no": row.order_no, "status": row.status, "payment_status": row.payment_status, "total": row.total, "fulfilment": row.fulfilment, "created_at": row.created_at, "items": [{"name": item.name_snapshot, "qty": item.qty} for item in row.items]} for row in rows]


@router.post("/api/admin/stock")
def stock(body: StockIn, user: User = Depends(require_staff), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Restock or adjust through the single stock service."""
    product = apply_stock_change(db, body.product_id, body.change_qty, body.reason, "admin", user.id)
    db.commit()
    return {"product_id": product.id, "stock_qty": product.stock_qty}


@router.get("/api/admin/stock/{product_id}/movements")
def movements(product_id: int, _user: User = Depends(require_staff), db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Show the audit trail for stock changes."""
    rows = db.query(StockMovement).filter(StockMovement.product_id == product_id).order_by(StockMovement.created_at.desc()).limit(100).all()
    return [{"change_qty": row.change_qty, "reason": row.reason, "reference_id": row.reference_id, "created_at": row.created_at} for row in rows]


@router.get("/api/admin/coupons", response_model=None)
def coupons(_user: User = Depends(require_staff), db: Session = Depends(get_db)) -> List[Coupon]:
    """List coupons for the admin editor."""
    return db.query(Coupon).order_by(Coupon.id.desc()).all()


@router.post("/api/admin/coupons", response_model=None)
def create_coupon(body: CouponIn, _user: User = Depends(require_admin), db: Session = Depends(get_db)) -> Coupon:
    """Create a coupon with server-side validation."""
    if db.query(Coupon).filter(Coupon.code == body.code.upper()).one_or_none() is not None:
        raise AppError("conflict", "Coupon code already exists.", 409)
    row = Coupon(code=body.code.upper(), type=body.type, value=body.value, min_order=body.min_order, max_uses=body.max_uses, expires_at=body.expires_at, is_active=body.is_active)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/api/admin/coupons/{coupon_id}")
def delete_coupon(coupon_id: int, _user: User = Depends(require_admin), db: Session = Depends(get_db)) -> Dict[str, str]:
    """Deactivate a coupon without destroying old order references."""
    row = db.get(Coupon, coupon_id)
    if row is None:
        raise AppError("not_found", "Coupon was not found.", 404)
    row.is_active = False
    db.commit()
    return {"message": "Coupon deactivated."}


@router.get("/api/admin/flash-deals", response_model=None)
def deals(_user: User = Depends(require_staff), db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List flash deals with product names."""
    rows = db.query(FlashDeal).order_by(FlashDeal.ends_at.desc()).all()
    output: List[Dict[str, Any]] = []
    for row in rows:
        product = db.get(Product, row.product_id)
        output.append({"id": row.id, "product_id": row.product_id, "product_name": product.name if product is not None else "", "deal_price": row.deal_price, "starts_at": row.starts_at, "ends_at": row.ends_at, "is_active": row.is_active})
    return output


@router.post("/api/admin/flash-deals", response_model=None)
def create_deal(body: FlashDealIn, _user: User = Depends(require_admin), db: Session = Depends(get_db)) -> FlashDeal:
    """Create a flash deal; the public endpoint decides whether it is live."""
    if body.ends_at <= body.starts_at:
        raise AppError("validation_error", "Deal end must be after its start.", 422)
    if db.get(Product, body.product_id) is None:
        raise AppError("not_found", "Product was not found.", 404)
    row = FlashDeal(product_id=body.product_id, deal_price=body.deal_price, starts_at=body.starts_at, ends_at=body.ends_at, is_active=body.is_active)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/api/admin/flash-deals/{deal_id}")
def delete_deal(deal_id: int, _user: User = Depends(require_admin), db: Session = Depends(get_db)) -> Dict[str, str]:
    """Deactivate a flash deal."""
    row = db.get(FlashDeal, deal_id)
    if row is None:
        raise AppError("not_found", "Deal was not found.", 404)
    row.is_active = False
    db.commit()
    return {"message": "Deal deactivated."}


@router.get("/api/admin/repairs", response_model=None)
def admin_repairs(_user: User = Depends(require_staff), db: Session = Depends(get_db)) -> List[RepairRequest]:
    """List repair tickets for the admin queue."""
    return db.query(RepairRequest).order_by(RepairRequest.created_at.desc()).limit(200).all()


@router.post("/api/admin/repairs/{repair_id}/status")
def repair_status(repair_id: int, body: StatusUpdate, _user: User = Depends(require_staff), db: Session = Depends(get_db)) -> Dict[str, str]:
    """Update repair status and append a timeline event."""
    row = db.get(RepairRequest, repair_id)
    if row is None:
        raise AppError("not_found", "Repair ticket was not found.", 404)
    row.status = body.status
    from app.models.entities import RepairEvent
    db.add(RepairEvent(repair_id=row.id, status=body.status, note=body.note))
    db.commit()
    return {"ticket_no": row.ticket_no, "status": row.status}


@router.get("/api/admin/reservations", response_model=None)
def admin_reservations(_user: User = Depends(require_staff), db: Session = Depends(get_db)) -> List[Reservation]:
    """List active and expired stock holds."""
    expire_reservations(db)
    return db.query(Reservation).order_by(Reservation.id.desc()).limit(200).all()


@router.post("/api/admin/reservations/{reservation_id}/cancel")
def cancel_reservation(reservation_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)) -> Dict[str, str]:
    """Cancel an active hold and restore its stock exactly once."""
    row = db.get(Reservation, reservation_id)
    if row is None:
        raise AppError("not_found", "Reservation was not found.", 404)
    if row.status == "active":
        apply_stock_change(db, row.product_id, row.qty, "reservation", "cancel-" + str(row.id), user.id)
        row.status = "cancelled"
        db.commit()
    return {"message": "Reservation cancelled."}


@router.get("/api/admin/customers", response_model=None)
def admin_customers(_user: User = Depends(require_staff), db: Session = Depends(get_db)) -> List[Any]:
    """List customer profiles for the owner."""
    from app.models.entities import Customer
    return db.query(Customer).order_by(Customer.created_at.desc()).limit(500).all()


@router.get("/api/admin/users", response_model=None)
def admin_users(_admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> List[User]:
    """List staff accounts without password hashes."""
    return db.query(User).order_by(User.id.asc()).all()


@router.post("/api/admin/users", response_model=None)
def create_user(body: UserIn, _admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> User:
    """Create an admin or staff login."""
    if body.role not in ["admin", "staff"]:
        raise AppError("validation_error", "Role must be admin or staff.", 422)
    if db.query(User).filter(User.email == body.email.lower()).one_or_none() is not None:
        raise AppError("conflict", "Email already exists.", 409)
    row = User(name=body.name, email=body.email.lower(), password_hash=hash_password(body.password), role=body.role, is_active=body.is_active)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/api/admin/reviews", response_model=None)
def reviews(_user: User = Depends(require_staff), db: Session = Depends(get_db)) -> List[Review]:
    """List reviews for moderation."""
    return db.query(Review).order_by(Review.created_at.desc()).limit(200).all()


@router.post("/api/admin/reviews/{review_id}/approve")
def approve_review(review_id: int, _user: User = Depends(require_staff), db: Session = Depends(get_db)) -> Dict[str, str]:
    """Approve a customer review."""
    row = db.get(Review, review_id)
    if row is None:
        raise AppError("not_found", "Review was not found.", 404)
    row.is_approved = True
    db.commit()
    return {"message": "Review approved."}


@router.get("/api/admin/enquiries", response_model=None)
def enquiries(_user: User = Depends(require_staff), db: Session = Depends(get_db)) -> List[Enquiry]:
    """List the contact inbox."""
    return db.query(Enquiry).order_by(Enquiry.created_at.desc()).limit(200).all()


@router.get("/api/admin/insights", response_model=None)
def insights(_user: User = Depends(require_staff), db: Session = Depends(get_db)) -> List[SearchZeroHit]:
    """Show searches that did not find stock."""
    return db.query(SearchZeroHit).order_by(SearchZeroHit.hit_count.desc()).limit(100).all()


@router.get("/api/admin/report/daily.csv")
def daily_report(_user: User = Depends(require_staff), db: Session = Depends(get_db)) -> Response:
    """Export a small CSV sales report for the owner."""
    rows = db.query(Order).filter(Order.status != "cancelled").order_by(Order.created_at.desc()).limit(500).all()
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["order_no", "status", "total", "created_at"])
    for row in rows:
        writer.writerow([row.order_no, row.status, row.total, row.created_at.isoformat()])
    return Response(content=stream.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=daily-sales.csv"})


@router.post("/api/admin/reset-demo")
def reset_demo(_admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> Dict[str, str]:
    """Reset all demo rows and seed them again; intentionally admin-only."""
    reset_and_seed(db)
    return {"message": "Demo data reset."}


@router.post("/api/assistant")
def assistant(body: AssistantIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Answer shopping questions from database products only."""
    parsed = parse_assistant_text(body.text)
    query = db.query(Product).filter(Product.is_active == True)  # noqa: E712
    if parsed["budget"] is not None:
        query = query.filter(Product.price <= parsed["budget"])
    if len(parsed["categories"]) > 0:
        query = query.join(Product.category).filter(Product.category.has(slug=parsed["categories"][0]))
    rows = query.order_by(Product.is_featured.desc(), Product.stock_qty.desc(), Product.price.asc()).limit(6).all()
    cards: List[Dict[str, Any]] = []
    for row in rows:
        cards.append(product_card(row, product_price(db, row)))
    reply = "I found " + str(len(cards)) + " options from the live catalogue."
    if len(cards) == 0:
        reply = "I could not find an in-stock match yet. Try a higher budget or another category."
    return {"reply": reply, "parsed": parsed, "products": cards}
