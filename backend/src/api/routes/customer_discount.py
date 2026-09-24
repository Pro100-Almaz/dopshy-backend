import typing

import fastapi

from src.api.dependencies.auth import require_roles
from src.api.dependencies.service import get_customer_discount_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.models.schemas.customer_discount import (
    CustomerInCreate,
    CustomerInUpdate,
    DiscountInCreate,
    DiscountInUpdate,
    DiscountStatus,
    ManagerBookingInCreate,
)
from src.services.customer_discount import CustomerDiscountService
from src.utilities.phone import normalize_kz_phone

router = fastapi.APIRouter(prefix="/manager", tags=["manager-customers-discounts"])

_VIEW_ROLES = (Role.MANAGER, Role.ARENA_MANAGER, Role.ADMIN)
_ADMIN_ROLES = (Role.ADMIN,)


def _actor(account: Account) -> str:
    return account.email


def _response(result: tuple[int, typing.Any]) -> fastapi.responses.JSONResponse:
    status_code, payload = result
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


@router.get("/customers")
async def list_customers(
    phone: str | None = None,
    search: str | None = None,
    _: Account = fastapi.Depends(require_roles(*_VIEW_ROLES)),
    service: CustomerDiscountService = fastapi.Depends(get_customer_discount_service),
) -> fastapi.Response:
    normalized_phone = normalize_kz_phone(phone) if phone is not None else None
    return _response(
        await service.request(
            "GET",
            "/api/manager/customers",
            params={"phone": normalized_phone, "search": search},
        )
    )


@router.get("/customers/{customer_id}")
async def get_customer(
    customer_id: int,
    _: Account = fastapi.Depends(require_roles(*_VIEW_ROLES)),
    service: CustomerDiscountService = fastapi.Depends(get_customer_discount_service),
) -> fastapi.Response:
    return _response(await service.request("GET", f"/api/manager/customers/{customer_id}"))


@router.post("/customers", status_code=fastapi.status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerInCreate,
    account: Account = fastapi.Depends(require_roles(*_VIEW_ROLES)),
    service: CustomerDiscountService = fastapi.Depends(get_customer_discount_service),
) -> fastapi.Response:
    if payload.is_regular_customer and account.role not in {
        Role.ADMIN.value,
        Role.SUPER_ADMIN.value,
    }:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_403_FORBIDDEN,
            detail="Only administrators can change regular-customer status.",
        )
    body = payload.model_dump(mode="json") | {"source": _actor(account)}
    return _response(await service.request("POST", "/api/manager/customers", json=body))


@router.patch("/customers/{customer_id}")
async def update_customer(
    customer_id: int,
    payload: CustomerInUpdate,
    account: Account = fastapi.Depends(require_roles(*_VIEW_ROLES)),
    service: CustomerDiscountService = fastapi.Depends(get_customer_discount_service),
) -> fastapi.Response:
    if "is_regular_customer" in payload.model_fields_set and account.role not in {
        Role.ADMIN.value,
        Role.SUPER_ADMIN.value,
    }:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_403_FORBIDDEN,
            detail="Only administrators can change regular-customer status.",
        )
    body = payload.model_dump(mode="json", exclude_unset=True) | {"source": _actor(account)}
    return _response(await service.request("PATCH", f"/api/manager/customers/{customer_id}", json=body))


@router.delete("/customers/{customer_id}")
async def delete_customer(
    customer_id: int,
    account: Account = fastapi.Depends(require_roles(Role.SUPER_ADMIN)),
    service: CustomerDiscountService = fastapi.Depends(get_customer_discount_service),
) -> fastapi.Response:
    return _response(
        await service.request("DELETE", f"/api/manager/customers/{customer_id}", json={"source": _actor(account)})
    )


@router.get("/discounts")
async def list_discounts(
    customer_id: int | None = None,
    phone: str | None = None,
    status: DiscountStatus | None = None,
    available_only: bool | None = None,
    _: Account = fastapi.Depends(require_roles(*_VIEW_ROLES)),
    service: CustomerDiscountService = fastapi.Depends(get_customer_discount_service),
) -> fastapi.Response:
    params = {
        "customer_id": customer_id,
        "phone": normalize_kz_phone(phone) if phone is not None else None,
        "status": (
            DiscountStatus.REJECTED.value if status == DiscountStatus.CANCELED else status.value if status else None
        ),
        "available_only": str(available_only).lower() if available_only is not None else None,
    }
    return _response(await service.request("GET", "/api/manager/discounts", params=params))


@router.get("/discounts/{discount_id}")
async def get_discount(
    discount_id: int,
    _: Account = fastapi.Depends(require_roles(*_VIEW_ROLES)),
    service: CustomerDiscountService = fastapi.Depends(get_customer_discount_service),
) -> fastapi.Response:
    return _response(await service.request("GET", f"/api/manager/discounts/{discount_id}"))


@router.post("/discounts", status_code=fastapi.status.HTTP_201_CREATED)
async def create_discount(
    payload: DiscountInCreate,
    account: Account = fastapi.Depends(require_roles(*_ADMIN_ROLES)),
    service: CustomerDiscountService = fastapi.Depends(get_customer_discount_service),
) -> fastapi.Response:
    body = payload.model_dump(mode="json")
    if account.role != Role.SUPER_ADMIN.value:
        body["status"] = DiscountStatus.PENDING.value
    elif body["status"] == DiscountStatus.CANCELED.value:
        body["status"] = DiscountStatus.REJECTED.value
    body["source"] = _actor(account)
    return _response(await service.request("POST", "/api/manager/discounts", json=body))


@router.patch("/discounts/{discount_id}")
async def update_discount(
    discount_id: int,
    payload: DiscountInUpdate,
    account: Account = fastapi.Depends(require_roles(Role.SUPER_ADMIN)),
    service: CustomerDiscountService = fastapi.Depends(get_customer_discount_service),
) -> fastapi.Response:
    body = payload.model_dump(mode="json", exclude_unset=True)
    if body.get("status") == DiscountStatus.CANCELED.value:
        body["status"] = DiscountStatus.REJECTED.value
    body["source"] = _actor(account)
    return _response(await service.request("PATCH", f"/api/manager/discounts/{discount_id}", json=body))


@router.delete("/discounts/{discount_id}")
async def delete_discount(
    discount_id: int,
    account: Account = fastapi.Depends(require_roles(Role.SUPER_ADMIN)),
    service: CustomerDiscountService = fastapi.Depends(get_customer_discount_service),
) -> fastapi.Response:
    return _response(
        await service.request("DELETE", f"/api/manager/discounts/{discount_id}", json={"source": _actor(account)})
    )


@router.post("/bookings", status_code=fastapi.status.HTTP_201_CREATED)
async def create_manager_booking(
    payload: ManagerBookingInCreate,
    account: Account = fastapi.Depends(require_roles(*_VIEW_ROLES)),
    service: CustomerDiscountService = fastapi.Depends(get_customer_discount_service),
) -> fastapi.Response:
    body = payload.model_dump(mode="json", exclude_none=True) | {"source": _actor(account)}
    return _response(await service.request("POST", "/api/manager/bookings", json=body))
