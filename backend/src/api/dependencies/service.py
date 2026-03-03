import fastapi

from src.api.dependencies.repository import get_repository
from src.repository.crud.account import AccountCRUDRepository
from src.repository.crud.booking import BookingCRUDRepository
from src.repository.crud.field import FieldCRUDRepository
from src.services.account import AccountService
from src.services.booking import BookingService
from src.services.field import FieldService


def get_account_service(
    account_repo: AccountCRUDRepository = fastapi.Depends(get_repository(repo_type=AccountCRUDRepository)),
) -> AccountService:
    return AccountService(account_repo=account_repo)


def get_field_service(
    field_repo: FieldCRUDRepository = fastapi.Depends(get_repository(repo_type=FieldCRUDRepository)),
) -> FieldService:
    return FieldService(field_repo=field_repo)


def get_booking_service(
    booking_repo: BookingCRUDRepository = fastapi.Depends(get_repository(repo_type=BookingCRUDRepository)),
    field_repo: FieldCRUDRepository = fastapi.Depends(get_repository(repo_type=FieldCRUDRepository)),
) -> BookingService:
    return BookingService(booking_repo=booking_repo, field_repo=field_repo)
