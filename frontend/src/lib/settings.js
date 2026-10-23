import { useSyncExternalStore } from 'react'

const SETTINGS_KEY = 'teaexport.settings'
const ERI_KEY = 'teaexport.lastEri'
const CHANGE_EVENT = 'teaexport:storage'

export const defaultSettings = {
  defaultMarket: 'Japan',
  defaultTeaType: 'Black Tea',
  defaultCapacity: 10,
  passportSiteUrl: '',
  notifications: true,
  animatedBackground: true,
}

export const markets = [
  ['Japan', '🇯🇵'], ['United States', '🇺🇸'], ['United Kingdom', '🇬🇧'],
  ['Germany', '🇩🇪'], ['United Arab Emirates', '🇦🇪'], ['Australia', '🇦🇺'],
]

export const teaTypes = ['Black Tea', 'Green Tea', 'White Tea', 'Oolong Tea']

function read(key) {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key, value) {
  try {
    if (value == null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch {
    // Storage can be unavailable (private mode); settings then last for the session only.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT))
}

function subscribe(callback) {
  window.addEventListener(CHANGE_EVENT, callback)
  window.addEventListener('storage', callback)
  return () => {
    window.removeEventListener(CHANGE_EVENT, callback)
    window.removeEventListener('storage', callback)
  }
}

// useSyncExternalStore needs stable snapshots, so parse once per raw string.
const parsed = new Map()
function parseCached(raw, fallback) {
  if (!raw) return fallback
  if (!parsed.has(raw)) {
    try { parsed.set(raw, JSON.parse(raw)) } catch { parsed.set(raw, fallback) }
  }
  return parsed.get(raw)
}

const mergedSettings = new Map()
export function useSettings() {
  const raw = useSyncExternalStore(subscribe, () => read(SETTINGS_KEY))
  if (!mergedSettings.has(raw)) mergedSettings.set(raw, { ...defaultSettings, ...parseCached(raw, {}) })
  return mergedSettings.get(raw)
}

export function saveSettings(settings) {
  write(SETTINGS_KEY, JSON.stringify(settings))
}

export function resetSettings() {
  write(SETTINGS_KEY, null)
}

export function useLastEri() {
  return parseCached(useSyncExternalStore(subscribe, () => read(ERI_KEY)), null)
}

export function saveLastEri(result, inputs) {
  write(ERI_KEY, JSON.stringify({ ...result, inputs, saved_at: new Date().toISOString() }))
}

export function clearLastEri() {
  write(ERI_KEY, null)
}

export function initials(name) {
  return (name || 'User').split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join('')
}
