import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Navigate, Outlet, Route, Routes } from 'react-router-dom'

import { useAuth } from './useAuth'
import { ErrorState, LoadingState } from '../components/AsyncStates'
import { ApiError, apiRequest } from '../lib/api'
import { LoginPage } from '../pages/LoginPage'
import { RegisterPage } from '../pages/RegisterPage'
import { OtpPage } from '../pages/OtpPage'
import { HomePage } from '../pages/HomePage'
import { ShopDetailPage } from '../pages/ShopDetailPage'
import { OrderPage } from '../pages/OrderPage'
import { QrPage } from '../pages/QrPage'
import { HistoryPage } from '../pages/HistoryPage'
import { SubscriptionPage } from '../pages/SubscriptionPage'
import { LandingPage } from '../pages/LandingPage'
import { AdminPage } from '../pages/AdminPage'
import { ShopOwnerOrderHistoryPage } from '../pages/ShopOwnerOrderHistoryPage'
import { ShopOwnerOrdersPage } from '../pages/ShopOwnerOrdersPage'
import { ShopOwnerShopPage } from '../pages/ShopOwnerShopPage'
import { ProfilePage } from '../pages/ProfilePage'
import { FavoritesPage } from '../pages/FavoritesPage'
import type { UserProfile } from '../types/api'

interface RoleAccess {
  token: string
  status: 'allowed' | 'forbidden' | 'unauthorized' | 'failed'
  message?: string
}

function AppLayout() {
  const { token, role, signOut } = useAuth()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!userMenuOpen) {
      return
    }

    function closeOnOutsideClick(event: PointerEvent) {
      if (
        event.target instanceof Node &&
        !userMenuRef.current?.contains(event.target)
      ) {
        setUserMenuOpen(false)
      }
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setUserMenuOpen(false)
      }
    }

    document.addEventListener('pointerdown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [userMenuOpen])

  return (
    <div className="app-shell">
      <header className="site-header">
        <Link className="brand" to="/">
          KahveCell
        </Link>
        <nav className="main-nav" aria-label="Ana menü">
          <NavLink
            className={({ isActive }) =>
              `nav-link${isActive ? ' active' : ''}`
            }
            end
            to="/"
          >
            Ana sayfa
          </NavLink>
          <NavLink
            className={({ isActive }) =>
              `nav-link${isActive ? ' active' : ''}`
            }
            to="/shops"
          >
            Dükkânlar
          </NavLink>
          {token && role === 'SHOP_OWNER' && (
            <>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? ' active' : ''}`
                }
                end
                to="/owner/shop"
              >
                Restoranım
              </NavLink>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? ' active' : ''}`
                }
                end
                to="/owner/orders"
              >
                Dükkân siparişleri
              </NavLink>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? ' active' : ''}`
                }
                end
                to="/owner/orders/history"
              >
                Sipariş geçmişi
              </NavLink>
            </>
          )}
          {token && role === 'ADMIN' && (
            <>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? ' active' : ''}`
                }
                to="/admin"
              >
                Yönetim
              </NavLink>
            </>
          )}
          {token && role === 'CUSTOMER' && (
            <>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? ' active' : ''}`
                }
                to="/history"
              >
                Siparişlerim
              </NavLink>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? ' active' : ''}`
                }
                to="/favorites"
              >
                Favorilerim
              </NavLink>
              <NavLink
                className={({ isActive }) =>
                  `nav-link${isActive ? ' active' : ''}`
                }
                to="/subscription"
              >
                Abonelik
              </NavLink>
            </>
          )}
        </nav>
        <div className="user-menu" ref={userMenuRef}>
          <button
            aria-expanded={userMenuOpen}
            aria-haspopup="menu"
            aria-label="Kullanıcı menüsünü aç"
            className="user-menu-trigger"
            onClick={() => setUserMenuOpen((open) => !open)}
            type="button"
          >
            <svg
              aria-hidden="true"
              fill="none"
              height="21"
              viewBox="0 0 24 24"
              width="21"
            >
              <circle cx="12" cy="8" r="3.5" />
              <path d="M4.75 20c.7-3.5 3.25-5.25 7.25-5.25s6.55 1.75 7.25 5.25" />
            </svg>
            <span className="user-menu-label">Hesap</span>
          </button>
          {userMenuOpen && (
            <div className="user-menu-popover" role="menu">
              {token ? (
                <>
                  <Link
                    onClick={() => setUserMenuOpen(false)}
                    role="menuitem"
                    to="/profile"
                  >
                    Profilim
                  </Link>
                  {role === 'CUSTOMER' && (
                    <Link
                      onClick={() => setUserMenuOpen(false)}
                      role="menuitem"
                      to="/favorites"
                    >
                      Favori siparişlerim
                    </Link>
                  )}
                  <button
                    onClick={() => {
                      setUserMenuOpen(false)
                      signOut()
                    }}
                    role="menuitem"
                    type="button"
                  >
                    Çıkış yap
                  </button>
                </>
              ) : (
                <>
                  <Link
                    onClick={() => setUserMenuOpen(false)}
                    role="menuitem"
                    to="/login"
                  >
                    Giriş yap
                  </Link>
                  <Link
                    onClick={() => setUserMenuOpen(false)}
                    role="menuitem"
                    to="/register"
                  >
                    Kayıt ol
                  </Link>
                </>
              )}
            </div>
          )}
        </div>
      </header>
      <main className="page-container">
        <Outlet />
      </main>
      <footer className="site-footer">KahveCell • Demo</footer>
    </div>
  )
}

