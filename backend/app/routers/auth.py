"""Admin/staff login with JWT. Rate-limited. Customer OTP lands in a later phase but the login path is live."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.rate_limit import limiter
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.entities import User
from app.schemas.catalogue import UserOut
from app.schemas.common import LoginIn, RefreshIn, TokenPair

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/admin/login", response_model=TokenPair)
@limiter.limit("8/minute")
def admin_login(request: Request, body: LoginIn, db: Session = Depends(get_db)) -> TokenPair:
    """
    Email + password for staff and admin.

    Rate limiting is applied in main.py on this path.
    """
    # Touch request so slowapi can key off the client IP when wrapping this route.
    _ = request.client
    user = db.query(User).filter(User.email == body.email.strip().lower()).one_or_none()
    if user is None:
        raise AppError("invalid_credentials", "Email or password is wrong.", 401)
    if verify_password(body.password, user.password_hash) is False:
        raise AppError("invalid_credentials", "Email or password is wrong.", 401)
    if user.is_active is False:
        raise AppError("forbidden", "This account is disabled.", 403)
    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/admin/refresh", response_model=TokenPair)
def admin_refresh(body: RefreshIn) -> TokenPair:
    payload = decode_token(body.refresh_token, "refresh")
    subject = str(payload.get("sub"))
    return TokenPair(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
