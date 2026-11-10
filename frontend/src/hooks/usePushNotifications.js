import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { getNotificationRegistration, supportsServiceWorker } from '../pwa'

const LOCAL_KEY = 'local-irrigation-alerts'

export function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = window.atob(base64)
  const output = new Uint8Array(rawData.length)
  for (let i = 0; i < rawData.length; i += 1) output[i] = rawData.charCodeAt(i)
  return output
}

function notificationPermission() {
  if (typeof window === 'undefined' || !('Notification' in window)) return 'unsupported'
  return Notification.permission
}

/**
 * Web Push subscription lifecycle plus the local-alert fallback used when the
 * server has no VAPID keys yet. Permission is only requested from a click.
 */
export function usePushNotifications() {
  const [config, setConfig] = useState(null)
  const [permission, setPermission] = useState(notificationPermission)
  const [subscription, setSubscription] = useState(null)
  const [localEnabled, setLocalEnabled] = useState(
    () => typeof localStorage !== 'undefined' && localStorage.getItem(LOCAL_KEY) === '1'
  )
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const secure = typeof window !== 'undefined' && window.isSecureContext
  const supported =
    secure &&
    typeof window !== 'undefined' &&
    'Notification' in window &&
    'PushManager' in window &&
    supportsServiceWorker()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [serverConfig, registration] = await Promise.all([
        api.getNotificationConfig().catch(() => null),
        getNotificationRegistration(),
      ])
      setConfig(serverConfig)
      if (registration) {
        const current = await registration.pushManager.getSubscription()
        setSubscription(current)
        // Repair the server side: a redeploy with a fresh database (or an
        // older deployment) loses the row even though the browser keeps the
        // subscription. Re-posting it is idempotent on the API.
        if (current && serverConfig?.push_supported) {
          const json = current.toJSON()
          api
            .subscribePush({
              endpoint: json.endpoint,
              keys: json.keys,
              user_agent: navigator.userAgent.slice(0, 255),
            })
            .catch(() => null)
        }
      }
    } catch (e) {
      setError(e.message || 'No se pudo consultar el estado de las notificaciones')
    } finally {
      setPermission(notificationPermission())
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  /* Create or reuse the browser subscription and store it on the API. */
  const ensureSubscription = useCallback(async (registration, serverConfig) => {
    let current = await registration.pushManager.getSubscription()
    if (!current) {
      if (!serverConfig?.vapid_public_key) {
        throw new Error('El servidor todavía no tiene configuradas las claves de notificaciones.')
      }
      current = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(serverConfig.vapid_public_key),
      })
    }
    const json = current.toJSON()
    await api.subscribePush({
      endpoint: json.endpoint,
      keys: json.keys,
      user_agent: navigator.userAgent.slice(0, 255),
    })
    return current
  }, [])

  /* Chromium and Safari can rotate a push subscription. The service worker
     tells open clients; re-create it and store the new endpoint. */
  useEffect(() => {
    if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return undefined

    const onMessage = async event => {
      if (event.data?.type !== 'PUSH_SUBSCRIPTION_CHANGED') return
      if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return
      try {
        const registration = await getNotificationRegistration()
        if (!registration) return
        const serverConfig = config || (await api.getNotificationConfig().catch(() => null))
        if (!serverConfig?.push_supported) return
        const current = await ensureSubscription(registration, serverConfig)
        setSubscription(current)
        setNotice('Suscripción de notificaciones renovada automáticamente.')
      } catch (e) {
        console.warn('No se pudo renovar la suscripción push:', e)
      }
    }

    navigator.serviceWorker.addEventListener('message', onMessage)
    return () => navigator.serviceWorker.removeEventListener('message', onMessage)
  }, [config, ensureSubscription])

  const requestPermission = useCallback(async () => {
    if (!supported) return 'unsupported'
    try {
      const result = await Notification.requestPermission()
      setPermission(result)
      return result
    } catch {
      setPermission(notificationPermission())
      return notificationPermission()
    }
  }, [supported])

  const enablePush = useCallback(async () => {
    setError('')
    setNotice('')
    setBusy(true)
    try {
      if (!supported) {
        throw new Error(
          'Este navegador no admite notificaciones push. Se requiere HTTPS e instalar la PWA.'
        )
      }
      if (!config?.push_supported || !config?.vapid_public_key) {
        throw new Error('El servidor todavía no tiene configuradas las claves de notificaciones.')
      }

      const result = await requestPermission()
      if (result !== 'granted') {
        throw new Error(
          result === 'denied'
            ? 'Permiso denegado. Actívalo en los ajustes del navegador para este sitio.'
            : 'No se concedió permiso para mostrar notificaciones.'
        )
      }

      const registration = await getNotificationRegistration()
      if (!registration) throw new Error('El service worker no está disponible.')

      const current = await ensureSubscription(registration, config)
      setSubscription(current)
      setNotice('Notificaciones activadas en este dispositivo.')
    } catch (e) {
      setError(e.message || 'No se pudieron activar las notificaciones')
    } finally {
      setBusy(false)
    }
  }, [config, ensureSubscription, requestPermission, supported])

  const disablePush = useCallback(async () => {
    setError('')
    setNotice('')
    setBusy(true)
    try {
      const registration = await getNotificationRegistration()
      const current =
        subscription || (registration ? await registration.pushManager.getSubscription() : null)
      if (current) {
        await api.unsubscribePush(current.endpoint).catch(() => null)
        await current.unsubscribe()
      }
      setSubscription(null)
      setNotice('Notificaciones push desactivadas.')
    } catch (e) {
      setError(e.message || 'No se pudieron desactivar las notificaciones')
    } finally {
      setBusy(false)
    }
  }, [subscription])

  const enableLocal = useCallback(async () => {
    setError('')
    setNotice('')
    const result = await requestPermission()
    if (result !== 'granted') {
      setError(
        result === 'denied'
          ? 'Permiso denegado. Actívalo en los ajustes del navegador.'
          : 'No se concedió permiso para mostrar notificaciones.'
      )
      return
    }
    localStorage.setItem(LOCAL_KEY, '1')
    setLocalEnabled(true)
    setNotice('Alertas locales activadas mientras la app esté abierta.')
  }, [requestPermission])

  const disableLocal = useCallback(() => {
    localStorage.removeItem(LOCAL_KEY)
    setLocalEnabled(false)
    setNotice('Alertas locales desactivadas.')
  }, [])

  const sendTest = useCallback(async () => {
    setError('')
    setNotice('')
    setBusy(true)
    try {
      await api.sendTestNotification()
      setNotice('Notificación de prueba enviada. Puede tardar unos segundos.')
    } catch (e) {
      setError(e.message || 'No se pudo enviar la notificación de prueba')
    } finally {
      setBusy(false)
    }
  }, [])

  return {
    config,
    permission,
    subscription,
    localEnabled,
    loading,
    busy,
    error,
    notice,
    secure,
    supported,
    pushConfigured: Boolean(config?.push_supported && config?.vapid_public_key),
    enablePush,
    disablePush,
    enableLocal,
    disableLocal,
    sendTest,
    reload: load,
  }
}
