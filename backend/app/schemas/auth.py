import re

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from app.core.roles import UserRole


class PhoneRequest(BaseModel):
    phone_number: str = Field(min_length=8, max_length=16)

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: str) -> str:
        normalized = re.sub(r"[\s()-]", "", value)
        if not re.fullmatch(r"\+?[1-9]\d{7,14}", normalized):
            raise ValueError("GSM numarasını ülke koduyla girin; ör. +905551234567.")
        return normalized


def _normalize_full_name(value: str) -> str:
    normalized = " ".join(value.split())
    if len(normalized) < 2:
        raise ValueError("Ad soyad en az iki karakter olmalıdır.")
    return normalized


class RegisterRequest(PhoneRequest):
    full_name: str = Field(min_length=2, max_length=100)
    password: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return _normalize_full_name(value)


class LoginRequest(BaseModel):
    phone_number: str | None = Field(default=None, min_length=8, max_length=16)
    username: str | None = Field(default=None, min_length=3, max_length=15)
    password: SecretStr

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return PhoneRequest.normalize_phone_number(value)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().casefold()
        if not re.fullmatch(r"[a-z][a-z0-9._-]{2,14}", normalized):
            raise ValueError(
                "Kullanıcı adı 3-15 karakter olmalı; harf, rakam, nokta, "
                "alt çizgi veya tire içerebilir."
            )
        return normalized

    @model_validator(mode="after")
    def validate_login_identifier_and_password(self) -> "LoginRequest":
        if (self.phone_number is None) == (self.username is None):
            raise ValueError("Telefon numarası veya kullanıcı adı girin.")
        password = self.password.get_secret_value()
        minimum_length = 5 if self.username is not None else 8
        if not minimum_length <= len(password) <= 128:
            raise ValueError(
                f"Şifre en az {minimum_length} karakter olmalıdır."
            )
        return self


class OTPVerifyRequest(PhoneRequest):
    otp: str = Field(pattern=r"^\d{4}$")


class OTPChallengeResponse(BaseModel):
    message: str
    phone_number: str
    demo_otp: str
    is_new_user: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    profile_completed: bool
    role: UserRole


class ProfileUpdateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    phone_number: str | None = Field(default=None, min_length=8, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    coffee_preferences: list[str] = Field(default_factory=list, max_length=20)
    allergens: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return _normalize_full_name(value)

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return PhoneRequest.normalize_phone_number(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip().lower()
            if value and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
                raise ValueError("Geçerli bir e-posta adresi girin.")
        return value or None


class PasswordChangeRequest(BaseModel):
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def reject_current_password_reuse(self) -> "PasswordChangeRequest":
        if (
            self.current_password.get_secret_value()
            == self.new_password.get_secret_value()
        ):
            raise ValueError("Yeni şifre mevcut şifrenizden farklı olmalıdır.")
        return self


class PasswordChangeResponse(BaseModel):
    message: str


class UserProfileResponse(BaseModel):
    id: int
    phone_number: str
    full_name: str
    email: str | None
    role: UserRole
    phone_verified: bool
    profile_completed: bool
    coffee_preferences: list[str]
    allergens: list[str]

    model_config = ConfigDict(from_attributes=True)


class AdminUserResponse(BaseModel):
    id: int
    username: str | None
    phone_number: str | None
    full_name: str
    email: str | None
    role: UserRole
    phone_verified: bool
    profile_completed: bool


class RoleUpdateRequest(BaseModel):
    role: UserRole
