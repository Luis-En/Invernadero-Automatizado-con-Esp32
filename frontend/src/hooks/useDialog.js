import { useEffect, useRef } from 'react'

const FOCUSABLE = [
  'a[href]',
  'area[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'iframe',
  'object',
  'embed',
  '[contenteditable="true"]',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

/**
 * Accessible dialog behaviour shared by modals and the mobile drawer:
 * moves focus inside, traps Tab, closes on Escape, locks body scroll and
 * restores focus to the element that opened it.
 */
export function useDialog(open, onClose, containerRef) {
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    if (!open) return undefined

    const container = containerRef.current
    const previouslyFocused = document.activeElement
    const bodyOverflow = document.body.style.overflow
    const bodyPaddingRight = document.body.style.paddingRight
    const scrollbar = window.innerWidth - document.documentElement.clientWidth

    document.body.style.overflow = 'hidden'
    if (scrollbar > 0) document.body.style.paddingRight = `${scrollbar}px`

    const getFocusable = () =>
      Array.from(container?.querySelectorAll(FOCUSABLE) || []).filter(
        element => element.offsetParent !== null || element === document.activeElement
      )

    const focusFirst = () => {
      const preferred = container?.querySelector('[data-autofocus]')
      const target = preferred || getFocusable()[0] || container
      target?.focus?.()
    }

    // Wait for the portal to be mounted.
    const focusTimer = window.setTimeout(focusFirst, 0)

    const handleKeyDown = event => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onCloseRef.current?.()
        return
      }
      if (event.key !== 'Tab' || !container) return

      const focusable = getFocusable()
      if (focusable.length === 0) {
        event.preventDefault()
        container.focus?.()
        return
      }
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)

    return () => {
      window.clearTimeout(focusTimer)
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = bodyOverflow
      document.body.style.paddingRight = bodyPaddingRight
      previouslyFocused?.focus?.()
    }
  }, [open, containerRef])
}
