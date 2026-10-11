"""Validated request bodies for commerce and customer features."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class OtpRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=20)


class OtpVerify(BaseModel):
    phone: str = Field(min_length=7, max_length=20)
    code: str = Field(min_length=4, max_length=8)
    name: str = Field(default="Customer", min_length=1, max_length=120)


class CartLine(BaseModel):
    product_id: int = Field(gt=0)
    qty: int = Field(gt=0, le=20)


class QuoteIn(BaseModel):
    items: List[CartLine] = Field(min_length=1)
    coupon_code: Optional[str] = None
    loyalty_points: int = Field(default=0, ge=0)
    fulfilment: str = "pickup_15min"


class OrderIn(QuoteIn):
    payment_method: str = "pay_at_shop"
    address: str = ""
    note: str = ""


class StatusUpdate(BaseModel):
    status: str = Field(min_length=2, max_length=40)
    note: str = ""


class UtrIn(BaseModel):
    utr: str = Field(min_length=4, max_length=64)


class ReservationIn(BaseModel):
    product_id: int = Field(gt=0)
    qty: int = Field(gt=0, le=20)


class RepairIn(BaseModel):
    device_brand: str = Field(min_length=2, max_length=80)
    device_model: str = Field(min_length=2, max_length=120)
    issue_type: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=2000)
    preferred_slot: str = Field(default="", max_length=80)


class TradeInIn(BaseModel):
    brand: str = Field(min_length=2, max_length=80)
    model: str = Field(min_length=2, max_length=120)
    storage: str = Field(min_length=1, max_length=40)
    condition: str = Field(min_length=2, max_length=20)
    has_box: bool = False
    has_bill: bool = False


class ReviewIn(BaseModel):
    product_id: int = Field(gt=0)
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=1000)


class EnquiryIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=7, max_length=20)
    message: str = Field(min_length=2, max_length=2000)
    source: str = "contact"


class CouponIn(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    type: str = "flat"
    value: int = Field(ge=0)
    min_order: int = Field(default=0, ge=0)
    max_uses: int = Field(default=0, ge=0)
    expires_at: Optional[datetime] = None
    is_active: bool = True


class FlashDealIn(BaseModel):
    product_id: int = Field(gt=0)
    deal_price: int = Field(ge=0)
    starts_at: datetime
    ends_at: datetime
    is_active: bool = True


class AssistantIn(BaseModel):
    text: str = Field(min_length=2, max_length=500)


class StockIn(BaseModel):
    product_id: int = Field(gt=0)
    change_qty: int
    reason: str = Field(min_length=2, max_length=40)


class UserIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: str = "staff"
    is_active: bool = True
