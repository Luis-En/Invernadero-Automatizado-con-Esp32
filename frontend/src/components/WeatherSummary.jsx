import { Link } from 'react-router-dom'
import { format } from 'date-fns'
import { useWeather } from '../context/WeatherContext'
import { WeatherIcon, rainStatus, percent, mm } from './WeatherIcon'

function Stat({ label, value }) {
  return (
    <div>
      <div className="weather-stat-label">{label}</div>
      <div className="weather-stat-value">{value}</div>
    </div>
  )
}

export function WeatherSummary() {
  const { weather, loading, error, refresh } = useWeather()

  if (!weather && loading) {
    return (
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">🌤️ Clima exterior</div>
        <div className="card-body" style={{ color: 'var(--color-text-muted)' }}>Cargando clima…</div>
      </div>
    )
  }

  if (!weather) {
    return (
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">🌤️ Clima exterior</div>
        <div className="card-body">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
            <span style={{ color: 'var(--color-text-muted)' }}>
              {error || 'No se pudo cargar el clima'}
            </span>
            <button className="btn btn-secondary btn-sm" onClick={refresh}>Reintentar</button>
          </div>
        </div>
      </div>
    )
  }

  if (!weather.configured) {
    return (
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">🌤️ Clima exterior</div>
        <div className="card-body" style={{ color: 'var(--color-text-muted)' }}>
          Configura <code>OPENWEATHER_API_KEY</code> en el <code>.env</code> del backend para ver el
          pronóstico de lluvia de la zona.
        </div>
      </div>
    )
  }

  const { current, rain, location } = weather
  const status = rainStatus(rain?.status)

  return (
    <div className="card" style={{ marginBottom: '1.5rem' }}>
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
        <span>🌤️ Clima exterior — {location?.name || 'Santa Lucía Cotzumalguapa'}</span>
        <Link to="/clima" style={{ fontSize: '0.8125rem', fontWeight: 500 }}>Ver pronóstico completo →</Link>
      </div>
      <div className="card-body">
        {weather.stale && (
          <div className="alert alert-warning" style={{ marginBottom: '1rem' }}>
            Mostrando los últimos datos guardados{weather.error ? ` (${weather.error})` : ''}.
          </div>
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <WeatherIcon icon={current?.icon} size="3rem" />
            <div>
              <div className="weather-temp">
                {current?.temperature !== null && current?.temperature !== undefined
                  ? current.temperature.toFixed(1)
                  : '—'}
                <span style={{ fontSize: '1.25rem', fontWeight: 400, color: 'var(--color-text-muted)' }}>°C</span>
              </div>
              <div style={{ color: 'var(--color-text-muted)', textTransform: 'capitalize' }}>
                {current?.description || '—'}
              </div>
            </div>
          </div>

          <div className="weather-stats" style={{ flex: 1, minWidth: '240px' }}>
            <Stat label="Humedad" value={current?.humidity !== null && current?.humidity !== undefined ? `${current.humidity}%` : '—'} />
            <Stat label="Viento" value={current?.wind_speed !== null && current?.wind_speed !== undefined ? `${current.wind_speed.toFixed(1)} m/s` : '—'} />
            <Stat label="Lluvia 1 h" value={mm(current?.rain_1h)} />
          </div>

          <div style={{ minWidth: '220px' }}>
            <span className={`badge ${status.badge}`}>{status.label}</span>
            <div style={{ marginTop: '0.5rem', fontWeight: 500 }}>{rain?.summary}</div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginTop: '0.25rem' }}>
              24 h: {percent(rain?.next_24h_probability)} · {mm(rain?.next_24h_mm)}
              {rain?.first_rain_at && (
                <> · desde las {format(new Date(rain.first_rain_at), 'HH:mm')}</>
              )}
            </div>
          </div>
        </div>

        <div style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
          Actualizado: {weather.fetched_at ? format(new Date(weather.fetched_at), 'dd/MM HH:mm') : '—'} · Datos: OpenWeather
        </div>
      </div>
    </div>
  )
}
