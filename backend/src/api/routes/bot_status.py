import typing

import fastapi
import loguru

from src.api.dependencies.auth import require_roles
from src.api.dependencies.service import get_bot_status_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.models.schemas.bot_status import (
    BotEnabledStatus,
    BotEnabledStatusIn,
    BotStatusBatchIn,
    BotStatusToggleOut,
)
from src.services.bot_status import BotStatusService

router = fastapi.APIRouter(prefix="/bot-status", tags=["bot-status"])


@router.get(
    path="/enabled_status",
    name="bot-status:get-enabled-status",
    response_model=BotEnabledStatus,
    status_code=fastapi.status.HTTP_200_OK,
)
async def get_bot_enabled_status(
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    bot_status_service: BotStatusService = fastapi.Depends(get_bot_status_service),
) -> BotEnabledStatus:
    return await bot_status_service.get_bot_enabled_status()


@router.patch(
    path="/enabled_status",
    name="bot-status:set-enabled-status",
    response_model=BotEnabledStatus,
    status_code=fastapi.status.HTTP_200_OK,
)
async def patch_bot_enabled_status(
    payload: BotEnabledStatusIn,
    account: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    bot_status_service: BotStatusService = fastapi.Depends(get_bot_status_service),
) -> BotEnabledStatus:
    enabled_status = await bot_status_service.set_bot_enabled_status(enabled=payload.enabled)
    loguru.logger.info(
        f"Global bot switch set to is_enabled={enabled_status.is_enabled} by account "
        f"id={account.id} username={account.username}"
    )
    return enabled_status


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
    path="/contacts",
    name="bot-status:contacts",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_bot_contacts(
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    bot_status_service: BotStatusService = fastapi.Depends(get_bot_status_service),
) -> typing.Any:
    return await bot_status_service.list_contacts()


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
