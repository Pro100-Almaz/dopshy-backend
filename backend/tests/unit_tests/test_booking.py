import datetime
from types import SimpleNamespace

import fastapi
import httpx
import pydantic
import pytest

from src.api.routes.booking import list_booked_slots, list_booked_slots_in_range, list_public_availability
from src.config.manager import settings
from src.models.enums.booking import BookingStatus
from src.models.enums.role import Role
from src.models.schemas.booking import (
    BookingBatchInCreate,
    BookingHoldPaymentIn,
    BookingInUpdate,
    BookingRefundIn,
    BookingStatusUpdate,
    BotBookedSlotOut,
    BotBookingRaw,
    KaspiCheckIn,
)
from src.services.booking import BookingService

EXCLUDED_SLOT_FIELDS = {
    "customer_name",
    "price_total",
    "paid_api",
    "paid_kaspi_qr",
    "paid_cash",
    "paid_avans",
}


def test_batch_schema_preserves_explicit_null_slot_discount_override() -> None:
    payload = BookingBatchInCreate.model_validate(
        {
            "discount_id": 10,
            "slots": [
                {
                    "field": 1,
                    "date": "2026-10-01",
                    "time_start": "10:00",
                    "time_end": "11:00",
                    "discount_id": None,
                }
            ],
        }
    )

    body = payload.model_dump(mode="json", exclude_unset=True)

    assert body["discount_id"] == 10
    assert "discount_id" in body["slots"][0]
    assert body["slots"][0]["discount_id"] is None


def test_booking_output_normalizes_empty_discount_fields_to_none() -> None:
    booking = BotBookingRaw.model_validate(
        {
            "id": 1,
            "field": 1,
            "customer_id": "",
            "discount_id": "",
            "discount_amount": "",
            "price_before_discount": "",
            "price_total": "13500.00",
            "state": "confirmed",
            "source": "manager:admin",
        }
    )

    assert booking.discount_id is None
    assert booking.customer_id is None
    assert booking.discount_amount is None
    assert booking.price_before_discount is None


def test_batch_booking_forwards_customer_id_and_normalizes_phone() -> None:
    payload = BookingBatchInCreate.model_validate(
        {
            "customer_id": 7,
            "phone": "8 707 111 22 33",
            "slots": [
                {
                    "field": 1,
                    "date": "2026-10-01",
                    "time_start": "10:00",
                    "time_end": "11:00",
                }
            ],
        }
    )

    body = payload.model_dump(mode="json", exclude_unset=True)

    assert body["customer_id"] == 7
    assert body["phone"] == "77071112233"


def test_booked_slot_output_excludes_customer_name_price_and_payment_fields() -> None:
    slot = BotBookedSlotOut.model_validate(
        {
            "id": 1,
            "field": 2,
            "customer_name": "Client One",
            "phone": "+77001112233",
            "time_start": "10:00",
            "time_end": "11:00",
            "price_total": "12000.00",
            "state": "confirmed",
            "source": "manager:admin",
            "notes": "Bring ball",
            "date": "2026-08-27",
            "reserved_until": "2026-08-27T09:30:00",
            "paid_api": "1000.00",
            "paid_kaspi_qr": "2000.00",
            "paid_cash": "3000.00",
            "paid_avans": "4000.00",
            "created_at": "2026-08-26T09:00:00",
            "updated_at": "2026-08-26T10:00:00",
        }
    )

    payload = slot.model_dump()

    assert payload.keys().isdisjoint(EXCLUDED_SLOT_FIELDS)
    assert payload["id"] == 1
    assert payload["field"] == 2
    assert payload["phone"] == "+77001112233"
    assert payload["state"] == "confirmed"


