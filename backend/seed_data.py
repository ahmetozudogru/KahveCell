import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.core.roles import UserRole
from app.core.security import hash_password
from app.db.database import engine
from app.db.init_db import initialize_database
from app.models import (
    Product,
    Shop,
    ShopRating,
    Subscription,
    SubscriptionPlan,
    User,
)


DEMO_PHONE = "+905550001234"
DEMO_PASSWORD = "Kahve2026!"
DEMO_SHOP_OWNER_PASSWORD = "KahveSahibi2026!"
DEMO_RATING_USER_COUNT = 100

BASE_PRODUCTS = (
    ("Espresso", "Single espresso", Decimal("115.00")),
    ("Americano", "Espresso with hot water", Decimal("145.00")),
    ("Cappuccino", "Espresso with steamed milk and milk foam", Decimal("170.00")),
    ("Latte", "Espresso with steamed milk", Decimal("180.00")),
    ("Turkish Coffee", "Traditional Turkish coffee", Decimal("135.00")),
)

# Location data: © OpenStreetMap contributors (ODbL 1.0); prices are estimates.
SHOPS = (
    {
        "name": "Cafe Down Engelsiz Cafe",
        "address": "İzmir 1 Caddesi, Kızılay Mahallesi, Çankaya, Ankara",
        "latitude": 39.9229865,
        "longitude": 32.8539956,
        "price_factor": Decimal("1.00"),
        "owner_phone_number": "+905550001236",
        "owner_full_name": "Demo Cafe Down Sahibi",
    },
    {
        "name": "Kocatepe Coffee 1919 Bahçelievler 7.Cadde",
        "address": "70. Sokak, Yukarı Bahçelievler Mahallesi, Çankaya, Ankara",
        "latitude": 39.9219387,
        "longitude": 32.8255133,
        "price_factor": Decimal("0.97"),
        "owner_phone_number": "+905550001237",
        "owner_full_name": "Demo Bahcelievler Sahibi",
    },
    {
        "name": "Cafe des Cafes",
        "address": "83, Tunalı Hilmi Caddesi, Barbaros Mahallesi, Çankaya, Ankara",
        "latitude": 39.9066216,
        "longitude": 32.8612044,
        "price_factor": Decimal("1.08"),
        "owner_phone_number": "+905550001238",
        "owner_full_name": "Demo Tunali Sahibi",
    },
    {
        "name": "Çimen Cafe & Bistro",
        "address": "2590. Sokak, Koru Mahallesi, Çayyolu, Çankaya, Ankara",
        "latitude": 39.8822544,
        "longitude": 32.6849103,
        "price_factor": Decimal("1.05"),
        "owner_phone_number": "+905550001239",
        "owner_full_name": "Demo Cay yolu Sahibi",
    },
    {
        "name": "Mozart Cafe",
        "address": "3. Cadde, Bilkent Yurtlar, Üniversiteler Mahallesi, Çankaya, Ankara",
        "latitude": 39.8695452,
        "longitude": 32.7550274,
        "price_factor": Decimal("1.03"),
        "owner_phone_number": "+905550001240",
        "owner_full_name": "Demo Bilkent Sahibi",
    },
)

DEMO_SHOP_OWNER_PHONES = {
    shop["owner_phone_number"] for shop in SHOPS
}


def _demo_rating(shop_index: int, reviewer_index: int) -> int:
    average_tenths = 32 + (shop_index % 5) * 4
    lower_rating = average_tenths // 10
    higher_rating_count = (average_tenths % 10) * DEMO_RATING_USER_COUNT // 10
    rating_position = (reviewer_index * 37 + shop_index * 13) % 100
    return lower_rating + 1 if rating_position < higher_rating_count else lower_rating


