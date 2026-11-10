import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { format } from 'date-fns'
import { usePublicTelemetry } from '../../hooks/usePublicTelemetry'
import { usePublicWeather } from '../../hooks/usePublicWeather'
import { SensorCard } from '../../components/SensorCard'
import { MultiChart } from '../../components/Charts'
import { WeatherIcon, rainStatus, percent, mm } from '../../components/WeatherIcon'
import { formatServerTime } from '../../utils/time'
import { api } from '../../api'

function soilStatus(pct, ok, threshold = 35) {
  if (!ok || pct === null || pct === undefined) return 'offline'
  if (pct <= threshold - 10) return 'critical'
  if (pct < threshold) return 'warning'
  return 'normal'
}

function fmtPct(value, digits = 0) {
  return value === null || value === undefined ? '—' : `${value.toFixed(digits)}%`
}

const ACTUATORS = [
  { key: 'fan_1', name: 'Ventilador 1', icon: '💨' },
  { key: 'fan_2', name: 'Ventilador 2', icon: '💨' },
  { key: 'humidifier_1', name: 'Humidificador 1', icon: '🌫️' },
  { key: 'humidifier_2', name: 'Humidificador 2', icon: '🌫️' },
  { key: 'pump', name: 'Bomba de riego', icon: '🚿' },
]

