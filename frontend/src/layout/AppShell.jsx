import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import Icon from '../components/Icon'
import LeafBackground from '../components/LeafBackground'
import sidebarPhoto from '../assets/sidebar-leaves.webp'
import { Link } from '../components/ui'
import { navItems, workspaceRoles } from '../lib/routes'
import { initials, useLastEri, useSettings } from '../lib/settings'
import { endpoints, useApi } from '../services/api'
import { pctChange, sum } from '../lib/format'

function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 48 48" aria-hidden="true">
      <path d="M10 40c0-17 10-28 30-31-2 19-12 30-30 31Z" fill="url(#leafA)" />
      <path d="M8 42c3-9 8-15 15-20" stroke="#0d3b2b" strokeWidth="2.2" strokeLinecap="round" fill="none" opacity=".55" />
      <path d="M6 33c-1-9 3-16 11-20-1 9-4 15-11 20Z" fill="url(#leafB)" />
      <defs>
        <linearGradient id="leafA" x1="10" y1="40" x2="40" y2="9"><stop stopColor="#2fa865" /><stop offset="1" stopColor="#b9f0b6" /></linearGradient>
        <linearGradient id="leafB" x1="6" y1="33" x2="17" y2="13"><stop stopColor="#1d7d4c" /><stop offset="1" stopColor="#7fd38f" /></linearGradient>
      </defs>
    </svg>
  )
}

function useOutsideClose(open, setOpen) {
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    const onPointer = (event) => { if (ref.current && !ref.current.contains(event.target)) setOpen(false) }
    const onKey = (event) => { if (event.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onPointer); document.removeEventListener('keydown', onKey) }
  }, [open, setOpen])
  return ref
}

function useNotifications(enabled) {
  const demand = useApi(endpoints.exportDemand, { enabled })
  const ledger = useApi(endpoints.passports, { enabled })
  const lastEri = useLastEri()

  return useMemo(() => {
    if (!enabled) return []
    const items = []
    if (demand.data?.forecast?.length) {
      const next = sum(demand.data.forecast, 'forecast_export_volume_kg')
      const last = sum(demand.data.history.slice(-12), 'export_volume_kg')
      const change = pctChange(next, last)
      items.push({ id: 'demand', icon: 'trend', tone: change >= 0 ? 'green' : 'amber', title: `Export demand ${change >= 0 ? 'up' : 'down'} ${Math.abs(change).toFixed(1)}%`, body: 'Next 12-month forecast vs the latest 12 observed months.', to: '/demand-forecast' })
    }
    if (ledger.data) {
      items.push(ledger.data.ledger_valid
        ? { id: 'ledger', icon: 'shield', tone: 'green', title: 'Traceability ledger verified', body: `${ledger.data.passports.length} batch passports · ${ledger.data.ledger_records} hash-linked records.`, to: '/digital-passport' }
        : { id: 'ledger', icon: 'alert', tone: 'red', title: 'Ledger integrity issue', body: `Hash chain verification failed at record ${ledger.data.broken_record}.`, to: '/digital-passport' })
    }
    items.push(lastEri
      ? { id: 'eri', icon: 'clipboard', tone: lastEri.score >= 80 ? 'green' : 'amber', title: `Last ERI score: ${lastEri.score}/100`, body: `${lastEri.band} · ${lastEri.destination_country}`, to: '/export-readiness' }
      : { id: 'eri', icon: 'clipboard', tone: 'amber', title: 'Export readiness not assessed', body: 'Calculate your Export Readiness Index to get next steps.', to: '/export-readiness' })
    if (demand.error) items.push({ id: 'demand-error', icon: 'alert', tone: 'red', title: 'Forecast service unavailable', body: demand.error, to: '/settings' })
    return items
  }, [enabled, demand.data, demand.error, ledger.data, lastEri])
}

