import re
import typing

import httpx
import loguru

from src.config.manager import settings

#: Kaspi accepts whole tenge only for phone invoices; a fractional amount is a 422.
MIN_INVOICE_AMOUNT: int = 1
MAX_INVOICE_AMOUNT: int = 99_999_999


class ApiPayError(Exception):
    """A non-2xx answer (or an unreachable host) from the ApiPay API.

    `error_code` is ApiPay's stable machine-readable slug — branch on it. `message`
    is human-facing text that may change wording at any time, so never parse it.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        meta: dict[str, typing.Any] | None = None,
        payload: typing.Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.meta = meta or {}
        self.payload = payload

    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.status_code} {self.error_code}] {self.message}"
        return f"[{self.status_code}] {self.message}"


def normalize_kz_phone(raw: str) -> str:
    """Coerce a Kazakh mobile number into ApiPay's required `8XXXXXXXXXX` form.

    Accepts the shapes people actually type — `+7 700 123-45-67`, `77001234567`,
    `7001234567` — and rejects anything that is not 11 digits starting with 8.
    """
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10 and digits.startswith("7"):
        digits = f"8{digits}"
    elif len(digits) == 11 and digits.startswith("7"):
        digits = f"8{digits[1:]}"

    if len(digits) != 11 or not digits.startswith("8"):
        raise ValueError(
            "Номер телефона должен быть казахстанским мобильным в формате 8XXXXXXXXXX " f"(11 цифр). Получено: {raw!r}"
        )
    return digits


class ApiPayClient:
    """Thin async wrapper over the ApiPay REST API.

    The `X-API-Key` header is a server-side secret: it authorises invoicing against
    the owner's Kaspi Pay account, so it must never be forwarded to a browser.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.APIPAY_API_KEY
        self.base_url = (base_url if base_url is not None else settings.APIPAY_BASE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.APIPAY_TIMEOUT

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @staticmethod
    def _extract_error(payload: typing.Any, status_code: int) -> tuple[str | None, str, dict[str, typing.Any]]:
        """Pull (error_code, message, meta) out of an ApiPay error body."""
        if not isinstance(payload, dict):
            return None, f"ApiPay вернул HTTP {status_code}", {}

        error_code = payload.get("error_code") or payload.get("error") or payload.get("code")
        message = (
            payload.get("error_message")
            or payload.get("message")
            or payload.get("detail")
            or f"ApiPay вернул HTTP {status_code}"
        )
        # 422 bodies carry per-field validation errors; surface the first one so the
        # caller sees "phone_number: ..." rather than a bare "Unprocessable Entity".
        errors = payload.get("errors")
        if isinstance(errors, dict) and errors:
            field, detail = next(iter(errors.items()))
            detail_text = detail[0] if isinstance(detail, list) and detail else detail
            message = f"{field}: {detail_text}"

        raw_meta = payload.get("meta")
        meta: dict[str, typing.Any] = raw_meta if isinstance(raw_meta, dict) else {}
        return (str(error_code) if error_code else None), str(message), meta

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: typing.Any | None = None,
        params: typing.Any | None = None,
    ) -> typing.Any:
        if not self.is_configured:
            raise ApiPayError("APIPAY_API_KEY не задан — приём платежей не настроен.", error_code="not_configured")

        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(method, url, headers=self._headers(), json=json, params=params)
            except httpx.HTTPError as exc:
                raise ApiPayError("Не удалось связаться с ApiPay.", error_code="network_unavailable") from exc

        try:
            payload: typing.Any = response.json()
        except ValueError:
            payload = None

        if response.status_code >= 400:
            error_code, message, meta = self._extract_error(payload, response.status_code)
            loguru.logger.warning(
                f"ApiPay {method} {path} failed: HTTP {response.status_code} error_code={error_code} {message}"
            )
            raise ApiPayError(
                message,
                status_code=response.status_code,
                error_code=error_code,
                meta=meta,
                payload=payload,
            )

        return payload

    async def create_invoice(
        self,
        *,
        phone_number: str,
        amount: int,
        description: str | None = None,
        external_order_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, typing.Any]:
        """POST /invoices — ask Kaspi to push a payment request to `phone_number`.

        Returns immediately with status `processing`; the invoice reaches `pending`
        (and later `paid`) asynchronously, which is what the webhook reports.
        """
        body: dict[str, typing.Any] = {"phone_number": phone_number, "amount": amount}
        if description:
            body["description"] = description[:500]
        if external_order_id:
            body["external_order_id"] = external_order_id
        if idempotency_key:
            # Protects against duplicate invoices if we retry a timed-out create.
            body["external_order_id_idempotency"] = idempotency_key

        payload = await self._request("POST", "/invoices", json=body)
        if not isinstance(payload, dict):
            raise ApiPayError("ApiPay вернул неожиданный ответ при создании счёта.", payload=payload)
        return payload

    async def get_invoice(self, invoice_id: int) -> dict[str, typing.Any]:
        payload = await self._request("GET", f"/invoices/{invoice_id}")
        if not isinstance(payload, dict):
            raise ApiPayError("ApiPay вернул неожиданный ответ при проверке счёта.", payload=payload)
        return payload

    async def check_statuses(self, invoice_ids: list[int]) -> typing.Any:
        return await self._request("POST", "/invoices/status/check", json={"invoice_ids": invoice_ids})

    async def refund_invoice(self, invoice_id: int, amount: int | None = None) -> typing.Any:
        body = {"amount": amount} if amount is not None else None
        return await self._request("POST", f"/invoices/{invoice_id}/refund", json=body)

    async def cancel_invoice(self, invoice_id: int) -> typing.Any:
        return await self._request("POST", f"/invoices/{invoice_id}/cancel")

    async def simulate_status(self, invoice_id: int, status: str, error_message: str | None = None) -> typing.Any:
        """Sandbox only — drive a test invoice to a terminal status without a human.

        A production invoice always answers `403 not_sandbox`.
        """
        body: dict[str, typing.Any] = {"status": status}
        if error_message:
            body["error_message"] = error_message
        return await self._request("POST", f"/invoices/{invoice_id}/simulate-status", json=body)

    async def get_webhook_logs(self, invoice_id: int | None = None, event: str | None = None) -> typing.Any:
        """Read-only delivery log — the programmatic version of the dashboard's
        «Лог уведомлений». Shows whether a webhook was sent and how we answered."""
        params: dict[str, typing.Any] = {}
        if invoice_id is not None:
            params["invoice_id"] = invoice_id
        if event is not None:
            params["event"] = event
        return await self._request("GET", "/webhook-logs", params=params or None)
