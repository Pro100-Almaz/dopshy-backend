import asyncio
import datetime
import hashlib
import secrets

import fastapi
import loguru

from src.config.manager import settings
from src.models.db.booking_prefill import BookingPrefill
from src.models.enums.booking import BookingSource
from src.models.schemas.prefill import (
    PrefillAlternativeOut,
    PrefillCreatedOut,
    PrefillCreateIn,
    PrefillOut,
    mask_phone,
    venue_now,
)
from src.repository.crud.booking_prefill import BookingPrefillCRUDRepository
from src.repository.database import async_db
from src.services.booking import BookingService

# The bot has no venue-hours endpoint; alternatives are offered inside this window, in whole hours.
_DAY_START_HOUR = 8
_DAY_END_HOUR = 24
_MAX_ALTERNATIVES = 5
_RETENTION = datetime.timedelta(days=30)
_CLEANUP_INTERVAL_SECONDS = 6 * 3600


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _hhmm(value: datetime.time | None) -> str | None:
    return value.strftime("%H:%M") if value is not None else None


class BookingPrefillService:
    def __init__(self, prefill_repo: BookingPrefillCRUDRepository) -> None:
        self.prefill_repo = prefill_repo

    async def create(self, payload: PrefillCreateIn) -> PrefillCreatedOut:
        if not settings.PLATFORM_BOOKING_URL:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_503_SERVICE_UNAVAILABLE, detail="Prefill API is not configured."
            )
        token = secrets.token_urlsafe(24)
        expires_at = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(
            hours=settings.PREFILL_TTL_HOURS
        )
        prefill = await self.prefill_repo.create(
            token_hash=hash_token(token),
            phone=payload.phone,
            customer_name=payload.customer_name,
            field_id=payload.field,
            date=payload.date,
            time_start=payload.time_start,
            time_end=payload.time_end,
            players=payload.players,
            lang=payload.lang,
            source=BookingSource.BOT_LINK.value,
            conversation_id=payload.conversation_id,
            expires_at=expires_at,
        )
        loguru.logger.info(f"Booking prefill {prefill.id} created.")
        return PrefillCreatedOut(
            token=token,
            url=f"{settings.PLATFORM_BOOKING_URL}?p={token}#booking",
            expires_at=expires_at,
        )

    async def get_valid(self, token: str) -> BookingPrefill | None:
        """The prefill for an unexpired, unconsumed token, else None."""
        prefill = await self.prefill_repo.read_by_hash(hash_token(token))
        if prefill is None or prefill.consumed_at is not None:
            return None
        if prefill.expires_at <= datetime.datetime.now(tz=datetime.timezone.utc):
            return None
        return prefill

    async def resolve(self, token: str, booking_service: BookingService) -> PrefillOut:
        prefill = await self.prefill_repo.read_by_hash(hash_token(token))
        if prefill is None or prefill.expires_at <= datetime.datetime.now(tz=datetime.timezone.utc):
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_404_NOT_FOUND, detail="Prefill not found or expired."
            )
        if prefill.consumed_at is not None:
            raise fastapi.HTTPException(status_code=fastapi.status.HTTP_410_GONE, detail="Prefill already used.")

        if prefill.first_opened_at is None:
            await self.prefill_repo.mark_opened(prefill.id, datetime.datetime.now(tz=datetime.timezone.utc))

        slot_available: bool | None = None
        alternatives: list[PrefillAlternativeOut] = []
        if (
            prefill.date is not None
            and prefill.time_start is not None
            and prefill.time_end is not None
            and prefill.field_id is not None
        ):
            try:
                busy = await booking_service.get_public_availability(
                    start_date=prefill.date.isoformat(), end_date=prefill.date.isoformat(), field=prefill.field_id
                )
            except fastapi.HTTPException:
                busy = None  # bot unreachable: still prefill the form
            if busy is not None:
                intervals = [
                    (b.time_start, b.time_end)
                    for b in busy
                    if b.time_start is not None and b.time_end is not None and b.field in (None, prefill.field_id)
                ]
                slot_available = not _overlaps(prefill.time_start, prefill.time_end, intervals)
                if not slot_available:
                    alternatives = _free_slots(prefill.date, prefill.time_start, prefill.time_end, intervals)

        return PrefillOut(
            phone_masked=mask_phone(prefill.phone),
            customer_name=prefill.customer_name,
            field=prefill.field_id,
            date=prefill.date,
            time_start=_hhmm(prefill.time_start),
            time_end=_hhmm(prefill.time_end),
            players=prefill.players,
            lang=prefill.lang,
            slot_available=slot_available,
            alternatives=alternatives,
        )

    async def mark_consumed(self, prefill_id: int, booking_ids: list[int] | None) -> None:
        await self.prefill_repo.mark_consumed(prefill_id, booking_ids, datetime.datetime.now(tz=datetime.timezone.utc))


def _overlaps(
    start: datetime.time, end: datetime.time, intervals: list[tuple[datetime.time, datetime.time]]
) -> bool:
    return any(start < b_end and b_start < end for b_start, b_end in intervals)


def _free_slots(
    day: datetime.date,
    start: datetime.time,
    end: datetime.time,
    intervals: list[tuple[datetime.time, datetime.time]],
) -> list[PrefillAlternativeOut]:
    """Up to 5 free whole-hour slots of the requested length on that day, nearest to the requested start first."""
    length = max(1, -(-((end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)) // 60))
    now = venue_now()
    candidates: list[tuple[int, int]] = []
    for hour in range(_DAY_START_HOUR, _DAY_END_HOUR - length + 1):
        slot_start = datetime.time(hour)
        slot_end = datetime.time(hour + length) if hour + length < 24 else datetime.time.max
        if day == now.date() and slot_start <= now.time():
            continue
        if _overlaps(slot_start, slot_end, intervals):
            continue
        candidates.append((abs(hour * 60 - (start.hour * 60 + start.minute)), hour))
    chosen = sorted(sorted(candidates)[:_MAX_ALTERNATIVES], key=lambda c: c[1])
    return [
        PrefillAlternativeOut(
            time_start=f"{hour:02d}:00",
            time_end="24:00" if hour + length >= 24 else f"{hour + length:02d}:00",
        )
        for _, hour in chosen
    ]


async def run_prefill_cleanup_loop() -> None:
    """Periodically delete stale prefills and scrub PII from old consumed ones."""
    while True:
        try:
            async with async_db.async_sessionmaker() as session:
                deleted, scrubbed = await BookingPrefillCRUDRepository(session).cleanup(
                    now=datetime.datetime.now(tz=datetime.timezone.utc), retention=_RETENTION
                )
            loguru.logger.info(f"Booking prefill cleanup: {deleted} deleted, {scrubbed} scrubbed.")
        except asyncio.CancelledError:
            raise
        except Exception:
            loguru.logger.exception("Booking prefill cleanup failed.")
        await asyncio.sleep(_CLEANUP_INTERVAL_SECONDS)
