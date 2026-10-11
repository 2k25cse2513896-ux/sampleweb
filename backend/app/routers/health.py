"""Liveness probe used by Docker and hosts."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/ready")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    """Readiness probe: the process is ready only when the database responds."""
    db.execute(text("SELECT 1"))
    return {"status": "ready"}
