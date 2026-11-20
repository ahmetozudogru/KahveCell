from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.schemas.billing import (
    PaymentHistoryResponse,
    PlanResponse,
    PurchaseResponse,
    SubscriptionResponse,
)

SUCCESS_CARD = "4242424242424242"
FAILURE_CARD = "4000000000000002"
SUBSCRIPTION_PERIOD_DAYS = 30
PLAN_TIER = {"STARTER": 1, "PREMIUM": 2, "UNLIMITED": 3}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_plan(session: Session, plan_code: str) -> SubscriptionPlan:
    plan = session.scalar(
        select(SubscriptionPlan).where(
            SubscriptionPlan.code == plan_code,
            SubscriptionPlan.is_active.is_(True),
        )
    )
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aktif abonelik paketi bulunamadı.",
        )
    return plan


def _subscription_response(
    subscription: Subscription,
) -> SubscriptionResponse:
    return SubscriptionResponse(
        id=subscription.id,
        plan_code=subscription.plan.code,
        plan_name=subscription.plan.name,
        status=subscription.status,
        remaining_credits=subscription.remaining_credits,
        started_at=subscription.started_at,
        expires_at=subscription.expires_at,
        guest_credits=subscription.plan.guest_credits,
        priority_pickup=subscription.plan.priority_pickup,
    )


def get_active_subscription(
    session: Session,
    user_id: int,
) -> Subscription | None:
    subscription = session.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == "ACTIVE",
        )
        .order_by(Subscription.started_at.desc(), Subscription.id.desc())
    )
    if subscription and subscription.expires_at <= _now():
        subscription.status = "EXPIRED"
        session.commit()
        return None
    return subscription


def _new_payment(
    session: Session,
    user: User,
    plan: SubscriptionPlan,
    card_number: str,
    subscription: Subscription | None = None,
) -> Payment:
    success = card_number == SUCCESS_CARD
    payment = Payment(
        user_id=user.id,
        plan_id=plan.id,
        subscription_id=subscription.id if subscription else None,
        transaction_id=str(uuid4()),
        amount=plan.monthly_price,
        status="SUCCEEDED" if success else "FAILED",
        card_last_four=card_number[-4:],
        failure_reason=(
            None
            if success
            else (
                "Test kartı ödeme simülasyonunda reddedildi."
                if card_number == FAILURE_CARD
                else "Desteklenmeyen test kartı."
            )
        ),
        created_at=_now(),
    )
    session.add(payment)
    session.flush()
    return payment


def _purchase_response(
    payment: Payment,
    subscription: Subscription | None,
) -> PurchaseResponse:
    success = payment.status == "SUCCEEDED"
    return PurchaseResponse(
        success=success,
        payment_id=payment.id,
        transaction_id=payment.transaction_id,
        amount=payment.amount,
        timestamp=payment.created_at,
        payment_status=payment.status,
        subscription=(
            _subscription_response(subscription) if subscription else None
        ),
        message=(
            (
                "Ödeme başarılı; abonelik aktifleştirildi."
                if subscription
                else (
                    "Ödeme başarılı; bu payment_id ile aboneliği "
                    "başlatabilir veya değiştirebilirsiniz."
                )
            )
            if success
            else payment.failure_reason or "Ödeme başarısız."
        ),
    )


def list_plans(session: Session) -> list[PlanResponse]:
    plans = session.scalars(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.id)
    ).all()
    return [
        PlanResponse(
            id=plan.id,
            code=plan.code,
            name=plan.name,
            monthly_price=plan.monthly_price,
            monthly_credits=plan.monthly_credits,
            guest_credits=plan.guest_credits,
            priority_pickup=plan.priority_pickup,
        )
        for plan in plans
    ]


def get_my_subscription(session: Session, user: User) -> SubscriptionResponse:
    subscription = get_active_subscription(session, user.id)
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aktif aboneliğiniz bulunmuyor.",
        )
    return _subscription_response(subscription)


