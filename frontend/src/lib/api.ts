const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
).replace(/\/+$/, '')

const TOKEN_KEY = 'kahvecell_access_token'

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

function getErrorMessage(payload: unknown, status: number): string {
  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    const detail = (payload as { detail?: unknown }).detail
    if (typeof detail === 'string') {
      return detail
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          typeof item === 'object' &&
          item !== null &&
          'msg' in item &&
          typeof item.msg === 'string'
            ? item.msg
            : '',
        )
        .filter(Boolean)
        .join(' ')
    }
  }
  return `İstek başarısız oldu (${status}).`
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    throw new ApiError(getErrorMessage(payload, response.status), response.status)
  }

  return (await response.json()) as T
}

export async function apiEventStream(
  path: string,
  signal: AbortSignal,
): Promise<ReadableStream<Uint8Array>> {
  const headers = new Headers({ Accept: 'text/event-stream' })
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers,
    cache: 'no-store',
    signal,
  })

  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    throw new ApiError(getErrorMessage(payload, response.status), response.status)
  }
  if (!response.headers.get('content-type')?.includes('text/event-stream')) {
    throw new Error('Canlı bildirim bağlantısı beklenen formatta değil.')
  }
  if (!response.body) {
    throw new Error('Canlı bildirim akışı kullanılamıyor.')
  }

  return response.body
}
