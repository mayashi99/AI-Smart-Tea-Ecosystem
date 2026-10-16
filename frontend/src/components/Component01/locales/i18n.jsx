import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import en from './en.json'
import si from './si.json'
import ta from './ta.json'

const DICT = { en, si, ta }
const Context = createContext(null)

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(() => {
    try { const saved = localStorage.getItem('teaguard-language'); return DICT[saved] ? saved : 'en' } catch { return 'en' }
  })
  useEffect(() => { document.documentElement.lang = language }, [language])
  const setLanguage = (code) => {
    if (!DICT[code]) return
    setLanguageState(code)
    try { localStorage.setItem('teaguard-language', code) } catch { /* private mode */ }
  }
  const context = useMemo(() => ({
    language, setLanguage,
    t: (key) => DICT[language][key] || en[key] || key,
    diseaseName: (key) => DICT[language][String(key || '').toLowerCase()] || key || '—',
  }), [language])
  return <Context.Provider value={context}>{children}</Context.Provider>
}
export function useLanguage() {
  const value = useContext(Context)
  if (!value) throw new Error('LanguageProvider is missing')
  return value
}
