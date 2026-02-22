import fastapi
import pydantic

from src.api.dependencies.service import get_account_service
from src.models.schemas.account import AccountInResponse, AccountInUpdate
from src.services.account import AccountService
from src.utilities.exceptions.database import EntityDoesNotExist
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
    account_service: AccountService = fastapi.Depends(get_account_service),
) -> list[AccountInResponse]:
    return await account_service.get_accounts()


@router.get(
    path="/{id}",
    name="accounts:read-account-by-id",
    response_model=AccountInResponse,
    status_code=fastapi.status.HTTP_200_OK,
)
async def get_account(
    id: int,
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
    query_id: int,
    update_username: str | None = None,
    update_email: pydantic.EmailStr | None = None,
    update_password: str | None = None,
    account_service: AccountService = fastapi.Depends(get_account_service),
) -> AccountInResponse:
    account_update = AccountInUpdate(username=update_username, email=update_email, password=update_password)
    try:
        return await account_service.update_account(id=query_id, account_update=account_update)
    except EntityDoesNotExist:
        raise await http_404_exc_id_not_found_request(id=query_id)


@router.delete(
    path="",
    name="accounts:delete-account-by-id",
    status_code=fastapi.status.HTTP_200_OK,
)
async def delete_account(
    id: int,
    account_service: AccountService = fastapi.Depends(get_account_service),
) -> dict[str, str]:
    try:
        return await account_service.delete_account(id=id)
    except EntityDoesNotExist:
        raise await http_404_exc_id_not_found_request(id=id)
