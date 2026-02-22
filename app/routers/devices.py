from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app import models, schemas
from app.database import get_db

router = APIRouter()

# Kreiranje novog uređaja
@router.post("/devices/", response_model=schemas.Device)
def create_device(device: schemas.DeviceCreate, db: Session = Depends(get_db)):
    # Proveravamo da li serijski broj već postoji
    db_device = db.query(models.Device).filter(models.Device.serial_number == device.serial_number).first()
    if db_device:
        raise HTTPException(status_code=400, detail="Serijski broj već postoji")

    # Kreiramo novi uređaj
    db_device = models.Device(**device.model_dump())
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    return db_device

# Lista svih uređaja sa paginacijom i filtriranjem
@router.get("/devices/", response_model=List[schemas.Device])
def read_devices(skip: int = 0, limit: int = 100, name: str = None, db: Session = Depends(get_db)):
    query = db.query(models.Device)
    if name:
        query = query.filter(models.Device.name.contains(name))  # Filtriranje po nazivu
    devices = query.offset(skip).limit(limit).all()
    return devices

# Dohvatanje pojedinačnog uređaja
@router.get("/devices/{device_id}", response_model=schemas.Device)
def read_device(device_id: int, db: Session = Depends(get_db)):
    db_device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if db_device is None:
        raise HTTPException(status_code=404, detail="Uređaj nije pronađen")
    return db_device

# Ažuriranje uređaja
@router.put("/devices/{device_id}", response_model=schemas.Device)
def update_device(device_id: int, device: schemas.DeviceCreate, db: Session = Depends(get_db)):
    db_device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if db_device is None:
        raise HTTPException(status_code=404, detail="Uređaj nije pronađen")

    existing = db.query(models.Device).filter(
        models.Device.serial_number == device.serial_number,
        models.Device.id != device_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Serijski broj već postoji")

    # Ako je uređaj već u rack-u, update ne sme probiti kapacitet rack-a
    if db_device.rack_id is not None:
        rack = db.query(models.Rack).filter(models.Rack.id == db_device.rack_id).first()

        other_devices = [d for d in rack.devices if d.id != db_device.id]
        used_units_without_this = sum(d.units_occupied for d in other_devices)
        used_power_without_this = sum(d.power_consumption for d in other_devices)

        if used_units_without_this + device.units_occupied > rack.total_units:
            raise HTTPException(status_code=400, detail="Update prelazi kapacitet jedinica rack-a")
        if used_power_without_this + device.power_consumption > rack.max_power:
            raise HTTPException(status_code=400, detail="Update prelazi kapacitet snage rack-a")

    for key, value in device.model_dump().items():
        setattr(db_device, key, value)

    db.commit()
    db.refresh(db_device)
    return db_device

# Brisanje uređaja
@router.delete("/devices/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db)):
    db_device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if db_device is None:
        raise HTTPException(status_code=404, detail="Uređaj nije pronađen")
    db.delete(db_device)
    db.commit()
    return {"message": "Uređaj obrisan"}

# Dodeljivanje uređaja rack-u
@router.post("/devices/{device_id}/assign/{rack_id}")
def assign_device_to_rack(device_id: int, rack_id: int, db: Session = Depends(get_db)):
    # Pronalazimo uređaj
    db_device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if db_device is None:
        raise HTTPException(status_code=404, detail="Uređaj nije pronađen")

    # Pronalazimo rack
    db_rack = db.query(models.Rack).filter(models.Rack.id == rack_id).first()
    if db_rack is None:
        raise HTTPException(status_code=404, detail="Rack nije pronađen")

    # Proveravamo da li je uređaj već dodeljen
    if db_device.rack_id is not None:
        raise HTTPException(status_code=400, detail="Uređaj je već dodeljen rack-u")

    # Računamo trenutnu zauzetost rack-a
    current_units = sum(d.units_occupied for d in db_rack.devices)
    current_power = sum(d.power_consumption for d in db_rack.devices)

    # Proveravamo kapacitet
    if current_units + db_device.units_occupied > db_rack.total_units:
        raise HTTPException(status_code=400, detail="Nema dovoljno jedinica u rack-u")
    if current_power + db_device.power_consumption > db_rack.max_power:
        raise HTTPException(status_code=400, detail="Nema dovoljno snage u rack-u")

    # Dodeljujemo uređaj
    db_device.rack_id = rack_id
    db.commit()
    return {"message": "Uređaj dodeljen rack-u"}

# Uklanjanje uređaja sa rack-a
@router.post("/devices/{device_id}/unassign")
def unassign_device_from_rack(device_id: int, db: Session = Depends(get_db)):
    db_device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if db_device is None:
        raise HTTPException(status_code=404, detail="Uređaj nije pronađen")
    if db_device.rack_id is None:
        raise HTTPException(status_code=400, detail="Uređaj nije dodeljen nijednom rack-u")

    db_device.rack_id = None
    db.commit()
    return {"message": "Uređaj uklonjen sa rack-a"}