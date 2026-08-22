import os
import typing

import fastapi
import httpx

from src.config.manager import settings


class AcademyService:
    async def _request(
        self,
        method: str,
        path: str,
        json: typing.Any | None = None,
    ) -> tuple[int, typing.Any]:
        base_url = settings.BOT_URL
        if not base_url:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="BOT_URL is not configured.",
            )

        url = base_url.rstrip("/") + path
        headers = {
            "Accept": "application/json",
            "X-API-Key": os.getenv("MANAGER_API_KEY") or settings.MANAGER_API_KEY or "",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.request(method, url, headers=headers, json=json)
            except httpx.HTTPError as exc:
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to reach the bot service.",
                ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="Bot service returned a non-JSON response.",
            ) from exc

        if response.status_code in (
            fastapi.status.HTTP_401_UNAUTHORIZED,
            fastapi.status.HTTP_403_FORBIDDEN,
        ):
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="Bot service authentication failed. Check MANAGER_API_KEY between backend and bot.",
            )

        return response.status_code, payload

    async def list_groups(self) -> tuple[int, typing.Any]:
        return await self._request("GET", "/api/manager/academy_groups")

    async def get_group_trials(self, group_id: int) -> tuple[int, typing.Any]:
        return await self._request("GET", f"/api/manager/academy_groups/{group_id}/trials")

    async def update_group(self, group_id: int, payload: dict[str, typing.Any]) -> tuple[int, typing.Any]:
        return await self._request(
            "PATCH",
            f"/api/manager/academy_groups/{group_id}",
            json=payload,
        )

    async def set_trial_attended(self, trial_id: int, attended: bool) -> tuple[int, typing.Any]:
        return await self._request(
            "PATCH",
            f"/api/manager/academy_trials/{trial_id}/attended",
            json={"attended": attended},
        )

    async def set_trial_subscribed(self, trial_id: int, subscribed: bool) -> tuple[int, typing.Any]:
        return await self._request(
            "PATCH",
            f"/api/manager/academy_trials/{trial_id}/subscribed",
            json={"subscribed": subscribed},
        )

    async def set_student_subscribed(self, student_id: int, subscribed: bool) -> tuple[int, typing.Any]:
        return await self._request(
            "PATCH",
            f"/api/manager/academy_users/{student_id}/subscribed",
            json={"subscribed": subscribed},
        )

    def extract_group_rows(self, payload: typing.Any, group_type: str | None = None) -> list[dict[str, typing.Any]]:
        if not isinstance(payload, dict):
            return []

        groups_by_type = payload.get("data", {}).get("groups", {})
        if not isinstance(groups_by_type, dict):
            return []

        rows: list[dict[str, typing.Any]] = []
        for current_type, group_rows in groups_by_type.items():
            if group_type is not None and current_type != group_type:
                continue
            if isinstance(group_rows, list):
                rows.extend(row for row in group_rows if isinstance(row, dict))
        return rows

    def normalize_group(
        self,
        row: dict[str, typing.Any],
        group_type: str = "boxing",
    ) -> dict[str, typing.Any]:
        group_id = row.get("group_id") or row.get("id")
        training_day = row.get("training_day_label") or row.get("training_day")
        return {
            "id": str(group_id) if group_id is not None else "",
            "group_id": group_id,
            "group_type": row.get("group_type") or group_type,
            "group_name": row.get("group_name") or "",
            "max_cap": row.get("max_cap"),
            "curr_cap": row.get("curr_cap"),
            "training_day": str(training_day) if training_day is not None else "",
            "training_day_value": row.get("training_day"),
            "training_day_label": row.get("training_day_label") or "",
            "start_time": row.get("start_time") or "",
            "end_time": row.get("end_time") or "",
        }

    def normalize_trial(
        self,
        trial: dict[str, typing.Any],
        groups_by_id: dict[int, dict[str, typing.Any]],
    ) -> dict[str, typing.Any]:
        raw_group_id = trial.get("group_id")
        group_id = int(raw_group_id) if raw_group_id is not None else None
        group = groups_by_id.get(group_id) if group_id is not None else None
        user = trial.get("user") if isinstance(trial.get("user"), dict) else None

        return {
            "id": str(trial.get("trial_id") or trial.get("id") or ""),
            "trial_id": trial.get("trial_id") or trial.get("id"),
            "group_id": str(raw_group_id) if raw_group_id is not None else "",
            "assigned_group_id": str(raw_group_id) if raw_group_id is not None else None,
            "assigned_group_name": group.get("group_name") if group else None,
            "child_name": trial.get("child_name") or "",
            "child_age": trial.get("child_age"),
            "birthdate": user.get("birthdate") if user else "",
            "language": trial.get("language") or "",
            "phone": trial.get("phone") or "",
            "trial_day": trial.get("trial_day") or "",
            "start_time": trial.get("start_time") or "",
            "end_time": trial.get("end_time") or "",
            "state": trial.get("state") or "",
            "state_label": trial.get("state_label") or "",
            "notes": trial.get("notes") or "",
            "attended": bool(trial.get("attended")),
            "subscribed": bool(trial.get("subscribed")),
            "user": user,
        }

    def normalize_student(
        self,
        user: dict[str, typing.Any],
        group: dict[str, typing.Any] | None,
        subscribed: bool,
    ) -> dict[str, typing.Any]:
        group_id = user.get("assigned_group_id")
        return {
            "id": str(user.get("id") or ""),
            "name": user.get("name") or user.get("child_name") or "",
            "age": user.get("age"),
            "birthdate": user.get("birthdate") or "",
            "parent_phone": user.get("parent_phone") or "",
            "total_trials": user.get("total_trials") or 0,
            "assigned_group": group.get("group_name") if group else "",
            "assigned_group_id": str(group_id) if group_id is not None else None,
            "assigned_group_name": group.get("group_name") if group else None,
            "subscribed": subscribed,
        }
