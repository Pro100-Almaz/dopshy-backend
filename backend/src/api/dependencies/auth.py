import typing

import fastapi
from fastapi.security import OAuth2PasswordBearer

from src.api.dependencies.repository import get_repository
from src.models.db.account import Account
from src.models.enums.role import Role
from src.repository.crud.account import AccountCRUDRepository
from src.securities.authorizations.jwt import jwt_generator
from src.config.manager import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/signin")


async def get_current_user(
    token: str = fastapi.Depends(oauth2_scheme),
    account_repo: AccountCRUDRepository = fastapi.Depends(get_repository(repo_type=AccountCRUDRepository)),
) -> Account:
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
