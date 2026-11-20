import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { useToast } from '../app/useToast'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncStates'
import { ShopRating } from '../components/ShopRating'
import { ShopMenuEditor } from '../components/ShopMenuEditor'
import { apiRequest } from '../lib/api'
import type { Product, Shop, ShopDetail } from '../types/api'

export function ShopOwnerShopPage() {
  const [shops, setShops] = useState<ShopDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retryVersion, setRetryVersion] = useState(0)
  const [openingHoursDraft, setOpeningHoursDraft] = useState<
    Record<number, string>
  >({})
  const [savingHoursShopId, setSavingHoursShopId] = useState<number | null>(
    null,
  )
  const { notify } = useToast()

  useEffect(() => {
    let active = true
    apiRequest<ShopDetail[]>('/shops/me')
      .then((result) => {
        if (active) {
          setShops(result)
          setOpeningHoursDraft(
            Object.fromEntries(
              result.map((shop) => [shop.id, shop.opening_hours ?? '']),
            ),
          )
        }
      })
      .catch((requestError: unknown) => {
        if (active) {
          const message =
            requestError instanceof Error
              ? requestError.message
              : 'Restoran bilgileri yüklenemedi.'
          setError(message)
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [retryVersion])

  function retryShopInfo() {
    setLoading(true)
    setError('')
    setRetryVersion((version) => version + 1)
  }

  async function saveOpeningHours(
    event: FormEvent<HTMLFormElement>,
    shopId: number,
  ) {
    event.preventDefault()
    setSavingHoursShopId(shopId)
    const openingHours = openingHoursDraft[shopId]?.trim() || null
    try {
      const updatedShop = await apiRequest<Shop>(`/shops/${shopId}`, {
        method: 'PATCH',
        body: JSON.stringify({ opening_hours: openingHours }),
      })
      setShops((currentShops) =>
        currentShops.map((shop) =>
          shop.id === shopId
            ? { ...shop, opening_hours: updatedShop.opening_hours }
            : shop,
        ),
      )
      setOpeningHoursDraft((currentDraft) => ({
        ...currentDraft,
        [shopId]: updatedShop.opening_hours ?? '',
      }))
      notify('Çalışma saatleri güncellendi.', 'success')
    } catch (requestError) {
      notify(
        requestError instanceof Error
          ? requestError.message
          : 'Çalışma saatleri kaydedilemedi.',
        'error',
      )
    } finally {
      setSavingHoursShopId(null)
    }
  }

  return (
    <section className="page-stack">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Restoran yönetimi</p>
          <h1>Restoranım</h1>
          <p className="muted">
            Bu hesapla ilişkilendirilmiş restoran bilgileri ve menüsü.
          </p>
        </div>
        <div className="owner-shop-links">
          <Link className="button-link" to="/owner/orders">
            Siparişleri yönet
          </Link>
          <Link className="button-link secondary-button" to="/owner/orders/history">
            Sipariş geçmişi
          </Link>
        </div>
      </header>

      {loading ? (
        <LoadingState message="Restoran bilgileri ve menüsü yükleniyor…" />
      ) : error ? (
        <ErrorState
          message={error}
          onRetry={retryShopInfo}
        />
      ) : shops.length === 0 ? (
        <EmptyState
          description="Hesap eşleştirmesini tamamlaması için sistem yöneticinize ulaşın."
          title="Bu hesaba bağlı restoran bulunamadı"
        />
      ) : (
        <div className="owner-shop-list">
          {shops.map((shop) => (
            <article className="panel owner-shop-card" key={shop.id}>
              <div className="owner-shop-heading">
                <div>
                  <p className="eyebrow">Yönettiğiniz restoran</p>
                  <h2>{shop.name}</h2>
                  <p className="muted">{shop.address}</p>
                </div>
                <ShopRating
                  rating={shop.rating}
                  ratingCount={shop.rating_count}
                />
              </div>
              <form
                className="shop-hours-form"
                onSubmit={(event) => void saveOpeningHours(event, shop.id)}
              >
                <label>
                  Çalışma saatleri
                  <input
                    disabled={savingHoursShopId !== null}
                    maxLength={255}
                    onChange={(event) =>
                      setOpeningHoursDraft((currentDraft) => ({
                        ...currentDraft,
                        [shop.id]: event.target.value,
                      }))
                    }
                    placeholder="Örn. Her gün 09:00-21:00"
                    value={openingHoursDraft[shop.id] ?? ''}
                  />
                </label>
                <div className="shop-hours-actions">
                  <p className="field-note">
                    Saatleri kaldırmak için alanı boş bırakıp kaydedin.
                  </p>
                  <button
                    disabled={savingHoursShopId !== null}
                    type="submit"
                  >
                    {savingHoursShopId === shop.id
                      ? 'Kaydediliyor…'
                      : 'Saatleri kaydet'}
                  </button>
                </div>
              </form>
              <div className="shop-info-grid owner-shop-info">
                <div className="shop-info-item">
                  <strong>Çalışma saatleri</strong>
                  <span className="muted">
                    {shop.opening_hours ?? 'Belirtilmemiş'}
                  </span>
                </div>
                <div className="shop-info-item">
                  <strong>Aktif menü ürünü</strong>
                  <span className="muted">
                    {shop.products.filter((product) => product.is_available).length}{' '}
                    aktif / {shop.products.length} toplam
                  </span>
                </div>
                <div className="shop-info-item">
                  <strong>Restoran kodu</strong>
                  <span className="muted">#{shop.id}</span>
                </div>
              </div>
              <ShopMenuEditor
                onProductChange={(product: Product) =>
                  setShops((currentShops) =>
                    currentShops.map((currentShop) => {
                      if (currentShop.id !== shop.id) {
                        return currentShop
                      }
                      const hasProduct = currentShop.products.some(
                        (currentProduct) => currentProduct.id === product.id,
                      )
                      const products = hasProduct
                        ? currentShop.products.map((currentProduct) =>
                            currentProduct.id === product.id
                              ? product
                              : currentProduct,
                          )
                        : [...currentShop.products, product]
                      return {
                        ...currentShop,
                        products: products.sort((first, second) =>
                          first.name.localeCompare(second.name, 'tr'),
                        ),
                      }
                    }),
                  )
                }
                products={shop.products}
                shopId={shop.id}
              />
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
