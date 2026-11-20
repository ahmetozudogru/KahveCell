import type { IScannerControls } from '@zxing/browser'
import { useCallback, useEffect, useRef, useState } from 'react'

import { useToast } from '../app/useToast'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncStates'
import { apiRequest } from '../lib/api'
import { ORDER_STATUS_LABELS } from '../lib/orderStatus'
import type {
  Order,
  QrCodePayload,
  QrVerificationResponse,
} from '../types/api'

const ORDER_POLL_INTERVAL_MS = 5_000

const ORDER_TABS: Array<{ status: Order['status']; label: string }> = [
  { status: 'PENDING', label: 'Bekleyen' },
  { status: 'ACCEPTED', label: 'Kabul Edilen' },
  { status: 'PREPARING', label: 'Hazırlanıyor' },
  { status: 'READY', label: 'Hazır' },
]

const NEXT_ORDER_STATUS: Partial<Record<Order['status'], Order['status']>> = {
  PENDING: 'ACCEPTED',
  ACCEPTED: 'PREPARING',
  PREPARING: 'READY',
}

const STATUS_ACTION_LABELS: Partial<Record<Order['status'], string>> = {
  PENDING: 'Kabul Et',
  ACCEPTED: 'Hazırlamaya Başla',
  PREPARING: 'Hazır',
}

const MILK_TYPE_LABELS: Record<Order['customizations']['milk_type'], string> = {
  NONE: 'Sütsüz',
  WHOLE: 'Normal süt',
  OAT: 'Yulaf sütü',
  ALMOND: 'Badem sütü',
  LACTOSE_FREE: 'Laktozsuz süt',
}

function isQrCodePayload(value: unknown): value is QrCodePayload {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  return (
    'order_id' in value &&
    typeof value.order_id === 'string' &&
    'user_id' in value &&
    typeof value.user_id === 'string' &&
    'shop_id' in value &&
    typeof value.shop_id === 'string' &&
    'created_at' in value &&
    typeof value.created_at === 'string' &&
    'signature' in value &&
    typeof value.signature === 'string' &&
    /^[a-f0-9]{64}$/.test(value.signature)
  )
}

function formatOrderTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Saat bilgisi yok'
    : date.toLocaleString('tr-TR')
}

