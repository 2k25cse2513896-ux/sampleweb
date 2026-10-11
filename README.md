# TECH TOYS

Sample shop site for a local electronics and mobile-accessories counter at **Sagar Market, Kanpur**.

Shop name, phone, timing and UPI ID are stored in the `settings` table and edited from admin. Do not hard-code them in the UI.

Prices and stock in the seed are **demo data**. Brand names (boAt, Samsung, Sony, …) are **plain text only** — no logos, no official photos, no authorised-dealer claim.

Money is **whole rupees stored as integers**. Percent discounts use `round_rupees()` (round half up). **1 loyalty point = Rs 1**.

## Current delivery

The foundation plus commerce, customer tools, admin dashboard APIs and a responsive React/Vite shop are included. The public app covers catalogue search, phone-model compatibility, bundle suggestions, cart pricing, pickup checkout, order tracking, repair lead capture and a rule-based assistant. `/admin` covers owner login, sales metrics, low-stock watch and order status updates.

## Demo logins

- Admin: `admin@demo.shop` / `Admin@123`
- Staff: `staff@demo.shop` / `Staff@123`

In a later phase, customer login uses phone OTP. In demo mode the OTP is returned by the API.

## Local backend

Python 3.11 or 3.12 is recommended because the pinned Pillow build targets those runtimes.

```powershell
cd C:\Users\Shadman\Desktop\sampleweb\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy ..\.env.example .env
uvicorn app.main:app --reload --port 8000
```

Then open:

- Health: http://127.0.0.1:8000/api/health
- Docs: http://127.0.0.1:8000/docs
- Public settings: http://127.0.0.1:8000/api/settings
- Products: http://127.0.0.1:8000/api/products

The first start creates `shop.db` and seeds demo rows if the users table is empty.

### Tests

```powershell
cd C:\Users\Shadman\Desktop\sampleweb\backend
.\.venv\Scripts\Activate.ps1
pytest -q
```

### Migrations

Startup also calls `create_all`. To use Alembic explicitly:

```powershell
cd C:\Users\Shadman\Desktop\sampleweb\backend
alembic upgrade head
```

## What to click in /docs (manual)

1. `GET /api/health` returns `{ "status": "ok" }`.
2. `GET /api/settings` shows TECH TOYS, Sagar Market, phone, timing, UPI.
3. `GET /api/brands` lists real brand names as text (boAt, Sony, …).
4. `POST /api/auth/admin/login` with the admin demo user, then Authorize.
5. `GET /api/auth/me` returns role `admin`.
6. Create a category and a product. Stock must be an integer rupee-priced SKU.
7. Staff token cannot change `price` and cannot PUT `/api/admin/settings`.

## Frontend

```powershell
cd C:\Users\Shadman\Desktop\sampleweb
copy .env.example .env
npm install
npm run dev
```

Open http://localhost:5173. Set `VITE_API_URL` in `.env` if the backend is hosted somewhere else.

### One-command local start

From PowerShell:

```powershell
cd C:\Users\Shadman\Desktop\sampleweb
Set-ExecutionPolicy -Scope Process Bypass -Force; .\start.ps1
```

This opens one terminal for FastAPI and one for Vite. Python 3.11 or 3.12 is recommended.

## Docker

```powershell
copy .env.example .env
docker compose up --build
```

The backend creates `shop.db` and demo rows on first start. Render/Railway deployments need a persistent disk for SQLite and uploads; otherwise a redeploy resets demo data. Vercel/Netlify can deploy the frontend with `VITE_API_URL` pointing to the backend.

To move to PostgreSQL later, change only `DATABASE_URL` to a PostgreSQL SQLAlchemy URL, install a PostgreSQL driver, and run Alembic migrations. Keep uploads on object storage for multiple backend instances.

### Production container template

Use `.env.production.example` as the starting point for a real deployment, then fill every secret and domain value:

```powershell
copy .env.production.example .env
docker compose -f docker-compose.production.yml up -d --build
docker compose -f docker-compose.production.yml run --rm backend python create_admin.py --email owner@yourdomain.com
```

The production compose file uses PostgreSQL, persistent upload storage, Alembic migrations, a production Uvicorn process and the built Nginx frontend. Do not use demo credentials or `DEMO_MODE=true` in production.