export default function AppShell({ activeKey, children, contentClassName = '', notificationsEnabled = true }) {
  const settings = useSettings()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [notifOpen, setNotifOpen] = useState(false)
  const [userOpen, setUserOpen] = useState(false)
  const [readIds, setReadIds] = useState(() => new Set())
  const notifRef = useOutsideClose(notifOpen, setNotifOpen)
  const userRef = useOutsideClose(userOpen, setUserOpen)
  // Component 02 pages do not depend on Component 04 model outputs. Avoid
  // background forecast requests there, especially before those models exist.
  const notifications = useNotifications(settings.notifications && notificationsEnabled)
  const unread = notifications.filter((item) => !readIds.has(`${item.id}:${item.title}`)).length
  const activeItem = navItems.find((item) => item.key === activeKey)
  const workspace = workspaceRoles[settings.role] || workspaceRoles.seller

  useEffect(() => {
    document.body.classList.toggle('no-scroll', sidebarOpen)
    return () => document.body.classList.remove('no-scroll')
  }, [sidebarOpen])

  const closeMenus = () => { setSidebarOpen(false); setNotifOpen(false); setUserOpen(false) }

  return (
    <div className={`app-shell ${sidebarOpen ? 'sidebar-open' : ''}`}>
      <LeafBackground animated={settings.animatedBackground} />
      <aside className="sidebar" aria-label="Sidebar">
        <div className="sidebar-brand">
          <BrandMark />
          <div><strong>TeaExportAI</strong><span>Sri Lanka Tea Intelligence</span></div>
          <button type="button" className="sidebar-close" aria-label="Close navigation" onClick={() => setSidebarOpen(false)}><Icon name="close" /></button>
        </div>
        <div className="sidebar-nav-scroll">
          <nav className="sidebar-nav" aria-label="Main navigation">
            {navItems.map((item, index) => (
              <Fragment key={item.key}>
                {index > 0 && item.group !== navItems[index - 1].group && <span className="sidebar-divider" role="separator" />}
                <Link to={item.path} className={`sidebar-link ${item.key === activeKey ? 'active' : ''}`} aria-current={item.key === activeKey ? 'page' : undefined} aria-label={item.label} onClick={(event) => { closeMenus(); if (event.detail > 0) event.currentTarget.blur() }}>
                  <span className="sidebar-tile"><Icon name={item.icon} size={24} /></span>
                  <span className="sidebar-label">{item.label}</span>
                </Link>
              </Fragment>
            ))}
          </nav>
        </div>
        <img className="sidebar-photo" src={sidebarPhoto} alt="" aria-hidden="true" />
        <div className="sidebar-footer">
          <span className="sidebar-footer-icon"><Icon name="sparkle" size={24} /></span>
          <div><strong>AI-Powered</strong><span>Tea Export Intelligence Platform</span><small>Sri Lanka</small></div>
        </div>
      </aside>
      <button type="button" className="sidebar-backdrop" aria-label="Close navigation" tabIndex={-1} onClick={() => setSidebarOpen(false)} />

      <div className="main-shell">
        <header className="topbar">
          <button type="button" className="icon-button menu-button" aria-label="Open navigation" onClick={() => setSidebarOpen(true)}><Icon name="menu" /></button>
          <span className="topbar-title">{activeItem?.label || 'TeaExportAI'}</span>
          <div className="topbar-actions">
            <div className="dropdown" ref={notifRef}>
              <button type="button" className="icon-button" aria-label={`Notifications${unread ? ` (${unread} unread)` : ''}`} aria-expanded={notifOpen} onClick={() => { setNotifOpen(!notifOpen); setUserOpen(false) }}>
                <Icon name="bell" size={21} />
                {unread > 0 && <span className="badge-dot">{unread}</span>}
              </button>
              {notifOpen && (
                <div className="dropdown-menu notif-menu" role="menu">
                  <div className="dropdown-header"><strong>Notifications</strong>{notifications.length > 0 && <button type="button" className="text-button" onClick={() => setReadIds(new Set(notifications.map((item) => `${item.id}:${item.title}`)))}>Mark all read</button>}</div>
                  {!settings.notifications ? <p className="dropdown-empty">Notifications are turned off. <Link to="/settings" onClick={closeMenus}>Enable in Settings</Link></p>
                    : notifications.length === 0 ? <p className="dropdown-empty">Loading updates…</p>
                      : notifications.map((item) => (
                        <Link key={item.id} to={item.to} className={`notif-item ${readIds.has(`${item.id}:${item.title}`) ? 'is-read' : ''}`} onClick={() => { setReadIds(new Set([...readIds, `${item.id}:${item.title}`])); closeMenus() }}>
                          <span className={`stat-icon tone-${item.tone}`}><Icon name={item.icon} size={17} /></span>
                          <span><strong>{item.title}</strong><small>{item.body}</small></span>
                        </Link>
                      ))}
                </div>
              )}
            </div>
            <div className="dropdown" ref={userRef}>
              <button type="button" className="user-button" aria-expanded={userOpen} onClick={() => { setUserOpen(!userOpen); setNotifOpen(false) }}>
                <span className="avatar">{initials(settings.displayName)}</span>
                <span className="user-name">{settings.displayName || 'User'}</span>
                <Icon name="chevronDown" size={16} />
              </button>
              {userOpen && (
                <div className="dropdown-menu user-menu" role="menu">
                  <div className="dropdown-profile"><span className="avatar">{initials(settings.displayName)}</span><div><strong>{settings.displayName || 'User'}</strong><small>{settings.organisation || workspace.title}</small></div></div>
                  <Link to={workspace.path} className="menu-item" onClick={closeMenus}><Icon name="user" size={17} />My workspace</Link>
                  <Link to="/reports" className="menu-item" onClick={closeMenus}><Icon name="file" size={17} />Reports</Link>
                  <Link to="/settings" className="menu-item" onClick={closeMenus}><Icon name="settings" size={17} />Settings</Link>
                </div>
              )}
            </div>
          </div>
        </header>
        <main className={`page ${contentClassName}`} id="main-content">{children}</main>
        <footer className="app-footer">© {new Date().getFullYear()} TeaExportAI · Planning intelligence for Sri Lankan tea exporters. Forecasts are model estimates, not guarantees.</footer>
      </div>
    </div>
  )
}
