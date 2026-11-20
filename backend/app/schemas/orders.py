from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CoffeeSize(str, Enum):
    S = "S"
    M = "M"
    L = "L"


class MilkType(str, Enum):
    NONE = "NONE"
    WHOLE = "WHOLE"
    OAT = "OAT"
    ALMOND = "ALMOND"
    LACTOSE_FREE = "LACTOSE_FREE"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    PREPARING = "PREPARING"
    READY = "READY"
    DELIVERED = "DELIVERED"


class OrderCustomizations(BaseModel):
    size: CoffeeSize = CoffeeSize.M
    sugar_level: int = Field(default=0, ge=0, le=5)
    milk_type: MilkType = MilkType.WHOLE
    extra_shots: int = Field(default=0, ge=0, le=3)


class OrderCreateRequest(BaseModel):
    shop_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    customizations: OrderCustomizations = Field(
        default_factory=OrderCustomizations
    )


class QRCodeClaims(BaseModel):
    order_id: UUID
    user_id: UUID
    shop_id: UUID
    created_at: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("QR created_at zaman dilimi içermelidir.")
        return value.astimezone(timezone.utc)


class QRCodePayload(QRCodeClaims):
    signature: str = Field(pattern=r"^[a-f0-9]{64}$")


class OrderResponse(BaseModel):
    id: int
    shop_id: int
    shop_name: str
    customer_name: str
    customer_phone: str
    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal
    customizations: OrderCustomizations
    status: OrderStatus
    qr_code: QRCodePayload | None
    created_at: datetime


class OrderStatusUpdateRequest(BaseModel):
    status: OrderStatus


class FavoriteOrderResponse(BaseModel):
    order_id: int
    is_favorite: bool


class QRVerificationResponse(BaseModel):
    valid: bool
    order_id: UUID | None
    status: OrderStatus | None
    message: str
