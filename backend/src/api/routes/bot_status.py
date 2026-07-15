import typing

import fastapi

from src.api.dependencies.auth import require_roles
from src.api.dependencies.service import get_bot_status_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.models.schemas.bot_status import BotStatusBatchIn, BotStatusToggleOut
from src.services.bot_status import BotStatusService

router = fastapi.APIRouter(prefix="/bot-status", tags=["bot-status"])


@router.post(
    path="/batch",
    name="bot-status:batch",
    status_code=fastapi.status.HTTP_200_OK,
)
async def batch_bot_status(
    payload: BotStatusBatchIn,
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    bot_status_service: BotStatusService = fastapi.Depends(get_bot_status_service),
) -> typing.Any:
    return await bot_status_service.batch_status(payload=payload)


@router.get(
    path="/{phone}",
    name="bot-status:get",
    status_code=fastapi.status.HTTP_200_OK,
)
async def get_bot_status(
    phone: str,
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    bot_status_service: BotStatusService = fastapi.Depends(get_bot_status_service),
) -> typing.Any:
    return await bot_status_service.get_status(phone=phone)


@router.post(
    path="/{phone}/pause",
    name="bot-status:pause",
    response_model=BotStatusToggleOut,
    status_code=fastapi.status.HTTP_200_OK,
)
async def pause_bot_status(
    phone: str,
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    bot_status_service: BotStatusService = fastapi.Depends(get_bot_status_service),
) -> BotStatusToggleOut:
    return await bot_status_service.pause(phone=phone)


@router.post(
    path="/{phone}/resume",
    name="bot-status:resume",
    response_model=BotStatusToggleOut,
    status_code=fastapi.status.HTTP_200_OK,
)
async def resume_bot_status(
    phone: str,
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    bot_status_service: BotStatusService = fastapi.Depends(get_bot_status_service),
) -> BotStatusToggleOut:
    return await bot_status_service.resume(phone=phone)
