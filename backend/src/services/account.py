from src.models.db.account import Account
from src.models.schemas.account import (
    AccountInCreate,
    AccountInLogin,
    AccountInResponse,
    AccountInUpdate,
    AccountWithToken,
)
from src.repository.crud.account import AccountCRUDRepository
from src.securities.authorizations.jwt import jwt_generator


class AccountService:
    def __init__(self, account_repo: AccountCRUDRepository) -> None:
        self.account_repo = account_repo

    def _build_response(self, account: Account) -> AccountInResponse:
        token = jwt_generator.generate_access_token(account=account)
        return AccountInResponse(
            id=account.id,
            authorized_account=AccountWithToken(
                token=token,
                username=account.username,
                email=account.email,  # type: ignore
                is_verified=account.is_verified,
                is_active=account.is_active,
                is_logged_in=account.is_logged_in,
                created_at=account.created_at,
                updated_at=account.updated_at,
            ),
        )

    async def signup(self, account_create: AccountInCreate) -> AccountInResponse:
        await self.account_repo.is_username_taken(username=account_create.username)
        await self.account_repo.is_email_taken(email=account_create.email)
        new_account = await self.account_repo.create_account(account_create=account_create)
        return self._build_response(account=new_account)

    async def signin(self, account_login: AccountInLogin) -> AccountInResponse:
        db_account = await self.account_repo.read_user_by_password_authentication(account_login=account_login)
        return self._build_response(account=db_account)

    async def get_accounts(self) -> list[AccountInResponse]:
        db_accounts = await self.account_repo.read_accounts()
        return [self._build_response(account=account) for account in db_accounts]

    async def get_account_by_id(self, id: int) -> AccountInResponse:
        db_account = await self.account_repo.read_account_by_id(id=id)
        return self._build_response(account=db_account)

    async def update_account(self, id: int, account_update: AccountInUpdate) -> AccountInResponse:
        updated_account = await self.account_repo.update_account_by_id(id=id, account_update=account_update)
        return self._build_response(account=updated_account)

    async def delete_account(self, id: int) -> dict[str, str]:
        result = await self.account_repo.delete_account_by_id(id=id)
        return {"notification": result}
