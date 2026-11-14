"""Validated extraction contract. Amounts are integer cents, never floats."""
from datetime import date
from pydantic import BaseModel, ConfigDict, Field

class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    quantity: int | None = Field(default=None, ge=1)
    price_cents: int | None = Field(default=None, ge=0)

class Order(BaseModel):
    model_config = ConfigDict(extra="forbid")
    restaurant: str | None = None
    provider: str | None = None
    order_reference: str | None = None
    order_date: date | None = None
    total_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    items: list[Item] = Field(default_factory=list)

class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    orders: list[Order] = Field(default_factory=list, max_length=100)
    warnings: list[str] = Field(default_factory=list)
