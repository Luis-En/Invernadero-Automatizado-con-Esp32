import { useCallback, useEffect, useState } from 'react'
import { format } from 'date-fns'
import { api } from '../../api'
import { formatServerTime } from '../../utils/time'

const ACTIONS = [
  '',
  'auth.login_failed',
  'auth.login_blocked',
  'auth.login_success',
  'actuator.control',
  'crop.create',
  'crop.update',
  'crop.delete',
  'crop.params.create',
  'crop.params.update',
  'config.apply',
  'user.create',
]

export function AdminLogs() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [action, setAction] = useState('')
  const [username, setUsername] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.getAdminLogs({
        action: action || undefined,
        username: username.trim() || undefined,
        limit: 200,
      })
      setLogs(data)
    } catch (e) {
      setError(e.message || 'No se pudo cargar la auditoría')
    } finally {
      setLoading(false)
    }
  }, [action, username])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Auditoría</h1>
          <p className="page-subtitle">
            Acciones administrativas y intentos de inicio de sesión.
          </p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={load} disabled={loading}>
          {loading ? 'Cargando…' : '🔄 Actualizar'}
        </button>
      </div>

      <div className="page-actions" style={{ marginBottom: '1rem' }}>
        <div className="form-group" style={{ margin: 0 }}>
          <label className="form-label" htmlFor="audit-action">
            Acción
          </label>
          <select
            id="audit-action"
            className="form-control"
            value={action}
            onChange={event => setAction(event.target.value)}
          >
            {ACTIONS.map(value => (
              <option key={value || 'all'} value={value}>
                {value || 'Todas'}
              </option>
            ))}
          </select>
        </div>
        <div className="form-group" style={{ margin: 0 }}>
          <label className="form-label" htmlFor="audit-user">
            Usuario
          </label>
          <input
            id="audit-user"
            className="form-control"
            value={username}
            onChange={event => setUsername(event.target.value)}
            placeholder="Filtrar por usuario"
          />
        </div>
      </div>

      {error && (
        <div className="alert alert-critical" role="alert">
          {error}
        </div>
      )}

      {loading && logs.length === 0 ? (
        <div className="loading-state" role="status" aria-live="polite">
          <span className="spinner" aria-hidden="true" />
          <p>Cargando auditoría…</p>
        </div>
      ) : logs.length === 0 ? (
        <div className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: '3rem' }}>
            <p>No hay registros para el filtro seleccionado.</p>
          </div>
        </div>
      ) : (
        <div className="card">
          <div
            className="table-container"
            tabIndex={0}
            role="region"
            aria-label="Registro de auditoría administrativa"
          >
            <table className="table-cards">
              <caption className="visually-hidden">Registro de auditoría administrativa</caption>
              <thead>
                <tr>
                  <th scope="col">Fecha</th>
                  <th scope="col">Usuario</th>
                  <th scope="col">Acción</th>
                  <th scope="col">Recurso</th>
                  <th scope="col">IP</th>
                  <th scope="col">Detalles</th>
                </tr>
              </thead>
              <tbody>
                {logs.map(log => (
                  <tr key={log.id}>
                    <td data-label="Fecha">
                      {formatServerTime(log.timestamp, d => format(d, 'dd/MM/yyyy HH:mm:ss'))}
                    </td>
                    <td data-label="Usuario">{log.username || '—'}</td>
                    <td data-label="Acción">
                      <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                        {log.action}
                      </code>
                    </td>
                    <td data-label="Recurso">{log.resource}</td>
                    <td data-label="IP">{log.ip || '—'}</td>
                    <td data-label="Detalles">
                      <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                        {log.details ? JSON.stringify(log.details) : '—'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
