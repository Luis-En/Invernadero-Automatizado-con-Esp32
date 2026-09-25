import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { api } from '../api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem('token')
      if (token) {
        api.setToken(token)
        try {
          const userData = await api.me()
          setUser(userData)
        } catch {
          api.setToken(null)
        }
      }
      setLoading(false)
    }
    initAuth()
  }, [])

  const login = useCallback(async (username, password) => {
    const data = await api.login(username, password)
    api.setToken(data.access_token)
    setUser(data.user)
    return data
  }, [])

  const logout = useCallback(() => {
    api.setToken(null)
    setUser(null)
  }, [])

  const register = useCallback(async (data) => {
    return api.register(data)
  }, [])

  const value = { user, login, logout, register, loading, isAdmin: user?.role === 'admin' }

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