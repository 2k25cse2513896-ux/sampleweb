"""Customer OTP authentication for demo mode."""

from datetime import timedelta
from random import randint

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.rate_limit import limiter
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models.base import utc_now
from app.models.entities import Customer, OtpCode
from app.schemas.commerce import OtpRequest, OtpVerify
from app.schemas.common import TokenPair

router = APIRouter(prefix="/api/auth", tags=["customer-auth"])


@router.post("/customer/request-otp")
@limiter.limit("5/minute")
def request_otp(request: Request, body: OtpRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    """Create a short-lived hashed OTP; demo mode returns it so a shop owner can test locally."""
    _ = request.client
    phone = body.phone.strip()
    code = str(randint(100000, 999999))
    row = OtpCode(phone=phone, code_hash=hash_password(code), expires_at=utc_now() + timedelta(minutes=5), attempts=0, used=False)
    db.add(row)
    db.commit()
    result = {"message": "OTP sent."}
    if get_settings().demo_mode:
        result["demo_otp"] = code
    return result


@router.post("/customer/verify-otp", response_model=TokenPair)
@limiter.limit("10/minute")
def verify_otp(request: Request, body: OtpVerify, db: Session = Depends(get_db)) -> TokenPair:
    """Verify the newest unused OTP and create or update a customer record."""
    _ = request.client
    row = db.query(OtpCode).filter(OtpCode.phone == body.phone.strip(), OtpCode.used == False).order_by(OtpCode.id.desc()).first()  # noqa: E712
    expires_at = None
    if row is not None:
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=utc_now().tzinfo)
    if row is None or expires_at < utc_now():
        raise AppError("otp_invalid", "That OTP is expired. Request a new one.", 401)
    row.attempts = row.attempts + 1
    if verify_password(body.code, row.code_hash) is False:
        db.commit()
        raise AppError("otp_invalid", "That OTP is incorrect.", 401)
    row.used = True
    customer = db.query(Customer).filter(Customer.phone == body.phone.strip()).one_or_none()
    if customer is None:
        customer = Customer(name=body.name.strip(), phone=body.phone.strip(), loyalty_points=0)
        db.add(customer)
        db.flush()
    elif body.name.strip() != "":
        customer.name = body.name.strip()
    db.commit()
    subject = "c:" + str(customer.id)
    return TokenPair(access_token=create_access_token(subject), refresh_token=create_refresh_token(subject))
