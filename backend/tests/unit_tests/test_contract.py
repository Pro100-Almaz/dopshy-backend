import typing

import fastapi
import httpx
import pytest

from src.api.dependencies.auth import require_roles_or_manager_api_key
from src.api.routes.contract import (
    create_contract,
    create_contract_bookings_batch,
    delete_contract,
    delete_contract_bookings_batch,
    get_contract,
    list_contracts,
    update_contract,
    update_contract_bookings_batch,
)
from src.config.manager import settings
from src.services.contract import ContractService


@pytest.mark.asyncio
async def test_contract_service_lists_contracts(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["method"] = request.method
        captured_request["url"] = str(request.url)
        captured_request["api_key"] = request.headers.get("X-API-Key")
        captured_request["authorization"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"ok": True, "data": []})

    async_client = httpx.AsyncClient
    monkeypatch.delenv("X_SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("MANAGER_API_KEY", raising=False)
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "secret")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: async_client(transport=httpx.MockTransport(handler)))

    status_code, payload = await ContractService().list_contracts(page=2, search="ivan")

    assert status_code == 200
    assert payload == {"ok": True, "data": []}
    assert captured_request == {
        "method": "GET",
        "url": "https://bot.example/api/manager/contracts?page=2&search=ivan",
        "api_key": "secret",
        "authorization": "Bearer secret",
    }


@pytest.mark.asyncio
async def test_contract_service_creates_contract_and_preserves_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_request = {}
    conflict = {
        "ok": False,
        "code": "SLOT_TAKEN",
        "error": "conflict",
        "conflicts": [{"field": 1, "date": "2026-09-01", "time_start": "10:00", "time_end": "11:00"}],
        "message": "Slot is already taken.",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["method"] = request.method
        captured_request["url"] = str(request.url)
        captured_request["body"] = request.read().decode()
        return httpx.Response(409, json=conflict)

    async_client = httpx.AsyncClient
    monkeypatch.delenv("X_SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("MANAGER_API_KEY", raising=False)
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "secret")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: async_client(transport=httpx.MockTransport(handler)))

    status_code, payload = await ContractService().create_contract(
        {
            "customer_name": "Ivan",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "price": "100000",
        }
    )

    assert status_code == 409
    assert payload == conflict
    assert captured_request == {
        "method": "POST",
        "url": "https://bot.example/api/manager/contracts",
        "body": '{"customer_name":"Ivan","start_date":"2026-09-01","end_date":"2026-09-30","price":"100000"}',
    }


@pytest.mark.asyncio
async def test_contract_service_forwards_all_contract_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, str(request.url), request.read().decode()))
        return httpx.Response(200, json={"ok": True})

    async_client = httpx.AsyncClient
    monkeypatch.delenv("X_SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("MANAGER_API_KEY", raising=False)
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "secret")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: async_client(transport=httpx.MockTransport(handler)))

    service = ContractService()
    await service.get_contract(contract_id=12)
    await service.update_contract(contract_id=12, payload={"notes": "VIP"})
    await service.delete_contract(contract_id=12)
    await service.create_contract_bookings(contract_id=12, payload={"slots": []})
    await service.update_contract_bookings(contract_id=12, payload={"bookings": []})
    await service.delete_contract_bookings(contract_id=12, payload={"booking_ids": [1, 2]})

    assert requests == [
        ("GET", "https://bot.example/api/manager/contracts/12", ""),
        ("PATCH", "https://bot.example/api/manager/contracts/12", '{"notes":"VIP"}'),
        ("DELETE", "https://bot.example/api/manager/contracts/12", ""),
        ("POST", "https://bot.example/api/manager/contracts/12/bookings/batch", '{"slots":[]}'),
        ("PATCH", "https://bot.example/api/manager/contracts/12/bookings/batch", '{"bookings":[]}'),
        ("DELETE", "https://bot.example/api/manager/contracts/12/bookings/batch", '{"booking_ids":[1,2]}'),
    ]


