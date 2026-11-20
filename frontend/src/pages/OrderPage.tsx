import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { EmptyState, ErrorState, LoadingState } from '../components/AsyncStates'
import { ApiError, apiRequest } from '../lib/api'
import { getProductPriceBreakdown } from '../lib/pricing'
import type {
  CoffeeSize,
  MilkType,
  Order,
  OrderCustomizations,
  Product,
  ShopDetail,
  Subscription,
} from '../types/api'

const DEFAULT_CUSTOMIZATIONS: OrderCustomizations = {
  size: 'M',
  sugar_level: 0,
  milk_type: 'WHOLE',
  extra_shots: 0,
}

interface OrderPageData {
  requestKey: string
  shop: ShopDetail | null
  shopError: string
  subscription: Subscription | null
  subscriptionError: string
}

export function OrderPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const shopId = searchParams.get('shopId')
  const initialProductId = searchParams.get('productId') ?? ''
  const requestKey = `${shopId ?? ''}:${initialProductId}`
  const [data, setData] = useState<OrderPageData | null>(null)
  const [customizations, setCustomizations] =
    useState<OrderCustomizations>(DEFAULT_CUSTOMIZATIONS)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [retryVersion, setRetryVersion] = useState(0)

  useEffect(() => {
    let active = true
    if (!shopId) {
      return () => {
        active = false
      }
    }

    void Promise.allSettled([
      apiRequest<ShopDetail>(`/shops/${shopId}`),
      apiRequest<Subscription>('/subscriptions/me'),
    ]).then(([shopResult, subscriptionResult]) => {
      if (!active) {
        return
      }

      let shop: ShopDetail | null = null
      let shopError = ''
      if (shopResult.status === 'fulfilled') {
        shop = shopResult.value
      } else {
        shopError =
          shopResult.reason instanceof Error
            ? shopResult.reason.message
            : 'Dükkân yüklenemedi.'
      }

      let subscription: Subscription | null = null
      let subscriptionError = ''
      if (subscriptionResult.status === 'fulfilled') {
        subscription = subscriptionResult.value
      } else if (
        !(
          subscriptionResult.reason instanceof ApiError &&
          subscriptionResult.reason.status === 404
        )
      ) {
        subscriptionError =
          subscriptionResult.reason instanceof Error
            ? subscriptionResult.reason.message
            : 'Abonelik bilgisi yüklenemedi.'
      }

      setData({
        requestKey,
        shop,
        shopError,
        subscription,
        subscriptionError,
      })
    })

    return () => {
      active = false
    }
  }, [requestKey, retryVersion, shopId])

  const currentData = data?.requestKey === requestKey ? data : null
  const shop = currentData?.shop ?? null
  const subscription = currentData?.subscription ?? null
  const selectedProduct: Product | undefined =
    shop?.products.find(
      (product) => String(product.id) === initialProductId,
    ) ?? shop?.products.find((product) => product.is_available)
  const priceBreakdown = selectedProduct
    ? getProductPriceBreakdown(selectedProduct, customizations)
    : null
  const subscriptionLoading = Boolean(shopId) && !currentData
  const hasCredits =
    subscription !== null &&
    (subscription.remaining_credits === null ||
      subscription.remaining_credits > 0)
  const canOrder =
    !subscriptionLoading &&
    !currentData?.shopError &&
    !currentData?.subscriptionError &&
    Boolean(selectedProduct?.is_available) &&
    hasCredits

  function formatCurrency(value: number | string): string {
    return new Intl.NumberFormat('tr-TR', {
      style: 'currency',
      currency: 'TRY',
    }).format(Number(value))
  }

  function formatPriceDelta(value: number | string): string {
    const amount = Number(value)
    if (amount === 0) {
      return 'fiyata dahil'
    }
    return amount > 0
      ? `+${formatCurrency(amount)}`
      : `−${formatCurrency(Math.abs(amount))}`
  }

  async function submitOrder(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault()
    if (!shopId || !selectedProduct || !canOrder) {
      return
    }
    setSubmitting(true)
    setSubmitError('')
    try {
      const order = await apiRequest<Order>('/orders', {
        method: 'POST',
        body: JSON.stringify({
          shop_id: Number(shopId),
          product_id: selectedProduct.id,
          customizations,
        }),
      })
      sessionStorage.setItem('kahvecell_latest_order', JSON.stringify(order))
      navigate('/qr', { state: order })
    } catch (requestError) {
      setSubmitError(
        requestError instanceof Error
          ? requestError.message
          : 'Sipariş oluşturulamadı.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  if (!shopId) {
    return (
      <EmptyState
        action={
          <Link className="button-link" to="/shops">
            Dükkânları keşfet
          </Link>
        }
        description="Sipariş vermek için ana sayfadan bir dükkân ve ürün seç."
        title="Önce bir dükkân seçmelisin"
      />
    )
  }

  if (!currentData) {
    return <LoadingState message="Dükkân ve abonelik bilgileri yükleniyor…" />
  }

  if (currentData.shopError || !shop) {
    return currentData.shopError ? (
      <ErrorState
        message={currentData.shopError}
        onRetry={() => {
          setData(null)
          setRetryVersion((version) => version + 1)
        }}
      />
    ) : (
      <EmptyState
        action={
          <Link className="button-link" to="/shops">
            Dükkânları keşfet
          </Link>
        }
        description="Dükkân listesine dönüp başka bir yer seçebilirsin."
        title="Dükkân bilgisi bulunamadı"
      />
    )
  }

  if (currentData.subscriptionError) {
    return (
      <div className="page-stack">
        <ErrorState
          message={currentData.subscriptionError}
          onRetry={() => {
            setData(null)
            setRetryVersion((version) => version + 1)
          }}
        />
        <Link className="text-link" to="/subscription">
          Abonelik sayfasına git
        </Link>
      </div>
    )
  }

  if (!selectedProduct || !selectedProduct.is_available) {
    return (
      <EmptyState
        action={<Link className="button-link" to={`/shops/${shop.id}`}>Menüye dön</Link>}
        description="Menüden siparişe açık başka bir içecek seçebilirsin."
        title={
          selectedProduct
            ? 'Bu ürün şu an siparişe açık değil'
            : 'Seçilen ürün bulunamadı'
        }
      />
    )
  }

  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Yeni sipariş</p>
          <h1>{shop.name}</h1>
          <p className="muted">{shop.address}</p>
        </div>
        <Link className="text-link" to={`/shops/${shop.id}`}>
          Menüye dön
        </Link>
      </section>

      <section className="panel order-product-summary">
        <div>
          <p className="eyebrow">Seçilen ürün</p>
          <h2>{selectedProduct?.name ?? 'Ürün bulunamadı'}</h2>
          <p className="muted">
            Temel fiyat {formatCurrency(priceBreakdown?.basePrice ?? 0)} · Boy{' '}
            {formatPriceDelta(priceBreakdown?.sizeDelta ?? 0)} · Süt{' '}
            {formatPriceDelta(priceBreakdown?.milkDelta ?? 0)} · Ek shot{' '}
            {formatCurrency(priceBreakdown?.extraShotsTotal ?? 0)}
          </p>
        </div>
        {priceBreakdown && (
          <strong className="order-total-price">
            {formatCurrency(priceBreakdown.total)}
          </strong>
        )}
      </section>

      {subscription === null ? (
        <div className="notice subscription-warning">
          <p>Sipariş vermek için aktif bir aboneliğin olmalı.</p>
          <Link className="text-link" to="/subscription">
            Abonelik sayfasına git
          </Link>
        </div>
      ) : subscription.remaining_credits === 0 ? (
        <div className="notice subscription-warning">
          <p>Kahve hakkın kalmadı. Sipariş vermek için paketini yenile.</p>
          <Link className="text-link" to="/subscription">
            Abonelik sayfasına git
          </Link>
        </div>
      ) : (
        <div className="notice credit-notice">
          <p>
            Kalan kahve kredin:{' '}
            <strong>
              {subscription.remaining_credits === null
                ? 'Sınırsız'
                : subscription.remaining_credits}
            </strong>
          </p>
          <strong>
            {subscription.remaining_credits === null
              ? 'Bu sipariş sonrası sınırsız kahve hakkın devam edecek.'
              : `Bu sipariş sonrası ${subscription.remaining_credits - 1} kredi kalacak.`}
          </strong>
        </div>
      )}

      {submitError && (
        <ErrorState
          message={submitError}
          onRetry={() => void submitOrder()}
          title="Sipariş oluşturulamadı"
        />
      )}

      <form className="panel stack order-form" onSubmit={submitOrder}>
        <h2>İçeceğini özelleştir</h2>
        <div className="customization-grid">
          <label>
            Boyut
            <select
              disabled={!canOrder || submitting}
              onChange={(event) =>
                setCustomizations((current) => ({
                  ...current,
                  size: event.target.value as OrderCustomizations['size'],
                }))
              }
              value={customizations.size}
            >
              {(['S', 'M', 'L'] as CoffeeSize[]).map((size) => (
                <option key={size} value={size}>
                  {size} ({formatPriceDelta(selectedProduct.size_price_deltas[size])})
                </option>
              ))}
            </select>
          </label>
          <label>
            Süt tipi
            <select
              disabled={!canOrder || submitting}
              onChange={(event) =>
                setCustomizations((current) => ({
                  ...current,
                  milk_type:
                    event.target.value as OrderCustomizations['milk_type'],
                }))
              }
              value={customizations.milk_type}
            >
              {(
                [
                  ['WHOLE', 'Normal süt'],
                  ['NONE', 'Sütsüz'],
                  ['OAT', 'Yulaf sütü'],
                  ['ALMOND', 'Badem sütü'],
                  ['LACTOSE_FREE', 'Laktozsuz süt'],
                ] as Array<[MilkType, string]>
              ).map(([milkType, label]) => (
                <option key={milkType} value={milkType}>
                  {label} (
                  {formatPriceDelta(
                    selectedProduct.milk_price_deltas[milkType],
                  )}
                  )
                </option>
              ))}
            </select>
          </label>
          <label>
            Şeker miktarı (0–5)
            <input
              disabled={!canOrder || submitting}
              max={5}
              min={0}
              onChange={(event) =>
                setCustomizations((current) => ({
                  ...current,
                  sugar_level: Number(event.target.value),
                }))
              }
              type="number"
              value={customizations.sugar_level}
            />
          </label>
          <label>
            Ek shot (0–3) ·{' '}
            {formatCurrency(selectedProduct.extra_shot_price)} / adet
            <input
              disabled={!canOrder || submitting}
              max={3}
              min={0}
              onChange={(event) =>
                setCustomizations((current) => ({
                  ...current,
                  extra_shots: Number(event.target.value),
                }))
              }
              type="number"
              value={customizations.extra_shots}
            />
          </label>
        </div>
        <button disabled={submitting || !canOrder} type="submit">
          {submitting
            ? 'Sipariş veriliyor…'
            : !hasCredits
              ? subscription
                ? 'Kahve hakkın tükendi'
                : 'Aktif abonelik gerekli'
              : !selectedProduct?.is_available
                ? 'Ürün siparişe açık değil'
                : 'Siparişi Onayla'}
        </button>
      </form>
    </div>
  )
}
