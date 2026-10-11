"""Offline product quick-add automation for the staff portal.

This intentionally uses a small, deterministic parser instead of an external
LLM.  Store owners can type a short Hinglish sentence and get a validated
product draft without exposing catalogue data or credentials to a third party.
"""

import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.entities import Brand, Category, Product


CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "earbuds": ("earbuds", "earbud", "tws", "buds"),
    "headphones": ("headphones", "headphone", "headset"),
    "neckbands": ("neckbands", "neckband"),
    "chargers": ("chargers", "charger", "charging"),
    "cables": ("cables", "cable", "wire"),
    "power-banks": ("power banks", "powerbank", "power bank"),
    "protection": ("covers", "cover", "tempered", "glass", "case"),
    "gadgets": ("smartwatch", "smart watch", "watch", "speaker", "pendrive", "pen drive", "flash drive", "memory card", "storage"),
}


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _number_after(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return int(match.group(1).replace(",", "")) if match else None


def _find_category(prompt: str, categories: list[Category]) -> Category | None:
    lowered = prompt.lower()
    matches: list[tuple[int, Category]] = []
    for category in categories:
        aliases = CATEGORY_ALIASES.get(category.slug, (category.slug, category.name.lower()))
        for alias in aliases:
            if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", lowered):
                matches.append((len(alias), category))
    return sorted(matches, key=lambda item: item[0], reverse=True)[0][1] if matches else None


def _find_brand(prompt: str, brands: list[Brand]) -> Brand | None:
    lowered = prompt.lower()
    matches = [brand for brand in brands if re.search(rf"(?<![a-z]){re.escape(brand.name.lower())}(?![a-z])", lowered)]
    return sorted(matches, key=lambda brand: len(brand.name), reverse=True)[0] if matches else None


def _extract_name(prompt: str, brand: Brand, category: Category) -> str:
    name = prompt.strip()
    # Remove labelled values first, otherwise their digits can look like a model number.
    name = re.sub(r"\b(?:price|rate|daam|mrp|stock|qty|quantity|pieces?|pcs|units?)\b\s*[:=\-]?\s*₹?\s*[\d,]+", " ", name, flags=re.IGNORECASE)
    name = re.sub(r"₹\s*[\d,]+|\brs\.?\s*[\d,]+|\b[\d,]+\s*(?:rupaye|rupees)\b", " ", name, flags=re.IGNORECASE)
    aliases = CATEGORY_ALIASES.get(category.slug, (category.slug, category.name.lower()))
    # Keep words that are commonly part of a model name (Nord Buds, Go speaker,
    # ColorFit watch); the category has already been detected above.
    removable_aliases = set(aliases) - {"buds", "watch", "speaker", "storage"}
    for alias in sorted(removable_aliases, key=len, reverse=True):
        name = re.sub(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", " ", name, flags=re.IGNORECASE)
    name = re.sub(rf"(?<![a-z]){re.escape(brand.name)}(?![a-z])", " ", name, flags=re.IGNORECASE)
    name = re.sub(r"\b(?:add|create|new|product|ka|ki|wala|wali|with|for|please|kar do|kardo|banao|banana|me|mein)\b", " ", name, flags=re.IGNORECASE)
    name = re.sub(r"[^\w\s&+.-]", " ", name)
    name = re.sub(r"\s+", " ", name).strip(" .,-")
    return f"{brand.name} {name}".strip() if name else brand.name


def parse_product_prompt(db: Session, prompt: str) -> dict[str, Any]:
    """Parse a short Hinglish prompt into validated ProductIn-compatible data."""
    text = re.sub(r"\s+", " ", prompt.strip())
    if len(text) < 8:
        raise AppError("validation_error", "Prompt thoda detail me likho: brand, product, category, price aur stock.", 422)

    categories = db.query(Category).all()
    brands = db.query(Brand).all()
    category = _find_category(text, categories)
    brand = _find_brand(text, brands)
    price = _number_after(r"\b(?:price|rate|daam)\b\s*[:=\-]?\s*₹?\s*([\d,]+)", text)
    if price is None:
        price = _number_after(r"₹\s*([\d,]+)", text)
    if price is None:
        price = _number_after(r"\brs\.?\s*([\d,]+)", text)
    mrp = _number_after(r"\bmrp\b\s*[:=\-]?\s*₹?\s*([\d,]+)", text)
    stock = _number_after(r"\b(?:stock|qty|quantity|pieces?|pcs|units?)\b\s*[:=\-]?\s*([\d,]+)", text)

    missing: list[str] = []
    if brand is None:
        missing.append("brand")
    if category is None:
        missing.append("category (jaise earbuds/charger/cable)")
    if price is None:
        missing.append("price")
    if stock is None:
        missing.append("stock")
    if missing:
        raise AppError("validation_error", "Prompt me ye details missing hain: " + ", ".join(missing) + ".", 422)
    assert brand is not None and category is not None and price is not None and stock is not None
    if price <= 0 or stock < 0:
        raise AppError("validation_error", "Price positive aur stock zero ya usse zyada hona chahiye.", 422)
    if mrp is None:
        mrp = max(price, int(round(price * 1.2)))
    if mrp < price:
        raise AppError("validation_error", "MRP selling price se kam nahi ho sakta.", 422)

    name = _extract_name(text, brand, category)
    base_slug = _slugify(name) or f"product-{uuid.uuid4().hex[:8]}"
    slug = base_slug
    while db.query(Product).filter(Product.slug == slug).first() is not None:
        slug = f"{base_slug}-{uuid.uuid4().hex[:5]}"
    # SKU is always unique and visibly marks products created from the quick-add flow.
    sku = f"AI-{uuid.uuid4().hex[:8].upper()}"
    return {
        "sku": sku,
        "name": name,
        "slug": slug,
        "description": f"{name} — genuine catalogue item for everyday use.",
        "category_id": category.id,
        "brand_id": brand.id,
        "price": price,
        "mrp": mrp,
        "cost_price": max(1, int(round(price * 0.65))),
        "stock_qty": stock,
        "low_stock_threshold": 3,
        "warranty_months": 6,
        "is_genuine_verified": True,
        "is_active": True,
        "is_featured": False,
        "specs_json": "{}",
        "category_slug": category.slug,
    }
