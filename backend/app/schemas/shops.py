from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.orders import CoffeeSize, MilkType


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str | None
    category: str
    price: Decimal
    size_price_deltas: dict[CoffeeSize, Decimal]
    milk_price_deltas: dict[MilkType, Decimal]
    extra_shot_price: Decimal
    is_available: bool


Money = Annotated[Decimal, Field(max_digits=10, decimal_places=2)]


class ProductUpsertRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    category: str = Field(min_length=1, max_length=50)
    price: Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
    size_price_deltas: dict[CoffeeSize, Money] = Field(
        default_factory=lambda: {
            size: Decimal("0.00") for size in CoffeeSize
        }
    )
    milk_price_deltas: dict[MilkType, Money] = Field(
        default_factory=lambda: {
            milk_type: Decimal("0.00") for milk_type in MilkType
        }
    )
    extra_shot_price: Annotated[
        Decimal, Field(ge=0, max_digits=10, decimal_places=2)
    ] = Decimal("0.00")

    @field_validator("name", "category")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Bu alan boş bırakılamaz.")
        return normalized_value

    @model_validator(mode="after")
    def validate_price_configuration(self) -> "ProductUpsertRequest":
        if set(self.size_price_deltas) != set(CoffeeSize):
            raise ValueError("S, M ve L boyutları için fiyat farkı gereklidir.")
        if set(self.milk_price_deltas) != set(MilkType):
            raise ValueError("Tüm süt tipleri için fiyat farkı gereklidir.")
        lowest_price = (
            self.price
            + min(self.size_price_deltas.values())
            + min(self.milk_price_deltas.values())
        )
        if lowest_price <= 0:
            raise ValueError("Ürünün hiçbir seçenekte fiyatı sıfır veya altı olamaz.")
        return self


class ProductAvailabilityRequest(BaseModel):
    is_available: bool


class ShopHoursUpdateRequest(BaseModel):
    opening_hours: str | None = Field(max_length=255)

    @field_validator("opening_hours")
    @classmethod
    def normalize_opening_hours(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class ShopListResponse(BaseModel):
    id: int
    name: str
    address: str
    latitude: float
    longitude: float
    opening_hours: str | None
    rating: float | None
    rating_count: int
    distance_km: float | None


class ShopDetailResponse(ShopListResponse):
    products: list[ProductResponse]


class ShopMenuResponse(BaseModel):
    shop_id: int
    shop_name: str
    products: list[ProductResponse]


class ShopRatingRequest(BaseModel):
    rating: int = Field(ge=1, le=5)


class MyShopRatingResponse(BaseModel):
    rating: int | None


class ShopRatingResult(BaseModel):
    user_rating: int
    average_rating: float
    rating_count: int
