"""Endpointi za agregirane statistike data centra."""

import os
import time
from threading import Lock

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.auth import require_roles

router = APIRouter()

STATS_CACHE_TTL_SECONDS = int(os.getenv("STATS_CACHE_TTL_SECONDS", "30"))
_stats_cache_lock = Lock()
_stats_cache_payload = None
_stats_cache_expires_at = 0.0


def invalidate_stats_cache() -> None:
    global _stats_cache_payload, _stats_cache_expires_at
    with _stats_cache_lock:
        _stats_cache_payload = None
        _stats_cache_expires_at = 0.0


def _get_cached_stats():
    now = time.time()
    with _stats_cache_lock:
        if _stats_cache_payload is None or now >= _stats_cache_expires_at:
            return None
        return dict(_stats_cache_payload)


def _set_cached_stats(payload: dict) -> None:
    global _stats_cache_payload, _stats_cache_expires_at
    ttl = max(STATS_CACHE_TTL_SECONDS, 1)
    with _stats_cache_lock:
        _stats_cache_payload = dict(payload)
        _stats_cache_expires_at = time.time() + ttl

# Endpoint za dohvatanje statistika celog data centra
@router.get(
    "/stats/",
    responses={
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
    },
)
def get_stats(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles("viewer", "operator", "admin")),
):
    """Vraća globalne brojače i metrike iskorišćenosti data centra."""
    cached_payload = _get_cached_stats()
    if cached_payload is not None:
        return cached_payload

    # Broj uređaja
    total_devices = db.query(models.Device).filter(models.Device.deleted_at.is_(None)).count()

    # Broj rack-ova
    total_racks = db.query(models.Rack).filter(models.Rack.deleted_at.is_(None)).count()

    # Ukupna potrošnja energije svih uređaja
    total_power_consumed = (
        db.query(models.Device)
        .filter(models.Device.deleted_at.is_(None))
        .with_entities(models.Device.power_consumption)
        .all()
    )
    total_power = sum(p[0] for p in total_power_consumed)

    # Ukupna maksimalna snaga svih rack-ova
    racks = db.query(models.Rack).filter(models.Rack.deleted_at.is_(None)).all()
    total_max_power = sum(r.max_power for r in racks)

    # Procenat iskorišćenosti
    utilization = (total_power / total_max_power * 100) if total_max_power > 0 else 0

    payload = {
        "total_devices": total_devices,
        "total_racks": total_racks,
        "total_power_consumed": total_power,
        "total_max_power": total_max_power,
        "overall_utilization_percent": utilization
    }
    _set_cached_stats(payload)
    return payload