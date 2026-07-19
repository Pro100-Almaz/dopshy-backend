import fastapi

from src.api.dependencies.auth import get_current_user, require_roles
from src.api.dependencies.service import get_booking_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.models.schemas.booking import (
    BookingBatchInCreate,
    BookingDetailOut,
    BookingInCreate,
    BookingInCreateAuthenticated,
    BookingInCreateByManager,
    BookingOut,
    BookingStatusUpdate, BotBookingRaw, BookingInUpdate,
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


@router.post(
    path="/batch",
    name="bookings:create-batch",
)
async def create_bookings_batch(
    payload: BookingBatchInCreate,
    booking_service: BookingService = fastapi.Depends(get_booking_service),
) -> fastapi.Response:
    status_code, data = await booking_service.create_bookings_batch(payload=payload)
    return fastapi.responses.JSONResponse(status_code=status_code, content=data)


@router.get(
    path="",
    name="bookings:list-all",
    response_model=list[BotBookingRaw | None],
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_all_bookings(
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    booking_service: BookingService = fastapi.Depends(get_booking_service),
) -> list[BotBookingRaw] | None:
    return await booking_service.get_all_bookings()


@router.get(
    path="/range/{start_date}/{end_date}/{field}",
    name="bookings:list-range",
    response_model=list[BotBookingRaw | None],
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_bookings_in_range(
        start_date: str,
        end_date: str,
        field: int,
        booking_service: BookingService = fastapi.Depends(get_booking_service),
) -> list[BotBookingRaw] | None:
    return await booking_service.get_bookings_in_range(
        start_date=start_date, end_date=end_date, field=field
    )


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
    path="/{id}",
    name="bookings:update-detail",
    status_code=fastapi.status.HTTP_200_OK,
)
async def update_booking_detail(
        id: int,
        payload: BookingInUpdate,
        current_user: Account = fastapi.Depends(get_current_user),
        booking_service: BookingService = fastapi.Depends(get_booking_service),
) -> dict:
    try:
        return await booking_service.update_booking(
            booking_id=id, payload=payload, current_user=current_user
        )
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

