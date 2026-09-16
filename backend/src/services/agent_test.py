import os
import typing

import fastapi
import httpx

from src.config.manager import settings

# A console turn runs the whole agent pipeline: routing, extraction and the
# reply are separate live OpenAI calls, so it routinely takes far longer than
# the 10s the other bot proxies use.
_AGENT_TURN_TIMEOUT_SECONDS = 180.0
_DEFAULT_TIMEOUT_SECONDS = 15.0


class AgentTestService:
    """Proxy to the bot service's agent-test console API.

    The agent itself lives in the bot service; this only forwards, so that the
    frontend keeps a single origin and the admin JWT stays the access control.
    """

    async def _request(
        self,
        method: str,
        path: str,
        json: typing.Any | None = None,
        params: dict[str, typing.Any] | None = None,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> tuple[int, typing.Any]:
        base_url = settings.BOT_URL
        if not base_url:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="BOT_URL is not configured.",
            )

        url = base_url.rstrip("/") + path
        headers = {
            "Accept": "application/json",
            "X-API-Key": os.getenv("MANAGER_API_KEY") or settings.MANAGER_API_KEY or "",
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.request(method, url, headers=headers, json=json, params=params)
            except httpx.TimeoutException as exc:
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="The agent did not answer in time. Try again or check the bot service.",
                ) from exc
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

        if response.status_code in (
            fastapi.status.HTTP_401_UNAUTHORIZED,
            fastapi.status.HTTP_403_FORBIDDEN,
        ):
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="Bot service authentication failed. Check MANAGER_API_KEY between backend and bot.",
            )

        return response.status_code, payload

    async def list_bots(self) -> tuple[int, typing.Any]:
        return await self._request("GET", "/api/agent-test/bots")

    async def list_sessions(self) -> tuple[int, typing.Any]:
        return await self._request("GET", "/api/agent-test/sessions")

    async def create_session(self, payload: dict[str, typing.Any]) -> tuple[int, typing.Any]:
        return await self._request("POST", "/api/agent-test/sessions", json=payload)

    async def get_session(self, session_id: int) -> tuple[int, typing.Any]:
        return await self._request("GET", f"/api/agent-test/sessions/{session_id}")

    async def send_message(self, session_id: int, payload: dict[str, typing.Any]) -> tuple[int, typing.Any]:
        return await self._request(
            "POST",
            f"/api/agent-test/sessions/{session_id}/messages",
            json=payload,
            timeout=_AGENT_TURN_TIMEOUT_SECONDS,
        )

    async def reset_session(self, session_id: int) -> tuple[int, typing.Any]:
        return await self._request("POST", f"/api/agent-test/sessions/{session_id}/reset")

    async def delete_session(self, session_id: int) -> tuple[int, typing.Any]:
        return await self._request("DELETE", f"/api/agent-test/sessions/{session_id}")
