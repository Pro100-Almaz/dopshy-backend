import fastapi

from src.api.dependencies.auth import require_bot_prefill_key
from src.api.dependencies.service import get_booking_prefill_service, get_booking_service
from src.models.schemas.prefill import PrefillCreatedOut, PrefillCreateIn, PrefillCreateResponse, PrefillOut
from src.services.booking import BookingService
from src.services.booking_prefill import BookingPrefillService

router = fastapi.APIRouter(tags=["booking-prefill"])


@router.post(
    path="/bot/prefill",
    name="prefill:create",
    response_model=PrefillCreateResponse,
    status_code=fastapi.status.HTTP_201_CREATED,
    dependencies=[fastapi.Depends(require_bot_prefill_key)],
)
async def create_prefill(
    payload: PrefillCreateIn,
    prefill_service: BookingPrefillService = fastapi.Depends(get_booking_prefill_service),
) -> PrefillCreateResponse:
    """Bot -> backend: store what the bot collected and get a short-lived landing link."""
    created: PrefillCreatedOut = await prefill_service.create(payload=payload)
    return PrefillCreateResponse(data=created)


@router.get(
    path="/bookings/prefill/{token}",
    name="prefill:resolve",
    response_model=PrefillOut,
    status_code=fastapi.status.HTTP_200_OK,
)
async def resolve_prefill(
    token: str,
    response: fastapi.Response,
    prefill_service: BookingPrefillService = fastapi.Depends(get_booking_prefill_service),
    booking_service: BookingService = fastapi.Depends(get_booking_service),
) -> PrefillOut:
    """Landing -> backend: no auth, the token is the credential. The phone is only ever returned masked."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return await prefill_service.resolve(token=token, booking_service=booking_service)
