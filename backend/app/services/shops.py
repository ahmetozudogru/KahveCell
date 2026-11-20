import math

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.product import Product
from app.models.shop import Shop
from app.models.shop_rating import ShopRating
from app.models.user import User
from app.schemas.shops import (
    MyShopRatingResponse,
    ProductResponse,
    ProductUpsertRequest,
    ShopRatingRequest,
    ShopRatingResult,
    ShopHoursUpdateRequest,
    ShopDetailResponse,
    ShopListResponse,
    ShopMenuResponse,
)

EARTH_RADIUS_KM = 6371.0088


def haversine_distance_km(
    latitude: float,
    longitude: float,
    shop_latitude: float,
    shop_longitude: float,
) -> float:
    latitude_delta = math.radians(shop_latitude - latitude)
    longitude_delta = math.radians(shop_longitude - longitude)
    latitude_radians = math.radians(latitude)
    shop_latitude_radians = math.radians(shop_latitude)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(latitude_radians)
        * math.cos(shop_latitude_radians)
        * math.sin(longitude_delta / 2) ** 2
    )
    central_angle = 2 * math.asin(math.sqrt(min(1.0, haversine)))
    return EARTH_RADIUS_KM * central_angle


def _product_response(product: Product) -> ProductResponse:
    return ProductResponse(
        id=product.id,
        name=product.name,
        description=product.description,
        category=product.category,
        price=product.price,
        size_price_deltas=product.size_price_deltas,
        milk_price_deltas=product.milk_price_deltas,
        extra_shot_price=product.extra_shot_price,
        is_available=product.is_available,
    )


def _owned_shop_or_404(
    session: Session,
    shop_id: int,
    owner: User,
) -> Shop:
    shop = session.scalar(
        select(Shop).where(Shop.id == shop_id, Shop.owner_id == owner.id)
    )
    if shop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dükkân bulunamadı.",
        )
    return shop


def _owned_product_or_404(
    session: Session,
    shop_id: int,
    product_id: int,
    owner: User,
) -> Product:
    _owned_shop_or_404(session, shop_id, owner)
    product = session.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.shop_id == shop_id,
        )
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ürün bulunamadı.",
        )
    return product


def _product_write_values(payload: ProductUpsertRequest) -> dict[str, object]:
    return {
        "name": payload.name.strip(),
        "description": payload.description.strip() or None
        if payload.description is not None
        else None,
        "category": payload.category.strip(),
        "price": payload.price,
        "size_price_deltas": {
            size.value: f"{price_delta:.2f}"
            for size, price_delta in payload.size_price_deltas.items()
        },
        "milk_price_deltas": {
            milk_type.value: f"{price_delta:.2f}"
            for milk_type, price_delta in payload.milk_price_deltas.items()
        },
        "extra_shot_price": payload.extra_shot_price,
    }


def _shop_response(
    shop: Shop,
    distance_km: float | None = None,
) -> ShopListResponse:
    return ShopListResponse(
        id=shop.id,
        name=shop.name,
        address=shop.address,
        latitude=shop.latitude,
        longitude=shop.longitude,
        opening_hours=shop.opening_hours,
        rating=shop.rating,
        rating_count=len(shop.ratings),
        distance_km=round(distance_km, 2) if distance_km is not None else None,
    )


def list_shops(
    session: Session,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float | None = None,
    search: str | None = None,
) -> list[ShopListResponse]:
    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Yakınlık araması için lat ve lng birlikte gönderilmelidir.",
        )
    if radius_km is not None and latitude is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="radius_km kullanmak için lat ve lng gönderilmelidir.",
        )

    shops = session.scalars(
        select(Shop).options(selectinload(Shop.ratings))
    ).all()
    normalized_search = search.strip().casefold() if search else ""
    if normalized_search:
        shops = [
            shop
            for shop in shops
            if normalized_search in shop.name.casefold()
            or normalized_search in shop.address.casefold()
        ]

    if latitude is None or longitude is None:
        return [_shop_response(shop) for shop in shops]

    nearby: list[tuple[Shop, float]] = []
    for shop in shops:
        distance = haversine_distance_km(
            latitude,
            longitude,
            shop.latitude,
            shop.longitude,
        )
        if radius_km is None or distance <= radius_km:
            nearby.append((shop, distance))
    nearby.sort(key=lambda result: result[1])
    return [_shop_response(shop, distance) for shop, distance in nearby]


def list_owned_shops(
    session: Session,
    owner: User,
) -> list[ShopDetailResponse]:
    shops = session.scalars(
        select(Shop)
        .options(selectinload(Shop.products), selectinload(Shop.ratings))
        .where(Shop.owner_id == owner.id)
        .order_by(Shop.name)
    ).all()
    return [
        ShopDetailResponse(
            **_shop_response(shop).model_dump(),
            products=[
                _product_response(product)
                for product in sorted(
                    shop.products,
                    key=lambda item: item.name.casefold(),
                )
            ],
        )
        for shop in shops
    ]


