import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ErrorState } from '../components/AsyncStates'
import { apiRequest } from '../lib/api'
import type { OtpChallenge } from '../types/api'

export function RegisterPage() {
  const [phone, setPhone] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function register(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await apiRequest<OtpChallenge>('/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          phone_number: phone,
          full_name: fullName,
          password,
        }),
      })
      sessionStorage.setItem('kahvecell_pending_phone', result.phone_number)
      navigate('/otp', { state: { phone: result.phone_number } })
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Kayıt başlatılamadı.',
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
      <p className="eyebrow">Yeni hesap</p>
      <h1>Kayıt ol</h1>
      <p className="muted">Hesabını oluşturmak için bilgilerini gir.</p>
      {error && (
        <ErrorState
          message={error}
          onRetry={() => void register()}
          title="Kayıt başlatılamadı"
        />
      )}
      <form className="stack" onSubmit={register}>
        <label>
          Telefon numarası
          <input
            autoComplete="tel"
            onChange={(event) => setPhone(event.target.value)}
            placeholder="+905551234567"
            required
            value={phone}
          />
        </label>
        <label>
          Ad soyad
          <input
            autoComplete="name"
            onChange={(event) => setFullName(event.target.value)}
            required
            value={fullName}
          />
        </label>
        <label>
          Şifre
          <input
            autoComplete="new-password"
            minLength={8}
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
        </label>
        <p className="field-note">Şifren en az 8 karakter olmalı.</p>
        <button disabled={busy} type="submit">
          {busy ? 'Kaydediliyor…' : 'Kayıt ol'}
        </button>
      </form>
      <p className="form-footnote">
        Zaten hesabın var mı? <Link to="/login">Giriş yap</Link>
      </p>
    </section>
  )
}
