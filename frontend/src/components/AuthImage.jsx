import { useEffect, useState } from 'react'
import { api } from '../api'

// Photos are served by the authenticated router, so a plain <img src> cannot
// fetch them (it cannot attach the bearer token). Fetch the bytes and render
// an object URL, revoking it when the image unmounts.
export function AuthImage({ photoId, latest = false, alt = '', style, className, onClick }) {
  const [url, setUrl] = useState(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    let objectUrl = null
    setFailed(false)
    setUrl(null)

    const load = async () => {
      try {
        objectUrl = latest
          ? await api.getLatestPhotoBlobUrl()
          : await api.getPhotoBlobUrl(photoId)
        if (cancelled) {
          URL.revokeObjectURL(objectUrl)
          return
        }
        setUrl(objectUrl)
      } catch {
        if (!cancelled) setFailed(true)
      }
    }
    load()

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [photoId, latest])

  if (failed) {
    return (
      <div style={{ ...style, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-text-muted)' }}>
        Foto no disponible
      </div>
    )
  }
  if (!url) {
    return <div style={{ ...style, background: 'var(--color-bg)' }} aria-label="Cargando foto" role="img" />
  }
  return <img src={url} alt={alt} style={style} className={className} onClick={onClick} decoding="async" loading={latest ? 'eager' : 'lazy'} />
}
