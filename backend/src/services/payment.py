import datetime
import decimal
import json
import typing
import uuid

import fastapi
import httpx
import loguru

from src.config.manager import settings
from src.models.db.account import Account
from src.models.db.payment import Payment
from src.models.enums.payment import PaymentStatus, TERMINAL_PAYMENT_STATUSES
from src.models.schemas.payment import PaymentInCreate
from src.repository.crud.payment import PaymentCRUDRepository
from src.securities.verifications.apipay_signature import verify_webhook_signature
from src.services.apipay import ApiPayClient, ApiPayError
from src.utilities.exceptions.database import EntityDoesNotExist

#: Statuses ApiPay may report on an invoice. Anything outside this set is stored
#: verbatim but logged, so a new ApiPay status never silently corrupts our ledger.
_KNOWN_STATUSES: frozenset[str] = frozenset(s.value for s in PaymentStatus)


class WebhookSignatureError(Exception):
    """The `X-Webhook-Signature` header is missing, malformed or does not match."""


class PaymentService:
    """Kaspi Pay invoicing through ApiPay.

    Invoice creation is synchronous, but *payment* is not: ApiPay answers `processing`
    and later calls our webhook when the customer actually pays in the Kaspi app.
    """

    def __init__(
        self,
        payment_repo: PaymentCRUDRepository,
        apipay_client: ApiPayClient | None = None,
    ) -> None:
        self.payment_repo = payment_repo
        self.apipay = apipay_client or ApiPayClient()

    # ------------------------------------------------------------------ invoices

    async def create_payment(self, payload: PaymentInCreate, account: Account | None = None) -> Payment:
        external_order_id = self._build_external_order_id(booking_id=payload.booking_id)

        payment = await self.payment_repo.create_payment(
            external_order_id=external_order_id,
            phone=payload.phone_number,
            amount=payload.amount,
            booking_id=payload.booking_id,
            account_id=account.id if account else None,
            description=payload.description,
        )

        try:
            invoice = await self.apipay.create_invoice(
                phone_number=payload.phone_number,
                amount=payload.amount,
                description=payload.description,
                external_order_id=external_order_id,
                idempotency_key=external_order_id,
            )
        except ApiPayError as exc:
            await self.payment_repo.mark_failed(
                payment_id=payment.id, error_code=exc.error_code, error_message=str(exc)
            )
            raise self._http_error_from_apipay(exc) from exc

        invoice_id = invoice.get("id")
        if invoice_id is None:
            await self.payment_repo.mark_failed(
                payment_id=payment.id, error_code="missing_invoice_id", error_message=json.dumps(invoice)[:1000]
            )
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="ApiPay не вернул идентификатор счёта.",
            )

        status = self._coerce_status(invoice.get("status"), default=PaymentStatus.PROCESSING.value)
        payment = await self.payment_repo.attach_invoice(
            payment_id=payment.id, apipay_invoice_id=int(invoice_id), status=status
        )
        loguru.logger.info(
            f"ApiPay invoice {invoice_id} created for payment id={payment.id} "
            f"booking_id={payment.booking_id} amount={payment.amount}"
        )
        return payment

    async def get_payment(self, payment_id: int, refresh: bool = False) -> Payment:
        payment = await self.payment_repo.read_payment_by_id(id=payment_id)
        if not refresh or payment.apipay_invoice_id is None:
            return payment
        if payment.status in TERMINAL_PAYMENT_STATUSES:
            return payment
        return await self.refresh_payment(payment=payment)

    async def refresh_payment(self, payment: Payment) -> Payment:
        """Poll ApiPay for the current invoice state.

        Used as a safety net for the webhook: if every delivery attempt failed, or a
        browser is waiting on a "paid yet?" answer, this reconciles our row.
        """
        if payment.apipay_invoice_id is None:
            return payment
        try:
            invoice = await self.apipay.get_invoice(invoice_id=payment.apipay_invoice_id)
        except ApiPayError as exc:
            loguru.logger.warning(f"Could not refresh payment id={payment.id}: {exc}")
            return payment

        updated, became_settled = await self._apply_invoice_snapshot(invoice=invoice, event=None)
        if became_settled:
            await self.notify_bot(payment_id=updated.id)
            updated = await self.payment_repo.read_payment_by_id(id=updated.id)
        return updated

    async def list_payments(
        self,
        booking_id: int | None = None,
        account_id: int | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> typing.Sequence[Payment]:
        return await self.payment_repo.read_payments(
            booking_id=booking_id, account_id=account_id, status=status, limit=limit, offset=offset
        )

    async def refund_payment(self, payment_id: int, amount: int | None = None) -> Payment:
        payment = await self.payment_repo.read_payment_by_id(id=payment_id)
        if payment.apipay_invoice_id is None:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail="Счёт не был создан в ApiPay — возвращать нечего.",
            )
        try:
            await self.apipay.refund_invoice(invoice_id=payment.apipay_invoice_id, amount=amount)
        except ApiPayError as exc:
            raise self._http_error_from_apipay(exc) from exc
        # ApiPay confirms the resulting status through `invoice.refunded`; poll once so
        # the caller sees the new state immediately instead of waiting for the webhook.
        return await self.refresh_payment(payment=payment)

    async def cancel_payment(self, payment_id: int) -> Payment:
        payment = await self.payment_repo.read_payment_by_id(id=payment_id)
        if payment.apipay_invoice_id is None:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail="Счёт не был создан в ApiPay — отменять нечего.",
            )
        try:
            await self.apipay.cancel_invoice(invoice_id=payment.apipay_invoice_id)
        except ApiPayError as exc:
            raise self._http_error_from_apipay(exc) from exc
        return await self.refresh_payment(payment=payment)

    async def simulate_status(self, payment_id: int, status: str, error_message: str | None = None) -> typing.Any:
        payment = await self.payment_repo.read_payment_by_id(id=payment_id)
        if payment.apipay_invoice_id is None:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail="Счёт не был создан в ApiPay.",
            )
        try:
            return await self.apipay.simulate_status(
                invoice_id=payment.apipay_invoice_id, status=status, error_message=error_message
            )
        except ApiPayError as exc:
            raise self._http_error_from_apipay(exc) from exc

    async def get_webhook_logs(self, payment_id: int | None = None, event: str | None = None) -> typing.Any:
        invoice_id: int | None = None
        if payment_id is not None:
            payment = await self.payment_repo.read_payment_by_id(id=payment_id)
            invoice_id = payment.apipay_invoice_id
        try:
            return await self.apipay.get_webhook_logs(invoice_id=invoice_id, event=event)
        except ApiPayError as exc:
            raise self._http_error_from_apipay(exc) from exc

    # ------------------------------------------------------------------ webhooks

    async def handle_webhook(self, raw_body: bytes, signature: str | None) -> tuple[str | None, Payment | None, bool]:
        """Verify and apply one ApiPay webhook.

        Returns (event name, affected payment, whether the bot must be told). The
        caller answers 2xx straight away and pushes the bot call to the background —
        ApiPay retries anything slower than five seconds.
        """
        if not verify_webhook_signature(raw_body=raw_body, signature=signature, secret=settings.APIPAY_WEBHOOK_SECRET):
            raise WebhookSignatureError("Подпись вебхука ApiPay не совпала.")

        try:
            body = json.loads(raw_body)
        except ValueError as exc:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail="Тело вебхука не является корректным JSON.",
            ) from exc

        if not isinstance(body, dict):
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail="Тело вебхука должно быть JSON-объектом.",
            )

        event = body.get("event")
        invoice = body.get("invoice")

        # A connectivity probe fired by the dashboard's «Проверить уведомления» button.
        if event == "webhook.test":
            loguru.logger.info("ApiPay webhook test event received and verified")
            return event, None, False

        if not isinstance(invoice, dict) or invoice.get("id") is None:
            # Subscription/catalog events carry no invoice. Acknowledge so ApiPay stops
            # retrying — replying non-2xx would queue eleven pointless redeliveries.
            loguru.logger.info(f"ApiPay webhook '{event}' carries no invoice — acknowledged without action")
            return event, None, False

        try:
            payment, became_settled = await self._apply_invoice_snapshot(invoice=invoice, event=body)
        except EntityDoesNotExist:
            # An invoice created outside this backend (dashboard, another service).
            # Not our business, but must still be acknowledged.
            loguru.logger.warning(f"ApiPay webhook for unknown invoice id={invoice.get('id')} — acknowledged")
            return event, None, False

        loguru.logger.info(
            f"ApiPay webhook '{event}' applied to payment id={payment.id} "
            f"status={payment.status} settled_now={became_settled}"
        )
        return event, payment, became_settled and payment.booking_id is not None

    async def _apply_invoice_snapshot(
        self, invoice: dict[str, typing.Any], event: dict[str, typing.Any] | None
    ) -> tuple[Payment, bool]:
        status = self._coerce_status(invoice.get("status"), default=PaymentStatus.PROCESSING.value)
        return await self.payment_repo.apply_status(
            apipay_invoice_id=int(invoice["id"]),
            status=status,
            paid_at=self._parse_datetime(invoice.get("paid_at")),
            refunded_amount=self._parse_decimal(invoice.get("refunded_amount")),
            error_code=invoice.get("error_code"),
            error_message=invoice.get("error_message"),
            event=event,
        )

    # ------------------------------------------------------------- bot side effect

    async def notify_bot(self, payment_id: int) -> Payment:
        """Record the received money against the booking in the bot service.

        The bot owns the booking rows the managers actually look at, so a Kaspi payment
        that is not mirrored there is invisible to staff. `paid_kaspi_qr` is written as
        an absolute net total (paid minus refunded) rather than a delta, which keeps
        repeated calls safe.
        """
        payment = await self.payment_repo.read_payment_by_id(id=payment_id)
        if payment.booking_id is None:
            return payment

        if not settings.BOT_URL:
            await self.payment_repo.mark_bot_notified(payment_id=payment.id, error="BOT_URL is not configured.")
            loguru.logger.error(f"Payment id={payment.id} is paid but BOT_URL is not configured")
            return payment

        total = await self.payment_repo.sum_settled_for_booking(booking_id=payment.booking_id)
        url = settings.BOT_URL.rstrip("/") + f"/api/manager/bookings/{payment.booking_id}"
        body = {
            "paid_kaspi_qr": float(total),
            "source": f"apipay:{payment.apipay_invoice_id}",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.patch(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "X-API-KEY": settings.MANAGER_API_KEY,
                    },
                    json=body,
                )
        except httpx.HTTPError as exc:
            error = f"Failed to reach the bot service: {exc}"
            loguru.logger.error(f"Payment id={payment.id}: {error}")
            return await self.payment_repo.mark_bot_notified(payment_id=payment.id, error=error)

        if response.status_code >= 400:
            error = f"Bot service returned {response.status_code}: {response.text[:200]}"
            loguru.logger.error(f"Payment id={payment.id}: {error}")
            return await self.payment_repo.mark_bot_notified(payment_id=payment.id, error=error)

        loguru.logger.info(
            f"Payment id={payment.id} mirrored to bot booking {payment.booking_id} (paid_kaspi_qr={total})"
        )
        return await self.payment_repo.mark_bot_notified(payment_id=payment.id, error=None)

    # ----------------------------------------------------------------- internals

    @staticmethod
    def _build_external_order_id(booking_id: int | None) -> str:
        """Readable on the ApiPay side, unique on ours — also the idempotency key."""
        suffix = uuid.uuid4().hex[:12]
        return f"booking-{booking_id}-{suffix}" if booking_id is not None else f"payment-{suffix}"

    @staticmethod
    def _coerce_status(value: typing.Any, default: str) -> str:
        if not isinstance(value, str) or not value:
            return default
        if value not in _KNOWN_STATUSES:
            loguru.logger.warning(f"ApiPay reported an unmapped invoice status '{value}' — stored as-is")
        return value

    @staticmethod
    def _parse_datetime(value: typing.Any) -> datetime.datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            loguru.logger.warning(f"Could not parse ApiPay timestamp {value!r}")
            return None

    @staticmethod
    def _parse_decimal(value: typing.Any) -> decimal.Decimal | None:
        if value is None or value == "":
            return None
        try:
            return decimal.Decimal(str(value))
        except (decimal.InvalidOperation, ValueError):
            loguru.logger.warning(f"Could not parse ApiPay amount {value!r}")
            return None

    @staticmethod
    def _http_error_from_apipay(exc: ApiPayError) -> fastapi.HTTPException:
        """Translate an ApiPay failure into an answer the frontend can act on.

        Client-fixable problems (bad phone, daily limit) keep their original status;
        merchant-side misconfiguration is reported as 502 with a plain-Russian hint,
        because the caller cannot do anything about it.
        """
        merchant_side = {
            "organization_required": "Организация не подключена в ApiPay.",
            "kaspi_session_not_configured": (
                "Не подключён кассир Kaspi — счета в рабочем режиме создаваться не будут. "
                "Подключите кассу: кабинет ApiPay → Настройки → «Авторизация Kaspi»."
            ),
            "kaspi_session_invalid": (
                "Сессия кассира Kaspi истекла. Нужно переподключить кассу по SMS: "
                "кабинет ApiPay → Настройки → «Авторизация Kaspi»."
            ),
            "not_configured": "Приём платежей не настроен: не задан APIPAY_API_KEY.",
            "network_unavailable": "Сервис ApiPay временно недоступен, попробуйте позже.",
        }
        if exc.error_code in merchant_side:
            return fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY, detail=merchant_side[exc.error_code]
            )

        if exc.status_code == fastapi.status.HTTP_401_UNAUTHORIZED:
            return fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="ApiPay отклонил ключ доступа — проверьте APIPAY_API_KEY.",
            )

        detail: dict[str, typing.Any] = {"message": str(exc.message), "error_code": exc.error_code}
        if exc.meta:
            detail["meta"] = exc.meta
        return fastapi.HTTPException(status_code=exc.status_code or fastapi.status.HTTP_502_BAD_GATEWAY, detail=detail)
