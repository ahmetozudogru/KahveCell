import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user, get_db
from app.core.roles import UserRole
from app.core.security import (
    ACCESS_TOKEN_EXPIRES_IN,
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    OTPChallengeResponse,
    OTPVerifyRequest,
    LoginRequest,
    PasswordChangeRequest,
    PasswordChangeResponse,
    PhoneRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    TokenResponse,
    UserProfileResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
SIMULATED_OTP = "1234"


def _otp_challenge(phone_number: str, is_new_user: bool) -> OTPChallengeResponse:
    return OTPChallengeResponse(
        message="SMS simülasyonu: doğrulama kodu 1234.",
        phone_number=phone_number,
        demo_otp=SIMULATED_OTP,
        is_new_user=is_new_user,
    )


def _profile_response(user: User) -> UserProfileResponse:
    preferences = json.loads(user.preferences) if user.preferences else {}
    return UserProfileResponse(
        id=user.id,
        phone_number=user.phone_number,
        full_name=user.full_name,
        email=user.email,
        role=UserRole(user.role),
        phone_verified=user.phone_verified_at is not None,
        profile_completed=user.profile_completed,
        coffee_preferences=preferences.get("coffee_preferences", []),
        allergens=preferences.get("allergens", []),
    )


@router.post(
    "/register",
    response_model=OTPChallengeResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    session: Session = Depends(get_db),
) -> OTPChallengeResponse:
    if session.scalar(
        select(User.id).where(User.phone_number == payload.phone_number)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu numara zaten kayıtlı. Giriş için OTP isteyin.",
        )

    user = User(
        phone_number=payload.phone_number,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password.get_secret_value()),
        role=UserRole.CUSTOMER.value,
        profile_completed=True,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu numara zaten kayıtlı. Giriş için OTP isteyin.",
        ) from None
    return _otp_challenge(user.phone_number, is_new_user=True)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    session: Session = Depends(get_db),
) -> TokenResponse:
    if payload.username is not None:
        user = session.scalar(
            select(User).where(User.username == payload.username)
        )
        invalid_credentials_message = "Kullanıcı adı veya şifre geçersiz."
    else:
        user = session.scalar(
            select(User).where(User.phone_number == payload.phone_number)
        )
        invalid_credentials_message = "GSM numarası veya şifre geçersiz."
    if (
        user is None
        or user.password_hash is None
        or not verify_password(
            payload.password.get_secret_value(),
            user.password_hash,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=invalid_credentials_message,
        )
    if user.phone_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Giriş yapmadan önce telefonunuzu OTP ile doğrulayın.",
        )
    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        expires_in=ACCESS_TOKEN_EXPIRES_IN,
        profile_completed=user.profile_completed,
        role=UserRole(user.role),
    )


@router.post("/request-otp", response_model=OTPChallengeResponse)
def request_otp(
    payload: PhoneRequest,
    session: Session = Depends(get_db),
) -> OTPChallengeResponse:
    user = session.scalar(
        select(User).where(User.phone_number == payload.phone_number)
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu numarayla kayıt bulunamadı. Önce kayıt olun.",
        )
    return _otp_challenge(user.phone_number, is_new_user=False)


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp(
    payload: OTPVerifyRequest,
    session: Session = Depends(get_db),
) -> TokenResponse:
    user = session.scalar(
        select(User).where(User.phone_number == payload.phone_number)
    )
    if user is None or payload.otp != SIMULATED_OTP:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GSM numarası veya OTP kodu geçersiz.",
        )

    user.phone_verified_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.commit()
    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        expires_in=ACCESS_TOKEN_EXPIRES_IN,
        profile_completed=user.profile_completed,
        role=UserRole(user.role),
    )


@router.get("/me", response_model=UserProfileResponse)
def get_profile(
    user: User = Depends(get_current_user),
) -> UserProfileResponse:
    return _profile_response(user)


@router.patch("/me/password", response_model=PasswordChangeResponse)
def change_password(
    payload: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> PasswordChangeResponse:
    if user.password_hash is None or not verify_password(
        payload.current_password.get_secret_value(),
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mevcut şifre yanlış.",
        )

    user.password_hash = hash_password(
        payload.new_password.get_secret_value()
    )
    session.commit()
    return PasswordChangeResponse(message="Şifreniz güncellendi.")


@router.patch("/me/profile", response_model=UserProfileResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> UserProfileResponse:
    if payload.phone_number and payload.phone_number != user.phone_number:
        existing_phone = session.scalar(
            select(User.id).where(
                User.phone_number == payload.phone_number,
                User.id != user.id,
            )
        )
        if existing_phone is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bu telefon numarası başka bir kullanıcı tarafından kullanılıyor.",
            )

    if payload.email:
        existing_email = session.scalar(
            select(User.id).where(
                User.email == payload.email,
                User.id != user.id,
            )
        )
        if existing_email is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bu e-posta adresi başka bir kullanıcı tarafından kullanılıyor.",
            )

    user.full_name = payload.full_name
    if payload.phone_number and payload.phone_number != user.phone_number:
        user.phone_number = payload.phone_number
        user.phone_verified_at = None
    user.email = payload.email
    user.preferences = json.dumps(
        {
            "coffee_preferences": payload.coffee_preferences,
            "allergens": payload.allergens,
        },
        ensure_ascii=False,
    )
    user.profile_completed = True
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profil bilgileri başka bir kullanıcıyla çakışıyor.",
        ) from None
    session.refresh(user)
    return _profile_response(user)
