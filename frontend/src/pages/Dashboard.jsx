import { useState, useCallback, useEffect } from 'react'
import { useTelemetry } from '../context/TelemetryContext'
import { useAuth } from '../context/AuthContext'
import { SensorCard, ActuatorCard } from '../components/SensorCard'
import { MultiChart } from '../components/Charts'
import { api } from '../api'
import { format } from 'date-fns'

export function Dashboard() {
  const { telemetry, history, status, connected, refresh, historyHours, setTimeRange } = useTelemetry()
  const { isAdmin } = useAuth()
  const [actuatorLoading, setActuatorLoading] = useState(null)
  const [error, setError] = useState('')
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
    return () => { cancelled = true }
  }, [status?.last_photo])

  const toggleActuator = useCallback(async (actuator, newState) => {
    if (!isAdmin) return
    setActuatorLoading(actuator)
    setError('')
    try {
      const active = await api.getActiveConfig()
      const current = active?.config_json || {}
      const manual = { ...(current.manual_override || {}), [actuator]: newState }
      await api.applyConfig({
        config_json: { ...current, manual_override: manual },
        crop_id: active?.crop_id ?? null,
      })
      refresh()
    } catch (e) {
      console.error('Failed to toggle actuator:', e)
      setError(e.message || 'No se pudo enviar el comando')
    } finally {
      setActuatorLoading(null)
    }
  }, [isAdmin, refresh])

  const getSoilStatus = (pct, ok) => {
    if (!ok || pct === null) return 'offline'
    if (pct < 30) return 'critical'
    if (pct < 40) return 'warning'
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

  if (!telemetry) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
        <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📡</div>
        <p style={{ color: 'var(--color-text-muted)' }}>Cargando datos del invernadero...</p>
        <button onClick={refresh} className="btn btn-primary" style={{ marginTop: '1rem' }}>Reintentar</button>
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
            Última actualización: {telemetry.last_update ? format(new Date(telemetry.last_update), 'HH:mm:ss') : '—'}
            {telemetry.sequence && <span style={{ marginLeft: '1rem', fontSize: '0.875rem' }}>Sec: {telemetry.sequence}</span>}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <select
            value={historyHours}
            onChange={e => setTimeRange(Number(e.target.value))}
            className="form-control"
            style={{ width: 'auto', padding: '0.375rem 2rem 0.375rem 0.75rem' }}
          >
            <option value={1}>Última hora</option>
            <option value={6}>Últimas 6h</option>
            <option value={12}>Últimas 12h</option>
            <option value={24}>Último día</option>
            <option value={168}>Última semana</option>
          </select>
          <button onClick={refresh} className="btn btn-secondary" disabled={!connected}>
            🔄 Actualizar
          </button>
        </div>
      </div>

      {error && <div className="alert alert-critical">{error}</div>}

      <div className="grid grid-4" style={{ marginBottom: '1.5rem' }}>
        <div className="card">
          <div className="card-header">🌡️ Temperatura</div>
          <div className="card-body" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '3rem', fontWeight: 700, color: tempStatus === 'critical' ? 'var(--color-critical)' : tempStatus === 'warning' ? 'var(--color-warning)' : 'var(--color-text)' }}>
              {telemetry.temperature !== null ? telemetry.temperature.toFixed(1) : '—'}
              <span style={{ fontSize: '1.5rem', fontWeight: 400, color: 'var(--color-text-muted)' }}>°C</span>
            </div>
            <div style={{ marginTop: '0.5rem', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
              {telemetry.pressure !== null ? `${telemetry.pressure.toFixed(1)} hPa` : ''}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">💧 Humedad Ambiental</div>
          <div className="card-body" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '3rem', fontWeight: 700, color: humidityStatus === 'critical' ? 'var(--color-critical)' : humidityStatus === 'warning' ? 'var(--color-warning)' : 'var(--color-text)' }}>
              {telemetry.humidity !== null ? telemetry.humidity.toFixed(1) : '—'}
              <span style={{ fontSize: '1.5rem', fontWeight: 400, color: 'var(--color-text-muted)' }}>%</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">🌿 Suelo Fila A (prom.)</div>
          <div className="card-body" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '3rem', fontWeight: 700, color: telemetry.soil_avg_row_a !== null ? (telemetry.soil_avg_row_a < 35 ? 'var(--color-warning)' : 'var(--color-text)') : 'var(--color-text-muted)' }}>
              {telemetry.soil_avg_row_a !== null ? telemetry.soil_avg_row_a.toFixed(1) : '—'}
              <span style={{ fontSize: '1.5rem', fontWeight: 400, color: 'var(--color-text-muted)' }}>%</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">🌿 Suelo Fila B (prom.)</div>
          <div className="card-body" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '3rem', fontWeight: 700, color: telemetry.soil_avg_row_b !== null ? (telemetry.soil_avg_row_b < 35 ? 'var(--color-warning)' : 'var(--color-text)') : 'var(--color-text-muted)' }}>
              {telemetry.soil_avg_row_b !== null ? telemetry.soil_avg_row_b.toFixed(1) : '—'}
              <span style={{ fontSize: '1.5rem', fontWeight: 400, color: 'var(--color-text-muted)' }}>%</span>
            </div>
          </div>
        </div>
      </div>

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
            state={telemetry.actuators?.[a.actuator]}
            onToggle={() => toggleActuator(a.actuator, !telemetry.actuators?.[a.actuator])}
            disabled={!isAdmin}
            loading={actuatorLoading === a.actuator}
          />
        ))}

        <ActuatorCard
          name="Bomba de Riego"
          icon="🚿"
          state={telemetry.actuators?.pump}
          onToggle={() => toggleActuator('pump', !telemetry.actuators?.pump)}
          disabled={!isAdmin || !status?.irrigation_enabled}
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
                <img
                  src={`${api.getLatestPhotoFile()}?t=${encodeURIComponent(latestPhoto.timestamp)}`}
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
                  Tomada: {format(new Date(latestPhoto.timestamp), 'dd/MM/yyyy HH:mm')}
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