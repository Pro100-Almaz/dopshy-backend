import typing

import fastapi

from src.api.dependencies.auth import require_roles
from src.api.dependencies.service import get_history_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.services.history import HistoryService

router = fastapi.APIRouter(prefix="/manager", tags=["manager-history"])


@router.get(
    path="/history",
    name="manager-history:list",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_history(
    source: str | None = fastapi.Query(default=None, description="Filter by exact source, e.g. whatsapp or manager:a1b2c3"),
    channel: str | None = fastapi.Query(default=None, description="Filter by channel: whatsapp or manager"),
    page: int | None = fastapi.Query(default=None, ge=1),
    page_size: int | None = fastapi.Query(default=None, ge=1, le=100),
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    history_service: HistoryService = fastapi.Depends(get_history_service),
) -> typing.Any:
    return await history_service.list_history(
        source=source, channel=channel, page=page, page_size=page_size
    )


@router.get(
    path="/history/range/{start_date}/{end_date}",
    name="manager-history:range",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_history_by_range(
    start_date: str,
    end_date: str,
    page: int | None = fastapi.Query(default=None, ge=1),
    page_size: int | None = fastapi.Query(default=None, ge=1, le=100),
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    history_service: HistoryService = fastapi.Depends(get_history_service),
) -> typing.Any:
    return await history_service.list_history_by_range(
        start_date=start_date, end_date=end_date, page=page, page_size=page_size
    )


@router.get(
    path="/history/source/{source}",
    name="manager-history:source",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_history_by_source(
    source: str,
    page: int | None = fastapi.Query(default=None, ge=1),
    page_size: int | None = fastapi.Query(default=None, ge=1, le=100),
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    history_service: HistoryService = fastapi.Depends(get_history_service),
) -> typing.Any:
    return await history_service.list_history_by_source(
        source=source, page=page, page_size=page_size
    )


@router.get(
    path="/bookings/{booking_id}/history",
    name="manager-history:booking",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_booking_history(
    booking_id: int,
    page: int | None = fastapi.Query(default=None, ge=1),
    page_size: int | None = fastapi.Query(default=None, ge=1, le=100),
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    history_service: HistoryService = fastapi.Depends(get_history_service),
) -> typing.Any:
    return await history_service.list_booking_history(
        booking_id=booking_id, page=page, page_size=page_size
    )
