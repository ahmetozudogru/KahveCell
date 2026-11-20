import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { useToast } from '../app/useToast'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncStates'
import { apiRequest } from '../lib/api'
import { ORDER_STATUS_LABELS } from '../lib/orderStatus'
import type { FavoriteOrderResponse, Order } from '../types/api'

export function HistoryPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(true)
  const [favoriteOrderIds, setFavoriteOrderIds] = useState<number[]>([])
  const [busyOrderId, setBusyOrderId] = useState<number | null>(null)
  const [retryVersion, setRetryVersion] = useState(0)
  const { notify } = useToast()

  const sortedOrders = [...orders].sort(
    (first, second) =>
      new Date(second.created_at).getTime() -
        new Date(first.created_at).getTime() ||
      second.id - first.id,
  )

  useEffect(() => {
    let active = true

    Promise.all([
      apiRequest<Order[]>('/orders/me'),
      apiRequest<Order[]>('/orders/me/favorites'),
    ])
      .then(([result, favorites]) => {
        if (active) {
          setOrders(result)
          setFavoriteOrderIds(favorites.map((order) => order.id))
        }
      })
      .catch((requestError: unknown) => {
        const message =
          requestError instanceof Error
            ? requestError.message
            : 'Sipariş geçmişi yüklenemedi.'
        if (active) {
          setError(message)
        }
      })
      .finally(() => {
        if (active) {
          setBusy(false)
        }
      })

    return () => {
      active = false
    }
  }, [retryVersion])

  function retryHistory() {
    setBusy(true)
    setError('')
    setRetryVersion((version) => version + 1)
  }

  async function toggleFavorite(order: Order) {
    const isFavorite = favoriteOrderIds.includes(order.id)
    setBusyOrderId(order.id)
    try {
      const result = await apiRequest<FavoriteOrderResponse>(
        `/orders/${order.id}/favorite`,
        { method: isFavorite ? 'DELETE' : 'PUT' },
      )
      setFavoriteOrderIds((current) =>
        result.is_favorite
          ? [...current, order.id]
          : current.filter((id) => id !== order.id),
      )
      notify(
        result.is_favorite
          ? 'Sipariş favorilere eklendi.'
          : 'Sipariş favorilerden çıkarıldı.',
        'success',
      )
    } catch (requestError) {
      notify(
        requestError instanceof Error
          ? requestError.message
          : 'Favori sipariş güncellenemedi.',
        'error',
      )
    } finally {
      setBusyOrderId(null)
    }
  }

  return (
    <section className="page-stack">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Hesabım</p>
          <h1>Sipariş geçmişim</h1>
        </div>
      </div>
      {busy ? (
        <LoadingState message="Sipariş geçmişin yükleniyor…" />
      ) : error ? (
        <ErrorState
          message={error}
          onRetry={retryHistory}
        />
      ) : orders.length === 0 ? (
        <EmptyState
          action={
            <Link className="button-link" to="/shops">
              Dükkânları keşfet
            </Link>
          }
          description="Ana sayfadan bir dükkân seçip ilk kahve siparişini verebilirsin."
          title="Henüz siparişin bulunmuyor"
        />
      ) : (
        <div className="order-list">
          {sortedOrders.map((order) => (
            <article className="panel order-card" key={order.id}>
              <div className="order-history-details">
                <h2>{order.product_name}</h2>
                <p className="order-shop-name">{order.shop_name}</p>
                <p className="muted">
                  {new Date(order.created_at).toLocaleString('tr-TR')}
                </p>
              </div>
              <span
                className={`status-badge status-${order.status.toLocaleLowerCase('en-US')}`}
              >
                {ORDER_STATUS_LABELS[order.status]}
              </span>
              <div className="history-order-actions">
                <button
                  className="secondary-button"
                  disabled={busyOrderId !== null}
                  onClick={() => void toggleFavorite(order)}
                  type="button"
                >
                  {busyOrderId === order.id
                    ? 'Güncelleniyor…'
                    : favoriteOrderIds.includes(order.id)
                      ? '★ Favorilerden çıkar'
                      : '☆ Favorilere ekle'}
                </button>
                <Link
                  className="text-link"
                  onClick={() =>
                    sessionStorage.setItem(
                      'kahvecell_latest_order',
                      JSON.stringify(order),
                    )
                  }
                  to="/qr"
                  state={order}
                >
                  QR kodunu gör
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
