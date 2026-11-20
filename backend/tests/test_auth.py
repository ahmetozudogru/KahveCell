import unittest
from datetime import datetime, timezone

import jwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from app.api.v1.auth import (
    change_password,
    get_profile,
    login,
    register,
    update_profile,
    verify_otp,
)
from app.api.v1.dependencies import get_current_user, require_roles
from app.core.roles import UserRole
from app.core.security import (
    JWT_ALGORITHM,
    JWT_SECRET,
    hash_password,
    verify_password,
)
from app.db.database import Base
from app.db.init_db import ensure_admin_account, initialize_database
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    OTPVerifyRequest,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    RegisterRequest,
)
from pydantic import ValidationError


class AuthFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_otp_verification_issues_a_valid_token(self) -> None:
        challenge = register(
            RegisterRequest(
                phone_number="+905550001235",
                full_name="Test Customer",
                password="test-password-123",
            ),
            self.session,
        )
        self.assertTrue(challenge.is_new_user)
        self.assertEqual(challenge.demo_otp, "1234")

        with self.assertRaises(HTTPException) as error:
            verify_otp(
                OTPVerifyRequest(phone_number="+905550001235", otp="0000"),
                self.session,
            )
        self.assertEqual(error.exception.status_code, 401)

        result = verify_otp(
            OTPVerifyRequest(phone_number="+905550001235", otp="1234"),
            self.session,
        )
        claims = jwt.decode(
            result.access_token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
        self.assertEqual(claims["role"], UserRole.CUSTOMER.value)
        self.assertEqual(claims["type"], "access")
        self.assertEqual(result.role, UserRole.CUSTOMER)

        user = get_current_user(
            HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=result.access_token,
            ),
            self.session,
        )
        self.assertTrue(get_profile(user).phone_verified)

    def test_profile_completion_and_role_authorization(self) -> None:
        register(
            RegisterRequest(
                phone_number="+905550001236",
                full_name="Demo User",
                password="test-password-123",
            ),
            self.session,
        )
        token = verify_otp(
            OTPVerifyRequest(phone_number="+905550001236", otp="1234"),
            self.session,
        )
        user = get_current_user(
            HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=token.access_token,
            ),
            self.session,
        )

        profile = update_profile(
            ProfileUpdateRequest(
                full_name="Demo User",
                coffee_preferences=["Latte"],
                allergens=["Milk"],
            ),
            user,
            self.session,
        )
        self.assertTrue(profile.profile_completed)
        self.assertEqual(profile.coffee_preferences, ["Latte"])
        self.assertEqual(profile.allergens, ["Milk"])

        admin_only = require_roles(UserRole.ADMIN)
        with self.assertRaises(HTTPException) as error:
            admin_only(user)
        self.assertEqual(error.exception.status_code, 403)

    def test_profile_phone_change_requires_verification_and_is_normalized(self) -> None:
        user = User(
            phone_number="+905550009860",
            full_name="Profile Customer",
            role=UserRole.CUSTOMER.value,
            phone_verified_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        self.session.add(user)
        self.session.commit()

        profile = update_profile(
            ProfileUpdateRequest(
                full_name="New Profile Name",
                phone_number=" +90 (555) 000-9861 ",
            ),
            user,
            self.session,
        )

        self.assertEqual(profile.phone_number, "+905550009861")
        self.assertFalse(profile.phone_verified)

    def test_profile_phone_cannot_be_assigned_to_another_user(self) -> None:
        user = User(
            phone_number="+905550009860",
            full_name="Profile Customer",
            role=UserRole.CUSTOMER.value,
        )
        other_user = User(
            phone_number="+905550009861",
            full_name="Other Customer",
            role=UserRole.CUSTOMER.value,
        )
        self.session.add_all([user, other_user])
        self.session.commit()

        with self.assertRaises(HTTPException) as error:
            update_profile(
                ProfileUpdateRequest(
                    full_name="Profile Customer",
                    phone_number="+905550009861",
                ),
                user,
                self.session,
            )

        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(user.phone_number, "+905550009860")

    def test_user_can_change_password_after_current_password_is_verified(self) -> None:
        user = User(
            phone_number="+905550009859",
            full_name="Password Customer",
            role=UserRole.CUSTOMER.value,
            password_hash=hash_password("current-password"),
        )
        self.session.add(user)
        self.session.commit()

        with self.assertRaises(HTTPException) as error:
            change_password(
                PasswordChangeRequest(
                    current_password="wrong-password",
                    new_password="new-password-123",
                ),
                user,
                self.session,
            )
        self.assertEqual(error.exception.status_code, 400)
        self.assertTrue(verify_password("current-password", user.password_hash))

        result = change_password(
            PasswordChangeRequest(
                current_password="current-password",
                new_password="new-password-123",
            ),
            user,
            self.session,
        )
        self.assertEqual(result.message, "Şifreniz güncellendi.")
        self.assertTrue(verify_password("new-password-123", user.password_hash))

    def test_password_change_rejects_reusing_current_password(self) -> None:
        with self.assertRaises(ValidationError):
            PasswordChangeRequest(
                current_password="same-password",
                new_password="same-password",
            )

    def test_password_login_requires_a_verified_phone(self) -> None:
        register(
            RegisterRequest(
                phone_number="+905550001237",
                full_name="Login Test",
                password="test-password-123",
            ),
            self.session,
        )
        credentials = LoginRequest(
            phone_number="+905550001237",
            password="test-password-123",
        )

        with self.assertRaises(HTTPException) as error:
            login(credentials, self.session)
        self.assertEqual(error.exception.status_code, 403)

        verify_otp(
            OTPVerifyRequest(phone_number="+905550001237", otp="1234"),
            self.session,
        )
        token = login(credentials, self.session)
        claims = jwt.decode(
            token.access_token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
        self.assertEqual(claims["role"], UserRole.CUSTOMER.value)
        self.assertEqual(token.role, UserRole.CUSTOMER)

        with self.assertRaises(HTTPException) as error:
            login(
                LoginRequest(
                    phone_number="+905550001237",
                    password="incorrect-password",
                ),
                self.session,
            )
        self.assertEqual(error.exception.status_code, 401)

    def test_shop_owner_login_returns_shop_owner_role(self) -> None:
        self.session.add(
            User(
                phone_number="+905550009870",
                full_name="Owner Login Test",
                role=UserRole.SHOP_OWNER.value,
                password_hash=hash_password("owner-password-123"),
                phone_verified_at=datetime.now(timezone.utc).replace(
                    tzinfo=None
                ),
            )
        )
        self.session.commit()

        result = login(
            LoginRequest(
                phone_number="+905550009870",
                password="owner-password-123",
            ),
            self.session,
        )
        self.assertEqual(result.role, UserRole.SHOP_OWNER)

    def test_development_admin_bootstrap_and_username_login(self) -> None:
        ensure_admin_account(self.engine, environment="development")
        admin = self.session.scalar(
            select(User).where(User.username == "admin")
        )
        self.assertIsNotNone(admin)
        first_password_hash = admin.password_hash

        ensure_admin_account(self.engine, environment="development")
        self.session.refresh(admin)
        self.assertEqual(admin.password_hash, first_password_hash)

        result = login(
            LoginRequest(username="ADMIN", password="admin"),
            self.session,
        )
        self.assertEqual(result.role, UserRole.ADMIN)
        with self.assertRaises(ValidationError):
            LoginRequest(phone_number="+905550001238", password="short")

    def test_admin_bootstrap_requires_custom_production_credentials(self) -> None:
        with self.assertRaises(RuntimeError):
            ensure_admin_account(
                self.engine,
                environment="production",
                username="admin",
                password="admin",
            )

        ensure_admin_account(
            self.engine,
            environment="production",
            username="ops-admin",
            password="secure-production-password",
        )
        result = login(
            LoginRequest(
                username="ops-admin",
                password="secure-production-password",
            ),
            self.session,
        )
        self.assertEqual(result.role, UserRole.ADMIN)

    def test_initialize_database_adds_unique_username_to_legacy_users(self) -> None:
        legacy_engine = create_engine("sqlite://")
        try:
            with legacy_engine.begin() as connection:
                connection.exec_driver_sql(
                    """
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY,
                        phone_number VARCHAR(15) NOT NULL,
                        full_name VARCHAR(100) NOT NULL,
                        email VARCHAR(255),
                        password_hash VARCHAR(255),
                        role VARCHAR(20) NOT NULL,
                        preferences VARCHAR,
                        phone_verified_at DATETIME,
                        profile_completed BOOLEAN NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL
                    )
                    """
                )

            initialize_database(legacy_engine)
            columns = {
                column["name"]
                for column in inspect(legacy_engine).get_columns("users")
            }
            username_index = next(
                index
                for index in inspect(legacy_engine).get_indexes("users")
                if index["name"] == "ix_users_username"
            )

            self.assertIn("username", columns)
            self.assertTrue(username_index["unique"])
            self.assertEqual(username_index["column_names"], ["username"])
        finally:
            legacy_engine.dispose()


if __name__ == "__main__":
    unittest.main()
