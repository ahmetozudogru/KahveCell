import { useEffect, useRef, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { Link, useLocation } from 'react-router-dom'

import { EmptyState, ErrorState } from '../components/AsyncStates'
import { apiEventStream } from '../lib/api'
import { ORDER_STATUS_LABELS } from '../lib/orderStatus'
import type { Order } from '../types/api'

const ORDER_STATUSES = [
  'PENDING',
  'ACCEPTED',
  'PREPARING',
  'READY',
  'DELIVERED',
] as const satisfies readonly Order['status'][]

interface OrderStatusEvent {
  order_id: number
  status: Order['status']
}

function isOrderStatusEvent(value: unknown): value is OrderStatusEvent {
  if (
    typeof value !== 'object' ||
    value === null ||
    !('order_id' in value) ||
    !('status' in value)
  ) {
    return false
  }
  return (
    typeof value.order_id === 'number' &&
    Number.isInteger(value.order_id) &&
    typeof value.status === 'string' &&
    ORDER_STATUSES.some((status) => status === value.status)
  )
}

function readStoredOrder(): Order | null {
  const storedOrder = sessionStorage.getItem('kahvecell_latest_order')
  if (!storedOrder) {
    return null
  }
  try {
    return JSON.parse(storedOrder) as Order
  } catch {
    return null
  }
}

export function QrPage() {
  const location = useLocation()
  const [order, setOrder] = useState<Order | null>(() => {
    const orderFromNavigation = location.state as Order | null
    return orderFromNavigation ?? readStoredOrder()
  })
  const orderRef = useRef(order)
  const [streamError, setStreamError] = useState('')
  const [retryVersion, setRetryVersion] = useState(0)
  const orderId = order?.id

  useEffect(() => {
    if (orderId === undefined) {
      return
    }

    let active = true
    const controller = new AbortController()
    let retryTimeout: number | undefined
    let retryDelayMs = 1_000

    async function connectToOrderEvents(): Promise<void> {
      while (active) {
        try {
          const stream = await apiEventStream(
            `/orders/${orderId}/events`,
            controller.signal,
          )
          const reader = stream.getReader()
          const decoder = new TextDecoder()
          let buffer = ''
          let delivered = false
          retryDelayMs = 1_000
          setStreamError('')

          try {
            while (active) {
              const { done, value } = await reader.read()
              if (done) {
                break
              }
              buffer += decoder.decode(value, { stream: true })

              let frameEnd = buffer.indexOf('\n\n')
              while (frameEnd !== -1) {
                const frame = buffer.slice(0, frameEnd)
                buffer = buffer.slice(frameEnd + 2)
                frameEnd = buffer.indexOf('\n\n')
                const data = frame
                  .split(/\r?\n/)
                  .filter((line) => line.startsWith('data:'))
                  .map((line) => line.slice(5).trimStart())
                  .join('\n')
                if (!data) {
                  continue
                }

                const value: unknown = JSON.parse(data)
                if (!isOrderStatusEvent(value)) {
                  throw new Error('Sipariş durumu bildirimi geçersiz.')
                }
                if (value.order_id !== orderId) {
                  continue
                }

                const currentOrder = orderRef.current
                if (currentOrder?.id === value.order_id) {
                  const updatedOrder = {
                    ...currentOrder,
                    status: value.status,
                  }
                  orderRef.current = updatedOrder
                  setOrder(updatedOrder)
                  sessionStorage.setItem(
                    'kahvecell_latest_order',
                    JSON.stringify(updatedOrder),
                  )
                }

                if (value.status === 'DELIVERED') {
                  delivered = true
                  break
                }
              }
              if (delivered) {
                break
              }
            }
          } finally {
            reader.releaseLock()
          }

          if (!active || delivered) {
            return
          }
          throw new Error('Sipariş durumu bağlantısı kapandı.')
        } catch {
          if (!active || controller.signal.aborted) {
            return
          }
          setStreamError(
            'Anlık bildirim bağlantısı kesildi; yeniden bağlanılıyor.',
          )
          await new Promise<void>((resolve) => {
            const finishRetry = () => {
              if (retryTimeout !== undefined) {
                window.clearTimeout(retryTimeout)
              }
              controller.signal.removeEventListener('abort', finishRetry)
              resolve()
            }
            if (controller.signal.aborted) {
              finishRetry()
              return
            }
            retryTimeout = window.setTimeout(finishRetry, retryDelayMs)
            controller.signal.addEventListener('abort', finishRetry, {
              once: true,
            })
          })
          retryDelayMs = Math.min(retryDelayMs * 2, 30_000)
        }
      }
    }

    void connectToOrderEvents()

    return () => {
      active = false
      controller.abort()
      if (retryTimeout !== undefined) {
        window.clearTimeout(retryTimeout)
      }
    }
  }, [orderId, retryVersion])

  if (!order) {
    return (
      <EmptyState
        action={
          <Link className="button-link" to="/shops">
            Dükkânları keşfet
          </Link>
        }
        description="Önce bir dükkândan sipariş ver; QR kodun burada görünecek."
        title="Henüz görüntülenecek bir sipariş yok"
      />
    )
  }

  const statusLabel = ORDER_STATUS_LABELS[order.status]
  const statusClass = `status-${order.status.toLocaleLowerCase('en-US')}`

  if (order.status === 'DELIVERED') {
    return (
      <section className="panel qr-panel order-complete">
        <p className="eyebrow">Sipariş teslim edildi</p>
        <span className="completion-mark" aria-hidden="true">
          ✓
        </span>
        <h1>Afiyet olsun!</h1>
        <p className="muted">
          {order.product_name} siparişin sana teslim edildi.
        </p>
        <span className={`status-badge ${statusClass}`}>{statusLabel}</span>
        <Link className="button-link" to="/history">
          Sipariş geçmişime git
        </Link>
      </section>
    )
  }

  if (!order.qr_code) {
    return (
      <EmptyState
        action={<Link className="button-link" to="/history">Sipariş geçmişime git</Link>}
        description="Sipariş geçmişinden sipariş durumunu kontrol edebilir veya yeni bir sipariş verebilirsin."
        title="Bu sipariş için QR kodu bulunamadı"
      />
    )
  }

  return (
    <section className="panel qr-panel">
      <p className="eyebrow">Sipariş #{order.id}</p>
      <h1>Teslim alma QR kodun</h1>
      <QRCodeSVG
        aria-label="Sipariş QR kodu"
        className="order-qr-code"
        size={280}
        value={JSON.stringify(order.qr_code)}
      />
      <div
        aria-live="polite"
        className={`qr-status-banner ${statusClass}`}
        key={order.status}
      >
        <span className="muted">Sipariş durumu</span>
        <strong className={`status-badge ${statusClass}`}>
          {statusLabel}
        </strong>
      </div>
      <p className="muted">
        Dükkân görevlisi bu kodu okutarak siparişini doğrulayabilir.
      </p>
      {streamError && (
        <ErrorState
          message={streamError}
          onRetry={() => {
            setStreamError('')
            setRetryVersion((version) => version + 1)
          }}
        />
      )}
      <details>
        <summary>QR JSON içeriğini göster</summary>
        <pre className="json-block">
          {JSON.stringify(order.qr_code, null, 2)}
        </pre>
      </details>
      <Link className="button-link" to="/history">
        Siparişlerime git
      </Link>
    </section>
  )
}
