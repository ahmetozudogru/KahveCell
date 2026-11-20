import re
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class CardRequest(BaseModel):
    card_number: str = Field(
        min_length=16,
        max_length=23,
        description=(
            "Simülasyon kartı: 4242-4242-4242-4242 başarılı, "
            "4000-0000-0000-0002 başarısız olur."
        ),
        examples=["4242-4242-4242-4242"],
    )

    @field_validator("card_number")
    @classmethod
    def normalize_card_number(cls, value: str) -> str:
        normalized = re.sub(r"[\s-]", "", value)
        if not re.fullmatch(r"\d{16}", normalized):
            raise ValueError("Kart numarası 16 rakamdan oluşmalıdır.")
        return normalized


class PurchaseRequest(CardRequest):
    plan_code: str = Field(
        description="Satın alınacak paket kodu.",
        examples=["STARTER"],
    )

    @field_validator("plan_code")
    @classmethod
    def normalize_plan_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"STARTER", "PREMIUM", "UNLIMITED"}:
            raise ValueError("Paket STARTER, PREMIUM veya UNLIMITED olmalıdır.")
        return normalized


class PlanResponse(BaseModel):
    id: int
    code: str
    name: str
    monthly_price: Decimal
    monthly_credits: int | None = Field(
        description="Sınırsız pakette null döner."
    )
    guest_credits: int
    priority_pickup: bool


class SubscriptionResponse(BaseModel):
    id: int
    plan_code: str
    plan_name: str
    status: str
    remaining_credits: int | None
    started_at: datetime
    expires_at: datetime
    guest_credits: int
    priority_pickup: bool


class PurchaseResponse(BaseModel):
    success: bool
    payment_id: int
    transaction_id: str
    amount: Decimal
    timestamp: datetime
    payment_status: str
    subscription: SubscriptionResponse | None
    message: str


class PaymentHistoryResponse(BaseModel):
    id: int
    transaction_id: str
    plan_code: str
    amount: Decimal
    status: str
    card_last_four: str
    failure_reason: str | None
    created_at: datetime
    subscription_id: int | None


class CancellationResponse(BaseModel):
    status: str
    message: str
