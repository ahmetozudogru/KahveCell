import { useState, type PropsWithChildren } from 'react'

import { AuthContext } from './auth-context'
import type { UserRole } from '../types/api'

const TOKEN_KEY = 'kahvecell_access_token'
const ROLE_KEY = 'kahvecell_user_role'

function readStoredRole(): UserRole | null {
  const role = localStorage.getItem(ROLE_KEY)
  return role === 'CUSTOMER' || role === 'SHOP_OWNER' || role === 'ADMIN'
    ? role
    : null
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY),
  )
  const [role, setRole] = useState<UserRole | null>(readStoredRole)

  function signIn(accessToken: string, userRole: UserRole) {
    localStorage.setItem(TOKEN_KEY, accessToken)
    localStorage.setItem(ROLE_KEY, userRole)
    setToken(accessToken)
    setRole(userRole)
  }

  function signOut() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(ROLE_KEY)
    setToken(null)
    setRole(null)
  }

  return (
    <AuthContext.Provider value={{ token, role, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}
