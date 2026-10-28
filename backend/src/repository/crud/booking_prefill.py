import datetime
import typing

import sqlalchemy

from src.models.db.booking_prefill import BookingPrefill
from src.repository.crud.base import BaseCRUDRepository


class BookingPrefillCRUDRepository(BaseCRUDRepository):
    async def create(self, **values: typing.Any) -> BookingPrefill:
        prefill = BookingPrefill(**values)
        self.async_session.add(prefill)
        await self.async_session.commit()
        await self.async_session.refresh(prefill)
        return prefill

    async def read_by_hash(self, token_hash: str) -> BookingPrefill | None:
        result = await self.async_session.execute(
            sqlalchemy.select(BookingPrefill).where(BookingPrefill.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def mark_opened(self, prefill_id: int, now: datetime.datetime) -> None:
        await self.async_session.execute(
            sqlalchemy.update(BookingPrefill)
            .where(BookingPrefill.id == prefill_id, BookingPrefill.first_opened_at.is_(None))
            .values(first_opened_at=now)
        )
        await self.async_session.commit()

    async def mark_consumed(self, prefill_id: int, booking_ids: list[int] | None, now: datetime.datetime) -> bool:
        """Atomic: only the first caller wins; returns False when it was already consumed."""
        result = await self.async_session.execute(
            sqlalchemy.update(BookingPrefill)
            .where(BookingPrefill.id == prefill_id, BookingPrefill.consumed_at.is_(None))
            .values(consumed_at=now, bot_booking_ids=booking_ids)
        )
        await self.async_session.commit()
        return result.rowcount > 0

    async def cleanup(self, now: datetime.datetime, retention: datetime.timedelta) -> tuple[int, int]:
        """Delete unused prefills `retention` after expiry; scrub PII of consumed ones, keeping the row."""
        cutoff = now - retention
        deleted = await self.async_session.execute(
            sqlalchemy.delete(BookingPrefill).where(
                BookingPrefill.consumed_at.is_(None), BookingPrefill.expires_at < cutoff
            )
        )
        scrubbed = await self.async_session.execute(
            sqlalchemy.update(BookingPrefill)
            .where(
                BookingPrefill.consumed_at.is_not(None),
                BookingPrefill.consumed_at < cutoff,
                sqlalchemy.or_(
                    BookingPrefill.phone.is_not(None),
                    BookingPrefill.customer_name.is_not(None),
                    BookingPrefill.conversation_id.is_not(None),
                ),
            )
            .values(phone=None, customer_name=None, conversation_id=None)
        )
        await self.async_session.commit()
        return deleted.rowcount, scrubbed.rowcount
