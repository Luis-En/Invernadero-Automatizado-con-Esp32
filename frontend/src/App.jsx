import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { TelemetryProvider } from './context/TelemetryContext'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { Photos } from './pages/Photos'
import { History } from './pages/History'
import { Events } from './pages/Events'
import { Config } from './pages/Config'
import { Crops } from './pages/Crops'
import { Login } from './pages/Login'

function ProtectedRoute({ children, adminOnly = false }) {
  const { user, loading, isAdmin } = useAuth()

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '200px' }}>
        <div style={{ fontSize: '1.5rem' }}>⏳</div>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (adminOnly && !isAdmin) {
    return <Navigate to="/" replace />
  }

  return children
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={
        <ProtectedRoute>
          <Layout />
        </ProtectedRoute>
      }>
        <Route path="/" element={<Dashboard />} />
        <Route path="/photos" element={<Photos />} />
        <Route path="/history" element={<History />} />
        <Route path="/events" element={<Events />} />
        <Route path="/config" element={<ProtectedRoute adminOnly><Config /></ProtectedRoute>} />
        <Route path="/crops" element={<ProtectedRoute adminOnly><Crops /></ProtectedRoute>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function App() {
  return (
    <AuthProvider>
      <TelemetryProvider>
        <AppRoutes />
      </TelemetryProvider>
    </AuthProvider>
  )
}

export default App