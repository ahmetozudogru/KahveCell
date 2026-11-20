from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.roles import UserRole
from app.db.database import Base


if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.shop import Shop
    from app.models.shop_rating import ShopRating
    from app.models.subscription import Subscription


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone_number: Mapped[str] = mapped_column(String(15), unique=True, index=True)
    username: Mapped[str | None] = mapped_column(
        String(15), unique=True, index=True, nullable=True
    )
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.CUSTOMER.value)
    preferences: Mapped[str | None] = mapped_column(String, nullable=True)
    phone_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    profile_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="user")
    orders: Mapped[list[Order]] = relationship(back_populates="user")
    shops: Mapped[list[Shop]] = relationship(
        back_populates="owner", foreign_keys="Shop.owner_id"
    )
    shop_ratings: Mapped[list[ShopRating]] = relationship(back_populates="user")
