import datetime
import zoneinfo

import pydantic

from src.config.manager import settings
from src.utilities.phone import normalize_kz_phone

_PREFILL_FIELD_IDS = range(1, 4)  # the bot's fields, same le=3 limit as the existing routes


def venue_now() -> datetime.datetime:
    return datetime.datetime.now(tz=zoneinfo.ZoneInfo(settings.PREFILL_VENUE_TZ))


class PrefillCreateIn(pydantic.BaseModel):
    """Booking data the bot collected from the user. The bot sends "" for null."""

    model_config = pydantic.ConfigDict(extra="forbid")

    phone: str
    customer_name: str | None = pydantic.Field(default=None, max_length=128)
    field: int | None = None
    date: datetime.date | None = None
    time_start: datetime.time | None = None
    time_end: datetime.time | None = None
    players: int | None = pydantic.Field(default=None, ge=1, le=100)
    lang: str | None = None
    conversation_id: str | None = pydantic.Field(default=None, max_length=128)

    @pydantic.field_validator(
        "customer_name", "field", "date", "time_start", "time_end", "players", "lang", "conversation_id", mode="before"
    )
    @classmethod
    def _blank_to_none(cls, v: object) -> object:
        return None if v == "" else v

    @pydantic.field_validator("phone", mode="before")
    @classmethod
    def _normalize_phone(cls, v: object) -> object:
        return normalize_kz_phone(v) if isinstance(v, str) else v

    @pydantic.field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str) -> str:
        if len(v) != 11 or not v.startswith("7"):
            raise ValueError("phone must be 11 digits starting with 7.")
        return v

    @pydantic.field_validator("field")
    @classmethod
    def _check_field(cls, v: int | None) -> int | None:
        if v is not None and v not in _PREFILL_FIELD_IDS:
            raise ValueError("field must be between 1 and 3.")
        return v

    @pydantic.field_validator("lang")
    @classmethod
    def _check_lang(cls, v: str | None) -> str | None:
        if v is not None and v not in ("ru", "kk"):
            raise ValueError("lang must be 'ru' or 'kk'.")
        return v

    @pydantic.model_validator(mode="after")
    def _check_schedule(self) -> "PrefillCreateIn":
        if (self.time_start is None) != (self.time_end is None):
            raise ValueError("time_start and time_end must be given together.")
        if self.time_start is not None and self.time_end is not None and self.time_start >= self.time_end:
            raise ValueError("time_start must be before time_end.")
        if self.time_start is not None and self.date is None:
            raise ValueError("date is required when a time is given.")
        if self.date is not None:
            now = venue_now()
            if self.date < now.date():
                raise ValueError("date must not be in the past.")
            if self.date == now.date() and self.time_start is not None and self.time_start <= now.time():
                raise ValueError("time_start has already passed.")
        return self


class PrefillCreatedOut(pydantic.BaseModel):
    token: str
    url: str
    expires_at: datetime.datetime


class PrefillCreateResponse(pydantic.BaseModel):
    ok: bool = True
    data: PrefillCreatedOut


class PrefillAlternativeOut(pydantic.BaseModel):
    time_start: str
    time_end: str


class PrefillOut(pydantic.BaseModel):
    phone_masked: str
    customer_name: str | None = None
    field: int | None = None
    date: datetime.date | None = None
    time_start: str | None = None
    time_end: str | None = None
    players: int | None = None
    lang: str | None = None
    slot_available: bool | None = None
    alternatives: list[PrefillAlternativeOut] = []


def mask_phone(phone: str | None) -> str:
    if not phone or len(phone) < 11:
        return "+7 *** *** ** **"
    return f"+7 {phone[1:4]} *** ** {phone[-2:]}"
