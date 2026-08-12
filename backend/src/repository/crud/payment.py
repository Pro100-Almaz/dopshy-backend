import datetime
import decimal
import typing

import sqlalchemy

from src.models.db.payment import Payment
from src.models.enums.payment import PaymentStatus, SETTLED_PAYMENT_STATUSES
from src.repository.crud.base import BaseCRUDRepository
from src.utilities.exceptions.database import EntityDoesNotExist


class PaymentCRUDRepository(BaseCRUDRepository):
    async def create_payment(
        self,
        *,
        external_order_id: str,
        phone: str,
        amount: decimal.Decimal | int,
        booking_id: int | None = None,
        account_id: int | None = None,
        description: str | None = None,
    ) -> Payment:
        """Insert the row *before* calling ApiPay, so a failed call still leaves a trace."""
        new_payment = Payment(
            external_order_id=external_order_id,
            phone=phone,
            amount=amount,
            booking_id=booking_id,
            account_id=account_id,
            description=description,
            status=PaymentStatus.CREATED.value,
        )
        self.async_session.add(new_payment)
        await self.async_session.commit()
        await self.async_session.refresh(new_payment)
        return new_payment

    async def read_payment_by_id(self, id: int) -> Payment:
        stmt = sqlalchemy.select(Payment).where(Payment.id == id)
        result = await self.async_session.execute(stmt)
        payment = result.scalar_one_or_none()
        if not payment:
            raise EntityDoesNotExist(f"Payment with id `{id}` does not exist!")
        return payment

    async def read_payment_by_invoice_id(self, apipay_invoice_id: int) -> Payment:
        stmt = sqlalchemy.select(Payment).where(Payment.apipay_invoice_id == apipay_invoice_id)
        result = await self.async_session.execute(stmt)
        payment = result.scalar_one_or_none()
        if not payment:
            raise EntityDoesNotExist(f"Payment for ApiPay invoice `{apipay_invoice_id}` does not exist!")
        return payment

    async def read_payment_by_external_order_id(self, external_order_id: str) -> Payment:
        stmt = sqlalchemy.select(Payment).where(Payment.external_order_id == external_order_id)
        result = await self.async_session.execute(stmt)
        payment = result.scalar_one_or_none()
        if not payment:
            raise EntityDoesNotExist(f"Payment with external_order_id `{external_order_id}` does not exist!")
        return payment

    async def read_payments(
        self,
        *,
        booking_id: int | None = None,
        account_id: int | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> typing.Sequence[Payment]:
        stmt = sqlalchemy.select(Payment).order_by(Payment.created_at.desc()).limit(limit).offset(offset)
        if booking_id is not None:
            stmt = stmt.where(Payment.booking_id == booking_id)
        if account_id is not None:
            stmt = stmt.where(Payment.account_id == account_id)
        if status is not None:
            stmt = stmt.where(Payment.status == status)
        result = await self.async_session.execute(stmt)
        return result.scalars().all()

    async def attach_invoice(self, payment_id: int, apipay_invoice_id: int, status: str) -> Payment:
        payment = await self.read_payment_by_id(id=payment_id)
        payment.apipay_invoice_id = apipay_invoice_id
        payment.status = status
        payment.updated_at = datetime.datetime.now(tz=datetime.timezone.utc)
        await self.async_session.commit()
        await self.async_session.refresh(payment)
        return payment

    async def mark_failed(self, payment_id: int, error_code: str | None, error_message: str) -> Payment:
        payment = await self.read_payment_by_id(id=payment_id)
        payment.status = PaymentStatus.ERROR.value
        payment.error_code = error_code
        payment.error_message = error_message
        payment.updated_at = datetime.datetime.now(tz=datetime.timezone.utc)
        await self.async_session.commit()
        await self.async_session.refresh(payment)
        return payment

    async def apply_status(
        self,
        *,
        apipay_invoice_id: int,
        status: str,
        paid_at: datetime.datetime | None = None,
        refunded_amount: decimal.Decimal | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        event: dict[str, typing.Any] | None = None,
    ) -> tuple[Payment, bool]:
        """Apply an ApiPay-reported status, returning (payment, became_settled).

        The row is locked FOR UPDATE because ApiPay retries deliveries up to eleven
        times and two of them can land concurrently. `became_settled` is True only on
        the first transition into a money-received status, which is what makes the
        downstream side effect (telling the bot) fire exactly once.
        """
        stmt = sqlalchemy.select(Payment).where(Payment.apipay_invoice_id == apipay_invoice_id).with_for_update()
        result = await self.async_session.execute(stmt)
        payment = result.scalar_one_or_none()
        if not payment:
            raise EntityDoesNotExist(f"Payment for ApiPay invoice `{apipay_invoice_id}` does not exist!")

        was_settled = payment.status in SETTLED_PAYMENT_STATUSES

        payment.status = status
        payment.last_event_at = datetime.datetime.now(tz=datetime.timezone.utc)
        if event is not None:
            payment.last_event = event
        if paid_at is not None:
            payment.paid_at = paid_at
        if refunded_amount is not None:
            payment.refunded_amount = refunded_amount
        if error_code is not None:
            payment.error_code = error_code
        if error_message is not None:
            payment.error_message = error_message
        payment.updated_at = datetime.datetime.now(tz=datetime.timezone.utc)

        await self.async_session.commit()
        await self.async_session.refresh(payment)

        became_settled = (not was_settled) and status in SETTLED_PAYMENT_STATUSES
        return payment, became_settled

    async def mark_bot_notified(self, payment_id: int, error: str | None = None) -> Payment:
        payment = await self.read_payment_by_id(id=payment_id)
        payment.bot_notify_error = error
        if error is None:
            payment.bot_notified_at = datetime.datetime.now(tz=datetime.timezone.utc)
        await self.async_session.commit()
        await self.async_session.refresh(payment)
        return payment

    async def sum_settled_for_booking(self, booking_id: int) -> decimal.Decimal:
        """Net amount actually received through ApiPay for a booking (paid minus refunded).

        Reported to the bot as an absolute figure rather than a delta, so replaying a
        webhook can never double-count.
        """
        stmt = sqlalchemy.select(
            sqlalchemy.func.coalesce(sqlalchemy.func.sum(Payment.amount - Payment.refunded_amount), 0)
        ).where(
            Payment.booking_id == booking_id,
            Payment.status.in_(tuple(SETTLED_PAYMENT_STATUSES)),
        )
        result = await self.async_session.execute(stmt)
        total = result.scalar_one()
        return decimal.Decimal(total or 0)
