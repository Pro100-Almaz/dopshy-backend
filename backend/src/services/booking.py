import datetime
import typing

import fastapi
import httpx
import loguru

from src.config.manager import settings
from src.models.db.account import Account
from src.models.enums.booking import BookingSource, BookingStatus, RepeatMode
from src.models.enums.role import Role
from src.models.schemas.booking import (
    BookingBatchInCreate,
    BookingDetailOut,
    BookingInCreate,
    BookingInCreateAuthenticated,
    BookingInCreateByManager,
    BookingInUpdate,
    BookingOut,
    BookingStatusUpdate,
    BotBookedSlotOut,
    PublicBookedSlotOut,
    BotBookingRaw,
)
from src.repository.crud.booking import BookingCRUDRepository
from src.repository.crud.field import FieldCRUDRepository
from src.utilities.bot_auth import get_bot_service_headers
from src.utilities.exceptions.database import EntityDoesNotExist

if typing.TYPE_CHECKING:
    from src.services.booking_prefill import BookingPrefillService


class BookingService:
    def __init__(
        self,
        booking_repo: BookingCRUDRepository,
        field_repo: FieldCRUDRepository,
        prefill_service: "BookingPrefillService | None" = None,
    ) -> None:
        self.booking_repo = booking_repo
        self.field_repo = field_repo
        self.prefill_service = prefill_service

    async def _compute_total_price(
        self, field_id: int, start_datetime: datetime.datetime, duration_hours: int
    ) -> float:
        price_per_hour = await self.field_repo.get_price_for_weekday(
            field_id=field_id, day_of_week=start_datetime.weekday()
        )
        return float(price_per_hour) * duration_hours

    async def create_anonymous_booking(self, payload: BookingInCreate) -> BookingDetailOut:
        # verify field exists
        await self.field_repo.read_field_by_id(id=payload.field_id)
        total_price = await self._compute_total_price(
            field_id=payload.field_id,
            start_datetime=payload.start_datetime,
            duration_hours=payload.duration_hours,
        )
        booking = await self.booking_repo.create_booking(
            field_id=payload.field_id,
            start_datetime=payload.start_datetime,
            duration_hours=payload.duration_hours,
            total_price=total_price,
            status=BookingStatus.PENDING.value,
            source=f"{payload.source.value}:{payload.guest_phone}",
            guest_name=payload.guest_name,
            guest_phone=payload.guest_phone,
            guest_email=payload.guest_email,
            internal_note=payload.internal_note,
        )
        return BookingDetailOut.model_validate(booking)

    async def create_authenticated_booking(
        self, payload: BookingInCreateAuthenticated, current_account: Account
    ) -> BookingDetailOut:
        await self.field_repo.read_field_by_id(id=payload.field_id)
        total_price = await self._compute_total_price(
            field_id=payload.field_id,
            start_datetime=payload.start_datetime,
            duration_hours=payload.duration_hours,
        )
        booking = await self.booking_repo.create_booking(
            field_id=payload.field_id,
            start_datetime=payload.start_datetime,
            duration_hours=payload.duration_hours,
            total_price=total_price,
            status=BookingStatus.PENDING.value,
            source=f"{BookingSource.ACCOUNT.value}:{current_account.email}",
            account_id=current_account.id,
            internal_note=payload.internal_note,
            created_by_account_id=current_account.id,
        )
        return BookingDetailOut.model_validate(booking)

    async def create_manager_booking(
        self, payload: BookingInCreateByManager, manager_account: Account
    ) -> BookingDetailOut:
        await self.field_repo.read_field_by_id(id=payload.field_id)
        total_price = await self._compute_total_price(
            field_id=payload.field_id,
            start_datetime=payload.start_datetime,
            duration_hours=payload.duration_hours,
        )
        booking = await self.booking_repo.create_booking(
            field_id=payload.field_id,
            start_datetime=payload.start_datetime,
            duration_hours=payload.duration_hours,
            total_price=total_price,
            status=BookingStatus.PENDING.value,
            source=f"{BookingSource.MANAGER.value}:{manager_account.username}",
            account_id=payload.account_id,
            guest_name=payload.guest_name,
            guest_phone=payload.guest_phone,
            guest_email=payload.guest_email,
            internal_note=payload.internal_note,
            created_by_account_id=manager_account.id,
        )
        return BookingDetailOut.model_validate(booking)

    async def get_all_bookings(self, page: int | None = None, search: str | None = None) -> list[BotBookingRaw]:
        base_url = settings.BOT_URL
        if not base_url:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail=", BOT_URL is not configured.",
            )

        url = base_url.rstrip("/") + "/api/manager/bookings/all"

        params = {}
        if page is not None:
            params["page"] = page
        if search is not None:
            params["search"] = search

        headers = get_bot_service_headers()

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to fetch bookings from the bot service.",
                ) from exc

        payload = response.json()
        if isinstance(payload, dict):
            bookings = payload.get("data") or payload.get("bookings") or payload.get("results") or []
        else:
            bookings = payload

        data = [BotBookingRaw.model_validate(b) for b in bookings]
        return data

    async def get_all_booked_slots(self, page: int | None = None, search: str | None = None) -> list[BotBookedSlotOut]:
        bookings = await self.get_all_bookings(page=page, search=search)
        return [BotBookedSlotOut.model_validate(booking.model_dump()) for booking in bookings]

    async def get_bookings_in_range(
        self,
        start_date: str,
        end_date: str,
        field: int | None = None,
        page: int | None = None,
        search: str | None = None,
    ) -> list[BotBookingRaw]:
        base_url = settings.BOT_URL
        if not base_url:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail=", BOT_URL is not configured.",
            )
        url = base_url.rstrip("/") + f"/api/manager/bookings/range/{start_date}/{end_date}"

        params = {}
        if page is not None:
            params["page"] = page
        if field is not None:
            params["field"] = field
        if search is not None:
            params["search"] = search

        headers = get_bot_service_headers()

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to fetch bookings from the bot service.",
                ) from exc

        payload = response.json()
        if isinstance(payload, dict):
            bookings = payload.get("data") or payload.get("bookings") or payload.get("results") or []
        else:
            bookings = payload

        booking_data = [BotBookingRaw.model_validate(b) for b in bookings]
        return booking_data

    async def get_booked_slots_in_range(
        self,
        start_date: str,
        end_date: str,
        field: int | None = None,
        page: int | None = None,
        search: str | None = None,
    ) -> list[BotBookedSlotOut]:
        bookings = await self.get_bookings_in_range(
            start_date=start_date,
            end_date=end_date,
            field=field,
            page=page,
            search=search,
        )
        return [BotBookedSlotOut.model_validate(booking.model_dump()) for booking in bookings]

    async def get_public_availability(
        self, start_date: str, end_date: str, field: int | None = None
    ) -> list[PublicBookedSlotOut]:
        slots = await self.get_booked_slots_in_range(start_date=start_date, end_date=end_date, field=field)
        return [
            PublicBookedSlotOut(field=s.field, date=s.date, time_start=s.time_start, time_end=s.time_end)
            for s in slots
            if s.state in _SLOT_BLOCKING_STATES
        ]

    async def create_bookings_batch(
        self, payload: BookingBatchInCreate, current_user: Account | None
    ) -> tuple[int, typing.Any]:
        has_discount = payload.discount_id is not None or any(
            "discount_id" in slot.model_fields_set and slot.discount_id is not None for slot in payload.slots
        )
        if has_discount and (current_user is None or current_user.role not in _BOOKING_STAFF_ROLE_VALUES):
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_403_FORBIDDEN,
                detail="Only staff can assign discounts.",
            )

        base_url = settings.BOT_URL
        if not base_url:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="BOT_URL is not configured.",
            )
        url = base_url.rstrip("/") + "/api/manager/bookings/batch"

        # A bad prefill never blocks a booking: anything wrong with it degrades to a normal booking.
        prefill = None
        if payload.prefill_token and self.prefill_service is not None:
            try:
                prefill = await self.prefill_service.get_valid(payload.prefill_token)
            except Exception:
                loguru.logger.exception("Booking prefill lookup failed; continuing without it.")
            if prefill is None:
                loguru.logger.info("Booking batch carried an invalid, expired or used prefill token; ignoring it.")
            else:
                # Typed values win; the prefill only fills what the user left empty.
                if not payload.phone and prefill.phone:
                    payload.phone = prefill.phone
                if not payload.customer and prefill.customer_name:
                    payload.customer = prefill.customer_name

        if current_user is None:
            source_kind = BookingSource.BOT_LINK if prefill is not None else BookingSource.LANDING
            payload.source = f"{source_kind.value}:{payload.phone}"
        elif current_user.role in _BOOKING_STAFF_ROLE_VALUES:
            payload.source = current_user.email
        else:
            payload.source = f"{BookingSource.ACCOUNT.value}:{current_user.email}"

        # exclude_unset preserves an explicitly supplied per-slot null discount,
        # which overrides a top-level discount according to the bot contract.
        body = payload.model_dump(mode="json", exclude_unset=True)
        body["source"] = payload.source
        body.pop("updated_by", None)
        body.pop("prefill_token", None)
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    url,
                    headers=get_bot_service_headers(json=True),
                    json=body,
                )
            except httpx.HTTPError as exc:
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to reach the bot service.",
                ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="Bot service returned a non-JSON response.",
            ) from exc

        data = _normalize_entity_ids(data)
        if prefill is not None and response.is_success and isinstance(data, dict) and data.get("ok") is True:
            # The booking already exists in the bot, so a failure here must not fail the request.
            try:
                await self.prefill_service.mark_consumed(prefill.id, _extract_booking_ids(data))  # type: ignore[union-attr]
            except Exception:
                loguru.logger.exception(f"Could not mark booking prefill {prefill.id} consumed.")

        return response.status_code, data

    async def get_my_bookings(self, current_account: Account) -> list[BookingOut]:
        bookings = await self.booking_repo.read_bookings(account_id=current_account.id)
        return [BookingOut.model_validate(b) for b in bookings]

    async def get_booking_detail(self, booking_id: int) -> dict[str, typing.Any]:
        """Fetch a single enriched booking from the bot service.

        The bot's ``GET /api/manager/bookings/{id}`` returns the full booking row
        (schedule, customer, state, manual payment buckets) plus aggregated
        bot-payment info (``paid_api``, ``last_receipt_date``). The response is
        passed through as-is so no enriched field is silently dropped. Raises 404
        when the bot reports the booking does not exist.
        """
        base_url = settings.BOT_URL
        if not base_url:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="BOT_URL is not configured.",
            )
        url = base_url.rstrip("/") + f"/api/manager/bookings/{booking_id}"
        headers = get_bot_service_headers()

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers=headers)
            except httpx.HTTPError as exc:
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to reach the bot service.",
                ) from exc

        if response.status_code == fastapi.status.HTTP_404_NOT_FOUND:
            raise EntityDoesNotExist(f"Booking with id `{booking_id}` does not exist!")
        if response.status_code >= 400:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail=f"Bot service returned {response.status_code}: {response.text[:200]}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="Bot service returned a non-JSON response.",
            ) from exc

        if isinstance(payload, dict):
            if payload.get("ok") is False:
                raise EntityDoesNotExist(f"Booking with id `{booking_id}` does not exist!")
            data = payload.get("data")
            if data is None:
                raise EntityDoesNotExist(f"Booking with id `{booking_id}` does not exist!")
            return _normalize_entity_ids(data)
        return _normalize_entity_ids(payload)

    async def update_booking(
        self, booking_id: int, payload: BookingInUpdate, current_user: Account
    ) -> tuple[int, typing.Any]:
        if current_user is None or current_user.role not in _BOOKING_STAFF_ROLE_VALUES:
            raise fastapi.HTTPException(status_code=fastapi.status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

        base_url = settings.BOT_URL
        if not base_url:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="BOT_URL is not configured.",
            )
        url = base_url.rstrip("/") + f"/api/manager/bookings/{booking_id}"

        payload.source = current_user.email
        # Explicit null is meaningful for discount_id: it removes the current
        # discount and returns one use. Preserve explicitly supplied nulls.
        body = payload.model_dump(mode="json", exclude_unset=True)
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.patch(
                    url,
                    headers=get_bot_service_headers(json=True),
                    json=body,
                )
            except httpx.HTTPError as exc:
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to reach the bot service.",
                ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="Bot service returned a non-JSON response.",
            ) from exc

        return response.status_code, _normalize_entity_ids(data)

    async def change_booking_status(
        self, booking_id: int, payload: BookingStatusUpdate, current_account: Account
    ) -> BookingDetailOut:
        booking = await self.booking_repo.read_booking_by_id(id=booking_id)
        is_staff = current_account.role in _BOOKING_STAFF_ROLE_VALUES
        new_status = payload.status

        if new_status in (BookingStatus.CONFIRMED, BookingStatus.REJECTED):
            if not is_staff:
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_403_FORBIDDEN,
                    detail="Only staff can confirm or decline bookings.",
                )

        if new_status == BookingStatus.CANCELLED:
            if not is_staff:
                # CLIENT must own the booking
                if booking.account_id != current_account.id:
                    raise fastapi.HTTPException(status_code=fastapi.status.HTTP_403_FORBIDDEN, detail="Access denied")
                # 48h cancellation window
                now = datetime.datetime.now(tz=booking.start_datetime.tzinfo)
                delta = booking.start_datetime - now
                if delta.total_seconds() < 48 * 3600:
                    raise fastapi.HTTPException(
                        status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                        detail="Cancellation is only allowed more than 48 hours before the booking start.",
                    )

        updated = await self.booking_repo.update_booking_status(
            booking_id=booking_id,
            new_status=new_status.value,
            changed_by_account_id=current_account.id,
            comment=payload.comment,
        )
        return BookingDetailOut.model_validate(updated)


