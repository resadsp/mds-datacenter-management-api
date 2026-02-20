from pydantic import BaseModel, Field
from typing import Optional

# Osnovna šema za uređaj - zajednička za kreiranje i prikaz
class DeviceBase(BaseModel):
    name: str  # Naziv uređaja
    description: Optional[str] = None  # Opcioni opis
    serial_number: str  # Serijski broj - mora biti jedinstven
    units_occupied: int = Field(..., gt=0)  # Broj jedinica - mora biti pozitivan
    power_consumption: float = Field(..., gt=0)  # Potrošnja - mora biti pozitivna

# Šema za kreiranje novog uređaja
class DeviceCreate(DeviceBase):
    pass

# Šema za prikaz uređaja sa ID i rack_id
class Device(DeviceBase):
    id: int  # Jedinstveni ID
    rack_id: Optional[int] = None  # ID rack-a ako je dodeljen

    class Config:
        from_attributes = True  # Dozvoljava konverziju iz SQLAlchemy modela

# Osnovna šema za rack
class RackBase(BaseModel):
    name: str  # Naziv rack-a
    description: Optional[str] = None  # Opcioni opis
    serial_number: str  # Serijski broj - jedinstven
    total_units: int = Field(..., gt=0)  # Ukupan broj jedinica
    max_power: float = Field(..., gt=0)  # Maksimalna snaga

# Šema za kreiranje rack-a
class RackCreate(RackBase):
    pass

# Šema za prikaz rack-a sa trenutnim stanjem
class Rack(RackBase):
    id: int  # Jedinstveni ID
    current_power: float = 0.0  # Trenutna potrošnja
    current_units: int = 0  # Trenutno zauzete jedinice

    class Config:
        from_attributes = True

# Šema za detaljan prikaz rack-a sa listom uređaja
class RackWithDevices(Rack):
    devices: list[Device] = []  # Lista uređaja u rack-u

# Šema za zahtev balansiranja - lista uređaja i rack-ova
class BalancingRequest(BaseModel):
    devices: list[DeviceCreate]  # Uređaji za raspored
    racks: list[RackCreate]  # Dostupni rack-ovi

# Šema za jednu dodelu u balansiranju
class Assignment(BaseModel):
    device_id: int  # Indeks uređaja
    rack_id: int  # Indeks rack-a

# Šema za odgovor balansiranja
class BalancingResponse(BaseModel):
    assignments: list[Assignment]  # Lista dodela
    unassigned_devices: list[int]  # Indeksi nedodeljenih uređaja