@pytest.mark.asyncio
async def test_booked_slots_endpoint_uses_sanitized_service_method() -> None:
    class FakeBookingService:
        async def get_all_booked_slots(self, **kwargs):
            assert kwargs == {"page": 2, "search": "client"}
            return [
                BotBookedSlotOut(
                    id=1,
                    field=2,
                    phone="+77001112233",
                    time_start=datetime.time(hour=10),
                    time_end=datetime.time(hour=11),
                    state="confirmed",
                    source="manager:admin",
                    notes="Bring ball",
                    date=datetime.date(year=2026, month=8, day=27),
                    reserved_until="2026-08-27T09:30:00",
                    created_at=datetime.datetime(year=2026, month=8, day=26, hour=9),
                    updated_at=datetime.datetime(year=2026, month=8, day=26, hour=10),
                )
            ]

    slots = await list_booked_slots(
        booking_service=FakeBookingService(),
        page=2,
        search="client",
    )

    assert slots is not None
    assert slots[0].model_dump().keys().isdisjoint(EXCLUDED_SLOT_FIELDS)


@pytest.mark.asyncio
async def test_booked_slots_range_endpoint_uses_sanitized_service_method() -> None:
    class FakeBookingService:
        async def get_booked_slots_in_range(self, **kwargs):
            assert kwargs == {
                "start_date": "2026-08-27",
                "end_date": "2026-08-28",
                "field": 2,
                "page": 3,
                "search": "client",
            }
            return [
                BotBookedSlotOut(
                    id=2,
                    field=2,
                    phone="+77001112233",
                    time_start=datetime.time(hour=12),
                    time_end=datetime.time(hour=13),
                    state="pending",
                    source="landing:+77001112233",
                    date=datetime.date(year=2026, month=8, day=28),
                )
            ]

    slots = await list_booked_slots_in_range(
        start_date="2026-08-27",
        end_date="2026-08-28",
        booking_service=FakeBookingService(),
        field=2,
        page=3,
        search="client",
    )

    assert slots is not None
    assert slots[0].model_dump().keys().isdisjoint(EXCLUDED_SLOT_FIELDS)


@pytest.mark.asyncio
async def test_public_availability_keeps_blocking_states_and_drops_customer_data() -> None:
    def slot(id: int, state: str) -> BotBookedSlotOut:
        return BotBookedSlotOut(
            id=id,
            field=1,
            phone="+77001112233",
            time_start=datetime.time(hour=19),
            time_end=datetime.time(hour=20),
            state=state,
            source="landing:+77001112233",
            notes="secret",
            date=datetime.date(year=2026, month=10, day=3),
        )

    class Service(BookingService):
        def __init__(self) -> None:  # no repos needed: only the bot fetch is faked
            pass

        async def get_booked_slots_in_range(self, **kwargs):
            assert kwargs == {"start_date": "2026-10-03", "end_date": "2026-10-09", "field": 1}
            return [
                slot(1, "confirmed"),
                slot(2, "awaiting_payment"),
                slot(3, "cancelled"),
                slot(4, "draft"),
                slot(5, "awaiting_consent"),
            ]

    rows = await Service().get_public_availability(start_date="2026-10-03", end_date="2026-10-09", field=1)

    assert len(rows) == 3  # cancelled/draft don't hold the slot; awaiting_consent does
    assert set(rows[0].model_dump()) == {"field", "date", "time_start", "time_end"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("start", "end"),
    [((2026, 10, 9), (2026, 10, 3)), ((2026, 10, 1), (2026, 11, 15))],
)
async def test_public_availability_rejects_reversed_or_oversized_range(start, end) -> None:
    class Untouched:
        async def get_public_availability(self, **kwargs):
            raise AssertionError("must not reach the bot")

    with pytest.raises(fastapi.HTTPException) as exc:
        await list_public_availability(
            start_date=datetime.date(*start),
            end_date=datetime.date(*end),
            booking_service=Untouched(),
            field=None,
        )
    assert exc.value.status_code == 422


# Offer consent / site channel / payment number (bot batch contract)


class FakeBot:
    """Replaces httpx.AsyncClient inside services.booking and records the POST body."""

    def __init__(self, status: int = 200, body: dict | None = None) -> None:
        self.status = status
        self.body = body if body is not None else {"ok": True, "booking_ids": [1], "data": {}}
        self.sent: dict | None = None
        self.url: str | None = None

    def __call__(self, *args, **kwargs):
        outer = self

        class Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def post(self, url, headers=None, json=None):
                outer.sent = json
                outer.url = url
                return httpx.Response(outer.status, json=outer.body)

            async def get(self, url, headers=None):
                outer.url = url
                return httpx.Response(outer.status, json=outer.body)

        return Client()


