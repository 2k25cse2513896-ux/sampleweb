"""Read and write the settings key/value table. Shop identity lives only here."""

from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.entities import Setting

# Keys the public website is allowed to see. Secrets stay off this list.
PUBLIC_KEYS = [
    "shop_name",
    "tagline",
    "address",
    "phone",
    "whatsapp",
    "timing",
    "upi_id",
    "upi_name",
    "delivery_fee_rupees",
    "free_delivery_threshold_rupees",
    "loyalty_points_per_100_rupees",
    "bundle_discount_percent",
    "reservation_hours",
    "repair_slots_per_day",
    "theme_ink",
    "theme_cobalt",
    "theme_orange",
    "demo_banner",
    "offers",
]


DEFAULT_SETTINGS: Dict[str, str] = {
    "shop_name": "TECH TOYS",
    "tagline": "Gadgets that last. Advice you can trust.",
    "address": "Sagar Market, Kanpur, Uttar Pradesh, India",
    "phone": "+916307001812",
    "whatsapp": "+916307001812",
    "timing": "10 AM to 10 PM",
    "upi_id": "techtoys@upi",
    "upi_name": "TECH TOYS",
    "delivery_fee_rupees": "40",
    "free_delivery_threshold_rupees": "499",
    "loyalty_points_per_100_rupees": "1",
    "bundle_discount_percent": "10",
    "reservation_hours": "24",
    "repair_slots_per_day": "8",
    "theme_ink": "#0E1726",
    "theme_cobalt": "#2D5BFF",
    "theme_orange": "#FF6A3D",
    "demo_banner": "Warranty-backed tech · Same-day Kanpur delivery · Human support",
    "demo_mode": "true",
    "offers": "6-month warranty; same-day delivery in Kanpur; walk-in repairs; 15-minute pickup; 24-hour stock hold; genuine-verified stock; trade-in estimates",
}


def get_map(db: Session) -> Dict[str, str]:
    rows = db.query(Setting).all()
    data: Dict[str, str] = {}
    for row in rows:
        data[row.key] = row.value
    return data


def get_public_map(db: Session) -> Dict[str, str]:
    full = get_map(db)
    public: Dict[str, str] = {}
    for key in PUBLIC_KEYS:
        if key in full:
            public[key] = full[key]
    return public


def upsert_many(db: Session, items: List[Setting]) -> None:
    for item in items:
        existing = db.get(Setting, item.key)
        if existing is None:
            db.add(item)
        else:
            existing.value = item.value


def ensure_defaults(db: Session) -> None:
    """Insert missing keys so a fresh database always has shop identity."""
    for key, value in DEFAULT_SETTINGS.items():
        existing = db.get(Setting, key)
        if existing is None:
            db.add(Setting(key=key, value=value))
    db.flush()
