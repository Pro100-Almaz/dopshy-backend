import fastapi

from src.api.dependencies.auth import get_current_user, require_roles
from src.api.dependencies.service import get_booking_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.models.schemas.booking import (
    BookingDetailOut,
    BookingInCreate,
    BookingInCreateAuthenticated,
    BookingInCreateByManager,
    BookingOut,
    BookingStatusUpdate,
)
from src.services.booking import BookingService
from src.utilities.exceptions.database import EntityDoesNotExist
from src.utilities.exceptions.http.exc_404 import http_404_exc_booking_not_found_request, http_404_exc_field_not_found_request

router = fastapi.APIRouter(prefix="/bookings", tags=["bookings"])


@router.post(
    path="/anonymous",
    name="bookings:create-anonymous",
    response_model=BookingDetailOut,
    status_code=fastapi.status.HTTP_201_CREATED,
)
async def create_anonymous_booking(
    payload: BookingInCreate,
    booking_service: BookingService = fastapi.Depends(get_booking_service),
) -> BookingDetailOut:
    try:
        return await booking_service.create_anonymous_booking(payload=payload)
    except EntityDoesNotExist:
        raise await http_404_exc_field_not_found_request(id=payload.field_id)


@router.post(
    path="/my",
    name="bookings:create-authenticated",
    response_model=BookingDetailOut,
    status_code=fastapi.status.HTTP_201_CREATED,
)
async def create_authenticated_booking(
    payload: BookingInCreateAuthenticated,
    current_user: Account = fastapi.Depends(get_current_user),
    booking_service: BookingService = fastapi.Depends(get_booking_service),
) -> BookingDetailOut:
    try:
        return await booking_service.create_authenticated_booking(payload=payload, current_account=current_user)
    except EntityDoesNotExist:
        raise await http_404_exc_field_not_found_request(id=payload.field_id)


@router.post(
    path="/staff",
    name="bookings:create-by-manager",
    response_model=BookingDetailOut,
    status_code=fastapi.status.HTTP_201_CREATED,
)
async def create_manager_booking(
    payload: BookingInCreateByManager,
    current_user: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    booking_service: BookingService = fastapi.Depends(get_booking_service),
) -> BookingDetailOut:
    try:
        return await booking_service.create_manager_booking(payload=payload, manager_account=current_user)
    except EntityDoesNotExist:
        raise await http_404_exc_field_not_found_request(id=payload.field_id)


@router.get(
    path="",
    name="bookings:list-all",
    response_model=list[BookingOut],
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_all_bookings(
    status: str | None = None,
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    booking_service: BookingService = fastapi.Depends(get_booking_service),
) -> list[BookingOut]:
    return await booking_service.get_all_bookings(status=status)


@router.get(
    path="/my",
    name="bookings:list-my",
    response_model=list[BookingOut],
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_my_bookings(
    current_user: Account = fastapi.Depends(get_current_user),
    booking_service: BookingService = fastapi.Depends(get_booking_service),
) -> list[BookingOut]:
    return await booking_service.get_my_bookings(current_account=current_user)


@router.get(
    path="/{id}",
    name="bookings:get-detail",
    response_model=BookingDetailOut,
    status_code=fastapi.status.HTTP_200_OK,
)
async def get_booking_detail(
    id: int,
    current_user: Account = fastapi.Depends(get_current_user),
    booking_service: BookingService = fastapi.Depends(get_booking_service),
) -> BookingDetailOut:
    try:
        return await booking_service.get_booking_detail(booking_id=id, current_account=current_user)
    except EntityDoesNotExist:
        raise await http_404_exc_booking_not_found_request(id=id)


@router.patch(
    path="/{id}/status",
    name="bookings:update-status",
    response_model=BookingDetailOut,
    status_code=fastapi.status.HTTP_200_OK,
)
async def update_booking_status(
    id: int,
    payload: BookingStatusUpdate,
    current_user: Account = fastapi.Depends(get_current_user),
    booking_service: BookingService = fastapi.Depends(get_booking_service),
) -> BookingDetailOut:
    try:
        return await booking_service.change_booking_status(
            booking_id=id, payload=payload, current_account=current_user
        )
    except EntityDoesNotExist:
        raise await http_404_exc_booking_not_found_request(id=id)
