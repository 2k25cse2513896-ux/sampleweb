"""
Load a full demo catalogue the first time the database is empty.

Prices and stock are demo data. Brand names are plain text only.
"""

import json
import logging
import re
import time
from threading import Lock
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.config import get_settings
from app.models.entities import (
    Brand,
    Category,
    Coupon,
    Customer,
    FlashDeal,
    Order,
    OrderEvent,
    OrderItem,
    PhoneModel,
    Product,
    ProductImage,
    ProductCompatibility,
    RepairEvent,
    RepairRequest,
    Review,
    StockMovement,
    User,
    Warranty,
)
from app.services.settings_service import ensure_defaults

logger = logging.getLogger(__name__)

BRANDS: List[Tuple[str, str]] = [
    ("boAt", "boat"),
    ("Samsung", "samsung"),
    ("Boult", "boult"),
    ("Fire-Boltt", "fire-boltt"),
    ("Portronics", "portronics"),
    ("pTron", "ptron"),
    ("Noise", "noise"),
    ("Mivi", "mivi"),
    ("Ambrane", "ambrane"),
    ("Anker", "anker"),
    ("realme", "realme"),
    ("Redmi", "redmi"),
    ("OnePlus", "oneplus"),
    ("JBL", "jbl"),
    ("Sony", "sony"),
    ("SanDisk", "sandisk"),
    ("Lenovo", "lenovo"),
    ("Zebronics", "zebronics"),
]

CATEGORIES: List[Tuple[str, str, int]] = [
    ("Headphones", "headphones", 1),
    ("Earbuds", "earbuds", 2),
    ("Neckbands", "neckbands", 3),
    ("Chargers", "chargers", 4),
    ("Cables", "cables", 5),
    ("Power banks", "power-banks", 6),
    ("Covers and glass", "protection", 7),
    ("Watches, speakers and storage", "gadgets", 8),
]

PRODUCT_IMAGE_URLS = {
    "headphones": "https://images.unsplash.com/photo-1505751171710-1f6d0ace5a85?auto=format&fit=crop&w=900&q=85",
    "earbuds": "https://images.unsplash.com/photo-1596207891316-23851be3cc20?auto=format&fit=crop&w=900&q=85",
    "neckbands": "https://images.unsplash.com/photo-1505751171710-1f6d0ace5a85?auto=format&fit=crop&w=900&q=85",
    "chargers": "https://images.unsplash.com/photo-1596207891316-23851be3cc20?auto=format&fit=crop&w=900&q=85",
    "cables": "https://images.unsplash.com/photo-1596207891316-23851be3cc20?auto=format&fit=crop&w=900&q=85",
    "power-banks": "https://images.unsplash.com/photo-1596207891316-23851be3cc20?auto=format&fit=crop&w=900&q=85",
    "speaker": "https://images.unsplash.com/photo-1612795146974-84dbe538f4a4?auto=format&fit=crop&w=900&q=85",
    "watch": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=85",
    "pendrive": "https://images.unsplash.com/photo-1702141556838-ab291da11618?auto=format&fit=crop&w=900&q=85",
    "memory-card": "https://images.unsplash.com/photo-1702141556838-ab291da11618?auto=format&fit=crop&w=900&q=85",
    "gadgets": "https://images.unsplash.com/photo-1596207891316-23851be3cc20?auto=format&fit=crop&w=900&q=85",
    "protection": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=900&q=85",
}


