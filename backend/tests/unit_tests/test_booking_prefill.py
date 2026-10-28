import datetime
import hashlib
import zoneinfo

import fastapi
import httpx
import pydantic
import pytest

from src.api.dependencies.auth import require_bot_prefill_key
from src.api.routes.prefill import create_prefill, resolve_prefill
from src.config.manager import settings
from src.models.db.booking_prefill import BookingPrefill
from src.models.schemas.booking import BookingBatchInCreate, PublicBookedSlotOut
from src.models.schemas.prefill import PrefillCreateIn
from src.services.booking import BookingService
from src.services.booking_prefill import BookingPrefillService

VENUE_TZ = zoneinfo.ZoneInfo("Asia/Almaty")
UTC = datetime.timezone.utc


def _future_day(days: int = 5) -> datetime.date:
    return datetime.datetime.now(tz=VENUE_TZ).date() + datetime.timedelta(days=days)


def _payload(**overrides) -> dict:
    data = {
        "phone": "87011234567",
        "customer_name": "Almaz",
        "field": 1,
        "date": _future_day().isoformat(),
        "time_start": "19:00",
        "time_end": "20:00",
        "players": 10,
        "lang": "ru",
        "conversation_id": "123456:77011234567",
    }
    data.update(overrides)
    return data


class FakePrefillRepo:
    def __init__(self) -> None:
        self.rows: dict[str, BookingPrefill] = {}
        self.next_id = 1

    async def create(self, **values) -> BookingPrefill:
        row = BookingPrefill(id=self.next_id, first_opened_at=None, consumed_at=None, bot_booking_ids=None, **values)
        self.next_id += 1
        self.rows[row.token_hash] = row
        return row

    async def read_by_hash(self, token_hash: str):
        return self.rows.get(token_hash)

    async def mark_opened(self, prefill_id: int, now: datetime.datetime) -> None:
        for row in self.rows.values():
            if row.id == prefill_id and row.first_opened_at is None:
                row.first_opened_at = now

    async def mark_consumed(self, prefill_id: int, booking_ids, now: datetime.datetime) -> bool:
        for row in self.rows.values():
            if row.id == prefill_id and row.consumed_at is None:
                row.consumed_at, row.bot_booking_ids = now, booking_ids
                return True
        return False


@pytest.fixture(autouse=True)
def prefill_settings(monkeypatch):
    monkeypatch.setattr(settings, "BOT_PREFILL_API_KEY", "bot-key")
    monkeypatch.setattr(settings, "PLATFORM_BOOKING_URL", "https://dopsy.kz/arena")
    monkeypatch.setattr(settings, "BOT_URL", "http://bot:5000")


@pytest.fixture(name="repo")
def repo_fixture() -> FakePrefillRepo:
    return FakePrefillRepo()


@pytest.fixture(name="service")
def service_fixture(repo) -> BookingPrefillService:
    return BookingPrefillService(prefill_repo=repo)


async def _create(service: BookingPrefillService, **overrides):
    return await service.create(PrefillCreateIn.model_validate(_payload(**overrides)))


class FakeAvailability:
    """Stands in for BookingService in the resolve route."""

    def __init__(self, busy=None, error: bool = False) -> None:
        self.busy, self.error = busy or [], error

    async def get_public_availability(self, **kwargs):
        if self.error:
            raise fastapi.HTTPException(status_code=502, detail="down")
        return self.busy


def _busy(start: int, end: int, day: str) -> PublicBookedSlotOut:
    return PublicBookedSlotOut(
        field=1, date=day, time_start=datetime.time(start), time_end=datetime.time(end)
    )


# 1. create


@pytest.mark.asyncio
async def test_create_returns_envelope_and_stores_only_the_token_hash(service, repo) -> None:
    response = await create_prefill(PrefillCreateIn.model_validate(_payload()), prefill_service=service)

    token = response.data.token
    assert response.ok is True
    assert response.data.url == f"https://dopsy.kz/arena?p={token}#booking"
    assert response.data.expires_at > datetime.datetime.now(tz=UTC) + datetime.timedelta(hours=23)
    [(stored_hash, row)] = repo.rows.items()
    assert stored_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in repr(row.__dict__)
    assert row.source == "bot_link"


