import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt

BACKEND_DIR = Path(__file__).resolve().parents[2]
JWT_SECRET_PATH = BACKEND_DIR / ".jwt_secret"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_LIFETIME = timedelta(days=30)
ACCESS_TOKEN_EXPIRES_IN = int(ACCESS_TOKEN_LIFETIME.total_seconds())
PASSWORD_HASH_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    return (
        f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}"
        f"${salt.hex()}${digest.hex()}"
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        expected_digest = bytes.fromhex(digest_hex)
        actual_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
    except ValueError:
        return False
    return hmac.compare_digest(actual_digest, expected_digest)


def _load_or_create_jwt_secret() -> str:
    configured_secret = os.getenv("KAHVECELL_JWT_SECRET")
    if configured_secret:
        if len(configured_secret) < 32:
            raise RuntimeError("KAHVECELL_JWT_SECRET must be at least 32 characters.")
        return configured_secret

    try:
        with JWT_SECRET_PATH.open("x", encoding="utf-8") as secret_file:
            secret = secrets.token_urlsafe(48)
            secret_file.write(secret)
            return secret
    except FileExistsError:
        secret = JWT_SECRET_PATH.read_text(encoding="utf-8").strip()
        if len(secret) < 32:
            raise RuntimeError(f"JWT secret file is invalid: {JWT_SECRET_PATH}")
        return secret


JWT_SECRET = _load_or_create_jwt_secret()


def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + ACCESS_TOKEN_LIFETIME,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
