"""Admin endpointi za pregled audit logova."""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_roles
from app.database import get_db

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get(
    "/",
    response_model=schemas.AuditLogPage,
    responses={
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
    },
)
def read_audit_logs(
    page: int = 1,
    page_size: int = 20,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    actor_username: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles("admin")),
):
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    page_size = min(page_size, 100)

    allowed_sort_fields = {
        "id": models.AuditLog.id,
        "created_at": models.AuditLog.created_at,
        "action": models.AuditLog.action,
        "entity_type": models.AuditLog.entity_type,
        "actor_username": models.AuditLog.actor_username,
    }
    sort_column = allowed_sort_fields.get(sort_by, models.AuditLog.created_at)
    sort_order = "asc" if sort_order.lower() == "asc" else "desc"

    query = db.query(models.AuditLog)

    if action:
        query = query.filter(models.AuditLog.action == action)
    if entity_type:
        query = query.filter(models.AuditLog.entity_type == entity_type)
    if actor_username:
        query = query.filter(models.AuditLog.actor_username.contains(actor_username))

    total = query.count()
    if sort_order == "asc":
        ordering = [sort_column.asc(), models.AuditLog.id.asc()]
    else:
        ordering = [sort_column.desc(), models.AuditLog.id.desc()]
    offset = (page - 1) * page_size
    items = query.order_by(*ordering).offset(offset).limit(page_size).all()

    return {
        "items": items,
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    }
