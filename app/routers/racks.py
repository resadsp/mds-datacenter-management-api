from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app import models, schemas
from app.database import get_db

router = APIRouter()

# Kreiranje novog rack-a
@router.post("/racks/", response_model=schemas.Rack)
def create_rack(rack: schemas.RackCreate, db: Session = Depends(get_db)):
    # Proveravamo jedinstvenost serijskog broja
    db_rack = db.query(models.Rack).filter(models.Rack.serial_number == rack.serial_number).first()
    if db_rack:
        raise HTTPException(status_code=400, detail="Serijski broj već postoji")

    db_rack = models.Rack(**rack.dict())
    db.add(db_rack)
    db.commit()
    db.refresh(db_rack)
    return db_rack

# Lista svih rack-ova sa paginacijom i filtriranjem
@router.get("/racks/", response_model=List[schemas.Rack])
def read_racks(skip: int = 0, limit: int = 100, name: str = None, db: Session = Depends(get_db)):
    query = db.query(models.Rack)
    if name:
        query = query.filter(models.Rack.name.contains(name))  # Filtriranje po nazivu

    racks = query.offset(skip).limit(limit).all()

    # Dinamički računamo trenutnu potrošnju i zauzetost za svaki rack
    for rack in racks:
        rack.current_power = sum(d.power_consumption for d in rack.devices)
        rack.current_units = sum(d.units_occupied for d in rack.devices)

    return racks

# Dohvatanje detalja rack-a sa listom uređaja
@router.get("/racks/{rack_id}", response_model=schemas.RackWithDevices)
def read_rack(rack_id: int, db: Session = Depends(get_db)):
    db_rack = db.query(models.Rack).filter(models.Rack.id == rack_id).first()
    if db_rack is None:
        raise HTTPException(status_code=404, detail="Rack nije pronađen")

    # Računamo trenutne vrednosti
    db_rack.current_power = sum(d.power_consumption for d in db_rack.devices)
    db_rack.current_units = sum(d.units_occupied for d in db_rack.devices)

    return db_rack

# Ažuriranje rack-a
@router.put("/racks/{rack_id}", response_model=schemas.Rack)
def update_rack(rack_id: int, rack: schemas.RackCreate, db: Session = Depends(get_db)):
    db_rack = db.query(models.Rack).filter(models.Rack.id == rack_id).first()
    if db_rack is None:
        raise HTTPException(status_code=404, detail="Rack nije pronađen")

    # Proveravamo jedinstvenost serijskog broja
    existing = db.query(models.Rack).filter(models.Rack.serial_number == rack.serial_number, models.Rack.id != rack_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Serijski broj već postoji")

    # Ažuriramo podatke
    for key, value in rack.dict().items():
        setattr(db_rack, key, value)
    db.commit()
    db.refresh(db_rack)
    return db_rack

# Brisanje rack-a
@router.delete("/racks/{rack_id}")
def delete_rack(rack_id: int, db: Session = Depends(get_db)):
    db_rack = db.query(models.Rack).filter(models.Rack.id == rack_id).first()
    if db_rack is None:
        raise HTTPException(status_code=404, detail="Rack nije pronađen")

    # Ne dozvoljavamo brisanje rack-a sa uređajima
    if db_rack.devices:
        raise HTTPException(status_code=400, detail="Ne može se obrisati rack sa dodeljenim uređajima")

    db.delete(db_rack)
    db.commit()
    return {"message": "Rack obrisan"}