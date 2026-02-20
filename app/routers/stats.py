from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models

router = APIRouter()

# Endpoint za dohvatanje statistika celog data centra
@router.get("/stats/")
def get_stats(db: Session = Depends(get_db)):
    # Broj uređaja
    total_devices = db.query(models.Device).count()

    # Broj rack-ova
    total_racks = db.query(models.Rack).count()

    # Ukupna potrošnja energije svih uređaja
    total_power_consumed = db.query(models.Device).with_entities(models.Device.power_consumption).all()
    total_power = sum(p[0] for p in total_power_consumed)

    # Ukupna maksimalna snaga svih rack-ova
    racks = db.query(models.Rack).all()
    total_max_power = sum(r.max_power for r in racks)

    # Procenat iskorišćenosti
    utilization = (total_power / total_max_power * 100) if total_max_power > 0 else 0

    return {
        "total_devices": total_devices,
        "total_racks": total_racks,
        "total_power_consumed": total_power,
        "total_max_power": total_max_power,
        "overall_utilization_percent": utilization
    }