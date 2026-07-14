import datetime
import os
import typing

import fastapi
import httpx

from src.config.manager import settings
from src.models.db.account import Account
from src.models.enums.booking import BookingSource, BookingStatus
from src.models.enums.role import Role
from src.models.schemas.booking import (
    BookingBatchInCreate,
    BookingDetailOut,
    BookingInCreate,
    BookingInCreateAuthenticated,
    BookingInCreateByManager,
    BookingOut,
    BookingStatusUpdate,
    BotBookingRaw,
)
from src.repository.crud.booking import BookingCRUDRepository
from src.repository.crud.field import FieldCRUDRepository


class BookingService:
    def __init__(self, booking_repo: BookingCRUDRepository, field_repo: FieldCRUDRepository) -> None:
        self.booking_repo = booking_repo
        self.field_repo = field_repo

    async def _compute_total_price(self, field_id: int, start_datetime: datetime.datetime, duration_hours: int) -> float:
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
            source=payload.source.value,
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
            source=BookingSource.ACCOUNT.value,
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
            source=BookingSource.MANAGER.value,
            account_id=payload.account_id,
            guest_name=payload.guest_name,
            guest_phone=payload.guest_phone,
            guest_email=payload.guest_email,
            internal_note=payload.internal_note,
            created_by_account_id=manager_account.id,
        )
        return BookingDetailOut.model_validate(booking)

    async def get_all_bookings(self) -> list[BotBookingRaw] | None:
        base_url = settings.BOT_URL
        if not base_url:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail=", BOT_URL is not configured.",
            )

        url = base_url.rstrip("/") + "/api/manager/bookings/all"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers={"Content-Type": "application/json", "Accept": "application/json", "X-API-KEY": os.getenv("MANAGER_API_KEY") or ""})
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

    async def get_bookings_in_range(
        self, start_date: str, end_date: str, field: int
    ) -> list[BotBookingRaw] | None:
        base_url = settings.BOT_URL
        if not base_url:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail=", BOT_URL is not configured.",
            )
        url = base_url.rstrip("/") + f"/api/manager/bookings/range/{start_date}/{end_date}/{field}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers={"Content-Type": "application/json", "Accept": "application/json", "X-API-KEY": os.getenv("MANAGER_API_KEY") or ""})
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise fastapi.HTTPException(status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to fetch bookings from the bot service.",
                ) from exc

        payload = response.json()
        if isinstance(payload, dict):
            bookings = (
                payload.get("date")
                or payload.get("data")
                or payload.get("bookings")
                or payload.get("results")
                or []
            )
        else:
            bookings = payload

        booking_data = [BotBookingRaw.model_validate(b) for b in bookings]
        return booking_data

    async def create_bookings_batch(self, payload: BookingBatchInCreate) -> tuple[int, typing.Any]:
        base_url = settings.BOT_URL
        if not base_url:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="BOT_URL is not configured.",
            )
        url = base_url.rstrip("/") + "/api/manager/bookings/batch"

        body = payload.model_dump(mode="json", exclude_none=True)
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "X-API-KEY": os.getenv("MANAGER_API_KEY") or "",
                    },
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

        return response.status_code, data


    async def get_my_bookings(self, current_account: Account) -> list[BookingOut]:
        bookings = await self.booking_repo.read_bookings(account_id=current_account.id)
        return [BookingOut.model_validate(b) for b in bookings]

    async def get_booking_detail(self, booking_id: int, current_account: Account) -> BookingDetailOut:
        booking = await self.booking_repo.read_booking_by_id(id=booking_id)
        is_staff = current_account.role in (Role.ADMIN.value, Role.MANAGER.value)
        if not is_staff and booking.account_id != current_account.id:
            raise fastapi.HTTPException(status_code=fastapi.status.HTTP_403_FORBIDDEN, detail="Access denied")
        return BookingDetailOut.model_validate(booking)

    async def change_booking_status(
        self, booking_id: int, payload: BookingStatusUpdate, current_account: Account
    ) -> BookingDetailOut:
        booking = await self.booking_repo.read_booking_by_id(id=booking_id)
        is_staff = current_account.role in (Role.ADMIN.value, Role.MANAGER.value)
        new_status = payload.status

        if new_status in (BookingStatus.CONFIRMED, BookingStatus.DECLINED):
            if not is_staff:
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_403_FORBIDDEN,
                    detail="Only staff can confirm or decline bookings.",
                )

        if new_status == BookingStatus.CANCELLED:
            if not is_staff:
                # CLIENT must own the booking
                if booking.account_id != current_account.id:
                    raise fastapi.HTTPException(
                        status_code=fastapi.status.HTTP_403_FORBIDDEN, detail="Access denied"
                    )
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
