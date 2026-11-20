import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.roles import UserRole
from app.core.security import hash_password, verify_password
from app.db.database import Base, engine
from app.models.product import (
    DEFAULT_MILK_PRICE_DELTAS,
    DEFAULT_SIZE_PRICE_DELTAS,
)
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User


PLAN_CATALOG = (
    {
        "code": "STARTER",
        "name": "Starter",
        "monthly_price": Decimal("89.99"),
        "monthly_credits": 10,
        "guest_credits": 0,
        "priority_pickup": False,
    },
    {
        "code": "PREMIUM",
        "name": "Premium",
        "monthly_price": Decimal("149.99"),
        "monthly_credits": 20,
        "guest_credits": 2,
        "priority_pickup": False,
    },
    {
        "code": "UNLIMITED",
        "name": "Unlimited",
        "monthly_price": Decimal("249.99"),
        "monthly_credits": None,
        "guest_credits": 5,
        "priority_pickup": True,
    },
)


def _insert_default_plans(connection) -> None:
    for plan in PLAN_CATALOG:
        parameters = {
            **plan,
            "monthly_price": str(plan["monthly_price"]),
            "priority_pickup": int(plan["priority_pickup"]),
        }
        connection.execute(
            text(
                """
                INSERT OR IGNORE INTO subscription_plans
                    (code, name, monthly_price, monthly_credits, guest_credits,
                     priority_pickup, is_active)
                VALUES
                    (:code, :name, :monthly_price, :monthly_credits, :guest_credits,
                     :priority_pickup, 1)
                """
            ),
            parameters,
        )


