import fastapi
import pytest
from fastapi.security import HTTPAuthorizationCredentials

from src.api.dependencies.auth import require_roles, require_roles_or_manager_api_key
from src.models.enums.role import Role
from src.securities.authorizations.jwt import jwt_generator


class FakeAccount:
    def __init__(self, role: str) -> None:
        self.role = role


class FakeAccountRepo:
    def __init__(self, account: FakeAccount | None) -> None:
        self.account = account

    async def read_account_by_email(self, email: str) -> FakeAccount | None:
        assert email == "admin@example.com"
        return self.account


def credentials() -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")


@pytest.mark.asyncio
async def test_require_roles_or_manager_api_key_accepts_manager_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANAGER_API_KEY", "secret")
    dependency = require_roles_or_manager_api_key(Role.ADMIN)

    result = await dependency(x_api_key="secret", credentials=None, account_repo=FakeAccountRepo(None))

    assert result is None


@pytest.mark.asyncio
async def test_require_roles_or_manager_api_key_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MANAGER_API_KEY", raising=False)
    dependency = require_roles_or_manager_api_key(Role.ADMIN)

    with pytest.raises(fastapi.HTTPException) as exc_info:
        await dependency(x_api_key=None, credentials=None, account_repo=FakeAccountRepo(None))

    assert exc_info.value.status_code == fastapi.status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_require_roles_or_manager_api_key_rejects_bad_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MANAGER_API_KEY", raising=False)
    monkeypatch.setattr(
        jwt_generator,
        "retrieve_details_from_token",
        lambda token, secret_key: (_ for _ in ()).throw(ValueError()),
    )
    dependency = require_roles_or_manager_api_key(Role.ADMIN)

    with pytest.raises(fastapi.HTTPException) as exc_info:
        await dependency(x_api_key=None, credentials=credentials(), account_repo=FakeAccountRepo(None))

    assert exc_info.value.status_code == fastapi.status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_require_roles_or_manager_api_key_rejects_missing_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MANAGER_API_KEY", raising=False)
    monkeypatch.setattr(jwt_generator, "retrieve_details_from_token", lambda token, secret_key: (1, "admin@example.com"))
    dependency = require_roles_or_manager_api_key(Role.ADMIN)

    with pytest.raises(fastapi.HTTPException) as exc_info:
        await dependency(x_api_key=None, credentials=credentials(), account_repo=FakeAccountRepo(None))

    assert exc_info.value.status_code == fastapi.status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_require_roles_or_manager_api_key_checks_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MANAGER_API_KEY", raising=False)
    monkeypatch.setattr(jwt_generator, "retrieve_details_from_token", lambda token, secret_key: (1, "admin@example.com"))
    dependency = require_roles_or_manager_api_key(Role.ADMIN)

    with pytest.raises(fastapi.HTTPException) as exc_info:
        await dependency(
            x_api_key=None,
            credentials=credentials(),
            account_repo=FakeAccountRepo(FakeAccount(Role.MANAGER.value)),
        )

    assert exc_info.value.status_code == fastapi.status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_require_roles_or_manager_api_key_returns_authorized_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MANAGER_API_KEY", raising=False)
    monkeypatch.setattr(jwt_generator, "retrieve_details_from_token", lambda token, secret_key: (1, "admin@example.com"))
    account = FakeAccount(Role.ADMIN.value)
    dependency = require_roles_or_manager_api_key(Role.ADMIN)

    result = await dependency(x_api_key=None, credentials=credentials(), account_repo=FakeAccountRepo(account))

    assert result is account


@pytest.mark.asyncio
async def test_require_roles_checks_current_user_role() -> None:
    dependency = require_roles(Role.ADMIN)

    assert await dependency(current_user=FakeAccount(Role.ADMIN.value)) is not None
    with pytest.raises(fastapi.HTTPException) as exc_info:
        await dependency(current_user=FakeAccount(Role.MANAGER.value))

    assert exc_info.value.status_code == fastapi.status.HTTP_403_FORBIDDEN
