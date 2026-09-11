import fastapi

from src.api.dependencies.auth import require_roles
from src.api.dependencies.service import get_account_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.models.schemas.account import AccountAdminCreate, AccountAdminUpdate, AccountInResponse
from src.services.account import AccountService
from src.utilities.exceptions.database import EntityAlreadyExists, EntityDoesNotExist
from src.utilities.exceptions.http.exc_404 import (
    http_404_exc_id_not_found_request,
)

router = fastapi.APIRouter(prefix="/accounts", tags=["accounts"])


@router.get(
    path="",
    name="accounts:read-accounts",
    response_model=list[AccountInResponse],
    status_code=fastapi.status.HTTP_200_OK,
)
async def get_accounts(
    _: Account = fastapi.Depends(require_roles(Role.SUPER_ADMIN)),
    account_service: AccountService = fastapi.Depends(get_account_service),
) -> list[AccountInResponse]:
    return await account_service.get_accounts()


@router.post(
    path="",
    name="accounts:create-account",
    response_model=AccountInResponse,
    status_code=fastapi.status.HTTP_201_CREATED,
)
async def create_account(
    account_create: AccountAdminCreate,
    _: Account = fastapi.Depends(require_roles(Role.SUPER_ADMIN)),
    account_service: AccountService = fastapi.Depends(get_account_service),
) -> AccountInResponse:
    try:
        return await account_service.create_account(account_create=account_create)
    except EntityAlreadyExists as exc:
        raise fastapi.HTTPException(status_code=fastapi.status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get(
    path="/{id}",
    name="accounts:read-account-by-id",
    response_model=AccountInResponse,
    status_code=fastapi.status.HTTP_200_OK,
)
async def get_account(
    id: int,
    _: Account = fastapi.Depends(require_roles(Role.SUPER_ADMIN)),
    account_service: AccountService = fastapi.Depends(get_account_service),
) -> AccountInResponse:
    try:
        return await account_service.get_account_by_id(id=id)
    except EntityDoesNotExist:
        raise await http_404_exc_id_not_found_request(id=id)


@router.patch(
    path="/{id}",
    name="accounts:update-account-by-id",
    response_model=AccountInResponse,
    status_code=fastapi.status.HTTP_200_OK,
)
async def update_account(
    id: int,
    account_update: AccountAdminUpdate,
    _: Account = fastapi.Depends(require_roles(Role.SUPER_ADMIN)),
    account_service: AccountService = fastapi.Depends(get_account_service),
) -> AccountInResponse:
    try:
        return await account_service.update_staff_account(id=id, account_update=account_update)
    except EntityDoesNotExist:
        raise await http_404_exc_id_not_found_request(id=id)
    except EntityAlreadyExists as exc:
        raise fastapi.HTTPException(status_code=fastapi.status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete(
    path="/{id}",
    name="accounts:delete-account-by-path-id",
    status_code=fastapi.status.HTTP_200_OK,
)
async def delete_account(
    id: int,
    _: Account = fastapi.Depends(require_roles(Role.SUPER_ADMIN)),
    account_service: AccountService = fastapi.Depends(get_account_service),
) -> dict[str, str]:
    try:
        return await account_service.delete_account(id=id)
    except EntityDoesNotExist:
        raise await http_404_exc_id_not_found_request(id=id)


@router.delete(
    path="",
    name="accounts:delete-account-by-query-id",
    status_code=fastapi.status.HTTP_200_OK,
)
async def delete_account_by_query_id(
    id: int,
    _: Account = fastapi.Depends(require_roles(Role.SUPER_ADMIN)),
    account_service: AccountService = fastapi.Depends(get_account_service),
) -> dict[str, str]:
    try:
        return await account_service.delete_account(id=id)
    except EntityDoesNotExist:
        raise await http_404_exc_id_not_found_request(id=id)