def clean_catalogue_text(value: str) -> str:
    """Remove internal seed wording before catalogue text reaches customers."""
    cleaned = re.sub(
        r"\s*(?:Demo stock and demo price\. Plain-text demo catalogue listing\.|Demo price\.?|Demo unit card\.?|Demo listing\.?|Demo photo is a gradient card\.?|demo SKU\.?|demo ticket\.?|Demo review\.?)",
        "",
        value,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\bdemos?\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s+([,.])", r"\1", cleaned)
    return cleaned.strip(" .-")


def product_image_url(category_slug: str, specs_json: str) -> str:
    try:
        product_type = str(json.loads(specs_json or "{}").get("type", "")).lower()
    except (TypeError, ValueError):
        product_type = ""
    return PRODUCT_IMAGE_URLS.get(product_type, PRODUCT_IMAGE_URLS.get(category_slug, PRODUCT_IMAGE_URLS["gadgets"]))


LOCAL_ADMIN_PASSWORD = "Admin@123"
POSTGRES_SEED_LOCK_KEY = 675921804
POSTGRES_SEED_LOCK_WAIT_SECONDS = 10
POSTGRES_STATEMENT_TIMEOUT_MS = 30000
LOCAL_SEED_LOCK = Lock()


def _resolve_admin_password(value: str | None) -> str:
    """Use the environment password in production and a local-only default in development."""
    settings = get_settings()
    if value is not None and value != "":
        return value
    if settings.environment.lower() == "production":
        raise RuntimeError("ADMIN_PASSWORD must be set when SEED_ON_STARTUP is enabled in production.")
    return LOCAL_ADMIN_PASSWORD


def _safe_error(value: Exception) -> str:
    """Keep secrets and connection strings out of seed error logs."""
    settings = get_settings()
    message = str(value).replace(settings.database_url, "[database-url-redacted]")
    return message.replace("postgresql+psycopg://", "postgresql+psycopg://[redacted]")


def _seed_if_products_empty(db: Session, admin_password: str) -> int:
    """Recheck after locking so only the first starter can seed the database."""
    existing = db.query(Product.id).first()
    if existing is not None:
        logger.info("seed: skipped because products already exist")
        return 0
    count = run_seed(db, admin_password)
    logger.info("seed: inserted %s products", count)
    return count


def seed_if_empty(db: Session, admin_password: str | None = None) -> Optional[int]:
    """Seed once without overwriting data, using a bounded cross-instance lock."""
    logger.info("seed: checking")
    lock_acquired = False
    try:
        password = _resolve_admin_password(admin_password)
        bind = db.get_bind()
        if bind.dialect.name != "postgresql":
            with LOCAL_SEED_LOCK:
                return _seed_if_products_empty(db, password)

        db.rollback()
        db.execute(text(f"SET statement_timeout = '{POSTGRES_STATEMENT_TIMEOUT_MS}ms'"))
        db.execute(text("SET lock_timeout = '5000ms'"))
        db.commit()
        deadline = time.monotonic() + POSTGRES_SEED_LOCK_WAIT_SECONDS
        while time.monotonic() < deadline:
            acquired = db.execute(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": POSTGRES_SEED_LOCK_KEY},
            ).scalar()
            db.commit()
            if acquired:
                lock_acquired = True
                break
            time.sleep(0.5)
        if lock_acquired is False:
            logger.info("seed: skipped because seed lock is held")
            return None
        return _seed_if_products_empty(db, password)
    except Exception as exc:
        db.rollback()
        logger.error("seed: FAILED %s", _safe_error(exc))
        raise
    finally:
        if lock_acquired:
            try:
                db.rollback()
                db.execute(text("SELECT pg_advisory_unlock(:lock_key)"), {"lock_key": POSTGRES_SEED_LOCK_KEY})
                db.commit()
            except Exception as exc:
                logger.error("seed: FAILED to release seed lock: %s", _safe_error(exc))


def normalize_catalogue(db: Session) -> None:
    """Update an existing local database to the customer-facing catalogue format."""
    products = db.query(Product).all()
    changed = False
    for product in products:
        new_name = clean_catalogue_text(product.name)
        new_description = clean_catalogue_text(product.description)
        if product.name != new_name:
            product.name = new_name
            changed = True
        if product.description != new_description:
            product.description = new_description
            changed = True
        if len(product.images) == 0:
            category_slug = product.category.slug if product.category is not None else "gadgets"
            db.add(ProductImage(product_id=product.id, url=product_image_url(category_slug, product.specs_json), sort_order=0))
            changed = True
    if changed:
        db.commit()


def run_seed(db: Session, admin_password: str | None = None) -> int:
    """Wipe is not done here. Caller (reset) must clear tables first."""
    ensure_defaults(db)
    password = _resolve_admin_password(admin_password)

    admin = User(
        name="Demo Admin",
        email="admin@demo.shop",
        password_hash=hash_password(password),
        role="admin",
        is_active=True,
    )
    staff = User(
        name="Counter Staff",
        email="staff@demo.shop",
        password_hash=hash_password("Staff@123"),
        role="staff",
        is_active=True,
    )
    db.add(admin)
    db.add(staff)
    db.flush()

    cat_map: Dict[str, Category] = {}
    for name, slug, order in CATEGORIES:
        cat_map[slug] = Category(name=name, slug=slug, sort_order=order)
    db.add_all(list(cat_map.values()))
    db.flush()

    brand_map: Dict[str, Brand] = {}
    for name, slug in BRANDS:
        brand_map[slug] = Brand(name=name, slug=slug)
    db.add_all(list(brand_map.values()))
    db.flush()

    products = _build_products(cat_map, brand_map)
    db.add_all([product for product, _opening_qty in products])
    db.flush()
    category_slugs = {category.id: slug for slug, category in cat_map.items()}
    images: List[ProductImage] = []
    movements: List[StockMovement] = []
    for product, opening_qty in products:
        category_slug = category_slugs[product.category_id]
        images.append(ProductImage(product_id=product.id, url=product_image_url(category_slug, product.specs_json), sort_order=0))
        if opening_qty > 0:
            movements.append(
                StockMovement(
                    product_id=product.id,
                    change_qty=opening_qty,
                    reason="restock",
                    reference_id="seed",
                    created_by=admin.id,
                )
            )
            product.stock_qty = opening_qty
    db.add_all(images)
    db.add_all(movements)

    phones = _build_phones()
    db.add_all(phones)
    db.flush()

    _map_compatibility(db)
    _customers_orders_extras(db, admin.id)
    _rebuild_fts(db)
    db.commit()
    return len(products)


def _build_products(cat_map: Dict[str, Category], brand_map: Dict[str, Brand]) -> List[Tuple[Product, int]]:
    """Sixty demo SKUs with Indian rupee integer prices. Some stock is low or zero."""
    rows: List[Tuple[Product, int]] = []

    def add(
        sku: str,
        name: str,
        slug: str,
        cat: str,
        brand: str,
        price: int,
        mrp: int,
        cost: int,
        stock: int,
        warranty: int,
        featured: bool,
        specs: dict[str, str],
        desc: str,
    ) -> None:
        product = Product(
            sku=sku,
            barcode="TT" + sku.replace("-", ""),
            name=clean_catalogue_text(name),
            slug=slug,
            description=clean_catalogue_text(desc),
            category_id=cat_map[cat].id,
            brand_id=brand_map[brand].id,
            price=price,
            mrp=mrp,
            cost_price=cost,
            stock_qty=0,
            low_stock_threshold=3,
            warranty_months=warranty,
            is_genuine_verified=True,
            is_active=True,
            is_featured=featured,
            specs_json=json.dumps(specs),
        )
        rows.append((product, stock))

    add("HP-001", "boAt Rockerz 450 demo", "boat-rockerz-450-demo", "headphones", "boat", 1499, 1990, 900, 18, 6, True, {"type": "on-ear", "wireless": "yes", "driver": "40mm"}, "Everyday wireless headphones for commuting.")
    add("HP-002", "Sony WH extra bass demo", "sony-wh-bass-demo", "headphones", "sony", 2499, 3490, 1500, 8, 12, True, {"type": "on-ear", "wireless": "yes"}, "Louder bass for travel. Demo unit card.")
    add("HP-003", "JBL Tune studio demo", "jbl-tune-studio-demo", "headphones", "jbl", 2999, 3999, 1800, 6, 12, False, {"type": "over-ear", "anc": "no"}, "Over-ear comfort for long listening.")
    add("HP-004", "Zebronics Zeb-Bang demo", "zebronics-bang-demo", "headphones", "zebronics", 899, 1299, 450, 22, 6, False, {"type": "on-ear"}, "Budget wired-plus-bt headphones.")
    add("HP-005", "Lenovo ThinkPlus fold demo", "lenovo-fold-hp-demo", "headphones", "lenovo", 1299, 1799, 700, 0, 6, False, {"foldable": "yes"}, "Out of stock on purpose for alert demos.")
    add("HP-006", "Boult Audio ProBass demo", "boult-probass-hp-demo", "headphones", "boult", 1199, 1699, 600, 14, 6, False, {"battery_hours": "20"}, "Long battery for students.")
    add("HP-007", "Noise Two wireless demo", "noise-two-hp-demo", "headphones", "noise", 1799, 2499, 1000, 9, 6, False, {"anc": "hybrid"}, "Light ANC for city noise.")
    add("HP-008", "pTron Studio boom demo", "ptron-studio-hp-demo", "headphones", "ptron", 799, 1199, 380, 25, 3, False, {"wired": "yes"}, "Entry wired set for shops and PCs.")

    add("EB-001", "boAt Airdopes 141 demo", "boat-airdopes-141-demo", "earbuds", "boat", 999, 1490, 520, 30, 6, True, {"buds": "tws", "battery_hours": "42", "connector": "Type-C"}, "Daily TWS earbuds. Demo price.")
    add("EB-002", "OnePlus Nord Buds demo", "oneplus-nord-buds-demo", "earbuds", "oneplus", 1999, 2799, 1200, 12, 12, True, {"buds": "tws", "latency_ms": "94"}, "Low-latency buds for short videos.")
    add("EB-003", "realme Buds Air demo", "realme-buds-air-demo", "earbuds", "realme", 1499, 1999, 800, 16, 6, False, {"buds": "tws"}, "Balanced sound, compact case.")
    add("EB-004", "Redmi Buds 5 demo", "redmi-buds-5-demo", "earbuds", "redmi", 1799, 2299, 950, 11, 6, False, {"anc": "yes"}, "ANC earbuds for commute.")
    add("EB-005", "Boult W20 demo", "boult-w20-demo", "earbuds", "boult", 899, 1299, 430, 28, 6, True, {"ipx": "5"}, "Sweat-ready training buds.")
    add("EB-006", "Noise VS102 demo", "noise-vs102-demo", "earbuds", "noise", 1099, 1599, 540, 2, 6, False, {"battery_hours": "50"}, "Low stock so the shop page shows urgency.")
    add("EB-007", "Mivi DuoPods demo", "mivi-duopods-demo", "earbuds", "mivi", 799, 1199, 360, 20, 6, False, {"buds": "tws"}, "Simple TWS for calls.")
    add("EB-008", "pTron Bassbuds demo", "ptron-bassbuds-demo", "earbuds", "ptron", 699, 999, 300, 0, 3, False, {"buds": "tws"}, "Zero stock demo SKU.")
    add("EB-009", "Samsung Galaxy Buds style demo", "samsung-buds-style-demo", "earbuds", "samsung", 3499, 4999, 2100, 5, 12, True, {"anc": "yes"}, "Premium-feel demo listing. Not official pack shots.")
    add("EB-010", "Sony WF everyday demo", "sony-wf-everyday-demo", "earbuds", "sony", 3999, 5990, 2400, 4, 12, False, {"anc": "yes"}, "Office-quiet buds.")

    add("NB-001", "boAt Rockerz 255 demo", "boat-rockerz-255-demo", "neckbands", "boat", 1199, 1990, 600, 24, 6, True, {"connector": "Type-C", "battery_hours": "20"}, "Neckband for long battery days.")
    add("NB-002", "Boult Y1 neckband demo", "boult-y1-nb-demo", "neckbands", "boult", 799, 1299, 380, 19, 6, False, {"magnetic": "yes"}, "Magnetic buds, light neckband.")
    add("NB-003", "pTron Tangent demo", "ptron-tangent-demo", "neckbands", "ptron", 599, 999, 280, 33, 3, False, {"battery_hours": "24"}, "Value neckband.")
    add("NB-004", "Mivi Collar demo", "mivi-collar-demo", "neckbands", "mivi", 899, 1399, 420, 13, 6, False, {"sweat": "yes"}, "Gym neckband.")
    add("NB-005", "realme Buds Wireless demo", "realme-buds-wireless-demo", "neckbands", "realme", 1499, 1999, 800, 7, 6, False, {"bass": "boost"}, "Bass-forward neckband.")
    add("NB-006", "Zebronics Muse demo", "zebronics-muse-nb-demo", "neckbands", "zebronics", 549, 899, 250, 1, 3, False, {"wired_mic": "no"}, "Almost sold out.")

    add("CH-001", "Ambrane 33W Type-C charger demo", "ambrane-33w-demo", "chargers", "ambrane", 499, 799, 220, 40, 6, True, {"watt": "33", "connector": "Type-C"}, "Wall charger for Type-C phones.")
    add("CH-002", "Anker 20W USB-C charger demo", "anker-20w-demo", "chargers", "anker", 1299, 1799, 700, 15, 12, True, {"watt": "20", "connector": "Type-C"}, "Compact travel charger.")
    add("CH-003", "Samsung 25W charger demo", "samsung-25w-demo", "chargers", "samsung", 1499, 1999, 850, 10, 12, False, {"watt": "25", "connector": "Type-C"}, "Fast wall block. Demo listing.")
    add("CH-004", "realme 33W dart-style demo", "realme-33w-demo", "chargers", "realme", 999, 1499, 480, 18, 6, False, {"watt": "33", "connector": "Type-C"}, "Pair with a matching cable.")
    add("CH-005", "OnePlus 65W warp-style demo", "oneplus-65w-demo", "chargers", "oneplus", 1999, 2699, 1100, 6, 12, False, {"watt": "65", "connector": "Type-C"}, "High-watt demo SKU.")
    add("CH-006", "Portronics Adapto 65 demo", "portronics-adapto-65-demo", "chargers", "portronics", 1599, 2199, 820, 9, 6, False, {"ports": "2", "connector": "Type-C"}, "Two-port laptop-phone block.")
    add("CH-007", "Ambrane micro-USB 10W demo", "ambrane-10w-micro-demo", "chargers", "ambrane", 249, 399, 90, 50, 6, False, {"watt": "10", "connector": "micro-USB"}, "For older micro-USB phones.")
    add("CH-008", "boAt Dual port 18W demo", "boat-18w-dual-demo", "chargers", "boat", 399, 699, 160, 27, 6, False, {"watt": "18", "ports": "2"}, "USB-A plus Type-C.")

    add("CB-001", "Type-C to Type-C 60W cable demo", "typec-60w-cable-demo", "cables", "ambrane", 199, 399, 70, 80, 6, True, {"connector": "Type-C", "length_m": "1"}, "Daily Type-C cable.")
    add("CB-002", "Lightning charge cable demo", "lightning-cable-demo", "cables", "anker", 499, 799, 220, 22, 6, True, {"connector": "Lightning", "length_m": "1"}, "Lightning cable for older iPhones. Demo SKU.")
    add("CB-003", "micro-USB 1m cable demo", "micro-usb-cable-demo", "cables", "portronics", 99, 199, 30, 90, 3, False, {"connector": "micro-USB", "length_m": "1"}, "Spare micro-USB lead.")
    add("CB-004", "OnePlus Type-C 65W cable demo", "oneplus-65w-cable-demo", "cables", "oneplus", 449, 699, 180, 16, 6, False, {"connector": "Type-C", "watt": "65"}, "Thicker high-watt cable.")
    add("CB-005", "SanDisk Type-C data cable demo", "sandisk-typec-data-demo", "cables", "sandisk", 349, 549, 140, 20, 6, False, {"data": "yes", "connector": "Type-C"}, "Sync plus charge.")
    add("CB-006", "boAt 3-in-1 cable demo", "boat-3in1-cable-demo", "cables", "boat", 299, 499, 110, 35, 6, False, {"connector": "Type-C / Lightning / micro-USB"}, "One lead, three tips.")

    add("PB-001", "Ambrane 10000 mAh power bank demo", "ambrane-10k-pb-demo", "power-banks", "ambrane", 899, 1299, 480, 21, 6, True, {"mah": "10000", "ports": "2"}, "Pocket 10,000 mAh pack.")
    add("PB-002", "Anker 20000 mAh demo", "anker-20k-pb-demo", "power-banks", "anker", 2499, 3499, 1500, 8, 12, True, {"mah": "20000", "pd": "yes"}, "Travel 20,000 mAh pack.")
    add("PB-003", "Redmi 20000 mAh demo", "redmi-20k-pb-demo", "power-banks", "redmi", 1699, 2199, 980, 12, 6, False, {"mah": "20000"}, "High capacity, simple ports.")
    add("PB-004", "boAt 10000 mAh demo", "boat-10k-pb-demo", "power-banks", "boat", 999, 1499, 520, 17, 6, False, {"mah": "10000"}, "Fast-charge pocket bank.")
    add("PB-005", "Portronics 10000 mAh demo", "portronics-10k-pb-demo", "power-banks", "portronics", 799, 1199, 400, 0, 6, False, {"mah": "10000"}, "Zero stock for notify-me demos.")
    add("PB-006", "pTron Dynamo 10000 demo", "ptron-dynamo-10k-demo", "power-banks", "ptron", 699, 999, 320, 26, 3, False, {"mah": "10000"}, "Budget bank for students.")

    add("PR-001", "Redmi Note 13 back cover demo", "redmi-note-13-cover-demo", "protection", "redmi", 249, 399, 80, 40, 0, True, {"type": "cover", "fit": "Redmi Note 13"}, "Soft cover. Demo photo is a gradient card.")
    add("PR-002", "Redmi Note 13 tempered glass demo", "redmi-note-13-glass-demo", "protection", "redmi", 149, 299, 40, 55, 0, True, {"type": "glass", "fit": "Redmi Note 13"}, "2.5D glass.")
    add("PR-003", "Samsung A15 cover demo", "samsung-a15-cover-demo", "protection", "samsung", 249, 399, 80, 30, 0, False, {"type": "cover", "fit": "Samsung Galaxy A15"}, "Matte cover.")
    add("PR-004", "Samsung A15 glass demo", "samsung-a15-glass-demo", "protection", "samsung", 149, 299, 40, 36, 0, False, {"type": "glass", "fit": "Samsung Galaxy A15"}, "Edge glass.")
    add("PR-005", "OnePlus Nord CE cover demo", "oneplus-nord-ce-cover-demo", "protection", "oneplus", 299, 499, 90, 18, 0, False, {"type": "cover", "fit": "OnePlus Nord CE 3"}, "Clear cover.")
    add("PR-006", "OnePlus Nord CE glass demo", "oneplus-nord-ce-glass-demo", "protection", "oneplus", 179, 349, 50, 22, 0, False, {"type": "glass", "fit": "OnePlus Nord CE 3"}, "Case-friendly glass.")
    add("PR-007", "realme Narzo cover demo", "realme-narzo-cover-demo", "protection", "realme", 199, 349, 60, 25, 0, False, {"type": "cover", "fit": "realme Narzo 60"}, "Shock corners.")
    add("PR-008", "Universal glass 6.5 inch demo", "universal-glass-65-demo", "protection", "ambrane", 99, 199, 25, 70, 0, False, {"type": "glass", "fit": "universal"}, "Cut-to-fit shop glass.")

    add("GD-001", "Noise ColorFit pulse demo", "noise-colorfit-pulse-demo", "gadgets", "noise", 1499, 2499, 800, 14, 6, True, {"type": "watch", "display": "1.8"}, "Smart watch demo listing.")
    add("GD-002", "Fire-Boltt Ninja demo", "fire-boltt-ninja-demo", "gadgets", "fire-boltt", 1299, 1999, 700, 11, 6, True, {"type": "watch", "bt_calling": "yes"}, "BT calling watch.")
    add("GD-003", "boAt Wave Call demo", "boat-wave-call-demo", "gadgets", "boat", 1399, 2199, 750, 9, 6, False, {"type": "watch"}, "Round dial watch.")
    add("GD-004", "Mivi Play 5W speaker demo", "mivi-play-5w-demo", "gadgets", "mivi", 799, 1299, 380, 20, 6, False, {"type": "speaker", "watt": "5"}, "Desk speaker.")
    add("GD-005", "JBL Go pocket speaker demo", "jbl-go-pocket-demo", "gadgets", "jbl", 1999, 2999, 1100, 7, 12, True, {"type": "speaker", "ip": "67"}, "Pocket speaker.")
    add("GD-006", "Zebronics Zeb-Warrior demo", "zebronics-warrior-sp-demo", "gadgets", "zebronics", 999, 1499, 480, 12, 6, False, {"type": "speaker", "rgb": "yes"}, "RGB party speaker.")
    add("GD-007", "SanDisk 64GB card demo", "sandisk-64gb-demo", "gadgets", "sandisk", 449, 699, 250, 40, 60, False, {"type": "memory-card", "gb": "64"}, "microSD 64 GB.")
    add("GD-008", "SanDisk 128GB card demo", "sandisk-128gb-demo", "gadgets", "sandisk", 799, 1199, 420, 28, 60, False, {"type": "memory-card", "gb": "128"}, "microSD 128 GB.")
    add("GD-009", "SanDisk 32GB pendrive demo", "sandisk-32gb-pd-demo", "gadgets", "sandisk", 349, 549, 180, 45, 24, False, {"type": "pendrive", "gb": "32"}, "USB 2.0 stick.")
    add("GD-010", "Lenovo 64GB pendrive demo", "lenovo-64gb-pd-demo", "gadgets", "lenovo", 499, 799, 240, 18, 24, False, {"type": "pendrive", "gb": "64"}, "Metal body stick.")
    add("GD-011", "Portronics iKonnect presenter demo", "portronics-ikonnect-demo", "gadgets", "portronics", 899, 1299, 400, 6, 6, False, {"type": "gadget"}, "Small office gadget.")
    add("GD-012", "Ambrane 3-in-1 stand demo", "ambrane-stand-demo", "gadgets", "ambrane", 399, 699, 140, 24, 3, False, {"type": "gadget"}, "Phone stand.")

    return rows


def _build_phones() -> List[PhoneModel]:
    pairs: List[Tuple[str, str, str, str]] = [
        ("Redmi", "Note 13", "redmi-note-13", "Type-C"),
        ("Redmi", "Note 13 Pro", "redmi-note-13-pro", "Type-C"),
        ("Redmi", "12 5G", "redmi-12-5g", "Type-C"),
        ("Redmi", "13C", "redmi-13c", "Type-C"),
        ("Samsung", "Galaxy A15", "samsung-galaxy-a15", "Type-C"),
        ("Samsung", "Galaxy A23", "samsung-galaxy-a23", "Type-C"),
        ("Samsung", "Galaxy S23", "samsung-galaxy-s23", "Type-C"),
        ("Samsung", "Galaxy M14", "samsung-galaxy-m14", "Type-C"),
        ("realme", "Narzo 60", "realme-narzo-60", "Type-C"),
        ("realme", "12 Pro", "realme-12-pro", "Type-C"),
        ("realme", "C55", "realme-c55", "Type-C"),
        ("OnePlus", "Nord CE 3", "oneplus-nord-ce-3", "Type-C"),
        ("OnePlus", "Nord CE 3 Lite", "oneplus-nord-ce-3-lite", "Type-C"),
        ("OnePlus", "12R", "oneplus-12r", "Type-C"),
        ("Apple", "iPhone 15", "iphone-15", "Type-C"),
        ("Apple", "iPhone 14", "iphone-14", "Lightning"),
        ("Apple", "iPhone 13", "iphone-13", "Lightning"),
        ("Apple", "iPhone 11", "iphone-11", "Lightning"),
        ("vivo", "T2", "vivo-t2", "Type-C"),
        ("vivo", "Y16", "vivo-y16", "Type-C"),
        ("OPPO", "A78", "oppo-a78", "Type-C"),
        ("OPPO", "Reno 11", "oppo-reno-11", "Type-C"),
        ("Motorola", "G54", "moto-g54", "Type-C"),
        ("Motorola", "Edge 40", "moto-edge-40", "Type-C"),
        ("Nothing", "Phone 2a", "nothing-phone-2a", "Type-C"),
        ("Poco", "X6", "poco-x6", "Type-C"),
        ("Poco", "M6 Pro", "poco-m6-pro", "Type-C"),
        ("Nokia", "G42", "nokia-g42", "Type-C"),
        ("Lava", "Blaze 2", "lava-blaze-2", "Type-C"),
        ("Jio", "Bharat 1", "jio-bharat-1", "micro-USB"),
    ]
    out: List[PhoneModel] = []
    for brand, model, slug, connector in pairs:
        out.append(PhoneModel(brand=brand, model_name=model, slug=slug, connector_type=connector))
    return out


def _map_compatibility(db: Session) -> None:
    """Covers, glass and chargers mapped onto popular Type-C and Lightning phones."""
    covers = db.query(Product).filter(Product.sku.in_(["PR-001", "PR-003", "PR-005", "PR-007"])).all()
    glasses = db.query(Product).filter(Product.sku.in_(["PR-002", "PR-004", "PR-006", "PR-008"])).all()
    chargers = db.query(Product).filter(Product.category.has(slug="chargers")).all()
    cables = db.query(Product).filter(Product.category.has(slug="cables")).all()
    phones = db.query(PhoneModel).all()

    def link(product_id: int, phone_id: int) -> None:
        db.add(ProductCompatibility(product_id=product_id, phone_model_id=phone_id))

    for phone in phones:
        if phone.slug == "redmi-note-13":
            for p in covers + glasses:
                if "note-13" in p.slug:
                    link(p.id, phone.id)
        if phone.slug == "samsung-galaxy-a15":
            for p in covers + glasses:
                if "a15" in p.slug:
                    link(p.id, phone.id)
        if phone.slug == "oneplus-nord-ce-3":
            for p in covers + glasses:
                if "nord-ce" in p.slug:
                    link(p.id, phone.id)
        if phone.connector_type == "Type-C":
            for p in chargers:
                if "micro" not in p.slug:
                    link(p.id, phone.id)
            for p in cables:
                if "typec" in p.slug.replace("-", "") or "Type-C" in p.specs_json:
                    link(p.id, phone.id)
        if phone.connector_type == "Lightning":
            for p in cables:
                if "lightning" in p.slug:
                    link(p.id, phone.id)
        if phone.connector_type == "micro-USB":
            for p in chargers:
                if "micro" in p.slug:
                    link(p.id, phone.id)
            for p in cables:
                if "micro" in p.slug:
                    link(p.id, phone.id)


def _customers_orders_extras(db: Session, admin_id: int) -> None:
    now = datetime.now(timezone.utc)
    names = [
        ("Amit Verma", "9876500001"),
        ("Neha Singh", "9876500002"),
        ("Rahul Yadav", "9876500003"),
        ("Pooja Gupta", "9876500004"),
        ("Imran Khan", "9876500005"),
    ]
    customers = [Customer(name=name, phone=phone, email=None, loyalty_points=50) for name, phone in names]
    db.add_all(customers)
    db.flush()

    products = db.query(Product).filter(Product.stock_qty > 0).all()
    statuses = [
        "new",
        "confirmed",
        "packed",
        "ready_for_pickup",
        "out_for_delivery",
        "delivered",
        "cancelled",
        "delivered",
        "confirmed",
        "packed",
        "new",
        "delivered",
        "out_for_delivery",
        "ready_for_pickup",
        "confirmed",
    ]
    orders: List[Order] = []
    order_items: List[OrderItem] = []
    order_events: List[OrderEvent] = []
    for i in range(0, 15):
        product = products[i]
        qty = 1
        price = product.price
        total = price * qty
        status = statuses[i]
        payment_status = "pending"
        if status == "delivered":
            payment_status = "paid"
        if status == "cancelled":
            payment_status = "failed"
        customer = customers[i % 5]
        order = Order(
            order_no="TT" + str(1001 + i),
            customer_id=customer.id,
            status=status,
            fulfilment="pickup_15min",
            payment_method="upi",
            payment_status=payment_status,
            subtotal=total,
            discount=0,
            delivery_fee=0,
            total=total,
            address="Sagar Market pickup",
            note="Demo order",
        )
        orders.append(order)
    db.add_all(orders)
    db.flush()
    for i, order in enumerate(orders):
        product = products[i]
        status = order.status
        order_items.append(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                name_snapshot=product.name,
                price_snapshot=product.price,
                qty=1,
            )
        )
        order_events.append(OrderEvent(order_id=order.id, status=status, note="Seeded timeline"))
    db.add_all(order_items)
    db.add_all(order_events)

    issues = ["charging port", "speaker crackle", "screen glass", "not turning on"]
    repairs: List[RepairRequest] = []
    for i in range(0, 4):
        repairs.append(RepairRequest(ticket_no="RP" + str(2001 + i), customer_id=customers[i].id, device_brand="Redmi", device_model="Note 13", issue_type=issues[i], description="Walk-in demo ticket.", preferred_slot="afternoon", status="booked", estimate_amount=499))
    db.add_all(repairs)
    db.flush()
    db.add_all([RepairEvent(repair_id=repair.id, status="booked", note="Booked from seed") for repair in repairs])

    watch = db.query(Product).filter(Product.sku == "GD-001").one()
    buds = db.query(Product).filter(Product.sku == "EB-001").one()
    bank = db.query(Product).filter(Product.sku == "PB-002").one()
    for i, product in enumerate([watch, buds, bank]):
        db.add(
            Warranty(
                customer_id=customers[i].id,
                product_id=product.id,
                serial_no="SN-DEMO-" + str(i + 1),
                purchase_date=now - timedelta(days=20),
                expiry_date=now + timedelta(days=160),
            )
        )

    db.add(
        FlashDeal(
            product_id=buds.id,
            deal_price=899,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(days=2),
            is_active=True,
        )
    )
    nb = db.query(Product).filter(Product.sku == "NB-001").one()
    db.add(
        FlashDeal(
            product_id=nb.id,
            deal_price=999,
            starts_at=now - timedelta(hours=2),
            ends_at=now + timedelta(days=1),
            is_active=True,
        )
    )

    db.add(Coupon(code="KANPUR50", type="flat", value=50, min_order=499, max_uses=100, used_count=3, is_active=True))
    db.add(Coupon(code="ACCESS10", type="percent", value=10, min_order=999, max_uses=200, used_count=8, is_active=True))
    db.add(Coupon(code="PICKUP0", type="flat", value=40, min_order=0, max_uses=50, used_count=1, is_active=True))

    db.add(
        Review(
            product_id=buds.id,
            customer_id=customers[0].id,
            rating=5,
            comment="Clear calls. Demo review.",
            is_approved=True,
        )
    )
    db.add(
        Review(
            product_id=watch.id,
            customer_id=customers[1].id,
            rating=4,
            comment="Display is bright enough outdoors.",
            is_approved=True,
        )
    )
    db.add(
        Review(
            product_id=bank.id,
            customer_id=customers[2].id,
            rating=3,
            comment="Works. Waiting for staff to approve extras.",
            is_approved=False,
        )
    )


def _rebuild_fts(db: Session) -> None:
    try:
        db.execute(text("INSERT INTO products_fts(products_fts) VALUES('rebuild')"))
    except Exception:
        # FTS5 may be missing on some SQLite builds. LIKE search still works.
        return


def reset_and_seed(db: Session) -> None:
    """Admin-only later. Phase 1 exposes the function; the button comes with the admin UI."""
    from app.models.base import Base
    from app.core.db import engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    run_seed(db)
