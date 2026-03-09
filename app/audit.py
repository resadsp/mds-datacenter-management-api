"""Pomoćne funkcije za upis audit logova."""

import json
from datetime import datetime, timezone

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app import models


def log_action(
    db: Session,
    actor_username: str,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    before_data: dict | None = None,
    after_data: dict | None = None,
) -> None:
    audit_row = models.AuditLog(
        actor_username=actor_username,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_data=json.dumps(jsonable_encoder(before_data), ensure_ascii=False) if before_data is not None else None,
        after_data=json.dumps(jsonable_encoder(after_data), ensure_ascii=False) if after_data is not None else None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit_row)