# 2. auth


@pytest.mark.asyncio
@pytest.mark.parametrize("key", [None, "", "wrong"])
async def test_bot_key_rejects_missing_or_wrong_key(key) -> None:
    with pytest.raises(fastapi.HTTPException) as exc:
        await require_bot_prefill_key(x_api_key=key)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid API key."


@pytest.mark.asyncio
async def test_bot_key_accepts_configured_key_and_falls_back_to_manager_key(monkeypatch) -> None:
    assert await require_bot_prefill_key(x_api_key="bot-key") is None
    monkeypatch.setattr(settings, "BOT_PREFILL_API_KEY", "")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "manager-key")
    assert await require_bot_prefill_key(x_api_key="manager-key") is None


@pytest.mark.asyncio
async def test_bot_key_503_when_no_key_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "BOT_PREFILL_API_KEY", "")
    monkeypatch.setattr(settings, "MANAGER_API_KEY", "")
    with pytest.raises(fastapi.HTTPException) as exc:
        await require_bot_prefill_key(x_api_key="anything")
    assert exc.value.status_code == 503
    assert exc.value.detail == "Prefill API is not configured."


# 3 + 4. validation


def test_phone_is_normalized() -> None:
    assert PrefillCreateIn.model_validate(_payload(phone="87011234567")).phone == "77011234567"
    assert PrefillCreateIn.model_validate(_payload(phone="+7 (701) 123-45-67")).phone == "77011234567"


def test_blank_strings_are_treated_as_null() -> None:
    payload = PrefillCreateIn.model_validate(
        {"phone": "77011234567", **{k: "" for k in _payload() if k != "phone"}}
    )
    assert payload.model_dump(exclude={"phone"}) == dict.fromkeys(_payload().keys() - {"phone"})


@pytest.mark.parametrize(
    "overrides",
    [
        {"date": (_future_day(-1)).isoformat()},
        {"time_start": "20:00", "time_end": "19:00"},
        {"time_start": "19:00", "time_end": "19:00"},
        {"time_end": ""},
        {"time_start": ""},
        {"phone": "12345"},
        {"phone": "+44 20 7946 0958"},
        {"field": 4},
        {"field": 0},
        {"lang": "en"},
        {"unknown": "x"},
    ],
)
def test_invalid_payloads_are_rejected(overrides) -> None:
    with pytest.raises(pydantic.ValidationError):
        PrefillCreateIn.model_validate(_payload(**overrides))


def test_same_day_time_already_passed_is_rejected(monkeypatch) -> None:
    from src.models.schemas import prefill as prefill_schema

    fixed = datetime.datetime(2026, 11, 6, 15, 0, tzinfo=VENUE_TZ)
    monkeypatch.setattr(prefill_schema, "venue_now", lambda: fixed)

    with pytest.raises(pydantic.ValidationError):
        PrefillCreateIn.model_validate(_payload(date="2026-11-06", time_start="14:00", time_end="15:00"))
    PrefillCreateIn.model_validate(_payload(date="2026-11-06", time_start="19:00", time_end="20:00"))


# 5. resolve


@pytest.mark.asyncio
async def test_resolve_masks_phone_and_sets_first_opened_once(service, repo) -> None:
    created = await _create(service)

    out = await resolve_prefill(created.token, fastapi.Response(), service, FakeAvailability())
    row = next(iter(repo.rows.values()))
    first_opened = row.first_opened_at
    await resolve_prefill(created.token, fastapi.Response(), service, FakeAvailability())

    assert out.phone_masked == "+7 701 *** ** 67"
    assert "7011234567" not in out.model_dump_json()
    assert (out.time_start, out.time_end, out.field, out.players) == ("19:00", "20:00", 1, 10)
    assert first_opened is not None and row.first_opened_at == first_opened


