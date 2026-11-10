import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useIrrigationAlerts } from '../hooks/useIrrigationAlerts'
import { getNotificationRegistration } from '../pwa'

vi.mock('../pwa', () => ({
  getNotificationRegistration: vi.fn(),
}))

function status(overrides = {}) {
  return {
    irrigation_needed: false,
    soil_avg_pct: 20,
    soil_threshold_pct: 35,
    ...overrides,
  }
}

describe('useIrrigationAlerts', () => {
  let showNotification

  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('local-irrigation-alerts', '1')
    showNotification = vi.fn().mockResolvedValue(undefined)
    getNotificationRegistration.mockResolvedValue({
      showNotification,
      pushManager: { getSubscription: vi.fn().mockResolvedValue(null) },
    })
    vi.stubGlobal('Notification', { permission: 'granted' })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('shows one notification when the soil crosses into "needs water"', async () => {
    const { rerender } = renderHook(({ value }) => useIrrigationAlerts(value), {
      initialProps: { value: status() },
    })

    rerender({ value: status({ irrigation_needed: true }) })

    await waitFor(() => expect(showNotification).toHaveBeenCalledTimes(1))
    expect(showNotification).toHaveBeenCalledWith(
      '💧 Riego necesario',
      expect.objectContaining({
        body: expect.stringContaining('20%'),
        tag: 'irrigation-needed',
      })
    )
    expect(localStorage.getItem('irrigation-last-notified')).toBeTruthy()

    // A later poll with the same dry state must not repeat the alert.
    rerender({ value: status({ irrigation_needed: true }) })
    expect(showNotification).toHaveBeenCalledTimes(1)
  })

  it('does not duplicate a server push subscription', async () => {
    getNotificationRegistration.mockResolvedValue({
      showNotification,
      pushManager: {
        getSubscription: vi.fn().mockResolvedValue({ endpoint: 'https://push.example/1' }),
      },
    })

    const { rerender } = renderHook(({ value }) => useIrrigationAlerts(value), {
      initialProps: { value: status() },
    })
    rerender({ value: status({ irrigation_needed: true }) })

    await new Promise(resolve => setTimeout(resolve, 20))
    expect(showNotification).not.toHaveBeenCalled()
    expect(localStorage.getItem('irrigation-last-notified')).toBeNull()
  })

  it('stays silent when local alerts were not enabled', async () => {
    localStorage.removeItem('local-irrigation-alerts')
    const { rerender } = renderHook(({ value }) => useIrrigationAlerts(value), {
      initialProps: { value: status() },
    })
    rerender({ value: status({ irrigation_needed: true }) })

    await new Promise(resolve => setTimeout(resolve, 20))
    expect(showNotification).not.toHaveBeenCalled()
  })
})
