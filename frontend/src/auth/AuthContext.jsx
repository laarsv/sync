import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, ApiError } from '../lib/api'

const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const me = await api.get('/auth/me')
      setUser(me)
    } catch (e) {
      if (e instanceof ApiError) setUser(null)
      else setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const logout = useCallback(async () => {
    await api.post('/auth/logout')
    setUser(null)
  }, [])

  return (
    <AuthCtx.Provider value={{ user, loading, refresh, logout, setUser }}>
      {children}
    </AuthCtx.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthCtx)
  if (!ctx) throw new Error('useAuth muss innerhalb von <AuthProvider> stehen')
  return ctx
}