@pytest.mark.asyncio
async def test_resolve_sets_no_store_headers(service) -> None:
    created = await _create(service)
    response = fastapi.Response()
    await resolve_prefill(created.token, response, service, FakeAvailability())
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"


@pytest.mark.asyncio
async def test_unknown_and_expired_tokens_give_identical_404(service, repo) -> None:
    created = await _create(service)
    next(iter(repo.rows.values())).expires_at = datetime.datetime.now(tz=UTC) - datetime.timedelta(seconds=1)

    errors = []
    for token in (created.token, "does-not-exist"):
        with pytest.raises(fastapi.HTTPException) as exc:
            await resolve_prefill(token, fastapi.Response(), service, FakeAvailability())
        errors.append((exc.value.status_code, exc.value.detail))

    assert errors[0] == errors[1] == (404, "Prefill not found or expired.")


@pytest.mark.asyncio
async def test_consumed_token_gives_410(service, repo) -> None:
    created = await _create(service)
    next(iter(repo.rows.values())).consumed_at = datetime.datetime.now(tz=UTC)

    with pytest.raises(fastapi.HTTPException) as exc:
        await resolve_prefill(created.token, fastapi.Response(), service, FakeAvailability())
    assert (exc.value.status_code, exc.value.detail) == (410, "Prefill already used.")


# 6. availability


@pytest.mark.asyncio
async def test_busy_slot_is_unavailable_and_offers_free_alternatives(service) -> None:
    created = await _create(service)
    day = _future_day().isoformat()

    out = await resolve_prefill(created.token, fastapi.Response(), service, FakeAvailability([_busy(19, 20, day)]))

    assert out.slot_available is False
    starts = [a.time_start for a in out.alternatives]
    assert 0 < len(starts) <= 5
    assert "19:00" not in starts
    assert {"18:00", "20:00"} <= set(starts)


@pytest.mark.asyncio
async def test_free_slot_is_available_without_alternatives(service) -> None:
    created = await _create(service)
    out = await resolve_prefill(created.token, fastapi.Response(), service, FakeAvailability())
    assert (out.slot_available, out.alternatives) == (True, [])


@pytest.mark.asyncio
async def test_bot_unreachable_still_prefills_with_unknown_availability(service) -> None:
    created = await _create(service)
    out = await resolve_prefill(created.token, fastapi.Response(), service, FakeAvailability(error=True))
    assert out.slot_available is None
    assert out.customer_name == "Almaz"


@pytest.mark.asyncio
async def test_no_slot_means_no_availability_check(service) -> None:
    created = await _create(service, date="", time_start="", time_end="")
    out = await resolve_prefill(created.token, fastapi.Response(), service, FakeAvailability(error=True))
    assert out.slot_available is None


# 12. routing


def test_prefill_route_is_not_captured_by_booking_id_route(backend_test_app) -> None:
    from starlette.routing import Match

    scope = {"type": "http", "method": "GET", "path": "/api/bookings/prefill/x", "root_path": "", "headers": []}
    for route in backend_test_app.routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            assert route.name == "prefill:resolve"
            return
    raise AssertionError("no route matched")


# 7-11. batch


class FakeBot:
    """Replaces httpx.AsyncClient inside services.booking and records the POST body."""

    def __init__(self, status: int = 201, body: dict | None = None) -> None:
        self.status = status
        self.body = body if body is not None else {"ok": True, "data": [{"id": 41}, {"id": 42}]}
        self.sent: dict | None = None

    def __call__(self, *args, **kwargs):
        outer = self

        class Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def post(self, url, headers=None, json=None):
                outer.sent = json
                return httpx.Response(outer.status, json=outer.body)

        return Client()


