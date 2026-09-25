export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
export const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/api/config/ws'

class ApiClient {
  constructor() {
    this.token = localStorage.getItem('token')
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
    this.token = token
    if (token) {
      localStorage.setItem('token', token)
    } else {
      localStorage.removeItem('token')
    }
  }

  getHeaders() {
    const headers = { 'Content-Type': 'application/json' }
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }
    return headers
  }

  async request(endpoint, options = {}) {
    const response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers: {
        ...this.getHeaders(),
        ...options.headers,
      },
    })

    if (response.status === 401) {
      this.setToken(null)
      window.location.href = '/login'
      throw new Error('Unauthorized')
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Error' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    if (response.status === 204) return null
    return response.json()
  }

  get(endpoint) {
    return this.request(endpoint, { method: 'GET' })
  }

  post(endpoint, data) {
    return this.request(endpoint, { method: 'POST', body: JSON.stringify(data) })
  }

  put(endpoint, data) {
    return this.request(endpoint, { method: 'PUT', body: JSON.stringify(data) })
  }

  delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' })
  }

  // Auth
  login(username, password) {
    return this.post('/api/auth/login', { username, password })
  }

  register(data) {
    return this.post('/api/auth/register', data)
  }

  me() {
    return this.get('/api/auth/me')
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

  confirmConfig(version) {
    return this.post(`/api/config/confirm/${version}`)
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

  // Photos
  getPhotos(limit = 50, offset = 0) {
    return this.get(`/api/photos?limit=${limit}&offset=${offset}`)
  }

  getLatestPhoto() {
    return this.get('/api/photos/latest')
  }

  getPhoto(id) {
    return this.get(`/api/photos/${id}`)
  }

  getPhotoFile(id) {
    return `${API_URL}/api/photos/${id}/file`
  }

  getLatestPhotoFile() {
    return `${API_URL}/api/photos/latest/file`
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