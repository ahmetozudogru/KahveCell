import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useAuth } from '../app/useAuth'
import { ErrorState } from '../components/AsyncStates'
import { apiRequest } from '../lib/api'
import type { TokenResponse } from '../types/api'

export function LoginPage() {
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const { signIn } = useAuth()
  const navigate = useNavigate()

  async function submitLogin(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault()
    setBusy(true)
    setError('')
    try {
      const loginIdentifier = identifier.trim()
      const isPhoneNumber = /^[+\d\s()-]+$/.test(loginIdentifier)
      const result = await apiRequest<TokenResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          ...(isPhoneNumber
            ? { phone_number: loginIdentifier }
            : { username: loginIdentifier }),
          password,
        }),
      })
      signIn(result.access_token, result.role)
      navigate(
        result.role === 'ADMIN'
          ? '/admin'
          : result.role === 'SHOP_OWNER'
            ? '/owner/shop'
            : '/',
      )
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Giriş yapılamadı.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="auth-card">
      <Link className="auth-brand" to="/">
        KahveCell
      </Link>
      <p className="eyebrow">Tekrar hoş geldin</p>
      <h1>Giriş yap</h1>
      <p className="muted">
        Müşteri hesabınla telefon numaranı, yönetici hesabınla kullanıcı adını
        gir.
      </p>
      {error && (
        <ErrorState
          message={error}
          onRetry={() => void submitLogin()}
          title="Giriş yapılamadı"
        />
      )}
      <form className="stack" onSubmit={submitLogin}>
        <label>
          Telefon numarası veya kullanıcı adı
          <input
            autoComplete="username"
            onChange={(event) => setIdentifier(event.target.value)}
            placeholder="+905551234567 veya admin"
            required
            value={identifier}
          />
        </label>
        <label>
          Şifre
          <input
            autoComplete="current-password"
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
        </label>
        <button disabled={busy} type="submit">
          {busy ? 'Giriş yapılıyor…' : 'Giriş yap'}
        </button>
      </form>
      <p className="form-footnote">
        Hesabın yok mu? <Link to="/register">Kayıt ol</Link>
      </p>
    </section>
  )
}
