// Backend timestamps are UTC. Older rows were serialized without a timezone
// suffix, which made `new Date(value)` interpret them as local time. Normalize
// the string before parsing so the dashboard shows the right hour everywhere.
export function parseServerTime(value) {
  if (!value) return null
  if (value instanceof Date) return value
  const text = String(value).trim()
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(text)
  return new Date(hasZone ? text : `${text}Z`)
}

export function formatServerTime(value, formatter) {
  const date = parseServerTime(value)
  if (!date || Number.isNaN(date.getTime())) return '—'
  return formatter ? formatter(date) : date.toLocaleString()
}
