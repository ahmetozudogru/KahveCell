import { useEffect, useRef, useState, type FormEvent } from 'react'

import { useToast } from '../app/useToast'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncStates'
import { ShopRating } from '../components/ShopRating'
import { apiRequest } from '../lib/api'
import type {
  AdminShop,
  AdminShopPayload,
  AdminUser,
  GeocodeResult,
  UserProfile,
  UserRole,
} from '../types/api'

type AdminTab = 'users' | 'shops'

interface ShopDraft {
  name: string
  address: string
  latitude: string
  longitude: string
  opening_hours: string
  owner_id: string
}

const EMPTY_SHOP_DRAFT: ShopDraft = {
  name: '',
  address: '',
  latitude: '',
  longitude: '',
  opening_hours: '',
  owner_id: '',
}

const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: 'CUSTOMER', label: 'Müşteri' },
  { value: 'SHOP_OWNER', label: 'Dükkân sahibi' },
  { value: 'ADMIN', label: 'Yönetici' },
]

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'İşlem tamamlanamadı.'
}

export function AdminPage() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [shops, setShops] = useState<AdminShop[]>([])
  const [currentAdminId, setCurrentAdminId] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState<AdminTab>('users')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retryVersion, setRetryVersion] = useState(0)
  const [busyUserId, setBusyUserId] = useState<number | null>(null)
  const [savingShop, setSavingShop] = useState(false)
  const [geocodingAddress, setGeocodingAddress] = useState(false)
  const [geocodeMessage, setGeocodeMessage] = useState('')
  const [editingShopId, setEditingShopId] = useState<number | null>(null)
  const [shopDraft, setShopDraft] = useState<ShopDraft>(EMPTY_SHOP_DRAFT)
  const geocodingAddressRef = useRef(false)
  const addressDirtyRef = useRef(false)
  const { notify } = useToast()

  useEffect(() => {
    let active = true
    Promise.all([
      apiRequest<AdminUser[]>('/admin/users'),
      apiRequest<AdminShop[]>('/admin/shops'),
      apiRequest<UserProfile>('/auth/me'),
    ])
      .then(([loadedUsers, loadedShops, profile]) => {
        if (active) {
          setUsers(loadedUsers)
          setShops(loadedShops)
          setCurrentAdminId(profile.id)
          setError('')
        }
      })
      .catch((requestError: unknown) => {
        if (active) {
          setError(getErrorMessage(requestError))
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

  function retry() {
    setLoading(true)
    setError('')
    setRetryVersion((version) => version + 1)
  }

  async function changeUserRole(userId: number, role: UserRole) {
    setBusyUserId(userId)
    try {
      const updatedUser = await apiRequest<AdminUser>(
        `/admin/users/${userId}/role`,
        {
          method: 'PATCH',
          body: JSON.stringify({ role }),
        },
      )
      setUsers((currentUsers) =>
        currentUsers.map((user) =>
          user.id === updatedUser.id ? updatedUser : user,
        ),
      )
      notify('Kullanıcı rolü güncellendi.', 'success')
    } catch (requestError) {
      notify(getErrorMessage(requestError), 'error')
    } finally {
      setBusyUserId(null)
    }
  }

  function startEditingShop(shop: AdminShop) {
    setEditingShopId(shop.id)
    setGeocodeMessage('')
    addressDirtyRef.current = false
    setShopDraft({
      name: shop.name,
      address: shop.address,
      latitude: String(shop.latitude),
      longitude: String(shop.longitude),
      opening_hours: shop.opening_hours ?? '',
      owner_id: shop.owner_id === null ? '' : String(shop.owner_id),
    })
  }

  function resetShopForm() {
    setEditingShopId(null)
    setShopDraft(EMPTY_SHOP_DRAFT)
    setGeocodeMessage('')
    addressDirtyRef.current = false
  }

  async function findShopCoordinates() {
    const address = shopDraft.address.trim()
    if (address.length < 3 || geocodingAddressRef.current) {
      return
    }

    geocodingAddressRef.current = true
    setGeocodingAddress(true)
    setGeocodeMessage('')
    try {
      const location = await apiRequest<GeocodeResult>('/admin/geocode', {
        method: 'POST',
        body: JSON.stringify({ address }),
      })
      setShopDraft((current) => ({
        ...current,
        latitude: String(location.latitude),
        longitude: String(location.longitude),
      }))
      addressDirtyRef.current = false
      setGeocodeMessage(`Bulunan konum: ${location.display_name}`)
      notify('Enlem ve boylam adresten dolduruldu.', 'success')
    } catch (requestError) {
      const message = getErrorMessage(requestError)
      setGeocodeMessage(message)
      notify(message, 'error')
    } finally {
      geocodingAddressRef.current = false
      setGeocodingAddress(false)
    }
  }

  async function saveShop(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSavingShop(true)
    const payload: AdminShopPayload = {
      name: shopDraft.name.trim(),
      address: shopDraft.address.trim(),
      latitude: Number(shopDraft.latitude),
      longitude: Number(shopDraft.longitude),
      opening_hours: shopDraft.opening_hours.trim() || null,
      owner_id: shopDraft.owner_id ? Number(shopDraft.owner_id) : null,
    }
    try {
      const savedShop = await apiRequest<AdminShop>(
        editingShopId === null
          ? '/admin/shops'
          : `/admin/shops/${editingShopId}`,
        {
          method: editingShopId === null ? 'POST' : 'PUT',
          body: JSON.stringify(payload),
        },
      )
      setShops((currentShops) => {
        const nextShops =
          editingShopId === null
            ? [...currentShops, savedShop]
            : currentShops.map((shop) =>
                shop.id === savedShop.id ? savedShop : shop,
              )
        return nextShops.sort((first, second) =>
          first.name.localeCompare(second.name, 'tr-TR'),
        )
      })
      resetShopForm()
      notify(
        editingShopId === null
          ? 'Dükkân oluşturuldu.'
          : 'Dükkân bilgileri güncellendi.',
        'success',
      )
    } catch (requestError) {
      notify(getErrorMessage(requestError), 'error')
    } finally {
      setSavingShop(false)
    }
  }

  const shopOwners = users.filter((user) => user.role === 'SHOP_OWNER')

  return (
    <section className="page-stack admin-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">KahveCell</p>
          <h1>Yönetim paneli</h1>
          <p className="muted">
            Kullanıcı rollerini ve dükkân bilgilerini buradan yönet.
          </p>
        </div>
      </header>

      {loading ? (
        <LoadingState message="Yönetim verileri yükleniyor…" />
      ) : error ? (
        <ErrorState message={error} onRetry={retry} />
      ) : (
        <>
          <div aria-label="Yönetim bölümleri" className="admin-tabs" role="tablist">
            <button
              aria-selected={activeTab === 'users'}
              className="order-tab"
              onClick={() => setActiveTab('users')}
              role="tab"
              type="button"
            >
              Kullanıcılar <span>{users.length}</span>
            </button>
            <button
              aria-selected={activeTab === 'shops'}
              className="order-tab"
              onClick={() => setActiveTab('shops')}
              role="tab"
              type="button"
            >
              Dükkânlar <span>{shops.length}</span>
            </button>
          </div>

          {activeTab === 'users' ? (
            <section aria-label="Kullanıcı yönetimi" className="page-stack">
              <div>
                <h2>Kullanıcılar ve roller</h2>
                <p className="muted">
                  Bir kullanıcıya dükkân sahibi rolü verip sonra dükkânını
                  atayabilirsin.
                </p>
              </div>
              {users.length === 0 ? (
                <EmptyState
                  description="Yeni kullanıcılar kayıt olduklarında burada görünür."
                  title="Henüz kullanıcı yok"
                />
              ) : (
                <div className="admin-table-wrap panel">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th scope="col">Kullanıcı</th>
                        <th scope="col">İletişim</th>
                        <th scope="col">Rol</th>
                        <th scope="col">Telefon</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map((user) => (
                        <tr key={user.id}>
                          <td>
                            <strong>{user.full_name}</strong>
                            <small>#{user.id}</small>
                          </td>
                          <td>
                            {user.username
                              ? `@${user.username}`
                              : (user.phone_number ?? '—')}
                          </td>
                          <td>
                            <select
                              aria-label={`${user.full_name} rolü`}
                              disabled={
                                busyUserId === user.id ||
                                currentAdminId === user.id
                              }
                              onChange={(event) =>
                                void changeUserRole(
                                  user.id,
                                  event.target.value as UserRole,
                                )
                              }
                              value={user.role}
                            >
                              {ROLE_OPTIONS.map((option) => (
                                <option
                                  key={option.value}
                                  value={option.value}
                                >
                                  {option.label}
                                </option>
                              ))}
                            </select>
                            {currentAdminId === user.id && (
                              <small>Kendi yönetici rolün korunuyor.</small>
                            )}
                          </td>
                          <td>{user.phone_verified ? 'Doğrulandı' : 'Bekliyor'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          ) : (
            <section aria-label="Dükkân yönetimi" className="page-stack">
              <div>
                <h2>Dükkânlar</h2>
                <p className="muted">
                  Dükkân ekle, bilgilerini güncelle veya bir dükkân sahibine
                  ata. Kayıtlar kalıcı olarak silinmez; geçmiş siparişler korunur.
                </p>
              </div>

              <form className="panel admin-shop-form" onSubmit={saveShop}>
                <div className="admin-form-heading">
                  <h3>
                    {editingShopId === null
                      ? 'Yeni dükkân ekle'
                      : 'Dükkânı düzenle'}
                  </h3>
                  {editingShopId !== null && (
                    <button
                      className="secondary-button"
                      onClick={resetShopForm}
                      type="button"
                    >
                      Düzenlemeyi iptal et
                    </button>
                  )}
                </div>
                <div className="admin-shop-form-grid">
                  <label>
                    Dükkân adı
                    <input
                      maxLength={150}
                      minLength={2}
                      onChange={(event) =>
                        setShopDraft({
                          ...shopDraft,
                          name: event.target.value,
                        })
                      }
                      required
                      value={shopDraft.name}
                    />
                  </label>
                  <div className="admin-geocode-field">
                    <label>
                      Adres
                      <input
                        maxLength={255}
                        minLength={3}
                        onBlur={() => {
                          if (addressDirtyRef.current) {
                            void findShopCoordinates()
                          }
                        }}
                        onChange={(event) => {
                          addressDirtyRef.current = true
                          setShopDraft({
                            ...shopDraft,
                            address: event.target.value,
                            latitude: '',
                            longitude: '',
                          })
                          setGeocodeMessage('')
                        }}
                        required
                        value={shopDraft.address}
                      />
                    </label>
                    <button
                      className="secondary-button"
                      disabled={
                        geocodingAddress || shopDraft.address.trim().length < 3
                      }
                      onClick={() => void findShopCoordinates()}
                      type="button"
                    >
                      {geocodingAddress
                        ? 'Konum aranıyor…'
                        : 'Adresten konum bul'}
                    </button>
                    <p className="field-note" role="status">
                      Adresten çıkınca koordinatlar otomatik aranır. Sonuç
                      OpenStreetMap Nominatim (© OpenStreetMap katkıda
                      bulunanlar) üzerinden gelir; gerekirse elle
                      düzeltebilirsin.
                    </p>
                    {geocodeMessage && (
                      <p className="field-note" role="status">
                        {geocodeMessage}
                      </p>
                    )}
                  </div>
                  <label>
                    Enlem
                    <input
                      max={90}
                      min={-90}
                      onChange={(event) =>
                        setShopDraft({
                          ...shopDraft,
                          latitude: event.target.value,
                        })
                      }
                      required
                      step="any"
                      type="number"
                      value={shopDraft.latitude}
                    />
                  </label>
                  <label>
                    Boylam
                    <input
                      max={180}
                      min={-180}
                      onChange={(event) =>
                        setShopDraft({
                          ...shopDraft,
                          longitude: event.target.value,
                        })
                      }
                      required
                      step="any"
                      type="number"
                      value={shopDraft.longitude}
                    />
                  </label>
                  <label>
                    Çalışma saatleri
                    <input
                      onChange={(event) =>
                        setShopDraft({
                          ...shopDraft,
                          opening_hours: event.target.value,
                        })
                      }
                      placeholder="Her gün 09:00-21:00"
                      value={shopDraft.opening_hours}
                    />
                  </label>
                  <label>
                    Dükkân sahibi
                    <select
                      onChange={(event) =>
                        setShopDraft({
                          ...shopDraft,
                          owner_id: event.target.value,
                        })
                      }
                      value={shopDraft.owner_id}
                    >
                      <option value="">Atanmamış</option>
                      {shopOwners.map((owner) => (
                        <option key={owner.id} value={owner.id}>
                          {owner.full_name} (#{owner.id})
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <button disabled={savingShop} type="submit">
                  {savingShop
                    ? 'Kaydediliyor…'
                    : editingShopId === null
                      ? 'Dükkân oluştur'
                      : 'Değişiklikleri kaydet'}
                </button>
              </form>

              {shops.length === 0 ? (
                <EmptyState
                  description="Yukarıdaki formdan ilk dükkânı ekleyebilirsin."
                  title="Henüz dükkân eklenmemiş"
                />
              ) : (
                <div className="admin-shop-list">
                  {shops.map((shop) => (
                    <article className="panel admin-shop-card" key={shop.id}>
                      <div>
                        <p className="eyebrow">Dükkân #{shop.id}</p>
                        <h3>{shop.name}</h3>
                        <p className="muted">{shop.address}</p>
                        <ShopRating
                          rating={shop.rating}
                          ratingCount={shop.rating_count}
                        />
                        <p className="admin-shop-meta">
                          {shop.opening_hours ?? 'Çalışma saati belirtilmemiş'}
                          <span>
                            {shop.owner_name
                              ? `Sorumlu: ${shop.owner_name}`
                              : 'Dükkân sahibi atanmamış'}
                          </span>
                        </p>
                      </div>
                      <button
                        className="secondary-button"
                        onClick={() => startEditingShop(shop)}
                        type="button"
                      >
                        Düzenle
                      </button>
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}
        </>
      )}
    </section>
  )
}
