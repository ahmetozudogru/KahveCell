import unittest

from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session

from app.core.roles import UserRole
from app.models import Shop, ShopRating, User
from seed_data import DEMO_PHONE, DEMO_RATING_USER_COUNT, seed_data


class DemoRatingSeedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_seed_creates_one_hundred_reviewers_and_aggregates_ratings(self) -> None:
        shops_added, _ = seed_data(self.engine, environment="development")
        self.assertEqual(shops_added, 5)

        with Session(self.engine) as session:
            reviewers = session.scalars(
                select(User).where(User.username.like("reviewer%"))
            ).all()
            demo_user = session.scalar(
                select(User).where(User.phone_number == DEMO_PHONE)
            )
            shops = session.scalars(select(Shop).order_by(Shop.id)).all()
            rating_count = session.scalar(
                select(func.count()).select_from(ShopRating)
            )

            self.assertEqual(len(reviewers), DEMO_RATING_USER_COUNT)
            self.assertTrue(
                all(reviewer.role == UserRole.CUSTOMER.value for reviewer in reviewers)
            )
            self.assertTrue(all(reviewer.password_hash is None for reviewer in reviewers))
            self.assertIsNotNone(demo_user)
            self.assertIsNotNone(demo_user.phone_verified_at)
            self.assertEqual(
                rating_count,
                DEMO_RATING_USER_COUNT * len(shops),
            )
            for shop in shops:
                ratings = session.scalars(
                    select(ShopRating).where(ShopRating.shop_id == shop.id)
                ).all()
                average = sum(rating.rating for rating in ratings) / len(ratings)
                self.assertEqual(len(ratings), DEMO_RATING_USER_COUNT)
                self.assertTrue(all(3 <= rating.rating <= 5 for rating in ratings))
                self.assertGreaterEqual(shop.rating, 3)
                self.assertLessEqual(shop.rating, 5)
                self.assertAlmostEqual(shop.rating, average, places=2)

        seed_data(self.engine, environment="development")
        with Session(self.engine) as session:
            self.assertEqual(
                session.scalar(
                    select(func.count()).select_from(User).where(
                        User.username.like("reviewer%")
                    )
                ),
                DEMO_RATING_USER_COUNT,
            )
            self.assertEqual(
                session.scalar(
                    select(func.count()).select_from(ShopRating)
                ),
                DEMO_RATING_USER_COUNT * 5,
            )

    def test_demo_seed_refuses_non_development_environment(self) -> None:
        with self.assertRaises(RuntimeError):
            seed_data(self.engine, environment="production")

        self.assertEqual(inspect(self.engine).get_table_names(), [])


if __name__ == "__main__":
    unittest.main()