def update_shop_opening_hours(
    session: Session,
    owner: User,
    shop_id: int,
    payload: ShopHoursUpdateRequest,
) -> ShopListResponse:
    shop = _owned_shop_or_404(session, shop_id, owner)
    shop.opening_hours = payload.opening_hours
    session.commit()
    session.refresh(shop)
    return _shop_response(shop)


def create_shop_product(
    session: Session,
    owner: User,
    shop_id: int,
    payload: ProductUpsertRequest,
) -> ProductResponse:
    shop = _owned_shop_or_404(session, shop_id, owner)
    product = Product(shop_id=shop.id, **_product_write_values(payload))
    session.add(product)
    session.commit()
    session.refresh(product)
    return _product_response(product)


def update_shop_product(
    session: Session,
    owner: User,
    shop_id: int,
    product_id: int,
    payload: ProductUpsertRequest,
) -> ProductResponse:
    product = _owned_product_or_404(session, shop_id, product_id, owner)
    for field, value in _product_write_values(payload).items():
        setattr(product, field, value)
    session.commit()
    session.refresh(product)
    return _product_response(product)


def set_shop_product_availability(
    session: Session,
    owner: User,
    shop_id: int,
    product_id: int,
    payload: ProductAvailabilityRequest,
) -> ProductResponse:
    product = _owned_product_or_404(session, shop_id, product_id, owner)
    product.is_available = payload.is_available
    session.commit()
    session.refresh(product)
    return _product_response(product)


def remove_shop_product(
    session: Session,
    owner: User,
    shop_id: int,
    product_id: int,
) -> ProductResponse:
    product = _owned_product_or_404(session, shop_id, product_id, owner)
    product.is_available = False
    session.commit()
    session.refresh(product)
    return _product_response(product)


def get_shop_detail(
    session: Session,
    shop_id: int,
    latitude: float | None = None,
    longitude: float | None = None,
) -> ShopDetailResponse:
    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Mesafe için lat ve lng birlikte gönderilmelidir.",
        )

    shop = session.scalar(
        select(Shop)
        .options(selectinload(Shop.products), selectinload(Shop.ratings))
        .where(Shop.id == shop_id)
    )
    if shop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dükkân bulunamadı.",
        )

    distance = (
        haversine_distance_km(
            latitude,
            longitude,
            shop.latitude,
            shop.longitude,
        )
        if latitude is not None and longitude is not None
        else None
    )
    return ShopDetailResponse(
        **_shop_response(shop, distance).model_dump(),
        products=[
            _product_response(product)
            for product in sorted(
                (item for item in shop.products if item.is_available),
                key=lambda item: item.name.casefold(),
            )
        ],
    )


def get_shop_menu(session: Session, shop_id: int) -> ShopMenuResponse:
    shop = session.scalar(
        select(Shop)
        .options(selectinload(Shop.products))
        .where(Shop.id == shop_id)
    )
    if shop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dükkân bulunamadı.",
        )
    return ShopMenuResponse(
        shop_id=shop.id,
        shop_name=shop.name,
        products=[
            _product_response(product)
            for product in sorted(
                (item for item in shop.products if item.is_available),
                key=lambda item: item.name.casefold(),
            )
        ],
    )


def get_my_shop_rating(
    session: Session,
    user: User,
    shop_id: int,
) -> MyShopRatingResponse:
    if session.get(Shop, shop_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dükkân bulunamadı.",
        )
    rating = session.scalar(
        select(ShopRating.rating).where(
            ShopRating.user_id == user.id,
            ShopRating.shop_id == shop_id,
        )
    )
    return MyShopRatingResponse(rating=rating)


def rate_shop(
    session: Session,
    user: User,
    shop_id: int,
    payload: ShopRatingRequest,
) -> ShopRatingResult:
    shop = session.get(Shop, shop_id)
    if shop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dükkân bulunamadı.",
        )

    rating = session.scalar(
        select(ShopRating).where(
            ShopRating.user_id == user.id,
            ShopRating.shop_id == shop_id,
        )
    )
    if rating is None:
        rating = ShopRating(
            user_id=user.id,
            shop_id=shop_id,
            rating=payload.rating,
        )
        session.add(rating)
    else:
        rating.rating = payload.rating

    session.flush()
    average_rating, rating_count = session.execute(
        select(
            func.avg(ShopRating.rating),
            func.count(ShopRating.id),
        ).where(ShopRating.shop_id == shop_id)
    ).one()
    shop.rating = round(float(average_rating), 2)
    session.commit()

    return ShopRatingResult(
        user_rating=payload.rating,
        average_rating=shop.rating,
        rating_count=rating_count,
    )
