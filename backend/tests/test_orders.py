import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.order_qr import verify_qr_signature
from app.core.roles import UserRole
from app.db.init_db import initialize_database
from app.models import (
    Order,
    Product,
    Shop,
    Subscription,
    SubscriptionPlan,
    User,
)
from app.schemas.orders import (
    CoffeeSize,
    MilkType,
    OrderCreateRequest,
    OrderStatus,
    OrderCustomizations,
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
from app.services.order_events import order_status_event_broker
from app.services.shops import remove_shop_product


class OrderFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        initialize_database(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)

        self.customer = User(
            phone_number="+905550009871",
            full_name="Order Customer",
            role=UserRole.CUSTOMER.value,
        )
        self.owner = User(
            phone_number="+905550009872",
            full_name="Order Shop Owner",
            role=UserRole.SHOP_OWNER.value,
        )
        self.shop = Shop(
            owner=self.owner,
            name="Order Test Cafe",
            address="Ankara",
            latitude=39.92,
            longitude=32.85,
        )
        self.product = Product(
            shop=self.shop,
            name="Espresso",
            description="Test espresso",
            category="COFFEE",
            price=Decimal("100.00"),
            is_available=True,
        )
        self.session.add_all(
            [self.customer, self.owner, self.shop, self.product]
        )
        self.session.flush()

        starter_plan = self.session.scalar(
            select(SubscriptionPlan).where(
                SubscriptionPlan.code == "STARTER"
            )
        )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        self.subscription = Subscription(
            user_id=self.customer.id,
            plan_id=starter_plan.id,
            remaining_credits=2,
            status="ACTIVE",
            started_at=now,
            expires_at=now + timedelta(days=30),
        )
        self.session.add(self.subscription)
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def _create_order(self):
        return create_order(
            self.session,
            self.customer,
            OrderCreateRequest(
                shop_id=self.shop.id,
                product_id=self.product.id,
            ),
        )

    def test_creation_consumes_one_credit_and_returns_signed_case_qr(self) -> None:
        response = self._create_order()
        self.session.refresh(self.subscription)

        self.assertEqual(self.subscription.remaining_credits, 1)
        self.assertEqual(response.status, OrderStatus.PENDING)
        self.assertEqual(response.shop_name, self.shop.name)
        self.assertEqual(response.customer_name, self.customer.full_name)
        self.assertEqual(response.customer_phone, self.customer.phone_number)
        self.assertEqual(
            set(response.qr_code.model_dump()),
            {"order_id", "user_id", "shop_id", "created_at", "signature"},
        )
        self.assertEqual(len(response.qr_code.signature), 64)
        self.assertTrue(verify_qr_signature(response.qr_code))
        self.assertEqual(len(list_my_orders(self.session, self.customer)), 1)
        self.assertEqual(len(list_shop_orders(self.session, self.owner)), 1)

    def test_order_price_uses_product_defined_modifiers(self) -> None:
        self.product.size_price_deltas = {
            "S": "-10.00",
            "M": "0.00",
            "L": "15.00",
        }
        self.product.milk_price_deltas = {
            "NONE": "0.00",
            "WHOLE": "0.00",
            "OAT": "8.00",
            "ALMOND": "10.00",
            "LACTOSE_FREE": "5.00",
        }
        self.product.extra_shot_price = Decimal("12.50")
        self.session.commit()

        response = create_order(
            self.session,
            self.customer,
            OrderCreateRequest(
                shop_id=self.shop.id,
                product_id=self.product.id,
                customizations=OrderCustomizations(
                    size=CoffeeSize.L,
                    milk_type=MilkType.OAT,
                    extra_shots=2,
                ),
            ),
        )

        self.assertEqual(response.unit_price, Decimal("148.00"))

    def test_order_requires_an_active_subscription(self) -> None:
        self.session.delete(self.subscription)
        self.session.commit()

        with self.assertRaises(HTTPException) as error:
            self._create_order()

        self.assertEqual(error.exception.status_code, 403)
        self.assertIn("aktif aboneliğiniz", error.exception.detail)
        self.assertEqual(self.session.scalars(select(Order)).all(), [])

    def test_order_is_rejected_when_credits_are_exhausted(self) -> None:
        self.subscription.remaining_credits = 0
        self.session.commit()

        with self.assertRaises(HTTPException) as error:
            self._create_order()

        self.assertEqual(error.exception.status_code, 409)
        self.assertIn("Kahve hakkınız kalmadı", error.exception.detail)
        self.assertEqual(self.session.scalars(select(Order)).all(), [])

    def test_unlimited_subscription_does_not_decrement_credits(self) -> None:
        unlimited_plan = self.session.scalar(
            select(SubscriptionPlan).where(
                SubscriptionPlan.code == "UNLIMITED"
            )
        )
        self.subscription.plan_id = unlimited_plan.id
        self.subscription.remaining_credits = None
        self.session.commit()

        self._create_order()
        self.session.refresh(self.subscription)

        self.assertIsNone(self.subscription.remaining_credits)

    def test_customer_can_favorite_and_repeat_an_order(self) -> None:
        original = self._create_order()
        favorite = set_order_favorite(
            self.session,
            self.customer,
            original.id,
            True,
        )
        repeated = repeat_favorite_order(
            self.session,
            self.customer,
            original.id,
        )

        self.assertTrue(favorite.is_favorite)
        self.assertNotEqual(repeated.id, original.id)
        self.assertEqual(repeated.product_id, original.product_id)
        self.assertEqual(repeated.customizations, original.customizations)
        self.assertEqual(len(list_favorite_orders(self.session, self.customer)), 1)
        self.assertEqual(len(list_my_orders(self.session, self.customer)), 2)
        self.session.refresh(self.subscription)
        self.assertEqual(self.subscription.remaining_credits, 0)

        removed = set_order_favorite(
            self.session,
            self.customer,
            original.id,
            False,
        )
        self.assertFalse(removed.is_favorite)
        self.assertEqual(list_favorite_orders(self.session, self.customer), [])

    def test_non_favorite_order_cannot_be_repeated(self) -> None:
        order = self._create_order()

        with self.assertRaises(HTTPException) as error:
            repeat_favorite_order(self.session, self.customer, order.id)

        self.assertEqual(error.exception.status_code, 404)

    def test_order_remains_intact_after_shop_removes_its_product(self) -> None:
        order = self._create_order()

        removed_product = remove_shop_product(
            self.session,
            self.owner,
            self.shop.id,
            self.product.id,
        )
        stored_order = self.session.get(Order, order.id)
        refreshed_order = get_order(self.session, self.customer, order.id)

        self.assertFalse(removed_product.is_available)
        self.assertIsNotNone(stored_order)
        self.assertEqual(refreshed_order.id, order.id)
        self.assertEqual(refreshed_order.product_name, "Espresso")
        self.assertEqual(refreshed_order.unit_price, Decimal("100.00"))
        self.assertEqual(refreshed_order.status, OrderStatus.PENDING)
        self.assertIsNotNone(refreshed_order.qr_code)
        self.assertEqual(len(list_my_orders(self.session, self.customer)), 1)

    def test_owner_advances_status_and_qr_redeems_once(self) -> None:
        order = self._create_order()
        subscriber = order_status_event_broker.subscribe(order.id)
        self.addCleanup(
            order_status_event_broker.unsubscribe,
            order.id,
            subscriber,
        )
        for next_status in (
            OrderStatus.ACCEPTED,
            OrderStatus.PREPARING,
            OrderStatus.READY,
        ):
            order = update_order_status(
                self.session,
                self.owner,
                order.id,
                next_status,
            )
            self.assertEqual(
                subscriber.get_nowait(),
                {"order_id": order.id, "status": next_status.value},
            )

        forged_qr = order.qr_code.model_copy(update={"shop_id": uuid4()})
        invalid_result = verify_and_redeem_qr(
            self.session,
            self.owner,
            forged_qr,
        )
        self.assertFalse(invalid_result.valid)
        self.assertEqual(order.status, OrderStatus.READY)

        result = verify_and_redeem_qr(
            self.session,
            self.owner,
            order.qr_code,
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.status, OrderStatus.DELIVERED)
        self.assertEqual(
            subscriber.get_nowait(),
            {"order_id": order.id, "status": OrderStatus.DELIVERED.value},
        )

        replay = verify_and_redeem_qr(
            self.session,
            self.owner,
            order.qr_code,
        )
        self.assertFalse(replay.valid)

    def test_owner_can_confirm_qr_with_button_and_history_keeps_delivered_orders(
        self,
    ) -> None:
        ready_order = self._create_order()
        for next_status in (
            OrderStatus.ACCEPTED,
            OrderStatus.PREPARING,
            OrderStatus.READY,
        ):
            ready_order = update_order_status(
                self.session,
                self.owner,
                ready_order.id,
                next_status,
            )
        pending_order = self._create_order()

        result = confirm_order_qr(self.session, self.owner, ready_order.id)
        history = list_shop_order_history(self.session, self.owner)
        replay = confirm_order_qr(self.session, self.owner, ready_order.id)

        self.assertTrue(result.valid)
        self.assertEqual(result.status, OrderStatus.DELIVERED)
        self.assertFalse(replay.valid)
        self.assertEqual([order.id for order in history], [ready_order.id])
        self.assertNotIn(pending_order.id, [order.id for order in history])

    def test_owner_cannot_skip_status_transitions(self) -> None:
        order = self._create_order()

        with self.assertRaises(HTTPException) as error:
            update_order_status(
                self.session,
                self.owner,
                order.id,
                OrderStatus.READY,
            )

        self.assertEqual(error.exception.status_code, 409)

    def test_order_cannot_be_updated_by_another_shop_owner(self) -> None:
        order = self._create_order()
        other_owner = User(
            phone_number="+905550009873",
            full_name="Other Shop Owner",
            role=UserRole.SHOP_OWNER.value,
        )
        self.session.add(other_owner)
        self.session.commit()
        self.assertEqual(list_shop_orders(self.session, other_owner), [])

        with self.assertRaises(HTTPException) as error:
            update_order_status(
                self.session,
                other_owner,
                order.id,
                OrderStatus.ACCEPTED,
            )

        self.assertEqual(error.exception.status_code, 404)
        with self.assertRaises(HTTPException) as error:
            confirm_order_qr(self.session, other_owner, order.id)

        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