def _batch(**overrides) -> BookingBatchInCreate:
    data = {
        "slots": [{"field": 1, "date": _future_day().isoformat(), "time_start": "19:00", "time_end": "20:00"}],
    }
    data.update(overrides)
    return BookingBatchInCreate.model_validate(data)


def _booking_service(prefill_service: BookingPrefillService) -> BookingService:
    return BookingService(booking_repo=None, field_repo=None, prefill_service=prefill_service)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_batch_with_valid_token_injects_phone_sets_source_and_consumes(service, repo, monkeypatch) -> None:
    bot = FakeBot()
    monkeypatch.setattr(httpx, "AsyncClient", bot)
    created = await _create(service)

    status, data = await _booking_service(service).create_bookings_batch(
        _batch(prefill_token=created.token), current_user=None
    )

    assert status == 201 and data["ok"] is True
    assert bot.sent["phone"] == "77011234567"
    assert bot.sent["customer"] == "Almaz"
    assert bot.sent["source"] == "bot_link:77011234567"
    assert "prefill_token" not in bot.sent
    row = next(iter(repo.rows.values()))
    assert row.consumed_at is not None
    assert row.bot_booking_ids == [41, 42]


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["unknown", "expired", "consumed"])
async def test_batch_with_bad_token_is_a_normal_landing_booking(service, repo, monkeypatch, state) -> None:
    bot = FakeBot()
    monkeypatch.setattr(httpx, "AsyncClient", bot)
    created = await _create(service)
    row = next(iter(repo.rows.values()))
    if state == "expired":
        row.expires_at = datetime.datetime.now(tz=UTC) - datetime.timedelta(hours=1)
    if state == "consumed":
        row.consumed_at = datetime.datetime.now(tz=UTC)
    token = "nope" if state == "unknown" else created.token

    status, _ = await _booking_service(service).create_bookings_batch(
        _batch(prefill_token=token, phone="77079998877"), current_user=None
    )

    assert status == 201
    assert bot.sent["source"] == "landing:77079998877"
    assert bot.sent["phone"] == "77079998877"
    assert "prefill_token" not in bot.sent
    assert row.bot_booking_ids is None


@pytest.mark.asyncio
async def test_bot_conflict_leaves_token_unconsumed(service, repo, monkeypatch) -> None:
    monkeypatch.setattr(
        httpx, "AsyncClient", FakeBot(status=409, body={"ok": False, "code": "SLOT_TAKEN", "message": "taken"})
    )
    created = await _create(service)

    status, data = await _booking_service(service).create_bookings_batch(
        _batch(prefill_token=created.token), current_user=None
    )

    assert status == 409 and data["ok"] is False
    assert next(iter(repo.rows.values())).consumed_at is None


@pytest.mark.asyncio
async def test_typed_phone_wins_over_prefill_phone(service, monkeypatch) -> None:
    bot = FakeBot()
    monkeypatch.setattr(httpx, "AsyncClient", bot)
    created = await _create(service)

    await _booking_service(service).create_bookings_batch(
        _batch(prefill_token=created.token, phone="8 707 111 22 33", customer="Other"), current_user=None
    )

    assert bot.sent["phone"] == "77071112233"
    assert bot.sent["customer"] == "Other"
    assert bot.sent["source"] == "bot_link:77071112233"


@pytest.mark.asyncio
async def test_consume_failure_does_not_fail_the_booking(service, monkeypatch) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", FakeBot())
    created = await _create(service)

    async def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(service, "mark_consumed", boom)

    status, data = await _booking_service(service).create_bookings_batch(
        _batch(prefill_token=created.token), current_user=None
    )
    assert status == 201 and data["ok"] is True


@pytest.mark.asyncio
async def test_token_does_not_unlock_discounts(service, monkeypatch) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", FakeBot())
    created = await _create(service)

    with pytest.raises(fastapi.HTTPException) as exc:
        await _booking_service(service).create_bookings_batch(
            _batch(prefill_token=created.token, discount_id=3), current_user=None
        )
    assert exc.value.status_code == 403
