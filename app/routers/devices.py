"""CRUD endpointi za uređaje i dodelu rack-u."""

import os
import time
from datetime import datetime, timezone
from threading import Lock

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app import models, schemas
from app.auth import require_roles
from app.audit import log_action
from app.database import get_db
from app.routers.stats import invalidate_stats_cache

router = APIRouter()

ASSIGN_IDEMPOTENCY_TTL_SECONDS = int(os.getenv("ASSIGN_IDEMPOTENCY_TTL_SECONDS", "600"))
_assign_idempotency_lock = Lock()
_assign_idempotency_store: dict[str, dict] = {}


def _cleanup_assign_idempotency(now: float) -> None:
    expired_keys = [
        key
        for key, value in _assign_idempotency_store.items()
        if value.get("expires_at", 0.0) <= now
    ]
    for key in expired_keys:
        _assign_idempotency_store.pop(key, None)


def _get_assign_idempotency(key: str, now: float) -> dict | None:
    with _assign_idempotency_lock:
        _cleanup_assign_idempotency(now)
        return _assign_idempotency_store.get(key)


def _save_assign_idempotency(key: str, fingerprint: str, message: str, now: float) -> None:
    ttl = max(ASSIGN_IDEMPOTENCY_TTL_SECONDS, 1)
    with _assign_idempotency_lock:
        _cleanup_assign_idempotency(now)
        _assign_idempotency_store[key] = {
            "fingerprint": fingerprint,
            "message": message,
            "expires_at": now + ttl,
        }


def _device_snapshot(device: models.Device) -> dict:
    return {
        "id": device.id,
        "name": device.name,
        "description": device.description,
        "serial_number": device.serial_number,
        "units_occupied": device.units_occupied,
        "power_consumption": device.power_consumption,
        "rack_id": device.rack_id,
        "version": device.version,
        "deleted_at": device.deleted_at,
    }

# Kreiranje novog uređaja
@router.post(
    "/devices/",
    response_model=schemas.Device,
    responses={
        400: {"model": schemas.ErrorResponse},
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
    },
)
def create_device(
    device: schemas.DeviceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("operator", "admin")),
):
    """Kreira novi uređaj nakon provere jedinstvenosti serijskog broja."""
    # Proveravamo da li serijski broj već postoji
    db_device = db.query(models.Device).filter(models.Device.serial_number == device.serial_number).first()
    if db_device:
        raise HTTPException(status_code=400, detail="Serijski broj već postoji")

    # Kreiramo novi uređaj
    db_device = models.Device(**device.model_dump())
    db.add(db_device)
    db.commit()
    db.refresh(db_device)

    log_action(
        db,
        actor_username=current_user.username,
        action="device.create",
        entity_type="device",
        entity_id=db_device.id,
        after_data=_device_snapshot(db_device),
    )
    db.commit()
    invalidate_stats_cache()
    return db_device

