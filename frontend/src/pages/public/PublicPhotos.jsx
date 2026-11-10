import { useCallback, useEffect, useState } from 'react'
import { format } from 'date-fns'
import { api } from '../../api'
import { Modal } from '../../components/Modal'
import { formatServerTime } from '../../utils/time'

const PAGE_SIZE = 24

export function PublicPhotos() {
  const [photos, setPhotos] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [page, setPage] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [selected, setSelected] = useState(null)

  const load = useCallback(async targetPage => {
    setLoading(true)
    setError('')
    try {
      const data = await api.getPublicPhotos(PAGE_SIZE, targetPage * PAGE_SIZE)
      setPhotos(previous => (targetPage === 0 ? data : [...previous, ...data]))
      setHasMore(data.length === PAGE_SIZE)
    } catch (e) {
      setError(e.message || 'No se pudieron cargar las fotografías')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load(page)
  }, [page, load])

  const refresh = () => {
    if (page === 0) load(0)
    else setPage(0)
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Galería pública</h1>
          <p className="page-subtitle">
            Fotografías periódicas del cultivo, sin necesidad de iniciar sesión.
          </p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={refresh} disabled={loading}>
          {loading ? 'Cargando…' : '🔄 Actualizar'}
        </button>
      </div>

      {error && (
        <div className="alert alert-warning" role="status">
          {error}
        </div>
      )}

      <div className="photo-grid">
        {photos.map(photo => (
          <button
            key={photo.id}
            type="button"
            className="photo-card"
            onClick={() => setSelected(photo)}
            aria-label={`Ver foto del ${formatServerTime(photo.timestamp, d => format(d, 'dd/MM/yyyy HH:mm'))}`}
          >
            <img
              src={`/api/public/photos/${photo.id}/file`}
              alt={`Fotografía del cultivo del ${formatServerTime(photo.timestamp, d => format(d, 'dd/MM/yyyy HH:mm'))}`}
              loading="lazy"
              decoding="async"
            />
            <div className="photo-overlay" aria-hidden="true">
              {formatServerTime(photo.timestamp, d => format(d, 'dd/MM/yyyy HH:mm'))}
            </div>
          </button>
        ))}
      </div>

      {!loading && photos.length === 0 && (
        <div className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: '3rem' }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📷</div>
            <p>No hay fotografías disponibles todavía.</p>
          </div>
        </div>
      )}

      {hasMore && photos.length > 0 && (
        <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setPage(value => value + 1)}
            disabled={loading}
          >
            {loading ? 'Cargando…' : 'Cargar más'}
          </button>
        </div>
      )}

      <Modal
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected ? `Foto ${selected.id}` : 'Foto'}
        size="xl"
      >
        {selected && (
          <div style={{ textAlign: 'center' }}>
            <img
              src={`/api/public/photos/${selected.id}/file`}
              alt={`Fotografía del cultivo del ${formatServerTime(selected.timestamp, d => format(d, 'dd/MM/yyyy HH:mm'))}`}
              style={{
                maxWidth: '100%',
                maxHeight: '65dvh',
                borderRadius: 'var(--radius-md)',
              }}
            />
            <p className="page-subtitle" style={{ marginTop: '0.75rem' }}>
              {formatServerTime(selected.timestamp, d => format(d, 'dd/MM/yyyy HH:mm:ss'))}
              {selected.size_bytes
                ? ` · ${(selected.size_bytes / 1024).toFixed(1)} KB`
                : ''}
            </p>
          </div>
        )}
      </Modal>
    </div>
  )
}
