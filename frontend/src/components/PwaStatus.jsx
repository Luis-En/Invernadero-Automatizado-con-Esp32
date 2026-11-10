import { useEffect, useState } from 'react'
import { applyServiceWorkerUpdate } from '../pwa'

/** Offline banner + "new version available" prompt for the installed PWA. */
export function PwaStatus() {
  const [online, setOnline] = useState(
    typeof navigator === 'undefined' ? true : navigator.onLine
  )
  const [updateReady, setUpdateReady] = useState(false)

  useEffect(() => {
    const goOnline = () => setOnline(true)
    const goOffline = () => setOnline(false)
    const onUpdate = () => setUpdateReady(true)

    window.addEventListener('online', goOnline)
    window.addEventListener('offline', goOffline)
    window.addEventListener('pwa:update-available', onUpdate)
    return () => {
      window.removeEventListener('online', goOnline)
      window.removeEventListener('offline', goOffline)
      window.removeEventListener('pwa:update-available', onUpdate)
    }
  }, [])

  if (!online) {
    return (
      <div className="offline-toast" role="status" aria-live="polite">
        <span>Sin conexión. Mostrando los últimos datos disponibles.</span>
      </div>
    )
  }

  if (!updateReady) return null

  return (
    <div className="update-toast" role="status" aria-live="polite">
      <span>Hay una nueva versión de la app disponible.</span>
      <button
        type="button"
        className="btn btn-sm"
        onClick={() => {
          setUpdateReady(false)
          applyServiceWorkerUpdate()
        }}
      >
        Actualizar
      </button>
    </div>
  )
}
