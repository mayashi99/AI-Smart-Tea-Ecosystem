import { useCallback, useEffect, useMemo, useState } from 'react'
import { AuthContext } from './auth-context'
import { endpoints, postJSON } from '../services/api'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    fetch(endpoints.currentUser, { credentials: 'include' })
      .then(async (response) => {
        if (response.status === 401) return null
        const payload = await response.json()
        if (!response.ok) throw new Error(payload.detail || 'Could not verify sign-in')
        return payload
      })
      .then((account) => { if (active) setUser(account) })
      .catch(() => { if (active) setUser(null) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const logout = useCallback(async () => {
    await postJSON(endpoints.logout, {}, 'Could not sign out')
    setUser(null)
  }, [])
  const value = useMemo(() => ({ user, loading, logout }), [user, loading, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
