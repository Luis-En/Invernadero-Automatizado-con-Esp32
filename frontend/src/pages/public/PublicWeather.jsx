import { format } from 'date-fns'
import { usePublicWeather } from '../../hooks/usePublicWeather'
import { WeatherIcon, rainStatus, percent, mm } from '../../components/WeatherIcon'
import { RainTempChart } from '../../components/WeatherCharts'

function Stat({ label, value }) {
  return (
    <div>
      <div className="weather-stat-label">{label}</div>
      <div className="weather-stat-value">{value ?? '—'}</div>
    </div>
  )
}

export function PublicWeather() {
  const { weather, loading, error, refresh } = usePublicWeather()

  if (loading && !weather) {
    return (
      <div className="loading-state" role="status" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <p>Cargando el clima…</p>
      </div>
    )
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Clima</h1>
          <p className="page-subtitle">
            {weather?.location?.name || 'Santa Lucía Cotzumalguapa'}
            {weather?.fetched_at
              ? ` · Actualizado ${format(new Date(weather.fetched_at), 'dd/MM HH:mm')}`
              : ''}
          </p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={refresh} disabled={loading}>
          {loading ? 'Actualizando…' : '🔄 Actualizar'}
        </button>
      </div>

      {error && (
        <div className="alert alert-warning" role="status">
          {error}
        </div>
      )}

      {weather && !weather.configured && (
        <div className="card">
          <div className="card-body" style={{ color: 'var(--color-text-muted)' }}>
            <p>El clima exterior no está configurado en este invernadero.</p>
            <p style={{ marginTop: '0.5rem', fontSize: '0.875rem' }}>
              El pronóstico es informativo: no controla el riego ni los actuadores.
            </p>
          </div>
        </div>
      )}

      {weather?.configured && (
        <>
          <div className="grid grid-2" style={{ marginBottom: '1.5rem' }}>
            <div className="card">
              <div className="card-header">Condiciones actuales</div>
              <div className="card-body">
                <div className="weather-hero">
                  <WeatherIcon icon={weather.current?.icon} size="4rem" />
                  <div>
                    <div className="weather-temp">
                      {weather.current?.temperature != null
                        ? weather.current.temperature.toFixed(1)
                        : '—'}
                      <span style={{ fontSize: '1.5rem', fontWeight: 400 }}> °C</span>
                    </div>
                    <div style={{ color: 'var(--color-text-muted)', textTransform: 'capitalize' }}>
                      {weather.current?.description || '—'}
                    </div>
                  </div>
                </div>
                <div className="weather-stats" style={{ marginTop: '1.25rem' }}>
                  <Stat label="Humedad" value={weather.current?.humidity != null ? `${weather.current.humidity}%` : '—'} />
                  <Stat label="Presión" value={weather.current?.pressure != null ? `${weather.current.pressure} hPa` : '—'} />
                  <Stat label="Viento" value={weather.current?.wind_speed != null ? `${weather.current.wind_speed.toFixed(1)} m/s` : '—'} />
                  <Stat label="Nubes" value={weather.current?.clouds != null ? `${weather.current.clouds}%` : '—'} />
                  <Stat label="Lluvia 1 h" value={mm(weather.current?.rain_1h)} />
                  <Stat label="Amanecer" value={weather.current?.sunrise ? format(new Date(weather.current.sunrise), 'HH:mm') : '—'} />
                  <Stat label="Atardecer" value={weather.current?.sunset ? format(new Date(weather.current.sunset), 'HH:mm') : '—'} />
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-header">Pronóstico de lluvia</div>
              <div className="card-body">
                <span className={`badge ${rainStatus(weather.rain?.status).badge}`}>
                  {rainStatus(weather.rain?.status).label}
                </span>
                <p style={{ marginTop: '0.75rem', fontWeight: 600 }}>{weather.rain?.summary}</p>
                <div className="weather-stats" style={{ marginTop: '1.25rem' }}>
                  <Stat label="Próximas 6 h" value={percent(weather.rain?.next_6h_probability)} />
                  <Stat label="Próximas 24 h" value={percent(weather.rain?.next_24h_probability)} />
                  <Stat label="Lluvia 24 h" value={mm(weather.rain?.next_24h_mm)} />
                  <Stat
                    label="Primera lluvia"
                    value={
                      weather.rain?.first_rain_at
                        ? format(new Date(weather.rain.first_rain_at), 'dd/MM HH:mm')
                        : weather.rain?.status === 'raining'
                          ? 'En curso'
                          : 'Sin lluvia'
                    }
                  />
                  <Stat label="Prob. primera" value={percent(weather.rain?.first_rain_probability)} />
                </div>
              </div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: '1.5rem' }}>
            <div className="card-header">Próximas {weather.hours} h — lluvia y temperatura</div>
            <div className="card-body">
              <RainTempChart hourly={weather.hourly} />
            </div>
          </div>

          <div className="card" style={{ marginBottom: '1.5rem' }}>
            <div className="card-header">Próximos días</div>
            <div className="card-body">
              <div className="weather-days">
                {(weather.daily || []).map(day => (
                  <div key={day.date} className="sensor-card" style={{ textAlign: 'left' }}>
                    <div className="sensor-label">
                      {format(new Date(`${day.date}T12:00:00`), 'EEE dd/MM')}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                      <WeatherIcon icon={day.icon} size="2rem" />
                      <span style={{ textTransform: 'capitalize', fontSize: '0.875rem' }}>
                        {day.description || '—'}
                      </span>
                    </div>
                    <div style={{ fontWeight: 600 }}>
                      {day.temp_min != null ? `${day.temp_min.toFixed(1)}°` : '—'} /{' '}
                      {day.temp_max != null ? `${day.temp_max.toFixed(1)}°` : '—'}
                    </div>
                    <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginTop: '0.25rem' }}>
                      Lluvia {percent(day.pop_max)} · {mm(day.rain_mm)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
            Datos meteorológicos de OpenWeather. Pronóstico de referencia; no sustituye
            los avisos oficiales (INSIVUMEH/CONRED).
          </p>
        </>
      )}
    </div>
  )
}
