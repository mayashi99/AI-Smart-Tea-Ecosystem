<<<<<<< HEAD
import { useEffect, useMemo, useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import './styles.css'
import ExportDemandPage from './pages/component04/ExportDemandPage'
import CombinedAuctionPriceForecast from './pages/component04/CombinedAuctionPriceForecast'
import ExportAdvisorPage from './pages/component04/ExportAdvisorPage'
import ExportReadinessPage from './pages/component04/ExportReadinessPage'
import DigitalPassportPage from './pages/component04/DigitalPassportPage'
import ZoneIntelligencePage from './pages/component04/ZoneIntelligencePage'

const API_URL = import.meta.env.VITE_API_URL || '/api/component04/train-output'
const isExportDemandPage = window.location.pathname.replace(/\/$/, '') === '/export-demand'
const isExportAdvisorPage = window.location.pathname.replace(/\/$/, '') === '/export-advisor'
const isExportReadinessPage = window.location.pathname.replace(/\/$/, '') === '/export-readiness'
const isDigitalPassportPage = window.location.pathname.replace(/\/$/, '') === '/digital-passport'
const isZoneIntelligencePage = window.location.pathname.replace(/\/$/, '') === '/zone-intelligence'

const formatNumber = (value) =>
  new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 2,
  }).format(value ?? 0)

const formatDate = (value) =>
  new Intl.DateTimeFormat('en', {
    month: 'short',
    year: 'numeric',
  }).format(new Date(value))

