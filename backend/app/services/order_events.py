from queue import Queue
from threading import Lock
from typing import TypedDict

from app.schemas.orders import OrderStatus


class OrderStatusEvent(TypedDict):
    order_id: int
    status: str


class OrderStatusEventBroker:
    def __init__(self) -> None:
        self._lock = Lock()
        self._subscribers: dict[int, set[Queue[OrderStatusEvent]]] = {}

    def subscribe(self, order_id: int) -> Queue[OrderStatusEvent]:
        subscriber: Queue[OrderStatusEvent] = Queue()
        with self._lock:
            self._subscribers.setdefault(order_id, set()).add(subscriber)
        return subscriber

    def unsubscribe(
        self,
        order_id: int,
        subscriber: Queue[OrderStatusEvent],
    ) -> None:
        with self._lock:
            subscribers = self._subscribers.get(order_id)
            if subscribers is None:
                return
            subscribers.discard(subscriber)
            if not subscribers:
                del self._subscribers[order_id]

    def publish(self, order_id: int, status: OrderStatus) -> None:
        event: OrderStatusEvent = {
            "order_id": order_id,
            "status": status.value,
        }
        with self._lock:
            subscribers = tuple(self._subscribers.get(order_id, ()))
        for subscriber in subscribers:
            subscriber.put_nowait(event)


order_status_event_broker = OrderStatusEventBroker()
