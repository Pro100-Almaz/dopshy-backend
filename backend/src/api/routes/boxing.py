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

router = fastapi.APIRouter(prefix="/boxing", tags=["boxing"])


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


class StudentAssignment(pydantic.BaseModel):
    group_id: int = pydantic.Field(strict=True)


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
    name="boxing:groups",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_boxing_groups(
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.BOXING_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> dict[str, typing.Any]:
    return await list_groups_by_type("boxing", academy_service)


@router.post(
    path="/groups",
    name="boxing:create-group",
    status_code=fastapi.status.HTTP_200_OK,
)
async def create_boxing_group(
    payload: dict[str, typing.Any] = fastapi.Body(...),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.BOXING_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    return await create_group_by_type("boxing", payload, academy_service)


@router.patch(
    path="/groups/{group_id}",
    name="boxing:update-group",
    status_code=fastapi.status.HTTP_200_OK,
)
async def update_boxing_group(
    group_id: int,
    payload: dict[str, typing.Any] = fastapi.Body(default_factory=dict),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.BOXING_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    return await update_group_by_type("boxing", group_id, payload, academy_service)


@router.delete(
    path="/groups/{group_id}",
    name="boxing:delete-group",
    status_code=fastapi.status.HTTP_200_OK,
)
async def delete_boxing_group(
    group_id: int,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.BOXING_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    return await delete_group_by_type("boxing", group_id, academy_service)


@router.post(
    path="/groups/{group_id}/students",
    name="boxing:assign-student-to-group",
    status_code=fastapi.status.HTTP_200_OK,
)
async def assign_student_to_boxing_group(
    group_id: int,
    payload: dict[str, typing.Any] = fastapi.Body(...),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.BOXING_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    return await assign_student_to_group_by_type("boxing", group_id, payload, academy_service)


@router.get(
    path="/trials",
    name="boxing:trials",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_boxing_trials(
    subscribed: bool | None = fastapi.Query(default=None),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.BOXING_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> dict[str, typing.Any]:
    return await list_trials_by_type("boxing", subscribed, academy_service)


@router.get(
    path="/students",
    name="boxing:students",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_boxing_students(
    subscribed: bool | None = fastapi.Query(default=None),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.BOXING_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> dict[str, typing.Any]:
    return await list_students_by_type("boxing", subscribed, academy_service)


@router.post(
    path="/students",
    name="boxing:create-student",
    status_code=fastapi.status.HTTP_201_CREATED,
)
async def create_boxing_student(
    payload: dict[str, typing.Any] = fastapi.Body(...),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.BOXING_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.create_sport_student("boxing", payload=payload)
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.patch(
    path="/students/{student_id}",
    name="boxing:update-student",
    status_code=fastapi.status.HTTP_200_OK,
)
async def update_boxing_student(
    student_id: int,
    payload: dict[str, typing.Any] = fastapi.Body(default_factory=dict),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.BOXING_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    if not payload:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail="At least one student field must be provided.",
        )
    status_code, response_payload = await academy_service.update_sport_student(
        "boxing",
        student_id=student_id,
        payload=payload,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.patch(
    path="/students/{student_id}/assignment",
    name="boxing:assign-student",
    status_code=fastapi.status.HTTP_200_OK,
)
async def assign_boxing_student(
    student_id: int,
    payload: StudentAssignment,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.BOXING_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.assign_sport_student(
        "boxing",
        student_id=student_id,
        group_id=payload.group_id,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.delete(
    path="/students/{student_id}/assignment",
    name="boxing:deassign-student",
    status_code=fastapi.status.HTTP_200_OK,
)
async def deassign_boxing_student(
    student_id: int,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.BOXING_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.deassign_sport_student("boxing", student_id=student_id)
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.patch(
    path="/trials/{trial_id}/attended",
    name="boxing:trial-attended",
    status_code=fastapi.status.HTTP_200_OK,
)
async def set_trial_attended(
    trial_id: int,
    payload: AttendanceUpdate,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.BOXING_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.set_sport_trial_attended(
        sport="boxing",
        trial_id=trial_id,
        payload=payload.model_dump(exclude_none=True),
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.patch(
    path="/trials/{trial_id}/subscribed",
    name="boxing:trial-subscribed",
    status_code=fastapi.status.HTTP_200_OK,
)
async def set_trial_subscribed(
    trial_id: int,
    payload: SubscriptionUpdate,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.BOXING_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.set_sport_trial_subscribed(
        sport="boxing",
        trial_id=trial_id,
        subscribed=payload.subscribed,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.patch(
    path="/students/{student_id}/subscribed",
    name="boxing:student-subscribed",
    status_code=fastapi.status.HTTP_200_OK,
)
async def set_student_subscribed(
    student_id: int,
    payload: SubscriptionUpdate,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.BOXING_MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.set_sport_student_subscribed(
        sport="boxing",
        student_id=student_id,
        subscribed=payload.subscribed,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.get(
    path="/payments",
    name="boxing:payments",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_boxing_payments(
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    return await list_payments_by_type("boxing", academy_service)


@router.patch(
    path="/payments/{payment_id}/confirmed",
    name="boxing:payment-confirmed",
    status_code=fastapi.status.HTTP_200_OK,
)
async def set_boxing_payment_confirmed(
    payment_id: int,
    payload: PaymentConfirmedUpdate,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.set_sport_payment_confirmed(
        sport="boxing",
        payment_id=payment_id,
        confirmed=payload.confirmed,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.patch(
    path="/payments/{payment_id}",
    name="boxing:payment-update",
    status_code=fastapi.status.HTTP_200_OK,
)
async def update_boxing_payment(
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
        sport="boxing",
        payment_id=payment_id,
        payload=update_payload,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.get(
    path="/bot-content",
    name="boxing:bot-content",
    status_code=fastapi.status.HTTP_200_OK,
)
async def get_boxing_bot_content(
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.SUPER_ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    return await get_bot_content_by_type("boxing", academy_service)


@router.put(
    path="/bot-content",
    name="boxing:bot-content-save",
    status_code=fastapi.status.HTTP_200_OK,
)
async def save_boxing_bot_content(
    payload: dict[str, typing.Any] = fastapi.Body(default_factory=dict),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.SUPER_ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.save_sport_bot_content(
        sport="boxing",
        payload=payload,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)
