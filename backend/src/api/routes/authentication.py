import fastapi

from src.api.dependencies.service import get_account_service
from src.models.schemas.account import AccountInCreate, AccountInLogin, AccountInResponse
from src.services.account import AccountService
from src.utilities.exceptions.database import EntityAlreadyExists
from src.utilities.exceptions.http.exc_400 import (
    http_exc_400_credentials_bad_signin_request,
    http_exc_400_credentials_bad_signup_request,
)

router = fastapi.APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/signup",
    name="auth:signup",
    response_model=AccountInResponse,
    status_code=fastapi.status.HTTP_201_CREATED,
)
async def signup(
    account_create: AccountInCreate,
    account_service: AccountService = fastapi.Depends(get_account_service),
) -> AccountInResponse:
    try:
        return await account_service.signup(account_create=account_create)
    except EntityAlreadyExists:
        raise await http_exc_400_credentials_bad_signup_request()


@router.post(
    path="/signin",
    name="auth:signin",
    response_model=AccountInResponse,
    status_code=fastapi.status.HTTP_202_ACCEPTED,
)
async def signin(
    account_login: AccountInLogin,
    account_service: AccountService = fastapi.Depends(get_account_service),
) -> AccountInResponse:
    try:
        return await account_service.signin(account_login=account_login)
    except Exception:
        raise await http_exc_400_credentials_bad_signin_request()
