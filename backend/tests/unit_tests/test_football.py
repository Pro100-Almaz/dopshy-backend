import typing

import pytest

from src.api.routes.football import (
    assign_student_to_football_group,
    create_football_group,
    delete_football_group,
    list_football_groups,
    list_football_students,
    list_football_trials,
    set_student_subscribed,
    set_trial_attended,
    set_trial_subscribed,
    update_football_group,
)
from src.api.routes.football import AttendanceUpdate, SubscriptionUpdate
from src.services.academy import AcademyService


class FakeAcademyService(AcademyService):
    async def list_groups(self) -> tuple[int, typing.Any]:
        return 200, {
            "ok": True,
            "data": {
                "groups": {
                    "boxing": [
                        {
                            "group_id": 1,
                            "group_name": "Boxing Kids A",
                            "group_type": "boxing",
                        }
                    ],
                    "football": [
                        {
                            "group_id": 2,
                            "group_name": "Football Kids A",
                            "max_cap": 18,
                            "curr_cap": 6,
                            "training_day": 1,
                            "training_day_label": "Вторник",
                            "start_time": "12:00",
                            "end_time": "13:00",
                            "age_min": 7,
                            "age_max": 9,
                            "shift": "morning",
                            "is_active": True,
                        },
                        {
                            "group_id": 2,
                            "group_name": "Football Kids A",
                            "group_type": "football",
                            "max_cap": 18,
                            "curr_cap": 6,
                            "training_day": 3,
                            "training_day_label": "Четверг",
                            "start_time": "12:00",
                            "end_time": "13:00",
                        },
                    ],
                }
            },
        }

    async def get_group_trials(self, group_id: int) -> tuple[int, typing.Any]:
        assert group_id == 2
        return 200, {
            "ok": True,
            "data": {
                "users": [
                    {
                        "id": 22,
                        "name": "Subscribed Football Child",
                        "age": 9,
                        "birthdate": "2017-04-12",
                        "parent_phone": "77001234567",
                        "total_trials": 2,
                        "assigned_group_id": 2,
                    },
                    {
                        "id": 23,
                        "name": "Trial Football Child",
                        "age": 8,
                        "birthdate": "2018-02-10",
                        "parent_phone": "77007654321",
                        "total_trials": 1,
                        "assigned_group_id": 2,
                    },
                ],
                "trials": [
                    {
                        "trial_id": 54,
                        "child_name": "Subscribed Football Child",
                        "child_age": 9,
                        "language": "ru",
                        "phone": "77001234567",
                        "group_id": 2,
                        "trial_day": "2026-08-15",
                        "start_time": "12:00",
                        "end_time": "13:00",
                        "state": "confirmed",
                        "notes": "",
                        "attended": True,
                        "subscribed": True,
                        "user": {
                            "id": 22,
                            "name": "Subscribed Football Child",
                            "age": 9,
                            "birthdate": "2017-04-12",
                            "parent_phone": "77001234567",
                            "total_trials": 2,
                            "assigned_group_id": 2,
                        },
                    },
                    {
                        "trial_id": 55,
                        "child_name": "Trial Football Child",
                        "child_age": 8,
                        "language": "kz",
                        "phone": "77007654321",
                        "group_id": 2,
                        "trial_day": "2026-08-16",
                        "start_time": "12:00",
                        "end_time": "13:00",
                        "state": "confirmed",
                        "notes": "Bring boots",
                        "attended": False,
                        "subscribed": False,
                        "user": {
                            "id": 23,
                            "name": "Trial Football Child",
                            "age": 8,
                            "birthdate": "2018-02-10",
                            "parent_phone": "77007654321",
                            "total_trials": 1,
                            "assigned_group_id": 2,
                        },
                    },
                ],
            },
        }

    async def set_trial_attended(self, trial_id: int, attended: bool) -> tuple[int, typing.Any]:
        return 200, {"ok": True, "data": {"trial_id": trial_id, "attended": attended}}

    async def set_trial_subscribed(self, trial_id: int, subscribed: bool) -> tuple[int, typing.Any]:
        return 200, {"ok": True, "data": {"trial_id": trial_id, "subscribed": subscribed}}

    async def set_student_subscribed(self, student_id: int, subscribed: bool) -> tuple[int, typing.Any]:
        return 200, {"ok": True, "data": {"id": student_id, "subscribed": subscribed}}

    async def create_sport_group(self, sport: str, payload: dict[str, typing.Any]) -> tuple[int, typing.Any]:
        assert sport == "football"
        return 200, {"ok": True, "data": {"group_id": 2, **payload}}

    async def update_sport_group(
        self,
        sport: str,
        group_id: int,
        payload: dict[str, typing.Any],
    ) -> tuple[int, typing.Any]:
        assert sport == "football"
        return 200, {"ok": True, "data": {"group_id": group_id, **payload}}

    async def delete_sport_group(self, sport: str, group_id: int) -> tuple[int, typing.Any]:
        assert sport == "football"
        return 200, {"ok": True, "data": {"group_id": group_id, "is_active": False}}

    async def assign_sport_student_to_group(
        self,
        sport: str,
        group_id: int,
        payload: dict[str, typing.Any],
    ) -> tuple[int, typing.Any]:
        assert sport == "football"
        return 200, {"ok": True, "data": {"group_id": group_id, **payload}}


