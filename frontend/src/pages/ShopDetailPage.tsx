import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'

import { useAuth } from '../app/useAuth'
import { useToast } from '../app/useToast'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncStates'
import { ShopRating } from '../components/ShopRating'
import { apiRequest } from '../lib/api'
import type {
  Coordinates,
  MyShopRating,
  Product,
  ShopDetail,
  ShopRatingResult,
} from '../types/api'

const DEFAULT_LOCATION: Coordinates = {
  latitude: 39.9208,
  longitude: 32.8541,
}

const MENU_CATEGORIES = [
  'Espresso Bazlı',
  'Filtre Kahveler',
  'Soğuk İçecekler',
  'Diğer',
] as const

function getMenuCategory(product: Product): (typeof MENU_CATEGORIES)[number] {
  const searchText = `${product.category} ${product.name}`.toLocaleLowerCase(
    'tr-TR',
  )

  if (
    ['cold', 'iced', 'soğuk', 'frappe', 'limonata'].some((keyword) =>
      searchText.includes(keyword),
    )
  ) {
    return 'Soğuk İçecekler'
  }
  if (
    ['filter', 'filtre', 'drip'].some((keyword) =>
      searchText.includes(keyword),
    )
  ) {
    return 'Filtre Kahveler'
  }
  if (
    [
      'espresso',
      'americano',
      'cappuccino',
      'latte',
      'macchiato',
      'mocha',
      'flat white',
    ].some((keyword) => searchText.includes(keyword))
  ) {
    return 'Espresso Bazlı'
  }
  return 'Diğer'
}

function formatPrice(value: string | number): string {
  return new Intl.NumberFormat('tr-TR', {
    style: 'currency',
    currency: 'TRY',
  }).format(Number(value))
}

