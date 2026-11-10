import { format } from 'date-fns'
import { useWeather } from '../context/WeatherContext'
import { WeatherIcon, rainStatus, percent, mm } from '../components/WeatherIcon'
import { RainTempChart } from '../components/WeatherCharts'

function Stat({ label, value, children }) {
  return (
    <div>
      <div className="weather-stat-label">{label}</div>
      <div className="weather-stat-value">{value ?? children ?? '—'}</div>
    </div>
  )
}

function windDirection(deg) {
  if (deg === null || deg === undefined) return ''
  const points = ['N', 'NE', 'E', 'SE', 'S', 'SO', 'O', 'NO']
  return points[Math.round(deg / 45) % 8]
}

export function Weather() {
  const { weather, loading, error, refresh } = useWeather()

  if (!weather && loading) {
    return (
      <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--color-text-muted)' }}>
        Cargando clima…
      </div>
    )
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Clima</h1>
          <p style={{ color: 'var(--color-text-muted)', marginTop: '0.25rem' }}>
            {weather?.location?.name || 'Santa Lucía Cotzumalguapa'}
            {weather?.fetched_at && ` · Actualizado ${format(new Date(weather.fetched_at), 'dd/MM HH:mm')}`}
          </p>
        </div>
        <button onClick={refresh} className="btn btn-secondary" disabled={loading}>
          {loading ? 'Actualizando…' : '🔄 Actualizar'}
        </button>
      </div>

      {error && !weather && <div className="alert alert-critical">{error}</div>}

      {weather && !weather.configured && (
        <div className="card">
          <div className="card-body" style={{ color: 'var(--color-text-muted)' }}>
            <p>
              El clima exterior no está configurado. Añade tu clave de OpenWeather en el{' '}
              <code>.env</code> del backend como <code>OPENWEATHER_API_KEY=...</code> y reinicia el
              servicio.
            </p>
            <p style={{ marginTop: '0.5rem', fontSize: '0.875rem' }}>
              El pronóstico es informativo: no controla el riego ni los actuadores.
            </p>
          </div>
        </div>
      )}

      {weather?.configured && (
        <>
          {weather.stale && (
            <div className="alert alert-warning" style={{ marginBottom: '1rem' }}>
              No se pudo actualizar con OpenWeather, así que se muestran los últimos datos guardados
              {weather.error ? ` (${weather.error})` : ''}.
            </div>
          )}
          {error && weather && (
            <div className="alert alert-warning" style={{ marginBottom: '1rem' }}>{error}</div>
          )}

          <div className="grid grid-2" style={{ marginBottom: '1.5rem', alignItems: 'stretch' }}>
            <div className="card">
              <div className="card-header">Condiciones actuales</div>
              <div className="card-body">
                <div className="weather-hero">
                  <WeatherIcon icon={weather.current?.icon} size="4rem" />
                  <div>
                    <div className="weather-temp">
                      {weather.current?.temperature !== null && weather.current?.temperature !== undefined
                        ? weather.current.temperature.toFixed(1)
                        : '—'}
                      <span style={{ fontSize: '1.5rem', fontWeight: 400, color: 'var(--color-text-muted)' }}>°C</span>
                    </div>
                    <div style={{ color: 'var(--color-text-muted)', textTransform: 'capitalize' }}>
                      {weather.current?.description || '—'}
                      {weather.current?.feels_like !== null && weather.current?.feels_like !== undefined
                        ? ` · sensación ${weather.current.feels_like.toFixed(1)} °C`
                        : ''}
                    </div>
                  </div>
                </div>

                <div className="weather-stats" style={{ marginTop: '1.25rem' }}>
                  <Stat label="Humedad" value={weather.current?.humidity !== null ? `${weather.current?.humidity}%` : '—'} />
                  <Stat label="Presión" value={weather.current?.pressure !== null ? `${weather.current?.pressure} hPa` : '—'} />
                  <Stat
                    label="Viento"
                    value={
                      weather.current?.wind_speed !== null && weather.current?.wind_speed !== undefined
                        ? `${weather.current.wind_speed.toFixed(1)} m/s ${windDirection(weather.current?.wind_deg)}`
                        : '—'
                    }
                  />
                  <Stat label="Nubes" value={weather.current?.clouds !== null ? `${weather.current?.clouds}%` : '—'} />
                  <Stat
                    label="Visibilidad"
                    value={
                      weather.current?.visibility !== null && weather.current?.visibility !== undefined
                        ? `${(weather.current.visibility / 1000).toFixed(1)} km`
                        : '—'
                    }
                  />
                  <Stat label="Lluvia 1 h" value={mm(weather.current?.rain_1h)} />
                  <Stat
                    label="Amanecer"
                    value={weather.current?.sunrise ? format(new Date(weather.current.sunrise), 'HH:mm') : '—'}
                  />
                  <Stat
                    label="Atardecer"
                    value={weather.current?.sunset ? format(new Date(weather.current.sunset), 'HH:mm') : '—'}
                  />
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-header">Pronóstico de lluvia</div>
              <div className="card-body">
                <span className={`badge ${rainStatus(weather.rain?.status).badge}`} style={{ fontSize: '0.875rem' }}>
                  {rainStatus(weather.rain?.status).label}
                </span>
                <p style={{ marginTop: '0.75rem', fontSize: '1.125rem', fontWeight: 600 }}>
                  {weather.rain?.summary}
                </p>

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

                <p style={{ marginTop: '1rem', fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
                  Pronóstico cada 3 h. Referencia para decidir el riego; la lluvia exterior no moja
                  directamente el cultivo bajo cubierta.
                </p>
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
            <div className="card-header">Detalle por horas</div>
            <div className="card-body">
              <div className="weather-table-wrap" tabIndex={0} role="region" aria-label="Pronóstico detallado por horas">
                <table className="weather-table">
                  <caption className="visually-hidden">
                    Pronóstico por horas: temperatura, probabilidad y cantidad de lluvia, humedad y viento
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Hora</th>
                      <th scope="col">Clima</th>
                      <th scope="col">Temp.</th>
                      <th scope="col">Prob. lluvia</th>
                      <th scope="col">Lluvia</th>
                      <th scope="col">Humedad</th>
                      <th scope="col">Viento</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(weather.hourly || []).map(hour => (
                      <tr key={hour.dt}>
                        <td>{format(new Date(hour.time), 'dd/MM HH:mm')}</td>
                        <td style={{ textTransform: 'capitalize' }}>
                          <WeatherIcon icon={hour.icon} size="1rem" /> {hour.description || '—'}
                        </td>
                        <td>{hour.temperature !== null ? `${hour.temperature.toFixed(1)} °C` : '—'}</td>
                        <td>{percent(hour.pop)}</td>
                        <td>{mm(hour.rain_mm)}</td>
                        <td>{hour.humidity !== null ? `${hour.humidity}%` : '—'}</td>
                        <td>
                          {hour.wind_speed !== null && hour.wind_speed !== undefined
                            ? `${hour.wind_speed.toFixed(1)} m/s ${windDirection(hour.wind_deg)}`
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
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
                      {day.temp_min !== null ? `${day.temp_min.toFixed(1)}°` : '—'} / {day.temp_max !== null ? `${day.temp_max.toFixed(1)}°` : '—'}
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
            Datos meteorológicos de{' '}
            <a href="https://openweathermap.org/" target="_blank" rel="noreferrer">OpenWeather</a>.
            Pronóstico de referencia; no sustituye los avisos oficiales (INSIVUMEH/CONRED).
          </p>
        </>
      )}
    </div>
  )
}
