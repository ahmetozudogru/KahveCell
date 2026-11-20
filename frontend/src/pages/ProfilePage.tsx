import { useEffect, useState, type FormEvent } from 'react'

import { useAuth } from '../app/useAuth'
import { useToast } from '../app/useToast'
import { ErrorState, LoadingState } from '../components/AsyncStates'
import { apiRequest } from '../lib/api'
import type { OtpChallenge, TokenResponse, UserProfile } from '../types/api'

function splitName(fullName: string) {
  const parts = fullName.trim().split(/\s+/)
  return {
    firstName: parts.length > 1 ? parts.slice(0, -1).join(' ') : parts[0] ?? '',
    lastName: parts.length > 1 ? parts[parts.length - 1] : '',
  }
}

export function ProfilePage() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [otp, setOtp] = useState('')
  const [otpRequested, setOtpRequested] = useState(false)
  const [otpSent, setOtpSent] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [retryVersion, setRetryVersion] = useState(0)
  const { signIn } = useAuth()
  const { notify } = useToast()

  useEffect(() => {
    let active = true
    apiRequest<UserProfile>('/auth/me')
      .then((result) => {
        if (!active) {
          return
        }
        const name = splitName(result.full_name)
        setProfile(result)
        setFirstName(name.firstName)
        setLastName(name.lastName)
        setPhoneNumber(result.phone_number)
        setOtpRequested(!result.phone_verified)
        setOtpSent(false)
      })
      .catch((requestError: unknown) => {
        if (active) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : 'Profil bilgileri yüklenemedi.',
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

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!profile) {
      return
    }
    setSaving(true)
    try {
      const updated = await apiRequest<UserProfile>('/auth/me/profile', {
        method: 'PATCH',
        body: JSON.stringify({
          full_name: `${firstName.trim()} ${lastName.trim()}`.trim(),
          phone_number: phoneNumber.trim(),
          email: profile.email,
          coffee_preferences: profile.coffee_preferences,
          allergens: profile.allergens,
        }),
      })
      setProfile(updated)
      setPhoneNumber(updated.phone_number)
      setOtpRequested(!updated.phone_verified)
      setOtpSent(false)
      setOtp('')
      notify(
        updated.phone_verified
          ? 'Profilin güncellendi.'
          : 'Profilin güncellendi. Yeni telefon numaranı doğrulaman gerekiyor.',
        'success',
      )
    } catch (requestError) {
      notify(
        requestError instanceof Error
          ? requestError.message
          : 'Profil güncellenemedi.',
        'error',
      )
    } finally {
      setSaving(false)
    }
  }

  async function requestPhoneOtp() {
    setSaving(true)
    try {
      await apiRequest<OtpChallenge>('/auth/request-otp', {
        method: 'POST',
        body: JSON.stringify({ phone_number: profile?.phone_number }),
      })
      setOtpRequested(true)
      setOtpSent(true)
      notify('Doğrulama kodu gönderildi.', 'success')
    } catch (requestError) {
      notify(
        requestError instanceof Error
          ? requestError.message
          : 'Doğrulama kodu gönderilemedi.',
        'error',
      )
    } finally {
      setSaving(false)
    }
  }

  async function verifyPhone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!profile) {
      return
    }
    setSaving(true)
    try {
      const result = await apiRequest<TokenResponse>('/auth/verify-otp', {
        method: 'POST',
        body: JSON.stringify({
          phone_number: profile.phone_number,
          otp,
        }),
      })
      signIn(result.access_token, result.role)
      setProfile((current) =>
        current ? { ...current, phone_verified: true } : current,
      )
      setOtpRequested(false)
      setOtpSent(false)
      setOtp('')
      notify('Telefon numaran doğrulandı.', 'success')
    } catch (requestError) {
      notify(
        requestError instanceof Error
          ? requestError.message
          : 'Telefon numarası doğrulanamadı.',
        'error',
      )
    } finally {
      setSaving(false)
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (newPassword !== confirmPassword) {
      notify('Yeni şifreler birbiriyle eşleşmiyor.', 'error')
      return
    }

    setSaving(true)
    try {
      await apiRequest<{ message: string }>('/auth/me/password', {
        method: 'PATCH',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      notify('Şifren güncellendi.', 'success')
    } catch (requestError) {
      notify(
        requestError instanceof Error
          ? requestError.message
          : 'Şifre güncellenemedi.',
        'error',
      )
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <LoadingState message="Profilin yükleniyor…" />
  }

  if (error || !profile) {
    return (
      <ErrorState
        message={error || 'Profil bilgileri bulunamadı.'}
        onRetry={() => {
          setLoading(true)
          setError('')
          setRetryVersion((version) => version + 1)
        }}
      />
    )
  }

  return (
    <section className="page-stack">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Hesap ayarları</p>
          <h1>Profilim</h1>
          <p className="muted">Kişisel bilgilerini buradan güncelleyebilirsin.</p>
        </div>
      </header>
      <form className="panel stack profile-form" onSubmit={saveProfile}>
        <div className="profile-name-fields">
          <label>
            Ad
            <input
              autoComplete="given-name"
              maxLength={100}
              onChange={(event) => setFirstName(event.target.value)}
              required
              value={firstName}
            />
          </label>
          <label>
            Soyad
            <input
              autoComplete="family-name"
              maxLength={100}
              onChange={(event) => setLastName(event.target.value)}
              required
              value={lastName}
            />
          </label>
        </div>
        <label>
          Telefon numarası
          <input
            autoComplete="tel"
            inputMode="tel"
            maxLength={32}
            onChange={(event) => setPhoneNumber(event.target.value)}
            placeholder="+905551234567"
            required
            value={phoneNumber}
          />
        </label>
        <p className="field-note">
          Telefon değişikliğinde yeni numarayı doğrulaman gerekir. Başka bir
          kullanıcıya ait numara kabul edilmez.
        </p>
        <button disabled={saving} type="submit">
          {saving ? 'Kaydediliyor…' : 'Değişiklikleri kaydet'}
        </button>
      </form>

      {otpRequested && (
        <section className="panel stack phone-verification-panel">
          <div>
            <p className="eyebrow">Güvenlik</p>
            <h2>Telefon numaranı doğrula</h2>
            <p className="muted">
              {otpSent
                ? `${profile.phone_number} numarasına gönderilen kodu gir.`
                : 'Telefon numarana doğrulama kodu göndererek devam et.'}
            </p>
          </div>
          {otpSent ? (
            <form className="stack" onSubmit={verifyPhone}>
              <label>
                4 haneli doğrulama kodu
                <input
                  autoComplete="one-time-code"
                  inputMode="numeric"
                  maxLength={4}
                  onChange={(event) =>
                    setOtp(event.target.value.replace(/\D/g, '').slice(0, 4))
                  }
                  pattern="\d{4}"
                  required
                  value={otp}
                />
              </label>
              <p className="field-note">
                Test ortamında doğrulama kodu <strong>1234</strong>.
              </p>
              <div className="profile-actions">
                <button disabled={saving} type="submit">
                  {saving ? 'Doğrulanıyor…' : 'Telefonu doğrula'}
                </button>
                <button
                  className="secondary-button"
                  disabled={saving}
                  onClick={() => void requestPhoneOtp()}
                  type="button"
                >
                  Kodu yeniden gönder
                </button>
              </div>
            </form>
          ) : (
            <button
              disabled={saving}
              onClick={() => void requestPhoneOtp()}
              type="button"
            >
              {saving ? 'Gönderiliyor…' : 'Doğrulama kodu gönder'}
            </button>
          )}
        </section>
      )}
      <section className="panel stack profile-form">
        <div>
          <p className="eyebrow">Güvenlik</p>
          <h2>Şifremi değiştir</h2>
          <p className="muted">
            Güvenliğin için önce mevcut şifreni doğrula.
          </p>
        </div>
        <form className="stack" onSubmit={changePassword}>
          <label>
            Mevcut şifre
            <input
              autoComplete="current-password"
              onChange={(event) => setCurrentPassword(event.target.value)}
              required
              type="password"
              value={currentPassword}
            />
          </label>
          <label>
            Yeni şifre
            <input
              autoComplete="new-password"
              minLength={8}
              onChange={(event) => setNewPassword(event.target.value)}
              required
              type="password"
              value={newPassword}
            />
          </label>
          <label>
            Yeni şifre (tekrar)
            <input
              autoComplete="new-password"
              minLength={8}
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
              type="password"
              value={confirmPassword}
            />
          </label>
          <button disabled={saving} type="submit">
            {saving ? 'Güncelleniyor…' : 'Şifreyi değiştir'}
          </button>
        </form>
      </section>
    </section>
  )
}
