import datetime
import decimal

import pydantic

from src.models.enums.booking import BookingSource, BookingStatus, RepeatMode


class BookingStatusHistoryOut(pydantic.BaseModel):
    id: int
    booking_id: int
    old_status: str | None
    new_status: str
    changed_by_account_id: int | None
    comment: str | None
    changed_at: datetime.datetime

    model_config = pydantic.ConfigDict(from_attributes=True)


class BookingInCreate(pydantic.BaseModel):
    """Used for LANDING and CHATBOT sources (no auth required)."""

    field_id: int
    guest_name: str
    guest_phone: str
    guest_email: str | None = None
    start_datetime: datetime.datetime
    duration_hours: int = pydantic.Field(ge=1)
    source: BookingSource = BookingSource.LANDING
    internal_note: str | None = None

    @pydantic.model_validator(mode="after")
    def validate_source(self) -> "BookingInCreate":
        if self.source not in (BookingSource.LANDING, BookingSource.CHATBOT):
            raise ValueError("This endpoint only accepts LANDING or CHATBOT source.")
        return self


class BookingInCreateAuthenticated(pydantic.BaseModel):
    """Used by authenticated CLIENT users."""

    field_id: int
    start_datetime: datetime.datetime
    duration_hours: int = pydantic.Field(ge=1)
    internal_note: str | None = None


class BookingInCreateByManager(pydantic.BaseModel):
    """Used by ADMIN/MANAGER staff."""

    field_id: int
    account_id: int | None = None
    guest_name: str | None = None
    guest_phone: str | None = None
    guest_email: str | None = None
    start_datetime: datetime.datetime
    duration_hours: int = pydantic.Field(ge=1)
    internal_note: str | None = None

class BookingInUpdate(pydantic.BaseModel):

    field_id: int | None = None
    customer_name: str | None = None
    time_start: datetime.time | None = None
    time_end: datetime.time | None = None
    date: datetime.date | None = None
    end_date: datetime.date | None = None
    status: BookingStatus | None = None
    paid_kaspi_qr: decimal.Decimal | None = None
    paid_cash: decimal.Decimal | None = None
    paid_avans: decimal.Decimal | None = None

class BatchSlotIn(pydantic.BaseModel):

    field: int = pydantic.Field(gt=0)
    date: str = pydantic.Field(min_length=1)         # "2026-07-20" — first occurrence / start date
    time_start: str = pydantic.Field(min_length=1)   # "10:00"
    time_end: str = pydantic.Field(min_length=1)     # "11:00"; may be "24:00" = end of day
    repeat_mode: RepeatMode = RepeatMode.NONE        # "none" | "daily" | "weekly" | "monthly"
    repeat_until: str | None = None                  # "yyyy-mm-dd"; required only when repeat_mode != "none"


class BookingBatchInCreate(pydantic.BaseModel):
    """Batch booking body proxied to the bot's POST /api/manager/bookings/batch.
    """

    slots: list[BatchSlotIn] = pydantic.Field(min_length=1)
    customer: str | None = None
    phone: str | None = None
    notes: str | None = None
    price_total: decimal.Decimal | None = None
    prepayment: decimal.Decimal | None = None
    reserved_until: int | None = None
    updated_by: str | None = None



class BookingStatusUpdate(pydantic.BaseModel):
    status: BookingStatus
    comment: str | None = None


class BookingOut(pydantic.BaseModel):
    id: int
    field_id: int
    account_id: int | None
    guest_name: str | None
    guest_phone: str | None
    guest_email: str | None
    start_datetime: datetime.time
    duration_hours: int
    total_price: decimal.Decimal
    status: str
    source: str
    created_at: datetime.datetime
    notes: str | None = None
    updated_at: datetime.datetime | None

    model_config = pydantic.ConfigDict(from_attributes=True)


class BookingDetailOut(BookingOut):
    internal_note: str | None
    status_history: list[BookingStatusHistoryOut] = []


class BotBookingRaw(pydantic.BaseModel):
    """Raw booking row as returned by the bot service.
    """
    id: int
    field: int | None = None
    customer_name: str | None = None
    phone: str | None = None
    time_start: datetime.time | None = None
    time_end: datetime.time | None = None
    price_total: decimal.Decimal | None = None
    state: str
    source: str
    notes: str | None = None
    date: datetime.date | None = None
    reserved_until: str | None = None
    paid_bot: decimal.Decimal | None = None
    paid_kaspi_qr: decimal.Decimal | None = None
    paid_cash: decimal.Decimal | None = None
    paid_avans: decimal.Decimal | None = None
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None

    model_config = pydantic.ConfigDict(extra="ignore")

    @pydantic.field_validator(
        "field",
        "price_total",
        "paid_bot",
        "paid_kaspi_qr",
        "paid_cash",
        "paid_avans",
        "time_start",
        "time_end",
        "date",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, v: object) -> object:
        return None if v == "" else v

    def to_booking_out(self) -> BookingOut:
        duration = self.time_end - self.time_start
        duration_hours = max(1, round(duration.total_seconds() / 3600))
        return BookingOut(
            id=self.id,
            field_id=self.field,
            account_id=None,
            guest_name=self.customer_name,
            guest_phone=self.phone,
            guest_email=None,
            start_datetime=self.time_start,
            duration_hours=duration_hours,
            total_price=self.price_total,
            status=self.state,
            source=self.source,
            notes=self.notes,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

