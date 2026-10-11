"""Category, brand and product schemas. Prices are integer rupees."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import OrmModel


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=140)
    parent_id: Optional[int] = None
    sort_order: int = 0


class CategoryOut(OrmModel):
    id: int
    name: str
    slug: str
    parent_id: Optional[int]
    sort_order: int


class BrandIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=140)


class BrandOut(OrmModel):
    id: int
    name: str
    slug: str


class ProductIn(BaseModel):
    sku: str
    barcode: Optional[str] = None
    name: str
    slug: str
    description: str = ""
    category_id: int
    brand_id: int
    price: int = Field(ge=0)
    mrp: int = Field(ge=0)
    cost_price: int = Field(ge=0)
    stock_qty: int = Field(ge=0, default=0)
    low_stock_threshold: int = Field(ge=0, default=3)
    warranty_months: int = Field(ge=0, default=6)
    is_genuine_verified: bool = True
    is_active: bool = True
    is_featured: bool = False
    specs_json: str = "{}"


class ProductPromptIn(BaseModel):
    prompt: str = Field(min_length=8, max_length=500)


class ProductUpdate(BaseModel):
    sku: Optional[str] = None
    barcode: Optional[str] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    price: Optional[int] = Field(default=None, ge=0)
    mrp: Optional[int] = Field(default=None, ge=0)
    cost_price: Optional[int] = Field(default=None, ge=0)
    low_stock_threshold: Optional[int] = Field(default=None, ge=0)
    warranty_months: Optional[int] = Field(default=None, ge=0)
    is_genuine_verified: Optional[bool] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    specs_json: Optional[str] = None


class ProductImageOut(OrmModel):
    id: int
    url: str
    sort_order: int


class ProductOut(OrmModel):
    id: int
    sku: str
    barcode: Optional[str]
    name: str
    slug: str
    description: str
    category_id: int
    brand_id: int
    price: int
    mrp: int
    cost_price: int
    stock_qty: int
    low_stock_threshold: int
    warranty_months: int
    is_genuine_verified: bool
    is_active: bool
    is_featured: bool
    specs_json: str
    created_at: datetime
    updated_at: datetime
    images: List[ProductImageOut] = []
    brand_name: Optional[str] = None
    category_name: Optional[str] = None
    average_rating_tenths: Optional[int] = None


class SettingOut(BaseModel):
    key: str
    value: str


class SettingPut(BaseModel):
    items: List[SettingOut]


class UserOut(OrmModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool
