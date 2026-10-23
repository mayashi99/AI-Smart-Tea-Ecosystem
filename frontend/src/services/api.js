import { useEffect, useState } from 'react'

export const API_BASE = '/api/component04'

export const endpoints = {
  trainOutput: import.meta.env.VITE_API_URL || `${API_BASE}/train-output`,
  exportDemand: `${API_BASE}/export-demand`,
  combinedAuctionPrice: `${API_BASE}/combined-auction-price`,
  usdForecast: `${API_BASE}/usd-forecast`,
  exportAdvisor: `${API_BASE}/export-advisor`,
  exportReadiness: `${API_BASE}/export-readiness`,
  passports: `${API_BASE}/digital-passports`,
  passportEvents: `${API_BASE}/digital-passports/events`,
  passportVerify: `${API_BASE}/digital-passports/verify`,
  zoneIntelligence: `${API_BASE}/zone-intelligence`,
  zoneScore: `${API_BASE}/zone-intelligence/score`,
  currentUser: '/api/auth/me',
  roleHint: '/api/auth/role-hint',
  logout: '/api/auth/logout',
  users: '/api/auth/users',
  userRequests: '/api/auth/user-requests',
  userApproval: (userId) => `/api/auth/users/${userId}/approval`,
  auditLog: '/api/auth/audit',
  publicPassport: (publicId) => `${API_BASE}/digital-passports/public/${encodeURIComponent(publicId)}`,
  reportExport: '/api/auth/report-export',
}

const fallbackMessages = {
  [endpoints.trainOutput]: 'Train output load failed',
  [endpoints.exportDemand]: 'Export demand forecast is not available yet',
  [endpoints.combinedAuctionPrice]: 'Combined auction price forecast is not available. Train the model first.',
  [endpoints.usdForecast]: 'USD/LKR forecast is not available. Train the USD forecasting models first.',
  [endpoints.passports]: 'Could not load passports',
  [endpoints.zoneIntelligence]: 'Could not load zone data',
}

async function parse(response, fallback) {
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : fallback)
  return payload
}

function csrfHeaders() {
  const match = document.cookie.match(/(?:^|;\s*)tea_csrf=([^;]+)/)
  return match ? { 'X-CSRF-Token': decodeURIComponent(match[1]) } : {}
}

// Model outputs only change when models are retrained, so GET responses are
// cached for the session and shared between pages (Home, Reports, etc.).
const cache = new Map()

export function getJSON(url, { force = false } = {}) {
  if (force || !cache.has(url)) {
    const request = fetch(url, { credentials: 'include' })
      .then((response) => parse(response, fallbackMessages[url] || 'Request failed'))
      .catch((error) => { cache.delete(url); throw error })
    cache.set(url, request)
  }
  return cache.get(url)
}

export function invalidate(url) {
  if (url) cache.delete(url)
  else cache.clear()
}

export async function postJSON(url, body, fallback = 'Request failed') {
  const response = await fetch(url, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', ...csrfHeaders() }, body: JSON.stringify(body) })
  return parse(response, fallback)
}

export async function patchJSON(url, body, fallback = 'Request failed') {
  const response = await fetch(url, { method: 'PATCH', credentials: 'include', headers: { 'Content-Type': 'application/json', ...csrfHeaders() }, body: JSON.stringify(body) })
  return parse(response, fallback)
}

export function useApi(url, { enabled = true } = {}) {
  const [state, setState] = useState({ data: null, error: '', url: null, refreshing: false })
  const [version, setVersion] = useState(0)

  useEffect(() => {
    if (!enabled) return undefined
    let active = true
    getJSON(url, { force: version > 0 })
      .then((data) => { if (active) setState({ data, error: '', url, refreshing: false }) })
      .catch((error) => { if (active) setState({ data: null, error: error.message, url, refreshing: false }) })
    return () => { active = false }
  }, [url, enabled, version])

  const settled = state.url === url
  return {
    // While reloading, the previous data stays visible until the new response arrives.
    data: settled ? state.data : null,
    error: settled && !state.refreshing ? state.error : '',
    loading: enabled && (!settled || state.refreshing),
    reload: () => { setState((current) => ({ ...current, refreshing: true })); setVersion((value) => value + 1) },
  }
}
