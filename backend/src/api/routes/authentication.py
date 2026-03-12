import fastapi
import loguru

from src.api.dependencies.auth import require_roles
from src.api.dependencies.service import get_account_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.models.schemas.account import (
    AccountInCreate,
    AccountInLogin,
    AccountInResponse,
    AccountResendVerification,
    AccountRoleUpdate,
    AccountVerifyCode,
)
from src.services.account import AccountService
from src.utilities.exceptions.database import EntityAlreadyExists, EntityDoesNotExist
from src.utilities.exceptions.http.exc_400 import (
    http_exc_400_credentials_bad_signin_request,
    http_exc_400_credentials_bad_signup_request,
    http_400_exc_bad_verification_code_request,
)
from src.utilities.exceptions.http.exc_404 import http_404_exc_id_not_found_request

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
    status_code=fastapi.status.HTTP_200_OK,
)
async def signin(
    account_login: AccountInLogin,
    account_service: AccountService = fastapi.Depends(get_account_service),
) -> AccountInResponse:
    try:
        return await account_service.signin(account_login=account_login)
    except Exception as e:
        loguru.logger.error(f"Signin failed: {type(e).__name__}: {e}")
        raise await http_exc_400_credentials_bad_signin_request()


@router.post(
    path="/verify",
    name="auth:verify",
    status_code=fastapi.status.HTTP_200_OK,
)
async def verify(
    payload: AccountVerifyCode,
    account_service: AccountService = fastapi.Depends(get_account_service),
) -> dict[str, str]:
    try:
        return await account_service.verify_code(payload=payload)
    except (ValueError, EntityDoesNotExist):
        raise await http_400_exc_bad_verification_code_request()


@router.post(
    path="/resend-verification",
    name="auth:resend-verification",
    status_code=fastapi.status.HTTP_200_OK,
)
async def resend_verification(
    body: AccountResendVerification,
    account_service: AccountService = fastapi.Depends(get_account_service),
) -> dict[str, str]:
    try:
        return await account_service.send_verification_email(email=body.email)
    except EntityDoesNotExist:
        raise await http_400_exc_bad_verification_code_request()


@router.post(
    path="/assign-role",
    name="auth:assign-role",
    response_model=AccountInResponse,
    status_code=fastapi.status.HTTP_200_OK,
)
async def assign_role(
    body: AccountRoleUpdate,
    _: Account = fastapi.Depends(require_roles(Role.ADMIN)),
    account_service: AccountService = fastapi.Depends(get_account_service),
) -> AccountInResponse:
    try:
        return await account_service.assign_role(payload=body)
    except EntityDoesNotExist:
        raise await http_404_exc_id_not_found_request(id=body.account_id)
