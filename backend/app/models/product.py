from __future__ import annotations

from decimal import Decimal
import json
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, JSON, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

DEFAULT_SIZE_PRICE_DELTAS = {"S": "0.00", "M": "0.00", "L": "0.00"}
DEFAULT_MILK_PRICE_DELTAS = {
    "NONE": "0.00",
    "WHOLE": "0.00",
    "OAT": "0.00",
    "ALMOND": "0.00",
    "LACTOSE_FREE": "0.00",
}

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.shop import Shop


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="COFFEE")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    size_price_deltas: Mapped[dict[str, str]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: DEFAULT_SIZE_PRICE_DELTAS.copy(),
        server_default=text(
            "'"
            + json.dumps(DEFAULT_SIZE_PRICE_DELTAS, separators=(",", ":"))
            + "'"
        ),
    )
    milk_price_deltas: Mapped[dict[str, str]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: DEFAULT_MILK_PRICE_DELTAS.copy(),
        server_default=text(
            "'"
            + json.dumps(DEFAULT_MILK_PRICE_DELTAS, separators=(",", ":"))
            + "'"
        ),
    )
    extra_shot_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )
    is_available: Mapped[bool] = mapped_column(default=True)

    shop: Mapped[Shop] = relationship(back_populates="products")
    orders: Mapped[list[Order]] = relationship(back_populates="product")
