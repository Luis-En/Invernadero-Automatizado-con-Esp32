import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Outlet, Link, useLocation, Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTelemetry } from '../context/TelemetryContext'
import { useDialog } from '../hooks/useDialog'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { useIrrigationAlerts } from '../hooks/useIrrigationAlerts'
import { NotificationBell } from './NotificationBell'
import { InstallHint, InstallPrompt } from './InstallPrompt'
import { PwaStatus } from './PwaStatus'
import { RouteAnnouncer } from './RouteAnnouncer'

function DeviceBadges({ status }) {
  if (!status) return null
  const devices = [
    { key: 'field', label: 'Campo', icon: '🌿', online: status.field_esp32_online },
    { key: 'gateway', label: 'Gateway', icon: '📡', online: status.gateway_esp32_online },
    { key: 'camera', label: 'Cámara', icon: '📷', online: status.camera_online },
  ]

  return (
    <div className="device-badges" aria-label="Estado de los dispositivos">
      {devices.map(device => (
        <span
          key={device.key}
          className={`device-badge ${device.online ? 'on' : 'off'}`}
          title={`${device.label}: ${device.online ? 'en línea' : 'sin conexión'}`}
        >
          <span aria-hidden="true">{device.icon}</span> {device.label}
        </span>
      ))}
    </div>
  )
}

