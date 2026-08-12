import httpx
import pytest

from src.config.manager import settings
from src.services.academy import AcademyService


@pytest.mark.asyncio
async def test_academy_service_lists_groups(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        captured_request["api_key"] = request.headers.get("X-API-KEY")
        return httpx.Response(200, json={"ok": True, "data": {"groups": {"boxing": []}}})

    async_client = httpx.AsyncClient
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "secret")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: async_client(transport=httpx.MockTransport(handler)))

    status_code, payload = await AcademyService().list_groups()

    assert status_code == 200
    assert payload == {"ok": True, "data": {"groups": {"boxing": []}}}
    assert captured_request == {
        "url": "https://bot.example/api/manager/academy_groups",
        "api_key": "secret",
    }


@pytest.mark.asyncio
async def test_academy_service_updates_trial_attended(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["method"] = request.method
        captured_request["url"] = str(request.url)
        captured_request["body"] = request.read().decode()
        return httpx.Response(200, json={"ok": True, "data": {"trial_id": 44, "attended": True}})

    async_client = httpx.AsyncClient
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "secret")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: async_client(transport=httpx.MockTransport(handler)))

    status_code, payload = await AcademyService().set_trial_attended(trial_id=44, attended=True)

    assert status_code == 200
    assert payload == {"ok": True, "data": {"trial_id": 44, "attended": True}}
    assert captured_request == {
        "method": "PATCH",
        "url": "https://bot.example/api/manager/academy_trials/44/attended",
        "body": '{"attended":true}',
    }


@pytest.mark.asyncio
async def test_academy_service_preserves_group_trials_404(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"ok": False, "code": "NOT_FOUND", "message": "Group not found."},
        )

    async_client = httpx.AsyncClient
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "secret")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: async_client(transport=httpx.MockTransport(handler)))

    status_code, payload = await AcademyService().get_group_trials(group_id=123)

    assert status_code == 404
    assert payload == {"ok": False, "code": "NOT_FOUND", "message": "Group not found."}


@pytest.mark.asyncio
async def test_academy_service_requires_bot_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BOT_URL", "")

    with pytest.raises(Exception) as exc_info:
        await AcademyService().list_groups()

    assert getattr(exc_info.value, "status_code") == 502


@pytest.mark.asyncio
async def test_academy_service_rejects_non_json_bot_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html></html>")

    async_client = httpx.AsyncClient
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "secret")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: async_client(transport=httpx.MockTransport(handler)))

    with pytest.raises(Exception) as exc_info:
        await AcademyService().list_groups()

    assert getattr(exc_info.value, "status_code") == 502
