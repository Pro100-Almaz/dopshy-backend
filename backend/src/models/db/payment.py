import datetime
import decimal
import typing

import sqlalchemy
from sqlalchemy.orm import Mapped as SQLAlchemyMapped, mapped_column as sqlalchemy_mapped_column, relationship
from sqlalchemy.sql import functions as sqlalchemy_functions

from src.repository.table import Base


class Payment(Base):  # type: ignore
    """An ApiPay invoice — one Kaspi Pay payment request sent to a customer's phone.

    ApiPay never holds the money: it asks Kaspi to push a payment request to the
    customer, and the funds land straight in the owner's Kaspi Pay account. This
    table is our own ledger of what we asked for and what ApiPay reported back.
    """

    __tablename__ = "payment"

    id: SQLAlchemyMapped[int] = sqlalchemy_mapped_column(primary_key=True, autoincrement="auto")
    # Our identifier, sent to ApiPay as `external_order_id` so both sides can reconcile.
    # Doubles as the idempotency key on invoice creation.
    external_order_id: SQLAlchemyMapped[str] = sqlalchemy_mapped_column(
        sqlalchemy.String(length=64), nullable=False, unique=True, index=True
    )
    # ApiPay's invoice id. NULL only in the brief window between our INSERT and a
    # successful POST /invoices (or permanently, if that call failed).
    apipay_invoice_id: SQLAlchemyMapped[int | None] = sqlalchemy_mapped_column(
        sqlalchemy.BigInteger, nullable=True, unique=True, index=True
    )
    # Bot-service booking id. Deliberately not a foreign key: the authoritative
    # booking rows live in the bot project, this backend only mirrors some of them.
    booking_id: SQLAlchemyMapped[int | None] = sqlalchemy_mapped_column(sqlalchemy.Integer, nullable=True, index=True)
    account_id: SQLAlchemyMapped[int | None] = sqlalchemy_mapped_column(
        sqlalchemy.ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    phone: SQLAlchemyMapped[str] = sqlalchemy_mapped_column(sqlalchemy.String(length=16), nullable=False)
    amount: SQLAlchemyMapped[decimal.Decimal] = sqlalchemy_mapped_column(
        sqlalchemy.Numeric(precision=12, scale=2), nullable=False
    )
    refunded_amount: SQLAlchemyMapped[decimal.Decimal] = sqlalchemy_mapped_column(
        sqlalchemy.Numeric(precision=12, scale=2), nullable=False, server_default=sqlalchemy.text("0")
    )
    description: SQLAlchemyMapped[str | None] = sqlalchemy_mapped_column(sqlalchemy.String(length=500), nullable=True)
    status: SQLAlchemyMapped[str] = sqlalchemy_mapped_column(sqlalchemy.String(length=24), nullable=False, index=True)
    # Machine-readable failure slug from ApiPay. Branch on this, never on error_message.
    error_code: SQLAlchemyMapped[str | None] = sqlalchemy_mapped_column(sqlalchemy.String(length=64), nullable=True)
    error_message: SQLAlchemyMapped[str | None] = sqlalchemy_mapped_column(sqlalchemy.Text, nullable=True)
    paid_at: SQLAlchemyMapped[datetime.datetime | None] = sqlalchemy_mapped_column(
        sqlalchemy.DateTime(timezone=True), nullable=True
    )
    # Bookkeeping for the "tell the bot about this payment" side effect, so a failed
    # notification is visible and can be replayed instead of silently lost.
    bot_notified_at: SQLAlchemyMapped[datetime.datetime | None] = sqlalchemy_mapped_column(
        sqlalchemy.DateTime(timezone=True), nullable=True
    )
    bot_notify_error: SQLAlchemyMapped[str | None] = sqlalchemy_mapped_column(sqlalchemy.Text, nullable=True)
    last_event_at: SQLAlchemyMapped[datetime.datetime | None] = sqlalchemy_mapped_column(
        sqlalchemy.DateTime(timezone=True), nullable=True
    )
    last_event: SQLAlchemyMapped[dict[str, typing.Any] | None] = sqlalchemy_mapped_column(
        sqlalchemy.JSON, nullable=True
    )
    created_at: SQLAlchemyMapped[datetime.datetime] = sqlalchemy_mapped_column(
        sqlalchemy.DateTime(timezone=True), nullable=False, server_default=sqlalchemy_functions.now()
    )
    updated_at: SQLAlchemyMapped[datetime.datetime | None] = sqlalchemy_mapped_column(
        sqlalchemy.DateTime(timezone=True),
        nullable=True,
        server_onupdate=sqlalchemy.schema.FetchedValue(for_update=True),
    )

    account: SQLAlchemyMapped["Account"] = relationship("Account")  # type: ignore[name-defined]

    __mapper_args__ = {"eager_defaults": True}
