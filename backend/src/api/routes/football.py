import typing

import fastapi
import pydantic

from src.api.routes.academy_type import (
    assign_student_to_group_by_type,
    create_group_by_type,
    delete_group_by_type,
    get_bot_content_by_type,
    list_groups_by_type,
    list_payments_by_type,
    list_students_by_type,
    list_trials_by_type,
    update_group_by_type,
)
from src.api.dependencies.auth import require_roles_or_manager_api_key
from src.api.dependencies.service import get_academy_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.services.academy import AcademyService

router = fastapi.APIRouter(prefix="/football", tags=["football"])


class AttendanceUpdate(pydantic.BaseModel):
    attended: bool | None = pydantic.Field(default=None, strict=True)
    attendance_state: typing.Literal["pending", "attended", "missed"] | None = None

    model_config = pydantic.ConfigDict(extra="forbid")

    @pydantic.model_validator(mode="after")
    def require_attendance_value(self) -> typing.Self:
        if self.attended is None and self.attendance_state is None:
            raise ValueError("Either attended or attendance_state must be provided.")
        return self


class SubscriptionUpdate(pydantic.BaseModel):
    subscribed: bool = pydantic.Field(default=True, strict=True)


class PaymentConfirmedUpdate(pydantic.BaseModel):
    confirmed: bool = pydantic.Field(strict=True)


class PaymentUpdate(pydantic.BaseModel):
    due_date: str | None = None
    is_active: bool | None = pydantic.Field(default=None, strict=True)
    notes: str | None = None
    check_status: (
        typing.Literal[
            "read",
            "blurry",
            "amount_mismatch",
            "manual",
            "Оқылды",
            "Бұлдыр",
            "Тексеру керек",
            "Қолмен тексеру",
        ]
        | None
    ) = None

    model_config = pydantic.ConfigDict(extra="forbid")


@router.get(
    path="/groups",
    name="football:groups",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_football_groups(
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.FOOTBALL_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> dict[str, typing.Any]:
    return await list_groups_by_type("football", academy_service)


@router.post(
    path="/groups",
    name="football:create-group",
    status_code=fastapi.status.HTTP_200_OK,
)
async def create_football_group(
    payload: dict[str, typing.Any] = fastapi.Body(...),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.FOOTBALL_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    return await create_group_by_type("football", payload, academy_service)


@router.patch(
    path="/groups/{group_id}",
    name="football:update-group",
    status_code=fastapi.status.HTTP_200_OK,
)
async def update_football_group(
    group_id: int,
    payload: dict[str, typing.Any] = fastapi.Body(default_factory=dict),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.FOOTBALL_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    return await update_group_by_type("football", group_id, payload, academy_service)


@router.delete(
    path="/groups/{group_id}",
    name="football:delete-group",
    status_code=fastapi.status.HTTP_200_OK,
)
async def delete_football_group(
    group_id: int,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.FOOTBALL_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    return await delete_group_by_type("football", group_id, academy_service)


@router.post(
    path="/groups/{group_id}/students",
    name="football:assign-student-to-group",
    status_code=fastapi.status.HTTP_200_OK,
)
async def assign_student_to_football_group(
    group_id: int,
    payload: dict[str, typing.Any] = fastapi.Body(...),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.FOOTBALL_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    return await assign_student_to_group_by_type("football", group_id, payload, academy_service)


@router.get(
    path="/trials",
    name="football:trials",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_football_trials(
    subscribed: bool | None = fastapi.Query(default=None),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.FOOTBALL_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> dict[str, typing.Any]:
    return await list_trials_by_type("football", subscribed, academy_service)


@router.get(
    path="/students",
    name="football:students",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_football_students(
    subscribed: bool | None = fastapi.Query(default=None),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.FOOTBALL_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> dict[str, typing.Any]:
    return await list_students_by_type("football", subscribed, academy_service)


@router.patch(
    path="/trials/{trial_id}/attended",
    name="football:trial-attended",
    status_code=fastapi.status.HTTP_200_OK,
)
async def set_trial_attended(
    trial_id: int,
    payload: AttendanceUpdate,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.FOOTBALL_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.set_sport_trial_attended(
        sport="football",
        trial_id=trial_id,
        payload=payload.model_dump(exclude_none=True),
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.patch(
    path="/trials/{trial_id}/subscribed",
    name="football:trial-subscribed",
    status_code=fastapi.status.HTTP_200_OK,
)
async def set_trial_subscribed(
    trial_id: int,
    payload: SubscriptionUpdate,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.FOOTBALL_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.set_sport_trial_subscribed(
        sport="football",
        trial_id=trial_id,
        subscribed=payload.subscribed,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.patch(
    path="/students/{student_id}/subscribed",
    name="football:student-subscribed",
    status_code=fastapi.status.HTTP_200_OK,
)
async def set_student_subscribed(
    student_id: int,
    payload: SubscriptionUpdate,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.FOOTBALL_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.set_sport_student_subscribed(
        sport="football",
        student_id=student_id,
        subscribed=payload.subscribed,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.get(
    path="/payments",
    name="football:payments",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_football_payments(
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    return await list_payments_by_type("football", academy_service)


@router.patch(
    path="/payments/{payment_id}/confirmed",
    name="football:payment-confirmed",
    status_code=fastapi.status.HTTP_200_OK,
)
async def set_football_payment_confirmed(
    payment_id: int,
    payload: PaymentConfirmedUpdate,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.set_sport_payment_confirmed(
        sport="football",
        payment_id=payment_id,
        confirmed=payload.confirmed,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.patch(
    path="/payments/{payment_id}",
    name="football:payment-update",
    status_code=fastapi.status.HTTP_200_OK,
)
async def update_football_payment(
    payment_id: int,
    payload: PaymentUpdate,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    update_payload = payload.model_dump(exclude_unset=True)
    if not update_payload:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail="At least one payment field must be provided.",
        )
    status_code, response_payload = await academy_service.update_sport_payment(
        sport="football",
        payment_id=payment_id,
        payload=update_payload,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.get(
    path="/bot-content",
    name="football:bot-content",
    status_code=fastapi.status.HTTP_200_OK,
)
async def get_football_bot_content(
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.SUPER_ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    return await get_bot_content_by_type("football", academy_service)


@router.put(
    path="/bot-content",
    name="football:bot-content-save",
    status_code=fastapi.status.HTTP_200_OK,
)
async def save_football_bot_content(
    payload: dict[str, typing.Any] = fastapi.Body(default_factory=dict),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.SUPER_ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.save_sport_bot_content(
        sport="football",
        payload=payload,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)
