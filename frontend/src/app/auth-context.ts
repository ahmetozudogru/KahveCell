import { createContext } from 'react'

import type { UserRole } from '../types/api'

export interface AuthContextValue {
  token: string | null
  role: UserRole | null
  signIn: (token: string, role: UserRole) => void
  signOut: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)
