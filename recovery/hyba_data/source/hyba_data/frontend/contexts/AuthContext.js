'use client'

/**
 * AuthContext
 *
 * Security model:
 * - JWT is stored exclusively in an httpOnly, Secure, SameSite=Lax cookie
 *   set by the server-side /api/auth/login route.  It is never accessible
 *   to JavaScript, eliminating the XSS token-theft vector.
 * - On mount, the context calls /api/auth/me to validate the cookie-bound
 *   session server-side and hydrate the user object.
 * - Token expiry is enforced by the backend; a 401 from /api/auth/me clears
 *   local state and redirects to login.
 * - Rate limiting (5 attempts / 15 min per IP) is enforced server-side in
 *   /api/auth/login/route.js — the frontend does not duplicate this logic.
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react'

const AuthContext = createContext()

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  // ------------------------------------------------------------------
  // Session hydration — validate cookie-bound JWT on every mount
  // ------------------------------------------------------------------
  const checkAuth = useCallback(async () => {
    try {
      const res = await fetch('/api/auth/me', { credentials: 'same-origin' })
      if (res.ok) {
        const { user: me } = await res.json()
        setUser(me)
        setIsAuthenticated(true)
      } else {
        setUser(null)
        setIsAuthenticated(false)
      }
    } catch {
      setUser(null)
      setIsAuthenticated(false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  // ------------------------------------------------------------------
  // Login — credentials go to the BFF route which sets the httpOnly cookie
  // ------------------------------------------------------------------
  const login = async (email, password) => {
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ email, password }),
      })

      if (res.status === 429) {
        return { success: false, error: 'Too many login attempts. Please try again in 15 minutes.' }
      }

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        return { success: false, error: err.detail || 'Login failed. Please try again.' }
      }

      const { user: me } = await res.json()
      setUser(me)
      setIsAuthenticated(true)
      return { success: true, user: me }
    } catch {
      return { success: false, error: 'Login failed. Please try again.' }
    }
  }

  // ------------------------------------------------------------------
  // Logout — server clears the httpOnly cookie
  // ------------------------------------------------------------------
  const logout = async () => {
    try {
      await fetch('/api/auth/login', { method: 'DELETE', credentials: 'same-origin' })
    } catch {
      // Best-effort — clear local state regardless
    }
    setUser(null)
    setIsAuthenticated(false)
  }

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------

  /**
   * Returns headers for fetch calls that go through the Next.js API proxy.
   * The proxy reads the httpOnly cookie automatically — no Authorization
   * header needed for browser requests.
   */
  const getAuthHeaders = () => ({ 'Content-Type': 'application/json' })

  const isAdmin = () => user?.role === 'admin'

  const hasLimit = (type, value) => {
    if (!user || user.role === 'admin') return true
    switch (type) {
      case 'blocks':        return value <= user.max_blocks
      case 'dollar_value':  return value <= user.max_dollar_value
      case 'hashrate_ehs':  return value <= user.max_hashrate_ehs
      default:              return true
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated,
        isAdmin,
        hasLimit,
        login,
        logout,
        checkAuth,
        getAuthHeaders,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
