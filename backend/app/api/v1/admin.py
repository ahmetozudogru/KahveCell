from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.v1.dependencies import get_db, require_roles
from app.core.roles import UserRole
from app.models.shop import Shop
from app.models.user import User
from app.schemas.auth import AdminUserResponse, RoleUpdateRequest
from app.schemas.admin import (
    AdminShopResponse,
    AdminShopUpsertRequest,
    GeocodeRequest,
    GeocodeResponse,
)
from app.services.geocoding import geocode_address

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)


def _admin_user_response(user: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        username=user.username,
        phone_number=None if user.username else user.phone_number,
        full_name=user.full_name,
        email=user.email,
        role=UserRole(user.role),
        phone_verified=user.phone_verified_at is not None,
        profile_completed=user.profile_completed,
    )


def _admin_shop_response(shop: Shop) -> AdminShopResponse:
    return AdminShopResponse(
        id=shop.id,
        name=shop.name,
        address=shop.address,
        latitude=shop.latitude,
        longitude=shop.longitude,
        opening_hours=shop.opening_hours,
        rating=shop.rating,
        rating_count=len(shop.ratings),
        owner_id=shop.owner_id,
        owner_name=shop.owner.full_name if shop.owner else None,
    )


def _get_shop_owner(session: Session, owner_id: int | None) -> User | None:
    if owner_id is None:
        return None
    owner = session.get(User, owner_id)
    if owner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atanacak kullanıcı bulunamadı.",
        )
    if owner.role != UserRole.SHOP_OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dükkân sahibi olarak atanacak kullanıcının rolü SHOP_OWNER olmalıdır.",
        )
    return owner


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(session: Session = Depends(get_db)) -> list[AdminUserResponse]:
    users = session.scalars(select(User).order_by(User.id)).all()
    return [_admin_user_response(user) for user in users]


@router.patch("/users/{user_id}/role", response_model=AdminUserResponse)
def update_user_role(
    user_id: int,
    payload: RoleUpdateRequest,
    session: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> AdminUserResponse:
    if user_id == admin.id and payload.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kendi yönetici rolünüzü değiştiremezsiniz.",
        )
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı.",
        )
    user.role = payload.role.value
    session.commit()
    session.refresh(user)
    return _admin_user_response(user)


@router.get("/shops", response_model=list[AdminShopResponse])
def list_admin_shops(session: Session = Depends(get_db)) -> list[AdminShopResponse]:
    shops = session.scalars(
        select(Shop)
        .options(joinedload(Shop.owner), selectinload(Shop.ratings))
        .order_by(Shop.name, Shop.id)
    ).all()
    return [_admin_shop_response(shop) for shop in shops]


@router.post("/geocode", response_model=GeocodeResponse)
def post_geocode_address(payload: GeocodeRequest) -> GeocodeResponse:
    return geocode_address(payload.address)


@router.post(
    "/shops",
    response_model=AdminShopResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_shop(
    payload: AdminShopUpsertRequest,
    session: Session = Depends(get_db),
) -> AdminShopResponse:
    owner = _get_shop_owner(session, payload.owner_id)
    shop = Shop(
        name=payload.name,
        address=payload.address,
        latitude=payload.latitude,
        longitude=payload.longitude,
        opening_hours=payload.opening_hours,
        owner=owner,
    )
    session.add(shop)
    session.commit()
    session.refresh(shop)
    return _admin_shop_response(shop)


@router.put("/shops/{shop_id}", response_model=AdminShopResponse)
def update_admin_shop(
    shop_id: int,
    payload: AdminShopUpsertRequest,
    session: Session = Depends(get_db),
) -> AdminShopResponse:
    shop = session.scalar(
        select(Shop)
        .options(joinedload(Shop.owner))
        .where(Shop.id == shop_id)
    )
    if shop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dükkân bulunamadı.",
        )
    shop.name = payload.name
    shop.address = payload.address
    shop.latitude = payload.latitude
    shop.longitude = payload.longitude
    shop.opening_hours = payload.opening_hours
    shop.owner = _get_shop_owner(session, payload.owner_id)
    session.commit()
    session.refresh(shop)
    return _admin_shop_response(shop)
