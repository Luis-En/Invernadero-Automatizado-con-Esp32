let registrationPromise = null

/** True when the browser can register a service worker and show notifications. */
export function supportsServiceWorker() {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    window.isSecureContext
  )
}

/**
 * Registers the production service worker. In development Vite serves modules
 * unbundled, so a cached shell would hide changes; the SW is production-only.
 */
export function registerServiceWorker() {
  if (!supportsServiceWorker() || !import.meta.env.PROD) return
  if (registrationPromise) return registrationPromise

  registrationPromise = new Promise(resolve => {
    const register = async () => {
      try {
        const registration = await navigator.serviceWorker.register('/sw.js')

        const announceUpdate = worker => {
          if (!worker) return
          worker.addEventListener('statechange', () => {
            if (worker.state === 'installed' && navigator.serviceWorker.controller) {
              window.dispatchEvent(new Event('pwa:update-available'))
            }
          })
        }

        announceUpdate(registration.installing)
        registration.addEventListener('updatefound', () => {
          announceUpdate(registration.installing)
        })

        resolve(registration)
      } catch (error) {
        console.warn('No se pudo registrar el service worker:', error)
        resolve(null)
      }
    }

    if (document.readyState === 'complete') register()
    else window.addEventListener('load', register, { once: true })
  })

  return registrationPromise
}

/** Registration used for notifications; waits for the SW to be active. */
export async function getNotificationRegistration() {
  if (!supportsServiceWorker()) return null
  try {
    const registration = await registerServiceWorker()
    if (!registration) return null
    if (registration.active) return registration
    return await navigator.serviceWorker.ready
  } catch {
    return null
  }
}

export async function applyServiceWorkerUpdate() {
  try {
    const registration = await navigator.serviceWorker.getRegistration()
    const waiting = registration?.waiting
    if (!waiting) {
      window.location.reload()
      return
    }
    navigator.serviceWorker.addEventListener(
      'controllerchange',
      () => window.location.reload(),
      { once: true }
    )
    waiting.postMessage({ type: 'SKIP_WAITING' })
  } catch {
    window.location.reload()
  }
}
