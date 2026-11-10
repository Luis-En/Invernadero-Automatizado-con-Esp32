import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { api } from '../api'
import { format } from 'date-fns'

export function Config() {
  const { isAdmin } = useAuth()
  const [activeConfig, setActiveConfig] = useState(null)
  const [history, setHistory] = useState([])
  const [crops, setCrops] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [notice, setNotice] = useState('')
  const [formData, setFormData] = useState({
    hysteresis: {
      temp: { on_above: 30, off_below: 27.5 },
      humidity: { on_below: 60, off_above: 68 },
      soil: { on_below_pct: 35, off_above_pct: 45 },
    },
    irrigation: { enabled: false },
    safety: {
      max_on_seconds: { fan: 7200, humidifier: 7200, pump: 900 },
    },
  })
  const [selectedCropId, setSelectedCropId] = useState('')

  const loadData = async () => {
    setLoading(true)
    try {
      const [config, hist, cropList] = await Promise.all([
        api.getActiveConfig(),
        api.getConfigHistory(20),
        api.getCrops(),
      ])
      setActiveConfig(config)
      setHistory(hist)
      setCrops(cropList)
      if (config) {
        setFormData(config.config_json)
        setSelectedCropId(config.crop_id?.toString() || '')
      }
    } catch (e) {
      console.error('Failed to load config:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleChange = (path, value) => {
    setFormData(prev => {
      const newObj = JSON.parse(JSON.stringify(prev))
      const keys = path.split('.')
      let obj = newObj
      for (let i = 0; i < keys.length - 1; i++) {
        obj = obj[keys[i]]
      }
      obj[keys[keys.length - 1]] = value
      return newObj
    })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!isAdmin) return
    setSaving(true)
    setSaveError('')
    setNotice('')
    try {
      await api.adminApplyConfig({
        config_json: formData,
        crop_id: selectedCropId ? Number(selectedCropId) : null,
      })
      await loadData()
      setNotice('Configuración aplicada correctamente.')
    } catch (e) {
      console.error('Failed to save config:', e)
      setSaveError('Error al guardar: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleCropSelect = async (cropId) => {
    setSelectedCropId(cropId)
    if (!cropId) return
    try {
      const params = await api.getCropParams(cropId)
      setFormData(prev => ({
        ...prev,
        hysteresis: {
          temp: { on_above: params.hysteresis_temp_on ?? 30, off_below: params.hysteresis_temp_off ?? 27.5 },
          humidity: { on_below: params.hysteresis_humidity_on ?? 60, off_above: params.hysteresis_humidity_off ?? 68 },
          soil: { on_below_pct: params.hysteresis_soil_on ?? 35, off_above_pct: params.hysteresis_soil_off ?? 45 },
        },
        irrigation: prev.irrigation ?? { enabled: false },
        safety: prev.safety,
      }))
    } catch (e) {
      console.error('Failed to load crop params:', e)
    }
  }

  if (!isAdmin) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
        <h2>Acceso denegado</h2>
        <p style={{ color: 'var(--color-text-muted)', marginTop: '1rem' }}>Se requieren permisos de administrador</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="loading-state" role="status" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <p>Cargando configuración…</p>
      </div>
    )
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Configuración del Sistema</h1>
      </div>

      <div className="grid grid-2" style={{ gap: '1.5rem' }}>
        <div className="card">
          <div className="card-header">⚙️ Configuración Activa v{activeConfig?.version || '—'}</div>
          <div className="card-body">
            {activeConfig?.crop_id && (
              <p style={{ marginBottom: '1rem', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                Cultivo: <strong>{crops.find(c => c.id === activeConfig.crop_id)?.display_name || activeConfig.crop_id}</strong>
              </p>
            )}

            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label" htmlFor="config-crop">
                  Cultivo activo
                </label>
                <select
                  id="config-crop"
                  aria-label="Cultivo activo"
                  value={selectedCropId}
                  onChange={e => handleCropSelect(e.target.value)}
                  className="form-control"
                >
                  <option value="">— Seleccionar cultivo —</option>
                  {crops.map(c => <option key={c.id} value={c.id}>{c.display_name}</option>)}
                </select>
              </div>

              <fieldset style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '1rem', marginBottom: '1rem' }}>
                <legend style={{ fontWeight: 600, padding: '0 0.5rem', fontSize: '0.875rem', background: 'var(--color-card)' }}>🌡️ Temperatura</legend>
                <div className="grid grid-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="config-temp-on">Encender ventilación &gt; °C</label>
                    <input id="config-temp-on" aria-label="Encender ventilación por encima de grados" type="number" step="0.1" min="0" max="50"
                      value={formData.hysteresis?.temp?.on_above ?? 30}
                      onChange={e => handleChange('hysteresis.temp.on_above', Number(e.target.value))}
                      className="form-control" />
                  </div>
                  <div className="form-group">
                    <label className="form-label" htmlFor="config-temp-off">Apagar ventilación &lt; °C</label>
                    <input id="config-temp-off" aria-label="Apagar ventilación por debajo de grados" type="number" step="0.1" min="0" max="50"
                      value={formData.hysteresis?.temp?.off_below ?? 27.5}
                      onChange={e => handleChange('hysteresis.temp.off_below', Number(e.target.value))}
                      className="form-control" />
                  </div>
                </div>
              </fieldset>

              <fieldset style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '1rem', marginBottom: '1rem' }}>
                <legend style={{ fontWeight: 600, padding: '0 0.5rem', fontSize: '0.875rem', background: 'var(--color-card)' }}>💧 Humedad ambiental</legend>
                <div className="grid grid-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="config-hum-on">Encender humidificación &lt; %</label>
                    <input id="config-hum-on" aria-label="Encender humidificación por debajo de porcentaje" type="number" step="0.1" min="0" max="100"
                      value={formData.hysteresis?.humidity?.on_below ?? 60}
                      onChange={e => handleChange('hysteresis.humidity.on_below', Number(e.target.value))}
                      className="form-control" />
                  </div>
                  <div className="form-group">
                    <label className="form-label" htmlFor="config-hum-off">Apagar humidificación &gt; %</label>
                    <input id="config-hum-off" aria-label="Apagar humidificación por encima de porcentaje" type="number" step="0.1" min="0" max="100"
                      value={formData.hysteresis?.humidity?.off_above ?? 68}
                      onChange={e => handleChange('hysteresis.humidity.off_above', Number(e.target.value))}
                      className="form-control" />
                  </div>
                </div>
              </fieldset>

              <fieldset style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '1rem', marginBottom: '1rem' }}>
                <legend style={{ fontWeight: 600, padding: '0 0.5rem', fontSize: '0.875rem', background: 'var(--color-card)' }}>🌿 Humedad del suelo</legend>
                <div className="grid grid-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="config-soil-on">Encender riego &lt; %</label>
                    <input id="config-soil-on" aria-label="Encender riego por debajo de porcentaje" type="number" step="1" min="0" max="100"
                      value={formData.hysteresis?.soil?.on_below_pct ?? 35}
                      onChange={e => handleChange('hysteresis.soil.on_below_pct', Number(e.target.value))}
                      className="form-control" />
                    <p className="form-hint">Umbral que dispara la alerta de riego.</p>
                  </div>
                  <div className="form-group">
                    <label className="form-label" htmlFor="config-soil-off">Apagar riego &gt; %</label>
                    <input id="config-soil-off" aria-label="Apagar riego por encima de porcentaje" type="number" step="1" min="0" max="100"
                      value={formData.hysteresis?.soil?.off_above_pct ?? 45}
                      onChange={e => handleChange('hysteresis.soil.off_above_pct', Number(e.target.value))}
                      className="form-control" />
                    <p className="form-hint">Humedad a la que se considera recuperado.</p>
                  </div>
                </div>
              </fieldset>

              <fieldset style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '1rem', marginBottom: '1rem' }}>
                <legend style={{ fontWeight: 600, padding: '0 0.5rem', fontSize: '0.875rem', background: 'var(--color-card)' }}>🚿 Riego</legend>
                <label className="form-label" htmlFor="config-irrigation-enabled" style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', cursor: 'pointer', fontWeight: 500, minHeight: '44px' }}>
                  <input id="config-irrigation-enabled" type="checkbox"
                    checked={formData.irrigation?.enabled}
                    onChange={e => handleChange('irrigation.enabled', e.target.checked)}
                    aria-label="Habilitar riego automático"
                    style={{ width: 20, height: 20, marginTop: 2 }}
                  />
                  <span>Habilitar riego automático (requiere fuente de agua verificada)</span>
                </label>
                <p style={{ marginTop: '0.5rem', fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
                  ⚠️ La bomba 0.5HP 110V tiene ciclo máximo 15min ON / 5min OFF. Verificar contacto y breaker 15A.
                </p>
              </fieldset>

              <div className="modal-footer" style={{ borderTop: 'none', padding: '0.5rem 0 0' }}>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? 'Guardando…' : 'Aplicar Configuración'}
                </button>
              </div>
            </form>

            {saveError && (
              <div className="alert alert-critical" role="alert" style={{ marginTop: '1rem' }}>
                {saveError}
              </div>
            )}

            {notice && (
              <div className="alert alert-success" role="status" style={{ marginTop: '1rem' }}>
                {notice}
              </div>
            )}

            {activeConfig && !activeConfig.esp32_confirmed && (
              <div className="alert alert-warning" role="status" style={{ marginTop: '1rem' }}>
                ⚠️ Configuración pendiente de confirmación por ESP32 de campo
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-header">📋 Historial de Cambios</div>
          <div className="card-body" style={{ padding: 0 }}>
            <div
              className="table-container"
              tabIndex={0}
              role="region"
              aria-label="Historial de configuraciones aplicadas"
            >
              <table className="table-cards">
                <caption className="visually-hidden">Historial de configuraciones aplicadas</caption>
                <thead>
                  <tr>
                    <th scope="col" style={{ width: '160px' }}>Fecha</th>
                    <th scope="col" style={{ width: '80px' }}>Versión</th>
                    <th scope="col" style={{ width: '120px' }}>Cultivo</th>
                    <th scope="col">Motivo</th>
                    <th scope="col" style={{ width: '100px' }}>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map(h => (
                    <tr key={h.id}>
                      <td data-label="Fecha">{format(new Date(h.created_at), 'dd/MM HH:mm')}</td>
                      <td data-label="Versión">v{h.version}</td>
                      <td data-label="Cultivo">{crops.find(c => c.id === h.crop_id)?.display_name || '—'}</td>
                      <td data-label="Motivo">{h.change_reason || '—'}</td>
                      <td data-label="Estado">
                        <span className={`badge ${h.id === activeConfig?.id ? 'badge-on' : 'badge-off'}`}>
                          {h.id === activeConfig?.id ? 'Activa' : 'Histórica'}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {history.length === 0 && <tr><td colSpan={5} style={{ textAlign: 'center', padding: '2rem', color: 'var(--color-text-muted)' }}>Sin historial</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}