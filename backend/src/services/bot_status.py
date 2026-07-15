import os
import typing
import urllib.parse

import fastapi
import httpx

from src.config.manager import settings
from src.models.schemas.bot_status import BotStatusBatchIn


class BotStatusService:
    """Proxy to the bot service's manager API for the WhatsApp pause/resume feature.

    The frontend authenticates against this project as usual; the bot API key is
    injected server-side and never exposed to the frontend.
    """

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: typing.Any | None = None,
    ) -> httpx.Response:
        base_url = settings.BOT_URL
        if not base_url:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="BOT_URL is not configured.",
            )
        url = base_url.rstrip("/") + path
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-KEY": os.getenv("MANAGER_API_KEY") or "",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.request(method, url, headers=headers, json=json)
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

    async def get_status(self, phone: str) -> typing.Any:
        quoted = urllib.parse.quote(phone, safe="")
        response = await self._request("GET", f"/api/manager/bot_status/{quoted}")
        return self._json(response)

    async def pause(self, phone: str) -> dict[str, typing.Any]:
        quoted = urllib.parse.quote(phone, safe="")
        await self._request("POST", f"/api/manager/bot_status/{quoted}/pause")
        return {"phone": phone, "paused": True}

    async def resume(self, phone: str) -> dict[str, typing.Any]:
        quoted = urllib.parse.quote(phone, safe="")
        await self._request("POST", f"/api/manager/bot_status/{quoted}/resume")
        return {"phone": phone, "paused": False}

    async def batch_status(self, payload: BotStatusBatchIn) -> typing.Any:
        body = payload.model_dump(mode="json")
        response = await self._request("POST", "/api/manager/bot_status/batch", json=body)
        return self._json(response)
