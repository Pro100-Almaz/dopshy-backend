import datetime

import pytest

from src.api.routes.booking import list_booked_slots, list_booked_slots_in_range
from src.models.schemas.booking import BotBookedSlotOut


EXCLUDED_SLOT_FIELDS = {
    "customer_name",
    "price_total",
    "paid_api",
    "paid_kaspi_qr",
    "paid_cash",
    "paid_avans",
}


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
