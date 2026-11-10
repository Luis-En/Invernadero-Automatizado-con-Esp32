import { useEffect, useRef } from 'react'
import { getNotificationRegistration } from '../pwa'

const LAST_KEY = 'irrigation-last-notified'
const COOLDOWN_MS = 6 * 60 * 60 * 1000

/**
 * Local notification fallback: when the app is open and no Web Push
 * subscription exists, announce the transition from "soil OK" to
 * "irrigation needed". Keeps a 6 h cooldown so an oscillating probe cannot
 * spam the phone.
 */
export function useIrrigationAlerts(status) {
  const previous = useRef(null)

  useEffect(() => {
    if (!status || status.irrigation_needed === undefined) return

    const needed = Boolean(status.irrigation_needed)
    const wasNeeded = previous.current
    previous.current = needed

    if (!needed || wasNeeded === true) return
    if (typeof window === 'undefined' || !('Notification' in window)) return
    if (Notification.permission !== 'granted') return
    if (localStorage.getItem('local-irrigation-alerts') !== '1') return

    const last = Number(localStorage.getItem(LAST_KEY) || 0)
    if (Date.now() - last < COOLDOWN_MS) return

    const average =
      status.soil_avg_pct !== null && status.soil_avg_pct !== undefined
        ? `${status.soil_avg_pct.toFixed(0)}%`
        : 'baja'
    const threshold =
      status.soil_threshold_pct !== null && status.soil_threshold_pct !== undefined
        ? `${status.soil_threshold_pct.toFixed(0)}%`
        : null

    const title = '💧 Riego necesario'
    const body = threshold
      ? `Humedad del suelo ${average} (umbral ${threshold}). Revisa el invernadero.`
      : 'La humedad del suelo está por debajo del umbral. Revisa el invernadero.'

    const show = async () => {
      try {
        const registration = await getNotificationRegistration()
        // If Web Push is already subscribed, the server will notify; avoid duplicates.
        const pushSubscription = registration
          ? await registration.pushManager.getSubscription()
          : null
        if (pushSubscription) return

        if (registration?.showNotification) {
          await registration.showNotification(title, {
            body,
            icon: '/icons/icon-192.png',
            badge: '/icons/badge-72.png',
            tag: 'irrigation-needed',
            data: { url: '/' },
          })
        } else {
          new Notification(title, { body, icon: '/icons/icon-192.png' })
        }
        localStorage.setItem(LAST_KEY, String(Date.now()))
      } catch (error) {
        console.warn('No se pudo mostrar la alerta local:', error)
      }
    }

    show()
  }, [status])
}
