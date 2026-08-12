import typing

import fastapi
import loguru

from src.api.dependencies.auth import get_current_user, require_roles
from src.api.dependencies.service import get_payment_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.models.schemas.payment import (
    PaymentInCreate,
    PaymentOut,
    PaymentRefundIn,
    PaymentSimulateIn,
    WebhookAck,
)
from src.repository.crud.payment import PaymentCRUDRepository
from src.repository.database import async_db
from src.services.payment import PaymentService, WebhookSignatureError
from src.utilities.exceptions.database import EntityDoesNotExist

router = fastapi.APIRouter(prefix="/payments", tags=["payments"])


async def _notify_bot_in_background(payment_id: int) -> None:
    """Run the bot notification outside the webhook request.

    The webhook handler must answer within five seconds or ApiPay retries it, so the
    outbound call gets its own session and its own lifetime.
    """
    async with async_db.async_sessionmaker() as session:
        service = PaymentService(payment_repo=PaymentCRUDRepository(async_session=session))
        try:
            await service.notify_bot(payment_id=payment_id)
        except Exception as exc:  # noqa: BLE001 — a background task must never crash silently
            loguru.logger.exception(f"Background bot notification failed for payment id={payment_id}: {exc}")


# Declared before `/{id}` so the literal path is not swallowed by the int path param.
@router.post(
    path="/webhook/apipay",
    name="payments:apipay-webhook",
    response_model=WebhookAck,
    status_code=fastapi.status.HTTP_200_OK,
    include_in_schema=False,
)
async def apipay_webhook(
    request: fastapi.Request,
    background_tasks: fastapi.BackgroundTasks,
    payment_service: PaymentService = fastapi.Depends(get_payment_service),
) -> WebhookAck:
    """Payment notifications from ApiPay.

    Public by design — authentication is the HMAC signature over the raw body, which
    is why the body is read as bytes and never re-serialised. This is the URL to put
    in the ApiPay dashboard: https://api.dopsy.kz/api/payments/webhook/apipay
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Webhook-Signature")

    try:
        event, payment, must_notify_bot = await payment_service.handle_webhook(raw_body=raw_body, signature=signature)
    except WebhookSignatureError as exc:
        # 401 is a non-retryable answer for ApiPay — correct, since redelivering a
        # payload with a bad signature would never start matching.
        loguru.logger.warning(f"Rejected ApiPay webhook: {exc}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature"
        ) from exc

    if must_notify_bot and payment is not None:
        background_tasks.add_task(_notify_bot_in_background, payment.id)

    return WebhookAck(ok=True, event=event, handled=payment is not None)


@router.post(
    path="",
    name="payments:create",
    response_model=PaymentOut,
    status_code=fastapi.status.HTTP_201_CREATED,
)
async def create_payment(
    payload: PaymentInCreate,
    current_user: Account = fastapi.Depends(get_current_user),
    payment_service: PaymentService = fastapi.Depends(get_payment_service),
) -> PaymentOut:
    """Bill a customer through Kaspi Pay.

    Authenticated on purpose: an open endpoint would let anyone push a real Kaspi
    payment request to any phone number in Kazakhstan.
    """
    payment = await payment_service.create_payment(payload=payload, account=current_user)
    return PaymentOut.model_validate(payment)


@router.get(
    path="",
    name="payments:list",
    response_model=list[PaymentOut],
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_payments(
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    payment_service: PaymentService = fastapi.Depends(get_payment_service),
    booking_id: int | None = fastapi.Query(default=None, ge=1),
    status: str | None = fastapi.Query(default=None),
    limit: int = fastapi.Query(default=100, ge=1, le=500),
    offset: int = fastapi.Query(default=0, ge=0),
) -> list[PaymentOut]:
    payments = await payment_service.list_payments(booking_id=booking_id, status=status, limit=limit, offset=offset)
    return [PaymentOut.model_validate(p) for p in payments]


@router.get(
    path="/webhook-logs",
    name="payments:webhook-logs",
    status_code=fastapi.status.HTTP_200_OK,
)
async def read_webhook_logs(
    _: Account = fastapi.Depends(require_roles(Role.ADMIN)),
    payment_service: PaymentService = fastapi.Depends(get_payment_service),
    payment_id: int | None = fastapi.Query(default=None, ge=1),
    event: str | None = fastapi.Query(default=None),
) -> typing.Any:
    """ApiPay's delivery log — shows whether a webhook was sent and how we answered."""
    return await payment_service.get_webhook_logs(payment_id=payment_id, event=event)


