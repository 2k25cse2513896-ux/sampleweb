"""Write one audit_log row for admin actions. details_json is a JSON string."""

from typing import Optional

from sqlalchemy.orm import Session

from app.models.entities import AuditLog


def write_audit(
    db: Session,
    user_id: Optional[int],
    action: str,
    entity: str,
    entity_id: str,
    details_json: str,
) -> None:
    row = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details_json=details_json,
    )
    db.add(row)
