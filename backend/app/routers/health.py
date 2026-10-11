"""Liveness probe used by Docker and hosts."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.startup_state import get_startup_state

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/ready")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    """Readiness probe: the process is ready only after startup seeding completes."""
    db.execute(text("SELECT 1"))
    state = get_startup_state()
    if state["status"] != "ready":
        raise HTTPException(status_code=503, detail=state)
    return state
