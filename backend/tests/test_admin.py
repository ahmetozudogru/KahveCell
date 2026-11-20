import unittest
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.admin import (
    create_admin_shop,
    list_admin_shops,
    list_users,
    update_admin_shop,
    update_user_role,
)
from app.core.roles import UserRole
from app.db.database import Base
from app.models.shop import Shop
from app.models.user import User
from app.schemas.admin import AdminShopUpsertRequest
from app.schemas.auth import RoleUpdateRequest


class AdminManagementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        verified_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.admin = User(
            phone_number="admin",
            username="admin",
            full_name="KahveCell Admin",
            role=UserRole.ADMIN.value,
            phone_verified_at=verified_at,
        )
        self.owner = User(
            phone_number="+905550009881",
            full_name="Cafe Owner",
            role=UserRole.SHOP_OWNER.value,
            phone_verified_at=verified_at,
        )
        self.customer = User(
            phone_number="+905550009882",
            full_name="Customer",
            role=UserRole.CUSTOMER.value,
            phone_verified_at=verified_at,
        )
        self.session.add_all([self.admin, self.owner, self.customer])
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_admin_can_list_users_and_change_roles(self) -> None:
        users = list_users(self.session)
        self.assertEqual(len(users), 3)
        self.assertIsNone(next(user for user in users if user.id == self.admin.id).phone_number)

        updated = update_user_role(
            self.customer.id,
            RoleUpdateRequest(role=UserRole.SHOP_OWNER),
            self.session,
            self.admin,
        )
        self.assertEqual(updated.role, UserRole.SHOP_OWNER)

    def test_admin_cannot_remove_own_admin_role(self) -> None:
        with self.assertRaises(HTTPException) as error:
            update_user_role(
                self.admin.id,
                RoleUpdateRequest(role=UserRole.CUSTOMER),
                self.session,
                self.admin,
            )
        self.assertEqual(error.exception.status_code, 409)

    def test_admin_can_create_edit_and_unassign_shop_owner(self) -> None:
        created = create_admin_shop(
            AdminShopUpsertRequest(
                name="  Test Kahve  ",
                address="Kızılay, Ankara",
                latitude=39.9208,
                longitude=32.8541,
                opening_hours="09:00-21:00",
                owner_id=self.owner.id,
            ),
            self.session,
        )
        self.assertEqual(created.name, "Test Kahve")
        self.assertEqual(created.rating_count, 0)
        self.assertEqual(created.owner_id, self.owner.id)
        self.assertEqual(created.owner_name, "Cafe Owner")

        updated = update_admin_shop(
            created.id,
            AdminShopUpsertRequest(
                name="Yeni Kahve",
                address="Tunalı, Ankara",
                latitude=39.91,
                longitude=32.86,
                opening_hours=None,
                owner_id=None,
            ),
            self.session,
        )
        self.assertEqual(updated.name, "Yeni Kahve")
        self.assertIsNone(updated.owner_id)
        self.assertIsNone(updated.owner_name)
        self.assertEqual(len(list_admin_shops(self.session)), 1)

    def test_admin_cannot_assign_customer_as_shop_owner(self) -> None:
        with self.assertRaises(HTTPException) as error:
            create_admin_shop(
                AdminShopUpsertRequest(
                    name="Test Kahve",
                    address="Kızılay, Ankara",
                    latitude=39.9208,
                    longitude=32.8541,
                    owner_id=self.customer.id,
                ),
                self.session,
            )
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.session.query(Shop).count(), 0)


if __name__ == "__main__":
    unittest.main()
