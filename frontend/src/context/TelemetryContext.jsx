import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import { api, WS_URL } from '../api'

const TelemetryContext = createContext(null)

const TELEMETRY_POLL_MS = 30000

function telemetryToHistoryPoint(t) {
  if (!t) return null
  const soil = t.soil_sensors || t.soil_pct || []
  const pct = Array.isArray(soil) && soil[0]?.pct !== undefined
    ? soil.map(s => s.pct)
    : soil
  return {
    timestamp: t.last_update || t.timestamp,
    temperature: t.temperature ?? null,
    humidity: t.humidity ?? null,
    pressure: t.pressure ?? null,
    soil_a1: pct[0] ?? null,
    soil_a2: pct[1] ?? null,
    soil_a3: pct[2] ?? null,
    soil_b1: pct[3] ?? null,
    soil_b2: pct[4] ?? null,
    soil_b3: pct[5] ?? null,
    fan_1: t.actuators?.fan_1 ?? false,
    fan_2: t.actuators?.fan_2 ?? false,
    humidifier_1: t.actuators?.humidifier_1 ?? false,
    humidifier_2: t.actuators?.humidifier_2 ?? false,
    pump: t.actuators?.pump ?? false,
  }
}

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
  const [telemetry, setTelemetry] = useState(null)
  const [history, setHistory] = useState([])
  const [historyHours, setHistoryHours] = useState(24)
  const [status, setStatus] = useState(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)
  const shouldReconnectRef = useRef(true)

  const fetchLatest = useCallback(async () => {
    try {
      const data = await api.getLatestTelemetry()
      setTelemetry(data)
    } catch (e) {
      console.error('Failed to fetch telemetry:', e)
    }
  }, [])

  const fetchHistory = useCallback(async (hours = historyHours) => {
    try {
      const data = await api.getTelemetryHistory(hours)
      setHistory(data)
    } catch (e) {
      console.error('Failed to fetch history:', e)
    }
  }, [historyHours])

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.getSystemStatus()
      setStatus(data)
    } catch (e) {
      console.error('Failed to fetch status:', e)
    }
  }, [])

  const connectWS = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
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
        } else if (message.type === 'config_update' || message.type === 'config_confirmed') {
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
    fetchLatest()
    fetchHistory()
    fetchStatus()
    connectWS()

    const poll = setInterval(() => {
      fetchLatest()
      fetchStatus()
    }, TELEMETRY_POLL_MS)

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
  }, [fetchLatest, fetchHistory, fetchStatus, connectWS])

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