def process_payment(
    session: Session,
    user: User,
    plan_code: str,
    card_number: str,
) -> PurchaseResponse:
    current = get_active_subscription(session, user.id)
    plan = _get_plan(session, plan_code)
    if current is not None:
        if current.plan_id == plan.id:
            return renew_subscription(session, user, card_number)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Aktif aboneliğiniz var. Paket değiştirmek için PATCH "
                "/api/v1/subscriptions/me kullanın."
            ),
        )

    payment = _new_payment(session, user, plan, card_number)
    if payment.status == "FAILED":
        session.commit()
        return _purchase_response(payment, None)

    now = _now()
    subscription = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        remaining_credits=plan.monthly_credits,
        status="ACTIVE",
        started_at=now,
        expires_at=now + timedelta(days=SUBSCRIPTION_PERIOD_DAYS),
    )
    session.add(subscription)
    session.flush()
    payment.subscription_id = subscription.id
    session.commit()
    return _purchase_response(payment, subscription)


def change_subscription(
    session: Session,
    user: User,
    plan_code: str,
    card_number: str,
) -> PurchaseResponse:
    current = get_active_subscription(session, user.id)
    if current is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paket değiştirmek için aktif aboneliğiniz olmalıdır.",
        )
    plan = _get_plan(session, plan_code)
    if current.plan_id == plan.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Zaten bu pakettesiniz. Aynı paketi yenilemek için POST /api/v1/subscriptions kullanın.",
        )
    current_plan = session.get(SubscriptionPlan, current.plan_id)
    if current_plan is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mevcut abonelik paketi bulunamadı.",
        )
    target_tier = PLAN_TIER.get(plan.code)
    current_tier = PLAN_TIER.get(current_plan.code)
    if target_tier is None or current_tier is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu abonelik paketinin geçiş sırası tanımlı değil.",
        )
    if target_tier < current_tier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Daha düşük pakete doğrudan geçilemez. Önce aktif aboneliğinizi "
                "iptal edin, ardından istediğiniz paketi satın alın."
            ),
        )

    payment = _new_payment(session, user, plan, card_number, current)
    if payment.status == "FAILED":
        session.commit()
        return _purchase_response(payment, current)

    now = _now()
    current.plan = plan
    current.plan_id = plan.id
    current.remaining_credits = plan.monthly_credits
    current.expires_at = now + timedelta(days=SUBSCRIPTION_PERIOD_DAYS)
    payment.subscription_id = current.id
    session.commit()
    response = _purchase_response(payment, current)
    response.message = (
        "Paketiniz yükseltildi. Kalan krediler yenilendi ve yeni 30 günlük "
        "abonelik dönemi bugün başladı."
    )
    return response


def renew_subscription(
    session: Session,
    user: User,
    card_number: str,
) -> PurchaseResponse:
    subscription = session.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.status.in_(("ACTIVE", "EXPIRED")),
        )
        .order_by(Subscription.started_at.desc(), Subscription.id.desc())
    )
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Yenilenecek abonelik bulunamadı.",
        )

    plan = _get_plan(session, subscription.plan.code)
    payment = _new_payment(session, user, plan, card_number, subscription)
    if payment.status == "FAILED":
        if subscription.expires_at <= _now():
            subscription.status = "EXPIRED"
        session.commit()
        return _purchase_response(
            payment,
            subscription if subscription.status == "ACTIVE" else None,
        )

    now = _now()
    subscription.plan_id = plan.id
    subscription.status = "ACTIVE"
    subscription.remaining_credits = plan.monthly_credits
    subscription.started_at = now
    subscription.expires_at = now + timedelta(days=SUBSCRIPTION_PERIOD_DAYS)
    payment.subscription_id = subscription.id
    payment.subscription_id = subscription.id
    session.commit()
    return _purchase_response(payment, subscription)


def cancel_subscription(session: Session, user: User) -> None:
    subscription = get_active_subscription(session, user.id)
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="İptal edilecek aktif aboneliğiniz bulunmuyor.",
        )
    subscription.status = "CANCELLED"
    session.commit()


def payment_history(
    session: Session,
    user: User,
) -> list[PaymentHistoryResponse]:
    payments = session.scalars(
        select(Payment)
        .where(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc(), Payment.id.desc())
    ).all()
    return [
        PaymentHistoryResponse(
            id=payment.id,
            transaction_id=payment.transaction_id,
            plan_code=payment.plan.code,
            amount=payment.amount,
            status=payment.status,
            card_last_four=payment.card_last_four,
            failure_reason=payment.failure_reason,
            created_at=payment.created_at,
            subscription_id=payment.subscription_id,
        )
        for payment in payments
    ]
