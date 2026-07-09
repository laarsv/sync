import { API_BASE } from '../apiBase'

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function request(method, path, body) {
  const opts = {
    method,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
  }
  if (body !== undefined) opts.body = JSON.stringify(body)

  const res = await fetch(`${API_BASE}${path}`, opts)

  if (res.status === 204) return null

  let data = null
  const text = await res.text()
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }

  if (!res.ok) {
    // FastAPI legt Fehlertexte in `detail` ab (String oder Validation-Array).
    let msg = `Fehler ${res.status}`
    if (data && typeof data === 'object' && data.detail) {
      msg = Array.isArray(data.detail)
        ? data.detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
        : String(data.detail)
    } else if (typeof data === 'string' && data) {
      msg = data
    }
    throw new ApiError(msg, res.status)
  }
  return data
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  put: (path, body) => request('PUT', path, body),
  patch: (path, body) => request('PATCH', path, body),
  del: (path) => request('DELETE', path),
}
