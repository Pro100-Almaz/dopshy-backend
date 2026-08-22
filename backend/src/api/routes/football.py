import typing

import fastapi
import pydantic

from src.api.routes.academy_type import list_groups_by_type, list_students_by_type, list_trials_by_type
from src.api.dependencies.auth import require_roles_or_manager_api_key
from src.api.dependencies.service import get_academy_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.services.academy import AcademyService

router = fastapi.APIRouter(prefix="/football", tags=["football"])


class AttendanceUpdate(pydantic.BaseModel):
    attended: bool = pydantic.Field(strict=True)


class SubscriptionUpdate(pydantic.BaseModel):
    subscribed: bool = pydantic.Field(default=True, strict=True)


@router.get(
    path="/groups",
    name="football:groups",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_football_groups(
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> dict[str, typing.Any]:
    return await list_groups_by_type("football", academy_service)


@router.get(
    path="/trials",
    name="football:trials",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_football_trials(
    subscribed: bool | None = fastapi.Query(default=None),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.MANAGER)),
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
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.MANAGER)),
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
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.set_trial_attended(
        trial_id=trial_id,
        attended=payload.attended,
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
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.set_trial_subscribed(
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
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.set_student_subscribed(
        student_id=student_id,
        subscribed=payload.subscribed,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)
