import type { ReactNode } from 'react'

export function LoadingState({ message }: { message: string }) {
  return (
    <section className="panel state-card loading-state" role="status">
      <span aria-hidden="true" className="loading-spinner" />
      <p>{message}</p>
    </section>
  )
}

export function ErrorState({
  message,
  onRetry,
  title = 'Bir şeyler ters gitti',
}: {
  message: string
  onRetry: () => void
  title?: string
}) {
  return (
    <section className="panel state-card error-state" role="alert">
      <span aria-hidden="true" className="state-icon error-state-icon">
        !
      </span>
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
      <button onClick={onRetry} type="button">
        Tekrar dene
      </button>
    </section>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <section className="panel state-card empty-state" role="status">
      <span aria-hidden="true" className="state-icon empty-state-icon">
        ☕
      </span>
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      {action}
    </section>
  )
}
