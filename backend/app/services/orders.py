from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.core.order_qr import create_qr_payload, verify_qr_signature
from app.models.order import Order
from app.models.order_favorite import OrderFavorite
from app.models.product import Product
from app.models.shop import Shop
from app.models.subscription import Subscription
from app.models.user import User
from app.services.pricing import calculate_product_price
from app.schemas.orders import (
    OrderCreateRequest,
    OrderCustomizations,
    FavoriteOrderResponse,
    OrderResponse,
    OrderStatus,
    QRCodePayload,
    QRVerificationResponse,
)
from app.services.billing import get_active_subscription
from app.services.order_events import order_status_event_broker


_NEXT_STATUS = {
    OrderStatus.PENDING: OrderStatus.ACCEPTED,
    OrderStatus.ACCEPTED: OrderStatus.PREPARING,
    OrderStatus.PREPARING: OrderStatus.READY,
    OrderStatus.READY: OrderStatus.DELIVERED,
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _order_response(order: Order) -> OrderResponse:
    qr_code: QRCodePayload | None = None
    if order.qr_token is not None:
        qr_code = create_qr_payload(
            order.qr_token,
            order.user_id,
            order.shop_id,
            order.created_at,
        )
    return OrderResponse(
        id=order.id,
        shop_id=order.shop_id,
        shop_name=order.shop.name,
        customer_name=order.user.full_name,
        customer_phone=order.user.phone_number,
        product_id=order.product_id,
        product_name=order.product.name,
        quantity=order.quantity,
        unit_price=order.unit_price,
        customizations=OrderCustomizations.model_validate(order.customizations),
        status=OrderStatus(order.status),
        qr_code=qr_code,
        created_at=order.created_at,
    )


def create_order(
    session: Session,
    user: User,
    payload: OrderCreateRequest,
) -> OrderResponse:
    subscription = get_active_subscription(session, user.id)
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sipariş vermek için geçerli bir aktif aboneliğiniz olmalıdır.",
        )
    if (
        subscription.remaining_credits is not None
        and subscription.remaining_credits <= 0
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kahve hakkınız kalmadı. Sipariş vermek için aboneliğinizi yenileyin.",
        )

    shop = session.get(Shop, payload.shop_id)
    if shop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dükkân bulunamadı.",
        )
    product = session.get(Product, payload.product_id)
    if product is None or product.shop_id != shop.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ürün bu dükkânın menüsünde bulunamadı.",
        )
    if not product.is_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu ürün şu anda siparişe açık değil.",
        )

    now = _now()
    order = Order(
        user=user,
        shop=shop,
        product=product,
        quantity=1,
        unit_price=calculate_product_price(product, payload.customizations),
        customizations=payload.customizations.model_dump(mode="json"),
        status=OrderStatus.PENDING.value,
        qr_token=str(uuid4()),
        created_at=now,
    )
    session.add(order)

    if subscription.remaining_credits is not None:
        result = session.execute(
            update(Subscription)
            .where(
                Subscription.id == subscription.id,
                Subscription.status == "ACTIVE",
                Subscription.expires_at > now,
                Subscription.remaining_credits > 0,
            )
            .values(
                remaining_credits=Subscription.remaining_credits - 1
            )
        )
        if result.rowcount != 1:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Kahve hakkınız kalmadı veya aboneliğinizin süresi doldu. "
                    "Aboneliğinizi kontrol edip tekrar deneyin."
                ),
            )

    session.flush()
    response = _order_response(order)
    session.commit()
    return response


def list_my_orders(session: Session, user: User) -> list[OrderResponse]:
    orders = session.scalars(
        select(Order)
        .options(
            joinedload(Order.product),
            joinedload(Order.shop),
            joinedload(Order.user),
        )
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc(), Order.id.desc())
    ).all()
    return [_order_response(order) for order in orders]


def list_favorite_orders(
    session: Session,
    user: User,
) -> list[OrderResponse]:
    orders = session.scalars(
        select(Order)
        .join(OrderFavorite, OrderFavorite.order_id == Order.id)
        .options(
            joinedload(Order.product),
            joinedload(Order.shop),
            joinedload(Order.user),
        )
        .where(OrderFavorite.user_id == user.id)
        .order_by(OrderFavorite.created_at.desc(), Order.id.desc())
    ).all()
    return [_order_response(order) for order in orders]


def set_order_favorite(
    session: Session,
    user: User,
    order_id: int,
    is_favorite: bool,
) -> FavoriteOrderResponse:
    order = session.scalar(
        select(Order).where(
            Order.id == order_id,
            Order.user_id == user.id,
        )
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sipariş bulunamadı.",
        )

    favorite = session.get(OrderFavorite, (user.id, order_id))
    if is_favorite and favorite is None:
        session.add(OrderFavorite(user_id=user.id, order_id=order_id))
        session.commit()
    elif not is_favorite and favorite is not None:
        session.delete(favorite)
        session.commit()
    return FavoriteOrderResponse(
        order_id=order_id,
        is_favorite=is_favorite,
    )


def repeat_favorite_order(
    session: Session,
    user: User,
    order_id: int,
) -> OrderResponse:
    favorite = session.get(OrderFavorite, (user.id, order_id))
    if favorite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favori sipariş bulunamadı.",
        )

    order = session.scalar(
        select(Order)
        .options(joinedload(Order.product))
        .where(Order.id == order_id, Order.user_id == user.id)
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sipariş bulunamadı.",
        )

    return create_order(
        session,
        user,
        OrderCreateRequest(
            shop_id=order.shop_id,
            product_id=order.product_id,
            customizations=OrderCustomizations.model_validate(
                order.customizations
            ),
        ),
    )


