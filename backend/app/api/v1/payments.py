from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.billing import (
    PaymentHistoryResponse,
    PurchaseRequest,
    PurchaseResponse,
)
from app.services.billing import (
    payment_history,
    process_payment as process_subscription_purchase,
)

router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


@router.post(
    "/process",
    response_model=PurchaseResponse,
    summary="Test kartını çalıştır ve aboneliği etkinleştir",
)
def process_payment(
    payload: PurchaseRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> PurchaseResponse:
    return process_subscription_purchase(
        session,
        user,
        payload.plan_code,
        payload.card_number,
    )


@router.get("/history", response_model=list[PaymentHistoryResponse])
def get_payment_history(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[PaymentHistoryResponse]:
    return payment_history(session, user)
