"""CRUD endpointi za rack-ove i operacije uz proveru kapaciteta."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models, schemas
from app.auth import require_roles
from app.audit import log_action
from app.database import get_db
from app.routers.stats import invalidate_stats_cache

router = APIRouter()


def _rack_snapshot(rack: models.Rack) -> dict:
    return {
        "id": rack.id,
        "name": rack.name,
        "description": rack.description,
        "serial_number": rack.serial_number,
        "total_units": rack.total_units,
        "max_power": rack.max_power,
        "version": rack.version,
        "deleted_at": rack.deleted_at,
    }

# Kreiranje novog rack-a
@router.post(
    "/racks/",
    response_model=schemas.Rack,
    responses={
        400: {"model": schemas.ErrorResponse},
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
    },
)
def create_rack(
    rack: schemas.RackCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("operator", "admin")),
):
    """Kreira novi rack nakon provere jedinstvenosti serijskog broja."""
    # Proveravamo jedinstvenost serijskog broja
    db_rack = db.query(models.Rack).filter(models.Rack.serial_number == rack.serial_number).first()
    if db_rack:
        raise HTTPException(status_code=400, detail="Serijski broj već postoji")

    db_rack = models.Rack(**rack.model_dump())
    db.add(db_rack)
    db.commit()
    db.refresh(db_rack)

    log_action(
        db,
        actor_username=current_user.username,
        action="rack.create",
        entity_type="rack",
        entity_id=db_rack.id,
        after_data=_rack_snapshot(db_rack),
    )
    db.commit()
    invalidate_stats_cache()
    return db_rack

# Lista svih rack-ova sa paginacijom i filtriranjem
@router.get(
    "/racks/",
    response_model=schemas.RackPage,
    responses={
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
    },
)
def read_racks(
    page: int = 1,
    page_size: int = 20,
    name: str | None = None,
    serial_number: str | None = None,
    include_deleted: bool = False,
    sort_by: str = "id",
    sort_order: str = "asc",
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles("viewer", "operator", "admin")),
):
    """Vraća paginiranu listu rack-ova, sa standardnim page/page_size/sort/filter parametrima."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    page_size = min(page_size, 100)

    allowed_sort_fields = {
        "id": models.Rack.id,
        "name": models.Rack.name,
        "serial_number": models.Rack.serial_number,
        "total_units": models.Rack.total_units,
        "max_power": models.Rack.max_power,
    }
    sort_column = allowed_sort_fields.get(sort_by, models.Rack.id)
    normalized_sort_by = sort_by if sort_by in allowed_sort_fields else "id"
    sort_order = "desc" if sort_order.lower() == "desc" else "asc"

    query = db.query(models.Rack)
    if not include_deleted:
        query = query.filter(models.Rack.deleted_at.is_(None))
    if name:
        query = query.filter(models.Rack.name.contains(name))  # Filtriranje po nazivu
    if serial_number:
        query = query.filter(models.Rack.serial_number.contains(serial_number))

    total = query.count()
    ordering = sort_column.desc() if sort_order == "desc" else sort_column.asc()
    offset = (page - 1) * page_size
    racks = query.order_by(ordering).offset(offset).limit(page_size).all()

    # Dinamički računamo trenutnu potrošnju i zauzetost za svaki rack
    for rack in racks:
        active_devices = (
            db.query(models.Device)
            .filter(models.Device.rack_id == rack.id, models.Device.deleted_at.is_(None))
            .all()
        )
        rack.current_power = sum(d.power_consumption for d in active_devices)
        rack.current_units = sum(d.units_occupied for d in active_devices)

    return {
        "items": racks,
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "sort_by": normalized_sort_by,
            "sort_order": sort_order,
        },
    }

# Dohvatanje detalja rack-a sa listom uređaja
@router.get(
    "/racks/{rack_id}",
    response_model=schemas.RackWithDevices,
    responses={
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
        404: {"model": schemas.ErrorResponse},
    },
)
def read_rack(
    rack_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles("viewer", "operator", "admin")),
):
    """Vraća detalje rack-a zajedno sa trenutno dodeljenim uređajima."""
    db_rack = (
        db.query(models.Rack)
        .filter(models.Rack.id == rack_id, models.Rack.deleted_at.is_(None))
        .first()
    )
    if db_rack is None:
        raise HTTPException(status_code=404, detail="Rack nije pronađen")

    active_devices = (
        db.query(models.Device)
        .filter(models.Device.rack_id == db_rack.id, models.Device.deleted_at.is_(None))
        .all()
    )

    # Računamo trenutne vrednosti
    current_power = sum(d.power_consumption for d in active_devices)
    current_units = sum(d.units_occupied for d in active_devices)

    return {
        "id": db_rack.id,
        "name": db_rack.name,
        "description": db_rack.description,
        "serial_number": db_rack.serial_number,
        "total_units": db_rack.total_units,
        "max_power": db_rack.max_power,
        "current_power": current_power,
        "current_units": current_units,
        "version": db_rack.version,
        "deleted_at": db_rack.deleted_at,
        "devices": active_devices,
    }

