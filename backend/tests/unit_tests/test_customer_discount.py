import json
from types import SimpleNamespace

import httpx
import pytest

from src.api.routes.customer_discount import create_customer, create_discount, list_customers, update_discount
from src.config.manager import settings
from src.models.enums.role import Role
from src.models.schemas.customer_discount import (
    CustomerInCreate,
    DiscountInCreate,
    DiscountInUpdate,
    DiscountStatus,
    ManagerBookingInCreate,
)
from src.services.customer_discount import CustomerDiscountService
from src.utilities.phone import normalize_kz_phone


class RecordingService:
    def __init__(self) -> None:
        self.call = None

    async def request(self, method, path, **kwargs):
        self.call = (method, path, kwargs)
        return 201, {"ok": True, "data": {"id": 1}}


@pytest.mark.asyncio
async def test_customer_creation_replaces_client_source_with_authenticated_email() -> None:
    service = RecordingService()

    response = await create_customer(
        payload=CustomerInCreate(phone="+7 (707) 111-22-33", name="Aliya"),
        account=SimpleNamespace(email="admin@example.com", role=Role.ADMIN.value),
        service=service,
    )

    assert response.status_code == 201
    assert service.call == (
        "POST",
        "/api/manager/customers",
        {
            "json": {
                "phone": "77071112233",
                "name": "Aliya",
                "is_regular_customer": False,
                "source": "admin@example.com",
            }
        },
    )


@pytest.mark.asyncio
async def test_manager_cannot_mark_customer_as_regular_during_creation() -> None:
    with pytest.raises(Exception) as exc_info:
        await create_customer(
            payload=CustomerInCreate(phone="77071112233", is_regular_customer=True),
            account=SimpleNamespace(email="manager@example.com", role=Role.MANAGER.value),
            service=RecordingService(),
        )

    assert exc_info.value.status_code == 403


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+7 (707) 111-22-33", "77071112233"),
        ("8 707 111 22 33", "77071112233"),
        ("7071112233", "77071112233"),
    ],
)
def test_kazakhstan_phones_use_one_canonical_representation(raw: str, expected: str) -> None:
    assert normalize_kz_phone(raw) == expected


def test_single_booking_forwards_customer_ownership_and_normalized_phone() -> None:
    payload = ManagerBookingInCreate.model_validate(
        {
            "field": 1,
            "date": "2026-10-01",
            "time_start": "10:00",
            "time_end": "11:00",
            "customer_id": 7,
            "phone": "8 (707) 111-22-33",
            "price_total": 13_500,
            "discount_id": 10,
        }
    )

    body = payload.model_dump(mode="json", exclude_none=True)

    assert body["customer_id"] == 7
    assert body["phone"] == "77071112233"


def test_booking_ids_allow_bot_to_return_machine_readable_validation_errors() -> None:
    payload = ManagerBookingInCreate.model_validate(
        {
            "field": 1,
            "date": "2026-10-01",
            "time_start": "10:00",
            "time_end": "11:00",
            "customer_id": "not-a-number",
            "price_total": 13_500,
            "discount_id": "also-invalid",
        }
    )

    assert payload.customer_id == "not-a-number"
    assert payload.discount_id == "also-invalid"


@pytest.mark.asyncio
async def test_customer_phone_lookup_is_normalized_before_proxying() -> None:
    service = RecordingService()

    await list_customers(
        phone="8 (707) 111-22-33",
        search=None,
        service=service,
    )

    assert service.call == (
        "GET",
        "/api/manager/customers",
        {"params": {"phone": "77071112233", "search": None}},
    )


@pytest.mark.asyncio
async def test_admin_cannot_create_an_already_approved_discount() -> None:
    service = RecordingService()

    await create_discount(
        payload=DiscountInCreate(customer_id=1, discount_amount=10_000, status=DiscountStatus.APPROVED),
        account=SimpleNamespace(role=Role.ADMIN.value, email="admin@example.com"),
        service=service,
    )

    assert service.call[2]["json"]["status"] == "pending"
    assert service.call[2]["json"]["source"] == "admin@example.com"


@pytest.mark.asyncio
async def test_super_admin_can_approve_and_canceled_is_canonicalized() -> None:
    service = RecordingService()

    await update_discount(
        discount_id=10,
        payload=DiscountInUpdate(status=DiscountStatus.CANCELED),
        account=SimpleNamespace(email="super@example.com"),
        service=service,
    )

    assert service.call[2]["json"] == {"status": "rejected", "source": "super@example.com"}


@pytest.mark.asyncio
async def test_proxy_preserves_upstream_discount_error_status_and_code(monkeypatch) -> None:
    async_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-Key"] == "secret"
        assert json.loads(request.content) == {"discount_id": 10}
        return httpx.Response(
            409,
            json={
                "ok": False,
                "code": "DISCOUNT_UNAVAILABLE",
                "message": "Скидка недоступна или закончилась.",
            },
        )

    monkeypatch.delenv("X_SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("BOT_SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("MANAGER_API_KEY", raising=False)
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "secret")
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **_: async_client(transport=httpx.MockTransport(handler)),
    )

    status, payload = await CustomerDiscountService().request(
        "POST", "/api/manager/bookings", json={"discount_id": 10}
    )

    assert status == 409
    assert payload["code"] == "DISCOUNT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_proxy_prefers_bot_service_token(monkeypatch) -> None:
    async_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-Key"] == "preferred-token"
        return httpx.Response(200, json={"ok": True, "data": []})

    monkeypatch.setenv("BOT_SERVICE_TOKEN", "preferred-token")
    monkeypatch.setenv("X_SERVICE_TOKEN", "legacy-token")
    monkeypatch.setattr(settings, "BOT_URL", "https://bot.example")
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **_: async_client(transport=httpx.MockTransport(handler)),
    )

    status, payload = await CustomerDiscountService().request("GET", "/api/manager/customers")

    assert status == 200
    assert payload == {"ok": True, "data": []}
