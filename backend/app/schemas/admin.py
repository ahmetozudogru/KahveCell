from pydantic import BaseModel, ConfigDict, Field, field_validator


class AdminShopUpsertRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    address: str = Field(min_length=3, max_length=255)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    opening_hours: str | None = Field(default=None, max_length=255)
    owner_id: int | None = Field(default=None, ge=1)

    @field_validator("name", "address")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Bu alan boş bırakılamaz.")
        return normalized

    @field_validator("opening_hours")
    @classmethod
    def normalize_opening_hours(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class GeocodeRequest(BaseModel):
    address: str = Field(min_length=3, max_length=255)

    @field_validator("address")
    @classmethod
    def normalize_address(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Adres boş bırakılamaz.")
        return normalized


class GeocodeResponse(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    display_name: str


class AdminShopResponse(BaseModel):
    id: int
    name: str
    address: str
    latitude: float
    longitude: float
    opening_hours: str | None
    rating: float | None
    rating_count: int
    owner_id: int | None
    owner_name: str | None

    model_config = ConfigDict(from_attributes=True)
