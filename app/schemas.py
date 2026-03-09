from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    refresh_expires_in: Optional[int] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserBase(BaseModel):
    username: str
    role: str = Field(default="viewer", pattern="^(admin|operator|viewer)$")
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserOut(UserBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class AuditLogOut(BaseModel):
    id: int
    actor_username: str
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    before_data: Optional[str] = None
    after_data: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginationMeta(BaseModel):
    total: int
    page: int
    page_size: int
    sort_by: str
    sort_order: str


class AuditLogPage(BaseModel):
    items: list[AuditLogOut]
    meta: PaginationMeta

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


class DeviceUpdate(DeviceBase):
    version: int = Field(..., ge=1)

# Šema za prikaz uređaja sa ID i rack_id
class Device(DeviceBase):
    id: int  # Jedinstveni ID
    rack_id: Optional[int] = None  # ID rack-a ako je dodeljen
    deleted_at: Optional[datetime] = None
    version: int = 1

    model_config = ConfigDict(from_attributes=True)  # Dozvoljava konverziju iz SQLAlchemy modela


class DevicePage(BaseModel):
    items: list[Device]
    meta: PaginationMeta

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


class RackUpdate(RackBase):
    version: int = Field(..., ge=1)

# Šema za prikaz rack-a sa trenutnim stanjem
class Rack(RackBase):
    id: int  # Jedinstveni ID
    current_power: float = 0.0  # Trenutna potrošnja
    current_units: int = 0  # Trenutno zauzete jedinice
    deleted_at: Optional[datetime] = None
    version: int = 1

    model_config = ConfigDict(from_attributes=True)


class RackPage(BaseModel):
    items: list[Rack]
    meta: PaginationMeta

# Šema za detaljan prikaz rack-a sa listom uređaja
class RackWithDevices(Rack):
    devices: list[Device] = Field(default_factory=list)  # Lista uređaja u rack-u

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