@router.get(
    path="/{id}",
    name="payments:get",
    response_model=PaymentOut,
    status_code=fastapi.status.HTTP_200_OK,
)
async def get_payment(
    id: int,
    current_user: Account = fastapi.Depends(get_current_user),
    payment_service: PaymentService = fastapi.Depends(get_payment_service),
    refresh: bool = fastapi.Query(
        default=False, description="Спросить статус напрямую у ApiPay, не дожидаясь вебхука."
    ),
) -> PaymentOut:
    # Ownership is checked before honouring `refresh`, so a stranger cannot make us
    # spend an ApiPay call on someone else's invoice.
    try:
        payment = await payment_service.get_payment(payment_id=id, refresh=False)
    except EntityDoesNotExist as exc:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND, detail=f"Платёж с id `{id}` не найден."
        ) from exc

    is_staff = current_user.role in (Role.ADMIN.value, Role.MANAGER.value)
    if not is_staff and payment.account_id != current_user.id:
        raise fastapi.HTTPException(status_code=fastapi.status.HTTP_403_FORBIDDEN, detail="Access denied")

    if refresh:
        payment = await payment_service.get_payment(payment_id=id, refresh=True)

    return PaymentOut.model_validate(payment)


@router.post(
    path="/{id}/refund",
    name="payments:refund",
    response_model=PaymentOut,
    status_code=fastapi.status.HTTP_200_OK,
)
async def refund_payment(
    id: int,
    payload: PaymentRefundIn,
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    payment_service: PaymentService = fastapi.Depends(get_payment_service),
) -> PaymentOut:
    try:
        payment = await payment_service.refund_payment(payment_id=id, amount=payload.amount)
    except EntityDoesNotExist as exc:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND, detail=f"Платёж с id `{id}` не найден."
        ) from exc
    return PaymentOut.model_validate(payment)


@router.post(
    path="/{id}/cancel",
    name="payments:cancel",
    response_model=PaymentOut,
    status_code=fastapi.status.HTTP_200_OK,
)
async def cancel_payment(
    id: int,
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    payment_service: PaymentService = fastapi.Depends(get_payment_service),
) -> PaymentOut:
    try:
        payment = await payment_service.cancel_payment(payment_id=id)
    except EntityDoesNotExist as exc:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND, detail=f"Платёж с id `{id}` не найден."
        ) from exc
    return PaymentOut.model_validate(payment)


@router.post(
    path="/{id}/sync-bot",
    name="payments:sync-bot",
    response_model=PaymentOut,
    status_code=fastapi.status.HTTP_200_OK,
)
async def sync_payment_to_bot(
    id: int,
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    payment_service: PaymentService = fastapi.Depends(get_payment_service),
) -> PaymentOut:
    """Replay the bot notification — for when the automatic one failed (see bot_notify_error)."""
    try:
        payment = await payment_service.notify_bot(payment_id=id)
    except EntityDoesNotExist as exc:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND, detail=f"Платёж с id `{id}` не найден."
        ) from exc
    return PaymentOut.model_validate(payment)


@router.post(
    path="/{id}/simulate-status",
    name="payments:simulate-status",
    status_code=fastapi.status.HTTP_200_OK,
)
async def simulate_payment_status(
    id: int,
    payload: PaymentSimulateIn,
    _: Account = fastapi.Depends(require_roles(Role.ADMIN)),
    payment_service: PaymentService = fastapi.Depends(get_payment_service),
) -> typing.Any:
    """Sandbox testing helper. ApiPay answers `403 not_sandbox` for a live invoice."""
    try:
        return await payment_service.simulate_status(
            payment_id=id, status=payload.status, error_message=payload.error_message
        )
    except EntityDoesNotExist as exc:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND, detail=f"Платёж с id `{id}` не найден."
        ) from exc
