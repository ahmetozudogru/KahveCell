import asyncio
import json
from collections.abc import AsyncIterator
from queue import Empty, Queue

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user, get_db, require_roles
from app.core.roles import UserRole
from app.models.order import Order
from app.models.user import User
from app.schemas.orders import (
    FavoriteOrderResponse,
    OrderCreateRequest,
    OrderResponse,
    OrderStatusUpdateRequest,
    QRCodePayload,
    QRVerificationResponse,
    OrderStatus,
)
from app.services.orders import (
    confirm_order_qr,
    create_order,
    get_order,
    list_favorite_orders,
    list_my_orders,
    list_shop_order_history,
    list_shop_orders,
    repeat_favorite_order,
    set_order_favorite,
    update_order_status,
    verify_and_redeem_qr,
)
from app.services.order_events import (
    OrderStatusEvent,
    order_status_event_broker,
)

router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])
_ORDER_STATUS_RANK = {
    OrderStatus.PENDING: 0,
    OrderStatus.ACCEPTED: 1,
    OrderStatus.PREPARING: 2,
    OrderStatus.READY: 3,
    OrderStatus.DELIVERED: 4,
}


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_order(
    payload: OrderCreateRequest,
    user: User = Depends(require_roles(UserRole.CUSTOMER)),
    session: Session = Depends(get_db),
) -> OrderResponse:
    return create_order(session, user, payload)


@router.get("/me", response_model=list[OrderResponse])
def get_my_orders(
    user: User = Depends(require_roles(UserRole.CUSTOMER)),
    session: Session = Depends(get_db),
) -> list[OrderResponse]:
    return list_my_orders(session, user)


@router.get("/me/favorites", response_model=list[OrderResponse])
def get_favorite_orders(
    user: User = Depends(require_roles(UserRole.CUSTOMER)),
    session: Session = Depends(get_db),
) -> list[OrderResponse]:
    return list_favorite_orders(session, user)


@router.post(
    "/me/favorites/{order_id}/repeat",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_repeat_favorite_order(
    order_id: int,
    user: User = Depends(require_roles(UserRole.CUSTOMER)),
    session: Session = Depends(get_db),
) -> OrderResponse:
    return repeat_favorite_order(session, user, order_id)


@router.get("/shop", response_model=list[OrderResponse])
def get_shop_orders(
    user: User = Depends(require_roles(UserRole.SHOP_OWNER)),
    session: Session = Depends(get_db),
) -> list[OrderResponse]:
    return list_shop_orders(session, user)


@router.get("/shop/history", response_model=list[OrderResponse])
def get_shop_order_history(
    user: User = Depends(require_roles(UserRole.SHOP_OWNER)),
    session: Session = Depends(get_db),
) -> list[OrderResponse]:
    return list_shop_order_history(session, user)


@router.post("/qr/verify", response_model=QRVerificationResponse)
def verify_qr(
    payload: QRCodePayload,
    user: User = Depends(require_roles(UserRole.SHOP_OWNER)),
    session: Session = Depends(get_db),
) -> QRVerificationResponse:
    return verify_and_redeem_qr(session, user, payload)


@router.post(
    "/{order_id}/qr/confirm",
    response_model=QRVerificationResponse,
)
def post_confirm_order_qr(
    order_id: int,
    user: User = Depends(require_roles(UserRole.SHOP_OWNER)),
    session: Session = Depends(get_db),
) -> QRVerificationResponse:
    return confirm_order_qr(session, user, order_id)


@router.put("/{order_id}/favorite", response_model=FavoriteOrderResponse)
def put_order_favorite(
    order_id: int,
    user: User = Depends(require_roles(UserRole.CUSTOMER)),
    session: Session = Depends(get_db),
) -> FavoriteOrderResponse:
    return set_order_favorite(session, user, order_id, True)


@router.delete("/{order_id}/favorite", response_model=FavoriteOrderResponse)
def delete_order_favorite(
    order_id: int,
    user: User = Depends(require_roles(UserRole.CUSTOMER)),
    session: Session = Depends(get_db),
) -> FavoriteOrderResponse:
    return set_order_favorite(session, user, order_id, False)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order_details(
    order_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> OrderResponse:
    return get_order(session, user, order_id)


def _order_status_stream(
    order_id: int,
    initial_status: OrderStatus,
    subscriber: Queue[OrderStatusEvent],
    request: Request,
) -> AsyncIterator[str]:
    async def stream() -> AsyncIterator[str]:
        try:
            current_status = initial_status
            while True:
                event = {
                    "order_id": order_id,
                    "status": current_status.value,
                }
                yield f"event: order_status\ndata: {json.dumps(event)}\n\n"
                if current_status is OrderStatus.DELIVERED:
                    return

                if await request.is_disconnected():
                    return

                try:
                    event = await asyncio.to_thread(subscriber.get, True, 15)
                except Empty:
                    yield ": keep-alive\n\n"
                    continue
                next_status = OrderStatus(event["status"])
                if _ORDER_STATUS_RANK[next_status] <= _ORDER_STATUS_RANK[
                    current_status
                ]:
                    continue
                current_status = next_status
        finally:
            order_status_event_broker.unsubscribe(order_id, subscriber)

    return stream()


@router.get("/{order_id}/events")
def get_order_status_events(
    order_id: int,
    request: Request,
    user: User = Depends(require_roles(UserRole.CUSTOMER)),
    session: Session = Depends(get_db),
) -> StreamingResponse:
    query = select(Order.status).where(
        Order.id == order_id,
        Order.user_id == user.id,
    )
    initial_status_value = session.scalar(query)
    if initial_status_value is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sipariş bulunamadı.",
        )

    subscriber = order_status_event_broker.subscribe(order_id)
    session.rollback()
    current_status_value = session.scalar(query)
    if current_status_value is None:
        order_status_event_broker.unsubscribe(order_id, subscriber)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sipariş bulunamadı.",
        )
    session.close()

    return StreamingResponse(
        _order_status_stream(
            order_id,
            OrderStatus(current_status_value),
            subscriber,
            request,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.patch("/{order_id}/status", response_model=OrderResponse)
def patch_order_status(
    order_id: int,
    payload: OrderStatusUpdateRequest,
    user: User = Depends(require_roles(UserRole.SHOP_OWNER)),
    session: Session = Depends(get_db),
) -> OrderResponse:
    return update_order_status(session, user, order_id, payload.status)
