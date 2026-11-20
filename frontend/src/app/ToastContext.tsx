import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PropsWithChildren,
} from 'react'

import {
  ToastContext,
  type ToastVariant,
} from './toast-context'

interface ToastMessage {
  id: number
  message: string
  variant: ToastVariant
}

function ToastItem({
  toast,
  dismiss,
}: {
  toast: ToastMessage
  dismiss: (id: number) => void
}) {
  useEffect(() => {
    const timeoutId = window.setTimeout(
      () => dismiss(toast.id),
      toast.variant === 'error' ? 6500 : 4500,
    )
    return () => window.clearTimeout(timeoutId)
  }, [dismiss, toast.id, toast.variant])

  return (
    <div
      className={`toast toast-${toast.variant}`}
      role={toast.variant === 'error' ? 'alert' : 'status'}
    >
      <span className="toast-indicator" aria-hidden="true">
        {toast.variant === 'error' ? '!' : '✓'}
      </span>
      <p>{toast.message}</p>
      <button
        aria-label="Bildirimi kapat"
        className="toast-dismiss"
        onClick={() => dismiss(toast.id)}
        type="button"
      >
        ×
      </button>
    </div>
  )
}

export function ToastProvider({ children }: PropsWithChildren) {
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  const nextId = useRef(0)

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const notify = useCallback(
    (message: string, variant: ToastVariant) => {
      const trimmedMessage = message.trim()
      if (!trimmedMessage) {
        return
      }

      const id = nextId.current++
      setToasts((current) => [
        ...current.slice(-3),
        { id, message: trimmedMessage, variant },
      ])
    },
    [],
  )

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div aria-label="Bildirimler" className="toast-viewport">
        {toasts.map((toast) => (
          <ToastItem dismiss={dismiss} key={toast.id} toast={toast} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}
