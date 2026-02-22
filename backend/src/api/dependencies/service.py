import fastapi

from src.api.dependencies.repository import get_repository
from src.repository.crud.account import AccountCRUDRepository
from src.services.account import AccountService


def get_account_service(
    account_repo: AccountCRUDRepository = fastapi.Depends(get_repository(repo_type=AccountCRUDRepository)),
) -> AccountService:
    return AccountService(account_repo=account_repo)
