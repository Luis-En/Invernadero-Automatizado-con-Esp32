import { describe, expect, it } from 'vitest'
import { parseServerTime } from '../utils/time'

describe('parseServerTime', () => {
  it('treats a naive backend timestamp as UTC', () => {
    expect(parseServerTime('2026-01-02T03:04:05').toISOString())
      .toBe('2026-01-02T03:04:05.000Z')
  })

  it('respects an explicit timezone suffix', () => {
    expect(parseServerTime('2026-01-02T03:04:05+00:00').toISOString())
      .toBe('2026-01-02T03:04:05.000Z')
  })

  it('returns null for empty values', () => {
    expect(parseServerTime(null)).toBeNull()
    expect(parseServerTime('')).toBeNull()
  })
})
