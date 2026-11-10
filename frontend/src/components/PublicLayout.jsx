import { Link, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTelemetry } from '../context/TelemetryContext'
import { useIrrigationAlerts } from '../hooks/useIrrigationAlerts'
import { InstallPrompt } from './InstallPrompt'
import { NotificationBell } from './NotificationBell'
import { PwaStatus } from './PwaStatus'
import { RouteAnnouncer } from './RouteAnnouncer'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

const PUBLIC_NAV = [
  { path: '/', label: 'Inicio', icon: '📊' },
  { path: '/fotos', label: 'Fotos', icon: '📸' },
  { path: '/clima', label: 'Clima', icon: '🌤️' },
]

export function PublicLayout() {
  const { user, isAdmin, authOffline, refreshAuth } = useAuth()
  const { status } = useTelemetry()
  const location = useLocation()
  const pageLabel = useDocumentTitle(location.pathname)
  // The installed PWA starts at the public dashboard. Keep the local-alert
  // fallback alive there too while an administrator is signed in.
  useIrrigationAlerts(status)

  const adminTarget = isAdmin && user ? '/admin' : '/admin/login'
  const adminLabel = isAdmin && user ? 'Panel admin' : 'Acceso admin'

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Saltar al contenido
      </a>
      <RouteAnnouncer pathname={location.pathname} label={pageLabel} />

      <header className="app-header">
        <div className="app-header-inner">
          <Link to="/" className="brand" aria-label="Invernadero — inicio">
            <span className="brand-mark" aria-hidden="true">
              🌱
            </span>
            <span>Invernadero</span>
          </Link>

          <nav className="desktop-nav" aria-label="Navegación pública">
            {PUBLIC_NAV.map(item => (
              <Link
                key={item.path}
                to={item.path}
                className="nav-link"
                aria-current={location.pathname === item.path ? 'page' : undefined}
              >
                <span className="nav-icon" aria-hidden="true">
                  {item.icon}
                </span>
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="header-actions">
            {user && <NotificationBell />}
            <Link to={adminTarget} className="btn btn-secondary btn-sm">
              {adminLabel}
            </Link>
          </div>
        </div>
      </header>

      <main id="main-content" className="app-main" tabIndex={-1}>
        <div className="container">
          <InstallPrompt />
          {authOffline && (
            <div className="alert alert-warning" role="status">
              <span style={{ flex: 1 }}>
                Sin conexión con el servidor. Las lecturas en vivo pueden estar desactualizadas.
              </span>
              <button type="button" className="btn btn-secondary btn-sm" onClick={refreshAuth}>
                Reintentar
              </button>
            </div>
          )}
          <Outlet />
        </div>
      </main>

      <footer className="app-footer">
        Invernadero Automatizado · Santa Lucía Cotzumalguapa, Escuintla, Guatemala
      </footer>

      <nav className="bottom-nav" aria-label="Accesos rápidos">
        {PUBLIC_NAV.map(item => (
          <Link
            key={item.path}
            to={item.path}
            className="bottom-nav-item"
            aria-current={location.pathname === item.path ? 'page' : undefined}
          >
            <span className="bottom-nav-icon" aria-hidden="true">
              {item.icon}
            </span>
            {item.label}
          </Link>
        ))}
        <Link to={adminTarget} className="bottom-nav-item">
          <span className="bottom-nav-icon" aria-hidden="true">
            🔐
          </span>
          {isAdmin && user ? 'Panel' : 'Admin'}
        </Link>
      </nav>

      <PwaStatus />
    </div>
  )
}