export function Layout() {
  const { user, logout, isAdmin, authOffline, refreshAuth } = useAuth()
  const { connected, status } = useTelemetry()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const drawerRef = useRef(null)

  const pageLabel = useDocumentTitle(location.pathname)
  useIrrigationAlerts(status)
  useDialog(menuOpen, () => setMenuOpen(false), drawerRef)

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  if (!user) {
    return <Navigate to="/admin/login" replace />
  }

  const navItems = [
    { path: '/admin', label: 'Panel', icon: '🎛️', short: 'Panel' },
    { path: '/admin/eventos', label: 'Eventos', icon: '⚠️', short: 'Eventos' },
    { path: '/admin/historial', label: 'Historial', icon: '📈', short: 'Historial' },
    { path: '/admin/fotos', label: 'Fotos', icon: '📸', short: 'Fotos' },
    { path: '/admin/clima', label: 'Clima', icon: '🌤️', short: 'Clima' },
    { path: '/admin/cultivos', label: 'Cultivos', icon: '🌱', short: 'Cultivos' },
    { path: '/admin/configuracion', label: 'Configuración', icon: '⚙️', short: 'Config' },
    { path: '/admin/logs', label: 'Auditoría', icon: '📋', short: 'Logs' },
    { path: '/admin/usuarios', label: 'Usuarios', icon: '👥', short: 'Usuarios' },
  ]

  const primaryItems = navItems.filter(item =>
    ['/admin', '/admin/fotos', '/admin/eventos', '/admin/logs'].includes(item.path)
  )

  const isCurrent = path => location.pathname === path

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Saltar al contenido
      </a>
      <RouteAnnouncer pathname={location.pathname} label={pageLabel} />

      <header className="app-header">
        <div className="app-header-inner">
          <Link to="/admin" className="brand" aria-label="Invernadero — panel de administración">
            <span className="brand-mark" aria-hidden="true">
              🌱
            </span>
            <span>Invernadero</span>
          </Link>

          <nav className="desktop-nav" aria-label="Navegación principal">
            {navItems.map(item => (
              <Link
                key={item.path}
                to={item.path}
                className="nav-link"
                aria-current={isCurrent(item.path) ? 'page' : undefined}
              >
                <span className="nav-icon" aria-hidden="true">
                  {item.icon}
                </span>
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="header-actions">
            <DeviceBadges status={status} />

            <span
              className="conn-pill"
              role="status"
              aria-live="polite"
              aria-label={connected ? 'Datos en vivo conectados' : 'Sin conexión en tiempo real, reconectando'}
              title={connected ? 'WebSocket conectado' : 'Sin conexión en tiempo real'}
            >
              <span
                className={`status-dot ${connected ? 'online' : 'offline'}`}
                aria-hidden="true"
              />
              <span className="conn-label">{connected ? 'En vivo' : 'Reconectando'}</span>
            </span>

            <NotificationBell />

            <div className="user-menu">
              <span className="username" title={user.username}>
                {user.username}
              </span>
              <button type="button" onClick={logout} className="btn btn-secondary btn-sm">
                Salir
              </button>
            </div>

            <button
              type="button"
              className="icon-btn menu-btn"
              aria-label="Abrir menú de navegación"
              aria-expanded={menuOpen}
              aria-controls="app-drawer"
              onClick={() => setMenuOpen(true)}
            >
              <span aria-hidden="true">☰</span>
            </button>
          </div>
        </div>
      </header>

      <main id="main-content" className="app-main" tabIndex={-1}>
        <div className="container">
          <InstallPrompt />
          {authOffline && (
            <div className="alert alert-warning" role="status">
              <span style={{ flex: 1 }}>
                Sin conexión con el servidor. Se muestra la última sesión conocida; los datos
                pueden estar desactualizados.
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
        {primaryItems.map(item => (
          <Link
            key={item.path}
            to={item.path}
            className="bottom-nav-item"
            aria-current={isCurrent(item.path) ? 'page' : undefined}
          >
            <span className="bottom-nav-icon" aria-hidden="true">
              {item.icon}
            </span>
            {item.short}
          </Link>
        ))}
        <button
          type="button"
          className={`bottom-nav-item${menuOpen ? ' active' : ''}`}
          aria-label="Abrir menú de navegación"
          aria-expanded={menuOpen}
          aria-controls="app-drawer"
          onClick={() => setMenuOpen(true)}
        >
          <span className="bottom-nav-icon" aria-hidden="true">
            ☰
          </span>
          Menú
        </button>
      </nav>

      {menuOpen &&
        createPortal(
          <div
            className="drawer-scrim"
            onMouseDown={event => {
              if (event.target === event.currentTarget) setMenuOpen(false)
            }}
          >
            <aside
              id="app-drawer"
              ref={drawerRef}
              className="drawer"
              role="dialog"
              aria-modal="true"
              aria-label="Menú de navegación"
              tabIndex={-1}
            >
              <div className="drawer-header">
                <span className="brand">
                  <span className="brand-mark" aria-hidden="true">
                    🌱
                  </span>
                  <span>Invernadero</span>
                </span>
                <button
                  type="button"
                  className="icon-btn"
                  aria-label="Cerrar menú"
                  onClick={() => setMenuOpen(false)}
                  data-autofocus
                >
                  ×
                </button>
              </div>

              <nav className="drawer-nav" aria-label="Navegación principal">
                {navItems.map(item => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className="drawer-link"
                    aria-current={isCurrent(item.path) ? 'page' : undefined}
                  >
                    <span aria-hidden="true">{item.icon}</span>
                    {item.label}
                  </Link>
                ))}
              </nav>

              <div className="drawer-section">
                <div className="drawer-section-title">Estado</div>
                <div
                  className="status-indicator"
                  style={{ marginBottom: '0.5rem' }}
                  aria-live="polite"
                >
                  <span
                    className={`status-dot ${connected ? 'online' : 'offline'}`}
                    aria-hidden="true"
                  />
                  {connected ? 'Datos en vivo' : 'Reconectando…'}
                </div>
                <DeviceBadges status={status} />
              </div>

              <div className="drawer-section">
                <InstallHint />
              </div>

              <div className="drawer-section" style={{ marginTop: 'auto' }}>
                <div className="drawer-user">
                  <div>
                    <div className="drawer-section-title" style={{ marginBottom: '0.15rem' }}>
                      Sesión
                    </div>
                    <strong>{user.username}</strong>
                    <div className="form-hint">
                      {isAdmin ? 'Administrador' : 'Solo lectura'}
                    </div>
                  </div>
                  <button type="button" onClick={logout} className="btn btn-secondary btn-sm">
                    Salir
                  </button>
                </div>
              </div>
            </aside>
          </div>,
          document.body
        )}

      <PwaStatus />
    </div>
  )
}
