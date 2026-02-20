from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

# Model za uređaj u data centru
class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)  # Jedinstveni identifikator
    name = Column(String, nullable=False)  # Naziv uređaja
    description = Column(String)  # Opis uređaja
    serial_number = Column(String, unique=True, nullable=False)  # Jedinstveni serijski broj
    units_occupied = Column(Integer, nullable=False)  # Broj jedinica koje zauzima u rack-u
    power_consumption = Column(Float, nullable=False)  # Potrošnja energije u Watima
    rack_id = Column(Integer, ForeignKey("racks.id"), nullable=True)  # ID rack-a gde je smešten

    # Relacija ka rack-u (jedan uređaj pripada jednom rack-u)
    rack = relationship("Rack", back_populates="devices")

# Model za rack u data centru
class Rack(Base):
    __tablename__ = "racks"

    id = Column(Integer, primary_key=True, index=True)  # Jedinstveni identifikator
    name = Column(String, nullable=False)  # Naziv rack-a
    description = Column(String)  # Opis rack-a
    serial_number = Column(String, unique=True, nullable=False)  # Jedinstveni serijski broj
    total_units = Column(Integer, nullable=False)  # Ukupan broj jedinica (npr. 42U)
    max_power = Column(Float, nullable=False)  # Maksimalna potrošnja energije u Watima

    # Relacija ka uređajima (jedan rack može imati više uređaja)
    devices = relationship("Device", back_populates="rack")