def seed_data(
    target_engine: Engine = engine,
    *,
    environment: str | None = None,
) -> tuple[int, int]:
    environment = (
        environment or os.getenv("KAHVECELL_ENV", "development")
    ).strip().lower()
    if environment != "development":
        raise RuntimeError("Demo shop, user, and rating data is development-only.")

    initialize_database(target_engine)
    session_factory = sessionmaker(
        bind=target_engine, autoflush=False, expire_on_commit=False
    )

    shops_added = 0
    products_added = 0
    with session_factory.begin() as session:
        user = session.scalar(
            select(User).where(User.phone_number == DEMO_PHONE)
        )
        if user is None:
            user = User(phone_number=DEMO_PHONE, full_name="Demo Kullanıcısı")
            session.add(user)
            session.flush()
        user.password_hash = hash_password(DEMO_PASSWORD)
        if user.phone_verified_at is None:
            user.phone_verified_at = datetime.now(timezone.utc).replace(
                tzinfo=None
            )

        starter_plan = session.scalar(
            select(SubscriptionPlan).where(SubscriptionPlan.code == "STARTER")
        )
        active_subscription = session.scalar(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.plan_id == starter_plan.id,
                Subscription.status == "ACTIVE",
            )
        )
        if active_subscription is None:
            started_at = datetime.now(timezone.utc).replace(tzinfo=None)
            session.add(
                Subscription(
                    user_id=user.id,
                    plan_id=starter_plan.id,
                    remaining_credits=10,
                    status="ACTIVE",
                    started_at=started_at,
                    expires_at=started_at + timedelta(days=30),
                )
            )

        for shop_data in SHOPS:
            shop = session.scalar(
                select(Shop).where(
                    Shop.name == shop_data["name"],
                    Shop.address == shop_data["address"],
                )
            )
            if shop is None:
                shop = Shop(
                    name=shop_data["name"],
                    address=shop_data["address"],
                    latitude=shop_data["latitude"],
                    longitude=shop_data["longitude"],
                )
                session.add(shop)
                session.flush()
                shops_added += 1

            shop_owner = session.scalar(
                select(User).where(
                    User.phone_number == shop_data["owner_phone_number"]
                )
            )
            if shop_owner is None:
                shop_owner = User(
                    phone_number=shop_data["owner_phone_number"],
                    full_name=shop_data["owner_full_name"],
                    role=UserRole.SHOP_OWNER.value,
                    profile_completed=True,
                )
                session.add(shop_owner)
                session.flush()
            elif shop_owner.role != UserRole.SHOP_OWNER.value:
                raise RuntimeError(
                    "A reserved demo shop-owner phone is already used by another role."
                )
            shop_owner.password_hash = hash_password(DEMO_SHOP_OWNER_PASSWORD)
            if shop_owner.phone_verified_at is None:
                shop_owner.phone_verified_at = (
                    datetime.now(timezone.utc).replace(tzinfo=None)
                )

            if shop.owner_id is not None and shop.owner_id != shop_owner.id:
                previous_owner = session.get(User, shop.owner_id)
                if (
                    previous_owner is None
                    or previous_owner.phone_number not in DEMO_SHOP_OWNER_PHONES
                ):
                    raise RuntimeError(
                        f"Seed shop '{shop.name}' is assigned to a non-demo owner."
                    )
            shop.owner_id = shop_owner.id

            for name, description, base_price in BASE_PRODUCTS:
                product = session.scalar(
                    select(Product).where(
                        Product.shop_id == shop.id,
                        Product.name == name,
                    )
                )
                if product is None:
                    session.add(
                        Product(
                            shop_id=shop.id,
                            name=name,
                            description=description,
                            category="COFFEE",
                            price=base_price * shop_data["price_factor"],
                            is_available=True,
                        )
                    )
                    products_added += 1

        sample_users: list[User] = []
        seeded_at = datetime.now(timezone.utc).replace(tzinfo=None)
        for index in range(1, DEMO_RATING_USER_COUNT + 1):
            username = f"reviewer{index:03d}"
            phone_number = f"+1555010{index:04d}"
            reviewer = session.scalar(
                select(User).where(User.username == username)
            )
            if reviewer is None:
                phone_collision = session.scalar(
                    select(User.id).where(User.phone_number == phone_number)
                )
                if phone_collision is not None:
                    raise RuntimeError(
                        f"Reserved demo reviewer phone {phone_number} is "
                        "already used by another account."
                    )
                reviewer = User(
                    username=username,
                    phone_number=phone_number,
                    full_name=f"Örnek Kullanıcı {index:03d}",
                    role=UserRole.CUSTOMER.value,
                    phone_verified_at=seeded_at,
                    profile_completed=True,
                )
                session.add(reviewer)
                session.flush()
            elif (
                reviewer.phone_number != phone_number
                or reviewer.role != UserRole.CUSTOMER.value
            ):
                raise RuntimeError(
                    f"Reserved demo reviewer username {username} is already "
                    "used by another account."
                )
            sample_users.append(reviewer)

        shops = session.scalars(select(Shop).order_by(Shop.id)).all()
        existing_ratings = {
            (user_id, shop_id)
            for user_id, shop_id in session.execute(
                select(ShopRating.user_id, ShopRating.shop_id).where(
                    ShopRating.user_id.in_(
                        [reviewer.id for reviewer in sample_users]
                    ),
                    ShopRating.shop_id.in_([shop.id for shop in shops]),
                )
            ).all()
        }
        for shop_index, shop in enumerate(shops):
            for reviewer_index, reviewer in enumerate(sample_users):
                rating_key = (reviewer.id, shop.id)
                if rating_key in existing_ratings:
                    continue
                session.add(
                    ShopRating(
                        user_id=reviewer.id,
                        shop_id=shop.id,
                        rating=_demo_rating(shop_index, reviewer_index),
                        created_at=seeded_at,
                    )
                )
                existing_ratings.add(rating_key)

        session.flush()
        for shop in shops:
            average_rating = session.scalar(
                select(func.avg(ShopRating.rating)).where(
                    ShopRating.shop_id == shop.id
                )
            )
            if average_rating is not None:
                shop.rating = round(float(average_rating), 2)

    return shops_added, products_added


if __name__ == "__main__":
    shops_added, products_added = seed_data()
    print(f"Yeni eklenen dukkan: {shops_added}")
    print(f"Yeni eklenen urun: {products_added}")
    print(f"Ornek puan veren kullanici: {DEMO_RATING_USER_COUNT}")
    print("Ornek restoran puanlari: 3.2 ile 4.8 arasinda")
    print(f"Demo telefon: {DEMO_PHONE}")
    print(f"Demo sifre: {DEMO_PASSWORD}")
    print("Starter abonelik: aktif, 10 kahve hakki")
    for shop_data in SHOPS:
        print(
            f"Test dukkan sahibi ({shop_data['name']}): "
            f"{shop_data['owner_phone_number']} | "
            f"Sifre: {DEMO_SHOP_OWNER_PASSWORD}"
        )
    print("Urun fiyatlari test amacli tahminidir; resmi menu fiyatlari degildir.")
