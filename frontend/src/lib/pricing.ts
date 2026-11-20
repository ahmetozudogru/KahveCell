import type { OrderCustomizations, Product } from '../types/api'

export interface ProductPriceBreakdown {
  basePrice: number
  sizeDelta: number
  milkDelta: number
  extraShotsTotal: number
  total: number
}

export function getProductPriceBreakdown(
  product: Product,
  customizations: OrderCustomizations,
): ProductPriceBreakdown {
  const basePrice = Number(product.price)
  const sizeDelta = Number(product.size_price_deltas[customizations.size])
  const milkDelta = Number(product.milk_price_deltas[customizations.milk_type])
  const extraShotsTotal =
    Number(product.extra_shot_price) * customizations.extra_shots
  const total =
    Math.round(
      (basePrice + sizeDelta + milkDelta + extraShotsTotal + Number.EPSILON) *
        100,
    ) / 100

  return {
    basePrice,
    sizeDelta,
    milkDelta,
    extraShotsTotal,
    total,
  }
}
