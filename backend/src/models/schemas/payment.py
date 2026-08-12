import datetime
import decimal
import typing

import pydantic

from src.services.apipay import MAX_INVOICE_AMOUNT, MIN_INVOICE_AMOUNT, normalize_kz_phone


class PaymentInCreate(pydantic.BaseModel):
    """Request to bill a customer through Kaspi Pay.

    The frontend decides the amount (full price, prepayment, whatever the business
    rule is); the backend only validates that Kaspi will accept it.
    """

    phone_number: str = pydantic.Field(description="Номер клиента, например +7 700 123 45 67")
    amount: int = pydantic.Field(
        ge=MIN_INVOICE_AMOUNT,
        le=MAX_INVOICE_AMOUNT,
        description="Сумма в целых тенге — Kaspi не принимает копейки для счетов на номер.",
    )
    booking_id: int | None = pydantic.Field(default=None, description="ID брони в бот-сервисе, если платёж за бронь.")
    description: str | None = pydantic.Field(default=None, max_length=500)

    @pydantic.field_validator("phone_number")
    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        return normalize_kz_phone(value)


class PaymentRefundIn(pydantic.BaseModel):
    amount: int | None = pydantic.Field(
        default=None,
        ge=MIN_INVOICE_AMOUNT,
        le=MAX_INVOICE_AMOUNT,
        description="Сумма возврата в тенге. Пусто — полный возврат.",
    )


class PaymentSimulateIn(pydantic.BaseModel):
    """Sandbox-only status push, used to test the flow without a live Kaspi cashier."""

    status: typing.Literal["paid", "cancelled", "expired", "error", "qr_scanned"]
    error_message: str | None = None


class PaymentOut(pydantic.BaseModel):
    id: int
    external_order_id: str
    apipay_invoice_id: int | None
    booking_id: int | None
    account_id: int | None
    phone: str
    amount: decimal.Decimal
    refunded_amount: decimal.Decimal
    description: str | None
    status: str
    error_code: str | None
    error_message: str | None
    paid_at: datetime.datetime | None
    bot_notified_at: datetime.datetime | None
    bot_notify_error: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime | None

    model_config = pydantic.ConfigDict(from_attributes=True)


class WebhookAck(pydantic.BaseModel):
    """Body returned to ApiPay. Only the 2xx status code matters to them."""

    ok: bool = True
    event: str | None = None
    handled: bool = True
