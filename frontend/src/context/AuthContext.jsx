import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../api'

const AuthContext = createContext(null)

// Username/role only: never a credential. It lets the installed PWA render the
// last known session while the network (not the cookie) is unavailable.
const LAST_USER_KEY = 'greenhouse-last-user'

function readLastUser() {
  try {
    const raw = localStorage.getItem(LAST_USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function rememberUser(user) {
  try {
    if (user) {
      localStorage.setItem(
        LAST_USER_KEY,
        JSON.stringify({ id: user.id, username: user.username, role: user.role })
      )
    } else {
      localStorage.removeItem(LAST_USER_KEY)
    }
  } catch {
    /* storage disabled: the app still works online */
  }
}

function isNetworkFailure(error) {
  const message = error?.message || ''
  return (
    message.includes('No se pudo conectar') ||
    message.includes('tardó demasiado') ||
    message.includes('Failed to fetch')
  )
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [authOffline, setAuthOffline] = useState(false)
  const mounted = useRef(true)
  const checked = useRef(false)

  const checkAuth = useCallback(async () => {
    // Only the first check shows the full-screen "Comprobando sesión" state;
    // a reconnect re-check must not unmount the page the user is reading.
    if (!checked.current) setLoading(true)
    try {
      const userData = await api.me({ skipAuthRedirect: true })
      if (!mounted.current) return
      setUser(userData)
      setAuthOffline(false)
      rememberUser(userData)
    } catch (error) {
      if (!mounted.current) return
      if (isNetworkFailure(error)) {
        // Keep the PWA usable when the server or the link is down. The
        // HttpOnly cookie is untouched and is re-validated on reconnect.
        setUser(readLastUser())
        setAuthOffline(true)
      } else {
        setUser(null)
        setAuthOffline(false)
        rememberUser(null)
      }
    } finally {
      checked.current = true
      if (mounted.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    checkAuth()
    const onOnline = () => checkAuth()
    window.addEventListener('online', onOnline)
    return () => {
      mounted.current = false
      window.removeEventListener('online', onOnline)
    }
  }, [checkAuth])

  const login = useCallback(async (username, password) => {
    const data = await api.login(username, password)
    // The server also sets the HttpOnly session cookie; do not persist the
    // token from the response in localStorage.
    api.setToken(null)
    setUser(data.user)
    setAuthOffline(false)
    rememberUser(data.user)
    return data
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } catch {
      // Clearing the local state is still correct if the server is offline;
      // the cookie expires on its own.
    }
    api.setToken(null)
    setUser(null)
    setAuthOffline(false)
    rememberUser(null)
  }, [])

  const register = useCallback(async (data) => {
    return api.register(data)
  }, [])

  const value = {
    user,
    login,
    logout,
    register,
    loading,
    authOffline,
    refreshAuth: checkAuth,
    isAdmin: user?.role === 'admin',
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
