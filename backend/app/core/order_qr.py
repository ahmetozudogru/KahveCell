import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import UUID, uuid5

from app.core.security import JWT_SECRET
from app.schemas.orders import QRCodeClaims, QRCodePayload

_QR_SIGNING_KEY = hmac.new(
    JWT_SECRET.encode("utf-8"),
    b"kahvecell-order-qr-signature-key-v1",
    hashlib.sha256,
).digest()
_PUBLIC_ID_NAMESPACE = UUID(
    bytes=hmac.new(
        JWT_SECRET.encode("utf-8"),
        b"kahvecell-order-qr-public-id-namespace-v1",
        hashlib.sha256,
    ).digest()[:16],
    version=5,
)


def _public_id(entity: str, internal_id: int) -> UUID:
    return uuid5(_PUBLIC_ID_NAMESPACE, f"{entity}:{internal_id}")


def _canonical_claims(claims: QRCodeClaims) -> bytes:
    document = {
        "order_id": str(claims.order_id),
        "user_id": str(claims.user_id),
        "shop_id": str(claims.shop_id),
        "created_at": claims.created_at.astimezone(timezone.utc).isoformat(),
    }
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def create_qr_payload(
    order_token: str,
    user_id: int,
    shop_id: int,
    created_at: datetime,
) -> QRCodePayload:
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    claims = QRCodeClaims(
        order_id=UUID(order_token),
        user_id=_public_id("user", user_id),
        shop_id=_public_id("shop", shop_id),
        created_at=created_at,
    )
    signature = hmac.new(
        _QR_SIGNING_KEY,
        _canonical_claims(claims),
        hashlib.sha256,
    ).hexdigest()
    return QRCodePayload(**claims.model_dump(), signature=signature)


def verify_qr_signature(payload: QRCodePayload) -> bool:
    expected_signature = hmac.new(
        _QR_SIGNING_KEY,
        _canonical_claims(payload),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(payload.signature, expected_signature)