@pytest.fixture(name="bot")
def bot_fixture(monkeypatch) -> FakeBot:
    monkeypatch.setattr(settings, "BOT_URL", "http://bot:5000")
    bot = FakeBot()
    monkeypatch.setattr(httpx, "AsyncClient", bot)
    return bot


CONSENT = {"accepted": True, "offer_version": "2026-10", "text_version": "v3", "at": "2026-10-30T12:00:00+05:00"}
STAFF = SimpleNamespace(role=Role.MANAGER.value, email="manager@example.com")
ADMIN = SimpleNamespace(role=Role.ADMIN.value, email="admin@example.com")
SUPER_ADMIN = SimpleNamespace(role=Role.SUPER_ADMIN.value, email="superadmin@example.com")
CLIENT = SimpleNamespace(role=Role.CLIENT.value, email="client@example.com")


def _batch_payload(**overrides) -> BookingBatchInCreate:
    data = {
        "phone": "8 707 111 22 33",
        "slots": [{"field": 1, "date": "2026-10-01", "time_start": "10:00", "time_end": "11:00"}],
    }
    data.update(overrides)
    return BookingBatchInCreate.model_validate(data)


def _service() -> BookingService:
    return BookingService(booking_repo=None, field_repo=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize("user", [None, CLIENT])
@pytest.mark.parametrize("consent", [None, {"accepted": False}])
async def test_public_batch_without_consent_is_rejected_before_the_bot(bot, user, consent) -> None:
    status, data = await _service().create_bookings_batch(_batch_payload(consent=consent), current_user=user)

    assert status == 400
    assert data == {
        "ok": False,
        "code": "CONSENT_REQUIRED",
        "message": "Для брони необходимо согласиться с офертой.",
    }
    assert bot.sent is None


@pytest.mark.asyncio
@pytest.mark.parametrize(("user", "source"), [(None, "landing:77071112233"), (CLIENT, "account:client@example.com")])
async def test_public_batch_with_consent_is_sent_as_site_channel(bot, user, source) -> None:
    status, data = await _service().create_bookings_batch(
        _batch_payload(consent=CONSENT, kaspi_phone="+7 (701) 555-44-33", lang="kk"), current_user=user
    )

    assert status == 200 and data["ok"] is True
    assert bot.sent["channel"] == "site"
    assert bot.sent["source"] == source
    assert bot.sent["consent"] == CONSENT
    assert bot.sent["kaspi_phone"] == "77015554433"
    assert bot.sent["phone"] == "77071112233"
    assert bot.sent["lang"] == "kk"


@pytest.mark.asyncio
async def test_public_batch_passes_bot_payment_link_response_through(bot) -> None:
    bot.body = {
        "ok": True,
        "created_count": 1,
        "booking_ids": [7],
        "invoice": None,
        "payment": {"method": "link", "url": "https://pay.kaspi.kz/x", "amount": 10000, "reason": "no_kaspi"},
        "consent": None,
        "data": {},
    }

    status, data = await _service().create_bookings_batch(_batch_payload(consent=CONSENT), current_user=None)

    assert status == 200
    assert data == bot.body


@pytest.mark.asyncio
async def test_staff_batch_strips_consent_and_channel_but_forwards_kaspi_phone(bot) -> None:
    bot.body = {
        "ok": True,
        "booking_ids": [9],
        "invoice": None,
        "payment": None,
        "consent": {"status": "pending", "request_id": 5},
        "data": {},
    }

    status, data = await _service().create_bookings_batch(
        _batch_payload(consent=CONSENT, kaspi_phone="87015554433", lang="ru"), current_user=STAFF
    )

    assert status == 200 and data["consent"] == {"status": "pending", "request_id": 5}
    assert "consent" not in bot.sent
    assert "channel" not in bot.sent
    assert bot.sent["kaspi_phone"] == "77015554433"
    assert bot.sent["lang"] == "ru"
    assert bot.sent["source"] == "manager@example.com"


@pytest.mark.asyncio
async def test_staff_batch_does_not_need_consent(bot) -> None:
    status, _ = await _service().create_bookings_batch(_batch_payload(), current_user=STAFF)

    assert status == 200
    assert bot.sent is not None and "consent" not in bot.sent and "channel" not in bot.sent


@pytest.mark.asyncio
@pytest.mark.parametrize("user", [None, CLIENT, STAFF])
async def test_24h_hold_is_restricted_to_admins(bot, user) -> None:
    with pytest.raises(fastapi.HTTPException) as exc:
        await _service().create_bookings_batch(_batch_payload(hold_without_payment=True), current_user=user)
    assert exc.value.status_code == 403
    assert bot.sent is None


@pytest.mark.asyncio
@pytest.mark.parametrize("user", [ADMIN, SUPER_ADMIN])
async def test_24h_hold_forces_no_payment_invariants(bot, user) -> None:
    status, _ = await _service().create_bookings_batch(
        _batch_payload(
            hold_without_payment=True,
            reserved_until=5,
            prepayment=9999,
            kaspi_phone="87015554433",
            consent=CONSENT,
        ),
        current_user=user,
    )
    assert status == 200
    assert bot.sent["hold_without_payment"] is True
    assert bot.sent["reserved_until"] == 1440
    assert bot.sent["prepayment"] == 0
    assert "kaspi_phone" not in bot.sent
    assert "consent" not in bot.sent


@pytest.mark.asyncio
async def test_admin_can_convert_hold_through_bot_consent_endpoint(bot) -> None:
    bot.body = {"ok": True, "request_id": 17, "booking_ids": [9]}
    status, data = await _service().request_payment_for_hold(
        9,
        BookingHoldPaymentIn(phone="8 707 111 22 33", lang="kk"),
        current_user=ADMIN,
    )
    assert status == 200 and data["request_id"] == 17
    assert bot.sent == {"phone": "77071112233", "lang": "kk", "source": "admin@example.com"}


@pytest.mark.asyncio
async def test_staff_kaspi_check_is_relayed_to_the_bot(bot) -> None:
    bot.body = {"ok": True, "has_kaspi": False, "phone": "87071112233", "checked": True}
    status, data = await _service().check_kaspi_number(KaspiCheckIn(phone="8 707 111 22 33"), current_user=STAFF)
    assert status == 200 and data["has_kaspi"] is False
    assert bot.sent == {"phone": "77071112233"}


@pytest.mark.asyncio
async def test_client_cannot_check_kaspi_numbers(bot) -> None:
    with pytest.raises(fastapi.HTTPException) as exc:
        await _service().check_kaspi_number(KaspiCheckIn(phone="77071112233"), current_user=CLIENT)
    assert exc.value.status_code == 403
    assert bot.sent is None


def test_batch_schema_rejects_bad_lang_and_ignores_client_channel() -> None:
    with pytest.raises(pydantic.ValidationError):
        _batch_payload(lang="en")
    with pytest.raises(pydantic.ValidationError):
        _batch_payload(consent={"offer_version": "x"})  # accepted is required
    # `channel` is not a schema field: a client-sent value never reaches the dump.
    assert "channel" not in _batch_payload(channel="admin_bot").model_dump()


def test_blank_kaspi_phone_means_default_contact_phone() -> None:
    assert _batch_payload(kaspi_phone="  ").kaspi_phone is None
    assert _batch_payload().kaspi_phone is None


def test_awaiting_consent_is_a_valid_status() -> None:
    assert BookingStatus("awaiting_consent") is BookingStatus.AWAITING_CONSENT
    assert BookingInUpdate.model_validate({"status": "awaiting_consent"}).model_dump(
        mode="json", exclude_unset=True
    ) == {"status": "awaiting_consent"}
    assert BookingStatusUpdate.model_validate({"status": "awaiting_consent"}).status is BookingStatus.AWAITING_CONSENT


def test_booking_row_exposes_consent_and_payment_fields() -> None:
    row = BotBookingRaw.model_validate(
        {
            "id": 1,
            "state": "awaiting_consent",
            "source": "manager:admin",
            "kaspi_phone": "77015554433",
            "consent_at": "2026-10-30T12:00:00+05:00",
            "consent_channel": "site",
            "consent_text_version": "v3",
            "offer_version": "2026-10",
            "payment_method": "link",
        }
    ).model_dump(mode="json")

    assert row["kaspi_phone"] == "77015554433"
    assert row["consent_at"] == "2026-10-30T12:00:00+05:00"
    assert row["consent_channel"] == "site"
    assert row["consent_text_version"] == "v3"
    assert row["offer_version"] == "2026-10"
    assert row["payment_method"] == "link"

    blank = BotBookingRaw.model_validate(
        {
            "id": 2,
            "state": "confirmed",
            "source": "x",
            "kaspi_phone": "",
            "consent_at": "",
            "consent_channel": "",
            "consent_text_version": "",
            "offer_version": "",
            "payment_method": "",
        }
    )
    assert blank.consent_at is None and blank.payment_method is None and blank.kaspi_phone is None


# Refunds (proxied to the bot, which enforces the amount cap)

ARENA_MANAGER = SimpleNamespace(role=Role.ARENA_MANAGER.value, email="arena@example.com")


@pytest.mark.asyncio
@pytest.mark.parametrize("user", [ADMIN, SUPER_ADMIN, ARENA_MANAGER])
async def test_refund_is_forwarded_with_actor(bot, user) -> None:
    bot.body = {"ok": True, "data": {"refundable": 0, "refunds": []}}
    status, data = await _service().create_booking_refund(
        7, BookingRefundIn(amount=5000, comment="отмена", request_key="press-0001"), current_user=user
    )
    assert status == 200 and data["ok"]
    assert bot.url == "http://bot:5000/api/manager/bookings/7/refunds"
    assert bot.sent == {"amount": 5000, "comment": "отмена", "request_key": "press-0001", "source": user.email}


@pytest.mark.asyncio
@pytest.mark.parametrize("user", [None, CLIENT, STAFF])
async def test_refund_is_restricted_roles(bot, user) -> None:
    with pytest.raises(fastapi.HTTPException) as exc:
        await _service().create_booking_refund(7, BookingRefundIn(amount=1), current_user=user)
    assert exc.value.status_code == 403
    assert bot.sent is None


@pytest.mark.asyncio
async def test_refund_cap_error_from_bot_passes_through(bot) -> None:
    bot.status = 409
    bot.body = {"ok": False, "code": "AMOUNT_TOO_LARGE", "message": "Можно вернуть не больше 10000₸."}
    status, data = await _service().create_booking_refund(7, BookingRefundIn(amount=99999), current_user=ADMIN)
    assert status == 409 and data["code"] == "AMOUNT_TOO_LARGE"


@pytest.mark.asyncio
async def test_refund_history_is_read_from_bot(bot) -> None:
    bot.body = {"ok": True, "data": {"within_window": False, "refunds": [{"id": 1, "booking_id": 7}]}}
    status, data = await _service().get_booking_refunds(7, current_user=ARENA_MANAGER)
    assert status == 200 and data["data"]["within_window"] is False
    assert bot.url == "http://bot:5000/api/manager/bookings/7/refunds"


@pytest.mark.parametrize("amount", [0, -1, 10.5])
def test_refund_schema_rejects_bad_amount(amount) -> None:
    with pytest.raises(pydantic.ValidationError):
        BookingRefundIn(amount=amount)


def test_booking_row_exposes_refund_fields() -> None:
    row = BotBookingRaw.model_validate(
        {"id": 1, "state": "confirmed", "source": "x", "first_paid_at": "", "refunded_total": 2500}
    )
    assert row.first_paid_at is None and row.refunded_total == 2500


@pytest.mark.parametrize("key", ["short", "has spaces in it", "x" * 101])
def test_refund_schema_rejects_bad_request_key(key) -> None:
    with pytest.raises(pydantic.ValidationError):
        BookingRefundIn(amount=1, request_key=key)
