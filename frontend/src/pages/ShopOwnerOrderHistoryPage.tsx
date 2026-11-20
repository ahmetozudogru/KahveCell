import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { EmptyState, ErrorState, LoadingState } from '../components/AsyncStates'
import { ORDER_STATUS_LABELS } from '../lib/orderStatus'
import { apiRequest } from '../lib/api'
import type { Order } from '../types/api'

function formatOrderTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Saat bilgisi yok'
    : date.toLocaleString('tr-TR')
}

export function ShopOwnerOrderHistoryPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retryVersion, setRetryVersion] = useState(0)

  useEffect(() => {
    let active = true
    apiRequest<Order[]>('/orders/shop/history')
      .then((result) => {
        if (active) {
          setOrders(result)
        }
      })
      .catch((requestError: unknown) => {
        if (active) {
          const message =
            requestError instanceof Error
              ? requestError.message
              : 'Sipariş geçmişi yüklenemedi.'
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

  function retryOrderHistory() {
    setLoading(true)
    setError('')
    setRetryVersion((version) => version + 1)
  }

  return (
    <section className="page-stack">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Restoran yönetimi</p>
          <h1>Sipariş geçmişi</h1>
          <p className="muted">Teslim edilmiş siparişler en yeniden eskiye sıralanır.</p>
        </div>
        <Link className="button-link secondary-button" to="/owner/orders">
          Aktif siparişlere dön
        </Link>
      </header>

      {loading ? (
        <LoadingState message="Teslim edilmiş siparişler yükleniyor…" />
      ) : error ? (
        <ErrorState
          message={error}
          onRetry={retryOrderHistory}
        />
      ) : orders.length === 0 ? (
        <EmptyState
          action={
            <Link className="button-link" to="/owner/orders">
              Aktif siparişleri görüntüle
            </Link>
          }
          description="Siparişler teslim edildikten sonra geçmiş listesine eklenir."
          title="Henüz teslim edilmiş siparişiniz yok"
        />
      ) : (
        <div className="order-list">
          {orders.map((order) => (
            <article className="panel owner-order-card" key={order.id}>
              <div className="owner-order-heading">
                <div>
                  <p className="eyebrow">
                    Sipariş #{order.id} · {order.shop_name}
                  </p>
                  <h2>{order.product_name}</h2>
                </div>
                <span className="status-badge status-delivered">
                  {ORDER_STATUS_LABELS[order.status]}
                </span>
              </div>
              <div className="owner-order-details">
                <p>
                  <strong>Müşteri:</strong> {order.customer_name} ·{' '}
                  <a href={`tel:${order.customer_phone}`}>
                    {order.customer_phone}
                  </a>
                </p>
                <p>
                  <strong>Sipariş zamanı:</strong>{' '}
                  {formatOrderTime(order.created_at)}
                </p>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