function App() {
  const [dashboard, setDashboard] = useState(null)
  const [selectedZone, setSelectedZone] = useState('')
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState('')

  useEffect(() => {
    if (isExportDemandPage || isExportAdvisorPage || isExportReadinessPage || isDigitalPassportPage || isZoneIntelligencePage) return
    fetch(API_URL)
      .then((response) => {
        if (!response.ok) {
          throw new Error('Train output load failed')
        }
        return response.json()
      })
      .then((data) => {
        setDashboard(data)
        setSelectedZone(data.default_zone)
        setStatus('ready')
      })
      .catch((err) => {
        setError(err.message)
        setStatus('error')
      })
  }, [])

  const selectedMetrics = useMemo(() => {
    if (!dashboard || !selectedZone) return []
    return dashboard.model_metrics.filter((metric) => metric.growing_zone === selectedZone)
  }, [dashboard, selectedZone])

  const lstmMetric = useMemo(() => {
    if (!selectedMetrics.length) return null
    return selectedMetrics.find((metric) => metric.model === 'LSTM') ?? selectedMetrics[0]
  }, [selectedMetrics])
  const auctionTestAccuracy = 100 - Number(lstmMetric?.mape ?? 100)

  const zonePeriods = useMemo(() => {
    if (!dashboard || !selectedZone) return dashboard?.periods
    return dashboard.zone_periods[selectedZone] ?? dashboard.periods
  }, [dashboard, selectedZone])

  const chartData = useMemo(() => {
    if (!dashboard || !selectedZone) return []
    const comparisonRows = (dashboard.test_comparison || dashboard.predictions || [])
      .filter((row) => row.growing_zone === selectedZone)
      .map((row) => ({
        date: formatDate(row.auction_date),
        actual: row.actual_avg_price_lkr,
        lstm: row.lstm_predicted_avg_price_lkr,
        future: null,
      }))
    const forecast = (dashboard.future_forecast || [])
      .filter((row) => row.growing_zone === selectedZone)
      .map((row) => ({
        date: formatDate(row.auction_date),
        actual: null,
        lstm: null,
        future: row.lstm_forecast_avg_price_lkr,
      }))
    return [...comparisonRows, ...forecast]
  }, [dashboard, selectedZone])

  const recentRows = useMemo(() => {
    if (!dashboard || !selectedZone) return []
    return dashboard.predictions
      .filter((row) => row.growing_zone === selectedZone)
      .slice(-8)
      .reverse()
  }, [dashboard, selectedZone])

  if (isExportDemandPage) {
    return (
      <>
        <nav className="page-nav" aria-label="Forecast pages">
          <a href="/">Auction Price</a>
          <a className="active" href="/export-demand">Export Demand</a>
          <a href="/export-advisor">Export Advisor</a>
          <a href="/export-readiness">ERI</a>
          <a href="/digital-passport">Digital Passport</a>
          <a href="/zone-intelligence">Zone Intelligence</a>
        </nav>
        <ExportDemandPage />
      </>
    )
  }

  if (isExportAdvisorPage) {
    return (
      <>
        <nav className="page-nav" aria-label="Component 04 pages">
          <a href="/">Auction Price</a>
          <a href="/export-demand">Export Demand</a>
          <a className="active" href="/export-advisor">Export Advisor</a>
          <a href="/export-readiness">ERI</a>
          <a href="/digital-passport">Digital Passport</a>
          <a href="/zone-intelligence">Zone Intelligence</a>
        </nav>
        <ExportAdvisorPage />
      </>
    )
  }

  if (isExportReadinessPage) {
    return <><nav className="page-nav" aria-label="Component 04 pages"><a href="/">Auction Price</a><a href="/export-demand">Export Demand</a><a href="/export-advisor">Export Advisor</a><a className="active" href="/export-readiness">ERI</a><a href="/digital-passport">Digital Passport</a><a href="/zone-intelligence">Zone Intelligence</a></nav><ExportReadinessPage /></>
  }

  if (isDigitalPassportPage) {
    return <><nav className="page-nav" aria-label="Component 04 pages"><a href="/">Auction Price</a><a href="/export-demand">Export Demand</a><a href="/export-advisor">Export Advisor</a><a href="/export-readiness">ERI</a><a className="active" href="/digital-passport">Digital Passport</a><a href="/zone-intelligence">Zone Intelligence</a></nav><DigitalPassportPage /></>
  }

  if (isZoneIntelligencePage) {
    return <><nav className="page-nav" aria-label="Component 04 pages"><a href="/">Auction Price</a><a href="/export-demand">Export Demand</a><a href="/export-advisor">Export Advisor</a><a href="/export-readiness">ERI</a><a href="/digital-passport">Digital Passport</a><a className="active" href="/zone-intelligence">Zone Intelligence</a></nav><ZoneIntelligencePage /></>
  }

  if (status === 'loading') {
    return <main className="screen">Loading train output...</main>
  }

  if (status === 'error') {
    return (
      <main className="screen">
        <section className="empty-state">
          <h1>Train output unavailable</h1>
          <p>{error}</p>
        </section>
      </main>
    )
  }

  return (
    <>
      <nav className="page-nav" aria-label="Forecast pages">
        <a className="active" href="/">Auction Price</a>
        <a href="/export-demand">Export Demand</a>
        <a href="/export-advisor">Export Advisor</a>
        <a href="/export-readiness">ERI</a>
        <a href="/digital-passport">Digital Passport</a>
        <a href="/zone-intelligence">Zone Intelligence</a>
      </nav>
      <main className="dashboard">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Component 04</p>
          <h1>Auction Price Forecasting Dashboard</h1>
          <p className="subtle">
            Train {formatDate(dashboard.periods.train_start)} -{' '}
            {formatDate(dashboard.periods.train_end)} | Test{' '}
            {formatDate(dashboard.periods.test_start)} -{' '}
            {formatDate(dashboard.periods.test_end)}
          </p>
        </div>
        <div className="header-actions">
          <label className="zone-select">
            <span>Growing Zone</span>
            <select value={selectedZone} onChange={(event) => setSelectedZone(event.target.value)}>
              {dashboard.zones.map((zone) => (
                <option key={zone} value={zone}>
                  {zone}
                </option>
              ))}
            </select>
          </label>
          <div className="model-chip">
            <span>{dashboard.model}</span>
            <strong>{lstmMetric?.lookback_months ?? dashboard.lstm.lookback_months} months</strong>
          </div>
        </div>
      </header>

      <p className="subtle zone-period">
        {selectedZone}: Train {formatDate(zonePeriods.train_start)} -{' '}
        {formatDate(zonePeriods.train_end)} | Test {formatDate(zonePeriods.test_start)} -{' '}
        {formatDate(zonePeriods.test_end)}
      </p>

      <section className="metric-grid" aria-label="Training metrics">
        <article className="metric-card">
          <span>LSTM MAE</span>
          <strong>{formatNumber(lstmMetric?.mae)}</strong>
        </article>
        <article className="metric-card">
          <span>LSTM RMSE</span>
          <strong>{formatNumber(lstmMetric?.rmse)}</strong>
        </article>
        <article className="metric-card">
          <span>LSTM MAPE</span>
          <strong>{formatNumber(lstmMetric?.mape)}%</strong>
        </article>
        <article className="metric-card accuracy-card" title="Calculated as 100% minus the selected growing zone's holdout MAPE; this is a retrospective error metric, not a probability or confidence score.">
          <span>Test accuracy (100% − MAPE)</span>
          <strong>{formatNumber(auctionTestAccuracy)}%</strong>
        </article>
        <article className="metric-card">
          <span>R² Score</span>
          <strong>{formatNumber(lstmMetric?.r2)}</strong>
        </article>
        <article className="metric-card">
          <span>Future Months</span>
          <strong>
            {formatNumber(
              dashboard.future_forecast.filter((row) => row.growing_zone === selectedZone).length,
            )}
          </strong>
        </article>
      </section>

      <section className="panel chart-panel">
        <div className="panel-heading">
          <h2>Actual vs LSTM Test Prediction</h2>
          <p>Monthly test-period comparison for the selected growing zone</p>
        </div>
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 12, right: 24, left: 0, bottom: 8 }}>
              <CartesianGrid stroke="#dbe5dc" strokeDasharray="4 4" />
              <XAxis dataKey="date" minTickGap={22} stroke="#64736a" />
              <YAxis stroke="#64736a" tickFormatter={formatNumber} width={72} />
              <Tooltip formatter={(value) => `LKR ${formatNumber(value)}`} />
              <Legend />
              <Line
                type="monotone"
                dataKey="actual"
                name="Actual"
                stroke="#176f4d"
                strokeWidth={3}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="lstm"
                name="LSTM Test Prediction"
                stroke="#2f6fb0"
                strokeWidth={3}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="future"
                name="Future Forecast"
                stroke="#9d3a63"
                strokeDasharray="6 5"
                strokeWidth={3}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="model-grid" aria-label="Model comparison">
        {selectedMetrics.map((metric) => (
          <article className="panel model-panel" key={metric.model}>
            <div>
              <h2>{metric.model}</h2>
              <p>
                MAE {formatNumber(metric.mae)} | RMSE {formatNumber(metric.rmse)}
              </p>
            </div>
          </article>
        ))}
        <article className="panel model-panel">
          <div>
            <h2>LSTM Setup</h2>
            <p>
              {dashboard.lstm.role}; {dashboard.lstm.model_type} architecture, {dashboard.lstm.lookback_months}-month lookback,{' '}
              {dashboard.lstm.hidden_size} hidden units, {dashboard.lstm.epochs} maximum epochs.
            </p>
          </div>
        </article>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>Latest Test Predictions</h2>
          <p>Last 8 months from the testing dataset</p>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Actual</th>
                <th>LSTM</th>
                <th>LSTM Error</th>
                <th>Error %</th>
              </tr>
            </thead>
            <tbody>
              {recentRows.map((row) => (
                <tr key={row.auction_date}>
                  <td>{formatDate(row.auction_date)}</td>
                  <td>LKR {formatNumber(row.actual_avg_price_lkr)}</td>
                  <td>LKR {formatNumber(row.lstm_predicted_avg_price_lkr)}</td>
                  <td>{formatNumber(row.lstm_error)}</td>
                  <td>{formatNumber(row.lstm_error_percent)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <CombinedAuctionPriceForecast />

      </main>
    </>
=======

import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'

import Home from './Home/Home'
import HarvestQuality from './components/component2/HarvestQuality/HarvestQuality'
import PlantDensity from './components/component2/PlantDensity/PlantDensity'
import PlantHealth from './components/component2/PlantHelth/PlantHealth'
import HarvestReadiness from './components/component2/HarvestReadiness/HarvestReadiness'
import YieldPrediction from './components/component2/yield prediction/YieldPrediction'
import IntelligentHarvestPlanning from './components/component2/IntelligentHarvestPlanning/IntelligentHarvestPlanning'
import Navbar from './components/Navbar'

function NormalizePath() {
  const location = useLocation()

  const normalizedPath = location.pathname.replace(/^\/{2,}/, '/')

  if (normalizedPath !== location.pathname) {
    return (
      <Navigate
        replace
        to={`${normalizedPath}${location.search}${location.hash}`}
      />
    )
  }

  return null
}

function App() {
  return (
    <BrowserRouter>
      <NormalizePath />

      <Navbar />

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/harvest-quality" element={<HarvestQuality />} />

        <Route
          path="/plant-density"
          element={<PlantDensity />}
        />

        <Route
          path="/plantation-health"
          element={<PlantHealth />}
        />

        <Route
          path="/harvest-readiness"
          element={<HarvestReadiness />}
        />
        <Route
          path="/yield-prediction"
          element={<YieldPrediction />}
        />
        <Route
          path="/intelligent-harvest-planning"
          element={<IntelligentHarvestPlanning />}
        />
      </Routes>
    </BrowserRouter>
>>>>>>> feature/yield-intelligence
  )
}

export default App