# Ažuriranje rack-a
@router.put(
    "/racks/{rack_id}",
    response_model=schemas.Rack,
    responses={
        400: {"model": schemas.ErrorResponse},
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
        404: {"model": schemas.ErrorResponse},
        409: {"model": schemas.ErrorResponse},
    },
)
def update_rack(
    rack_id: int,
    rack: schemas.RackUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("operator", "admin")),
):
    """Ažurira rack bez narušavanja trenutne zauzetosti i potrošnje."""
    db_rack = (
        db.query(models.Rack)
        .filter(models.Rack.id == rack_id, models.Rack.deleted_at.is_(None))
        .first()
    )
    if db_rack is None:
        raise HTTPException(status_code=404, detail="Rack nije pronađen")

    if db_rack.version != rack.version:
        raise HTTPException(status_code=409, detail="Konflikt verzije rack-a. Osvežite podatke i pokušajte ponovo.")

    before_state = _rack_snapshot(db_rack)

    existing = db.query(models.Rack).filter(
        models.Rack.serial_number == rack.serial_number,
        models.Rack.id != rack_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Serijski broj već postoji")

    active_devices = (
        db.query(models.Device)
        .filter(models.Device.rack_id == db_rack.id, models.Device.deleted_at.is_(None))
        .all()
    )
    current_units = sum(d.units_occupied for d in active_devices)
    current_power = sum(d.power_consumption for d in active_devices)

    if rack.total_units < current_units:
        raise HTTPException(status_code=400, detail="Novi total_units je manji od trenutne zauzetosti")
    if rack.max_power < current_power:
        raise HTTPException(status_code=400, detail="Novi max_power je manji od trenutne potrošnje")

    update_payload = rack.model_dump(exclude={"version"})
    affected_rows = (
        db.query(models.Rack)
        .filter(
            models.Rack.id == rack_id,
            models.Rack.deleted_at.is_(None),
            models.Rack.version == rack.version,
        )
        .update(
            {
                **update_payload,
                models.Rack.version: models.Rack.version + 1,
            },
            synchronize_session=False,
        )
    )
    if affected_rows == 0:
        db.rollback()
        raise HTTPException(status_code=409, detail="Konflikt verzije rack-a. Osvežite podatke i pokušajte ponovo.")

    db.commit()
    db_rack = (
        db.query(models.Rack)
        .filter(models.Rack.id == rack_id, models.Rack.deleted_at.is_(None))
        .first()
    )
    if db_rack is None:
        raise HTTPException(status_code=404, detail="Rack nije pronađen")

    log_action(
        db,
        actor_username=current_user.username,
        action="rack.update",
        entity_type="rack",
        entity_id=db_rack.id,
        before_data=before_state,
        after_data=_rack_snapshot(db_rack),
    )
    db.commit()
    invalidate_stats_cache()
    return db_rack

# Brisanje rack-a
@router.delete(
    "/racks/{rack_id}",
    response_model=schemas.MessageResponse,
    responses={
        400: {"model": schemas.ErrorResponse},
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
        404: {"model": schemas.ErrorResponse},
    },
)
def delete_rack(
    rack_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("operator", "admin")),
):
    """Soft-delete praznog rack-a (bez aktivnih dodeljenih uređaja)."""
    db_rack = (
        db.query(models.Rack)
        .filter(models.Rack.id == rack_id, models.Rack.deleted_at.is_(None))
        .first()
    )
    if db_rack is None:
        raise HTTPException(status_code=404, detail="Rack nije pronađen")

    # Ne dozvoljavamo brisanje rack-a sa uređajima
    has_active_devices = (
        db.query(models.Device)
        .filter(models.Device.rack_id == db_rack.id, models.Device.deleted_at.is_(None))
        .first()
    )
    if has_active_devices:
        raise HTTPException(status_code=400, detail="Ne može se obrisati rack sa dodeljenim uređajima")

    before_state = _rack_snapshot(db_rack)

    db_rack.deleted_at = datetime.now(timezone.utc)
    db_rack.version += 1
    db.commit()

    log_action(
        db,
        actor_username=current_user.username,
        action="rack.soft_delete",
        entity_type="rack",
        entity_id=db_rack.id,
        before_data=before_state,
        after_data=_rack_snapshot(db_rack),
    )
    db.commit()
    invalidate_stats_cache()
    return {"message": "Rack arhiviran"}


@router.post(
    "/racks/{rack_id}/restore",
    response_model=schemas.MessageResponse,
    responses={
        400: {"model": schemas.ErrorResponse},
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
        404: {"model": schemas.ErrorResponse},
    },
)
def restore_rack(
    rack_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("operator", "admin")),
):
    """Vraća arhivirani rack u aktivno stanje."""
    db_rack = db.query(models.Rack).filter(models.Rack.id == rack_id).first()
    if db_rack is None:
        raise HTTPException(status_code=404, detail="Rack nije pronađen")
    if db_rack.deleted_at is None:
        raise HTTPException(status_code=400, detail="Rack nije arhiviran")

    before_state = _rack_snapshot(db_rack)

    db_rack.deleted_at = None
    db_rack.version += 1
    db.commit()

    log_action(
        db,
        actor_username=current_user.username,
        action="rack.restore",
        entity_type="rack",
        entity_id=db_rack.id,
        before_data=before_state,
        after_data=_rack_snapshot(db_rack),
    )
    db.commit()
    invalidate_stats_cache()
    return {"message": "Rack vraćen iz arhive"}