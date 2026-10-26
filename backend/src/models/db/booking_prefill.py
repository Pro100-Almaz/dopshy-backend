import datetime

import sqlalchemy
from sqlalchemy.orm import Mapped as SQLAlchemyMapped, mapped_column as sqlalchemy_mapped_column
from sqlalchemy.sql import functions as sqlalchemy_functions

from src.repository.table import Base


class BookingPrefill(Base):  # type: ignore
    """Booking data collected by the bot, resolved by the landing through an opaque token.

    ``field_id`` is the bot's field id, not a FK: the bot owns fields and bookings.
    """

    __tablename__ = "booking_prefill"

    id: SQLAlchemyMapped[int] = sqlalchemy_mapped_column(primary_key=True, autoincrement="auto")
    token_hash: SQLAlchemyMapped[str] = sqlalchemy_mapped_column(
        sqlalchemy.String(length=64), nullable=False, unique=True, index=True
    )
    phone: SQLAlchemyMapped[str | None] = sqlalchemy_mapped_column(sqlalchemy.String(length=32), nullable=True)
    customer_name: SQLAlchemyMapped[str | None] = sqlalchemy_mapped_column(
        sqlalchemy.String(length=128), nullable=True
    )
    field_id: SQLAlchemyMapped[int | None] = sqlalchemy_mapped_column(sqlalchemy.SmallInteger, nullable=True)
    date: SQLAlchemyMapped[datetime.date | None] = sqlalchemy_mapped_column(sqlalchemy.Date, nullable=True)
    time_start: SQLAlchemyMapped[datetime.time | None] = sqlalchemy_mapped_column(sqlalchemy.Time, nullable=True)
    time_end: SQLAlchemyMapped[datetime.time | None] = sqlalchemy_mapped_column(sqlalchemy.Time, nullable=True)
    players: SQLAlchemyMapped[int | None] = sqlalchemy_mapped_column(sqlalchemy.SmallInteger, nullable=True)
    lang: SQLAlchemyMapped[str | None] = sqlalchemy_mapped_column(sqlalchemy.String(length=2), nullable=True)
    source: SQLAlchemyMapped[str] = sqlalchemy_mapped_column(
        sqlalchemy.String(length=32), nullable=False, default="bot_link", server_default="bot_link"
    )
    conversation_id: SQLAlchemyMapped[str | None] = sqlalchemy_mapped_column(
        sqlalchemy.String(length=128), nullable=True
    )
    created_at: SQLAlchemyMapped[datetime.datetime] = sqlalchemy_mapped_column(
        sqlalchemy.DateTime(timezone=True), nullable=False, server_default=sqlalchemy_functions.now()
    )
    expires_at: SQLAlchemyMapped[datetime.datetime] = sqlalchemy_mapped_column(
        sqlalchemy.DateTime(timezone=True), nullable=False, index=True
    )
    first_opened_at: SQLAlchemyMapped[datetime.datetime | None] = sqlalchemy_mapped_column(
        sqlalchemy.DateTime(timezone=True), nullable=True
    )
    consumed_at: SQLAlchemyMapped[datetime.datetime | None] = sqlalchemy_mapped_column(
        sqlalchemy.DateTime(timezone=True), nullable=True
    )
    bot_booking_ids: SQLAlchemyMapped[list[int] | None] = sqlalchemy_mapped_column(sqlalchemy.JSON, nullable=True)
