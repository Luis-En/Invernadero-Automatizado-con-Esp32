import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { api } from '../api'
import { Modal } from '../components/Modal'

// Only render known-safe schemes as links; a malicious source_url must never
// become a clickable javascript: URL.
function safeExternalUrl(value) {
  if (!value) return null
  try {
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) ? url.toString() : null
  } catch {
    return null
  }
}

const EMPTY_FORM = {
  name: '',
  display_name: '',
  description: '',
  temp_min: '',
  temp_max: '',
  temp_night_min: '',
  temp_night_max: '',
  humidity_min: '',
  humidity_max: '',
  soil_moisture_min_pct: '',
  soil_moisture_max_pct: '',
  hysteresis_temp_on: '',
  hysteresis_temp_off: '',
  hysteresis_humidity_on: '',
  hysteresis_humidity_off: '',
  hysteresis_soil_on: '',
  hysteresis_soil_off: '',
  source_reference: '',
  source_url: '',
  notes: '',
}

function TextField({ id, label, value, onChange, type = 'text', ...props }) {
  return (
    <div className="form-group">
      <label className="form-label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={event => onChange(event.target.value)}
        className="form-control"
        aria-label={label}
        {...props}
      />
    </div>
  )
}

function NumberField({ id, label, value, onChange, step = '0.1' }) {
  return (
    <div className="form-group">
      <label className="form-label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        type="number"
        step={step}
        inputMode="decimal"
        value={value}
        onChange={event => onChange(event.target.value)}
        className="form-control"
        aria-label={label}
      />
    </div>
  )
}

