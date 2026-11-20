import { useEffect, useRef, useState, type FormEvent } from 'react'

import { useToast } from '../app/useToast'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncStates'
import { ApiError, apiRequest } from '../lib/api'
import type {
  CancellationResponse,
  Plan,
  PurchaseResponse,
  Subscription,
} from '../types/api'

const TEST_CARD_NUMBER = '4242-4242-4242-4242'
const PLAN_TIER: Record<string, number> = {
  STARTER: 1,
  PREMIUM: 2,
  UNLIMITED: 3,
}
const SUBSCRIPTION_PERIOD_DAYS = 30

function formatDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Belirtilmemiş'
    : date.toLocaleDateString('tr-TR')
}

function estimatedRenewalDate(): string {
  const renewalDate = new Date()
  renewalDate.setDate(renewalDate.getDate() + SUBSCRIPTION_PERIOD_DAYS)
  return renewalDate.toLocaleDateString('tr-TR')
}

export function SubscriptionPage() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [subscription, setSubscription] = useState<Subscription | null>(null)
  const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [plansLoading, setPlansLoading] = useState(true)
  const [subscriptionLoading, setSubscriptionLoading] = useState(true)
  const [plansError, setPlansError] = useState('')
  const [subscriptionError, setSubscriptionError] = useState('')
  const [plansRetryVersion, setPlansRetryVersion] = useState(0)
  const [subscriptionRetryVersion, setSubscriptionRetryVersion] = useState(0)
  const [busyPlan, setBusyPlan] = useState('')
  const [cancelBusy, setCancelBusy] = useState(false)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const { notify } = useToast()
  const currentPlanTier = subscription
    ? (PLAN_TIER[subscription.plan_code] ?? 0)
    : 0
  const selectedPlanTier = selectedPlan
    ? (PLAN_TIER[selectedPlan.code] ?? 0)
    : 0
  const isUpgrade =
    selectedPlan !== null &&
    subscription !== null &&
    selectedPlanTier > currentPlanTier

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
    let active = true
    apiRequest<Plan[]>('/subscriptions/plans')
      .then((result) => {
        if (active) {
          setPlans(result)
        }
      })
      .catch((requestError: unknown) => {
        if (active) {
          setPlansError(
            requestError instanceof Error
              ? requestError.message
              : 'Paketler yüklenemedi.',
          )
        }
      })
      .finally(() => {
        if (active) {
          setPlansLoading(false)
        }
      })

      return () => {
        active = false
      }
  }, [plansRetryVersion])

  useEffect(() => {
    let active = true
    apiRequest<Subscription>('/subscriptions/me')
      .then((result) => {
        if (active) {
          setSubscription(result)
          setSubscriptionError('')
        }
      })
      .catch((requestError: unknown) => {
        if (
          active &&
          !(requestError instanceof ApiError && requestError.status === 404)
        ) {
          setSubscriptionError(
            requestError instanceof Error
              ? requestError.message
              : 'Abonelik bilgisi yüklenemedi.',
          )
        } else if (active) {
          setSubscription(null)
        }
      })
      .finally(() => {
        if (active) {
          setSubscriptionLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [subscriptionRetryVersion])

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) {
      return
    }
    if (selectedPlan && !dialog.open) {
      dialog.showModal()
    } else if (!selectedPlan && dialog.open) {
      dialog.close()
    }
  }, [selectedPlan])

  async function purchaseSelectedPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedPlan) {
      return
    }

    const isPlanChange =
      subscription !== null && subscription.plan_code !== selectedPlan.code
    setBusyPlan(selectedPlan.code)
    setMessage('')
    setError('')
    try {
      const result = await apiRequest<PurchaseResponse>(
        isPlanChange ? '/subscriptions/me' : '/subscriptions',
        {
          method: isPlanChange ? 'PATCH' : 'POST',
          body: JSON.stringify({
            plan_code: selectedPlan.code,
            card_number: TEST_CARD_NUMBER,
          }),
        },
      )
      if (!result.success) {
        setError(result.message)
        return
      }
      if (!result.subscription) {
        setError('Ödeme başarılı oldu ancak abonelik bilgisi alınamadı.')
        return
      }

      setSubscription(result.subscription)
      setMessage(result.message)
      setSelectedPlan(null)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Ödeme tamamlanamadı.',
      )
    } finally {
      setBusyPlan('')
    }
  }

  async function cancelSubscription() {
    setCancelBusy(true)
    setMessage('')
    setError('')
    try {
      const result = await apiRequest<CancellationResponse>('/subscriptions/me', {
        method: 'DELETE',
      })
      setSubscription(null)
      setMessage(result.message)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Abonelik iptal edilemedi.',
      )
    } finally {
      setCancelBusy(false)
    }
  }

  function retryPlans() {
    setPlansLoading(true)
    setPlansError('')
    setPlansRetryVersion((version) => version + 1)
  }

  function retrySubscription() {
    setSubscriptionLoading(true)
    setSubscriptionError('')
    setSubscriptionRetryVersion((version) => version + 1)
  }

  return (
    <section className="page-stack">
      <header className="page-heading">
        <div>
          <p className="eyebrow">KahveCell</p>
          <h1>Aboneliğim</h1>
        </div>
      </header>

      <div className="page-stack">
        <p className="eyebrow">Aktif abonelik</p>
        {subscriptionLoading ? (
          <LoadingState message="Abonelik bilgisi yükleniyor…" />
        ) : subscriptionError ? (
          <ErrorState
            message={subscriptionError}
            onRetry={retrySubscription}
          />
        ) : subscription ? (
          <section className="panel current-subscription" aria-live="polite">
            <div className="active-subscription-content">
              <div className="active-subscription-details">
                <h2>{subscription.plan_name}</h2>
                <p>
                  Kalan kredi:{' '}
                  <strong>
                    {subscription.remaining_credits === null
                      ? 'Sınırsız'
                      : subscription.remaining_credits}
                  </strong>
                </p>
                <p>
                  Bitiş tarihi:{' '}
                  <strong>{formatDate(subscription.expires_at)}</strong>
                </p>
              </div>
              <button
                className="danger-button"
                disabled={cancelBusy || busyPlan !== ''}
                onClick={() => void cancelSubscription()}
                type="button"
              >
                {cancelBusy ? 'İptal ediliyor…' : 'İptal Et'}
              </button>
            </div>
          </section>
        ) : (
          <EmptyState
            description="Aşağıdaki paketlerden birini seçerek kahve hakkı kazanabilirsin."
            title="Aktif aboneliğiniz yok"
          />
        )}
      </div>

      <div>
        <p className="eyebrow">Paket seçenekleri</p>
        <h2>Sana uygun paketi seç</h2>
      </div>

      {plansLoading ? (
        <LoadingState message="Abonelik paketleri yükleniyor…" />
      ) : plansError ? (
        <ErrorState
          message={plansError}
          onRetry={retryPlans}
        />
      ) : plans.length === 0 ? (
        <EmptyState
          action={
            <button
              className="secondary-button"
              onClick={retryPlans}
              type="button"
            >
              Paketleri yeniden yükle
            </button>
          }
          description="Şu anda satın alınabilir paket yok. Biraz sonra tekrar kontrol edebilirsin."
          title="Listelenecek paket bulunamadı"
        />
      ) : (
        <div className="plan-grid">
          {plans.map((plan) => (
            <article className="panel plan-card" key={plan.code}>
              <h2>{plan.name}</h2>
              <p className="plan-price">
                {Number(plan.monthly_price).toFixed(2)} TL
                <span>/ ay</span>
              </p>
              <ul className="plan-features">
                <li>
                  {plan.monthly_credits === null
                    ? 'Sınırsız kahve'
                    : `${plan.monthly_credits} kahve / ay`}
                </li>
                <li>{plan.guest_credits} misafir kahve hakkı</li>
                <li>
                  {plan.priority_pickup
                    ? 'Öncelikli teslim alma'
                    : 'Standart teslim alma'}
                </li>
              </ul>
              {subscription &&
                (PLAN_TIER[plan.code] ?? 0) < currentPlanTier && (
                  <p className="muted plan-change-note">
                    Alt pakete geçmek için önce mevcut aboneliğinizi iptal edin.
                  </p>
                )}
              <button
                disabled={
                  subscriptionLoading ||
                  subscriptionError !== '' ||
                  busyPlan !== '' ||
                  cancelBusy ||
                  plansLoading ||
                  Boolean(
                    subscription &&
                      (PLAN_TIER[plan.code] ?? 0) < currentPlanTier,
                  )
                }
                onClick={() => {
                  setError('')
                  setSelectedPlan(plan)
                }}
                type="button"
              >
                {busyPlan === plan.code
                  ? 'İşleniyor…'
                  : plan.code === subscription?.plan_code
                    ? 'Yenile'
                    : subscription && (PLAN_TIER[plan.code] ?? 0) < currentPlanTier
                      ? 'Önce iptal et'
                      : 'Satın Al'}
              </button>
            </article>
          ))}
        </div>
      )}

      <dialog
        aria-labelledby="purchase-dialog-title"
        className="purchase-dialog"
        onClose={() => setSelectedPlan(null)}
        ref={dialogRef}
      >
        {selectedPlan && (
          <form className="purchase-dialog-content" onSubmit={purchaseSelectedPlan}>
            <div className="purchase-dialog-heading">
              <div>
                <p className="eyebrow">Güvenli test ödemesi</p>
                <h2 id="purchase-dialog-title">{selectedPlan.name}</h2>
              </div>
              <button
                aria-label="Pencereyi kapat"
                className="dialog-close-button"
                onClick={() => setSelectedPlan(null)}
                type="button"
              >
                ×
              </button>
            </div>
            <p className="muted">
              Aylık {Number(selectedPlan.monthly_price).toFixed(2)} TL
            </p>
            {isUpgrade && subscription && (
              <div className="notice subscription-warning upgrade-warning">
                <p>
                  <strong>Plan değişikliği hemen uygulanır.</strong> Ödeme
                  onaylanınca mevcut paketiniz sona erer ve mevcut hakkınız
                  (
                  {subscription.remaining_credits === null
                    ? 'sınırsız'
                    : `${subscription.remaining_credits} kalan kredi`}
                  ) yeni paketin hakkıyla değiştirilir. Yeni paket hakkı:{' '}
                  <strong>
                    {selectedPlan.monthly_credits === null
                      ? 'sınırsız'
                      : `${selectedPlan.monthly_credits} kredi`}
                  </strong>
                  .
                </p>
                <p>
                  Mevcut bitiş tarihi {formatDate(subscription.expires_at)}.
                  Ödeme onaylanırsa yeni 30 günlük dönem bugün başlar; tahmini
                  yeni bitiş tarihi: <strong>{estimatedRenewalDate()}</strong>.
                </p>
              </div>
            )}
            <label>
              Kart numarası
              <input
                aria-describedby="test-card-note"
                autoComplete="cc-number"
                readOnly
                value={TEST_CARD_NUMBER}
              />
            </label>
            <p className="field-note" id="test-card-note">
              Test kartı, değiştirmeyin.
            </p>
            <button disabled={busyPlan !== ''} type="submit">
              {busyPlan ? 'Ödeme yapılıyor…' : 'Ödemeyi Onayla'}
            </button>
          </form>
        )}
      </dialog>
    </section>
  )
}
