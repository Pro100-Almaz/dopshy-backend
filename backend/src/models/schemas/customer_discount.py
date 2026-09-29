import datetime
import decimal
import enum

import pydantic

from src.utilities.phone import normalize_kz_phone


class DiscountStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELED = "canceled"


class CustomerInCreate(pydantic.BaseModel):
    phone: str = pydantic.Field(min_length=1)
    name: str | None = None
    is_regular_customer: bool = False

    @pydantic.field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return normalize_kz_phone(value)


class CustomerInUpdate(pydantic.BaseModel):
    phone: str | None = pydantic.Field(default=None, min_length=1)
    name: str | None = None
    is_regular_customer: bool | None = None

    @pydantic.field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        return normalize_kz_phone(value) if value is not None else None


class DiscountInCreate(pydantic.BaseModel):
    customer_id: int = pydantic.Field(gt=0)
    discount_amount: decimal.Decimal = pydantic.Field(gt=0)
    condition: str | None = None
    status: DiscountStatus = DiscountStatus.PENDING
    usage_limit: int = pydantic.Field(default=5, gt=0)


class DiscountInUpdate(pydantic.BaseModel):
    discount_amount: decimal.Decimal | None = pydantic.Field(default=None, gt=0)
    condition: str | None = None
    status: DiscountStatus | None = None
    is_active: bool | None = None
    usage_limit: int | None = pydantic.Field(default=None, gt=0)


class ManagerBookingInCreate(pydantic.BaseModel):
    field: int = pydantic.Field(gt=0)
    date: datetime.date
    time_start: str = pydantic.Field(min_length=1)
    time_end: str = pydantic.Field(min_length=1)
    customer: str | None = None
    customer_id: int | str | None = None
    phone: str | None = pydantic.Field(default=None, min_length=1)
    price_total: decimal.Decimal = pydantic.Field(ge=0)
    discount_id: int | str | None = None
    prepayment: decimal.Decimal = pydantic.Field(default=0, ge=0)
    notes: str | None = None

    @pydantic.field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        return normalize_kz_phone(value) if value is not None else None
