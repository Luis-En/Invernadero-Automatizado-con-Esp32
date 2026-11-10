import { useEffect, useState } from 'react'

const DISMISS_KEY = 'pwa-install-dismissed'

function isStandalone() {
  if (typeof window === 'undefined') return false
  return (
    window.matchMedia?.('(display-mode: standalone)')?.matches ||
    window.navigator.standalone === true
  )
}

function isIos() {
  if (typeof navigator === 'undefined') return false
  return (
    /iphone|ipad|ipod/i.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  )
}

/** Android/desktop install banner driven by `beforeinstallprompt`. */
export function InstallPrompt() {
  const [deferred, setDeferred] = useState(null)
  const [dismissed, setDismissed] = useState(() => {
    if (typeof localStorage === 'undefined') return false
    return (
      localStorage.getItem(DISMISS_KEY) === '1' ||
      (isIos() && localStorage.getItem(`${DISMISS_KEY}-ios`) === '1')
    )
  })
  const [installed, setInstalled] = useState(isStandalone)

  useEffect(() => {
    const onPrompt = event => {
      event.preventDefault()
      setDeferred(event)
    }
    const onInstalled = () => {
      setInstalled(true)
      setDeferred(null)
    }
    window.addEventListener('beforeinstallprompt', onPrompt)
    window.addEventListener('appinstalled', onInstalled)
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [])

  if (installed || dismissed) return null

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, '1')
    setDismissed(true)
  }

  if (deferred) {
    return (
      <div className="install-prompt" role="region" aria-label="Instalar la aplicación">
        <span className="irrigation-banner-icon" aria-hidden="true">
          📲
        </span>
        <div className="install-prompt-body">
          <strong>Instala el invernadero en tu teléfono</strong>
          Acceso directo a pantalla completa y notificaciones en segundo plano.
        </div>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={async () => {
            deferred.prompt()
            await deferred.userChoice
            setDeferred(null)
          }}
        >
          Instalar
        </button>
        <button type="button" className="btn btn-secondary btn-sm" onClick={dismiss}>
          Ahora no
        </button>
      </div>
    )
  }

  // iOS never fires beforeinstallprompt: show the Share-sheet steps instead.
  if (isIos()) {
    return (
      <div className="install-prompt" role="region" aria-label="Instalar la aplicación en iOS">
        <span className="irrigation-banner-icon" aria-hidden="true">
          📲
        </span>
        <div className="install-prompt-body">
          <strong>Instala el invernadero en tu iPhone/iPad</strong>
          Toca <strong>Compartir</strong> en Safari y luego{' '}
          <strong>Añadir a pantalla de inicio</strong>. Las notificaciones push requieren iOS 16.4+
          y abrir la app desde el icono.
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => {
            localStorage.setItem(`${DISMISS_KEY}-ios`, '1')
            setDismissed(true)
          }}
        >
          Entendido
        </button>
      </div>
    )
  }

  return null
}

/** iOS has no install prompt event; show the Share-sheet instructions instead. */
export function InstallHint() {
  const [hidden, setHidden] = useState(
    () => typeof localStorage !== 'undefined' && localStorage.getItem(`${DISMISS_KEY}-ios`) === '1'
  )

  if (isStandalone() || !isIos() || hidden) return null

  return (
    <div className="drawer-install-hint">
      <strong>Instalar en iPhone/iPad</strong>
      <p style={{ marginTop: '0.35rem' }}>
        Toca el botón <strong>Compartir</strong> de Safari y luego{' '}
        <strong>Añadir a pantalla de inicio</strong>. Las notificaciones push requieren iOS 16.4+
        con la app instalada.
      </p>
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        style={{ marginTop: '0.5rem' }}
        onClick={() => {
          localStorage.setItem(`${DISMISS_KEY}-ios`, '1')
          setHidden(true)
        }}
      >
        Entendido
      </button>
    </div>
  )
}
