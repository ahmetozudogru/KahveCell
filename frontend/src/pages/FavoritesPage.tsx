import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useToast } from '../app/useToast'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncStates'
import { apiRequest } from '../lib/api'
import { ORDER_STATUS_LABELS } from '../lib/orderStatus'
import type { FavoriteOrderResponse, Order } from '../types/api'

export function FavoritesPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [busyOrderId, setBusyOrderId] = useState<number | null>(null)
  const [retryVersion, setRetryVersion] = useState(0)
  const { notify } = useToast()
  const navigate = useNavigate()

  useEffect(() => {
    let active = true
    apiRequest<Order[]>('/orders/me/favorites')
      .then((result) => {
        if (active) {
          setOrders(result)
        }
      })
      .catch((requestError: unknown) => {
        if (active) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : 'Favori siparişlerin yüklenemedi.',
          )
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

  async function removeFavorite(orderId: number) {
    setBusyOrderId(orderId)
    try {
      await apiRequest<FavoriteOrderResponse>(`/orders/${orderId}/favorite`, {
        method: 'DELETE',
      })
      setOrders((current) => current.filter((order) => order.id !== orderId))
      notify('Sipariş favorilerinden çıkarıldı.', 'success')
    } catch (requestError) {
      notify(
        requestError instanceof Error
          ? requestError.message
          : 'Sipariş favorilerden çıkarılamadı.',
        'error',
      )
    } finally {
      setBusyOrderId(null)
    }
  }

  async function repeatOrder(orderId: number) {
    setBusyOrderId(orderId)
    try {
      const newOrder = await apiRequest<Order>(
        `/orders/me/favorites/${orderId}/repeat`,
        { method: 'POST' },
      )
      sessionStorage.setItem(
        'kahvecell_latest_order',
        JSON.stringify(newOrder),
      )
      navigate('/qr', { state: newOrder })
    } catch (requestError) {
      notify(
        requestError instanceof Error
          ? requestError.message
          : 'Sipariş yeniden oluşturulamadı.',
        'error',
      )
    } finally {
      setBusyOrderId(null)
    }
  }

  function retryFavorites() {
    setLoading(true)
    setError('')
    setRetryVersion((version) => version + 1)
  }

  return (
    <section className="page-stack">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Hesabım</p>
          <h1>Favori siparişlerim</h1>
          <p className="muted">
            Beğendiğin siparişleri kaydet ve dilediğinde yeniden sipariş ver.
          </p>
        </div>
      </header>
      {loading ? (
        <LoadingState message="Favori siparişlerin yükleniyor…" />
      ) : error ? (
        <ErrorState message={error} onRetry={retryFavorites} />
      ) : orders.length === 0 ? (
        <EmptyState
          action={
            <Link className="button-link" to="/history">
              Sipariş geçmişime git
            </Link>
          }
          description="Sipariş geçmişindeki bir siparişin yanındaki “Favorilere ekle” düğmesini kullanabilirsin."
          title="Henüz favori siparişin yok"
        />
      ) : (
        <div className="order-list">
          {orders.map((order) => (
            <article className="panel order-card favorite-order-card" key={order.id}>
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
              <div className="favorite-order-actions">
                <button
                  className="secondary-button"
                  disabled={busyOrderId !== null}
                  onClick={() => void removeFavorite(order.id)}
                  type="button"
                >
                  {busyOrderId === order.id
                    ? 'Güncelleniyor…'
                    : 'Favoriden çıkar'}
                </button>
                <button
                  disabled={busyOrderId !== null}
                  onClick={() => void repeatOrder(order.id)}
                  type="button"
                >
                  {busyOrderId === order.id
                    ? 'Hazırlanıyor…'
                    : 'Tekrar sipariş ver'}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
