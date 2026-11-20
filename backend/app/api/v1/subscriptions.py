from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.billing import (
    CardRequest,
    CancellationResponse,
    PlanResponse,
    PurchaseRequest,
    PurchaseResponse,
    SubscriptionResponse,
)
from app.services.billing import (
    cancel_subscription,
    change_subscription,
    get_my_subscription,
    list_plans,
    process_payment,
    renew_subscription,
)

router = APIRouter(prefix="/api/v1/subscriptions", tags=["Subscriptions"])


@router.get("/plans", response_model=list[PlanResponse])
def get_plans(session: Session = Depends(get_db)) -> list[PlanResponse]:
    return list_plans(session)


@router.post(
    "",
    response_model=PurchaseResponse,
    summary="Test ödemesiyle abonelik başlat veya aynı paketi yenile",
)
def create_subscription(
    payload: PurchaseRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> PurchaseResponse:
    return process_payment(
        session,
        user,
        payload.plan_code,
        payload.card_number,
    )


@router.get("/me", response_model=SubscriptionResponse)
def get_subscription(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> SubscriptionResponse:
    return get_my_subscription(session, user)


@router.patch("/me", response_model=PurchaseResponse)
def update_subscription(
    payload: PurchaseRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> PurchaseResponse:
    return change_subscription(
        session,
        user,
        payload.plan_code,
        payload.card_number,
    )


@router.post("/me/renew", response_model=PurchaseResponse)
def renew_my_subscription(
    payload: CardRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> PurchaseResponse:
    return renew_subscription(session, user, payload.card_number)


@router.delete("/me", response_model=CancellationResponse)
def delete_subscription(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> CancellationResponse:
    cancel_subscription(session, user)
    return CancellationResponse(
        status="CANCELLED",
        message="Aboneliğiniz iptal edildi. Ödeme iadesi yapılmadı.",
    )
