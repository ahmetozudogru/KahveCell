from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_db, require_roles
from app.core.roles import UserRole
from app.models.user import User
from app.schemas.shops import (
    ProductAvailabilityRequest,
    ProductResponse,
    ProductUpsertRequest,
    ShopDetailResponse,
    ShopHoursUpdateRequest,
    ShopListResponse,
    ShopMenuResponse,
    MyShopRatingResponse,
    ShopRatingRequest,
    ShopRatingResult,
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
    update_shop_product,
    update_shop_opening_hours,
)

router = APIRouter(prefix="/api/v1/shops", tags=["Shops"])


@router.get("", response_model=list[ShopListResponse])
def get_shops(
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float | None = Query(default=None, gt=0, le=200),
    q: str | None = Query(default=None, description="Dükkân adı veya adresinde ara."),
    session: Session = Depends(get_db),
) -> list[ShopListResponse]:
    return list_shops(session, lat, lng, radius_km, q)


@router.get("/me", response_model=list[ShopDetailResponse])
def get_my_shops(
    user: User = Depends(require_roles(UserRole.SHOP_OWNER)),
    session: Session = Depends(get_db),
) -> list[ShopDetailResponse]:
    return list_owned_shops(session, user)


@router.patch("/{shop_id}", response_model=ShopListResponse)
def patch_shop(
    shop_id: int,
    payload: ShopHoursUpdateRequest,
    user: User = Depends(require_roles(UserRole.SHOP_OWNER)),
    session: Session = Depends(get_db),
) -> ShopListResponse:
    return update_shop_opening_hours(session, user, shop_id, payload)


@router.post(
    "/{shop_id}/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_shop_product(
    shop_id: int,
    payload: ProductUpsertRequest,
    user: User = Depends(require_roles(UserRole.SHOP_OWNER)),
    session: Session = Depends(get_db),
) -> ProductResponse:
    return create_shop_product(session, user, shop_id, payload)


@router.put(
    "/{shop_id}/products/{product_id}",
    response_model=ProductResponse,
)
def put_shop_product(
    shop_id: int,
    product_id: int,
    payload: ProductUpsertRequest,
    user: User = Depends(require_roles(UserRole.SHOP_OWNER)),
    session: Session = Depends(get_db),
) -> ProductResponse:
    return update_shop_product(session, user, shop_id, product_id, payload)


@router.patch(
    "/{shop_id}/products/{product_id}/availability",
    response_model=ProductResponse,
)
def patch_shop_product_availability(
    shop_id: int,
    product_id: int,
    payload: ProductAvailabilityRequest,
    user: User = Depends(require_roles(UserRole.SHOP_OWNER)),
    session: Session = Depends(get_db),
) -> ProductResponse:
    return set_shop_product_availability(
        session,
        user,
        shop_id,
        product_id,
        payload,
    )


@router.delete(
    "/{shop_id}/products/{product_id}",
    response_model=ProductResponse,
)
def delete_shop_product(
    shop_id: int,
    product_id: int,
    user: User = Depends(require_roles(UserRole.SHOP_OWNER)),
    session: Session = Depends(get_db),
) -> ProductResponse:
    return remove_shop_product(session, user, shop_id, product_id)


@router.get("/{shop_id}", response_model=ShopDetailResponse)
def get_shop(
    shop_id: int,
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    session: Session = Depends(get_db),
) -> ShopDetailResponse:
    return get_shop_detail(session, shop_id, lat, lng)


@router.get("/{shop_id}/menu", response_model=ShopMenuResponse)
def get_menu(
    shop_id: int,
    session: Session = Depends(get_db),
) -> ShopMenuResponse:
    return get_shop_menu(session, shop_id)


@router.get("/{shop_id}/rating/me", response_model=MyShopRatingResponse)
def get_my_rating(
    shop_id: int,
    user: User = Depends(require_roles(UserRole.CUSTOMER)),
    session: Session = Depends(get_db),
) -> MyShopRatingResponse:
    return get_my_shop_rating(session, user, shop_id)


@router.put("/{shop_id}/rating", response_model=ShopRatingResult)
def put_shop_rating(
    shop_id: int,
    payload: ShopRatingRequest,
    user: User = Depends(require_roles(UserRole.CUSTOMER)),
    session: Session = Depends(get_db),
) -> ShopRatingResult:
    return rate_shop(session, user, shop_id, payload)
