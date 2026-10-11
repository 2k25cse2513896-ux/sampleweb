"""FastAPI entry. CORS, rate limits, static uploads, OpenAPI at /docs."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import get_settings
from app.core.db import SessionLocal, init_db
from app.core.errors import error_body, register_error_handlers
from app.core.rate_limit import limiter
from app.routers import admin, auth, brands, categories, commerce, customer, customer_auth, health, products, settings
from app.services.seed import normalize_catalogue, seed_if_empty

app_settings = get_settings()


def rate_limit_handler(_request: Request, _exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content=error_body("rate_limited", "Too many attempts. Wait a minute."),
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create tables and load demo rows when the users table is empty."""
    if app_settings.environment.lower() == "production":
        if app_settings.demo_mode:
            raise RuntimeError("DEMO_MODE must be false in production.")
        if app_settings.secret_key == "change-me-to-a-long-random-string" or len(app_settings.secret_key) < 32:
            raise RuntimeError("SECRET_KEY must be a long random production secret.")
    init_db()
    db = SessionLocal()
    try:
        if app_settings.seed_on_startup:
            seed_if_empty(db, app_settings.admin_password)
        if app_settings.demo_mode:
            normalize_catalogue(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="TECH TOYS API",
    description="Local electronics shop backend. Shop identity is stored in the settings table.",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)
register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if app_settings.environment.lower() == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

upload_dir = Path(app_settings.upload_dir)
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(customer_auth.router)
app.include_router(settings.router)
app.include_router(brands.router)
app.include_router(categories.router)
app.include_router(products.router)
app.include_router(commerce.router)
app.include_router(customer.router)
app.include_router(admin.router)
