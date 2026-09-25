import { useState, useEffect, useCallback } from 'react'
import { useTelemetry } from '../context/TelemetryContext'
import { api } from '../api'
import { format } from 'date-fns'

const PAGE_SIZE = 20

export function Photos() {
  const { status } = useTelemetry()
  const [photos, setPhotos] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [selectedPhoto, setSelectedPhoto] = useState(null)
  const [latestPhoto, setLatestPhoto] = useState(null)

  const loadPhotos = useCallback(async (targetPage) => {
    setLoading(true)
    try {
      const data = await api.getPhotos(PAGE_SIZE, targetPage * PAGE_SIZE)
      setPhotos(prev => targetPage === 0 ? data : [...prev, ...data])
      setHasMore(data.length === PAGE_SIZE)
    } catch (e) {
      console.error('Failed to load photos:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadLatest = useCallback(async () => {
    try {
      const data = await api.getLatestPhoto()
      setLatestPhoto(data)
    } catch {
      setLatestPhoto(null)
    }
  }, [])

  useEffect(() => {
    loadPhotos(page)
  }, [page, loadPhotos])

  useEffect(() => {
    loadLatest()
  }, [loadLatest, status?.last_photo])

  const handleRefresh = () => {
    if (page === 0) {
      loadPhotos(0)
      loadLatest()
    } else {
      setPage(0)
    }
  }

  const handleLoadMore = () => setPage(p => p + 1)

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Galería de Fotos</h1>
          <p style={{ color: 'var(--color-text-muted)' }}>
            Fotografías periódicas del cultivo (cada 30 min)
          </p>
        </div>
        <button onClick={handleRefresh} className="btn btn-primary" disabled={loading}>
          {loading ? 'Cargando...' : 'Actualizar'}
        </button>
      </div>

      {latestPhoto && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <div className="card-header">📸 Foto más reciente</div>
          <div className="card-body">
            <div style={{ textAlign: 'center' }}>
              <img
                src={`${api.getLatestPhotoFile()}?t=${Date.now()}`}
                alt="Última foto"
                style={{
                  maxWidth: '100%',
                  maxHeight: '500px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--color-border)',
                  cursor: 'pointer',
                }}
                onClick={() => setSelectedPhoto(latestPhoto)}
              />
              <p style={{ marginTop: '0.75rem', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                Tomada: {format(new Date(latestPhoto.timestamp), 'dd/MM/yyyy HH:mm:ss')}
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="photo-grid">
        {photos.map(photo => (
          <div key={photo.id} className="photo-card" onClick={() => setSelectedPhoto(photo)}>
            <img
              src={api.getPhotoFile(photo.id)}
              alt={photo.filename}
              loading="lazy"
            />
            <div className="photo-overlay">
              {format(new Date(photo.timestamp), 'dd/MM/yyyy HH:mm')}
            </div>
          </div>
        ))}
      </div>

      {hasMore && (
        <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
          <button onClick={handleLoadMore} className="btn btn-secondary" disabled={loading}>
            {loading ? 'Cargando...' : 'Cargar más'}
          </button>
        </div>
      )}

      {photos.length === 0 && !loading && (
        <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--color-text-muted)' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📷</div>
          <p>No hay fotos disponibles aún</p>
        </div>
      )}

      {selectedPhoto && (
        <div className="modal-overlay" onClick={() => setSelectedPhoto(null)}>
          <div className="modal" style={{ maxWidth: '90vw', maxHeight: '90vh' }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">{selectedPhoto.filename}</h3>
              <button onClick={() => setSelectedPhoto(null)} style={{ fontSize: '1.5rem', lineHeight: 1, color: 'var(--color-text-muted)' }}>×</button>
            </div>
            <div className="modal-body" style={{ padding: 0, textAlign: 'center' }}>
              <img
                src={api.getPhotoFile(selectedPhoto.id)}
                alt={selectedPhoto.filename}
                style={{ maxWidth: '100%', maxHeight: '70vh', borderRadius: 'var(--radius-md)' }}
              />
              <div style={{ padding: '1rem', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                {format(new Date(selectedPhoto.timestamp), 'dd/MM/yyyy HH:mm:ss')}
                {selectedPhoto.size_bytes ? ` · ${(selectedPhoto.size_bytes / 1024).toFixed(1)} KB` : ''}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
