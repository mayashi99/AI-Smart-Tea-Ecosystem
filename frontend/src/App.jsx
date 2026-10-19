<<<<<<< HEAD
// Group project integration point. Component01 is self-contained and can be
// mounted by the team's shared router without importing its private pages.
import Component01App from './components/Component01/Component01App.jsx'

export default function App() {
  return <Component01App />
}
=======
import { lazy, Suspense, useEffect } from 'react'
import './styles.css'
import Icon from './components/Icon'
import { Link, LoadingState } from './components/ui'
import AppShell from './layout/AppShell'
import { useLocation } from './lib/router'
import { matchRoute } from './lib/routes'

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
  const route = matchRoute(path)
  const Page = pages[route.key]

  useEffect(() => {
    document.title = route.item ? `${route.item.label} · TeaExportAI` : 'TeaExportAI · Sri Lanka Tea Intelligence'
  }, [route.item])

  return (
    <AppShell activeKey={route.key === 'workspace' ? 'home' : route.key}>
      <Suspense fallback={<LoadingState label="Loading page…" />}>
        {route.key === 'workspace' ? <WorkspacePage key={path} role={route.role} /> : Page ? <Page key={path} /> : <NotFound />}
      </Suspense>
    </AppShell>
  )
}

export default App
>>>>>>> 119d635afe96b6dd3265084713f2cdfb831272f2
