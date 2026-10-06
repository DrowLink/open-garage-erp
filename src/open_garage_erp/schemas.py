from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_serializer

MAX_SQLITE_INTEGER = 2**63 - 1


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)


class TimestampedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return aware.isoformat().replace("+00:00", "Z")


class CustomerResponse(TimestampedResponse):
    id: int
    name: str
    email: str | None
    phone: str | None


class VehicleCreate(BaseModel):
    customer_id: int = Field(gt=0, le=MAX_SQLITE_INTEGER)
    vin: str | None = Field(default=None, min_length=17, max_length=17)
    year: int = Field(ge=1886, le=2200)
    make: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    license_plate: str | None = Field(default=None, max_length=20)


class VehicleResponse(TimestampedResponse):
    id: int
    customer_id: int
    vin: str | None
    year: int
    make: str
    model: str
    license_plate: str | None


class RepairOrderStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RepairOrderCreate(BaseModel):
    vehicle_id: int = Field(gt=0, le=MAX_SQLITE_INTEGER)
    description: str = Field(min_length=1, max_length=2000)
    estimate_cents: StrictInt = Field(ge=0, le=MAX_SQLITE_INTEGER)


class RepairOrderStatusUpdate(BaseModel):
    status: RepairOrderStatus


class RepairOrderResponse(TimestampedResponse):
    id: int
    vehicle_id: int
    description: str
    estimate_cents: int
    status: RepairOrderStatus
