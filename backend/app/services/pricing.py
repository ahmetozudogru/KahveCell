from decimal import Decimal

from fastapi import HTTPException, status

from app.models.product import Product
from app.schemas.orders import OrderCustomizations


def calculate_product_price(
    product: Product,
    customizations: OrderCustomizations,
) -> Decimal:
    size_delta = Decimal(
        str(product.size_price_deltas.get(customizations.size.value, "0.00"))
    )
    milk_delta = Decimal(
        str(product.milk_price_deltas.get(customizations.milk_type.value, "0.00"))
    )
    extra_shot_total = (
        Decimal(product.extra_shot_price) * customizations.extra_shots
    )
    total = (
        Decimal(product.price) + size_delta + milk_delta + extra_shot_total
    ).quantize(Decimal("0.01"))

    if total <= 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seçilen özelleştirmeler için ürün fiyatı geçersiz.",
        )
    return total
