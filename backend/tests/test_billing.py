import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.v1.payments import process_payment as process_payment_endpoint
from app.db.init_db import initialize_database
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.billing import PurchaseRequest
from app.services.billing import (
    cancel_subscription,
    change_subscription,
    get_my_subscription,
    payment_history,
    process_payment,
)


class BillingFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        initialize_database(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        self.user = User(
            phone_number="+905550009876",
            full_name="Billing Test",
            phone_verified_at=None,
        )
        self.session.add(self.user)
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_successful_purchase_activates_plan_and_records_payment(self) -> None:
        request = PurchaseRequest(
            plan_code="starter",
            card_number="4242-4242-4242-4242",
        )
        payment_result = process_payment_endpoint(
            request,
            self.user,
            self.session,
        )

        self.assertTrue(payment_result.success)
        self.assertEqual(payment_result.payment_status, "SUCCEEDED")
        self.assertEqual(payment_result.subscription.remaining_credits, 10)
        self.assertEqual(payment_result.subscription.plan_code, "STARTER")
        payment = self.session.scalar(select(Payment))
        self.assertEqual(payment.card_last_four, "4242")
        self.assertEqual(payment.subscription_id, payment_result.subscription.id)
        self.assertNotIn("4242424242424242", payment.card_last_four)

    def test_declined_payment_does_not_activate_subscription(self) -> None:
        result = process_payment(
            self.session,
            self.user,
            "STARTER",
            "4000000000000002",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.payment_status, "FAILED")
        self.assertIsNone(result.subscription)
        self.assertEqual(len(payment_history(self.session, self.user)), 1)
        self.assertIsNone(
            self.session.scalar(
                select(Subscription).where(Subscription.user_id == self.user.id)
            )
        )

    def test_unlimited_plan_has_no_credit_limit(self) -> None:
        result = process_payment(
            self.session,
            self.user,
            "UNLIMITED",
            "4242424242424242",
        )

        self.assertTrue(result.success)
        self.assertIsNone(result.subscription.remaining_credits)
        self.assertEqual(result.subscription.guest_credits, 5)
        self.assertTrue(result.subscription.priority_pickup)

    def test_failed_upgrade_keeps_current_plan_and_credits(self) -> None:
        process_payment(
            self.session,
            self.user,
            "STARTER",
            "4242424242424242",
        )

        failed_upgrade = change_subscription(
            self.session, self.user, "PREMIUM", "4000000000000002"
        )
        self.assertFalse(failed_upgrade.success)
        self.assertEqual(failed_upgrade.subscription.plan_code, "STARTER")

        upgraded = change_subscription(
            self.session,
            self.user,
            "PREMIUM",
            "4242424242424242",
        )
        self.assertTrue(upgraded.success)
        self.assertEqual(upgraded.subscription.plan_code, "PREMIUM")
        self.assertEqual(upgraded.subscription.remaining_credits, 20)
        self.assertIn("yeni 30 günlük", upgraded.message)

    def test_downgrade_requires_cancel_then_purchase(self) -> None:
        premium = process_payment(
            self.session,
            self.user,
            "PREMIUM",
            "4242424242424242",
        )
        subscription = self.session.get(
            Subscription,
            premium.subscription.id,
        )
        subscription.remaining_credits = 7
        self.session.commit()
        payment_count = len(payment_history(self.session, self.user))

        with self.assertRaises(HTTPException) as error:
            change_subscription(
                self.session,
                self.user,
                "STARTER",
                "4242424242424242",
            )

        self.assertEqual(error.exception.status_code, 409)
        self.session.refresh(subscription)
        self.assertEqual(subscription.plan.code, "PREMIUM")
        self.assertEqual(subscription.remaining_credits, 7)
        self.assertEqual(
            len(payment_history(self.session, self.user)),
            payment_count,
        )

        cancel_subscription(self.session, self.user)
        starter = process_payment(
            self.session,
            self.user,
            "STARTER",
            "4242424242424242",
        )
        self.assertTrue(starter.success)
        self.assertEqual(starter.subscription.plan_code, "STARTER")

    def test_purchasing_same_active_plan_renews_and_resets_credits(self) -> None:
        first_purchase = process_payment(
            self.session,
            self.user,
            "STARTER",
            "4242424242424242",
        )
        subscription = self.session.get(Subscription, first_purchase.subscription.id)
        subscription.remaining_credits = 3
        self.session.commit()

        renewal = process_payment(
            self.session,
            self.user,
            "STARTER",
            "4242424242424242",
        )

        self.assertTrue(renewal.success)
        self.assertEqual(renewal.subscription.remaining_credits, 10)
        self.assertEqual(len(payment_history(self.session, self.user)), 2)

    def test_cancellation_removes_active_subscription(self) -> None:
        process_payment(
            self.session,
            self.user,
            "STARTER",
            "4242424242424242",
        )
        cancel_subscription(self.session, self.user)

        with self.assertRaises(HTTPException) as error:
            get_my_subscription(self.session, self.user)
        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
