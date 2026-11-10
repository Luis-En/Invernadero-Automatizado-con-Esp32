import { useState } from 'react'
import { useTelemetry } from '../context/TelemetryContext'
import { usePushNotifications } from '../hooks/usePushNotifications'
import { Modal } from './Modal'

function fmtPct(value) {
  return value === null || value === undefined ? '—' : `${value.toFixed(0)}%`
}

function PermissionState({ permission }) {
  const labels = {
    granted: 'Permiso concedido',
    denied: 'Permiso denegado',
    default: 'Permiso pendiente',
    unsupported: 'Sin soporte',
  }
  const tone = permission === 'granted' ? 'granted' : permission === 'denied' ? 'denied' : 'default'
  return <span className={`permission-state ${tone}`}>{labels[permission] || labels.default}</span>
}

export function NotificationBell() {
  const { status } = useTelemetry()
  const [open, setOpen] = useState(false)
  const push = usePushNotifications()
  const needed = Boolean(status?.irrigation_needed)
  const hasAlert = needed || Number(status?.alerts_count || 0) > 0

  return (
    <>
      <button
        type="button"
        className={`icon-btn${hasAlert ? ' has-alert' : ''}`}
        aria-label={
          hasAlert ? 'Abrir notificaciones (hay alertas pendientes)' : 'Abrir notificaciones'
        }
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        <span aria-hidden="true">🔔</span>
      </button>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Notificaciones de riego"
        size="md"
      >
        <section aria-labelledby="irrigation-state-title">
          <h3 id="irrigation-state-title" className="form-label">
            Estado actual
          </h3>
          <div className={`notification-row${needed ? ' irrigation-needed' : ''}`}>
            <div>
              <strong>
                {status?.telemetry_stale
                  ? '⏸️ Datos desactualizados'
                  : needed
                    ? '💧 Riego necesario'
                    : '✅ Suelo en rango'}
              </strong>
              <span>
                Humedad media {fmtPct(status?.soil_avg_pct)} · umbral{' '}
                {fmtPct(status?.soil_threshold_pct)}
                {status?.active_crop ? ` · ${status.active_crop}` : ''}
              </span>
              {status?.telemetry_stale && (
                <span>
                  Sin telemetría reciente del campo; no se generan alertas de riego con datos
                  viejos.
                </span>
              )}
            </div>
            <span
              className={`badge ${
                status?.telemetry_stale ? 'badge-off' : needed ? 'badge-warning' : 'badge-normal'
              }`}
            >
              {status?.telemetry_stale ? 'Sin datos' : needed ? 'Regar' : 'OK'}
            </span>
          </div>
        </section>

        <section style={{ marginTop: '1.1rem' }} aria-labelledby="device-alerts-title">
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '0.5rem',
              flexWrap: 'wrap',
            }}
          >
            <h3 id="device-alerts-title" className="form-label" style={{ margin: 0 }}>
              Alertas en este dispositivo
            </h3>
            <PermissionState permission={push.permission} />
          </div>

          {!push.secure && (
            <div className="alert alert-warning" style={{ marginTop: '0.6rem' }}>
              Las notificaciones y la instalación de la PWA requieren HTTPS. En una IP local por
              HTTP el teléfono no las permitirá. Abre la app por HTTPS o mediante una red privada
              (Tailscale, Cloudflare Tunnel o un certificado local). El aviso de riego seguirá
              apareciendo dentro de la app.
            </div>
          )}

          {push.secure && !push.supported && (
            <div className="alert alert-warning" style={{ marginTop: '0.6rem' }}>
              Este navegador no permite notificaciones push. Prueba Chrome en Android o Safari en
              iOS 16.4+ con la app instalada.
            </div>
          )}

          {push.secure && push.supported && push.loading && (
            <p className="form-hint" role="status">
              Consultando el estado…
            </p>
          )}

          {push.secure && push.supported && !push.loading && push.pushConfigured && (
            <div style={{ marginTop: '0.75rem' }}>
              <p className="form-hint" style={{ marginTop: 0 }}>
                Recibe el aviso aunque la app esté cerrada. El servidor revisa la humedad cada{' '}
                {Math.round((push.config?.check_interval_sec || 60) / 60) || 1} min y recuerda el
                aviso cada {push.config?.reminder_hours || 6} h mientras el suelo siga seco.
              </p>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.6rem' }}>
                {push.subscription ? (
                  <>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={push.disablePush}
                      disabled={push.busy}
                    >
                      Desactivar push
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={push.sendTest}
                      disabled={push.busy}
                    >
                      Enviar prueba
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={push.enablePush}
                    disabled={push.busy || push.permission === 'denied'}
                  >
                    {push.busy ? 'Activando…' : 'Activar notificaciones push'}
                  </button>
                )}
              </div>
              {push.permission === 'denied' && (
                <p className="form-hint">
                  El permiso está bloqueado. Habilítalo desde los ajustes del navegador para este
                  sitio y vuelve a intentarlo.
                </p>
              )}
            </div>
          )}

          {push.secure && push.supported && !push.loading && !push.pushConfigured && (
            <div style={{ marginTop: '0.75rem' }}>
              <div className="alert alert-info" style={{ marginBottom: '0.6rem' }}>
                El servidor aún no tiene claves VAPID, así que no puede enviar avisos en segundo
                plano. Mientras tanto puedes activar alertas locales: se muestran si la app está
                abierta o en segundo plano con el navegador activo.
              </div>
              {push.localEnabled ? (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={push.disableLocal}
                >
                  Desactivar alertas locales
                </button>
              ) : (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={push.enableLocal}
                  disabled={push.permission === 'denied'}
                >
                  Activar alertas locales
                </button>
              )}
              {push.localEnabled && (
                <p className="form-hint">
                  Alertas locales activas. Se envían al pasar de suelo húmedo a seco, con un
                  máximo de una cada 6 horas.
                </p>
              )}
            </div>
          )}

          {push.error && (
            <div className="alert alert-critical" role="alert" style={{ marginTop: '0.6rem' }}>
              {push.error}
            </div>
          )}
          {push.notice && (
            <div className="alert alert-success" role="status" style={{ marginTop: '0.6rem' }}>
              {push.notice}
            </div>
          )}
        </section>

        <p className="form-hint" style={{ marginTop: '1rem' }}>
          El umbral de riego se configura en <strong>Configuración</strong> (humedad del suelo).
          Si el riego automático está deshabilitado, la alerta te pide regar manualmente.
        </p>
      </Modal>
    </>
  )
}
