from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from open_garage_erp.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class UserRole(StrEnum):
    OWNER = "owner"
    SERVICE_ADVISOR = "service_advisor"
    TECHNICIAN = "technician"
    ACCOUNTANT = "accountant"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class Shop(TimestampMixin, Base):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'service_advisor', 'technician', 'accountant')",
            name="ck_users_role",
        ),
        UniqueConstraint("shop_id", "email", name="uq_users_shop_email"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="RESTRICT"))
    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            values_callable=lambda roles: [role.value for role in roles],
            native_enum=False,
            create_constraint=False,
            length=32,
        )
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LoginAttempt(TimestampMixin, Base):
    __tablename__ = "login_attempts"

    shop_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), primary_key=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SessionToken(TimestampMixin, Base):
    __tablename__ = "session_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)


class Vehicle(TimestampMixin, Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint("year >= 1886 AND year <= 2200", name="ck_vehicles_year_range"),
        Index("ix_vehicles_customer_id", "customer_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"))
    vin: Mapped[str | None] = mapped_column(String(17), nullable=True, unique=True)
    year: Mapped[int] = mapped_column(Integer)
    make: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    license_plate: Mapped[str | None] = mapped_column(String(20), nullable=True)


class RepairOrder(TimestampMixin, Base):
    __tablename__ = "repair_orders"
    __table_args__ = (
        CheckConstraint("estimate_cents >= 0", name="ck_repair_orders_estimate_nonnegative"),
        CheckConstraint(
            "status IN ('draft', 'approved', 'in_progress', 'completed', 'cancelled')",
            name="ck_repair_orders_status",
        ),
        Index("ix_repair_orders_vehicle_id", "vehicle_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="RESTRICT"))
    description: Mapped[str] = mapped_column(String(2000))
    estimate_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")