@pytest.mark.asyncio
async def test_list_football_groups_returns_mock_compatible_rows() -> None:
    response = await list_football_groups(academy_service=FakeAcademyService())

    groups = response["data"]["groups"]
    assert len(groups) == 2
    assert groups[0]["id"] == "2"
    assert groups[0]["group_id"] == 2
    assert groups[0]["group_type"] == "football"
    assert groups[0]["training_day"] == "Вторник"
    assert groups[0]["training_day_value"] == 1
    assert groups[0]["age_min"] == 7
    assert groups[0]["age_max"] == 9
    assert groups[0]["shift"] == "morning"
    assert groups[0]["is_active"] is True


@pytest.mark.asyncio
async def test_list_football_trials_filters_unsubscribed_and_adds_group_name() -> None:
    response = await list_football_trials(subscribed=False, academy_service=FakeAcademyService())

    trials = response["data"]["trials"]
    assert len(trials) == 1
    assert trials[0]["id"] == "55"
    assert trials[0]["assigned_group_id"] == "2"
    assert trials[0]["assigned_group_name"] == "Football Kids A"
    assert trials[0]["birthdate"] == "2018-02-10"
    assert trials[0]["subscribed"] is False


@pytest.mark.asyncio
async def test_list_football_students_filters_subscribed() -> None:
    response = await list_football_students(subscribed=True, academy_service=FakeAcademyService())

    students = response["data"]["students"]
    assert len(students) == 1
    assert students[0]["id"] == "22"
    assert students[0]["assigned_group"] == "Football Kids A"
    assert students[0]["assigned_group_id"] == "2"
    assert students[0]["subscribed"] is True


@pytest.mark.asyncio
async def test_football_mutations_proxy_to_academy_service() -> None:
    group_create = await create_football_group(
        payload={"group_name": "Football Kids A"},
        academy_service=FakeAcademyService(),
    )
    group_update = await update_football_group(
        group_id=2,
        payload={"max_cap": 18},
        academy_service=FakeAcademyService(),
    )
    group_delete = await delete_football_group(
        group_id=2,
        academy_service=FakeAcademyService(),
    )
    assign_student = await assign_student_to_football_group(
        group_id=2,
        payload={"student_id": "22"},
        academy_service=FakeAcademyService(),
    )
    attended = await set_trial_attended(
        trial_id=54,
        payload=AttendanceUpdate(attended=True),
        academy_service=FakeAcademyService(),
    )
    trial_subscribed = await set_trial_subscribed(
        trial_id=54,
        payload=SubscriptionUpdate(subscribed=True),
        academy_service=FakeAcademyService(),
    )
    student_subscribed = await set_student_subscribed(
        student_id=22,
        payload=SubscriptionUpdate(subscribed=True),
        academy_service=FakeAcademyService(),
    )

    assert group_create.status_code == 200
    assert group_update.status_code == 200
    assert group_delete.status_code == 200
    assert assign_student.status_code == 200
    assert attended.status_code == 200
    assert trial_subscribed.status_code == 200
    assert student_subscribed.status_code == 200
