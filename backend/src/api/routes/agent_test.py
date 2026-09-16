"""Admin agent-test console.

Thin proxy to the bot service, which owns the agents. The value added here is
access control: the bot's console API is guarded only by a shared service key,
so the JWT role check below is what actually keeps the console to staff.
"""

import fastapi
import pydantic

from src.api.dependencies.auth import require_roles
from src.api.dependencies.service import get_agent_test_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.services.agent_test import AgentTestService

router = fastapi.APIRouter(prefix="/agent-test", tags=["agent-test"])

# SUPER_ADMIN is allowed implicitly by require_roles.
_STAFF = (Role.ADMIN, Role.MANAGER)


class SessionCreate(pydantic.BaseModel):
    bot_name: str
    title: str | None = None

    model_config = pydantic.ConfigDict(extra="forbid")


class MessageCreate(pydantic.BaseModel):
    text: str | None = None
    button_title: str | None = None

    model_config = pydantic.ConfigDict(extra="forbid")


@router.get(
    path="/bots",
    name="agent-test:list-bots",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_bots(
    _: Account = fastapi.Depends(require_roles(*_STAFF)),
    service: AgentTestService = fastapi.Depends(get_agent_test_service),
) -> fastapi.responses.JSONResponse:
    status_code, payload = await service.list_bots()
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


@router.get(
    path="/sessions",
    name="agent-test:list-sessions",
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_sessions(
    _: Account = fastapi.Depends(require_roles(*_STAFF)),
    service: AgentTestService = fastapi.Depends(get_agent_test_service),
) -> fastapi.responses.JSONResponse:
    status_code, payload = await service.list_sessions()
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


@router.post(
    path="/sessions",
    name="agent-test:create-session",
    status_code=fastapi.status.HTTP_200_OK,
)
async def create_session(
    body: SessionCreate,
    account: Account = fastapi.Depends(require_roles(*_STAFF)),
    service: AgentTestService = fastapi.Depends(get_agent_test_service),
) -> fastapi.responses.JSONResponse:
    payload = body.model_dump(exclude_none=True)
    # Attribution comes from the JWT, never from the request body.
    payload["created_by"] = account.username
    status_code, response_payload = await service.create_session(payload=payload)
    return fastapi.responses.JSONResponse(status_code=status_code, content=response_payload)


@router.get(
    path="/sessions/{session_id}",
    name="agent-test:get-session",
    status_code=fastapi.status.HTTP_200_OK,
)
async def get_session(
    session_id: int,
    _: Account = fastapi.Depends(require_roles(*_STAFF)),
    service: AgentTestService = fastapi.Depends(get_agent_test_service),
) -> fastapi.responses.JSONResponse:
    status_code, payload = await service.get_session(session_id=session_id)
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


@router.post(
    path="/sessions/{session_id}/messages",
    name="agent-test:send-message",
    status_code=fastapi.status.HTTP_200_OK,
)
async def send_message(
    session_id: int,
    body: MessageCreate,
    _: Account = fastapi.Depends(require_roles(*_STAFF)),
    service: AgentTestService = fastapi.Depends(get_agent_test_service),
) -> fastapi.responses.JSONResponse:
    status_code, payload = await service.send_message(
        session_id=session_id,
        payload=body.model_dump(exclude_none=True),
    )
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


@router.post(
    path="/sessions/{session_id}/reset",
    name="agent-test:reset-session",
    status_code=fastapi.status.HTTP_200_OK,
)
async def reset_session(
    session_id: int,
    _: Account = fastapi.Depends(require_roles(*_STAFF)),
    service: AgentTestService = fastapi.Depends(get_agent_test_service),
) -> fastapi.responses.JSONResponse:
    status_code, payload = await service.reset_session(session_id=session_id)
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)


@router.delete(
    path="/sessions/{session_id}",
    name="agent-test:delete-session",
    status_code=fastapi.status.HTTP_200_OK,
)
async def delete_session(
    session_id: int,
    _: Account = fastapi.Depends(require_roles(*_STAFF)),
    service: AgentTestService = fastapi.Depends(get_agent_test_service),
) -> fastapi.responses.JSONResponse:
    status_code, payload = await service.delete_session(session_id=session_id)
    return fastapi.responses.JSONResponse(status_code=status_code, content=payload)
