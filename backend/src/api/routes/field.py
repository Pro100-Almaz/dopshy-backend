import fastapi

from src.api.dependencies.auth import get_current_user, require_roles
from src.api.dependencies.service import get_field_service
from src.models.db.account import Account
from src.models.enums.role import Role
from src.models.schemas.field import FieldInCreate, FieldInUpdate, FieldListOut, FieldOut, PricingRuleIn
from src.services.field import FieldService
from src.utilities.exceptions.database import EntityDoesNotExist
from src.utilities.exceptions.http.exc_404 import http_404_exc_field_not_found_request

router = fastapi.APIRouter(prefix="/fields", tags=["fields"])


@router.post(
    path="",
    name="fields:create-field",
    response_model=FieldOut,
    status_code=fastapi.status.HTTP_201_CREATED,
)
async def create_field(
    field_in: FieldInCreate,
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    field_service: FieldService = fastapi.Depends(get_field_service),
) -> FieldOut:
    return await field_service.create_field(field_create=field_in)


@router.get(
    path="",
    name="fields:list-fields",
    response_model=list[FieldListOut],
    status_code=fastapi.status.HTTP_200_OK,
)
async def list_fields(
    include_inactive: bool = False,
    field_service: FieldService = fastapi.Depends(get_field_service),
) -> list[FieldListOut]:
    return await field_service.get_fields(include_inactive=include_inactive)


@router.get(
    path="/{id}",
    name="fields:get-field",
    response_model=FieldOut,
    status_code=fastapi.status.HTTP_200_OK,
)
async def get_field(
    id: int,
    field_service: FieldService = fastapi.Depends(get_field_service),
) -> FieldOut:
    try:
        return await field_service.get_field_by_id(id=id)
    except EntityDoesNotExist:
        raise await http_404_exc_field_not_found_request(id=id)


@router.patch(
    path="/{id}",
    name="fields:update-field",
    response_model=FieldOut,
    status_code=fastapi.status.HTTP_200_OK,
)
async def update_field(
    id: int,
    field_in: FieldInUpdate,
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    field_service: FieldService = fastapi.Depends(get_field_service),
) -> FieldOut:
    try:
        return await field_service.update_field(id=id, field_update=field_in)
    except EntityDoesNotExist:
        raise await http_404_exc_field_not_found_request(id=id)


@router.delete(
    path="/{id}",
    name="fields:delete-field",
    status_code=fastapi.status.HTTP_200_OK,
)
async def delete_field(
    id: int,
    _: Account = fastapi.Depends(require_roles(Role.ADMIN)),
    field_service: FieldService = fastapi.Depends(get_field_service),
) -> dict[str, str]:
    try:
        return await field_service.delete_field(id=id)
    except EntityDoesNotExist:
        raise await http_404_exc_field_not_found_request(id=id)


@router.put(
    path="/{id}/pricing-rules",
    name="fields:replace-pricing-rules",
    response_model=FieldOut,
    status_code=fastapi.status.HTTP_200_OK,
)
async def replace_pricing_rules(
    id: int,
    rules: list[PricingRuleIn],
    _: Account = fastapi.Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    field_service: FieldService = fastapi.Depends(get_field_service),
) -> FieldOut:
    try:
        return await field_service.replace_pricing_rules(field_id=id, rules=rules)
    except EntityDoesNotExist:
        raise await http_404_exc_field_not_found_request(id=id)
