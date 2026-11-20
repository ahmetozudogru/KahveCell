import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { EmptyState, ErrorState, LoadingState } from '../components/AsyncStates'
import { ShopMap } from '../components/ShopMap'
import { ShopRating } from '../components/ShopRating'
import { apiRequest } from '../lib/api'
import type { Coordinates, Shop } from '../types/api'

const DEFAULT_LOCATION: Coordinates = {
  latitude: 39.9208,
  longitude: 32.8541,
}

export function HomePage() {
  const [shops, setShops] = useState<Shop[]>([])
  const [query, setQuery] = useState('')
  const [location, setLocation] = useState(DEFAULT_LOCATION)
  const [locationMessage, setLocationMessage] = useState('Konumunuz alınıyor…')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(true)
  const [retryVersion, setRetryVersion] = useState(0)

  useEffect(() => {
    let active = true

    async function loadShops(
      userLocation: Coordinates,
      message: string,
    ): Promise<void> {
      if (!active) {
        return
      }

      setLocation(userLocation)
      setLocationMessage(message)
      setError('')
      setBusy(true)

      const params = new URLSearchParams({
        lat: String(userLocation.latitude),
        lng: String(userLocation.longitude),
      })

      try {
        const result = await apiRequest<Shop[]>(`/shops?${params.toString()}`)
        if (active) {
          setShops(result)
        }
      } catch (requestError) {
        if (active) {
          const message =
            requestError instanceof Error
              ? requestError.message
              : 'Dükkânlar yüklenemedi.'
          setError(message)
        }
      } finally {
        if (active) {
          setBusy(false)
        }
      }
    }

    if (!navigator.geolocation) {
      void loadShops(
        DEFAULT_LOCATION,
        'Tarayıcı konum alamıyor; Ankara Kızılay varsayılan konum olarak kullanılıyor.',
      )
    } else {
      navigator.geolocation.getCurrentPosition(
        ({ coords }) => {
          void loadShops(
            {
              latitude: coords.latitude,
              longitude: coords.longitude,
            },
            'Dükkânlar konumunuza göre sıralandı.',
          )
        },
        () => {
          void loadShops(
            DEFAULT_LOCATION,
            'Konum izni alınamadı; Ankara Kızılay varsayılan konum olarak kullanılıyor.',
          )
        },
        { enableHighAccuracy: false, maximumAge: 60_000, timeout: 10_000 },
      )
    }

    return () => {
      active = false
    }
  }, [retryVersion])

  const visibleShops = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase('tr-TR')
    if (!normalizedQuery) {
      return shops
    }
    return shops.filter(
      (shop) =>
        shop.name.toLocaleLowerCase('tr-TR').includes(normalizedQuery) ||
        shop.address.toLocaleLowerCase('tr-TR').includes(normalizedQuery),
    )
  }, [query, shops])

  function retryShops() {
    setBusy(true)
    setError('')
    setLocationMessage('Konumunuz alınıyor…')
    setRetryVersion((version) => version + 1)
  }

  return (
    <div className="page-stack">
      <section className="page-heading discovery-heading">
        <div>
          <p className="eyebrow">KahveCell</p>
          <h1>Yakınındaki kahve dükkânları</h1>
          <p className="muted location-message">{locationMessage}</p>
        </div>
        <label className="search-field">
          <span>Dükkân ara</span>
          <input
            aria-label="Dükkân adı veya adresinde ara"
            autoComplete="off"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="İsim veya adres yaz"
            type="search"
            value={query}
          />
        </label>
      </section>

      {busy ? (
        <LoadingState message="Yakınındaki dükkânlar yükleniyor…" />
      ) : error ? (
        <ErrorState
          message={error}
          onRetry={retryShops}
        />
      ) : (
      <div className="discovery-layout">
        <section className="shop-list-panel" aria-label="Dükkân listesi">
          <div className="shop-list-heading">
            <h2>Dükkânlar</h2>
            <span className="muted">
              {`${visibleShops.length} dükkân`}
            </span>
          </div>

          {visibleShops.length === 0 && (
            <EmptyState
              action={
                query ? (
                  <button
                    className="secondary-button"
                    onClick={() => setQuery('')}
                    type="button"
                  >
                    Aramayı temizle
                  </button>
                ) : (
                  <button
                    className="secondary-button"
                    onClick={retryShops}
                    type="button"
                  >
                    Konumu yeniden dene
                  </button>
                )
              }
              description={
                query
                  ? 'Arama kelimeni değiştirebilir veya tüm dükkânları yeniden görebilirsin.'
                  : 'Yakınında henüz listelenen dükkân yok. Konumunu yenileyip tekrar bakabilirsin.'
              }
              title={
                query
                  ? 'Bu aramayla dükkân bulamadık'
                  : 'Yakınında dükkân bulunamadı'
              }
            />
          )}

          <div className="shop-list">
            {visibleShops.map((shop) => (
              <article className="shop-card" key={shop.id}>
                <h3>
                  <Link
                    state={{ userLocation: location }}
                    to={`/shops/${shop.id}`}
                  >
                    {shop.name}
                  </Link>
                </h3>
                <p className="shop-address">{shop.address}</p>
                <div className="shop-card-meta">
                  <ShopRating
                    rating={shop.rating}
                    ratingCount={shop.rating_count}
                  />
                  <span>
                    Mesafe:{' '}
                    {shop.distance_km === null
                      ? '—'
                      : `${shop.distance_km.toFixed(1)} km`}
                  </span>
                </div>
                <Link
                  className="button-link"
                  state={{ userLocation: location }}
                  to={`/shops/${shop.id}`}
                >
                  Menüyü Gör
                </Link>
              </article>
            ))}
          </div>
        </section>

        <section className="discovery-map" aria-label="Dükkân haritası">
          <ShopMap shops={visibleShops} userLocation={location} />
        </section>
      </div>
      )}
    </div>
  )
}
