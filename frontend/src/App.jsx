import { Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { TelemetryProvider } from './context/TelemetryContext'
import { WeatherProvider } from './context/WeatherContext'
import { Layout } from './components/Layout'
import { PublicLayout } from './components/PublicLayout'
import { RequireAuth } from './components/RequireAuth'

const AdminLogin = lazy(() =>
  import('./pages/admin/AdminLogin').then(m => ({ default: m.AdminLogin }))
)

const PublicDashboard = lazy(() =>
  import('./pages/public/PublicDashboard').then(m => ({ default: m.PublicDashboard }))
)
const PublicPhotos = lazy(() =>
  import('./pages/public/PublicPhotos').then(m => ({ default: m.PublicPhotos }))
)
const PublicWeather = lazy(() =>
  import('./pages/public/PublicWeather').then(m => ({ default: m.PublicWeather }))
)
const AdminPanel = lazy(() =>
  import('./pages/admin/AdminPanel').then(m => ({ default: m.AdminPanel }))
)
const AdminCrops = lazy(() =>
  import('./pages/admin/AdminCrops').then(m => ({ default: m.AdminCrops }))
)
const AdminConfig = lazy(() =>
  import('./pages/admin/AdminConfig').then(m => ({ default: m.AdminConfig }))
)
const Photos = lazy(() => import('./pages/Photos').then(m => ({ default: m.Photos })))
const History = lazy(() => import('./pages/History').then(m => ({ default: m.History })))
const Events = lazy(() => import('./pages/Events').then(m => ({ default: m.Events })))
const Weather = lazy(() => import('./pages/Weather').then(m => ({ default: m.Weather })))
const AdminLogs = lazy(() =>
  import('./pages/admin/AdminLogs').then(m => ({ default: m.AdminLogs }))
)
const AdminUsers = lazy(() =>
  import('./pages/admin/AdminUsers').then(m => ({ default: m.AdminUsers }))
)

function RouteFallback() {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <p>Cargando…</p>
    </div>
  )
}

function AppRoutes() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route path="/login" element={<Navigate to="/admin/login" replace />} />

        <Route element={<PublicLayout />}>
          <Route index element={<PublicDashboard />} />
          <Route path="/fotos" element={<PublicPhotos />} />
          <Route path="/clima" element={<PublicWeather />} />
        </Route>

        <Route
          path="/admin/login"
          element={<AdminLogin />}
        />
        <Route
          path="/admin"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<AdminPanel />} />
          <Route path="eventos" element={<Events />} />
          <Route path="historial" element={<History />} />
          <Route path="fotos" element={<Photos />} />
          <Route path="clima" element={<Weather />} />
          <Route path="cultivos" element={<AdminCrops />} />
          <Route path="configuracion" element={<AdminConfig />} />
          <Route path="logs" element={<AdminLogs />} />
          <Route path="usuarios" element={<AdminUsers />} />
        </Route>

        {/* Legacy aliases. */}
        <Route path="/photos" element={<Navigate to="/fotos" replace />} />
        <Route path="/historial" element={<Navigate to="/admin/historial" replace />} />
        <Route path="/history" element={<Navigate to="/admin/historial" replace />} />
        <Route path="/eventos" element={<Navigate to="/admin/eventos" replace />} />
        <Route path="/events" element={<Navigate to="/admin/eventos" replace />} />
        <Route path="/configuracion" element={<Navigate to="/admin/configuracion" replace />} />
        <Route path="/config" element={<Navigate to="/admin/configuracion" replace />} />
        <Route path="/cultivos" element={<Navigate to="/admin/cultivos" replace />} />
        <Route path="/crops" element={<Navigate to="/admin/cultivos" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}

function App() {
  return (
    <AuthProvider>
      <TelemetryProvider>
        <WeatherProvider>
          <AppRoutes />
        </WeatherProvider>
      </TelemetryProvider>
    </AuthProvider>
  )
}

export default App
