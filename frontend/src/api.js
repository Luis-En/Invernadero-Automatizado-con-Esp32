// Relative by default: the same build works on localhost, on the LAN behind
// Nginx, and behind the Vite dev proxy. VITE_API_URL can still override it.
export const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

function defaultWsUrl() {
  if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL
  if (typeof window === 'undefined') return '/api/config/ws'
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/config/ws`
}

export const WS_URL = defaultWsUrl()

class ApiClient {
  constructor() {
    // The session lives in an HttpOnly cookie. The in-memory token is only a
    // fallback for non-browser clients and is deliberately not persisted.
    this.token = null
    this.ws = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 10
  }

  get API_URL() {
    return API_URL
  }

  get WS_URL() {
    return WS_URL
  }

  setToken(token) {
    // Never write the token to localStorage: an XSS could read it forever.
    this.token = token || null
  }

  getHeaders() {
    const headers = { 'Content-Type': 'application/json' }
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }
    return headers
  }

  async request(endpoint, options = {}) {
    const {
      skipAuthRedirect = false,
      timeoutMs = 15000,
      signal,
      headers: extraHeaders,
      ...fetchOptions
    } = options

    const controller = signal ? null : new AbortController()
    const timeout = controller ? setTimeout(() => controller.abort(), timeoutMs) : null
    let response
    try {
      response = await fetch(`${API_URL}${endpoint}`, {
        ...fetchOptions,
        // Send the HttpOnly session cookie on same-origin requests.
        credentials: 'same-origin',
        signal: signal || controller?.signal,
        headers: {
          ...this.getHeaders(),
          ...extraHeaders,
        },
      })
    } catch (error) {
      if (error.name === 'AbortError') {
        throw new Error('La solicitud tardó demasiado. Reintente.')
      }
      throw new Error('No se pudo conectar con el servidor')
    } finally {
      if (timeout) clearTimeout(timeout)
    }

    if (response.status === 401 && !skipAuthRedirect) {
      this.setToken(null)
      if (typeof window !== 'undefined') {
        // Only the admin area needs a login. A 401 on a public page must not
        // bounce a visitor to the administrator login.
        const path = window.location.pathname
        if (path.startsWith('/admin') && path !== '/admin/login') {
          window.location.assign('/admin/login')
        }
      }
      throw new Error('Sesión expirada')
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Error' }))
      const detail = Array.isArray(error.detail)
        ? error.detail.map(item => item.msg || item).join(', ')
        : error.detail
      const failure = new Error(detail || `HTTP ${response.status}`)
      failure.status = response.status
      const retryAfter = response.headers.get('retry-after')
      if (retryAfter) failure.retryAfter = Number(retryAfter)
      throw failure
    }

    if (response.status === 204) return null
    const contentType = response.headers.get('content-type') || ''
    if (!contentType.includes('application/json')) return response.blob()
    return response.json()
  }

  get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'GET' })
  }

  post(endpoint, data, options = {}) {
    return this.request(endpoint, { ...options, method: 'POST', body: JSON.stringify(data) })
  }

  put(endpoint, data, options = {}) {
    return this.request(endpoint, { ...options, method: 'PUT', body: JSON.stringify(data) })
  }

  delete(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'DELETE' })
  }

  // Photos are behind the authenticated router now (the static /photos mount
  // was removed). Fetch the bytes with the bearer token and hand the caller an
  // object URL it must revoke when the image unmounts.
  async getPhotoBlobUrl(id) {
    const blob = await this.get(`/api/photos/${id}/file`)
    return URL.createObjectURL(blob)
  }

  async getLatestPhotoBlobUrl() {
    const blob = await this.get('/api/photos/latest/file')
    return URL.createObjectURL(blob)
  }

  getWsUrl() {
    // The browser sends the HttpOnly cookie on the WebSocket handshake.
    // Keeping the JWT out of the query string avoids leaking it in logs.
    return WS_URL
  }

  // Auth
  login(username, password) {
    return this.post(
      '/api/auth/login',
      { username, password },
      { skipAuthRedirect: true }
    )
  }

  logout() {
    return this.post('/api/auth/logout', {}, { skipAuthRedirect: true })
  }

  register(data) {
    return this.post('/api/auth/register', data)
  }

  me(options = {}) {
    return this.get('/api/auth/me', options)
  }

  getUsers() {
    return this.get('/api/admin/users')
  }

  adminCreateUser(data) {
    return this.post('/api/admin/users', data)
  }

  // Public (no auth)
  getPublicTelemetry() {
    return this.get('/api/public/telemetry')
  }

  getPublicTelemetryHistory(hours = 24) {
    return this.get(`/api/public/telemetry/history?hours=${hours}`)
  }

  getPublicPhotos(limit = 30, offset = 0) {
    return this.get(`/api/public/photos?limit=${limit}&offset=${offset}`)
  }

  getPublicLatestPhoto() {
    return this.get('/api/public/photos/latest')
  }

  getPublicWeather(hours = 48) {
    return this.get(`/api/public/weather?hours=${hours}`)
  }

  getPublicCrops() {
    return this.get('/api/public/crops')
  }

  // Admin actions
  adminControlActuator(actuator, state) {
    return this.post('/api/admin/actuators/control', { actuator, state })
  }

  adminApplyConfig(config) {
    return this.post('/api/admin/config', config)
  }

  adminCreateCrop(data) {
    return this.post('/api/admin/crops', data)
  }

  adminUpdateCrop(id, data) {
    return this.put(`/api/admin/crops/${id}`, data)
  }

  adminDeleteCrop(id) {
    return this.delete(`/api/admin/crops/${id}`)
  }

  adminCreateCropParams(cropId, data) {
    return this.post(`/api/admin/crops/${cropId}/params`, data)
  }

  adminUpdateCropParams(cropId, data) {
    return this.put(`/api/admin/crops/${cropId}/params`, data)
  }

  getAdminLogs({ action, username, user_id, since, until, limit = 100, offset = 0 } = {}) {
    const params = new URLSearchParams()
    if (action) params.append('action', action)
    if (username) params.append('username', username)
    if (user_id) params.append('user_id', user_id)
    if (since) params.append('since', since)
    if (until) params.append('until', until)
    params.append('limit', limit)
    params.append('offset', offset)
    return this.get(`/api/admin/logs?${params.toString()}`)
  }

  getAdminHealth() {
    return this.get('/api/admin/health')
  }

  // Crops
  getCrops() {
    return this.get('/api/crops')
  }

  getAllCrops() {
    return this.get('/api/crops/all')
  }

  getCrop(id) {
    return this.get(`/api/crops/${id}`)
  }

  createCrop(data) {
    return this.post('/api/crops', data)
  }

  updateCrop(id, data) {
    return this.put(`/api/crops/${id}`, data)
  }

  deleteCrop(id) {
    return this.delete(`/api/crops/${id}`)
  }

  getCropParams(cropId) {
    return this.get(`/api/crops/${cropId}/params`)
  }

  createCropParams(cropId, data) {
    return this.post(`/api/crops/${cropId}/params`, data)
  }

  updateCropParams(cropId, data) {
    return this.put(`/api/crops/${cropId}/params`, data)
  }

  // Config
  getActiveConfig() {
    return this.get('/api/config/active')
  }

  getConfigHistory(limit = 50) {
    return this.get(`/api/config/history?limit=${limit}`)
  }

  applyConfig(config) {
    return this.post('/api/config/apply', config)
  }

  updateActiveConfig(data) {
    return this.put('/api/config/active', data)
  }

  getLatestTelemetry() {
    return this.get('/api/config/telemetry/latest')
  }

  getTelemetryHistory(hours = 24, limit = 1000) {
    return this.get(`/api/config/telemetry/history?hours=${hours}&limit=${limit}`)
  }

  getSystemStatus() {
    return this.get('/api/config/status')
  }

  // Weather
  getWeather(hours = 48) {
    return this.get(`/api/weather/overview?hours=${hours}`)
  }

  commandActuator(actuator, state) {
    return this.post(`/api/actuators/${actuator}/command`, { state })
  }

  // Photos
  getPhotos(limit = 50, offset = 0) {
    return this.get(`/api/photos?limit=${limit}&offset=${offset}`)
  }

  getLatestPhoto() {
    return this.get('/api/photos/latest')
  }

  // Notifications (Web Push)
  getNotificationConfig() {
    return this.get('/api/notifications/config')
  }

  subscribePush(subscription) {
    return this.post('/api/notifications/subscribe', subscription)
  }

  unsubscribePush(endpoint) {
    return this.request('/api/notifications/subscribe', {
      method: 'DELETE',
      body: JSON.stringify({ endpoint }),
    })
  }

  sendTestNotification() {
    return this.post('/api/notifications/test', {})
  }

  // Events
  getEvents(severity, limit = 100) {
    const params = new URLSearchParams()
    if (severity) params.append('severity', severity)
    params.append('limit', limit)
    return this.get(`/api/events?${params.toString()}`)
  }

  getUnacknowledgedEvents() {
    return this.get('/api/events/unacknowledged')
  }

  acknowledgeEvent(id) {
    return this.post(`/api/events/${id}/acknowledge`)
  }
}

export const api = new ApiClient()
