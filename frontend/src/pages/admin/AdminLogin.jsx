import { Login } from '../Login'

/** Admin login reuses the hardened form but always redirects to /admin. */
export function AdminLogin() {
  return <Login adminMode redirectTo="/admin" />
}
