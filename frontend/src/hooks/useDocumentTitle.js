import { useEffect } from 'react'

const TITLES = {
  '/': 'Dashboard',
  '/fotos': 'Fotos',
  '/clima': 'Clima',
  '/historial': 'Historial',
  '/eventos': 'Eventos',
  '/configuracion': 'Configuración',
  '/cultivos': 'Cultivos',
  '/login': 'Iniciar sesión',
  '/admin': 'Panel',
  '/admin/login': 'Acceso administrador',
  '/admin/fotos': 'Fotos',
  '/admin/clima': 'Clima',
  '/admin/historial': 'Historial',
  '/admin/eventos': 'Eventos',
  '/admin/cultivos': 'Cultivos',
  '/admin/configuracion': 'Configuración',
  '/admin/logs': 'Auditoría',
  '/admin/usuarios': 'Usuarios',
}

/**
 * Keeps the document title meaningful for tabs, history and screen readers.
 * Returns the short page label so the route announcer can use the same source
 * without depending on effect ordering.
 */
export function useDocumentTitle(pathname) {
  const page = TITLES[pathname]
  const title = page ? `${page} · Invernadero Automatizado` : 'Invernadero Automatizado'

  useEffect(() => {
    document.title = title
  }, [title])

  return page || 'Invernadero'
}
