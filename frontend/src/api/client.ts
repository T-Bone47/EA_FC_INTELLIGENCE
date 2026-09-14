/**
 * API client — the ONLY place that talks to the backend.
 * Relative URLs only (same-origin via Vite proxy in dev, same-origin in prod).
 * Errors surface the backend's `detail` plus `request_id` for support; the UI
 * never invents data the API didn't return.
 */

const TOKEN_KEY = 'eafc.token'

export class ApiError extends Error {
  status: number
  detail: string
  requestId?: string
  constructor(status: number, detail: string, requestId?: string) {
    super(detail)
    this.status = status
    this.detail = detail
    this.requestId = requestId
  }
}

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}
export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch { /* private mode — session-only auth */ }
}

async function request<T>(method: string, path: string, body?: unknown,
                          auth = true): Promise<T> {
  const headers: Record<string, string> = { 'Accept': 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = auth ? getToken() : null
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  const rid = res.headers.get('x-request-id') || undefined
  if (res.status === 204) return undefined as T

  let data: any = null
  const text = await res.text()
  if (text) {
    try { data = JSON.parse(text) } catch { /* non-JSON body */ }
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    if (data && typeof data.detail === 'string') detail = data.detail
    else if (data && Array.isArray(data.detail)) {
      detail = data.detail.map((d: any) =>
        `${(d.loc || []).slice(1).join('.') || 'body'}: ${d.msg}`).join('; ')
    }
    throw new ApiError(res.status, detail, data?.request_id || rid)
  }
  return data as T
}

export const api = {
  get: <T,>(p: string) => request<T>('GET', p),
  post: <T,>(p: string, b?: unknown) => request<T>('POST', p, b),
  put: <T,>(p: string, b?: unknown) => request<T>('PUT', p, b),
  patch: <T,>(p: string, b?: unknown) => request<T>('PATCH', p, b),
  del: <T,>(p: string) => request<T>('DELETE', p),
}

export function qs(params: Record<string, unknown>): string {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue
    sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}
