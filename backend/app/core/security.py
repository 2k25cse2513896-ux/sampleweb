"""JWT tokens and password hashing. Uses passlib bcrypt as required."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.errors import AppError

# passlib wraps bcrypt so we do not store plain passwords.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def hash_password(plain: str) -> str:
    """Hash a password for storage. Never log the plain value."""
    return pwd_context.hash(plain)


def verify_password(plain: str, password_hash: str) -> bool:
    """Return True when the password matches the stored hash."""
    return pwd_context.verify(plain, password_hash)


def create_token(subject: str, token_type: str, minutes: Optional[int] = None, days: Optional[int] = None) -> str:
    """
    Build a signed JWT.

    token_type is "access" or "refresh". Expiry is either minutes or days, not both.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if minutes is not None:
        expire = now + timedelta(minutes=minutes)
    else:
        if days is None:
            days = 1
        expire = now + timedelta(days=days)
    payload: Dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_access_token(subject: str) -> str:
    settings = get_settings()
    return create_token(subject, "access", minutes=settings.access_token_minutes)


def create_refresh_token(subject: str) -> str:
    settings = get_settings()
    return create_token(subject, "refresh", days=settings.refresh_token_days)


def decode_token(token: str, expected_type: str) -> Dict[str, Any]:
    """Decode and check the token type. Raises AppError on failure."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        raise AppError("unauthorized", "Invalid or expired token.", 401)
    token_type = payload.get("type")
    if token_type != expected_type:
        raise AppError("unauthorized", "Wrong token type.", 401)
    return payload
