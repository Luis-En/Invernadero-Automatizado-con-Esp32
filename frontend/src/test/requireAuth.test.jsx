import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { RequireAuth } from '../components/RequireAuth'
import { useAuth } from '../context/AuthContext'

vi.mock('../context/AuthContext', () => ({ useAuth: vi.fn() }))

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/admin"
          element={
            <RequireAuth>
              <div>contenido admin</div>
            </RequireAuth>
          }
        />
        <Route path="/admin/login" element={<div>login admin</div>} />
        <Route path="/" element={<div>inicio público</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('RequireAuth', () => {
  it('redirects anonymous visitors to the admin login', () => {
    useAuth.mockReturnValue({ user: null, loading: false, isAdmin: false })
    renderAt('/admin')
    expect(screen.getByText('login admin')).toBeInTheDocument()
  })

  it('keeps viewers out of the admin area', () => {
    useAuth.mockReturnValue({
      user: { username: 'viewer', role: 'viewer' },
      loading: false,
      isAdmin: false,
    })
    renderAt('/admin')
    expect(screen.getByText('inicio público')).toBeInTheDocument()
  })

  it('renders the admin content for an admin', () => {
    useAuth.mockReturnValue({
      user: { username: 'admin', role: 'admin' },
      loading: false,
      isAdmin: true,
    })
    renderAt('/admin')
    expect(screen.getByText('contenido admin')).toBeInTheDocument()
  })

  it('shows a loading state while the session is checked', () => {
    useAuth.mockReturnValue({ user: null, loading: true, isAdmin: false })
    renderAt('/admin')
    expect(screen.getByText('Comprobando sesión…')).toBeInTheDocument()
  })

  it('does not bounce to login when the session cannot be verified offline', () => {
    useAuth.mockReturnValue({
      user: null,
      loading: false,
      isAdmin: false,
      authOffline: true,
      refreshAuth: vi.fn(),
    })
    renderAt('/admin')
    expect(screen.getByText(/no se pudo verificar la sesión/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument()
    expect(screen.queryByText('login admin')).not.toBeInTheDocument()
  })
})
