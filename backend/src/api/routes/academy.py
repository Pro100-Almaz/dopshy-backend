import typing

import fastapi
import pydantic

from src.api.dependencies.auth import require_roles_or_manager_api_key
from src.api.dependencies.service import get_academy_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.services.academy import AcademyService

router = fastapi.APIRouter(prefix="/manager", tags=["manager-academy"])


class AttendanceUpdate(pydantic.BaseModel):
    attended: bool = pydantic.Field(strict=True)


class SubscriptionUpdate(pydantic.BaseModel):
    subscribed: bool = pydantic.Field(default=True, strict=True)


class AcademyGroupUpdate(pydantic.BaseModel):
    group_name: str | None = None
    max_cap: int | None = None
    start_time: str | None = None
    end_time: str | None = None

    model_config = pydantic.ConfigDict(extra="forbid")


@router.get(
    path="/academy_groups",
    name="manager-academy:list-groups",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_academy_groups(
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, payload = await academy_service.list_groups()
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


@router.post(
    path="/academy_groups",
    name="manager-academy:create-group",
    status_code=fastapi.status.HTTP_200_OK,
)
async def create_academy_group(
    payload: dict[str, typing.Any] = fastapi.Body(...),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.create_group(payload=payload)
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.get(
    path="/academy_groups/{group_id}/trials",
    name="manager-academy:group-trials",
    status_code=fastapi.status.HTTP_200_OK,
)
async def get_academy_group_trials(
    group_id: int,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, payload = await academy_service.get_group_trials(group_id=group_id)
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


@router.patch(
    path="/academy_groups/{group_id}",
    name="manager-academy:update-group",
    status_code=fastapi.status.HTTP_200_OK,
)
async def update_academy_group(
    group_id: int,
    payload: dict[str, typing.Any] | AcademyGroupUpdate = fastapi.Body(default_factory=dict),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    update_payload = _payload_to_dict(payload)
    if not update_payload:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail="At least one group field must be provided.",
        )

    status_code, response_payload = await academy_service.update_group(group_id=group_id, payload=update_payload)
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.delete(
    path="/academy_groups/{group_id}",
    name="manager-academy:delete-group",
    status_code=fastapi.status.HTTP_200_OK,
)
async def delete_academy_group(
    group_id: int,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.delete_group(group_id=group_id)
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.post(
    path="/academy_groups/{group_id}/students",
    name="manager-academy:assign-student-to-group",
    status_code=fastapi.status.HTTP_200_OK,
)
async def assign_student_to_academy_group(
    group_id: int,
    payload: dict[str, typing.Any] = fastapi.Body(...),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.assign_student_to_group(
        group_id=group_id,
        payload=payload,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.patch(
    path="/academy_trials/{trial_id}/attended",
    name="manager-academy:trial-attended",
    status_code=fastapi.status.HTTP_200_OK,
)
async def set_academy_trial_attended(
    trial_id: int,
    payload: AttendanceUpdate,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.set_trial_attended(
        trial_id=trial_id,
        attended=payload.attended,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.patch(
    path="/academy_trials/{trial_id}/subscribed",
    name="manager-academy:trial-subscribed",
    status_code=fastapi.status.HTTP_200_OK,
)
async def set_academy_trial_subscribed(
    trial_id: int,
    payload: SubscriptionUpdate,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.set_trial_subscribed(
        trial_id=trial_id,
        subscribed=payload.subscribed,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.patch(
    path="/academy_users/{user_id}/subscribed",
    name="manager-academy:user-subscribed",
    status_code=fastapi.status.HTTP_200_OK,
)
async def set_academy_user_subscribed(
    user_id: int,
    payload: SubscriptionUpdate,
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.set_student_subscribed(
        student_id=user_id,
        subscribed=payload.subscribed,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


def _payload_to_dict(payload: dict[str, typing.Any] | pydantic.BaseModel) -> dict[str, typing.Any]:
    if isinstance(payload, pydantic.BaseModel):
        return payload.model_dump(exclude_unset=True)
    return payload
