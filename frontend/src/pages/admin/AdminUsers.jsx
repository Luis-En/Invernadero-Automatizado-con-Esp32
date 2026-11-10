import { useEffect, useState } from 'react'
import { api } from '../../api'
import {
  passwordStrengthErrors,
  passwordStrengthScore,
} from '../../utils/passwordPolicy'

const EMPTY_FORM = { username: '', email: '', password: '', role: 'viewer' }

export function AdminUsers() {
  const [users, setUsers] = useState([])
  const [form, setForm] = useState(EMPTY_FORM)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const errors = passwordStrengthErrors(form.password, form.username)
  const score = passwordStrengthScore(form.password, form.username)

  const load = async () => {
    setLoading(true)
    try {
      setUsers(await api.getUsers())
    } catch (e) {
      setError(e.message || 'No se pudieron cargar los usuarios')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const submit = async event => {
    event.preventDefault()
    setError('')
    setNotice('')
    if (errors.length) {
      setError('La contraseña no cumple la política de seguridad')
      return
    }
    setSaving(true)
    try {
      await api.adminCreateUser({
        username: form.username.trim(),
        email: form.email.trim() || null,
        password: form.password,
        role: form.role,
      })
      setForm(EMPTY_FORM)
      setNotice('Usuario creado correctamente.')
      await load()
    } catch (e) {
      setError(e.message || 'No se pudo crear el usuario')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Usuarios</h1>
          <p className="page-subtitle">
            Altas con contraseña fuerte. Los usuarios viewer solo pueden consultar.
          </p>
        </div>
      </div>

      {error && (
        <div className="alert alert-critical" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="alert alert-success" role="status">
          {notice}
        </div>
      )}

      <div className="grid grid-2" style={{ alignItems: 'start' }}>
        <div className="card">
          <div className="card-header">➕ Nuevo usuario</div>
          <div className="card-body">
            <form onSubmit={submit}>
              <div className="form-group">
                <label className="form-label" htmlFor="new-username">
                  Usuario
                </label>
                <input
                  id="new-username"
                  className="form-control"
                  aria-label="Usuario"
                  value={form.username}
                  onChange={event => setForm({ ...form, username: event.target.value })}
                  autoComplete="off"
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="new-email">
                  Email (opcional)
                </label>
                <input
                  id="new-email"
                  type="email"
                  className="form-control"
                  aria-label="Email (opcional)"
                  value={form.email}
                  onChange={event => setForm({ ...form, email: event.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="new-role">
                  Rol
                </label>
                <select
                  id="new-role"
                  className="form-control"
                  value={form.role}
                  onChange={event => setForm({ ...form, role: event.target.value })}
                >
                  <option value="viewer">Viewer (solo lectura)</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="new-password">
                  Contraseña
                </label>
                <input
                  id="new-password"
                  type="password"
                  className="form-control"
                  aria-label="Contraseña"
                  value={form.password}
                  onChange={event => setForm({ ...form, password: event.target.value })}
                  autoComplete="new-password"
                  required
                />
                <div
                  className="form-hint"
                  aria-live="polite"
                  style={{
                    color:
                      !form.password
                        ? 'var(--color-text-muted)'
                        : errors.length
                          ? 'var(--color-critical)'
                          : 'var(--color-success)',
                  }}
                >
                  {!form.password
                    ? 'Mínimo 12 caracteres, mayúscula, minúscula, número y símbolo.'
                    : errors.length
                      ? errors.join(' · ')
                      : `Contraseña fuerte (${score}/7).`}
                </div>
              </div>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={saving || errors.length > 0}
              >
                {saving ? 'Creando…' : 'Crear usuario'}
              </button>
            </form>
          </div>
        </div>

        <div className="card">
          <div className="card-header">👥 Usuarios existentes</div>
          <div className="card-body" style={{ padding: 0 }}>
            {loading ? (
              <p style={{ padding: '1rem' }}>Cargando…</p>
            ) : (
              <div
                className="table-container"
                tabIndex={0}
                role="region"
                aria-label="Usuarios del sistema"
              >
                <table className="table-cards">
                  <caption className="visually-hidden">Usuarios del sistema</caption>
                  <thead>
                    <tr>
                      <th scope="col">Usuario</th>
                      <th scope="col">Rol</th>
                      <th scope="col">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map(user => (
                      <tr key={user.id}>
                        <td data-label="Usuario">{user.username}</td>
                        <td data-label="Rol">
                          <span className={`badge ${user.role === 'admin' ? 'badge-on' : 'badge-off'}`}>
                            {user.role}
                          </span>
                        </td>
                        <td data-label="Estado">{user.is_active ? 'Activo' : 'Inactivo'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
