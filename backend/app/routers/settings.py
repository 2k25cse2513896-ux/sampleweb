"""Public shop identity and admin editor. Components must not hard-code these values."""

from typing import Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_admin
from app.models.entities import Setting, User
from app.schemas.catalogue import SettingOut, SettingPut
from app.services.audit import write_audit
from app.services.settings_service import get_map, get_public_map, upsert_many

router = APIRouter(tags=["settings"])


@router.get("/api/settings")
def public_settings(db: Session = Depends(get_db)) -> Dict[str, str]:
    return get_public_map(db)


@router.get("/api/admin/settings", response_model=List[SettingOut])
def admin_settings(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> List[SettingOut]:
    data = get_map(db)
    items: List[SettingOut] = []
    for key, value in data.items():
        items.append(SettingOut(key=key, value=value))
    return items


@router.put("/api/admin/settings", response_model=List[SettingOut])
def put_settings(
    body: SettingPut,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> List[SettingOut]:
    rows: List[Setting] = []
    for item in body.items:
        rows.append(Setting(key=item.key, value=item.value))
    upsert_many(db, rows)
    write_audit(db, admin.id, "update", "settings", "all", "{}")
    db.commit()
    data = get_map(db)
    out: List[SettingOut] = []
    for key, value in data.items():
        out.append(SettingOut(key=key, value=value))
    return out
