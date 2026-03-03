import datetime
import decimal

import sqlalchemy
from sqlalchemy.orm import Mapped as SQLAlchemyMapped, mapped_column as sqlalchemy_mapped_column, relationship
from sqlalchemy.sql import functions as sqlalchemy_functions

from src.repository.table import Base


class Field(Base):  # type: ignore
    __tablename__ = "field"

    id: SQLAlchemyMapped[int] = sqlalchemy_mapped_column(primary_key=True, autoincrement="auto")
    name: SQLAlchemyMapped[str] = sqlalchemy_mapped_column(sqlalchemy.String(length=128), nullable=False)
    description: SQLAlchemyMapped[str | None] = sqlalchemy_mapped_column(sqlalchemy.Text, nullable=True)
    surface_type: SQLAlchemyMapped[str] = sqlalchemy_mapped_column(sqlalchemy.String(length=32), nullable=False)
    size: SQLAlchemyMapped[str] = sqlalchemy_mapped_column(sqlalchemy.String(length=8), nullable=False)
    base_price: SQLAlchemyMapped[decimal.Decimal] = sqlalchemy_mapped_column(
        sqlalchemy.Numeric(precision=10, scale=2), nullable=False
    )
    is_active: SQLAlchemyMapped[bool] = sqlalchemy_mapped_column(sqlalchemy.Boolean, nullable=False, default=True)
    created_at: SQLAlchemyMapped[datetime.datetime] = sqlalchemy_mapped_column(
        sqlalchemy.DateTime(timezone=True), nullable=False, server_default=sqlalchemy_functions.now()
    )
    updated_at: SQLAlchemyMapped[datetime.datetime | None] = sqlalchemy_mapped_column(
        sqlalchemy.DateTime(timezone=True),
        nullable=True,
        server_onupdate=sqlalchemy.schema.FetchedValue(for_update=True),
    )

    pricing_rules: SQLAlchemyMapped[list["FieldPricingRule"]] = relationship(
        "FieldPricingRule", back_populates="field", cascade="all, delete-orphan"
    )
    bookings: SQLAlchemyMapped[list["Booking"]] = relationship(  # type: ignore[name-defined]
        "Booking", back_populates="field"
    )

    __mapper_args__ = {"eager_defaults": True}


class FieldPricingRule(Base):  # type: ignore
    __tablename__ = "field_pricing_rule"
    __table_args__ = (sqlalchemy.UniqueConstraint("field_id", "day_of_week", name="uq_field_day"),)

    id: SQLAlchemyMapped[int] = sqlalchemy_mapped_column(primary_key=True, autoincrement="auto")
    field_id: SQLAlchemyMapped[int] = sqlalchemy_mapped_column(
        sqlalchemy.ForeignKey("field.id", ondelete="CASCADE"), nullable=False
    )
    day_of_week: SQLAlchemyMapped[int] = sqlalchemy_mapped_column(sqlalchemy.SmallInteger, nullable=False)
    price: SQLAlchemyMapped[decimal.Decimal] = sqlalchemy_mapped_column(
        sqlalchemy.Numeric(precision=10, scale=2), nullable=False
    )

    field: SQLAlchemyMapped["Field"] = relationship("Field", back_populates="pricing_rules")
