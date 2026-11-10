import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from './AuthContext'

const TelemetryContext = createContext(null)

const TELEMETRY_POLL_MS = 30000
const PUBLIC_POLL_MS = 60000

function wsPayloadToHistoryPoint(data) {
  const adc = data.soil_pct || []
  return {
    timestamp: data.timestamp,
    temperature: data.temperature ?? null,
    humidity: data.humidity ?? null,
    pressure: data.pressure ?? null,
    soil_a1: adc[0] ?? null,
    soil_a2: adc[1] ?? null,
    soil_a3: adc[2] ?? null,
    soil_b1: adc[3] ?? null,
    soil_b2: adc[4] ?? null,
    soil_b3: adc[5] ?? null,
    fan_1: data.fan_1_state ?? false,
    fan_2: data.fan_2_state ?? false,
    humidifier_1: data.humidifier_1_state ?? false,
    humidifier_2: data.humidifier_2_state ?? false,
    pump: data.pump_state ?? false,
  }
}

export function TelemetryProvider({ children }) {
  const { user } = useAuth()
  const location = useLocation()
  // On public pages the page has its own live feed. The admin poll is only
  // needed for the alert bell and the local notification fallback, so keep it
  // lightweight instead of opening a second WebSocket.
  const adminArea = location.pathname.startsWith('/admin')
  const [telemetry, setTelemetry] = useState(null)
  const [history, setHistory] = useState([])
  const [historyHours, setHistoryHours] = useState(24)
  const [status, setStatus] = useState(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState('')
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)
  const shouldReconnectRef = useRef(true)
  const historyHoursRef = useRef(historyHours)
  historyHoursRef.current = historyHours

  const fetchLatest = useCallback(async () => {
    try {
      const data = await api.getLatestTelemetry()
      setTelemetry(data)
      setError('')
    } catch (e) {
      setError(e.message || 'No se pudo cargar la telemetría')
    }
  }, [])

  const fetchHistory = useCallback(async (hours) => {
    const target = hours ?? historyHoursRef.current
    try {
      const data = await api.getTelemetryHistory(target)
      setHistory(data)
    } catch (e) {
      setError(e.message || 'No se pudo cargar el historial')
    }
  }, [])

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.getSystemStatus()
      setStatus(data)
    } catch (e) {
      setError(e.message || 'No se pudo cargar el estado del sistema')
    }
  }, [])

  const connectWS = useCallback(() => {
    // The WebSocket authenticates with the HttpOnly session cookie.
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(api.getWsUrl())
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current)
        reconnectRef.current = null
      }
    }

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'telemetry') {
          setTelemetry(prev => ({ ...(prev || {}), ...message.data }))
          const point = wsPayloadToHistoryPoint(message.data)
          setHistory(prev => [...prev.slice(-499), point])
        } else if (message.type === 'config_update' || message.type === 'config_confirmed' ||
                   message.type === 'event') {
          fetchLatest()
          fetchStatus()
        }
      } catch (e) {
        console.error('WS message error:', e)
      }
    }

    ws.onclose = () => {
      setConnected(false)
      if (shouldReconnectRef.current && !reconnectRef.current) {
        reconnectRef.current = setTimeout(() => {
          reconnectRef.current = null
          connectWS()
        }, 5000)
      }
    }

    ws.onerror = () => {
      if (ws.readyState !== WebSocket.CLOSED) {
        ws.close()
      }
    }
  }, [fetchLatest, fetchStatus])

  useEffect(() => {
    shouldReconnectRef.current = true

    if (!user) {
      setTelemetry(null)
      setHistory([])
      setStatus(null)
      setConnected(false)
      return () => {
        shouldReconnectRef.current = false
      }
    }

    fetchLatest()
    fetchStatus()
    if (adminArea) {
      fetchHistory()
      connectWS()
    }

    const poll = setInterval(() => {
      fetchLatest()
      fetchStatus()
    }, adminArea ? TELEMETRY_POLL_MS : PUBLIC_POLL_MS)

    return () => {
      shouldReconnectRef.current = false
      clearInterval(poll)
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current)
        reconnectRef.current = null
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [user, adminArea, fetchLatest, fetchHistory, fetchStatus, connectWS])

  const setTimeRange = useCallback((hours) => {
    setHistoryHours(hours)
    fetchHistory(hours)
  }, [fetchHistory])

  const value = {
    telemetry,
    history,
    historyHours,
    status,
    connected,
    error,
    setTimeRange,
    refresh: () => {
      fetchLatest()
      fetchStatus()
    },
  }

  return (
    <TelemetryContext.Provider value={value}>
      {children}
    </TelemetryContext.Provider>
  )
}

export function useTelemetry() {
  const context = useContext(TelemetryContext)
  if (!context) {
    throw new Error('useTelemetry must be used within TelemetryProvider')
  }
  return context
}
