import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

/**
 * Admin-only guard. Public visitors are sent to the admin login; authenticated
 * viewers stay out of the admin area.
 */
export function RequireAuth({ children }) {
  const { user, loading, isAdmin, authOffline, refreshAuth } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="loading-state" role="status" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <p>Comprobando sesión…</p>
      </div>
    )
  }

  if (!user && authOffline) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '2rem' }}>
        <div className="alert alert-warning" role="status" style={{ textAlign: 'left' }}>
          Sin conexión con el servidor, así que no se pudo verificar la sesión. El panel
          volverá a estar disponible cuando recuperes la red.
        </div>
        <button type="button" className="btn btn-primary" onClick={refreshAuth}>
          Reintentar
        </button>
      </div>
    )
  }

  if (!user) {
    return (
      <Navigate
        to="/admin/login"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    )
  }

  if (!isAdmin) {
    return <Navigate to="/" replace />
  }

  return children
}
