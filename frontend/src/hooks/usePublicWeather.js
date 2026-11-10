import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'

const POLL_MS = 10 * 60 * 1000

export function usePublicWeather() {
  const [weather, setWeather] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getPublicWeather(48)
      setWeather(data)
      setError('')
    } catch (e) {
      setError(e.message || 'No se pudo cargar el clima público')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const poll = setInterval(refresh, POLL_MS)
    return () => clearInterval(poll)
  }, [refresh])

  return { weather, loading, error, refresh }
}