export function Crops() {
  const { isAdmin } = useAuth()
  const [crops, setCrops] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingCrop, setEditingCrop] = useState(null)
  const [formData, setFormData] = useState(EMPTY_FORM)
  const [formError, setFormError] = useState('')
  const [pageError, setPageError] = useState('')

  const loadCrops = async () => {
    setLoading(true)
    setPageError('')
    try {
      const data = await api.getAllCrops()
      setCrops(data)
    } catch (e) {
      setPageError(e.message || 'No se pudieron cargar los cultivos')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCrops()
  }, [])

  const setField = (field, value) => setFormData(previous => ({ ...previous, [field]: value }))

  const handleSubmit = async event => {
    event.preventDefault()
    if (!isAdmin) return
    setFormError('')

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
      soil_moisture_min_pct: formData.soil_moisture_min_pct
        ? Number(formData.soil_moisture_min_pct)
        : null,
      soil_moisture_max_pct: formData.soil_moisture_max_pct
        ? Number(formData.soil_moisture_max_pct)
        : null,
      hysteresis_temp_on: formData.hysteresis_temp_on ? Number(formData.hysteresis_temp_on) : null,
      hysteresis_temp_off: formData.hysteresis_temp_off
        ? Number(formData.hysteresis_temp_off)
        : null,
      hysteresis_humidity_on: formData.hysteresis_humidity_on
        ? Number(formData.hysteresis_humidity_on)
        : null,
      hysteresis_humidity_off: formData.hysteresis_humidity_off
        ? Number(formData.hysteresis_humidity_off)
        : null,
      hysteresis_soil_on: formData.hysteresis_soil_on
        ? Number(formData.hysteresis_soil_on)
        : null,
      hysteresis_soil_off: formData.hysteresis_soil_off
        ? Number(formData.hysteresis_soil_off)
        : null,
      source_reference: formData.source_reference || null,
      source_url: formData.source_url || null,
      notes: formData.notes || null,
    }

    try {
      if (editingCrop) {
        await api.adminUpdateCrop(editingCrop.id, cropData)
        try {
          await api.adminUpdateCropParams(editingCrop.id, paramsData)
        } catch {
          await api.adminCreateCropParams(editingCrop.id, { ...paramsData, crop_id: editingCrop.id })
        }
      } else {
        const newCrop = await api.adminCreateCrop(cropData)
        await api.adminCreateCropParams(newCrop.id, { ...paramsData, crop_id: newCrop.id })
      }
      setShowForm(false)
      setEditingCrop(null)
      setFormData(EMPTY_FORM)
      loadCrops()
    } catch (e) {
      setFormError('No se pudo guardar: ' + e.message)
    }
  }

  const handleEdit = async crop => {
    setFormError('')
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
    setFormError('')
    setFormData(EMPTY_FORM)
    setShowForm(true)
  }

  const handleDelete = async id => {
    if (!window.confirm('¿Desactivar este cultivo?')) return
    try {
      await api.adminDeleteCrop(id)
      loadCrops()
    } catch (e) {
      setPageError('No se pudo desactivar: ' + e.message)
    }
  }

  if (!isAdmin) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
        <h2>Acceso denegado</h2>
        <p style={{ color: 'var(--color-text-muted)', marginTop: '1rem' }}>
          Se requieren permisos de administrador
        </p>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="loading-state" role="status" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <p>Cargando cultivos…</p>
      </div>
    )
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Catálogo de Cultivos</h1>
          <p className="page-subtitle">
            Parámetros agronómicos y umbrales de histéresis por cultivo.
          </p>
        </div>
        <button onClick={handleNew} className="btn btn-primary">
          + Nuevo Cultivo
        </button>
      </div>

      {pageError && (
        <div className="alert alert-critical" role="alert">
          {pageError}
        </div>
      )}

      <Modal
        open={showForm}
        onClose={() => setShowForm(false)}
        title={`${editingCrop ? 'Editar' : 'Nuevo'} Cultivo`}
        size="lg"
        footer={
          <>
            <button type="button" onClick={() => setShowForm(false)} className="btn btn-secondary">
              Cancelar
            </button>
            <button type="submit" form="crop-form" className="btn btn-primary">
              {editingCrop ? 'Actualizar' : 'Crear'}
            </button>
          </>
        }
      >
        <form id="crop-form" onSubmit={handleSubmit}>
          {formError && (
            <div className="alert alert-critical" role="alert">
              {formError}
            </div>
          )}

          <div className="grid grid-2" style={{ gap: '0 1rem' }}>
            <TextField
              id="crop-name"
              label="Nombre interno *"
              value={formData.name}
              onChange={value => setField('name', value)}
              placeholder="tomate"
              required
              autoComplete="off"
            />
            <TextField
              id="crop-display-name"
              label="Nombre visible *"
              value={formData.display_name}
              onChange={value => setField('display_name', value)}
              placeholder="Tomate"
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="crop-description">
              Descripción
            </label>
            <textarea
              id="crop-description"
              aria-label="Descripción"
              value={formData.description}
              onChange={event => setField('description', event.target.value)}
              className="form-control"
              rows={2}
            />
          </div>

          <hr style={{ margin: '1rem 0', borderColor: 'var(--color-border)' }} />

          <h3 className="form-label">🌡️ Temperatura (°C)</h3>
          <div className="grid grid-4" style={{ gap: '0 1rem' }}>
            <NumberField id="crop-temp-min" label="Mín crecimiento" value={formData.temp_min} onChange={value => setField('temp_min', value)} />
            <NumberField id="crop-temp-max" label="Máx crecimiento" value={formData.temp_max} onChange={value => setField('temp_max', value)} />
            <NumberField id="crop-temp-night-min" label="Óptima noche mín" value={formData.temp_night_min} onChange={value => setField('temp_night_min', value)} />
            <NumberField id="crop-temp-night-max" label="Óptima noche máx" value={formData.temp_night_max} onChange={value => setField('temp_night_max', value)} />
          </div>

          <h3 className="form-label">💧 Humedad Ambiental (%)</h3>
          <div className="grid grid-2" style={{ gap: '0 1rem' }}>
            <NumberField id="crop-humidity-min" label="Mínima" value={formData.humidity_min} onChange={value => setField('humidity_min', value)} />
            <NumberField id="crop-humidity-max" label="Máxima" value={formData.humidity_max} onChange={value => setField('humidity_max', value)} />
          </div>

          <h3 className="form-label">🌿 Humedad Suelo (%)</h3>
          <div className="grid grid-2" style={{ gap: '0 1rem' }}>
            <NumberField id="crop-soil-min" label="Mínima" step="1" value={formData.soil_moisture_min_pct} onChange={value => setField('soil_moisture_min_pct', value)} />
            <NumberField id="crop-soil-max" label="Máxima" step="1" value={formData.soil_moisture_max_pct} onChange={value => setField('soil_moisture_max_pct', value)} />
          </div>

          <hr style={{ margin: '1rem 0', borderColor: 'var(--color-border)' }} />

          <h3 className="form-label">⚙️ Histéresis (umbrales de actuación)</h3>
          <div className="grid grid-2" style={{ gap: '0 1rem' }}>
            <NumberField id="crop-hyst-temp-on" label="Temp ON > °C" value={formData.hysteresis_temp_on} onChange={value => setField('hysteresis_temp_on', value)} />
            <NumberField id="crop-hyst-temp-off" label="Temp OFF < °C" value={formData.hysteresis_temp_off} onChange={value => setField('hysteresis_temp_off', value)} />
            <NumberField id="crop-hyst-hum-on" label="Hum ON < %" value={formData.hysteresis_humidity_on} onChange={value => setField('hysteresis_humidity_on', value)} />
            <NumberField id="crop-hyst-hum-off" label="Hum OFF > %" value={formData.hysteresis_humidity_off} onChange={value => setField('hysteresis_humidity_off', value)} />
            <NumberField id="crop-hyst-soil-on" label="Suelo ON < %" step="1" value={formData.hysteresis_soil_on} onChange={value => setField('hysteresis_soil_on', value)} />
            <NumberField id="crop-hyst-soil-off" label="Suelo OFF > %" step="1" value={formData.hysteresis_soil_off} onChange={value => setField('hysteresis_soil_off', value)} />
          </div>

          <hr style={{ margin: '1rem 0', borderColor: 'var(--color-border)' }} />

          <h3 className="form-label">📚 Referencia Bibliográfica</h3>
          <TextField
            id="crop-source-reference"
            label="Referencia (cita corta)"
            value={formData.source_reference}
            onChange={value => setField('source_reference', value)}
            placeholder="FAO a1374s; INTA hortalizas…"
          />
          <TextField
            id="crop-source-url"
            label="URL fuente"
            type="url"
            value={formData.source_url}
            onChange={value => setField('source_url', value)}
            placeholder="https://…"
            inputMode="url"
          />
          <div className="form-group">
            <label className="form-label" htmlFor="crop-notes">
              Notas
            </label>
            <textarea
              id="crop-notes"
              aria-label="Notas"
              value={formData.notes}
              onChange={event => setField('notes', event.target.value)}
              className="form-control"
              rows={2}
            />
          </div>
        </form>
      </Modal>

      <div className="card">
        <div
          className="table-container"
          tabIndex={0}
          role="region"
          aria-label="Cultivos configurados"
        >
          <table className="table-cards">
            <caption className="visually-hidden">Cultivos configurados</caption>
            <thead>
              <tr>
                <th scope="col">Nombre</th>
                <th scope="col">Temp Día (°C)</th>
                <th scope="col">Temp Noche (°C)</th>
                <th scope="col">Humedad (%)</th>
                <th scope="col">Suelo (%)</th>
                <th scope="col">Histéresis T°</th>
                <th scope="col">Fuente</th>
                <th scope="col" style={{ width: '120px' }}>
                  <span className="visually-hidden">Acciones</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {crops.map(crop => (
                <tr key={crop.id}>
                  <td data-label="Nombre">
                    <strong>{crop.display_name}</strong>
                    <br />
                    <small style={{ color: 'var(--color-text-muted)' }}>{crop.name}</small>
                    {crop.description && <br />}
                    {crop.description && (
                      <small style={{ color: 'var(--color-text-muted)' }}>{crop.description}</small>
                    )}
                  </td>
                  <td data-label="Temp Día">
                    {crop.params?.temp_min != null
                      ? `${crop.params.temp_min}–${crop.params.temp_max}`
                      : '—'}
                  </td>
                  <td data-label="Temp Noche">
                    {crop.params?.temp_night_min != null
                      ? `${crop.params.temp_night_min}–${crop.params.temp_night_max}`
                      : '—'}
                  </td>
                  <td data-label="Humedad">
                    {crop.params?.humidity_min != null
                      ? `${crop.params.humidity_min}–${crop.params.humidity_max}`
                      : '—'}
                  </td>
                  <td data-label="Suelo">
                    {crop.params?.soil_moisture_min_pct != null
                      ? `${crop.params.soil_moisture_min_pct}–${crop.params.soil_moisture_max_pct}`
                      : '—'}
                  </td>
                  <td data-label="Histéresis T°">
                    {crop.params?.hysteresis_temp_on != null
                      ? `ON>${crop.params.hysteresis_temp_on} OFF<${crop.params.hysteresis_temp_off}`
                      : '—'}
                  </td>
                  <td data-label="Fuente">
                    {crop.params?.source_reference &&
                      (safeExternalUrl(crop.params.source_url) ? (
                        <a
                          href={safeExternalUrl(crop.params.source_url)}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ fontSize: '0.78rem' }}
                        >
                          {crop.params.source_reference}
                        </a>
                      ) : (
                        <span style={{ fontSize: '0.78rem' }}>
                          {crop.params.source_reference}
                        </span>
                      ))}
                  </td>
                  <td data-label="">
                    <button
                      onClick={() => handleEdit(crop)}
                      className="btn btn-secondary btn-sm"
                      style={{ marginRight: '0.25rem' }}
                    >
                      Editar
                    </button>
                    {!crop.is_active && <span className="badge badge-off">Inactivo</span>}
                    {crop.is_active && (
                      <button onClick={() => handleDelete(crop.id)} className="btn btn-danger btn-sm">
                        Desactivar
                      </button>
                    )}
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
