import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { api } from '../api'

export function Crops() {
  const { isAdmin } = useAuth()
  const [crops, setCrops] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingCrop, setEditingCrop] = useState(null)
  const [formData, setFormData] = useState({
    name: '', display_name: '', description: '',
    temp_min: '', temp_max: '', temp_night_min: '', temp_night_max: '',
    humidity_min: '', humidity_max: '',
    soil_moisture_min_pct: '', soil_moisture_max_pct: '',
    hysteresis_temp_on: '', hysteresis_temp_off: '',
    hysteresis_humidity_on: '', hysteresis_humidity_off: '',
    hysteresis_soil_on: '', hysteresis_soil_off: '',
    source_reference: '', source_url: '', notes: '',
  })

  const loadCrops = async () => {
    setLoading(true)
    try {
      const data = await api.getAllCrops()
      setCrops(data)
    } catch (e) {
      console.error('Failed to load crops:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadCrops() }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!isAdmin) return

    const cropData = {
      name: formData.name,
      display_name: formData.display_name,
      description: formData.description,
    }

    const paramsData = {
      temp_min: formData.temp_min ? Number(formData.temp_min) : null,
      temp_max: formData.temp_max ? Number(formData.temp_max) : null,
      temp_night_min: formData.temp_night_min ? Number(formData.temp_night_min) : null,
      temp_night_max: formData.temp_night_max ? Number(formData.temp_night_max) : null,
      humidity_min: formData.humidity_min ? Number(formData.humidity_min) : null,
      humidity_max: formData.humidity_max ? Number(formData.humidity_max) : null,
      soil_moisture_min_pct: formData.soil_moisture_min_pct ? Number(formData.soil_moisture_min_pct) : null,
      soil_moisture_max_pct: formData.soil_moisture_max_pct ? Number(formData.soil_moisture_max_pct) : null,
      hysteresis_temp_on: formData.hysteresis_temp_on ? Number(formData.hysteresis_temp_on) : null,
      hysteresis_temp_off: formData.hysteresis_temp_off ? Number(formData.hysteresis_temp_off) : null,
      hysteresis_humidity_on: formData.hysteresis_humidity_on ? Number(formData.hysteresis_humidity_on) : null,
      hysteresis_humidity_off: formData.hysteresis_humidity_off ? Number(formData.hysteresis_humidity_off) : null,
      hysteresis_soil_on: formData.hysteresis_soil_on ? Number(formData.hysteresis_soil_on) : null,
      hysteresis_soil_off: formData.hysteresis_soil_off ? Number(formData.hysteresis_soil_off) : null,
      source_reference: formData.source_reference || null,
      source_url: formData.source_url || null,
      notes: formData.notes || null,
    }

    try {
      if (editingCrop) {
        await api.updateCrop(editingCrop.id, cropData)
        try {
          await api.updateCropParams(editingCrop.id, paramsData)
        } catch {
          await api.createCropParams(editingCrop.id, { ...paramsData, crop_id: editingCrop.id })
        }
      } else {
        const newCrop = await api.createCrop(cropData)
        await api.createCropParams(newCrop.id, { ...paramsData, crop_id: newCrop.id })
      }
      setShowForm(false)
      setEditingCrop(null)
      resetForm()
      loadCrops()
    } catch (e) {
      console.error('Failed to save crop:', e)
      alert('Error: ' + e.message)
    }
  }

  const handleEdit = async (crop) => {
    let fullCrop = crop
    try {
      fullCrop = await api.getCrop(crop.id)
    } catch (e) {
      console.error('Failed to load crop params:', e)
    }
    const p = fullCrop.params || {}
    setEditingCrop(fullCrop)
    setFormData({
      name: fullCrop.name,
      display_name: fullCrop.display_name,
      description: fullCrop.description || '',
      temp_min: p.temp_min ?? '',
      temp_max: p.temp_max ?? '',
      temp_night_min: p.temp_night_min ?? '',
      temp_night_max: p.temp_night_max ?? '',
      humidity_min: p.humidity_min ?? '',
      humidity_max: p.humidity_max ?? '',
      soil_moisture_min_pct: p.soil_moisture_min_pct ?? '',
      soil_moisture_max_pct: p.soil_moisture_max_pct ?? '',
      hysteresis_temp_on: p.hysteresis_temp_on ?? '',
      hysteresis_temp_off: p.hysteresis_temp_off ?? '',
      hysteresis_humidity_on: p.hysteresis_humidity_on ?? '',
      hysteresis_humidity_off: p.hysteresis_humidity_off ?? '',
      hysteresis_soil_on: p.hysteresis_soil_on ?? '',
      hysteresis_soil_off: p.hysteresis_soil_off ?? '',
      source_reference: p.source_reference || '',
      source_url: p.source_url || '',
      notes: p.notes || '',
    })
    setShowForm(true)
  }

  const handleNew = () => {
    setEditingCrop(null)
    resetForm()
    setShowForm(true)
  }

  const handleDelete = async (id) => {
    if (!confirm('¿Desactivar este cultivo?')) return
    try {
      await api.deleteCrop(id)
      loadCrops()
    } catch (e) {
      alert('Error: ' + e.message)
    }
  }

  const resetForm = () => {
    setFormData({
      name: '', display_name: '', description: '',
      temp_min: '', temp_max: '', temp_night_min: '', temp_night_max: '',
      humidity_min: '', humidity_max: '',
      soil_moisture_min_pct: '', soil_moisture_max_pct: '',
      hysteresis_temp_on: '', hysteresis_temp_off: '',
      hysteresis_humidity_on: '', hysteresis_humidity_off: '',
      hysteresis_soil_on: '', hysteresis_soil_off: '',
      source_reference: '', source_url: '', notes: '',
    })
  }

  if (!isAdmin) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
        <h2>Acceso denegado</h2>
        <p style={{ color: 'var(--color-text-muted)', marginTop: '1rem' }}>Se requieren permisos de administrador</p>
      </div>
    )
  }

  if (loading) return <div style={{ textAlign: 'center', padding: '2rem' }}>Cargando...</div>

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Catálogo de Cultivos</h1>
        <button onClick={handleNew} className="btn btn-primary">+ Nuevo Cultivo</button>
      </div>

      {showForm && (
        <div className="modal-overlay" onClick={() => setShowForm(false)}>
          <div className="modal" style={{ maxWidth: '700px' }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">{editingCrop ? 'Editar' : 'Nuevo'} Cultivo</h3>
              <button onClick={() => setShowForm(false)} style={{ fontSize: '1.5rem', color: 'var(--color-text-muted)' }}>×</button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="modal-body" style={{ maxHeight: '70vh', overflow: 'auto' }}>
                <div className="grid grid-2" style={{ gap: '1rem' }}>
                  <div className="form-group">
                    <label className="form-label">Nombre interno *</label>
                    <input value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} className="form-control" placeholder="tomate" required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Nombre visible *</label>
                    <input value={formData.display_name} onChange={e => setFormData({...formData, display_name: e.target.value})} className="form-control" placeholder="Tomate" required />
                  </div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}>
                    <label className="form-label">Descripción</label>
                    <textarea value={formData.description} onChange={e => setFormData({...formData, description: e.target.value})} className="form-control" rows={2} />
                  </div>
                </div>

                <hr style={{ margin: '1rem 0', borderColor: 'var(--color-border)' }} />

                <h4 style={{ marginBottom: '1rem', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>🌡️ Temperatura (&deg;C)</h4>
                <div className="grid grid-4">
                  <div className="form-group"><label className="form-label">Mín crecimiento</label><input type="number" step="0.1" value={formData.temp_min} onChange={e => setFormData({...formData, temp_min: e.target.value})} className="form-control" /></div>
                  <div className="form-group"><label className="form-label">Máx crecimiento</label><input type="number" step="0.1" value={formData.temp_max} onChange={e => setFormData({...formData, temp_max: e.target.value})} className="form-control" /></div>
                  <div className="form-group"><label className="form-label">Óptima noche mín</label><input type="number" step="0.1" value={formData.temp_night_min} onChange={e => setFormData({...formData, temp_night_min: e.target.value})} className="form-control" /></div>
                  <div className="form-group"><label className="form-label">Óptima noche máx</label><input type="number" step="0.1" value={formData.temp_night_max} onChange={e => setFormData({...formData, temp_night_max: e.target.value})} className="form-control" /></div>
                </div>

                <h4 style={{ margin: '1rem 0', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>💧 Humedad Ambiental (%)</h4>
                <div className="grid grid-2">
                  <div className="form-group"><label className="form-label">Mínima</label><input type="number" step="0.1" value={formData.humidity_min} onChange={e => setFormData({...formData, humidity_min: e.target.value})} className="form-control" /></div>
                  <div className="form-group"><label className="form-label">Máxima</label><input type="number" step="0.1" value={formData.humidity_max} onChange={e => setFormData({...formData, humidity_max: e.target.value})} className="form-control" /></div>
                </div>

                <h4 style={{ margin: '1rem 0', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>🌿 Humedad Suelo (%)</h4>
                <div className="grid grid-2">
                  <div className="form-group"><label className="form-label">Mínima</label><input type="number" step="1" value={formData.soil_moisture_min_pct} onChange={e => setFormData({...formData, soil_moisture_min_pct: e.target.value})} className="form-control" /></div>
                  <div className="form-group"><label className="form-label">Máxima</label><input type="number" step="1" value={formData.soil_moisture_max_pct} onChange={e => setFormData({...formData, soil_moisture_max_pct: e.target.value})} className="form-control" /></div>
                </div>

                <hr style={{ margin: '1rem 0', borderColor: 'var(--color-border)' }} />

                <h4 style={{ marginBottom: '1rem', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>⚙️ Histéresis (umbrales de actuación)</h4>
                <div className="grid grid-2">
                  <div className="form-group"><label className="form-label">Temp ON &gt; &deg;C</label><input type="number" step="0.1" value={formData.hysteresis_temp_on} onChange={e => setFormData({...formData, hysteresis_temp_on: e.target.value})} className="form-control" /></div>
                  <div className="form-group"><label className="form-label">Temp OFF &lt; &deg;C</label><input type="number" step="0.1" value={formData.hysteresis_temp_off} onChange={e => setFormData({...formData, hysteresis_temp_off: e.target.value})} className="form-control" /></div>
                  <div className="form-group"><label className="form-label">Hum ON &lt; %</label><input type="number" step="0.1" value={formData.hysteresis_humidity_on} onChange={e => setFormData({...formData, hysteresis_humidity_on: e.target.value})} className="form-control" /></div>
                  <div className="form-group"><label className="form-label">Hum OFF &gt; %</label><input type="number" step="0.1" value={formData.hysteresis_humidity_off} onChange={e => setFormData({...formData, hysteresis_humidity_off: e.target.value})} className="form-control" /></div>
                  <div className="form-group"><label className="form-label">Suelo ON &lt; %</label><input type="number" step="1" value={formData.hysteresis_soil_on} onChange={e => setFormData({...formData, hysteresis_soil_on: e.target.value})} className="form-control" /></div>
                  <div className="form-group"><label className="form-label">Suelo OFF &gt; %</label><input type="number" step="1" value={formData.hysteresis_soil_off} onChange={e => setFormData({...formData, hysteresis_soil_off: e.target.value})} className="form-control" /></div>
                </div>

                <hr style={{ margin: '1rem 0', borderColor: 'var(--color-border)' }} />

                <h4 style={{ marginBottom: '1rem', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>📚 Referencia Bibliográfica</h4>
                <div className="form-group"><label className="form-label">Referencia (cita corta)</label><input value={formData.source_reference} onChange={e => setFormData({...formData, source_reference: e.target.value})} className="form-control" placeholder="FAO a1374s; INTA hortalizas..." /></div>
                <div className="form-group"><label className="form-label">URL fuente</label><input type="url" value={formData.source_url} onChange={e => setFormData({...formData, source_url: e.target.value})} className="form-control" placeholder="https://..." /></div>
                <div className="form-group"><label className="form-label">Notas</label><textarea value={formData.notes} onChange={e => setFormData({...formData, notes: e.target.value})} className="form-control" rows={2} /></div>
              </div>
              <div className="modal-footer">
                <button type="button" onClick={() => setShowForm(false)} className="btn btn-secondary">Cancelar</button>
                <button type="submit" className="btn btn-primary">{editingCrop ? 'Actualizar' : 'Crear'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="card">
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Temp Día (&deg;C)</th>
                <th>Temp Noche (&deg;C)</th>
                <th>Humedad (%)</th>
                <th>Suelo (%)</th>
                <th>Histéresis T&deg;</th>
                <th>Fuente</th>
                <th style={{ width: '120px' }}></th>
              </tr>
            </thead>
            <tbody>
              {crops.map(crop => (
                <tr key={crop.id}>
                  <td>
                    <strong>{crop.display_name}</strong>
                    <br />
                    <small style={{ color: 'var(--color-text-muted)' }}>{crop.name}</small>
                    {crop.description && <br />}
                    {crop.description && <small style={{ color: 'var(--color-text-muted)' }}>{crop.description}</small>}
                  </td>
                  <td>{crop.params?.temp_min != null ? `${crop.params.temp_min}–${crop.params.temp_max}` : '—'}</td>
                  <td>{crop.params?.temp_night_min != null ? `${crop.params.temp_night_min}–${crop.params.temp_night_max}` : '—'}</td>
                  <td>{crop.params?.humidity_min != null ? `${crop.params.humidity_min}–${crop.params.humidity_max}` : '—'}</td>
                  <td>{crop.params?.soil_moisture_min_pct != null ? `${crop.params.soil_moisture_min_pct}–${crop.params.soil_moisture_max_pct}` : '—'}</td>
                  <td>
                    {crop.params?.hysteresis_temp_on != null ? `ON>${crop.params.hysteresis_temp_on} OFF<${crop.params.hysteresis_temp_off}` : '—'}
                  </td>
                  <td>
                    {crop.params?.source_reference && (
                      <a href={crop.params.source_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.75rem' }}>
                        {crop.params.source_reference}
                      </a>
                    )}
                  </td>
                  <td>
                    <button onClick={() => handleEdit(crop)} className="btn btn-secondary btn-sm" style={{ marginRight: '0.25rem' }}>Editar</button>
                    {!crop.is_active && <span className="badge badge-off">Inactivo</span>}
                    {crop.is_active && <button onClick={() => handleDelete(crop.id)} className="btn btn-danger btn-sm">Desactivar</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}