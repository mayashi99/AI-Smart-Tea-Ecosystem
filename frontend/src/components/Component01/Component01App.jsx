import { useEffect, useState } from 'react'
import { Activity, BellRing, Camera, ChartNoAxesCombined, ChevronDown, ClipboardList, CloudSun, LayoutDashboard, Leaf, Menu, ShieldCheck, X } from './ui/icons.jsx'
import { LanguageProvider, useLanguage } from './locales/i18n.jsx'
import { useRemote } from './hooks/useRemote.js'
import Dashboard from './pages/Dashboard.jsx'
import DiseaseDetection from './pages/DiseaseDetection.jsx'
import ClimateSeverity from './pages/ClimateSeverity.jsx'
import SpreadForecast from './pages/SpreadForecast.jsx'
import OfficerObservations from './pages/OfficerObservations.jsx'
import AlertsRisk from './pages/AlertsRisk.jsx'
import Recommendations from './pages/Recommendations.jsx'
import LeafBackground from '../LeafBackground'
import './styles/component01.css'

const NAV = [
  {id:'overview', icon:LayoutDashboard}, {id:'detection',icon:Camera},
  {id:'climate',icon:CloudSun}, {id:'forecast',icon:ChartNoAxesCombined},
  {id:'observations',icon:ClipboardList}, {id:'alerts',icon:BellRing},
  {id:'recommendations',icon:ShieldCheck},
]
const TITLE = { overview:'overviewTitle',detection:'detectionTitle',climate:'climateTitle',forecast:'forecastTitle',observations:'observationsTitle',alerts:'alertsTitle',recommendations:'recommendationsTitle' }
const DESC = { overview:'overviewDesc',detection:'detectionDesc',climate:'climateDesc',forecast:'forecastDesc',observations:'observationsDesc',alerts:'alertsDesc',recommendations:'recommendationsDesc' }
function activeFromHash() {
  const key = window.location.hash.replace(/^#\/?(?:component01\/)?/, '').split('/')[0]
  return NAV.some(({id})=>id===key) ? key : 'overview'
}
function TeaApp({ embedded = false, page: routedPage, onNavigate }) {
  const {t,language,setLanguage} = useLanguage()
  const [localPage, setPage] = useState(activeFromHash)
  const page = routedPage || localPage
  const [mobileNav, setMobileNav] = useState(false)
  const [latestImage, setLatestImage] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [focusBlock, setFocusBlock] = useState('')
  const [focusDisease, setFocusDisease] = useState('')
  const blocks = useRemote('/api/estate/blocks')
  const diseases = useRemote('/api/estate/diseases')
  const health = useRemote('/health')
  useEffect(() => {
    const sync = () => { setPage(activeFromHash()); setMobileNav(false) }
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
  }, [])
  const navigate = (target) => { if (onNavigate) { onNavigate(target); return } window.location.assign(`#/component01/${target}`); setPage(target); setMobileNav(false); window.scrollTo({top:0,behavior:'smooth'}) }
  const props = {navigate,blocks:blocks.data?.blocks?.map(x=>typeof x==='string'?x:x.block_id)||[],diseases:diseases.data?.diseases||[],latestImage,setLatestImage,forecast,setForecast,focusBlock,setFocusBlock,focusDisease,setFocusDisease}
  const Component = {overview:Dashboard,detection:DiseaseDetection,climate:ClimateSeverity,forecast:SpreadForecast,observations:OfficerObservations,alerts:AlertsRisk,recommendations:Recommendations}[page]
  return <div className={`tg-app${embedded ? ' tg-embedded' : ''}`} data-language={language}>
    {/* Render the Traceability animation directly for all seven disease pages. */}
    <LeafBackground animated />
    {!embedded && <aside className={`tg-sidebar ${mobileNav?'shown':''}`}>
      <div className="tg-brand"><div className="tg-brand-symbol"><Leaf size={26} strokeWidth={2.25}/></div><div><strong>TeaGuard<span>®</span></strong><small>INTELLIGENCE SYSTEM</small></div></div>
      <div className="tg-side-caption">{t('workspace')}</div>
      <nav aria-label={t('navigation')}>
        {NAV.map(({id,icon:Icon})=><button key={id} className={`tg-nav-item ${page===id?'active':''}`} type="button" onClick={()=>navigate(id)}><Icon size={19}/><span>{t(id)}</span>{page===id && <div className="tg-nav-dot"/>}</button>)}
      </nav>
      <div className="tg-side-bottom"><div className="tg-side-medallion"><Activity size={22}/></div><strong>{t('brand')}</strong><p>{t('subbrand')}</p><div className="tg-side-line"/><small>J26-IT-415 · COMPONENT 01</small></div>
    </aside>}
    {mobileNav && <button className="tg-backdrop" aria-label={t('close')} onClick={()=>setMobileNav(false)}/>}
    <div className="tg-main">
      <header className="tg-topbar">
        <div className="tg-topbar-left">{!embedded && <button type="button" className="tg-icon-btn tg-mobile-menu" aria-label={t('navigation')} onClick={()=>setMobileNav(v=>!v)}>{mobileNav?<X/>:<Menu/>}</button>}<span className="tg-breadcrumb">TeaGuard</span><span className="tg-breadcrumb-sep">/</span><span>{t(page)}</span></div>
        <div className="tg-topbar-right"><div className="tg-connection" title={health.error||health.data?.status||t('status')}><span className={health.data?.status==='ready'?'tg-online':'tg-offline'}/><span>{health.data?.status==='ready'?t('apiReady'):t('apiOffline')}</span></div>
          <label className="tg-lang" aria-label={t('changeLanguage')}><span>🌐</span><select value={language} onChange={e=>setLanguage(e.target.value)}><option value="en">English</option><option value="si">සිංහල</option><option value="ta">தமிழ்</option></select><ChevronDown size={14}/></label>
          <div className="tg-user-icon"><Leaf size={18}/></div>
        </div>
      </header>
      <main className="tg-content"><div className="tg-page-title"><div><div className="tg-eyebrow"><span className="tg-eyebrow-dot"/> TEA HEALTH INTELLIGENCE <span className="tg-eyebrow-line"/></div><h1>{t(TITLE[page])}</h1><p>{t(DESC[page])}</p></div><div className="tg-page-mark"><Leaf size={37}/></div></div><Component {...props}/></main>
      <footer className="tg-footer"><span>{t('footer')}</span><span>© {new Date().getFullYear()} · J26-IT-415</span></footer>
    </div>
  </div>
}
export default function Component01App(props) {return <LanguageProvider><TeaApp {...props}/></LanguageProvider>}
