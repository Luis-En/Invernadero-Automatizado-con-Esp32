import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { format } from 'date-fns'

function tick(value) {
  if (!value) return ''
  try {
    return format(new Date(value), 'dd/MM HH:mm')
  } catch {
    return ''
  }
}

function label(value) {
  if (!value) return ''
  try {
    return format(new Date(value), 'dd/MM HH:mm')
  } catch {
    return ''
  }
}

export function RainTempChart({ hourly }) {
  const data = (hourly || []).map(h => ({
    time: h.time,
    rain: h.rain_mm ?? 0,
    temperature: h.temperature,
  }))

  if (!data.length) {
    return (
      <div className="chart-container" role="img" aria-label="Sin datos de pronóstico" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-text-muted)' }}>
        Sin datos de pronóstico
      </div>
    )
  }

  const totalRain = data.reduce((sum, point) => sum + (Number(point.rain) || 0), 0)
  const temperatures = data.map(point => point.temperature).filter(value => value !== null && value !== undefined && !Number.isNaN(value))
  const tempSummary = temperatures.length
    ? `, temperatura entre ${Math.min(...temperatures).toFixed(1)} y ${Math.max(...temperatures).toFixed(1)} grados`
    : ''

  return (
    <div
      className="chart-container"
      role="img"
      aria-label={`Pronóstico de lluvia y temperatura: ${totalRain.toFixed(1)} milímetros acumulados${tempSummary}`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis
            dataKey="time"
            tick={{ fontSize: 10 }}
            stroke="#999"
            tickFormatter={tick}
            minTickGap={40}
          />
          <YAxis yAxisId="rain" tick={{ fontSize: 10 }} stroke="#1e88e5" allowDecimals={false} />
          <YAxis yAxisId="temp" orientation="right" tick={{ fontSize: 10 }} stroke="#e53935" />
          <Tooltip
            contentStyle={{ background: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '8px' }}
            labelFormatter={label}
            formatter={(value, name) => [
              name === 'Lluvia (mm/3 h)' ? `${Number(value).toFixed(1)} mm` : `${Number(value).toFixed(1)} °C`,
              name,
            ]}
          />
          <Legend />
          <Bar yAxisId="rain" dataKey="rain" name="Lluvia (mm/3 h)" fill="#1e88e5" radius={[3, 3, 0, 0]} />
          <Line
            yAxisId="temp"
            type="monotone"
            dataKey="temperature"
            name="Temperatura (°C)"
            stroke="#e53935"
            strokeWidth={2}
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