# Lista svih uređaja sa paginacijom i filtriranjem
@router.get(
    "/devices/",
    response_model=schemas.DevicePage,
    responses={
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
    },
)
def read_devices(
    page: int = 1,
    page_size: int = 20,
    name: str | None = None,
    serial_number: str | None = None,
    rack_id: int | None = None,
    include_deleted: bool = False,
    sort_by: str = "id",
    sort_order: str = "asc",
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles("viewer", "operator", "admin")),
):
    """Vraća paginiranu listu uređaja, sa standardnim page/page_size/sort/filter parametrima."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    page_size = min(page_size, 100)

    allowed_sort_fields = {
        "id": models.Device.id,
        "name": models.Device.name,
        "serial_number": models.Device.serial_number,
        "units_occupied": models.Device.units_occupied,
        "power_consumption": models.Device.power_consumption,
    }
    sort_column = allowed_sort_fields.get(sort_by, models.Device.id)
    normalized_sort_by = sort_by if sort_by in allowed_sort_fields else "id"
    sort_order = "desc" if sort_order.lower() == "desc" else "asc"

    query = db.query(models.Device)
    if not include_deleted:
        query = query.filter(models.Device.deleted_at.is_(None))
    if name:
        query = query.filter(models.Device.name.contains(name))  # Filtriranje po nazivu
    if serial_number:
        query = query.filter(models.Device.serial_number.contains(serial_number))
    if rack_id is not None:
        query = query.filter(models.Device.rack_id == rack_id)

    total = query.count()
    ordering = sort_column.desc() if sort_order == "desc" else sort_column.asc()
    offset = (page - 1) * page_size
    devices = query.order_by(ordering).offset(offset).limit(page_size).all()

    return {
        "items": devices,
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "sort_by": normalized_sort_by,
            "sort_order": sort_order,
        },
    }

# Dohvatanje pojedinačnog uređaja
@router.get(
    "/devices/{device_id}",
    response_model=schemas.Device,
    responses={
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
        404: {"model": schemas.ErrorResponse},
    },
)
def read_device(
    device_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles("viewer", "operator", "admin")),
):
    """Vraća jedan uređaj po ID-u."""
    db_device = (
        db.query(models.Device)
        .filter(models.Device.id == device_id, models.Device.deleted_at.is_(None))
        .first()
    )
    if db_device is None:
        raise HTTPException(status_code=404, detail="Uređaj nije pronađen")
    return db_device

# Ažuriranje uređaja
@router.put(
    "/devices/{device_id}",
    response_model=schemas.Device,
    responses={
        400: {"model": schemas.ErrorResponse},
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
        404: {"model": schemas.ErrorResponse},
        409: {"model": schemas.ErrorResponse},
    },
)
def update_device(
    device_id: int,
    device: schemas.DeviceUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("operator", "admin")),
):
    """Ažurira uređaj uz poštovanje kapaciteta rack-a."""
    db_device = (
        db.query(models.Device)
        .filter(models.Device.id == device_id, models.Device.deleted_at.is_(None))
        .first()
    )
    if db_device is None:
        raise HTTPException(status_code=404, detail="Uređaj nije pronađen")

    if db_device.version != device.version:
        raise HTTPException(status_code=409, detail="Konflikt verzije uređaja. Osvežite podatke i pokušajte ponovo.")

    before_state = _device_snapshot(db_device)

    existing = db.query(models.Device).filter(
        models.Device.serial_number == device.serial_number,
        models.Device.id != device_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Serijski broj već postoji")

    # Ako je uređaj već u rack-u, update ne sme probiti kapacitet rack-a
    if db_device.rack_id is not None:
        rack = (
            db.query(models.Rack)
            .filter(models.Rack.id == db_device.rack_id, models.Rack.deleted_at.is_(None))
            .first()
        )

        if rack is None:
            raise HTTPException(status_code=400, detail="Rack dodeljen uređaju više ne postoji")

        other_devices = (
            db.query(models.Device)
            .filter(
                models.Device.rack_id == rack.id,
                models.Device.id != db_device.id,
                models.Device.deleted_at.is_(None),
            )
            .all()
        )
        used_units_without_this = sum(d.units_occupied for d in other_devices)
        used_power_without_this = sum(d.power_consumption for d in other_devices)

        if used_units_without_this + device.units_occupied > rack.total_units:
            raise HTTPException(status_code=400, detail="Update prelazi kapacitet jedinica rack-a")
        if used_power_without_this + device.power_consumption > rack.max_power:
            raise HTTPException(status_code=400, detail="Update prelazi kapacitet snage rack-a")

    update_payload = device.model_dump(exclude={"version"})
    affected_rows = (
        db.query(models.Device)
        .filter(
            models.Device.id == device_id,
            models.Device.deleted_at.is_(None),
            models.Device.version == device.version,
        )
        .update(
            {
                **update_payload,
                models.Device.version: models.Device.version + 1,
            },
            synchronize_session=False,
        )
    )
    if affected_rows == 0:
        db.rollback()
        raise HTTPException(status_code=409, detail="Konflikt verzije uređaja. Osvežite podatke i pokušajte ponovo.")

    db.commit()
    db_device = (
        db.query(models.Device)
        .filter(models.Device.id == device_id, models.Device.deleted_at.is_(None))
        .first()
    )
    if db_device is None:
        raise HTTPException(status_code=404, detail="Uređaj nije pronađen")

    log_action(
        db,
        actor_username=current_user.username,
        action="device.update",
        entity_type="device",
        entity_id=db_device.id,
        before_data=before_state,
        after_data=_device_snapshot(db_device),
    )
    db.commit()
    invalidate_stats_cache()
    return db_device

# Brisanje uređaja
@router.delete(
    "/devices/{device_id}",
    response_model=schemas.MessageResponse,
    responses={
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
        404: {"model": schemas.ErrorResponse},
    },
)
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("operator", "admin")),
):
    """Soft-delete uređaja po ID-u."""
    db_device = (
        db.query(models.Device)
        .filter(models.Device.id == device_id, models.Device.deleted_at.is_(None))
        .first()
    )
    if db_device is None:
        raise HTTPException(status_code=404, detail="Uređaj nije pronađen")

    before_state = _device_snapshot(db_device)

    db_device.deleted_at = datetime.now(timezone.utc)
    db_device.version += 1
    db.commit()

    log_action(
        db,
        actor_username=current_user.username,
        action="device.soft_delete",
        entity_type="device",
        entity_id=db_device.id,
        before_data=before_state,
        after_data=_device_snapshot(db_device),
    )
    db.commit()
    invalidate_stats_cache()
    return {"message": "Uređaj arhiviran"}


@router.post(
    "/devices/{device_id}/restore",
    response_model=schemas.MessageResponse,
    responses={
        400: {"model": schemas.ErrorResponse},
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
        404: {"model": schemas.ErrorResponse},
    },
)
def restore_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("operator", "admin")),
):
    """Vraća arhivirani uređaj u aktivno stanje uz proveru kapaciteta rack-a."""
    db_device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if db_device is None:
        raise HTTPException(status_code=404, detail="Uređaj nije pronađen")
    if db_device.deleted_at is None:
        raise HTTPException(status_code=400, detail="Uređaj nije arhiviran")

    before_state = _device_snapshot(db_device)

    if db_device.rack_id is not None:
        rack = (
            db.query(models.Rack)
            .filter(models.Rack.id == db_device.rack_id, models.Rack.deleted_at.is_(None))
            .first()
        )
        if rack is None:
            raise HTTPException(status_code=400, detail="Rack dodeljen uređaju više ne postoji")

        other_active_devices = (
            db.query(models.Device)
            .filter(
                models.Device.rack_id == rack.id,
                models.Device.id != db_device.id,
                models.Device.deleted_at.is_(None),
            )
            .all()
        )
        used_units = sum(d.units_occupied for d in other_active_devices)
        used_power = sum(d.power_consumption for d in other_active_devices)

        if used_units + db_device.units_occupied > rack.total_units:
            raise HTTPException(status_code=400, detail="Restore prelazi kapacitet jedinica rack-a")
        if used_power + db_device.power_consumption > rack.max_power:
            raise HTTPException(status_code=400, detail="Restore prelazi kapacitet snage rack-a")

    db_device.deleted_at = None
    db_device.version += 1
    db.commit()

    log_action(
        db,
        actor_username=current_user.username,
        action="device.restore",
        entity_type="device",
        entity_id=db_device.id,
        before_data=before_state,
        after_data=_device_snapshot(db_device),
    )
    db.commit()
    invalidate_stats_cache()
    return {"message": "Uređaj vraćen iz arhive"}

# Dodeljivanje uređaja rack-u
@router.post(
    "/devices/{device_id}/assign/{rack_id}",
    response_model=schemas.MessageResponse,
    responses={
        400: {"model": schemas.ErrorResponse},
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
        404: {"model": schemas.ErrorResponse},
    },
)
def assign_device_to_rack(
    device_id: int,
    rack_id: int,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("operator", "admin")),
):
    """Dodeljuje uređaj rack-u ako kapacitet jedinica i snage to dozvoljava."""
    if idempotency_key:
        now = time.time()
        fingerprint = f"{current_user.username}:{device_id}:{rack_id}"
        existing_entry = _get_assign_idempotency(idempotency_key, now)
        if existing_entry is not None:
            if existing_entry.get("fingerprint") != fingerprint:
                raise HTTPException(status_code=409, detail="Idempotency-Key already used for different request")
            return {"message": existing_entry.get("message", "Uređaj dodeljen rack-u")}

    # Pronalazimo uređaj
    db_device = (
        db.query(models.Device)
        .filter(models.Device.id == device_id, models.Device.deleted_at.is_(None))
        .first()
    )
    if db_device is None:
        raise HTTPException(status_code=404, detail="Uređaj nije pronađen")

    # Pronalazimo rack
    db_rack = (
        db.query(models.Rack)
        .filter(models.Rack.id == rack_id, models.Rack.deleted_at.is_(None))
        .first()
    )
    if db_rack is None:
        raise HTTPException(status_code=404, detail="Rack nije pronađen")

    # Proveravamo da li je uređaj već dodeljen
    if db_device.rack_id is not None:
        raise HTTPException(status_code=400, detail="Uređaj je već dodeljen rack-u")

    # Računamo trenutnu zauzetost rack-a
    active_devices = (
        db.query(models.Device)
        .filter(models.Device.rack_id == db_rack.id, models.Device.deleted_at.is_(None))
        .all()
    )
    current_units = sum(d.units_occupied for d in active_devices)
    current_power = sum(d.power_consumption for d in active_devices)

    # Proveravamo kapacitet
    if current_units + db_device.units_occupied > db_rack.total_units:
        raise HTTPException(status_code=400, detail="Nema dovoljno jedinica u rack-u")
    if current_power + db_device.power_consumption > db_rack.max_power:
        raise HTTPException(status_code=400, detail="Nema dovoljno snage u rack-u")

    before_state = _device_snapshot(db_device)

    # Dodeljujemo uređaj
    db_device.rack_id = rack_id
    db_device.version += 1
    db.commit()

    log_action(
        db,
        actor_username=current_user.username,
        action="device.assign",
        entity_type="device",
        entity_id=db_device.id,
        before_data=before_state,
        after_data=_device_snapshot(db_device),
    )
    db.commit()

    invalidate_stats_cache()

    if idempotency_key:
        _save_assign_idempotency(
            idempotency_key,
            fingerprint=f"{current_user.username}:{device_id}:{rack_id}",
            message="Uređaj dodeljen rack-u",
            now=time.time(),
        )

    return {"message": "Uređaj dodeljen rack-u"}

# Uklanjanje uređaja sa rack-a
@router.post(
    "/devices/{device_id}/unassign",
    response_model=schemas.MessageResponse,
    responses={
        400: {"model": schemas.ErrorResponse},
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
        404: {"model": schemas.ErrorResponse},
    },
)
def unassign_device_from_rack(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("operator", "admin")),
):
    """Uklanja dodelu uređaja sa rack-a."""
    db_device = (
        db.query(models.Device)
        .filter(models.Device.id == device_id, models.Device.deleted_at.is_(None))
        .first()
    )
    if db_device is None:
        raise HTTPException(status_code=404, detail="Uređaj nije pronađen")
    if db_device.rack_id is None:
        raise HTTPException(status_code=400, detail="Uređaj nije dodeljen nijednom rack-u")

    before_state = _device_snapshot(db_device)

    db_device.rack_id = None
    db_device.version += 1
    db.commit()

    log_action(
        db,
        actor_username=current_user.username,
        action="device.unassign",
        entity_type="device",
        entity_id=db_device.id,
        before_data=before_state,
        after_data=_device_snapshot(db_device),
    )
    db.commit()
    invalidate_stats_cache()
    return {"message": "Uređaj uklonjen sa rack-a"}