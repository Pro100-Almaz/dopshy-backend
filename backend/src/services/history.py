import os
import typing
import urllib.parse

import fastapi
import httpx

from src.config.manager import settings


class HistoryService:
    """Proxy to the bot service's manager history API.

    The frontend authenticates against this project as usual; the bot API key is
    injected server-side and never exposed to the frontend. Responses from the bot
    (``{"ok": ..., "data": [...], "page": ..., "total": ...}``) are passed through
    as-is so the frontend can rely on the bot's pagination envelope.
    """

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, typing.Any] | None = None,
    ) -> httpx.Response:
        base_url = settings.BOT_URL
        if not base_url:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="BOT_URL is not configured.",
            )
        url = base_url.rstrip("/") + path
        headers = {
            "Accept": "application/json",
            "X-API-KEY": os.getenv("MANAGER_API_KEY") or settings.MANAGER_API_KEY or "",
        }
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.request(method, url, headers=headers, params=clean_params)
            except httpx.HTTPError as exc:
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to reach the bot service.",
                ) from exc

        if response.status_code >= 400:
            detail = "Bot service authentication failed (check MANAGER_API_KEY)." \
                if response.status_code == 401 \
                else f"Bot service returned {response.status_code}: {response.text[:200]}"
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail=detail,
            )
        return response

    def _json(self, response: httpx.Response) -> typing.Any:
        try:
            return response.json()
        except ValueError as exc:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="Bot service returned a non-JSON response.",
            ) from exc

    async def list_history(
        self,
        *,
        source: str | None = None,
        channel: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> typing.Any:
        params = {"source": source, "channel": channel, "page": page, "page_size": page_size}
        response = await self._request("GET", "/api/manager/history", params=params)
        return self._json(response)

    async def list_history_by_range(
        self,
        *,
        start_date: str,
        end_date: str,
        page: int | None = None,
        page_size: int | None = None,
    ) -> typing.Any:
        start = urllib.parse.quote(start_date, safe="")
        end = urllib.parse.quote(end_date, safe="")
        params = {"page": page, "page_size": page_size}
        response = await self._request(
            "GET", f"/api/manager/history/range/{start}/{end}", params=params
        )
        return self._json(response)

    async def list_history_by_source(
        self,
        *,
        source: str,
        page: int | None = None,
        page_size: int | None = None,
    ) -> typing.Any:
        quoted = urllib.parse.quote(source, safe="")
        params = {"page": page, "page_size": page_size}
        response = await self._request(
            "GET", f"/api/manager/history/source/{quoted}", params=params
        )
        return self._json(response)

    async def list_booking_history(
        self,
        *,
        booking_id: int,
        page: int | None = None,
        page_size: int | None = None,
    ) -> typing.Any:
        params = {"page": page, "page_size": page_size}
        response = await self._request(
            "GET", f"/api/manager/bookings/{booking_id}/history", params=params
        )
        return self._json(response)
