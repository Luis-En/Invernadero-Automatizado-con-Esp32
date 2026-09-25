import { Outlet, Link, useLocation, Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTelemetry } from '../context/TelemetryContext'

export function Layout() {
  const { user, logout, isAdmin } = useAuth()
  const { connected, status } = useTelemetry()
  const location = useLocation()

  if (!user) {
    return <Navigate to="/login" replace />
  }

  const navItems = [
    { path: '/', label: 'Dashboard', icon: '📊' },
    { path: '/photos', label: 'Fotos', icon: '📸' },
    { path: '/history', label: 'Historial', icon: '📈' },
    { path: '/events', label: 'Eventos', icon: '⚠️' },
  ]

  if (isAdmin) {
    navItems.push(
      { path: '/config', label: 'Configuración', icon: '⚙️' },
      { path: '/crops', label: 'Cultivos', icon: '🌱' }
    )
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header style={{
        background: 'var(--color-card)',
        borderBottom: '1px solid var(--color-border)',
        padding: '0.75rem 1rem',
        position: 'sticky',
        top: 0,
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '1rem',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <Link to="/" style={{ fontWeight: 700, fontSize: '1.25rem', color: 'var(--color-primary-dark)' }}>
            🌱 Invernadero
          </Link>
          <nav style={{ display: 'flex', gap: '0.25rem' }}>
            {navItems.map(item => (
              <Link
                key={item.path}
                to={item.path}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.375rem',
                  padding: '0.5rem 0.875rem',
                  borderRadius: 'var(--radius-sm)',
                  color: location.pathname === item.path ? 'var(--color-primary)' : 'var(--color-text)',
                  background: location.pathname === item.path ? 'rgba(45, 106, 79, 0.1)' : 'transparent',
                  fontWeight: 500,
                  fontSize: '0.875rem',
                }}
              >
                <span>{item.icon}</span> {item.label}
              </Link>
            ))}
          </nav>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontSize: '0.8125rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
            <span className={`status-dot ${connected ? 'online' : 'offline'}`}></span>
            <span>{connected ? 'Conectado' : 'Desconectado'}</span>
          </div>

          {status && (
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
              <span className={`badge ${status.field_esp32_online ? 'badge-on' : 'badge-off'}`}>
                🌿 Campo
              </span>
              <span className={`badge ${status.gateway_esp32_online ? 'badge-on' : 'badge-off'}`}>
                📡 Gateway
              </span>
              <span className={`badge ${status.camera_online ? 'badge-on' : 'badge-off'}`}>
                📷 Cámara
              </span>
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ color: 'var(--color-text-muted)' }}>{user.username}</span>
            <span style={{ color: 'var(--color-border)' }}>|</span>
            <button onClick={logout} className="btn btn-secondary btn-sm">
              Salir
            </button>
          </div>
        </div>
      </header>

      <main style={{ flex: 1, padding: '1.5rem 1rem' }}>
        <div className="container">
          <Outlet />
        </div>
      </main>

      <footer style={{
        padding: '1rem',
        textAlign: 'center',
        color: 'var(--color-text-muted)',
        fontSize: '0.75rem',
        borderTop: '1px solid var(--color-border)',
        background: 'var(--color-card)',
      }}>
        Invernadero Automatizado - Santa Lucía Cotzumalguapa, Escuintla, Guatemala
      </footer>
    </div>
  )
}