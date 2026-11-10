import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'

describe('ApiClient', () => {
  beforeEach(() => {
    localStorage.clear()
    api.setToken(null)
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('stores and clears the bearer token', () => {
    api.setToken('abc')
    expect(api.getHeaders().Authorization).toBe('Bearer abc')
    api.setToken(null)
    expect(api.getHeaders().Authorization).toBeUndefined()
  })

  it('sends the bearer token and parses JSON', async () => {
    api.setToken('abc')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      json: async () => ({ status: 'ok' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(api.get('/health')).resolves.toEqual({ status: 'ok' })
    expect(fetchMock).toHaveBeenCalledWith(
      '/health',
      expect.objectContaining({
        credentials: 'same-origin',
        headers: expect.objectContaining({ Authorization: 'Bearer abc' }),
      }),
    )
  })

  it('never persists the token in localStorage', () => {
    api.setToken('secret-token')
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('attaches Retry-After metadata to a 429', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      headers: {
        get: (name) => {
          if (name === 'content-type') return 'application/json'
          if (name === 'retry-after') return '120'
          return null
        },
      },
      json: async () => ({ detail: 'Demasiados intentos' }),
    }))

    await expect(api.get('/api/x')).rejects.toMatchObject({
      status: 429,
      retryAfter: 120,
      message: 'Demasiados intentos',
    })
  })

  it('turns an HTTP error detail into an Error message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'dato inválido' }),
    }))
    await expect(api.get('/api/x')).rejects.toThrow('dato inválido')
  })
})
