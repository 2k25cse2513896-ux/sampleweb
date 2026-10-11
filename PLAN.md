# TECH TOYS — Phase 0 plan (updated)

Shop sample for Sagar Market, Kanpur. Shop name, phone, timing and UPI ID live in the `settings` table only.

## Locked decisions

- Shop: TECH TOYS. Tagline: Gadgets that last. Advice you can trust.
- Hours: 10 AM to 10 PM. Phone / WhatsApp: +91 63070 01812.
- Location: Sagar Market, Kanpur, Uttar Pradesh, India.
- **Money: whole rupees as integer columns everywhere. No paise. No floats. No divide-by-100.**
- **Percent discounts go through `round_rupees()` (round half up) and store an integer rupee amount.**
- **Loyalty: 1 point = Rs 1.**
- Brands are **real names as plain text only**: boAt, Samsung, Boult, Fire-Boltt, Portronics, pTron, Noise, Mivi, Ambrane, Anker, realme, Redmi, OnePlus, JBL, Sony, SanDisk, Lenovo, Zebronics.
- No logos, no official product images, no "authorized dealer" claim.
- Prices and stock are **demo data**. Banner: "Demo store. Orders are for demonstration."
- Product photos: SVG/gradient placeholders; owner uploads real photos in admin.

## Offers (copy, also settings)

6-month warranty on electronics we sell. Same-day delivery in Kanpur. Walk-in repairs. 15-minute pickup. 24-hour stock hold. Genuine-verified stock. Trade-in estimates.

## Stack and layout

See original Phase 0: FastAPI + SQLite backend, React 18 Vite frontend later. Desktop wow at 1024px+. Mobile never loads Three.js.

## Phase 1 (this delivery)

Backend foundation: models, Alembic, seed, JWT auth, products/categories/brands CRUD, settings, tests, `/docs`.
