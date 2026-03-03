import decimal
import typing

import sqlalchemy
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import functions as sqlalchemy_functions

from src.models.db.field import Field, FieldPricingRule
from src.models.schemas.field import FieldInCreate, FieldInUpdate, PricingRuleIn
from src.repository.crud.base import BaseCRUDRepository
from src.utilities.exceptions.database import EntityDoesNotExist


class FieldCRUDRepository(BaseCRUDRepository):
    async def create_field(self, field_create: FieldInCreate) -> Field:
        new_field = Field(
            name=field_create.name,
            description=field_create.description,
            surface_type=field_create.surface_type.value,
            size=field_create.size.value,
            base_price=field_create.base_price,
        )
        self.async_session.add(new_field)
        await self.async_session.flush()

        if field_create.pricing_rules:
            rules = [
                FieldPricingRule(field_id=new_field.id, day_of_week=r.day_of_week, price=r.price)
                for r in field_create.pricing_rules
            ]
            self.async_session.add_all(rules)

        await self.async_session.commit()
        await self.async_session.refresh(new_field)

        # reload with rules
        stmt = sqlalchemy.select(Field).where(Field.id == new_field.id).options(selectinload(Field.pricing_rules))
        result = await self.async_session.execute(stmt)
        return result.scalar_one()

    async def read_fields(self, include_inactive: bool = False) -> typing.Sequence[Field]:
        stmt = sqlalchemy.select(Field).options(selectinload(Field.pricing_rules))
        if not include_inactive:
            stmt = stmt.where(Field.is_active.is_(True))
        result = await self.async_session.execute(stmt)
        return result.scalars().all()

    async def read_field_by_id(self, id: int) -> Field:
        stmt = sqlalchemy.select(Field).where(Field.id == id).options(selectinload(Field.pricing_rules))
        result = await self.async_session.execute(stmt)
        field = result.scalar_one_or_none()
        if not field:
            raise EntityDoesNotExist(f"Field with id `{id}` does not exist!")
        return field

    async def update_field_by_id(self, id: int, field_update: FieldInUpdate) -> Field:
        field = await self.read_field_by_id(id=id)

        update_data = field_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == "surface_type":
                field.surface_type = value.value if hasattr(value, "value") else value
            elif key == "size":
                field.size = value.value if hasattr(value, "value") else value
            else:
                setattr(field, key, value)

        update_stmt = (
            sqlalchemy.update(Field).where(Field.id == id).values(updated_at=sqlalchemy_functions.now())
        )
        await self.async_session.execute(update_stmt)
        await self.async_session.commit()
        await self.async_session.refresh(field)

        stmt = sqlalchemy.select(Field).where(Field.id == id).options(selectinload(Field.pricing_rules))
        result = await self.async_session.execute(stmt)
        return result.scalar_one()

    async def delete_field_by_id(self, id: int) -> str:
        field = await self.read_field_by_id(id=id)
        stmt = sqlalchemy.delete(Field).where(Field.id == field.id)
        await self.async_session.execute(stmt)
        await self.async_session.commit()
        return f"Field with id '{id}' is successfully deleted!"

    async def set_pricing_rules(self, field_id: int, rules: list[PricingRuleIn]) -> Field:
        # verify field exists
        await self.read_field_by_id(id=field_id)

        # delete existing rules
        del_stmt = sqlalchemy.delete(FieldPricingRule).where(FieldPricingRule.field_id == field_id)
        await self.async_session.execute(del_stmt)

        # insert new batch
        if rules:
            new_rules = [
                FieldPricingRule(field_id=field_id, day_of_week=r.day_of_week, price=r.price)
                for r in rules
            ]
            self.async_session.add_all(new_rules)

        await self.async_session.commit()

        stmt = sqlalchemy.select(Field).where(Field.id == field_id).options(selectinload(Field.pricing_rules))
        result = await self.async_session.execute(stmt)
        return result.scalar_one()

    async def get_price_for_weekday(self, field_id: int, day_of_week: int) -> decimal.Decimal:
        rule_stmt = sqlalchemy.select(FieldPricingRule).where(
            FieldPricingRule.field_id == field_id,
            FieldPricingRule.day_of_week == day_of_week,
        )
        rule_result = await self.async_session.execute(rule_stmt)
        rule = rule_result.scalar_one_or_none()
        if rule:
            return rule.price

        field_stmt = sqlalchemy.select(Field.base_price).where(Field.id == field_id)
        field_result = await self.async_session.execute(field_stmt)
        return field_result.scalar_one()
