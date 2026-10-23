import { lazy, Suspense, useEffect } from 'react'
import './styles.css'
import Icon from './components/Icon'
import { Link, LoadingState } from './components/ui'
import AppShell from './layout/AppShell'
import { navigate, useLocation } from './lib/router'
import { matchRoute } from './lib/routes'
import { useAuth } from './lib/auth-context'
import { canAccessPage } from './lib/permissions'
import { AuthPage, PublicPassportPage } from './pages/AuthPages'

const LandingPage = lazy(() => import('./pages/LandingPage'))

const HomePage = lazy(() => import('./pages/HomePage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const MarketAnalysisPage = lazy(() => import('./pages/MarketAnalysisPage'))
const ExportDemandPage = lazy(() => import('./pages/component04/ExportDemandPage'))
const UsdForecastPage = lazy(() => import('./pages/component04/UsdForecastPage'))
const ExportReadinessPage = lazy(() => import('./pages/component04/ExportReadinessPage'))
const ExportAdvisorPage = lazy(() => import('./pages/component04/ExportAdvisorPage'))
const DigitalPassportPage = lazy(() => import('./pages/component04/DigitalPassportPage'))
const ReportsPage = lazy(() => import('./pages/ReportsPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const WorkspacePage = lazy(() => import('./pages/WorkspacePage'))
const UserManagementPage = lazy(() => import('./pages/UserManagementPage'))

const pages = {
  home: HomePage,
  dashboard: DashboardPage,
  market: MarketAnalysisPage,
  forecast: ExportDemandPage,
  'usd-forecast': UsdForecastPage,
  readiness: ExportReadinessPage,
  insights: ExportAdvisorPage,
  traceability: DigitalPassportPage,
  reports: ReportsPage,
  settings: SettingsPage,
  'user-management': UserManagementPage,
}

function NotFound() {
  return (
    <div className="state-box is-page">
      <Icon name="leaf" size={36} />
      <h1>Page not found</h1>
      <p>The page you requested does not exist.</p>
      <Link className="btn btn-primary" to="/">Back to Home</Link>
    </div>
  )
}

function App() {
  const { path } = useLocation()
  const { user, loading } = useAuth()
  const route = matchRoute(path)
  const Page = pages[route.key]

  useEffect(() => {
    const titles = { login: 'Sign in', signup: 'Create account' }
    const label = route.item?.label || titles[route.key]
    document.title = label ? `${label} · CeylonTea IQ` : 'CeylonTea IQ · Sri Lanka Tea Intelligence'
  }, [route.item, route.key])

  useEffect(() => {
    if (user && (route.key === 'login' || route.key === 'signup')) navigate('/')
  }, [user, route.key])

  const landing = <Suspense fallback={<main className="landing" />}><LandingPage /></Suspense>

  if (route.key === 'public-passport') return <PublicPassportPage publicId={route.publicId} />
  if (route.key === 'login' || route.key === 'signup') return <AuthPage mode={route.key} />
  if (route.key === 'landing') return landing
  // Logged-out visitors to "/" get the landing page; keep it dark while the session check runs.
  if (route.key === 'home' && (loading || !user)) return loading ? <main className="landing" /> : landing
  if (loading) return <LoadingState label="Verifying your account…" />
  if (!user) return <AuthPage mode="login" />
  if (route.key === 'not-found') {
    return <AppShell activeKey=""><NotFound /></AppShell>
  }

  const workspaceRole = { seller: 'farmer_seller', 'tea-board': 'export_manager', buyer: 'viewer_buyer' }[route.role]
  const allowed = route.key === 'workspace'
    ? user.role === workspaceRole
    : canAccessPage(user.role, route.key)

  if (!allowed) {
    return (
      <AppShell activeKey="">
        <div className="state-box is-page" role="alert">
          <Icon name="shield" size={36} />
          <h1>Access denied</h1>
          <p>Your account role does not have permission to open this page.</p>
          <Link className="btn btn-primary" to="/">Go to your workspace</Link>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell activeKey={route.key === 'workspace' ? 'home' : route.key}>
      <Suspense fallback={<LoadingState label="Loading page…" />}>
        {route.key === 'workspace' ? <WorkspacePage key={path} role={route.role} /> : Page ? <Page key={path} /> : <NotFound />}
      </Suspense>
    </AppShell>
  )
}

export default App
