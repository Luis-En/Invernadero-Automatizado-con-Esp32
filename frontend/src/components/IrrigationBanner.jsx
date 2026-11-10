import { Link } from 'react-router-dom'

function fmtPct(value) {
  return value === null || value === undefined ? '—' : `${value.toFixed(0)}%`
}

/**
 * Persistent in-app alert. This is the fallback that always works, even when
 * the browser blocks notifications on a plain-HTTP LAN origin.
 */
export function IrrigationBanner({ status, isAdmin }) {
  if (!status?.irrigation_needed) return null

  const average = status.soil_avg_pct
  const threshold = status.soil_threshold_pct
  const critical =
    average !== null && average !== undefined && threshold !== null && threshold !== undefined
      ? average <= threshold - 10
      : false

  return (
    <div
      className={`irrigation-banner${critical ? ' critical' : ''}`}
      role={critical ? 'alert' : 'status'}
    >
      <span className="irrigation-banner-icon" aria-hidden="true">
        {critical ? '🚨' : '💧'}
      </span>
      <div className="irrigation-banner-body">
        <div className="irrigation-banner-title">
          {critical ? 'Riego urgente' : 'Riego necesario'}
        </div>
        <p className="irrigation-banner-text">
          Humedad media del suelo {fmtPct(average)} (umbral {fmtPct(threshold)}).
          {status.irrigation_enabled
            ? ' El riego automático está habilitado; verifica que la bomba tenga agua y que el comando haya llegado al campo.'
            : ' El riego automático está deshabilitado: habilítalo o riega manualmente.'}
          {status.active_crop ? ` Cultivo activo: ${status.active_crop}.` : ''}
        </p>
      </div>
      {isAdmin && (
        <Link to="/configuracion" className="btn btn-secondary btn-sm">
          Revisar riego
        </Link>
      )}
    </div>
  )
}
