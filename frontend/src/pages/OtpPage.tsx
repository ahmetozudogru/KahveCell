import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../app/useAuth'
import { ErrorState } from '../components/AsyncStates'
import { apiRequest } from '../lib/api'
import type { TokenResponse } from '../types/api'

const PENDING_PHONE_KEY = 'kahvecell_pending_phone'

export function OtpPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { signIn } = useAuth()
  const routeState = location.state as { phone?: string } | null
  const phone = routeState?.phone ?? sessionStorage.getItem(PENDING_PHONE_KEY)
  const [otp, setOtp] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function verifyOtp(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault()
    if (!phone) {
      return
    }
    setBusy(true)
    setError('')
    try {
      const result = await apiRequest<TokenResponse>('/auth/verify-otp', {
        method: 'POST',
        body: JSON.stringify({ phone_number: phone, otp }),
      })
      sessionStorage.removeItem(PENDING_PHONE_KEY)
      signIn(result.access_token, result.role)
      navigate(result.role === 'SHOP_OWNER' ? '/owner/shop' : '/')
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Kod doğrulanamadı.',
      )
    } finally {
      setBusy(false)
    }
  }

  if (!phone) {
    return <Navigate to="/register" replace />
  }

  return (
    <section className="auth-card">
      <Link className="auth-brand" to="/">
        KahveCell
      </Link>
      <p className="eyebrow">Telefon doğrulama</p>
      <h1>Kodu gir</h1>
      <p className="muted">Telefonuna gelen 4 haneli kodu gir.</p>
      {error && (
        <ErrorState
          message={error}
          onRetry={() => void verifyOtp()}
          title="Kod doğrulanamadı"
        />
      )}
      <form className="stack" onSubmit={verifyOtp}>
        <label>
          4 haneli kod
          <input
            autoComplete="one-time-code"
            autoFocus
            inputMode="numeric"
            maxLength={4}
            onChange={(event) =>
              setOtp(event.target.value.replace(/\D/g, '').slice(0, 4))
            }
            pattern="\d{4}"
            placeholder="••••"
            required
            value={otp}
          />
        </label>
        <p className="field-note">
          Test notu: SMS simülasyonunda doğrulama kodu her zaman <strong>1234</strong>.
        </p>
        <button disabled={busy} type="submit">
          {busy ? 'Doğrulanıyor…' : 'Telefonu doğrula'}
        </button>
      </form>
    </section>
  )
}
