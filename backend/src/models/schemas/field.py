import decimal

import pydantic

from src.models.enums.field import FieldSize, SurfaceType


class PricingRuleIn(pydantic.BaseModel):
    day_of_week: int = pydantic.Field(ge=0, le=6)
    price: decimal.Decimal = pydantic.Field(gt=0)


class PricingRuleOut(pydantic.BaseModel):
    id: int
    field_id: int
    day_of_week: int
    price: decimal.Decimal

    model_config = pydantic.ConfigDict(from_attributes=True)


class FieldInCreate(pydantic.BaseModel):
    name: str = pydantic.Field(max_length=128)
    description: str | None = None
    surface_type: SurfaceType
    size: FieldSize
    base_price: decimal.Decimal = pydantic.Field(gt=0)
    pricing_rules: list[PricingRuleIn] = []


class FieldInUpdate(pydantic.BaseModel):
    name: str | None = pydantic.Field(default=None, max_length=128)
    description: str | None = None
    surface_type: SurfaceType | None = None
    size: FieldSize | None = None
    base_price: decimal.Decimal | None = pydantic.Field(default=None, gt=0)
    is_active: bool | None = None


class FieldOut(pydantic.BaseModel):
    id: int
    name: str
    description: str | None
    surface_type: str
    size: str
    base_price: decimal.Decimal
    is_active: bool
    pricing_rules: list[PricingRuleOut] = []

    model_config = pydantic.ConfigDict(from_attributes=True)


class FieldListOut(pydantic.BaseModel):
    id: int
    name: str
    surface_type: str
    size: str
    base_price: decimal.Decimal
    is_active: bool

    model_config = pydantic.ConfigDict(from_attributes=True)
