import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'

const POLL_MS = 30000

function publicWsUrl() {
  if (typeof window === 'undefined') return '/api/public/ws'
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/public/ws`
}

function pointFromTelemetry(data) {
  const sensors = data.soil_sensors || []
  const byId = Object.fromEntries(sensors.map(sensor => [sensor.id, sensor.pct]))
  return {
    timestamp: data.timestamp,
    temperature: data.temperature ?? null,
    humidity: data.humidity ?? null,
    pressure: data.pressure ?? null,
    soil_a1: byId.A1 ?? null,
    soil_a2: byId.A2 ?? null,
    soil_a3: byId.A3 ?? null,
    soil_b1: byId.B1 ?? null,
    soil_b2: byId.B2 ?? null,
    soil_b3: byId.B3 ?? null,
  }
}

export function usePublicTelemetry() {
  const [telemetry, setTelemetry] = useState(null)
  const [history, setHistory] = useState([])
  const [hours, setHours] = useState(24)
  const [connected, setConnected] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)
  const hoursRef = useRef(hours)
  hoursRef.current = hours

  const fetchLatest = useCallback(async () => {
    try {
      const data = await api.getPublicTelemetry()
      setTelemetry(data)
      setError('')
    } catch (e) {
      setError(e.message || 'No se pudo cargar la telemetría pública')
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchHistory = useCallback(async (targetHours) => {
    try {
      const data = await api.getPublicTelemetryHistory(
        targetHours ?? hoursRef.current
      )
      setHistory(data)
    } catch {
      // The latest-value card is still useful if history fails.
    }
  }, [])

  const connect = useCallback(() => {
    if (typeof window === 'undefined' || !window.WebSocket) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    const ws = new WebSocket(publicWsUrl())
    wsRef.current = ws
    ws.onopen = () => {
      setConnected(true)
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current)
        reconnectRef.current = null
      }
    }
    ws.onmessage = event => {
      try {
        const message = JSON.parse(event.data)
        if (message.type !== 'telemetry') return
        setTelemetry(previous => ({ ...(previous || {}), ...message.data }))
        setHistory(previous => [
          ...previous.slice(-499),
          pointFromTelemetry(message.data),
        ])
      } catch {
        // Ignore malformed public frames.
      }
    }
    ws.onclose = () => {
      setConnected(false)
      if (!reconnectRef.current) {
        reconnectRef.current = setTimeout(() => {
          reconnectRef.current = null
          connect()
        }, 5000)
      }
    }
    ws.onerror = () => {
      if (ws.readyState !== WebSocket.CLOSED) ws.close()
    }
  }, [])

  useEffect(() => {
    fetchLatest()
    fetchHistory()
    connect()
    const poll = setInterval(() => {
      fetchLatest()
    }, POLL_MS)
    return () => {
      clearInterval(poll)
      if (reconnectRef.current) clearTimeout(reconnectRef.current)
      reconnectRef.current = null
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect, fetchHistory, fetchLatest])

  const setTimeRange = useCallback(
    value => {
      setHours(value)
      fetchHistory(value)
    },
    [fetchHistory]
  )

  return {
    telemetry,
    history,
    hours,
    connected,
    loading,
    error,
    setTimeRange,
    refresh: fetchLatest,
  }
}
