import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

export function Login({ redirectTo = '/', adminMode = false }) {
  const { login, user, isAdmin } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  useDocumentTitle(adminMode ? '/admin/login' : '/login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (adminMode && user && isAdmin) {
    return <Navigate to={redirectTo} replace />
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      const target = location.state?.from || redirectTo
      navigate(target, { replace: true })
    } catch (e) {
      setError(e.message || 'Error de autenticación')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-container">
      <div className="login-card card">
        <div className="login-header">
          <h1>🌱 Invernadero</h1>
          <p>
            {adminMode
              ? 'Acceso al panel de administración'
              : 'Sistema de Automatización y Monitoreo'}
          </p>
        </div>

        {error && (
          <div className="alert alert-critical" role="alert" style={{ marginBottom: '1rem' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="login-username">
              Usuario
            </label>
            <input
              id="login-username"
              name="username"
              aria-label="Usuario"
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="form-control"
              placeholder="Usuario"
              autoComplete="username"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="login-password">
              Contraseña
            </label>
            <input
              id="login-password"
              name="password"
              aria-label="Contraseña"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="form-control"
              placeholder="Contraseña"
              autoComplete="current-password"
              required
            />
          </div>

          <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
            {loading ? 'Iniciando…' : 'Iniciar Sesión'}
          </button>
        </form>

        <div className="login-footer">
          <p>
            El administrador inicial se configura con <code>ADMIN_PASSWORD</code> en el archivo{' '}
            <code>.env</code> del servidor.
          </p>
        </div>
      </div>
    </main>
  )
}