function AuthLayout() {
  return (
    <main className="auth-page">
      <Outlet />
    </main>
  )
}

function RequireAuth() {
  const { token } = useAuth()
  return token ? <Outlet /> : <Navigate to="/login" replace />
}

function RequireRole({
  requiredRole,
  loadingMessage,
}: {
  requiredRole: UserProfile['role']
  loadingMessage: string
}) {
  const { token } = useAuth()
  const [access, setAccess] = useState<RoleAccess | null>(null)
  const [retryVersion, setRetryVersion] = useState(0)

  useEffect(() => {
    if (!token) {
      return
    }

    let active = true
    apiRequest<UserProfile>('/auth/me')
      .then((profile) => {
        if (active) {
          setAccess({
            token,
            status: profile.role === requiredRole ? 'allowed' : 'forbidden',
          })
        }
      })
      .catch((requestError: unknown) => {
        if (active) {
          setAccess({
            token,
            status:
              requestError instanceof ApiError && requestError.status === 401
                ? 'unauthorized'
                : 'failed',
            message:
              requestError instanceof Error
                ? requestError.message
                : 'Kullanıcı rolü doğrulanamadı.',
          })
        }
      })

    return () => {
      active = false
    }
  }, [requiredRole, retryVersion, token])

  if (!token) {
    return <Navigate to="/login" replace />
  }

  const currentAccess = access?.token === token ? access : null
  if (!currentAccess) {
    return <LoadingState message={loadingMessage} />
  }
  if (currentAccess.status === 'allowed') {
    return <Outlet />
  }
  if (currentAccess.status === 'forbidden') {
    return <Navigate to="/" replace />
  }
  if (currentAccess.status === 'unauthorized') {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="page-stack">
      <ErrorState
        message={currentAccess.message ?? 'Kullanıcı rolü doğrulanamadı.'}
        onRetry={() => {
          setAccess(null)
          setRetryVersion((version) => version + 1)
        }}
        title="Yetki doğrulanamadı"
      />
      <Link to="/">Ana sayfaya dön</Link>
    </div>
  )
}

function RequireShopOwner() {
  return (
    <RequireRole
      loadingMessage="Dükkân sahibi yetkisi kontrol ediliyor…"
      requiredRole="SHOP_OWNER"
    />
  )
}

function RequireAdmin() {
  return (
    <RequireRole
      loadingMessage="Yönetici yetkisi kontrol ediliyor…"
      requiredRole="ADMIN"
    />
  )
}

function NotFoundPage() {
  return (
    <section className="panel">
      <h1>Sayfa bulunamadı</h1>
      <Link to="/shops">Dükkânlara dön</Link>
    </section>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<AuthLayout />}>
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route path="otp" element={<OtpPage />} />
      </Route>
      <Route element={<AppLayout />}>
        <Route index element={<LandingPage />} />
        <Route path="shops" element={<HomePage />} />
        <Route path="shops/:shopId" element={<ShopDetailPage />} />
        <Route element={<RequireAuth />}>
          <Route path="profile" element={<ProfilePage />} />
          <Route path="orders/new" element={<OrderPage />} />
          <Route path="qr" element={<QrPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="subscription" element={<SubscriptionPage />} />
          <Route path="favorites" element={<FavoritesPage />} />
        </Route>
        <Route element={<RequireShopOwner />}>
          <Route path="owner/shop" element={<ShopOwnerShopPage />} />
          <Route path="owner/orders" element={<ShopOwnerOrdersPage />} />
          <Route
            path="owner/orders/history"
            element={<ShopOwnerOrderHistoryPage />}
          />
        </Route>
        <Route element={<RequireAdmin />}>
          <Route path="admin" element={<AdminPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