export function ShopOwnerOrdersPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [activeStatus, setActiveStatus] =
    useState<(typeof ORDER_TABS)[number]['status']>('PENDING')
  const [error, setError] = useState('')
  const [loadError, setLoadError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(true)
  const [retryVersion, setRetryVersion] = useState(0)
  const [busyOrderId, setBusyOrderId] = useState<number | null>(null)
  const [scanningOrder, setScanningOrder] = useState<Order | null>(null)
  const [scannerStarting, setScannerStarting] = useState(false)
  const [scanError, setScanError] = useState('')
  const [scanMessage, setScanMessage] = useState('')
  const [capturedQr, setCapturedQr] = useState('')
  const [manualConfirmOrder, setManualConfirmOrder] = useState<Order | null>(
    null,
  )
  const [confirmingOrderId, setConfirmingOrderId] = useState<number | null>(
    null,
  )
  const videoRef = useRef<HTMLVideoElement>(null)
  const { notify } = useToast()

  useEffect(() => {
    if (message) {
      notify(message, 'success')
    }
  }, [message, notify])

  useEffect(() => {
    if (error) {
      notify(error, 'error')
    }
  }, [error, notify])

  useEffect(() => {
    if (scanMessage) {
      notify(scanMessage, 'success')
    }
  }, [notify, scanMessage])

  useEffect(() => {
    if (scanError) {
      notify(scanError, 'error')
    }
  }, [notify, scanError])

  const refreshOrders = useCallback(async () => {
    try {
      const result = await apiRequest<Order[]>('/orders/shop')
      setOrders(result)
      setLoadError('')
      setLoading(false)
      return true
    } catch (requestError) {
      setLoadError(
        requestError instanceof Error
          ? requestError.message
          : 'Siparişler yüklenemedi.',
      )
      setLoading(false)
      return false
    }
  }, [])

  useEffect(() => {
    let active = true
    let timeoutId: number

    async function pollOrders(): Promise<void> {
      try {
        const result = await apiRequest<Order[]>('/orders/shop')
        if (active) {
          setOrders(result)
          setLoadError('')
          setLoading(false)
        }
      } catch (requestError) {
        if (active) {
          setLoadError(
            requestError instanceof Error
              ? requestError.message
              : 'Siparişler yüklenemedi.',
          )
          setLoading(false)
        }
      }

      if (active) {
        timeoutId = window.setTimeout(
          () => void pollOrders(),
          ORDER_POLL_INTERVAL_MS,
        )
      }
    }

    void pollOrders()
    return () => {
      active = false
      window.clearTimeout(timeoutId)
    }
  }, [retryVersion])

  async function updateOrderStatus(order: Order) {
    const nextStatus = NEXT_ORDER_STATUS[order.status]
    if (!nextStatus) {
      return
    }
    setBusyOrderId(order.id)
    setError('')
    setMessage('')
    try {
      const updatedOrder = await apiRequest<Order>(
        `/orders/${order.id}/status`,
        {
          method: 'PATCH',
          body: JSON.stringify({ status: nextStatus }),
        },
      )
      setOrders((currentOrders) =>
        currentOrders.map((currentOrder) =>
          currentOrder.id === updatedOrder.id ? updatedOrder : currentOrder,
        ),
      )
      setMessage(
        `Sipariş #${updatedOrder.id}: ${ORDER_STATUS_LABELS[updatedOrder.status]}.`,
      )
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Sipariş durumu güncellenemedi.',
      )
    } finally {
      setBusyOrderId(null)
    }
  }

  async function confirmOrderWithoutCamera() {
    if (!manualConfirmOrder) {
      return
    }
    const order = manualConfirmOrder
    setConfirmingOrderId(order.id)
    setError('')
    setMessage('')
    try {
      const result = await apiRequest<QrVerificationResponse>(
        `/orders/${order.id}/qr/confirm`,
        { method: 'POST' },
      )
      if (!result.valid) {
        throw new Error(result.message)
      }
      setManualConfirmOrder(null)
      setMessage(result.message)
      await refreshOrders()
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'QR kod onaylanamadı.',
      )
    } finally {
      setConfirmingOrderId(null)
    }
  }

  function openScanner(order: Order) {
    if (!order.qr_code) {
      setError('Bu sipariş için doğrulanabilir QR kodu bulunamadı.')
      return
    }
    setError('')
    setScanError('')
    setScanMessage('')
    setCapturedQr('')
    setScannerStarting(true)
    setScanningOrder(order)
  }

  useEffect(() => {
    const videoElement = videoRef.current
    if (!scanningOrder || !videoElement) {
      return
    }

    let active = true
    let decoded = false
    let controls: IScannerControls | undefined
    async function startScanner(
      previewElement: HTMLVideoElement,
    ): Promise<void> {
      try {
        const { BrowserQRCodeReader } = await import('@zxing/browser')
        if (!active) {
          return
        }
        const reader = new BrowserQRCodeReader()
        controls = await reader.decodeFromConstraints(
          { audio: false, video: { facingMode: { ideal: 'environment' } } },
          previewElement,
          (result, _decodeError, scannerControls) => {
            controls = scannerControls
            if (!active || decoded || !result) {
              return
            }
            decoded = true
            scannerControls.stop()
            setScannerStarting(false)
            setCapturedQr(result.getText())
          },
        )
        if (active) {
          setScannerStarting(false)
        } else {
          controls.stop()
        }
      } catch (cameraError: unknown) {
        if (active) {
          setScannerStarting(false)
          setScanError(
            cameraError instanceof Error
              ? `Kamera açılamadı: ${cameraError.message}`
              : 'Kamera açılamadı. Tarayıcı kamera iznini kontrol edin.',
          )
        }
      }
    }

    void startScanner(videoElement)

    return () => {
      active = false
      controls?.stop()
    }
  }, [scanningOrder])

  useEffect(() => {
    if (!capturedQr || !scanningOrder) {
      return
    }

    const orderToVerify = scanningOrder
    let active = true
    async function verifyScannedQr(): Promise<void> {
      try {
        const decodedValue: unknown = JSON.parse(capturedQr)
        if (!isQrCodePayload(decodedValue)) {
          throw new Error('Okunan QR kod biçimi geçersiz.')
        }
        if (decodedValue.order_id !== orderToVerify.qr_code?.order_id) {
          throw new Error('Okunan QR kod seçili siparişe ait değil.')
        }

        const result = await apiRequest<QrVerificationResponse>(
          '/orders/qr/verify',
          {
            method: 'POST',
            body: JSON.stringify(decodedValue),
          },
        )
        if (!active) {
          return
        }
        if (!result.valid) {
          throw new Error(result.message)
        }

        setScanMessage(result.message)
        setScanningOrder(null)
        setCapturedQr('')
        await refreshOrders()
      } catch (requestError) {
        if (active) {
          setScanError(
            requestError instanceof Error
              ? requestError.message
              : 'QR kod doğrulanamadı.',
          )
          setScanningOrder(null)
          setCapturedQr('')
        }
      }
    }

    void verifyScannedQr()
    return () => {
      active = false
    }
  }, [capturedQr, refreshOrders, scanningOrder])

  const visibleOrders = orders
    .filter((order) => order.status === activeStatus)
    .sort(
      (first, second) =>
        new Date(second.created_at).getTime() -
          new Date(first.created_at).getTime() ||
        second.id - first.id,
    )

  function retryOrders() {
    setLoading(true)
    setLoadError('')
    setRetryVersion((version) => version + 1)
  }

  return (
    <section className="page-stack">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Dükkân yönetimi</p>
          <h1>Siparişler</h1>
          <p className="muted">Sipariş listesi otomatik olarak yenilenir.</p>
        </div>
      </header>

      <div className="order-tabs" role="tablist" aria-label="Sipariş durumu">
        {ORDER_TABS.map((tab) => {
          const count = orders.filter(
            (order) => order.status === tab.status,
          ).length
          return (
            <button
              aria-selected={activeStatus === tab.status}
              className="order-tab"
              id={`order-tab-${tab.status.toLowerCase()}`}
              key={tab.status}
              onClick={() => setActiveStatus(tab.status)}
              role="tab"
              type="button"
            >
              {tab.label} <span>{count}</span>
            </button>
          )
        })}
      </div>

      <div
        aria-labelledby={`order-tab-${activeStatus.toLowerCase()}`}
        className="order-list"
        role="tabpanel"
      >
        {loading ? (
          <LoadingState message="Siparişler yükleniyor…" />
        ) : loadError ? (
          <ErrorState
            message={loadError}
            onRetry={retryOrders}
          />
        ) : visibleOrders.length === 0 ? (
          <EmptyState
            description="Yeni siparişler geldiğinde bu liste otomatik olarak güncellenir."
            title={`"${ORDER_TABS.find((tab) => tab.status === activeStatus)?.label}" sekmesinde sipariş yok`}
          />
        ) : (
          visibleOrders.map((order) => (
            <article className="panel owner-order-card" key={order.id}>
              <div className="owner-order-heading">
                <div>
                  <p className="eyebrow">Sipariş #{order.id}</p>
                  <h2>{order.product_name}</h2>
                </div>
                <span
                  className={`status-badge status-${order.status.toLocaleLowerCase('en-US')}`}
                >
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
                  <strong>Dükkân:</strong> {order.shop_name}
                </p>
                <p>
                  <strong>Ürün:</strong> {order.product_name}
                </p>
                <p>
                  <strong>Özelleştirmeler:</strong>{' '}
                  {order.customizations.size} boy ·{' '}
                  {MILK_TYPE_LABELS[order.customizations.milk_type]} · Şeker{' '}
                  {order.customizations.sugar_level} · Ek shot{' '}
                  {order.customizations.extra_shots}
                </p>
                <p>
                  <strong>Sipariş zamanı:</strong>{' '}
                  {formatOrderTime(order.created_at)}
                </p>
              </div>
              {order.status === 'READY' ? (
                <div className="owner-order-actions">
                  <button
                    disabled={busyOrderId !== null || confirmingOrderId !== null}
                    onClick={() => openScanner(order)}
                    type="button"
                  >
                    QR Okut
                  </button>
                  <button
                    className="secondary-button"
                    disabled={busyOrderId !== null || confirmingOrderId !== null}
                    onClick={() => setManualConfirmOrder(order)}
                    type="button"
                  >
                    QR'ı Butonla Onayla
                  </button>
                </div>
              ) : (
                <button
                  disabled={busyOrderId === order.id}
                  onClick={() => void updateOrderStatus(order)}
                  type="button"
                >
                  {busyOrderId === order.id
                    ? 'Güncelleniyor…'
                    : STATUS_ACTION_LABELS[order.status]}
                </button>
              )}
            </article>
          ))
        )}
      </div>

      {scanningOrder && (
        <div className="scanner-backdrop">
          <section
            aria-labelledby="scanner-title"
            aria-modal="true"
            className="panel scanner-dialog"
            role="dialog"
          >
            <div className="scanner-heading">
              <div>
                <p className="eyebrow">Sipariş #{scanningOrder.id}</p>
                <h2 id="scanner-title">QR kodu okut</h2>
              </div>
              <button
                aria-label="Kamerayı kapat"
                className="dialog-close-button"
                onClick={() => setScanningOrder(null)}
                type="button"
              >
                ×
              </button>
            </div>
            <video
              autoPlay
              className="qr-scanner-video"
              muted
              playsInline
              ref={videoRef}
            />
            {scannerStarting && (
              <p className="muted">Kamera açılıyor…</p>
            )}
            <p className="muted">
              Bu siparişin QR kodunu kameranın önünde tutun.
            </p>
            <button
              className="secondary-button"
              onClick={() => setScanningOrder(null)}
              type="button"
            >
              Kapat
            </button>
          </section>
        </div>
      )}

      {manualConfirmOrder && (
        <div className="scanner-backdrop">
          <section
            aria-labelledby="manual-confirm-title"
            aria-modal="true"
            className="panel scanner-dialog"
            role="dialog"
          >
            <div className="scanner-heading">
              <div>
                <p className="eyebrow">Sipariş #{manualConfirmOrder.id}</p>
                <h2 id="manual-confirm-title">QR kodunu butonla onayla</h2>
              </div>
              <button
                aria-label="Onay penceresini kapat"
                className="dialog-close-button"
                disabled={confirmingOrderId !== null}
                onClick={() => setManualConfirmOrder(null)}
                type="button"
              >
                ×
              </button>
            </div>
            <p>
              <strong>{manualConfirmOrder.shop_name}</strong> restoranındaki{' '}
              <strong>{manualConfirmOrder.product_name}</strong> siparişini
              teslim edilmiş olarak işaretlemek üzeresiniz.
            </p>
            <p className="muted">
              Bu işlem kamerayı kullanmadan sunucudaki imzalı sipariş QR kodunu
              doğrular. Yalnızca müşterinin QR kodunu gördükten sonra onaylayın.
            </p>
            <div className="owner-order-actions">
              <button
                disabled={confirmingOrderId !== null}
                onClick={() => void confirmOrderWithoutCamera()}
                type="button"
              >
                {confirmingOrderId === manualConfirmOrder.id
                  ? 'Onaylanıyor…'
                  : 'Onayla ve teslim et'}
              </button>
              <button
                className="secondary-button"
                disabled={confirmingOrderId !== null}
                onClick={() => setManualConfirmOrder(null)}
                type="button"
              >
                Vazgeç
              </button>
            </div>
          </section>
        </div>
      )}
    </section>
  )
}