def _migrate_subscriptions(target_engine: Engine) -> None:
    with target_engine.begin() as connection:
        old_subscriptions = connection.execute(
            text(
                """
                SELECT id, user_id, plan_type, monthly_price, monthly_credits,
                       remaining_credits, status, started_at, expires_at
                FROM subscriptions
                ORDER BY id
                """
            )
        ).mappings().all()
        _insert_default_plans(connection)

        plan_ids = {
            row["code"]: row["id"]
            for row in connection.execute(
                text("SELECT id, code FROM subscription_plans")
            ).mappings()
        }
        for subscription in old_subscriptions:
            code = subscription["plan_type"].upper()
            if code not in plan_ids:
                result = connection.execute(
                    text(
                        """
                        INSERT INTO subscription_plans
                            (code, name, monthly_price, monthly_credits,
                             guest_credits, priority_pickup, is_active)
                        VALUES
                            (:code, :name, :monthly_price, :monthly_credits, 0, 0, 1)
                        """
                    ),
                    {
                        "code": code,
                        "name": subscription["plan_type"].title(),
                        "monthly_price": subscription["monthly_price"],
                        "monthly_credits": subscription["monthly_credits"],
                    },
                )
                plan_ids[code] = result.lastrowid

        connection.exec_driver_sql(
            "ALTER TABLE subscriptions RENAME TO subscriptions_legacy"
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE subscriptions (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                plan_id INTEGER NOT NULL,
                remaining_credits INTEGER,
                status VARCHAR(20) NOT NULL,
                started_at DATETIME NOT NULL,
                expires_at DATETIME NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users (id),
                FOREIGN KEY(plan_id) REFERENCES subscription_plans (id)
            )
            """
        )
        for subscription in old_subscriptions:
            connection.execute(
                text(
                    """
                    INSERT INTO subscriptions
                        (id, user_id, plan_id, remaining_credits, status,
                         started_at, expires_at)
                    VALUES
                        (:id, :user_id, :plan_id, :remaining_credits, :status,
                         :started_at, :expires_at)
                    """
                ),
                {
                    **subscription,
                    "plan_id": plan_ids[subscription["plan_type"].upper()],
                },
            )
        connection.exec_driver_sql("DROP TABLE subscriptions_legacy")
        connection.exec_driver_sql(
            "CREATE INDEX ix_subscriptions_user_id ON subscriptions (user_id)"
        )


def initialize_database(target_engine: Engine = engine) -> None:
    Base.metadata.create_all(bind=target_engine)

    inspector = inspect(target_engine)
    if inspector.has_table("users"):
        user_columns = {
            column["name"] for column in inspector.get_columns("users")
        }
        with target_engine.begin() as connection:
            if "password_hash" not in user_columns:
                connection.execute(
                    text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)")
                )
            if "phone_verified_at" not in user_columns:
                connection.execute(
                    text("ALTER TABLE users ADD COLUMN phone_verified_at DATETIME")
                )
            if "profile_completed" not in user_columns:
                connection.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN "
                        "profile_completed BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
            if "username" not in user_columns:
                connection.execute(
                    text("ALTER TABLE users ADD COLUMN username VARCHAR(15)")
                )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username "
                    "ON users (username)"
                )
            )

    if inspector.has_table("subscriptions") and "plan_id" not in {
        column["name"] for column in inspector.get_columns("subscriptions")
    }:
        _migrate_subscriptions(target_engine)

    product_columns = {
        column["name"] for column in inspect(target_engine).get_columns("products")
    }
    with target_engine.begin() as connection:
        if "size_price_deltas" not in product_columns:
            default_size_deltas = json.dumps(
                DEFAULT_SIZE_PRICE_DELTAS, separators=(",", ":")
            )
            connection.exec_driver_sql(
                "ALTER TABLE products ADD COLUMN size_price_deltas JSON "
                f"NOT NULL DEFAULT '{default_size_deltas}'"
            )
        if "milk_price_deltas" not in product_columns:
            default_milk_deltas = json.dumps(
                DEFAULT_MILK_PRICE_DELTAS, separators=(",", ":")
            )
            connection.exec_driver_sql(
                "ALTER TABLE products ADD COLUMN milk_price_deltas JSON "
                f"NOT NULL DEFAULT '{default_milk_deltas}'"
            )
        if "extra_shot_price" not in product_columns:
            connection.exec_driver_sql(
                "ALTER TABLE products ADD COLUMN extra_shot_price "
                "NUMERIC(10, 2) NOT NULL DEFAULT 0.00"
            )

    with target_engine.begin() as connection:
        _insert_default_plans(connection)


def ensure_admin_account(
    target_engine: Engine = engine,
    *,
    environment: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> None:
    environment = (
        environment or os.getenv("KAHVECELL_ENV", "development")
    ).strip().lower()
    if environment == "development":
        username = (
            username
            or os.getenv("KAHVECELL_ADMIN_USERNAME")
            or "admin"
        )
        password = (
            password
            or os.getenv("KAHVECELL_ADMIN_PASSWORD")
            or "admin"
        )
    else:
        username = username or os.getenv("KAHVECELL_ADMIN_USERNAME")
        password = password or os.getenv("KAHVECELL_ADMIN_PASSWORD")
        if not username or not password:
            raise RuntimeError(
                "KAHVECELL_ADMIN_USERNAME and KAHVECELL_ADMIN_PASSWORD "
                "are required outside development."
            )
        if len(password) < 12 or password == "admin":
            raise RuntimeError(
                "The production admin password must be at least 12 "
                "characters and must not be 'admin'."
            )
        if username.strip().casefold() == "admin":
            raise RuntimeError(
                "The production admin username must not be the default 'admin'."
            )

    if not username or not password:
        raise RuntimeError("Admin username and password must not be empty.")
    normalized_username = username.strip().casefold()
    if not re.fullmatch(r"[a-z][a-z0-9._-]{2,14}", normalized_username):
        raise RuntimeError(
            "The admin username must start with a letter and contain "
            "3-15 letters, numbers, dots, underscores or hyphens."
        )

    with Session(target_engine, expire_on_commit=False) as session:
        existing_admin = session.scalar(
            select(User).where(User.username == normalized_username)
        )
        if existing_admin is not None:
            if existing_admin.role != UserRole.ADMIN.value:
                raise RuntimeError(
                    "The configured admin username already belongs to "
                    "a non-admin user."
                )
            if environment != "development" and (
                existing_admin.password_hash is None
                or not verify_password(
                    password,
                    existing_admin.password_hash,
                )
            ):
                existing_admin.password_hash = hash_password(password)
            if existing_admin.phone_verified_at is None:
                existing_admin.phone_verified_at = datetime.now(
                    timezone.utc
                ).replace(tzinfo=None)
            session.commit()
            return

        if environment != "development":
            local_admin = session.scalar(
                select(User).where(
                    User.username == "admin",
                    User.role == UserRole.ADMIN.value,
                )
            )
            if local_admin is not None:
                raise RuntimeError(
                    "A development admin account exists in this database. "
                    "Use a clean production database or configure its "
                    "admin credentials before deployment."
                )

        phone_collision = session.scalar(
            select(User.id).where(User.phone_number == normalized_username)
        )
        if phone_collision is not None:
            raise RuntimeError(
                "The admin username conflicts with an existing phone number."
            )
        admin = User(
            username=normalized_username,
            phone_number=normalized_username,
            full_name="KahveCell Admin",
            password_hash=hash_password(password),
            role=UserRole.ADMIN.value,
            phone_verified_at=datetime.now(timezone.utc).replace(tzinfo=None),
            profile_completed=True,
        )
        session.add(admin)
        session.commit()
