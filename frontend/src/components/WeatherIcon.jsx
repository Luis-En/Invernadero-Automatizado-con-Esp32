// Small helpers shared by the dashboard summary and the weather page.

const ICON_RULES = [
  [/^01/, '☀️'],
  [/^02/, '🌤️'],
  [/^03/, '⛅'],
  [/^04/, '☁️'],
  [/^09/, '🌧️'],
  [/^10/, '🌦️'],
  [/^11/, '⛈️'],
  [/^13/, '❄️'],
  [/^50/, '🌫️'],
]

export function weatherEmoji(icon) {
  const code = (icon || '').slice(0, 2)
  const rule = ICON_RULES.find(([pattern]) => pattern.test(code))
  return rule ? rule[1] : '🌡️'
}

export function WeatherIcon({ icon, size = '1.5rem' }) {
  return (
    <span role="img" aria-hidden="true" style={{ fontSize: size, lineHeight: 1 }}>
      {weatherEmoji(icon)}
    </span>
  )
}

export const RAIN_STATUS = {
  raining: { label: 'Lloviendo', badge: 'badge-critical' },
  rain_soon: { label: 'Lluvia próxima', badge: 'badge-warning' },
  likely: { label: 'Probable', badge: 'badge-warning' },
  possible: { label: 'Posible', badge: 'badge-off' },
  dry: { label: 'Sin lluvia', badge: 'badge-normal' },
}

export function rainStatus(status) {
  return RAIN_STATUS[status] || RAIN_STATUS.dry
}

export function percent(value) {
  if (value === null || value === undefined) return '—'
  return `${Math.round(value * 100)}%`
}

export function mm(value) {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(1)} mm`
}