export function ShopDetailPage() {
  const { shopId } = useParams()
  const { role, token } = useAuth()
  const { notify } = useToast()
  const routeLocation = useLocation()
  const navigationState = routeLocation.state as {
    userLocation?: Coordinates
  } | null
  const userLocation = navigationState?.userLocation ?? DEFAULT_LOCATION
  const [loadedShop, setLoadedShop] = useState<{
    id: string
    shop: ShopDetail | null
    error: string
  } | null>(null)
  const [retryVersion, setRetryVersion] = useState(0)
  const [userRating, setUserRating] = useState<number | null>(null)
  const [selectedRating, setSelectedRating] = useState(0)
  const [ratingSaving, setRatingSaving] = useState(false)
  const [ratingRetryVersion, setRatingRetryVersion] = useState(0)
  const [ratingLoadState, setRatingLoadState] = useState<{
    key: string
    error: string
  } | null>(null)
  const ratingRequestKey =
    shopId && role === 'CUSTOMER' && token
      ? `${shopId}:${token}:${ratingRetryVersion}`
      : ''
  const currentRatingLoad =
    ratingLoadState?.key === ratingRequestKey ? ratingLoadState : null
  const ratingLoading = Boolean(ratingRequestKey && !currentRatingLoad)
  const ratingLoadError = currentRatingLoad?.error ?? ''

  useEffect(() => {
    let active = true

    if (!shopId) {
      return () => {
        active = false
      }
    }

    const params = new URLSearchParams({
      lat: String(userLocation.latitude),
      lng: String(userLocation.longitude),
    })

    apiRequest<ShopDetail>(`/shops/${shopId}?${params.toString()}`)
      .then((result) => {
        if (active) {
          setLoadedShop({ id: shopId, shop: result, error: '' })
        }
      })
      .catch((requestError: unknown) => {
        if (active) {
          const message =
            requestError instanceof Error
              ? requestError.message
              : 'Dükkân yüklenemedi.'
          setLoadedShop({
            id: shopId,
            shop: null,
            error: message,
          })
        }
      })

    return () => {
      active = false
    }
  }, [shopId, userLocation, retryVersion])

  useEffect(() => {
    if (!ratingRequestKey) {
      return
    }

    let active = true
    apiRequest<MyShopRating>(`/shops/${shopId}/rating/me`)
      .then((result) => {
        if (active) {
          setUserRating(result.rating)
          setSelectedRating(result.rating ?? 0)
          setRatingLoadState({ key: ratingRequestKey, error: '' })
        }
      })
      .catch((requestError: unknown) => {
        if (active) {
          setRatingLoadState({
            key: ratingRequestKey,
            error:
              requestError instanceof Error
                ? requestError.message
                : 'Puanınız yüklenemedi.',
          })
        }
      })

    return () => {
      active = false
    }
  }, [ratingRequestKey, shopId])

  async function submitRating(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!shopId || selectedRating < 1 || selectedRating > 5) {
      return
    }

    setRatingSaving(true)
    try {
      const result = await apiRequest<ShopRatingResult>(
        `/shops/${shopId}/rating`,
        {
          method: 'PUT',
          body: JSON.stringify({ rating: selectedRating }),
        },
      )
      setUserRating(result.user_rating)
      setLoadedShop((current) => {
        if (current?.id !== shopId || !current.shop) {
          return current
        }
        return {
          ...current,
          shop: {
            ...current.shop,
            rating: result.average_rating,
            rating_count: result.rating_count,
          },
        }
      })
      notify('Puanın kaydedildi.', 'success')
    } catch (requestError) {
      notify(
        requestError instanceof Error
          ? requestError.message
          : 'Puanın kaydedilemedi.',
        'error',
      )
    } finally {
      setRatingSaving(false)
    }
  }

  const currentShop = loadedShop?.id === shopId ? loadedShop : null

  if (!shopId) {
    return (
      <EmptyState
        action={
          <Link className="button-link" to="/shops">
            Dükkânları keşfet
          </Link>
        }
        description="Dükkân listesine dönerek başka bir yer seçebilirsin."
        title="Dükkân bulunamadı"
      />
    )
  }
  if (!currentShop) {
    return <LoadingState message="Dükkân ve menüsü yükleniyor…" />
  }
  if (currentShop.error) {
    return (
      <ErrorState
        message={currentShop.error}
        onRetry={() => {
          setLoadedShop(null)
          setRetryVersion((version) => version + 1)
        }}
      />
    )
  }
  const shop = currentShop.shop
  if (!shop) {
    return (
      <EmptyState
        action={
          <Link className="button-link" to="/shops">
            Dükkân listesine dön
          </Link>
        }
        description="Dükkân listesine dönüp başka bir dükkân seçebilirsin."
        title="Dükkân bilgisi bulunamadı"
      />
    )
  }

  const menuGroups = MENU_CATEGORIES.map((category) => ({
    category,
    products: shop.products.filter(
      (product) => getMenuCategory(product) === category,
    ),
  })).filter((group) => group.products.length > 0)

  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Dükkân detayı</p>
          <h1>{shop.name}</h1>
          <p className="muted">{shop.address}</p>
        </div>
        <Link className="text-link" to="/shops">
          Dükkân listesine dön
        </Link>
      </section>

      <section className="shop-info-grid" aria-label="Dükkân bilgileri">
        <article className="panel shop-info-item">
          <span className="muted">Çalışma saatleri</span>
          <strong>{shop.opening_hours || 'Belirtilmemiş'}</strong>
        </article>
        <article className="panel shop-info-item">
          <span className="muted">Puan</span>
          <ShopRating rating={shop.rating} ratingCount={shop.rating_count} />
        </article>
        <article className="panel shop-info-item">
          <span className="muted">Konumunuza uzaklık</span>
          <strong>
            {shop.distance_km === null
              ? 'Hesaplanamadı'
              : `${shop.distance_km.toFixed(1)} km`}
          </strong>
        </article>
      </section>

      <section className="panel shop-rating-panel" aria-label="Dükkânı puanla">
        <div>
          <p className="eyebrow">Deneyimini paylaş</p>
          <h2>Bu kahveciyi puanla</h2>
          <p className="muted">
            Her kullanıcı bu dükkân için bir puan verebilir; puanını sonradan
            güncelleyebilirsin.
          </p>
        </div>
        {role === 'CUSTOMER' ? (
          ratingLoading ? (
            <LoadingState message="Mevcut puanın kontrol ediliyor…" />
          ) : ratingLoadError ? (
            <ErrorState
              message={ratingLoadError}
              onRetry={() =>
                setRatingRetryVersion((version) => version + 1)
              }
            />
          ) : (
            <form className="shop-rating-form" onSubmit={submitRating}>
              <div
                aria-label="1 ile 5 yıldız arasında puan seç"
                className="rating-star-picker"
                role="group"
              >
                {[1, 2, 3, 4, 5].map((rating) => (
                  <button
                    aria-label={`${rating} yıldız`}
                    aria-pressed={selectedRating === rating}
                    className={
                      rating <= selectedRating
                        ? 'rating-star selected'
                        : 'rating-star'
                    }
                    key={rating}
                    onClick={() => setSelectedRating(rating)}
                    type="button"
                  >
                    ★
                  </button>
                ))}
              </div>
              <p className="muted">
                {userRating === null
                  ? 'Henüz puan vermedin.'
                  : `Mevcut puanın: ${userRating} / 5`}
              </p>
              <button
                disabled={ratingSaving || selectedRating === 0}
                type="submit"
              >
                {ratingSaving
                  ? 'Kaydediliyor…'
                  : userRating === null
                    ? 'Puanı gönder'
                    : 'Puanımı güncelle'}
              </button>
            </form>
          )
        ) : token ? (
          <p className="muted">
            Puan vermek için müşteri hesabı kullanmalısın.
          </p>
        ) : (
          <Link className="button-link" to="/login">
            Giriş yap ve puan ver
          </Link>
        )}
      </section>

      <section className="page-stack" aria-label="Dükkân menüsü">
        <div>
          <p className="eyebrow">Menü</p>
          <h2>İçecekler</h2>
        </div>
        {menuGroups.length === 0 ? (
            <EmptyState
              action={
                <Link className="button-link" to="/shops">
                  Dükkânları keşfet
                </Link>
              }
              description="Başka bir dükkânın menüsüne göz atabilir, daha sonra buraya tekrar dönebilirsin."
              title="Bu dükkânın menüsü henüz eklenmemiş"
            />
        ) : (
          <>
            <p className="menu-pricing-explainer">
              Gösterilen temel fiyat M boy, normal süt ve ekstra shotsız
              seçeneğe aittir. Seçimlerinize göre toplam değişebilir.
            </p>
            {menuGroups.map((group) => (
              <section
                className="panel menu-category"
                aria-label={group.category}
                key={group.category}
              >
                <h3>{group.category}</h3>
                <div className="product-list">
                  {group.products.map((product) => (
                    <article className="product-row" key={product.id}>
                      <div>
                        <h3>{product.name}</h3>
                        <p className="muted">
                          {product.description ?? product.category}
                        </p>
                        <p className="product-base-price">
                          Temel fiyat: {formatPrice(product.price)}
                        </p>
                      </div>
                      {product.is_available ? (
                        <Link
                          className="button-link"
                          to={`/orders/new?shopId=${shop.id}&productId=${product.id}`}
                        >
                          Sipariş Ver
                        </Link>
                      ) : (
                        <span className="muted">Şu an mevcut değil</span>
                      )}
                    </article>
                  ))}
                </div>
              </section>
            ))}
          </>
        )}
      </section>
    </div>
  )
}
