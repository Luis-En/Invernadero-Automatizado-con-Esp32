import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import { useAuth } from './AuthContext'

const WeatherContext = createContext(null)

// The forecast changes slowly and the free OpenWeather tier has a daily quota,
// so a 10 minute poll is plenty. The backend caches for the same window.
const WEATHER_POLL_MS = 10 * 60 * 1000
const WEATHER_HOURS = 48

export function WeatherProvider({ children }) {
  const { user } = useAuth()
  const [weather, setWeather] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchWeather = useCallback(async () => {
    if (!user) return
    setLoading(true)
    try {
      const data = await api.getWeather(WEATHER_HOURS)
      setWeather(data)
      setError('')
    } catch (e) {
      setError(e.message || 'No se pudo cargar el clima')
    } finally {
      setLoading(false)
    }
  }, [user])

  useEffect(() => {
    if (!user) {
      setWeather(null)
      setError('')
      return
    }
    fetchWeather()
    const poll = setInterval(fetchWeather, WEATHER_POLL_MS)
    return () => clearInterval(poll)
  }, [user, fetchWeather])

  const value = { weather, loading, error, refresh: fetchWeather }

  return (
    <WeatherContext.Provider value={value}>
      {children}
    </WeatherContext.Provider>
  )
}

export function useWeather() {
  const context = useContext(WeatherContext)
  if (!context) {
    throw new Error('useWeather must be used within WeatherProvider')
  }
  return context
}
