from types import SimpleNamespace

import fastapi
import httpx
import pytest

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.service import get_history_service
from src.api.routes.history import router
from src.models.enums.role import Role


class FakeHistoryService:
    async def list_history(self, **kwargs):
        return {"items": [], "filters": kwargs}


@pytest.mark.parametrize(
    ("role", "expected_status"),
    [
        (Role.SUPER_ADMIN, fastapi.status.HTTP_200_OK),
        (Role.ADMIN, fastapi.status.HTTP_200_OK),
        (Role.MANAGER, fastapi.status.HTTP_200_OK),
        (Role.ARENA_MANAGER, fastapi.status.HTTP_200_OK),
        (Role.FOOTBALL_MANAGER, fastapi.status.HTTP_200_OK),
        (Role.BOXING_MANAGER, fastapi.status.HTTP_403_FORBIDDEN),
        (Role.CLIENT, fastapi.status.HTTP_403_FORBIDDEN),
    ],
)
@pytest.mark.asyncio
async def test_list_history_role_access(role: Role, expected_status: int) -> None:
    app = fastapi.FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=role.value)
    app.dependency_overrides[get_history_service] = FakeHistoryService

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/manager/history?page=1&page_size=20")

    assert response.status_code == expected_status
