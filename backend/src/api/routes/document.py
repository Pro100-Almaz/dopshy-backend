import fastapi

from src.api.dependencies.auth import require_roles
from src.api.dependencies.service import get_document_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.models.schemas.document import DocumentExtractIn
from src.services.document import DocumentService

router = fastapi.APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    path="/extract",
    name="documents:extract",
    status_code=fastapi.status.HTTP_200_OK,
)
async def extract_document(
    payload: DocumentExtractIn,
    current_user: Account = fastapi.Depends(
        require_roles(Role.ADMIN, Role.ARENA_MANAGER),
    ),
    document_service: DocumentService = fastapi.Depends(get_document_service),
) -> fastapi.Response:
    filename, content = await document_service.generate_document(
        payload=payload,
        current_user=current_user,
    )
    return fastapi.Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
