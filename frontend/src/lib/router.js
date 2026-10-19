import { useSyncExternalStore } from 'react'

// Minimal History API router: keeps the existing URL scheme (including QR links
// such as /digital-passport?batch=...) while avoiding full page reloads.
const NAVIGATE_EVENT = 'teaexport:navigate'

function subscribe(callback) {
  window.addEventListener('popstate', callback)
  window.addEventListener(NAVIGATE_EVENT, callback)
  return () => {
    window.removeEventListener('popstate', callback)
    window.removeEventListener(NAVIGATE_EVENT, callback)
  }
}

const getLocation = () => `${window.location.pathname}${window.location.search}`

export function normalisePath(pathname) {
  return pathname.replace(/\/+$/, '') || '/'
}

export function useLocation() {
  const href = useSyncExternalStore(subscribe, getLocation)
  const url = new URL(href, window.location.origin)
  return { path: normalisePath(url.pathname), search: url.search, query: url.searchParams, href }
}

export function navigate(to, { replace = false } = {}) {
  if (to === getLocation()) return
  window.history[replace ? 'replaceState' : 'pushState']({}, '', to)
  window.dispatchEvent(new Event(NAVIGATE_EVENT))
  window.scrollTo({ top: 0 })
}
