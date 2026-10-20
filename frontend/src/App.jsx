import { lazy, Suspense, useEffect } from 'react'
import Icon from './components/Icon'
import { Link, LoadingState } from './components/ui'
import AppShell from './layout/AppShell'
import { useLocation } from './lib/router'
import { matchRoute } from './lib/routes'

const component02RouteKeys = new Set([
  'plantation-hub',
  'yield-prediction',
  'yield-trends',
  'harvest-quality',
  'plant-density',
  'plantation-health',
  'harvest-readiness',
  'intelligent-harvest-planning',
])

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
const PlantationHubPage = lazy(() => import('./Home/Home'))
const YieldPredictionPage = lazy(() => import('./components/component2/yield prediction/YieldPrediction'))
const YieldTrendsPage = lazy(() => import('./components/component2/yield trend/YieldTrends'))
const HarvestQualityPage = lazy(() => import('./components/component2/HarvestQuality/HarvestQuality'))
const PlantDensityPage = lazy(() => import('./components/component2/PlantDensity/PlantDensity'))
const PlantationHealthPage = lazy(() => import('./components/component2/PlantHelth/PlantHealth'))
const HarvestReadinessPage = lazy(() => import('./components/component2/HarvestReadiness/HarvestReadiness'))
const IntelligentHarvestPlanningPage = lazy(() => import('./components/component2/IntelligentHarvestPlanning/IntelligentHarvestPlanning'))

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
  'plantation-hub': PlantationHubPage,
  'yield-prediction': YieldPredictionPage,
  'yield-trends': YieldTrendsPage,
  'harvest-quality': HarvestQualityPage,
  'plant-density': PlantDensityPage,
  'plantation-health': PlantationHealthPage,
  'harvest-readiness': HarvestReadinessPage,
  'intelligent-harvest-planning': IntelligentHarvestPlanningPage,
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
  const isComponent02Route = component02RouteKeys.has(route.key)

  useEffect(() => {
    document.title = route.item ? `${route.item.label} · TeaExportAI` : 'TeaExportAI · Sri Lanka Tea Intelligence'
  }, [route.item])

  return (
    <AppShell
      activeKey={route.key === 'workspace' ? 'home' : route.key}
      contentClassName={isComponent02Route ? 'is-component02 !max-w-none !p-0' : ''}
      notificationsEnabled={!isComponent02Route}
    >
      <Suspense fallback={<LoadingState label="Loading page…" />}>
        {route.key === 'workspace' ? <WorkspacePage key={path} role={route.role} /> : Page ? <Page key={path} /> : <NotFound />}
      </Suspense>
    </AppShell>
  )
}

export default App
