import typing

import fastapi

from src.api.dependencies.auth import require_roles_or_manager_api_key
from src.api.dependencies.service import get_contract_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.services.contract import ContractService

router = fastapi.APIRouter(prefix="/manager/contracts", tags=["manager-contracts"])


@router.get(
    path="",
    name="manager-contracts:list",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_contracts(
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
    page: int | None = fastapi.Query(default=None),
    search: str | None = fastapi.Query(default=None),
) -> fastapi.responses.JSONResponse:
    if page is not None and page < 1:
        return fastapi.responses.JSONResponse(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            content={"ok": False, "code": "INVALID", "message": "page must be greater than or equal to 1"},
        )

    status_code, payload = await contract_service.list_contracts(page=page, search=search)
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


@router.get(
    path="/{contract_id}",
    name="manager-contracts:get",
    status_code=fastapi.status.HTTP_200_OK,
)
async def get_contract(
    contract_id: int,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, payload = await contract_service.get_contract(contract_id=contract_id)
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


@router.post(
    path="",
    name="manager-contracts:create",
    status_code=fastapi.status.HTTP_200_OK,
)
async def create_contract(
    payload: dict[str, typing.Any],
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await contract_service.create_contract(payload=payload)
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.patch(
    path="/{contract_id}",
    name="manager-contracts:update",
    status_code=fastapi.status.HTTP_200_OK,
)
async def update_contract(
    contract_id: int,
    payload: dict[str, typing.Any],
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await contract_service.update_contract(
        contract_id=contract_id,
        payload=payload,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.delete(
    path="/{contract_id}",
    name="manager-contracts:delete",
    status_code=fastapi.status.HTTP_200_OK,
)
async def delete_contract(
    contract_id: int,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, payload = await contract_service.delete_contract(contract_id=contract_id)
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


@router.post(
    path="/{contract_id}/bookings/batch",
    name="manager-contracts:create-bookings-batch",
    status_code=fastapi.status.HTTP_200_OK,
)
async def create_contract_bookings_batch(
    contract_id: int,
    payload: dict[str, typing.Any],
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await contract_service.create_contract_bookings(
        contract_id=contract_id,
        payload=payload,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.patch(
    path="/{contract_id}/bookings/batch",
    name="manager-contracts:update-bookings-batch",
    status_code=fastapi.status.HTTP_200_OK,
)
async def update_contract_bookings_batch(
    contract_id: int,
    payload: dict[str, typing.Any],
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await contract_service.update_contract_bookings(
        contract_id=contract_id,
        payload=payload,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.delete(
    path="/{contract_id}/bookings/batch",
    name="manager-contracts:delete-bookings-batch",
    status_code=fastapi.status.HTTP_200_OK,
)
async def delete_contract_bookings_batch(
    contract_id: int,
    payload: dict[str, typing.Any] | None = None,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await contract_service.delete_contract_bookings(
        contract_id=contract_id,
        payload=payload or {},
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)
