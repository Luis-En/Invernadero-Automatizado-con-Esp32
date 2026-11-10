import { useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useDialog } from '../hooks/useDialog'

/**
 * Accessible modal used by Photos, Crops and the notification panel.
 * On phones it is presented as a bottom sheet; on larger screens as a
 * centred dialog. It is portalled so no ancestor overflow can clip it.
 */
export function Modal({ open, onClose, title, children, footer, size = 'md', id }) {
  const generatedId = useId()
  const titleId = id || `modal-title-${generatedId}`
  const dialogRef = useRef(null)

  useDialog(open, onClose, dialogRef)

  if (!open) return null

  return createPortal(
    <div
      className="modal-overlay"
      onMouseDown={event => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        ref={dialogRef}
        className={`modal modal-${size}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <div className="modal-header">
          <h2 className="modal-title" id={titleId}>
            {title}
          </h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Cerrar" data-autofocus>
            ×
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>,
    document.body
  )
}