# Same states the bot's EXCLUDE constraint uses to reject overlaps (SLOT_TAKEN).
_SLOT_BLOCKING_STATES = {"awaiting_payment", "confirmed"}

_BOOKING_STAFF_ROLE_VALUES = {
    Role.SUPER_ADMIN.value,
    Role.ADMIN.value,
    Role.MANAGER.value,
    Role.ARENA_MANAGER.value,
}


def _extract_booking_ids(data: dict[str, typing.Any]) -> list[int] | None:
    """Best-effort ids of the bookings the bot created, whatever shape its batch envelope uses."""
    inner = data.get("data")
    if isinstance(inner, dict):
        inner = inner.get("bookings") or inner.get("ids") or inner.get("booking_ids") or inner.get("results")
    if not isinstance(inner, list):
        return None
    ids = []
    for item in inner:
        raw = item.get("id", item.get("booking_id")) if isinstance(item, dict) else item
        if isinstance(raw, int) and not isinstance(raw, bool):
            ids.append(raw)
    return ids or None


def _normalize_entity_ids(value: typing.Any) -> typing.Any:
    if isinstance(value, list):
        return [_normalize_entity_ids(item) for item in value]
    if isinstance(value, dict):
        return {
            key: (
                None
                if key in {"booking_id", "customer_id", "discount_id"} and item == ""
                else _normalize_entity_ids(item)
            )
            for key, item in value.items()
        }
    return value
