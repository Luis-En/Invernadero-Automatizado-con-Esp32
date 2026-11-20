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
    soil_a1: adc[0] ?? null,
    soil_a2: adc[1] ?? null,
    soil_a3: adc[2] ?? null,
    soil_b1: adc[3] ?? null,
    soil_b2: adc[4] ?? null,
    soil_b3: adc[5] ?? null,
    fan_1: data.fan_1_state ?? false,
    fan_2: data.fan_2_state ?? false,
    humidifier_1: data.humidifier_1_state ?? false,
    pump: data.pump_state ?? false,
  }
}

// The admin WebSocket sends the raw device payload (fan_1_state, soil_pct…);
// the REST snapshot exposes nested actuators/soil_sensors. Normalize both so
// every admin sees actuator and sensor changes without waiting for the poll.
function mergeWsTelemetry(previous, data) {
  const next = { ...(previous || {}), ...data }
  const actuatorData =
    data.actuators ||
    (data.fan_1_state !== undefined
      ? {
          fan_1: Boolean(data.fan_1_state),
          fan_2: Boolean(data.fan_2_state),
          humidifier_1: Boolean(data.humidifier_1_state),
          pump: Boolean(data.pump_state),
        }
      : null)
  if (actuatorData) next.actuators = actuatorData

  if (Array.isArray(data.soil_pct)) {
    const ids = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3']
    const ok = Array.isArray(data.soil_ok) ? data.soil_ok : []
    next.soil_sensors = ids.map((id, index) => ({
      id,
      pct: data.soil_pct[index] ?? null,
      ok: index < ok.length ? Boolean(ok[index]) : false,
      row: id[0],
    }))
    const valid = next.soil_sensors.filter(
      sensor => sensor.ok && sensor.pct !== null && sensor.pct !== undefined
    )
    next.soil_avg_general = valid.length
      ? valid.reduce((sum, sensor) => sum + sensor.pct, 0) / valid.length
      : null
    const rowAverage = row => {
      const values = valid.filter(sensor => sensor.row === row).map(s => s.pct)
      return values.length
        ? values.reduce((sum, value) => sum + value, 0) / values.length
        : null
    }
    next.soil_avg_row_a = rowAverage('A')
    next.soil_avg_row_b = rowAverage('B')
  }

  if (data.timestamp && !data.last_update) next.last_update = data.timestamp
  return next
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
          setTelemetry(prev => mergeWsTelemetry(prev, message.data))
          const point = wsPayloadToHistoryPoint(message.data)
          setHistory(prev => [...prev.slice(-499), point])
        } else if (message.type === 'actuator_state') {
          const { actuator, state } = message.data || {}
          if (actuator) {
            setTelemetry(prev =>
              prev
                ? {
                    ...prev,
                    actuators: {
                      ...(prev.actuators || {}),
                      [actuator]: Boolean(state),
                    },
                  }
                : prev
            )
          }
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