def list_shop_orders(session: Session, user: User) -> list[OrderResponse]:
    orders = session.scalars(
        select(Order)
        .join(Shop, Order.shop_id == Shop.id)
        .options(
            joinedload(Order.product),
            joinedload(Order.shop),
            joinedload(Order.user),
        )
        .where(Shop.owner_id == user.id)
        .order_by(Order.created_at.desc(), Order.id.desc())
    ).all()
    return [_order_response(order) for order in orders]


def list_shop_order_history(
    session: Session,
    user: User,
) -> list[OrderResponse]:
    orders = session.scalars(
        select(Order)
        .join(Shop, Order.shop_id == Shop.id)
        .options(
            joinedload(Order.product),
            joinedload(Order.shop),
            joinedload(Order.user),
        )
        .where(
            Shop.owner_id == user.id,
            Order.status == OrderStatus.DELIVERED.value,
        )
        .order_by(Order.created_at.desc(), Order.id.desc())
    ).all()
    return [_order_response(order) for order in orders]


def get_order(
    session: Session,
    user: User,
    order_id: int,
) -> OrderResponse:
    order = session.scalar(
        select(Order)
        .options(
            joinedload(Order.product),
            joinedload(Order.shop),
            joinedload(Order.user),
        )
        .where(Order.id == order_id)
    )
    if order is None or (
        order.user_id != user.id
        and (order.shop.owner is None or order.shop.owner.id != user.id)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sipariş bulunamadı.",
        )
    return _order_response(order)


def update_order_status(
    session: Session,
    user: User,
    order_id: int,
    next_status: OrderStatus,
) -> OrderResponse:
    order = session.scalar(
        select(Order)
        .options(
            joinedload(Order.product),
            joinedload(Order.shop),
            joinedload(Order.user),
        )
        .where(Order.id == order_id)
    )
    if order is None or order.shop.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sipariş bulunamadı.",
        )

    current_status = OrderStatus(order.status)
    expected_status = _NEXT_STATUS.get(current_status)
    if next_status != expected_status:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Bu sipariş için geçerli sonraki durum: "
                f"{expected_status.value if expected_status else 'yok'}."
            ),
        )

    order.status = next_status.value
    session.commit()
    order_status_event_broker.publish(order.id, next_status)
    return _order_response(order)


def verify_and_redeem_qr(
    session: Session,
    user: User,
    payload: QRCodePayload,
) -> QRVerificationResponse:
    if not verify_qr_signature(payload):
        return QRVerificationResponse(
            valid=False,
            order_id=None,
            status=None,
            message="QR kod imzası geçersiz; sipariş doğrulanamadı.",
        )

    order = session.scalar(
        select(Order)
        .options(joinedload(Order.shop))
        .where(Order.qr_token == str(payload.order_id))
    )
    if order is None or order.shop.owner_id != user.id:
        return QRVerificationResponse(
            valid=False,
            order_id=None,
            status=None,
            message="QR kod bu dükkândaki bir siparişle eşleşmiyor.",
        )

    expected_payload = create_qr_payload(
        order.qr_token,
        order.user_id,
        order.shop_id,
        order.created_at,
    )
    if payload != expected_payload:
        return QRVerificationResponse(
            valid=False,
            order_id=None,
            status=None,
            message="QR kod sipariş bilgileriyle eşleşmiyor.",
        )

    current_status = OrderStatus(order.status)
    if current_status != OrderStatus.READY:
        message = (
            "Bu sipariş daha önce teslim edildi."
            if current_status == OrderStatus.DELIVERED
            else "Sipariş hazır olmadan QR kod kullanılamaz."
        )
        return QRVerificationResponse(
            valid=False,
            order_id=payload.order_id,
            status=current_status,
            message=message,
        )

    result = session.execute(
        update(Order)
        .where(
            Order.id == order.id,
            Order.status == OrderStatus.READY.value,
        )
        .values(status=OrderStatus.DELIVERED.value)
    )
    if result.rowcount != 1:
        session.rollback()
        return QRVerificationResponse(
            valid=False,
            order_id=payload.order_id,
            status=OrderStatus.DELIVERED,
            message="Bu QR kod daha önce kullanılmış.",
        )
    session.commit()
    order_status_event_broker.publish(order.id, OrderStatus.DELIVERED)
    return QRVerificationResponse(
        valid=True,
        order_id=payload.order_id,
        status=OrderStatus.DELIVERED,
        message="QR kod doğrulandı; sipariş teslim edildi.",
    )


def confirm_order_qr(
    session: Session,
    user: User,
    order_id: int,
) -> QRVerificationResponse:
    order = session.scalar(
        select(Order)
        .join(Shop, Order.shop_id == Shop.id)
        .options(joinedload(Order.shop))
        .where(Order.id == order_id, Shop.owner_id == user.id)
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sipariş bulunamadı.",
        )
    if order.qr_token is None:
        return QRVerificationResponse(
            valid=False,
            order_id=None,
            status=OrderStatus(order.status),
            message="Bu sipariş için doğrulanabilir QR kodu bulunamadı.",
        )

    payload = create_qr_payload(
        order.qr_token,
        order.user_id,
        order.shop_id,
        order.created_at,
    )
    return verify_and_redeem_qr(session, user, payload)
