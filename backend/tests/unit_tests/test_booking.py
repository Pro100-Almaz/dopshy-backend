import datetime

import fastapi
import pytest

from src.api.routes.booking import list_booked_slots, list_booked_slots_in_range, list_public_availability
from src.models.schemas.booking import BookingBatchInCreate, BotBookedSlotOut, BotBookingRaw
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
            return [slot(1, "confirmed"), slot(2, "awaiting_payment"), slot(3, "cancelled"), slot(4, "draft")]

    rows = await Service().get_public_availability(start_date="2026-10-03", end_date="2026-10-09", field=1)

    assert len(rows) == 2  # cancelled/draft don't hold the slot
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
