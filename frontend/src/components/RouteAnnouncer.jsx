import { useEffect, useRef, useState } from 'react'

/**
 * SPA route changes do not reload the document, so screen-reader users get no
 * page-change feedback. Announce the new page and move focus to the main
 * landmark (without scrolling) after each navigation.
 */
export function RouteAnnouncer({ pathname, label }) {
  const [message, setMessage] = useState('')
  const firstRender = useRef(true)

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }

    const main = document.getElementById('main-content')
    main?.focus?.({ preventScroll: true })
    setMessage(label ? `Página: ${label}` : '')
  }, [pathname, label])

  return (
    <div className="visually-hidden" role="status" aria-live="polite" aria-atomic="true">
      {message}
    </div>
  )
}
