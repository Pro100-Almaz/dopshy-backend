import typing

import httpx
import pytest

from src.api.routes.bot_status import list_bot_contacts
from src.config.manager import settings
from src.models.schemas.bot_status import BotEnabledStatusIn
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
        "url": "https://bot.example/api/manager/contacts?bot_type=arena",
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
        "url": "https://bot.example/api/manager/contacts?page=2&page_size=20&bot_type=arena",
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
        "url": "https://bot.example/api/manager/contacts?page=not-a-number&page_size=500&bot_type=arena",
    }


@pytest.mark.asyncio
async def test_bot_status_service_forwards_contacts_bot_type(
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

    await BotStatusService().list_contacts(bot_type="football_academy")

    assert captured_request == {
        "url": "https://bot.example/api/manager/contacts?bot_type=football_academy",
    }


@pytest.mark.asyncio
async def test_bot_status_service_forwards_enabled_status_bot_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        return httpx.Response(200, json={"is_enabled": False})

    async_client = httpx.AsyncClient
    monkeypatch.delenv("MANAGER_API_KEY", raising=False)
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "secret")
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **_: async_client(transport=httpx.MockTransport(handler)),
    )

    payload = await BotStatusService().get_bot_enabled_status(bot_type="boxing_academy")

    assert payload.is_enabled is False
    assert captured_request == {
        "url": "https://bot.example/api/manager/is_messaging_enabled?bot_type=boxing_academy",
    }


@pytest.mark.asyncio
async def test_bot_status_service_forwards_enabled_status_change_bot_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        captured_request["body"] = request.content
        return httpx.Response(200, json={"is_enabled": True})

    async_client = httpx.AsyncClient
    monkeypatch.delenv("MANAGER_API_KEY", raising=False)
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "secret")
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **_: async_client(transport=httpx.MockTransport(handler)),
    )

    payload = await BotStatusService().set_bot_enabled_status(
        enabled=True,
        bot_type="football_academy",
    )

    assert payload.is_enabled is True
    assert captured_request["url"] == "https://bot.example/api/manager/change_messaging_enabled"
    assert captured_request["body"] == b'{"enabled":true,"bot_type":"football_academy"}'


class FakeBotStatusService(BotStatusService):
    async def list_contacts(
        self,
        *,
        page: str | None = None,
        page_size: str | None = None,
        bot_type: str = "arena",
    ) -> typing.Any:
        return {"page": page, "page_size": page_size, "bot_type": bot_type}


@pytest.mark.asyncio
async def test_bot_status_contacts_route_passes_pagination_params_to_service() -> None:
    payload = await list_bot_contacts(
        page="2",
        page_size="20",
        bot_type="boxing_academy",
        bot_status_service=FakeBotStatusService(),
    )

    assert payload == {"page": "2", "page_size": "20", "bot_type": "boxing_academy"}


def test_bot_enabled_status_payload_defaults_to_arena() -> None:
    payload = BotEnabledStatusIn(enabled=True)

    assert payload.bot_type == "arena"
