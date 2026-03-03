import datetime
import decimal

import pydantic

from src.models.enums.booking import BookingSource, BookingStatus


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
    start_datetime: datetime.datetime
    duration_hours: int
    total_price: decimal.Decimal
    status: str
    source: str
    created_at: datetime.datetime

    model_config = pydantic.ConfigDict(from_attributes=True)


class BookingDetailOut(BookingOut):
    internal_note: str | None
    status_history: list[BookingStatusHistoryOut] = []
