import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import Icon from '../components/Icon'
import LeafBackground from '../components/LeafBackground'
import sidebarPhoto from '../assets/sidebar-leaves.webp'
import teaExportLogo from '../assets/teaexport-logo.png'
import { Link } from '../components/ui'
import { navItems } from '../lib/routes'
import { canAccessPage, navigationForRole, roleLabels } from '../lib/permissions'
import { useAuth } from '../lib/auth-context'
import { initials, useSettings } from '../lib/settings'
import { endpoints, useApi } from '../services/api'
import { pctChange, sum } from '../lib/format'

function BrandMark() {
  return <img className="brand-mark" src={teaExportLogo} alt="" aria-hidden="true" />
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

function useNotifications(enabled, user) {
  const role = user?.role
  const demandEnabled = enabled && canAccessPage(role, 'forecast')
  const ledgerEnabled = enabled && canAccessPage(role, 'traceability')
  const readinessEnabled = enabled && canAccessPage(role, 'readiness')
  const requestsEnabled = enabled && role === 'admin'
  const demand = useApi(endpoints.exportDemand, { enabled: demandEnabled })
  const ledger = useApi(endpoints.passports, { enabled: ledgerEnabled })
  const userRequests = useApi(endpoints.userRequests, { enabled: requestsEnabled })

  return useMemo(() => {
    if (!enabled) return []
    const items = []
    if (demandEnabled && demand.data?.forecast?.length) {
      const next = sum(demand.data.forecast, 'forecast_export_volume_kg')
      const last = sum(demand.data.history.slice(-12), 'export_volume_kg')
      const change = pctChange(next, last)
      items.push({ id: 'demand', icon: 'trend', tone: change >= 0 ? 'green' : 'amber', title: `Export demand ${change >= 0 ? 'up' : 'down'} ${Math.abs(change).toFixed(1)}%`, body: 'Next 12-month forecast vs the latest 12 observed months.', to: '/demand-forecast' })
    }
    if (ledgerEnabled && ledger.data) {
      items.push(ledger.data.ledger_valid
        ? { id: 'ledger', icon: 'shield', tone: 'green', title: 'Traceability ledger verified', body: `${ledger.data.passports.length} batch passports · ${ledger.data.ledger_records} hash-linked records.`, to: '/digital-passport' }
        : { id: 'ledger', icon: 'alert', tone: 'red', title: 'Ledger integrity issue', body: `Hash chain verification failed at record ${ledger.data.broken_record}.`, to: '/digital-passport' })
    }
    if (readinessEnabled) items.push({ id: 'eri', icon: 'clipboard', tone: 'amber', title: 'Export readiness', body: 'Review export preparation requirements and assessment.', to: '/export-readiness' })
    if (requestsEnabled && userRequests.data?.requests?.length) {
      const requests = userRequests.data.requests
      const count = requests.length
      const applicants = requests.slice(0, 3).map((request) => `${request.display_name} · ${roleLabels[request.role] || request.role}`)
      const remaining = count > applicants.length ? `, and ${count - applicants.length} more` : ''
      items.push({ id: 'access-requests', icon: 'user', tone: 'amber', title: `${count} role request${count === 1 ? '' : 's'} awaiting review`, body: `${applicants.join('; ')}${remaining}.`, to: '/user-management' })
    }
    if (demandEnabled && demand.error) items.push({ id: 'demand-error', icon: 'alert', tone: 'red', title: 'Forecast service unavailable', body: demand.error, to: '/demand-forecast' })
    return items
  }, [enabled, demandEnabled, ledgerEnabled, readinessEnabled, requestsEnabled, userRequests.data, demand.data, demand.error, ledger.data])
}

export default function AppShell({ activeKey, children }) {
  const settings = useSettings()
  const { user, logout } = useAuth()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [notifOpen, setNotifOpen] = useState(false)
  const [userOpen, setUserOpen] = useState(false)
  const [readIds, setReadIds] = useState(() => new Set())
  const [logoutError, setLogoutError] = useState('')
  const notifRef = useOutsideClose(notifOpen, setNotifOpen)
  const userRef = useOutsideClose(userOpen, setUserOpen)
  const notifications = useNotifications(settings.notifications, user)
  const unread = notifications.filter((item) => !readIds.has(`${item.id}:${item.title}`)).length
  const activeItem = navItems.find((item) => item.key === activeKey)
  const visibleItems = navigationForRole(navItems, user?.role)

  useEffect(() => {
    document.body.classList.toggle('no-scroll', sidebarOpen)
    return () => document.body.classList.remove('no-scroll')
  }, [sidebarOpen])

  const closeMenus = () => { setSidebarOpen(false); setNotifOpen(false); setUserOpen(false) }
  const signOut = async () => {
    setLogoutError('')
    try {
      await logout()
      window.location.assign('/login')
    } catch (error) {
      setLogoutError(error.message)
    }
  }

  return (
    <div className={`app-shell ${sidebarOpen ? 'sidebar-open' : ''}`}>
      <LeafBackground animated={settings.animatedBackground} />
      <aside className="sidebar" aria-label="Sidebar">
        <div className="sidebar-brand">
          <BrandMark />
          <div><strong>CeylonTea IQ</strong><span>Sri Lanka Tea Intelligence</span></div>
          <button type="button" className="sidebar-close" aria-label="Close navigation" onClick={() => setSidebarOpen(false)}><Icon name="close" /></button>
        </div>
        <nav className="sidebar-nav" aria-label="Main navigation">
          {visibleItems.map((item, index) => (
            <Fragment key={item.key}>
              {index > 0 && item.group !== visibleItems[index - 1].group && <span className="sidebar-divider" role="separator" />}
              <Link to={item.path} className={`sidebar-link ${item.key === activeKey ? 'active' : ''}`} aria-current={item.key === activeKey ? 'page' : undefined} aria-label={item.label} onClick={(event) => { closeMenus(); if (event.detail > 0) event.currentTarget.blur() }}>
                <span className="sidebar-tile"><Icon name={item.icon} size={24} /></span>
                <span className="sidebar-label">{item.label}</span>
              </Link>
            </Fragment>
          ))}
        </nav>
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
          <span className="topbar-title">{activeItem?.label || 'CeylonTea IQ'}</span>
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
                <span className="avatar">{initials(user?.display_name)}</span>
                <span className="user-name">{user?.display_name || 'User'}</span>
                <Icon name="chevronDown" size={16} />
              </button>
              {userOpen && (
                <div className="dropdown-menu user-menu" role="menu">
                  <div className="dropdown-profile"><span className="avatar">{initials(user?.display_name)}</span><div><strong>{user?.display_name || 'User'}</strong><small>{user?.email} · {user?.is_super_admin ? 'Super Admin' : roleLabels[user?.role]}</small></div></div>
                  <Link to="/" className="menu-item" onClick={closeMenus}><Icon name="home" size={17} />My workspace</Link>
                  {canAccessPage(user?.role, 'reports') && <Link to="/reports" className="menu-item" onClick={closeMenus}><Icon name="file" size={17} />Reports</Link>}
                  {canAccessPage(user?.role, 'settings') && <Link to="/settings" className="menu-item" onClick={closeMenus}><Icon name="settings" size={17} />Settings</Link>}
                  {logoutError && <p className="auth-error" role="alert">{logoutError}</p>}
                  <button type="button" className="menu-item menu-action" onClick={signOut}><Icon name="close" size={17} />Sign out</button>
                </div>
              )}
            </div>
          </div>
        </header>
        <main className="page" id="main-content">{children}</main>
        <footer className="app-footer">© {new Date().getFullYear()} CeylonTea IQ · Planning intelligence for Sri Lankan tea exporters. Forecasts are model estimates, not guarantees.</footer>
      </div>
    </div>
  )
}
