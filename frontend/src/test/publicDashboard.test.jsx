import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { PublicDashboard } from '../pages/public/PublicDashboard'

vi.mock('../hooks/usePublicTelemetry', () => ({
  usePublicTelemetry: () => ({
    telemetry: {
      timestamp: '2026-11-06T10:00:00Z',
      last_update: '2026-11-06T10:00:00Z',
      temperature: 24.5,
      humidity: 71,
      soil_avg_row_a: 45,
      soil_avg_row_b: 40,
      soil_sensors: [
        { id: 'A1', pct: 45, ok: true, row: 'A' },
        { id: 'B1', pct: 40, ok: true, row: 'B' },
      ],
      actuators: { fan_1: false, fan_2: false, humidifier_1: false, humidifier_2: false, pump: false },
      irrigation_enabled: false,
      irrigation_needed: false,
      active_crop: 'Tomate',
      telemetry_stale: false,
    },
    history: [],
    hours: 24,
    connected: true,
    loading: false,
    error: '',
    setTimeRange: vi.fn(),
    refresh: vi.fn(),
  }),
}))

vi.mock('../hooks/usePublicWeather', () => ({
  usePublicWeather: () => ({ weather: null, loading: false, error: '', refresh: vi.fn() }),
}))

vi.mock('../api', () => ({
  api: { getPublicLatestPhoto: vi.fn().mockResolvedValue(null) },
}))

describe('PublicDashboard', () => {
  it('renders live values without requiring a session', () => {
    render(
      <MemoryRouter>
        <PublicDashboard />
      </MemoryRouter>
    )
    expect(screen.getByText('Invernadero en vivo')).toBeInTheDocument()
    expect(screen.getByText(/24\.5/)).toBeInTheDocument()
    expect(screen.getByText(/Tomate/)).toBeInTheDocument()
  })
})