@pytest.mark.asyncio
async def test_manager_auth_accepts_bearer_service_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X_SERVICE_TOKEN", "service-token")

    dependency = require_roles_or_manager_api_key()
    result = await dependency(
        x_api_key=None,
        credentials=fastapi.security.HTTPAuthorizationCredentials(scheme="Bearer", credentials="service-token"),
        account_repo=None,
    )

    assert result is None


class FakeContractService(ContractService):
    async def list_contracts(self, page: int | None = None, search: str | None = None) -> tuple[int, typing.Any]:
        return 200, {"ok": True, "data": [{"id": 1, "bookings_count": 0, "search": search, "page": page}]}

    async def get_contract(self, contract_id: int) -> tuple[int, typing.Any]:
        return 200, {"ok": True, "data": {"id": contract_id, "booking_ids": []}}

    async def create_contract(self, payload: dict[str, typing.Any]) -> tuple[int, typing.Any]:
        return 200, {"ok": True, "data": {"contract_id": 1, "payload": payload}}

    async def update_contract(self, contract_id: int, payload: dict[str, typing.Any]) -> tuple[int, typing.Any]:
        return 200, {"ok": True, "data": {"contract_id": contract_id, "payload": payload}}

    async def delete_contract(self, contract_id: int) -> tuple[int, typing.Any]:
        return 200, {"ok": True, "data": {"contract_id": contract_id, "cancelled_ids": [1]}}

    async def create_contract_bookings(
        self,
        contract_id: int,
        payload: dict[str, typing.Any],
    ) -> tuple[int, typing.Any]:
        return 200, {"ok": True, "data": {"contract_id": contract_id, "payload": payload}}

    async def update_contract_bookings(
        self,
        contract_id: int,
        payload: dict[str, typing.Any],
    ) -> tuple[int, typing.Any]:
        return 200, {"ok": True, "data": {"contract_id": contract_id, "payload": payload}}

    async def delete_contract_bookings(
        self,
        contract_id: int,
        payload: dict[str, typing.Any],
    ) -> tuple[int, typing.Any]:
        return 200, {"ok": True, "data": {"contract_id": contract_id, "payload": payload}}


@pytest.mark.asyncio
async def test_contract_routes_proxy_to_service() -> None:
    service = FakeContractService()

    listed = await list_contracts(contract_service=service, page=1, search="ivan")
    detail = await get_contract(contract_id=12, contract_service=service)
    created = await create_contract(
        payload={
            "customer_name": "Ivan",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "price": "100000",
        },
        contract_service=service,
    )
    updated = await update_contract(
        contract_id=12,
        payload={"notes": "VIP"},
        contract_service=service,
    )
    deleted = await delete_contract(contract_id=12, contract_service=service)
    bookings_created = await create_contract_bookings_batch(
        contract_id=12,
        payload={
            "slots": [
                {
                    "field": 1,
                    "date": "2026-09-01",
                    "time_start": "10:00",
                    "time_end": "11:00",
                }
            ]
        },
        contract_service=service,
    )
    bookings_updated = await update_contract_bookings_batch(
        contract_id=12,
        payload={"bookings": [{"booking_id": 1, "notes": "Moved"}]},
        contract_service=service,
    )
    bookings_deleted = await delete_contract_bookings_batch(
        contract_id=12,
        payload={"booking_ids": [1]},
        contract_service=service,
    )

    assert listed.status_code == 200
    assert detail.status_code == 200
    assert created.status_code == 200
    assert updated.status_code == 200
    assert deleted.status_code == 200
    assert bookings_created.status_code == 200
    assert bookings_updated.status_code == 200
    assert bookings_deleted.status_code == 200


@pytest.mark.asyncio
async def test_list_contracts_rejects_invalid_page() -> None:
    response = await list_contracts(contract_service=FakeContractService(), page=0)

    assert response.status_code == fastapi.status.HTTP_400_BAD_REQUEST
