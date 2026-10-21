const configured = import.meta.env.VITE_COMPONENT01_API_BASE_URL?.trim()
export const API_BASE = (configured || '').replace(/\/$/, '')

function errorMessage(detail, fallback) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg || d.message || 'Invalid field').join('; ')
  return fallback
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...options.headers } })
  } catch {
    throw new Error('Unable to connect to the tea intelligence API. Please check that the backend is running.')
  }
  let body
  try { body = await response.json() } catch { body = null }
  if (!response.ok) {
    const err = new Error(errorMessage(body?.detail, `Request failed (${response.status})`))
    err.status = response.status
    throw err
  }
  return body
}

export const get = (path) => request(path)
export const post = (path, obj) => request(path, { method: 'POST', body: JSON.stringify(obj) })
export const uploadImage = (file, options = {}) => {
  const form = new FormData()
  form.append('file', file)
  return request('/api/image/analyze', { ...options, method: 'POST', body: form })
}
export const assetUrl = (path) => !path ? '' : `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
