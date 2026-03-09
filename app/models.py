from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="viewer")
    is_active = Column(Boolean, nullable=False, default=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_username = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=False, index=True)
    entity_id = Column(Integer, nullable=True)
    before_data = Column(Text, nullable=True)
    after_data = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)

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
    deleted_at = Column(DateTime, nullable=True)
    version = Column(Integer, nullable=False, default=1)

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
    deleted_at = Column(DateTime, nullable=True)
    version = Column(Integer, nullable=False, default=1)

    # Relacija ka uređajima (jedan rack može imati više uređaja)
    devices = relationship("Device", back_populates="rack")