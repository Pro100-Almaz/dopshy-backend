import typing

import fastapi
import httpx
import pytest

from src.api.routes.academy import (
    AcademyGroupUpdate,
    AttendanceUpdate,
    SubscriptionUpdate,
    get_academy_group_trials,
    list_academy_groups,
    set_academy_trial_attended,
    set_academy_trial_subscribed,
    set_academy_user_subscribed,
    update_academy_group,
)
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
async def test_academy_service_updates_group_max_cap_without_group_name(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["method"] = request.method
        captured_request["url"] = str(request.url)
        captured_request["body"] = request.read().decode()
        return httpx.Response(200, json={"ok": True, "data": {"group_id": 12}})

    async_client = httpx.AsyncClient
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "secret")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: async_client(transport=httpx.MockTransport(handler)))

    status_code, payload = await AcademyService().update_group(group_id=12, payload={"max_cap": 14})

    assert status_code == 200
    assert payload == {"ok": True, "data": {"group_id": 12}}
    assert captured_request == {
        "method": "PATCH",
        "url": "https://bot.example/api/manager/academy_groups/12",
        "body": '{"max_cap":14}',
    }


@pytest.mark.asyncio
async def test_academy_service_updates_group_name_without_max_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["method"] = request.method
        captured_request["url"] = str(request.url)
        captured_request["body"] = request.read().decode()
        return httpx.Response(200, json={"ok": True, "data": {"group_id": 12}})

    async_client = httpx.AsyncClient
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "secret")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: async_client(transport=httpx.MockTransport(handler)))

    status_code, payload = await AcademyService().update_group(group_id=12, payload={"group_name": "Kids A"})

    assert status_code == 200
    assert payload == {"ok": True, "data": {"group_id": 12}}
    assert captured_request == {
        "method": "PATCH",
        "url": "https://bot.example/api/manager/academy_groups/12",
        "body": '{"group_name":"Kids A"}',
    }


@pytest.mark.asyncio
async def test_academy_service_updates_group_start_time_without_other_group_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["method"] = request.method
        captured_request["url"] = str(request.url)
        captured_request["body"] = request.read().decode()
        return httpx.Response(200, json={"ok": True, "data": {"group_id": 12}})

    async_client = httpx.AsyncClient
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "secret")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: async_client(transport=httpx.MockTransport(handler)))

    status_code, payload = await AcademyService().update_group(group_id=12, payload={"start_time": "10:00"})

    assert status_code == 200
    assert payload == {"ok": True, "data": {"group_id": 12}}
    assert captured_request == {
        "method": "PATCH",
        "url": "https://bot.example/api/manager/academy_groups/12",
        "body": '{"start_time":"10:00"}',
    }


@pytest.mark.asyncio
async def test_academy_service_updates_group_end_time_without_other_group_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["method"] = request.method
        captured_request["url"] = str(request.url)
        captured_request["body"] = request.read().decode()
        return httpx.Response(200, json={"ok": True, "data": {"group_id": 12}})

    async_client = httpx.AsyncClient
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "secret")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: async_client(transport=httpx.MockTransport(handler)))

    status_code, payload = await AcademyService().update_group(group_id=12, payload={"end_time": "11:00"})

    assert status_code == 200
    assert payload == {"ok": True, "data": {"group_id": 12}}
    assert captured_request == {
        "method": "PATCH",
        "url": "https://bot.example/api/manager/academy_groups/12",
        "body": '{"end_time":"11:00"}',
    }


def test_academy_group_update_preserves_only_explicitly_set_fields() -> None:
    payload = AcademyGroupUpdate(start_time="10:00")

    assert payload.model_dump(exclude_unset=True) == {"start_time": "10:00"}


class FakeRouteAcademyService(AcademyService):
    async def list_groups(self) -> tuple[int, typing.Any]:
        return 200, {"ok": True, "data": {"groups": {"boxing": []}}}

    async def get_group_trials(self, group_id: int) -> tuple[int, typing.Any]:
        return 200, {"ok": True, "data": {"group_id": group_id, "trials": []}}

    async def update_group(self, group_id: int, payload: dict[str, typing.Any]) -> tuple[int, typing.Any]:
        return 200, {"ok": True, "data": {"group_id": group_id, **payload}}

    async def set_trial_attended(self, trial_id: int, attended: bool) -> tuple[int, typing.Any]:
        return 200, {"ok": True, "data": {"trial_id": trial_id, "attended": attended}}

    async def set_trial_subscribed(self, trial_id: int, subscribed: bool) -> tuple[int, typing.Any]:
        return 200, {"ok": True, "data": {"trial_id": trial_id, "subscribed": subscribed}}

    async def set_student_subscribed(self, student_id: int, subscribed: bool) -> tuple[int, typing.Any]:
        return 200, {"ok": True, "data": {"id": student_id, "subscribed": subscribed}}


@pytest.mark.asyncio
async def test_academy_manager_routes_proxy_to_service() -> None:
    service = FakeRouteAcademyService()

    groups = await list_academy_groups(academy_service=service)
    trials = await get_academy_group_trials(group_id=12, academy_service=service)
    group_update = await update_academy_group(
        group_id=12,
        payload=AcademyGroupUpdate(group_name="Kids A"),
        academy_service=service,
    )
    attended = await set_academy_trial_attended(
        trial_id=44,
        payload=AttendanceUpdate(attended=True),
        academy_service=service,
    )
    trial_subscribed = await set_academy_trial_subscribed(
        trial_id=44,
        payload=SubscriptionUpdate(subscribed=True),
        academy_service=service,
    )
    user_subscribed = await set_academy_user_subscribed(
        user_id=12,
        payload=SubscriptionUpdate(subscribed=True),
        academy_service=service,
    )

    assert groups.status_code == 200
    assert trials.status_code == 200
    assert group_update.status_code == 200
    assert attended.status_code == 200
    assert trial_subscribed.status_code == 200
    assert user_subscribed.status_code == 200


@pytest.mark.asyncio
async def test_update_academy_group_rejects_empty_payload() -> None:
    with pytest.raises(fastapi.HTTPException) as exc_info:
        await update_academy_group(
            group_id=12,
            payload=AcademyGroupUpdate(),
            academy_service=FakeRouteAcademyService(),
        )

    assert exc_info.value.status_code == fastapi.status.HTTP_400_BAD_REQUEST


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
