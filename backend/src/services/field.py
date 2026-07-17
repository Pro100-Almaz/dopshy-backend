import typing

import fastapi
import httpx

from src.config.manager import settings
from src.models.db.field import Field
from src.models.schemas.field import FieldInCreate, FieldInUpdate, FieldListOut, FieldOut, PricingRuleIn, \
    PricingRuleOut, BotPriceRow, BotFieldRow, BotFieldResponse
from src.repository.crud.field import FieldCRUDRepository


class FieldService:
    def __init__(self, field_repo: FieldCRUDRepository) -> None:
        self.field_repo = field_repo

    def _to_field_out(self, field: Field) -> FieldOut:
        return FieldOut(
            id=field.id,
            name=field.name,
            description=field.description,
            surface_type=field.surface_type,
            size=field.size,
            base_price=field.base_price,
            is_active=field.is_active,
            pricing_rules=[
                PricingRuleOut(id=r.id, field_id=r.field_id, day_of_week=r.day_of_week, price=r.price)
                for r in field.pricing_rules
            ],
        )

    async def create_field(self, field_create: FieldInCreate) -> FieldOut:
        field = await self.field_repo.create_field(field_create=field_create)
        return self._to_field_out(field)


    async def get_fields(self) -> BotFieldResponse:
        base_url = settings.BOT_URL
        if not base_url:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail=", BOT_URL is not configured.",
            )

        url = base_url.rstrip("/") + "/api/manager/fields"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers={"Content-Type": "application/json", "Accept": "application/json", "X-API-KEY": settings.MANAGER_API_KEY})
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to fetch bookings from the bot service.",
                ) from exc

        payload = response.json()
        prices = payload.get("data").get("prices") or []
        fields = payload.get("data").get("fields") or []

        prices_data = [BotPriceRow.model_validate(p) for p in prices]
        fields_data = [BotFieldRow.model_validate(f) for f in fields]

        data = BotFieldResponse.model_validate(dict(prices=prices_data, fields=fields_data))
        return data


    async def get_field_by_id(self, id: int) -> FieldOut:
        field = await self.field_repo.read_field_by_id(id=id)
        return self._to_field_out(field)

    async def update_field(self, id: int, field_update: FieldInUpdate) -> FieldOut:
        field = await self.field_repo.update_field_by_id(id=id, field_update=field_update)
        return self._to_field_out(field)

    async def delete_field(self, id: int) -> dict[str, str]:
        result = await self.field_repo.delete_field_by_id(id=id)
        return {"notification": result}

    async def replace_pricing_rules(self, field_id: int, rules: list[PricingRuleIn]) -> FieldOut:
        field = await self.field_repo.set_pricing_rules(field_id=field_id, rules=rules)
        return self._to_field_out(field)