export function PublicDashboard() {
  const {
    telemetry,
    history,
    hours,
    connected,
    loading,
    error,
    setTimeRange,
    refresh,
  } = usePublicTelemetry()
  const { weather } = usePublicWeather()
  const [latestPhoto, setLatestPhoto] = useState(null)
  const [photoError, setPhotoError] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .getPublicLatestPhoto()
      .then(photo => {
        if (!cancelled) {
          setLatestPhoto(photo)
          setPhotoError(false)
        }
      })
      .catch(() => {
        if (!cancelled) setPhotoError(true)
      })
    return () => {
      cancelled = true
    }
  }, [telemetry?.last_update])

  if (loading && !telemetry) {
    return (
      <div className="loading-state" role="status" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <p>Cargando el invernadero…</p>
      </div>
    )
  }

  const soilThreshold = telemetry?.soil_threshold_pct ?? 35

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Invernadero en vivo</h1>
          <p className="page-subtitle">
            Última actualización:{' '}
            {formatServerTime(telemetry?.last_update, d => format(d, 'dd/MM HH:mm:ss'))}
            {' · '}
            {connected ? 'datos en tiempo real' : 'actualización periódica'}
            {telemetry?.active_crop ? ` · ${telemetry.active_crop}` : ''}
          </p>
        </div>
        <div className="page-actions">
          <label className="form-label" htmlFor="public-range" style={{ margin: 0 }}>
            Rango
          </label>
          <select
            id="public-range"
            className="form-control"
            value={hours}
            onChange={event => setTimeRange(Number(event.target.value))}
            style={{ width: 'auto' }}
          >
            <option value={1}>Última hora</option>
            <option value={6}>Últimas 6 h</option>
            <option value={24}>Último día</option>
            <option value={168}>Última semana</option>
          </select>
          <button type="button" className="btn btn-secondary" onClick={refresh}>
            🔄 Actualizar
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-warning" role="status">
          {error}
        </div>
      )}

      {telemetry?.irrigation_needed && (
        <div className="irrigation-banner" role="status">
          <span className="irrigation-banner-icon" aria-hidden="true">
            💧
          </span>
          <div className="irrigation-banner-body">
            <div className="irrigation-banner-title">Riego necesario</div>
            <p className="irrigation-banner-text">
              La humedad media del suelo es {fmtPct(telemetry.soil_avg_general)}.
              {telemetry.irrigation_enabled
                ? ' El riego automático está habilitado.'
                : ' El riego automático está deshabilitado.'}
              {telemetry.active_crop ? ` Cultivo activo: ${telemetry.active_crop}.` : ''}
            </p>
          </div>
        </div>
      )}

      {telemetry?.telemetry_stale && (
        <div className="alert alert-warning" role="status">
          El campo no está enviando datos recientes. Se muestra la última lectura
          disponible.
        </div>
      )}

      <div className="stat-grid" style={{ marginBottom: '1.5rem' }}>
        <div className="card">
          <div className="card-header">🌡️ Temperatura</div>
          <div className="card-body" style={{ textAlign: 'center' }}>
            <div className="metric-value">
              {telemetry?.temperature != null ? telemetry.temperature.toFixed(1) : '—'}
              <span className="metric-unit">°C</span>
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-header">💧 Humedad ambiental</div>
          <div className="card-body" style={{ textAlign: 'center' }}>
            <div className="metric-value">
              {telemetry?.humidity != null ? telemetry.humidity.toFixed(1) : '—'}
              <span className="metric-unit">%</span>
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-header">🌿 Suelo fila A</div>
          <div className="card-body" style={{ textAlign: 'center' }}>
            <div className="metric-value">
              {telemetry?.soil_avg_row_a != null
                ? telemetry.soil_avg_row_a.toFixed(1)
                : '—'}
              <span className="metric-unit">%</span>
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-header">🌿 Suelo fila B</div>
          <div className="card-body" style={{ textAlign: 'center' }}>
            <div className="metric-value">
              {telemetry?.soil_avg_row_b != null
                ? telemetry.soil_avg_row_b.toFixed(1)
                : '—'}
              <span className="metric-unit">%</span>
            </div>
          </div>
        </div>
      </div>

      {weather?.configured && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <div className="card-header">
            <span>🌤️ Clima exterior</span>
            <Link to="/clima" style={{ fontSize: '0.8rem' }}>
              Ver pronóstico completo →
            </Link>
          </div>
          <div className="card-body">
            <div className="weather-hero">
              <WeatherIcon icon={weather.current?.icon} size="3rem" />
              <div>
                <div className="weather-temp">
                  {weather.current?.temperature != null
                    ? weather.current.temperature.toFixed(1)
                    : '—'}
                  <span style={{ fontSize: '1.2rem', fontWeight: 400 }}> °C</span>
                </div>
                <div style={{ color: 'var(--color-text-muted)', textTransform: 'capitalize' }}>
                  {weather.current?.description || '—'}
                </div>
              </div>
              <div className="weather-stats" style={{ flex: 1, minWidth: '220px' }}>
                <div>
                  <div className="weather-stat-label">Humedad</div>
                  <div className="weather-stat-value">{weather.current?.humidity ?? '—'}%</div>
                </div>
                <div>
                  <div className="weather-stat-label">Lluvia 24 h</div>
                  <div className="weather-stat-value">{mm(weather.rain?.next_24h_mm)}</div>
                </div>
                <div>
                  <div className="weather-stat-label">Prob. lluvia</div>
                  <div className="weather-stat-value">
                    {percent(weather.rain?.next_24h_probability)}
                  </div>
                </div>
              </div>
              <span className={`badge ${rainStatus(weather.rain?.status).badge}`}>
                {rainStatus(weather.rain?.status).label}
              </span>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-6" style={{ marginBottom: '1.5rem' }}>
        {(telemetry?.soil_sensors || []).map(sensor => (
          <SensorCard
            key={sensor.id}
            label={`Sensor ${sensor.id}`}
            value={sensor.pct}
            unit="%"
            status={soilStatus(sensor.pct, sensor.ok, soilThreshold)}
            row={sensor.row}
          />
        ))}
      </div>

      <div className="grid grid-4" style={{ marginBottom: '1.5rem' }}>
        {ACTUATORS.map(actuator => {
          const active = Boolean(telemetry?.actuators?.[actuator.key])
          return (
            <div className="actuator-card" key={actuator.key}>
              <div
                className="actuator-icon"
                style={{
                  background: active
                    ? 'rgba(45, 106, 79, 0.15)'
                    : 'rgba(100, 116, 139, 0.1)',
                }}
                aria-hidden="true"
              >
                {actuator.icon}
              </div>
              <div className="actuator-info">
                <div className="actuator-name">{actuator.name}</div>
                <div className="actuator-status">
                  <span className={`badge ${active ? 'badge-on' : 'badge-off'}`}>
                    {active ? 'ENCENDIDO' : 'APAGADO'}
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <span>📸 Última fotografía</span>
          <Link to="/fotos" style={{ fontSize: '0.8rem' }}>
            Ver galería →
          </Link>
        </div>
        <div className="card-body" style={{ textAlign: 'center' }}>
          {latestPhoto && !photoError ? (
            <>
              <img
                src={`/api/public/photos/latest/file?t=${encodeURIComponent(latestPhoto.timestamp)}`}
                alt="Última fotografía del cultivo"
                loading="eager"
                decoding="async"
                style={{
                  maxWidth: '100%',
                  maxHeight: '420px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--color-border)',
                }}
                onError={() => setPhotoError(true)}
              />
              <p className="page-subtitle" style={{ marginTop: '0.5rem' }}>
                Tomada:{' '}
                {formatServerTime(latestPhoto.timestamp, d => format(d, 'dd/MM/yyyy HH:mm'))}
              </p>
            </>
          ) : (
            <p style={{ color: 'var(--color-text-muted)' }}>
              No hay fotografías disponibles ahora mismo.
            </p>
          )}
        </div>
      </div>

      <MultiChart data={history} hours={hours} />
    </div>
  )
}
