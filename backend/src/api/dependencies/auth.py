import os
import typing

import fastapi
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.api.dependencies.repository import get_repository
from src.models.db.account import Account
from src.models.enums.role import Role
from src.repository.crud.account import AccountCRUDRepository
from src.securities.authorizations.jwt import jwt_generator
from src.config.manager import settings


bearer_scheme = HTTPBearer()
optional_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = fastapi.Depends(bearer_scheme),
    account_repo: AccountCRUDRepository = fastapi.Depends(get_repository(repo_type=AccountCRUDRepository)),
) -> Account:
    token = credentials.credentials
    try:
        details = jwt_generator.retrieve_details_from_token(token=token, secret_key=settings.JWT_SECRET_KEY)
        email = details[1]
    except ValueError:
        raise fastapi.HTTPException(status_code=fastapi.status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    account = await account_repo.read_account_by_email(email=email)
    if not account:
        raise fastapi.HTTPException(status_code=fastapi.status.HTTP_404_NOT_FOUND, detail="Account not found")

    return account  # type: ignore


def require_roles(*roles: Role) -> typing.Callable[..., typing.Awaitable[Account]]:
    async def _check_role(current_user: Account = fastapi.Depends(get_current_user)) -> Account:
        if current_user.role not in [r.value for r in roles]:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _check_role


def require_roles_or_manager_api_key(*roles: Role) -> typing.Callable[..., typing.Awaitable[Account | None]]:
    async def _check_role_or_key(
        x_api_key: str | None = fastapi.Header(default=None, alias="X-API-Key"),
        credentials: HTTPAuthorizationCredentials | None = fastapi.Depends(optional_bearer_scheme),
        account_repo: AccountCRUDRepository = fastapi.Depends(get_repository(repo_type=AccountCRUDRepository)),
    ) -> Account | None:
        expected_key = os.getenv("MANAGER_API_KEY") or settings.MANAGER_API_KEY or ""
        if expected_key and x_api_key == expected_key:
            return None

        if credentials is None:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
            )

        token = credentials.credentials
        try:
            details = jwt_generator.retrieve_details_from_token(token=token, secret_key=settings.JWT_SECRET_KEY)
            email = details[1]
        except ValueError:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        account = await account_repo.read_account_by_email(email=email)
        if not account:
            raise fastapi.HTTPException(status_code=fastapi.status.HTTP_404_NOT_FOUND, detail="Account not found")

        if account.role not in [r.value for r in roles]:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return account  # type: ignore

    return _check_role_or_key
