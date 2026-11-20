import json
import unittest
from decimal import Decimal

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.init_db import initialize_database
from app.models.product import Product
from app.models.shop import Shop
from app.models.shop_rating import ShopRating
from app.models.user import User
from app.core.roles import UserRole
from app.schemas.orders import CoffeeSize, MilkType
from app.schemas.shops import (
    MyShopRatingResponse,
    ProductAvailabilityRequest,
    ProductUpsertRequest,
    ShopRatingRequest,
    ShopHoursUpdateRequest,
)
from app.services.shops import (
    create_shop_product,
    get_shop_detail,
    get_shop_menu,
    get_my_shop_rating,
    list_owned_shops,
    list_shops,
    remove_shop_product,
    rate_shop,
    set_shop_product_availability,
    update_shop_opening_hours,
    update_shop_product,
)


class ShopDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)

        self.owner = User(
            phone_number="+905550009881",
            full_name="Cafe Owner",
            role=UserRole.SHOP_OWNER.value,
        )
        self.session.add(self.owner)
        self.session.flush()

        self.shops = [
            Shop(
                owner=self.owner,
                name="Cafe Down Engelsiz Cafe",
                address="İzmir 1 Caddesi, Kızılay Mahallesi, Ankara",
                latitude=39.9229865,
                longitude=32.8539956,
            ),
            Shop(
                name="Kocatepe Coffee 1919",
                address="7. Cadde, Bahçelievler, Ankara",
                latitude=39.9219387,
                longitude=32.8255133,
            ),
            Shop(
                name="Cafe des Cafes",
                address="Tunalı Hilmi Caddesi, Ankara",
                latitude=39.9066216,
                longitude=32.8612044,
            ),
            Shop(
                name="Çimen Cafe & Bistro",
                address="2590. Sokak, Çayyolu, Ankara",
                latitude=39.8822544,
                longitude=32.6849103,
            ),
            Shop(
                name="Mozart Cafe",
                address="Bilkent, Ankara",
                latitude=39.8695452,
                longitude=32.7550274,
            ),
        ]
        self.session.add_all(self.shops)
        self.session.flush()
        self.session.add(
            Product(
                shop_id=self.shops[0].id,
                name="Espresso",
                description="Single espresso",
                category="COFFEE",
                price=Decimal("115.00"),
                is_available=True,
            )
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_location_results_are_filtered_and_sorted_by_distance(self) -> None:
        shops = list_shops(
            self.session,
            latitude=39.9208,
            longitude=32.8541,
            radius_km=5,
        )

        self.assertEqual(shops[0].name, "Cafe Down Engelsiz Cafe")
        self.assertLess(shops[0].distance_km, 1)
        self.assertTrue(all(shop.distance_km <= 5 for shop in shops))
        distances = [shop.distance_km for shop in shops]
        self.assertEqual(distances, sorted(distances))

    def test_search_matches_turkish_shop_names_and_addresses(self) -> None:
        shops = list_shops(self.session, search="çayyolu")

        self.assertEqual([shop.name for shop in shops], ["Çimen Cafe & Bistro"])

    def test_shop_detail_includes_its_menu(self) -> None:
        detail = get_shop_detail(
            self.session,
            self.shops[0].id,
            latitude=39.9208,
            longitude=32.8541,
        )
        menu = get_shop_menu(self.session, self.shops[0].id)

        self.assertEqual([product.name for product in detail.products], ["Espresso"])
        self.assertEqual(detail.products[0].price, Decimal("115.00"))
        self.assertEqual(menu.shop_name, detail.name)
        self.assertEqual(
            detail.products[0].size_price_deltas[CoffeeSize.M],
            Decimal("0.00"),
        )

    def test_shop_responses_include_exact_rating_count(self) -> None:
        reviewers = [
            User(
                phone_number="+905550009891",
                full_name="First Reviewer",
            ),
            User(
                phone_number="+905550009892",
                full_name="Second Reviewer",
            ),
        ]
        self.session.add_all(reviewers)
        self.session.flush()
        self.session.add_all(
            [
                ShopRating(
                    user_id=reviewers[0].id,
                    shop_id=self.shops[0].id,
                    rating=4,
                ),
                ShopRating(
                    user_id=reviewers[1].id,
                    shop_id=self.shops[0].id,
                    rating=5,
                ),
            ]
        )
        self.session.commit()

        listed_shop = next(
            shop
            for shop in list_shops(self.session)
            if shop.id == self.shops[0].id
        )
        detail = get_shop_detail(self.session, self.shops[0].id)
        owned_shop = list_owned_shops(self.session, self.owner)[0]

        self.assertEqual(listed_shop.rating_count, 2)
        self.assertEqual(detail.rating_count, 2)
        self.assertEqual(owned_shop.rating_count, 2)

    def test_customer_can_rate_and_update_a_shop_once(self) -> None:
        customer = User(
            phone_number="+905550009893",
            full_name="Rating Customer",
        )
        another_customer = User(
            phone_number="+905550009894",
            full_name="Another Rating Customer",
        )
        self.session.add_all([customer, another_customer])
        self.session.commit()

        created = rate_shop(
            self.session,
            customer,
            self.shops[0].id,
            ShopRatingRequest(rating=4),
        )
        another_rating = rate_shop(
            self.session,
            another_customer,
            self.shops[0].id,
            ShopRatingRequest(rating=3),
        )
        updated = rate_shop(
            self.session,
            customer,
            self.shops[0].id,
            ShopRatingRequest(rating=5),
        )
        current = get_my_shop_rating(
            self.session,
            customer,
            self.shops[0].id,
        )
        detail = get_shop_detail(self.session, self.shops[0].id)

        self.assertEqual(created.user_rating, 4)
        self.assertEqual(created.average_rating, 4.0)
        self.assertEqual(created.rating_count, 1)
        self.assertEqual(another_rating.average_rating, 3.5)
        self.assertEqual(another_rating.rating_count, 2)
        self.assertEqual(updated.user_rating, 5)
        self.assertEqual(updated.average_rating, 4.0)
        self.assertEqual(updated.rating_count, 2)
        self.assertEqual(current, MyShopRatingResponse(rating=5))
        self.assertEqual(detail.rating, 4.0)
        self.assertEqual(detail.rating_count, 2)

    def test_shop_rating_must_be_between_one_and_five(self) -> None:
        for rating in (0, 6):
            with self.subTest(rating=rating):
                with self.assertRaises(ValidationError):
                    ShopRatingRequest(rating=rating)

    def test_owner_shop_list_includes_only_owned_shops_and_menu(self) -> None:
        shops = list_owned_shops(self.session, self.owner)

        self.assertEqual(len(shops), 1)
        self.assertEqual(shops[0].name, "Cafe Down Engelsiz Cafe")
        self.assertEqual([product.name for product in shops[0].products], ["Espresso"])

    def test_owner_can_update_opening_hours_and_clear_them(self) -> None:
        result = update_shop_opening_hours(
            self.session,
            self.owner,
            self.shops[0].id,
            ShopHoursUpdateRequest(
                opening_hours="  Her gün   09:00-21:00  "
            ),
        )
        self.assertEqual(result.opening_hours, "Her gün 09:00-21:00")
        self.assertEqual(
            get_shop_detail(self.session, self.shops[0].id).opening_hours,
            "Her gün 09:00-21:00",
        )

        cleared = update_shop_opening_hours(
            self.session,
            self.owner,
            self.shops[0].id,
            ShopHoursUpdateRequest(opening_hours="   "),
        )
        self.assertIsNone(cleared.opening_hours)

    def test_opening_hours_update_requires_an_explicit_value(self) -> None:
        with self.assertRaises(ValidationError):
            ShopHoursUpdateRequest.model_validate({})

    def test_owner_cannot_update_another_shops_opening_hours(self) -> None:
        other_owner = User(
            phone_number="+905550009880",
            full_name="Other Owner",
            role=UserRole.SHOP_OWNER.value,
        )
        self.session.add(other_owner)
        self.session.commit()

        with self.assertRaises(HTTPException) as error:
            update_shop_opening_hours(
                self.session,
                other_owner,
                self.shops[0].id,
                ShopHoursUpdateRequest(opening_hours="Her gün 09:00-21:00"),
            )
        self.assertEqual(error.exception.status_code, 404)

    def test_owner_can_create_edit_and_remove_menu_products(self) -> None:
        payload = ProductUpsertRequest(
            name="Latte",
            description="Yumuşak içimli latte",
            category="Espresso Bazlı",
            price=Decimal("100.00"),
            size_price_deltas={
                CoffeeSize.S: Decimal("-10.00"),
                CoffeeSize.M: Decimal("0.00"),
                CoffeeSize.L: Decimal("15.00"),
            },
            milk_price_deltas={
                MilkType.NONE: Decimal("0.00"),
                MilkType.WHOLE: Decimal("0.00"),
                MilkType.OAT: Decimal("8.00"),
                MilkType.ALMOND: Decimal("10.00"),
                MilkType.LACTOSE_FREE: Decimal("5.00"),
            },
            extra_shot_price=Decimal("12.50"),
        )
        created = create_shop_product(
            self.session,
            self.owner,
            self.shops[0].id,
            payload,
        )
        self.assertEqual(created.name, "Latte")
        self.assertTrue(created.is_available)
        self.assertEqual(created.size_price_deltas[CoffeeSize.L], Decimal("15.00"))
        self.assertEqual(
            created.milk_price_deltas[MilkType.OAT],
            Decimal("8.00"),
        )
        self.assertEqual(created.extra_shot_price, Decimal("12.50"))

        updated_payload = payload.model_copy(
            update={"price": Decimal("105.00")}
        )
        updated = update_shop_product(
            self.session,
            self.owner,
            self.shops[0].id,
            created.id,
            updated_payload,
        )
        self.assertEqual(updated.price, Decimal("105.00"))

        removed = remove_shop_product(
            self.session,
            self.owner,
            self.shops[0].id,
            created.id,
        )
        self.assertFalse(removed.is_available)
        public_detail = get_shop_detail(self.session, self.shops[0].id)
        owner_products = list_owned_shops(self.session, self.owner)[0].products
        self.assertNotIn(created.id, [product.id for product in public_detail.products])
        self.assertIn(created.id, [product.id for product in owner_products])

        restored = set_shop_product_availability(
            self.session,
            self.owner,
            self.shops[0].id,
            created.id,
            ProductAvailabilityRequest(is_available=True),
        )
        self.assertTrue(restored.is_available)
        self.assertIn(
            created.id,
            [
                product.id
                for product in get_shop_detail(
                    self.session,
                    self.shops[0].id,
                ).products
            ],
        )

    def test_owner_cannot_manage_another_shop_menu(self) -> None:
        other_owner = User(
            phone_number="+905550009880",
            full_name="Other Owner",
            role=UserRole.SHOP_OWNER.value,
        )
        self.session.add(other_owner)
        self.session.commit()
        payload = ProductUpsertRequest(
            name="Unauthorized",
            category="COFFEE",
            price=Decimal("10.00"),
        )

        with self.assertRaises(HTTPException) as error:
            create_shop_product(
                self.session,
                other_owner,
                self.shops[0].id,
                payload,
            )

        self.assertEqual(error.exception.status_code, 404)

    def test_product_price_configuration_must_keep_all_options_positive(self) -> None:
        with self.assertRaises(ValidationError):
            ProductUpsertRequest(
                name="Invalid drink",
                category="COFFEE",
                price=Decimal("5.00"),
                size_price_deltas={
                    CoffeeSize.S: Decimal("-6.00"),
                    CoffeeSize.M: Decimal("0.00"),
                    CoffeeSize.L: Decimal("0.00"),
                },
            )

    def test_initialize_database_adds_product_price_columns_to_old_database(
        self,
    ) -> None:
        legacy_engine = create_engine("sqlite://")
        try:
            with legacy_engine.begin() as connection:
                connection.exec_driver_sql(
                    """
                    CREATE TABLE products (
                        id INTEGER PRIMARY KEY,
                        shop_id INTEGER NOT NULL,
                        name VARCHAR(120) NOT NULL,
                        description TEXT,
                        category VARCHAR(50) NOT NULL,
                        price NUMERIC(10, 2) NOT NULL,
                        is_available BOOLEAN NOT NULL
                    )
                    """
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO products
                            (id, shop_id, name, category, price, is_available)
                        VALUES (1, 1, 'Espresso', 'COFFEE', 100.00, 1)
                        """
                    )
                )

            initialize_database(legacy_engine)
            columns = {
                column["name"]
                for column in inspect(legacy_engine).get_columns("products")
            }
            with legacy_engine.connect() as connection:
                migrated_product = connection.execute(
                    text(
                        """
                        SELECT size_price_deltas, milk_price_deltas,
                               extra_shot_price
                        FROM products WHERE id = 1
                        """
                    )
                ).one()

            self.assertTrue(
                {
                    "size_price_deltas",
                    "milk_price_deltas",
                    "extra_shot_price",
                }.issubset(columns)
            )
            self.assertEqual(json.loads(migrated_product[0])["M"], "0.00")
            self.assertEqual(
                json.loads(migrated_product[1])["WHOLE"],
                "0.00",
            )
            self.assertEqual(Decimal(migrated_product[2]), Decimal("0.00"))
        finally:
            legacy_engine.dispose()

    def test_location_requires_both_coordinates(self) -> None:
        with self.assertRaises(HTTPException) as error:
            list_shops(self.session, latitude=39.9208)
        self.assertEqual(error.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
