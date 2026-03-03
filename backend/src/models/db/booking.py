import datetime
import decimal

import sqlalchemy
from sqlalchemy.orm import Mapped as SQLAlchemyMapped, mapped_column as sqlalchemy_mapped_column, relationship
from sqlalchemy.sql import functions as sqlalchemy_functions

from src.repository.table import Base


class Booking(Base):  # type: ignore
    __tablename__ = "booking"

    id: SQLAlchemyMapped[int] = sqlalchemy_mapped_column(primary_key=True, autoincrement="auto")
    field_id: SQLAlchemyMapped[int] = sqlalchemy_mapped_column(
        sqlalchemy.ForeignKey("field.id", ondelete="RESTRICT"), nullable=False
    )
    account_id: SQLAlchemyMapped[int | None] = sqlalchemy_mapped_column(
        sqlalchemy.ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    guest_name: SQLAlchemyMapped[str | None] = sqlalchemy_mapped_column(sqlalchemy.String(length=128), nullable=True)
    guest_phone: SQLAlchemyMapped[str | None] = sqlalchemy_mapped_column(sqlalchemy.String(length=32), nullable=True)
    guest_email: SQLAlchemyMapped[str | None] = sqlalchemy_mapped_column(sqlalchemy.String(length=128), nullable=True)
    start_datetime: SQLAlchemyMapped[datetime.datetime] = sqlalchemy_mapped_column(
        sqlalchemy.DateTime(timezone=True), nullable=False, index=True
    )
    duration_hours: SQLAlchemyMapped[int] = sqlalchemy_mapped_column(sqlalchemy.SmallInteger, nullable=False)
    total_price: SQLAlchemyMapped[decimal.Decimal] = sqlalchemy_mapped_column(
        sqlalchemy.Numeric(precision=10, scale=2), nullable=False
    )
    status: SQLAlchemyMapped[str] = sqlalchemy_mapped_column(sqlalchemy.String(length=16), nullable=False)
    source: SQLAlchemyMapped[str] = sqlalchemy_mapped_column(sqlalchemy.String(length=16), nullable=False)
    internal_note: SQLAlchemyMapped[str | None] = sqlalchemy_mapped_column(sqlalchemy.Text, nullable=True)
    created_at: SQLAlchemyMapped[datetime.datetime] = sqlalchemy_mapped_column(
        sqlalchemy.DateTime(timezone=True), nullable=False, server_default=sqlalchemy_functions.now()
    )
    updated_at: SQLAlchemyMapped[datetime.datetime | None] = sqlalchemy_mapped_column(
        sqlalchemy.DateTime(timezone=True),
        nullable=True,
        server_onupdate=sqlalchemy.schema.FetchedValue(for_update=True),
    )

    field: SQLAlchemyMapped["Field"] = relationship("Field", back_populates="bookings")  # type: ignore[name-defined]
    account: SQLAlchemyMapped["Account"] = relationship("Account")  # type: ignore[name-defined]
    status_history: SQLAlchemyMapped[list["BookingStatusHistory"]] = relationship(
        "BookingStatusHistory", back_populates="booking", cascade="all, delete-orphan"
    )

    __mapper_args__ = {"eager_defaults": True}


class BookingStatusHistory(Base):  # type: ignore
    __tablename__ = "booking_status_history"

    id: SQLAlchemyMapped[int] = sqlalchemy_mapped_column(primary_key=True, autoincrement="auto")
    booking_id: SQLAlchemyMapped[int] = sqlalchemy_mapped_column(
        sqlalchemy.ForeignKey("booking.id", ondelete="CASCADE"), nullable=False
    )
    old_status: SQLAlchemyMapped[str | None] = sqlalchemy_mapped_column(
        sqlalchemy.String(length=16), nullable=True
    )
    new_status: SQLAlchemyMapped[str] = sqlalchemy_mapped_column(sqlalchemy.String(length=16), nullable=False)
    changed_by_account_id: SQLAlchemyMapped[int | None] = sqlalchemy_mapped_column(
        sqlalchemy.ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    comment: SQLAlchemyMapped[str | None] = sqlalchemy_mapped_column(sqlalchemy.Text, nullable=True)
    changed_at: SQLAlchemyMapped[datetime.datetime] = sqlalchemy_mapped_column(
        sqlalchemy.DateTime(timezone=True), nullable=False, server_default=sqlalchemy_functions.now()
    )

    booking: SQLAlchemyMapped["Booking"] = relationship("Booking", back_populates="status_history")
