"""FastAPI dependencies for database sessions and the logged-in user."""

from typing import Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import decode_token
from app.models.entities import Customer, User

bearer_scheme = HTTPBearer(auto_error=False)


def _bearer_token(creds: Optional[HTTPAuthorizationCredentials]) -> str:
    if creds is None:
        raise AppError("unauthorized", "Missing Authorization header.", 401)
    return creds.credentials


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Staff or admin JWT. Subject is users.id."""
    token = _bearer_token(creds)
    payload = decode_token(token, "access")
    raw_id = payload.get("sub")
    if raw_id is None:
        raise AppError("unauthorized", "Token is missing a subject.", 401)
    user = db.get(User, int(raw_id))
    if user is None:
        raise AppError("unauthorized", "User no longer exists.", 401)
    if user.is_active is False:
        raise AppError("forbidden", "This account is disabled.", 403)
    return user


def require_staff(user: User = Depends(get_current_user)) -> User:
    """Staff and admin may manage orders, repairs and stock."""
    if user.role != "staff":
        if user.role != "admin":
            raise AppError("forbidden", "Staff access required.", 403)
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Only admin may manage users, settings, prices and deletes."""
    if user.role != "admin":
        raise AppError("forbidden", "Admin access required.", 403)
    return user


def get_current_customer(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Customer:
    """Customer JWT. Subject is prefixed with c: so it cannot collide with staff ids."""
    token = _bearer_token(creds)
    payload = decode_token(token, "access")
    raw = payload.get("sub")
    if raw is None:
        raise AppError("unauthorized", "Token is missing a subject.", 401)
    text = str(raw)
    if text.startswith("c:") is False:
        raise AppError("unauthorized", "This token is not a customer session.", 401)
    customer_id = int(text.replace("c:", "", 1))
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise AppError("unauthorized", "Customer no longer exists.", 401)
    return customer
