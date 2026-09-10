import typing

import fastapi

from src.services.academy import AcademyService


async def list_groups_by_type(
    group_type: str,
    academy_service: AcademyService,
) -> dict[str, typing.Any]:
    status_code, payload = await academy_service.list_sport_groups(group_type)
    if status_code >= 400:
        return fastapi.responses.JSONResponse(status_code=status_code, content=payload)  # type: ignore[return-value]

    raw_groups = payload.get("data", {}).get("groups") if isinstance(payload, dict) else None
    if isinstance(raw_groups, list):
        return payload

    groups = [
        academy_service.normalize_group(row, group_type=group_type)
        for row in academy_service.extract_group_rows(payload, group_type=group_type)
    ]
    return {"ok": True, "data": {"groups": groups}}


async def create_group_by_type(
    group_type: str,
    payload: dict[str, typing.Any],
    academy_service: AcademyService,
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.create_sport_group(group_type, payload=payload)
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


async def update_group_by_type(
    group_type: str,
    group_id: int,
    payload: dict[str, typing.Any],
    academy_service: AcademyService,
) -> fastapi.responses.JSONResponse:
    if not payload:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail="At least one group field must be provided.",
        )
    status_code, response_payload = await academy_service.update_sport_group(
        group_type,
        group_id=group_id,
        payload=payload,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


async def delete_group_by_type(
    group_type: str,
    group_id: int,
    academy_service: AcademyService,
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.delete_sport_group(group_type, group_id=group_id)
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


async def assign_student_to_group_by_type(
    group_type: str,
    group_id: int,
    payload: dict[str, typing.Any],
    academy_service: AcademyService,
) -> fastapi.responses.JSONResponse:
    status_code, response_payload = await academy_service.assign_sport_student_to_group(
        group_type,
        group_id=group_id,
        payload=payload,
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


async def list_trials_by_type(
    group_type: str,
    subscribed: bool | None,
    academy_service: AcademyService,
) -> dict[str, typing.Any]:
    status_code, payload = await academy_service.list_sport_trials(group_type, subscribed=subscribed)
    if status_code >= 400:
        return fastapi.responses.JSONResponse(status_code=status_code, content=payload)  # type: ignore[return-value]

    raw_trials = payload.get("data", {}).get("trials") if isinstance(payload, dict) else None
    if isinstance(raw_trials, list):
        return payload

    group_rows = academy_service.extract_group_rows(payload, group_type=group_type)
    groups_by_id = unique_groups_by_id(group_rows)
    trials: list[dict[str, typing.Any]] = []

    for group_id in groups_by_id:
        detail_status, detail_payload = await academy_service.get_group_trials(group_id=group_id)
        if detail_status == fastapi.status.HTTP_404_NOT_FOUND:
            continue
        if detail_status >= 400:
            return fastapi.responses.JSONResponse(status_code=detail_status, content=detail_payload)  # type: ignore[return-value]

        raw_group_trials = detail_payload.get("data", {}).get("trials", []) if isinstance(detail_payload, dict) else []
        for trial in raw_group_trials:
            if isinstance(trial, dict):
                normalized = academy_service.normalize_trial(trial, groups_by_id=groups_by_id)
                if subscribed is None or normalized["subscribed"] is subscribed:
                    trials.append(normalized)

    return {"ok": True, "data": {"trials": trials}}


async def list_students_by_type(
    group_type: str,
    subscribed: bool | None,
    academy_service: AcademyService,
) -> dict[str, typing.Any]:
    status_code, payload = await academy_service.list_sport_students(group_type, subscribed=subscribed)
    if status_code >= 400:
        return fastapi.responses.JSONResponse(status_code=status_code, content=payload)  # type: ignore[return-value]

    raw_students = payload.get("data", {}).get("students") if isinstance(payload, dict) else None
    if isinstance(raw_students, list):
        return payload

    group_rows = academy_service.extract_group_rows(payload, group_type=group_type)
    groups_by_id = unique_groups_by_id(group_rows)
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


async def list_payments_by_type(
    group_type: str,
    academy_service: AcademyService,
) -> fastapi.responses.JSONResponse:
    status_code, payload = await academy_service.list_sport_payments(group_type)
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


async def get_bot_content_by_type(
    group_type: str,
    academy_service: AcademyService,
) -> fastapi.responses.JSONResponse:
    status_code, payload = await academy_service.get_sport_bot_content(group_type)
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


def unique_groups_by_id(group_rows: list[dict[str, typing.Any]]) -> dict[int, dict[str, typing.Any]]:
    groups_by_id: dict[int, dict[str, typing.Any]] = {}
    for row in group_rows:
        group_id = row.get("group_id") or row.get("id")
        if group_id is None:
            continue
        groups_by_id.setdefault(int(group_id), row)
    return groups_by_id
