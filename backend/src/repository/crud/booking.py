import typing

import sqlalchemy
from sqlalchemy.orm import selectinload

from src.models.db.booking import Booking, BookingStatusHistory
from src.models.enums.booking import BookingStatus
from src.repository.crud.base import BaseCRUDRepository
from src.utilities.exceptions.database import EntityDoesNotExist


class BookingCRUDRepository(BaseCRUDRepository):
    async def create_booking(
        self,
        field_id: int,
        start_datetime: typing.Any,
        duration_hours: int,
        total_price: typing.Any,
        status: str,
        source: str,
        account_id: int | None = None,
        guest_name: str | None = None,
        guest_phone: str | None = None,
        guest_email: str | None = None,
        internal_note: str | None = None,
        created_by_account_id: int | None = None,
    ) -> Booking:
        new_booking = Booking(
            field_id=field_id,
            account_id=account_id,
            guest_name=guest_name,
            guest_phone=guest_phone,
            guest_email=guest_email,
            start_datetime=start_datetime,
            duration_hours=duration_hours,
            total_price=total_price,
            status=status,
            source=source,
            internal_note=internal_note,
        )
        self.async_session.add(new_booking)
        await self.async_session.flush()

        initial_history = BookingStatusHistory(
            booking_id=new_booking.id,
            old_status=None,
            new_status=BookingStatus.PENDING.value,
            changed_by_account_id=created_by_account_id,
            comment=None,
        )
        self.async_session.add(initial_history)
        await self.async_session.commit()
        await self.async_session.refresh(new_booking)

        return await self.read_booking_by_id(id=new_booking.id)

    async def read_bookings(
        self,
        account_id: int | None = None,
        status: str | None = None,
    ) -> typing.Sequence[Booking]:
        stmt = (
            sqlalchemy.select(Booking)
            .options(selectinload(Booking.status_history))
            .order_by(Booking.start_datetime.desc())
        )
        if account_id is not None:
            stmt = stmt.where(Booking.account_id == account_id)
        if status is not None:
            stmt = stmt.where(Booking.status == status)
        result = await self.async_session.execute(stmt)
        return result.scalars().all()

    async def read_booking_by_id(self, id: int) -> Booking:
        stmt = (
            sqlalchemy.select(Booking)
            .where(Booking.id == id)
            .options(selectinload(Booking.status_history))
        )
        result = await self.async_session.execute(stmt)
        booking = result.scalar_one_or_none()
        if not booking:
            raise EntityDoesNotExist(f"Booking with id `{id}` does not exist!")
        return booking

    async def update_booking_status(
        self,
        booking_id: int,
        new_status: str,
        changed_by_account_id: int | None,
        comment: str | None,
    ) -> Booking:
        booking = await self.read_booking_by_id(id=booking_id)
        old_status = booking.status

        update_stmt = (
            sqlalchemy.update(Booking)
            .where(Booking.id == booking_id)
            .values(status=new_status)
        )
        await self.async_session.execute(update_stmt)

        history_entry = BookingStatusHistory(
            booking_id=booking_id,
            old_status=old_status,
            new_status=new_status,
            changed_by_account_id=changed_by_account_id,
            comment=comment,
        )
        self.async_session.add(history_entry)
        await self.async_session.commit()

        return await self.read_booking_by_id(id=booking_id)
