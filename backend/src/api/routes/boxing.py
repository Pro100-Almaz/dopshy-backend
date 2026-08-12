import typing

import fastapi
import pydantic

from src.api.dependencies.auth import require_roles_or_manager_api_key
from src.api.dependencies.service import get_academy_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.services.academy import AcademyService

router = fastapi.APIRouter(prefix="/boxing", tags=["boxing"])


class AttendanceUpdate(pydantic.BaseModel):
    attended: bool = pydantic.Field(strict=True)


class SubscriptionUpdate(pydantic.BaseModel):
    subscribed: bool = pydantic.Field(default=True, strict=True)


@router.get(
    path="/groups",
    name="boxing:groups",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_boxing_groups(
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> dict[str, typing.Any]:
    status_code, payload = await academy_service.list_groups()
    if status_code >= 400:
        return fastapi.responses.JSONResponse(status_code=status_code, content=payload)  # type: ignore[return-value]

    groups = [
        academy_service.normalize_group(row)
        for row in academy_service.extract_group_rows(payload, group_type="boxing")
    ]
    return {"ok": True, "data": {"groups": groups}}


@router.get(
    path="/trials",
    name="boxing:trials",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_boxing_trials(
    subscribed: bool | None = fastapi.Query(default=None),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> dict[str, typing.Any]:
    groups_status, groups_payload = await academy_service.list_groups()
    if groups_status >= 400:
        return fastapi.responses.JSONResponse(status_code=groups_status, content=groups_payload)  # type: ignore[return-value]

    group_rows = academy_service.extract_group_rows(groups_payload, group_type="boxing")
    groups_by_id = _unique_groups_by_id(group_rows)
    trials: list[dict[str, typing.Any]] = []

    for group_id in groups_by_id:
        detail_status, detail_payload = await academy_service.get_group_trials(group_id=group_id)
        if detail_status == fastapi.status.HTTP_404_NOT_FOUND:
            continue
        if detail_status >= 400:
            return fastapi.responses.JSONResponse(status_code=detail_status, content=detail_payload)  # type: ignore[return-value]

        raw_trials = detail_payload.get("data", {}).get("trials", []) if isinstance(detail_payload, dict) else []
        for trial in raw_trials:
            if isinstance(trial, dict):
                normalized = academy_service.normalize_trial(trial, groups_by_id=groups_by_id)
                if subscribed is None or normalized["subscribed"] is subscribed:
                    trials.append(normalized)

    return {"ok": True, "data": {"trials": trials}}


@router.get(
    path="/students",
    name="boxing:students",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_boxing_students(
    subscribed: bool | None = fastapi.Query(default=None),
    _: Account | None = fastapi.Depends(require_roles_or_manager_api_key(Role.ADMIN, Role.MANAGER)),
    academy_service: AcademyService = fastapi.Depends(get_academy_service),
) -> dict[str, typing.Any]:
    groups_status, groups_payload = await academy_service.list_groups()
    if groups_status >= 400:
        return fastapi.responses.JSONResponse(status_code=groups_status, content=groups_payload)  # type: ignore[return-value]

    group_rows = academy_service.extract_group_rows(groups_payload, group_type="boxing")
    groups_by_id = _unique_groups_by_id(group_rows)
    students_by_id: dict[str, dict[str, typing.Any]] = {}
    subscribed_by_user_id: dict[str, bool] = {}

    for group_id, group in groups_by_id.items():
        detail_status, detail_payload = await academy_service.get_group_trials(group_id=group_id)
        if detail_status == fastapi.status.HTTP_404_NOT_FOUND:
            continue
        if detail_status >= 400:
            return fastapi.responses.JSONResponse(status_code=detail_status, content=detail_payload)  # type: ignore[return-value]

        data = detail_payload.get("data", {}) if isinstance(detail_payload, dict) else {}
        for user in data.get("users", []):
            if isinstance(user, dict) and user.get("id") is not None:
                user_id = str(user["id"])
                students_by_id[user_id] = academy_service.normalize_student(
                    user=user,
                    group=group,
                    subscribed=subscribed_by_user_id.get(user_id, False),
                )

        for trial in data.get("trials", []):
            trial_user = trial.get("user") if isinstance(trial, dict) else None
            if isinstance(trial_user, dict) and trial_user.get("id") is not None:
                user_id = str(trial_user["id"])
                is_subscribed = bool(trial.get("subscribed"))
                subscribed_by_user_id[user_id] = subscribed_by_user_id.get(user_id, False) or is_subscribed
                students_by_id[user_id] = academy_service.normalize_student(
                    user=trial_user,
                    group=group,
                    subscribed=subscribed_by_user_id[user_id],
                )

    students = [
        student
        for student in students_by_id.values()
        if subscribed is None or student["subscribed"] is subscribed
    ]
    return {"ok": True, "data": {"students": students}}


@router.patch(
    path="/trials/{trial_id}/attended",
    name="boxing:trial-attended",
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
    name="boxing:trial-subscribed",
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
    name="boxing:student-subscribed",
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


def _unique_groups_by_id(group_rows: list[dict[str, typing.Any]]) -> dict[int, dict[str, typing.Any]]:
    groups_by_id: dict[int, dict[str, typing.Any]] = {}
    for row in group_rows:
        group_id = row.get("group_id") or row.get("id")
        if group_id is None:
            continue
        groups_by_id.setdefault(int(group_id), row)
    return groups_by_id
