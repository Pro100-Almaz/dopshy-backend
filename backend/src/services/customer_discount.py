import typing

import fastapi
import httpx

from src.config.manager import settings
from src.utilities.bot_auth import get_bot_service_headers


class CustomerDiscountService:
    """Authenticated, transparent proxy for bot-owned customers and discounts."""

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, typing.Any] | None = None,
        json: dict[str, typing.Any] | None = None,
    ) -> tuple[int, typing.Any]:
        if not settings.BOT_URL:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="BOT_URL is not configured.",
            )

        headers = get_bot_service_headers(json=True)
        clean_params = {key: value for key, value in (params or {}).items() if value is not None}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.request(
                    method,
                    settings.BOT_URL.rstrip("/") + path,
                    headers=headers,
                    params=clean_params,
                    json=json,
                )
        except httpx.HTTPError as exc:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="Failed to reach the bot service.",
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="Bot service returned a non-JSON response.",
            ) from exc

        # Preserve the bot's status and machine-readable error envelope. In
        # particular, callers need discount error codes even when several of
        # them share HTTP 409.
        return response.status_code, self._normalize_entity_ids(payload)

    def _normalize_entity_ids(self, value: typing.Any) -> typing.Any:
        if isinstance(value, list):
            return [self._normalize_entity_ids(item) for item in value]
        if isinstance(value, dict):
            return {
                key: (
                    None
                    if key in {"booking_id", "customer_id", "discount_id"} and item == ""
                    else self._normalize_entity_ids(item)
                )
                for key, item in value.items()
            }
        return value
