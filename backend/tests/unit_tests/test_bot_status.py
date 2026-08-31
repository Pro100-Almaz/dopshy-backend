import typing

import httpx
import pytest

from src.api.routes.bot_status import list_bot_contacts
from src.config.manager import settings
from src.services.bot_status import BotStatusService


@pytest.mark.asyncio
async def test_bot_status_service_lists_contacts_without_pagination_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["method"] = request.method
        captured_request["url"] = str(request.url)
        captured_request["api_key"] = request.headers.get("X-API-Key")
        return httpx.Response(200, json=[])

    async_client = httpx.AsyncClient
    monkeypatch.delenv("MANAGER_API_KEY", raising=False)
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "secret")
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **_: async_client(transport=httpx.MockTransport(handler)),
    )

    payload = await BotStatusService().list_contacts()

    assert payload == []
    assert captured_request == {
        "method": "GET",
        "url": "https://bot.example/api/manager/contacts",
        "api_key": "secret",
    }


@pytest.mark.asyncio
async def test_bot_status_service_forwards_contacts_pagination_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_request = {}
    paginated_payload = {
        "ok": True,
        "data": [{"phone": "77000000003"}],
        "page": 2,
        "page_size": 20,
        "total": 54,
        "total_pages": 3,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        return httpx.Response(200, json=paginated_payload)

    async_client = httpx.AsyncClient
    monkeypatch.delenv("MANAGER_API_KEY", raising=False)
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "secret")
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **_: async_client(transport=httpx.MockTransport(handler)),
    )

    payload = await BotStatusService().list_contacts(page="2", page_size="20")

    assert payload == paginated_payload
    assert captured_request == {
        "url": "https://bot.example/api/manager/contacts?page=2&page_size=20",
    }


@pytest.mark.asyncio
async def test_bot_status_service_forwards_raw_contacts_pagination_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        return httpx.Response(200, json={"ok": True, "data": []})

    async_client = httpx.AsyncClient
    monkeypatch.delenv("MANAGER_API_KEY", raising=False)
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "secret")
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **_: async_client(transport=httpx.MockTransport(handler)),
    )

    await BotStatusService().list_contacts(page="not-a-number", page_size="500")

    assert captured_request == {
        "url": "https://bot.example/api/manager/contacts?page=not-a-number&page_size=500",
    }


class FakeBotStatusService(BotStatusService):
    async def list_contacts(
        self,
        *,
        page: str | None = None,
        page_size: str | None = None,
    ) -> typing.Any:
        return {"page": page, "page_size": page_size}


@pytest.mark.asyncio
async def test_bot_status_contacts_route_passes_pagination_params_to_service() -> None:
    payload = await list_bot_contacts(
        page="2",
        page_size="20",
        bot_status_service=FakeBotStatusService(),
    )

    assert payload == {"page": "2", "page_size": "20"}
