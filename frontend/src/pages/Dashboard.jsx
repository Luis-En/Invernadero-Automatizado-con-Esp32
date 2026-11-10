import { useState, useCallback, useEffect } from 'react'
import { useTelemetry } from '../context/TelemetryContext'
import { useAuth } from '../context/AuthContext'
import { SensorCard, ActuatorCard } from '../components/SensorCard'
import { AuthImage } from '../components/AuthImage'
import { WeatherSummary } from '../components/WeatherSummary'
import { IrrigationBanner } from '../components/IrrigationBanner'
import { MultiChart } from '../components/Charts'
import { api } from '../api'
import { format } from 'date-fns'
import { parseServerTime, formatServerTime } from '../utils/time'

export function Dashboard() {
  const { telemetry, history, status, error: telemetryError, refresh, historyHours, setTimeRange } = useTelemetry()
  const { isAdmin } = useAuth()
  const [actuatorLoading, setActuatorLoading] = useState(null)
  const [error, setError] = useState('')
  const [confirmed, setConfirmed] = useState({})
  const [latestPhoto, setLatestPhoto] = useState(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const photo = await api.getLatestPhoto()
        if (!cancelled) setLatestPhoto(photo)
      } catch {
        if (!cancelled) setLatestPhoto(null)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [status?.last_photo])

  const toggleActuator = useCallback(async (actuator, newState) => {
    if (!isAdmin) return
    setActuatorLoading(actuator)
    setError('')
    try {
      const ack = await api.adminControlActuator(actuator, newState)
      setConfirmed(previous => ({ ...previous, [actuator]: {
        state: ack.state, confirmedAt: Date.parse(ack.confirmed_at),
      } }))
      refresh()
    } catch (e) {
      console.error('Failed to toggle actuator:', e)
      setError(e.message || 'No se pudo enviar el comando')
    } finally {
      setActuatorLoading(null)
    }
  }, [isAdmin, refresh])

  const actuatorState = name => {
    const ack = confirmed[name]
    const telemetryAt = parseServerTime(telemetry?.last_update || telemetry?.timestamp)?.getTime() || 0
    return ack && !(telemetryAt > ack.confirmedAt)
      ? ack.state : Boolean(telemetry?.actuators?.[name])
  }

  const soilOnThreshold = status?.soil_threshold_pct ?? 35

  const getSoilStatus = (pct, ok) => {
    if (!ok || pct === null || pct === undefined) return 'offline'
    // Use the configured trigger instead of a hard-coded 30/40 split so the
    // sensor colours, the banner and the push alert never disagree.
    if (pct <= soilOnThreshold - 10) return 'critical'
    if (pct < soilOnThreshold) return 'warning'
    return 'normal'
  }

  const getTempStatus = (temp) => {
    if (temp === null) return 'offline'
    if (temp > 32) return 'critical'
    if (temp > 29) return 'warning'
    return 'normal'
  }

  const getHumidityStatus = (hum) => {
    if (hum === null || hum === undefined) return 'offline'
    if (hum < 40 || hum > 90) return 'critical'
    if (hum < 50 || hum > 85) return 'warning'
    return 'normal'
  }

  const metricTone = value =>
    value === 'critical' ? ' critical' : value === 'warning' ? ' warning' : value === 'offline' ? ' muted' : ''

  if (!telemetry) {
    if (telemetryError) {
      return (
        <div className="card" style={{ textAlign: 'center', padding: '2rem' }}>
          <div className="alert alert-warning" role="alert" style={{ textAlign: 'left' }}>
            {telemetryError}
          </div>
          <button onClick={refresh} className="btn btn-primary" type="button">
            Reintentar
          </button>
        </div>
      )
    }
    return (
      <div className="loading-state" role="status" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <p>Cargando datos del invernadero…</p>
        <button onClick={refresh} className="btn btn-primary" type="button">
          Reintentar
        </button>
      </div>
    )
  }

  const soilSensors = telemetry.soil_sensors || []

  const tempStatus = getTempStatus(telemetry.temperature)
  const humidityStatus = getHumidityStatus(telemetry.humidity)

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p style={{ color: 'var(--color-text-muted)', marginTop: '0.25rem' }}>
            Última actualización: {formatServerTime(telemetry.last_update, d => format(d, 'HH:mm:ss'))}
            {telemetry.sequence && <span style={{ marginLeft: '1rem', fontSize: '0.875rem' }}>Sec: {telemetry.sequence}</span>}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }} className="page-actions">
          <select
            value={historyHours}
            onChange={e => setTimeRange(Number(e.target.value))}
            className="form-control"
            aria-label="Rango de historial"
            style={{ width: 'auto', padding: '0.375rem 2rem 0.375rem 0.75rem' }}
          >
            <option value={1}>Última hora</option>
            <option value={6}>Últimas 6h</option>
            <option value={12}>Últimas 12h</option>
            <option value={24}>Último día</option>
            <option value={168}>Última semana</option>
          </select>
          <button onClick={refresh} className="btn btn-secondary" type="button">
            🔄 Actualizar
          </button>
        </div>
      </div>

      <IrrigationBanner status={status} isAdmin={isAdmin} />

      {error && (
        <div className="alert alert-critical" role="alert">
          {error}
        </div>
      )}
      {telemetryError && (
        <div className="alert alert-warning" role="status">
          <span style={{ flex: 1 }}>{telemetryError}</span>
          <button onClick={refresh} className="btn btn-secondary btn-sm">
            Reintentar
          </button>
        </div>
      )}

      <div className="stat-grid" style={{ marginBottom: '1.5rem' }}>
        <div className="card">
          <div className="card-header">🌡️ Temperatura</div>
          <div className="card-body" style={{ textAlign: 'center' }}>
            <div className={`metric-value${metricTone(tempStatus)}`}>
              {telemetry.temperature !== null ? telemetry.temperature.toFixed(1) : '—'}
              <span className="metric-unit">°C</span>
            </div>
            <div className="metric-secondary">
              {telemetry.pressure !== null ? `${telemetry.pressure.toFixed(1)} hPa` : ''}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">💧 Humedad Ambiental</div>
          <div className="card-body" style={{ textAlign: 'center' }}>
            <div className={`metric-value${metricTone(humidityStatus)}`}>
              {telemetry.humidity !== null ? telemetry.humidity.toFixed(1) : '—'}
              <span className="metric-unit">%</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">🌿 Suelo Fila A (prom.)</div>
          <div className="card-body" style={{ textAlign: 'center' }}>
            <div
              className={`metric-value${
                telemetry.soil_avg_row_a !== null
                  ? telemetry.soil_avg_row_a < soilOnThreshold
                    ? ' warning'
                    : ''
                  : ' muted'
              }`}
            >
              {telemetry.soil_avg_row_a !== null ? telemetry.soil_avg_row_a.toFixed(1) : '—'}
              <span className="metric-unit">%</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">🌿 Suelo Fila B (prom.)</div>
          <div className="card-body" style={{ textAlign: 'center' }}>
            <div
              className={`metric-value${
                telemetry.soil_avg_row_b !== null
                  ? telemetry.soil_avg_row_b < soilOnThreshold
                    ? ' warning'
                    : ''
                  : ' muted'
              }`}
            >
              {telemetry.soil_avg_row_b !== null ? telemetry.soil_avg_row_b.toFixed(1) : '—'}
              <span className="metric-unit">%</span>
            </div>
          </div>
        </div>
      </div>

      <WeatherSummary />

      <div className="grid grid-6" style={{ marginBottom: '1.5rem' }}>
        {soilSensors.map(sensor => (
          <SensorCard
            key={sensor.id}
            label={`Sensor ${sensor.id}`}
            value={sensor.pct}
            unit="%"
            status={getSoilStatus(sensor.pct, sensor.ok)}
            row={sensor.row}
            id={sensor.id}
          />
        ))}
      </div>

      <div className="grid grid-4" style={{ marginBottom: '1.5rem' }}>
        {[
          { name: 'Ventilador 1', icon: '💨', actuator: 'fan_1' },
          { name: 'Ventilador 2', icon: '💨', actuator: 'fan_2' },
          { name: 'Humidificador 1', icon: '🌫️', actuator: 'humidifier_1' },
          { name: 'Humidificador 2', icon: '🌫️', actuator: 'humidifier_2' },
        ].map(a => (
          <ActuatorCard
            key={a.actuator}
            name={a.name}
            icon={a.icon}
            state={actuatorState(a.actuator)}
            onToggle={() => toggleActuator(a.actuator, !actuatorState(a.actuator))}
            disabled={!isAdmin || actuatorLoading !== null}
            loading={actuatorLoading === a.actuator}
          />
        ))}

        <ActuatorCard
          name="Bomba de Riego"
          icon="🚿"
          state={actuatorState('pump')}
          onToggle={() => toggleActuator('pump', !actuatorState('pump'))}
          disabled={!isAdmin || actuatorLoading !== null || (!status?.irrigation_enabled && !actuatorState('pump'))}
          loading={actuatorLoading === 'pump'}
        />

        <div className="actuator-card" style={{ justifyContent: 'center' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
            <div className={`badge ${status?.irrigation_enabled ? 'badge-on' : 'badge-off'}`} style={{ fontSize: '0.875rem', padding: '0.5rem 1rem' }}>
              {status?.irrigation_enabled ? 'RIEGO HABILITADO' : 'RIEGO DESHABILITADO'}
            </div>
            <small style={{ color: 'var(--color-text-muted)' }}>
              {status?.irrigation_enabled ? 'Automático según humedad suelo' : 'Configurar fuente de agua primero'}
            </small>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">📸 Última Fotografía</div>
        <div className="card-body">
          <div style={{ textAlign: 'center' }}>
            {latestPhoto ? (
              <>
                <AuthImage
                  key={status?.last_photo || latestPhoto.id}
                  latest
                  alt="Última foto del cultivo"
                  style={{
                    maxWidth: '100%',
                    maxHeight: '400px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--color-border)',
                    boxShadow: 'var(--shadow-sm)',
                  }}
                />
                <p style={{ marginTop: '0.5rem', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                  Tomada: {formatServerTime(latestPhoto.timestamp, d => format(d, 'dd/MM/yyyy HH:mm'))}
                </p>
              </>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px', color: 'var(--color-text-muted)' }}>
                No hay fotos disponibles
              </div>
            )}
          </div>
        </div>
      </div>

      <MultiChart data={history} hours={historyHours} />
    </div>
  )
}
