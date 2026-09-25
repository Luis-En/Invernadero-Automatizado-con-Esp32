import { useTelemetry } from '../context/TelemetryContext'
import { MultiChart } from '../components/Charts'
import { format } from 'date-fns'

function numericValues(data, selector) {
  return data
    .map(selector)
    .filter(v => v !== null && v !== undefined && !Number.isNaN(v))
}

function average(values) {
  if (!values.length) return null
  return values.reduce((a, b) => a + b, 0) / values.length
}

function fmt(value, unit = '', digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${value.toFixed(digits)}${unit}`
}

function averageSoilRow(data, keys) {
  const values = []
  data.forEach(d => keys.forEach(k => {
    if (d[k] !== null && d[k] !== undefined && !Number.isNaN(d[k])) values.push(d[k])
  }))
  return average(values)
}

export function History() {
  const { history, historyHours, setTimeRange } = useTelemetry()
  const data = history

  const temps = numericValues(data, d => d.temperature)
  const hums = numericValues(data, d => d.humidity)
  const avgTemp = average(temps)
  const avgHum = average(hums)
  const avgSoilA = averageSoilRow(data, ['soil_a1', 'soil_a2', 'soil_a3'])
  const avgSoilB = averageSoilRow(data, ['soil_b1', 'soil_b2', 'soil_b3'])
  const minTemp = temps.length ? Math.min(...temps) : null
  const maxTemp = temps.length ? Math.max(...temps) : null
  const minHum = hums.length ? Math.min(...hums) : null
  const maxHum = hums.length ? Math.max(...hums) : null

  const periodStart = data.length ? format(new Date(data[0].timestamp), 'dd/MM HH:mm') : '—'
  const periodEnd = data.length ? format(new Date(data[data.length - 1].timestamp), 'dd/MM HH:mm') : '—'

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Historial de Sensores</h1>
          <p style={{ color: 'var(--color-text-muted)' }}>Gráficas históricas de temperatura, humedad y humedad del suelo</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <select
            value={historyHours}
            onChange={e => setTimeRange(Number(e.target.value))}
            className="form-control"
            style={{ width: 'auto' }}
          >
            <option value={1}>Última hora</option>
            <option value={6}>Últimas 6 horas</option>
            <option value={12}>Últimas 12 horas</option>
            <option value={24}>Último día</option>
            <option value={48}>Últimos 2 días</option>
            <option value={168}>Última semana</option>
          </select>
        </div>
      </div>

      <div className="grid grid-3" style={{ marginBottom: '1.5rem' }}>
        <div className="card">
          <div className="card-header">📊 Resumen del período</div>
          <div className="card-body">
            {data.length > 0 ? (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span>Puntos de datos:</span>
                  <strong>{data.length}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span>Período:</span>
                  <strong>{periodStart} - {periodEnd}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span>Temp. media:</span>
                  <strong>{fmt(avgTemp, ' °C')}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span>Humedad media:</span>
                  <strong>{fmt(avgHum, ' %')}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span>Suelo A media:</span>
                  <strong>{fmt(avgSoilA, ' %')}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Suelo B media:</span>
                  <strong>{fmt(avgSoilB, ' %')}</strong>
                </div>
              </>
            ) : (
              <p style={{ color: 'var(--color-text-muted)', textAlign: 'center', padding: '2rem' }}>No hay datos para el período seleccionado</p>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-header">🌡️ Temperatura Min/Max</div>
          <div className="card-body">
            {temps.length > 0 ? (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span>Mínima:</span>
                  <strong style={{ color: '#1e88e5' }}>{fmt(minTemp, ' °C')}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span>Máxima:</span>
                  <strong style={{ color: '#e53935' }}>{fmt(maxTemp, ' °C')}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Rango:</span>
                  <strong>{fmt(maxTemp - minTemp, ' °C')}</strong>
                </div>
              </>
            ) : <p style={{ color: 'var(--color-text-muted)' }}>—</p>}
          </div>
        </div>

        <div className="card">
          <div className="card-header">💧 Humedad Min/Max</div>
          <div className="card-body">
            {hums.length > 0 ? (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span>Mínima:</span>
                  <strong style={{ color: '#e53935' }}>{fmt(minHum, ' %')}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span>Máxima:</span>
                  <strong style={{ color: '#1e88e5' }}>{fmt(maxHum, ' %')}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Rango:</span>
                  <strong>{fmt(maxHum - minHum, ' %')}</strong>
                </div>
              </>
            ) : <p style={{ color: 'var(--color-text-muted)' }}>—</p>}
          </div>
        </div>
      </div>

      <MultiChart data={data} hours={historyHours} />
    </div>
  )
}
