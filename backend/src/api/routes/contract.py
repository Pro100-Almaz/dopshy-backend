import typing

import fastapi

from src.api.dependencies.auth import require_roles_or_manager_api_key
from src.api.dependencies.service import get_contract_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.services.contract import ContractService

router = fastapi.APIRouter(prefix="/manager/contracts", tags=["manager-contracts"])


@router.get(
    path="",
    name="manager-contracts:list",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_contracts(
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
    page: int | None = fastapi.Query(default=None),
    search: str | None = fastapi.Query(default=None),
) -> fastapi.responses.JSONResponse:
    if page is not None and page < 1:
        return fastapi.responses.JSONResponse(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            content={"ok": False, "code": "INVALID", "message": "page must be greater than or equal to 1"},
        )

    status_code, payload = await contract_service.list_contracts(page=page, search=search)
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


@router.post(
    path="/check-slots",
    name="manager-contracts:check-slots",
    status_code=fastapi.status.HTTP_200_OK,
)
async def check_contract_slots(
    payload: dict[str, typing.Any],
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await contract_service.check_contract_slots(payload=payload)
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.post(
    path="/payment-plan/preview",
    name="manager-contracts:preview-payment-plan",
    status_code=fastapi.status.HTTP_200_OK,
)
async def preview_contract_payment_plan(
    payload: dict[str, typing.Any],
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await contract_service.preview_payment_plan(payload=payload)
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.get(
    path="/{contract_id}",
    name="manager-contracts:get",
    status_code=fastapi.status.HTTP_200_OK,
)
async def get_contract(
    contract_id: int,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, payload = await contract_service.get_contract(contract_id=contract_id)
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


@router.post(
    path="",
    name="manager-contracts:create",
    status_code=fastapi.status.HTTP_200_OK,
)
async def create_contract(
    payload: dict[str, typing.Any],
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await contract_service.create_contract(payload=payload)
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.patch(
    path="/{contract_id}",
    name="manager-contracts:update",
    status_code=fastapi.status.HTTP_200_OK,
)
async def update_contract(
    contract_id: int,
    payload: dict[str, typing.Any],
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await contract_service.update_contract(
        contract_id=contract_id,
        payload=payload,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.delete(
    path="/{contract_id}",
    name="manager-contracts:delete",
    status_code=fastapi.status.HTTP_200_OK,
)
async def delete_contract(
    contract_id: int,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, payload = await contract_service.delete_contract(contract_id=contract_id)
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


@router.post(
    path="/{contract_id}/bookings/batch",
    name="manager-contracts:create-bookings-batch",
    status_code=fastapi.status.HTTP_200_OK,
)
async def create_contract_bookings_batch(
    contract_id: int,
    payload: dict[str, typing.Any],
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await contract_service.create_contract_bookings(
        contract_id=contract_id,
        payload=payload,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.patch(
    path="/{contract_id}/bookings/batch",
    name="manager-contracts:update-bookings-batch",
    status_code=fastapi.status.HTTP_200_OK,
)
async def update_contract_bookings_batch(
    contract_id: int,
    payload: dict[str, typing.Any],
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await contract_service.update_contract_bookings(
        contract_id=contract_id,
        payload=payload,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.delete(
    path="/{contract_id}/bookings/batch",
    name="manager-contracts:delete-bookings-batch",
    status_code=fastapi.status.HTTP_200_OK,
)
async def delete_contract_bookings_batch(
    contract_id: int,
    payload: dict[str, typing.Any] | None = None,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await contract_service.delete_contract_bookings(
        contract_id=contract_id,
        payload=payload or {},
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.get(
    path="/{contract_id}/payments",
    name="manager-contracts:get-payments",
    status_code=fastapi.status.HTTP_200_OK,
)
async def get_contract_payments(
    contract_id: int,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, payload = await contract_service.get_contract_payments(contract_id=contract_id)
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


@router.put(
    path="/{contract_id}/payment-plan",
    name="manager-contracts:replace-payment-plan",
    status_code=fastapi.status.HTTP_200_OK,
)
async def replace_contract_payment_plan(
    contract_id: int,
    payload: dict[str, typing.Any],
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await contract_service.replace_payment_plan(
        contract_id=contract_id,
        payload=payload,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.delete(
    path="/{contract_id}/payment-plan",
    name="manager-contracts:stop-payment-plan",
    status_code=fastapi.status.HTTP_200_OK,
)
async def stop_contract_payment_plan(
    contract_id: int,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, payload = await contract_service.stop_payment_plan(contract_id=contract_id)
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


@router.patch(
    path="/{contract_id}/installments/{installment_id}",
    name="manager-contracts:update-installment",
    status_code=fastapi.status.HTTP_200_OK,
)
async def update_contract_installment(
    contract_id: int,
    installment_id: int,
    payload: dict[str, typing.Any],
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await contract_service.update_installment(
        contract_id=contract_id,
        installment_id=installment_id,
        payload=payload,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.post(
    path="/{contract_id}/installments/{installment_id}/mark-paid",
    name="manager-contracts:mark-installment-paid",
    status_code=fastapi.status.HTTP_200_OK,
)
async def mark_contract_installment_paid(
    contract_id: int,
    installment_id: int,
    payload: dict[str, typing.Any] | None = None,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await contract_service.mark_installment_paid(
        contract_id=contract_id,
        installment_id=installment_id,
        payload=payload or {},
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.post(
    path="/{contract_id}/installments/{installment_id}/send",
    name="manager-contracts:send-installment",
    status_code=fastapi.status.HTTP_200_OK,
)
async def send_contract_installment(
    contract_id: int,
    installment_id: int,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.ARENA_MANAGER)),
    contract_service: ContractService = fastapi.Depends(get_contract_service),
) -> fastapi.responses.JSONResponse:
    status_code, payload = await contract_service.send_installment(
        contract_id=contract_id,
        installment_id=installment_id,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)
