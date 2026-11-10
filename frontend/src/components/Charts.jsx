import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { format } from 'date-fns'
import { parseServerTime } from '../utils/time'

const COLORS = {
  temperature: '#e53935',
  humidity: '#1e88e5',
  soil: '#43a047',
}

function formatTick(value) {
  const date = parseServerTime(value)
  if (!date || Number.isNaN(date.getTime())) return ''
  return format(date, 'HH:mm')
}

function formatLabel(value) {
  const date = parseServerTime(value)
  if (!date || Number.isNaN(date.getTime())) return ''
  return format(date, 'dd/MM HH:mm')
}

function EmptyChart({ label = 'Sin datos' }) {
  return (
    <div
      className="chart-container"
      role="img"
      aria-label={label}
      style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-text-muted)' }}
    >
      {label}
    </div>
  )
}

function seriesSummary(values, unit, name) {
  const usable = values.filter(value => value !== null && value !== undefined && !Number.isNaN(value))
  if (!usable.length) return `${name}: sin datos`
  const latest = usable[usable.length - 1]
  const min = Math.min(...usable)
  const max = Math.max(...usable)
  return `${name}: último valor ${latest.toFixed(1)}${unit}, mínimo ${min.toFixed(1)}${unit}, máximo ${max.toFixed(1)}${unit}`
}

export function TemperatureChart({ data }) {
  if (!data?.length) return <EmptyChart />

  const chartData = data
    .filter(d => d.temperature !== null && d.temperature !== undefined)
    .map(d => ({ time: d.timestamp, value: d.temperature }))

  if (!chartData.length) return <EmptyChart />

  return (
    <div
      className="chart-container"
      role="img"
      aria-label={seriesSummary(chartData.map(point => point.value), ' grados Celsius', 'Temperatura')}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis dataKey="time" tick={{ fontSize: 10 }} stroke="#999" tickFormatter={formatTick} minTickGap={30} />
          <YAxis tick={{ fontSize: 10 }} stroke="#999" domain={['auto', 'auto']} />
          <Tooltip
            contentStyle={{ background: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '8px' }}
            labelFormatter={formatLabel}
            formatter={(value) => [value?.toFixed(1) + ' °C', 'Temperatura']}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="value"
            stroke={COLORS.temperature}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 6 }}
            name="Temperatura (°C)"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export function HumidityChart({ data }) {
  if (!data?.length) return <EmptyChart />

  const chartData = data
    .filter(d => d.humidity !== null && d.humidity !== undefined)
    .map(d => ({ time: d.timestamp, value: d.humidity }))

  if (!chartData.length) return <EmptyChart />

  return (
    <div
      className="chart-container"
      role="img"
      aria-label={seriesSummary(chartData.map(point => point.value), ' por ciento', 'Humedad ambiental')}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis dataKey="time" tick={{ fontSize: 10 }} stroke="#999" tickFormatter={formatTick} minTickGap={30} />
          <YAxis tick={{ fontSize: 10 }} stroke="#999" domain={[0, 100]} />
          <Tooltip
            contentStyle={{ background: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '8px' }}
            labelFormatter={formatLabel}
            formatter={(value) => [value?.toFixed(1) + ' %', 'Humedad']}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="value"
            stroke={COLORS.humidity}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 6 }}
            name="Humedad (%)"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export function SoilMoistureChart({ data }) {
  if (!data?.length) return <EmptyChart />

  const sensors = ['soil_a1', 'soil_a2', 'soil_a3', 'soil_b1', 'soil_b2', 'soil_b3']
  const labels = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3']

  const chartData = data.map(d => {
    const obj = { time: d.timestamp }
    sensors.forEach(s => { obj[s] = d[s] })
    return obj
  })

  const summary = labels
    .map((label, index) => {
      const values = chartData.map(point => point[sensors[index]])
      const usable = values.filter(value => value !== null && value !== undefined)
      return usable.length ? `${label} ${usable[usable.length - 1].toFixed(0)}%` : `${label} sin datos`
    })
    .join(', ')

  return (
    <div
      className="chart-container"
      role="img"
      aria-label={`Humedad del suelo por sensor: ${summary}`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis dataKey="time" tick={{ fontSize: 10 }} stroke="#999" tickFormatter={formatTick} minTickGap={30} />
          <YAxis tick={{ fontSize: 10 }} stroke="#999" domain={[0, 100]} />
          <Tooltip
            contentStyle={{ background: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '8px' }}
            labelFormatter={formatLabel}
            formatter={(value) => [value?.toFixed?.(1) ?? '—', '']}
          />
          <Legend />
          {sensors.map((sensor, i) => (
            <Line
              key={sensor}
              type="monotone"
              dataKey={sensor}
              stroke={COLORS.soil}
              strokeWidth={1.5}
              dot={false}
              connectNulls
              strokeDasharray={i >= 3 ? '5 5' : '0'}
              activeDot={{ r: 5 }}
              name={labels[i]}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export function MultiChart({ data, hours = 24 }) {
  return (
    <div className="grid grid-2" style={{ gap: '1rem' }}>
      <div className="card">
        <div className="card-header">Temperatura ({hours}h)</div>
        <div className="card-body"><TemperatureChart data={data} /></div>
      </div>
      <div className="card">
        <div className="card-header">Humedad Ambiental ({hours}h)</div>
        <div className="card-body"><HumidityChart data={data} /></div>
      </div>
      <div className="card">
        <div className="card-header">Humedad Suelo ({hours}h)</div>
        <div className="card-body"><SoilMoistureChart data={data} /></div>
      </div>
    </div>
  )
}
