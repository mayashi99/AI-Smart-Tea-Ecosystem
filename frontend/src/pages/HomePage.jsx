import { useMemo } from 'react'
import { Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import Icon from '../components/Icon'
import { Card, ErrorState, Link, LoadingState, StatCard } from '../components/ui'
import { useAuth } from '../lib/auth-context'
import { canAccessPage, navigationForRole, roleLabels } from '../lib/permissions'
import { navItems } from '../lib/routes'
import { chartTheme } from '../lib/chartTheme'
import { formatCompact, formatDate, formatNumber, pctChange, sum } from '../lib/format'
import { useLastEri } from '../lib/settings'
import { endpoints, useApi } from '../services/api'
import homeHeroImage from '../assets/home-hero.jpg'

const roleIntros = {
  admin: 'Manage the platform, users, traceability, and tea export intelligence from one workspace.',
  export_manager: 'Plan exports with market intelligence, monthly forecasts, readiness checks, and batch traceability.',
  quality_officer: 'Review export readiness, record evidence-backed quality checks, and verify batch documentation.',
  data_analyst: 'Explore market signals, forecasting outputs, model performance, and analytics reports.',
  farmer_seller: 'Manage your tea batches, follow traceability events, and track export-readiness requirements.',
  viewer_buyer: 'Explore approved market intelligence and reports, and verify public tea passports using QR codes.',
}

const roleActions = {
  admin: ['readiness', 'forecast'],
  export_manager: ['readiness', 'forecast'],
  quality_officer: ['readiness', 'traceability'],
  data_analyst: ['forecast', 'market'],
  farmer_seller: ['readiness', 'traceability'],
  viewer_buyer: ['forecast', 'reports'],
}

function timeGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function DemandTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      <strong>{label}</strong>
      {payload.filter((item) => item.value != null).map((item) => (
        <span key={item.dataKey}><i style={{ background: item.color }} />{item.name}: <b>{formatCompact(item.value)} tonnes</b></span>
      ))}
    </div>
  )
}

function PriceTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      <strong>{label}</strong>
      {payload.filter((item) => item.value != null).map((item) => (
        <span key={item.dataKey}><i style={{ background: item.color }} />{item.name}: <b>LKR {formatNumber(item.value, 0)}/kg</b></span>
      ))}
    </div>
  )
}

function EventTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return <div className="chart-tooltip"><strong>{label}</strong><span><i style={{ background: chartTheme.primary }} />Events: <b>{payload[0].value}</b></span></div>
}

export default function HomePage() {
  const { user } = useAuth()
  const role = user?.role
  const canForecast = canAccessPage(role, 'forecast')
  const canDashboard = canAccessPage(role, 'dashboard') && role !== 'farmer_seller'
  const canTraceability = canAccessPage(role, 'traceability')
  const canReadiness = canAccessPage(role, 'readiness') && role !== 'data_analyst'
  const demand = useApi(endpoints.exportDemand, { enabled: canForecast })
  const auction = useApi(endpoints.trainOutput, { enabled: canDashboard })
  const passports = useApi(endpoints.passports, { enabled: canTraceability })
  const lastEri = useLastEri()
  const links = navigationForRole(navItems.filter((item) => item.key !== 'home'), role)
  const actionKeys = roleActions[role] || []
  const actions = actionKeys
    .map((key) => links.find((item) => item.key === key))
    .filter(Boolean)
    .slice(0, 2)

  const demandChart = useMemo(() => {
    if (!demand.data) return []
    const history = (demand.data.history || []).slice(-24)
    const forecast = demand.data.forecast || []
    return [
      ...history.map((row) => ({ month: formatDate(row.date), historical: Number(row.export_volume_kg) / 1000, forecast: null })),
      ...forecast.map((row) => ({ month: formatDate(row.date), historical: null, forecast: Number(row.forecast_export_volume_kg) / 1000 })),
    ]
  }, [demand.data])

  const priceChart = useMemo(() => {
    if (!auction.data) return []
    const zone = auction.data.default_zone || 'Total'
    const history = (auction.data.predictions || []).filter((row) => row.growing_zone === zone)
    const forecast = (auction.data.future_forecast || []).filter((row) => row.growing_zone === zone)
    const rows = history.slice(-24).map((row) => ({
      month: formatDate(row.auction_date),
      actual: Number(row.actual_avg_price_lkr),
      forecast: null,
    }))
    if (rows.length) rows[rows.length - 1].forecast = rows[rows.length - 1].actual
    forecast.forEach((row) => rows.push({
      month: formatDate(row.auction_date),
      actual: null,
      forecast: Number(row.lstm_forecast_avg_price_lkr),
    }))
    return rows
  }, [auction.data])

  const allEvents = useMemo(() => (passports.data?.passports || [])
    .flatMap((passport) => passport.events.map((event) => ({ ...event, batch_id: passport.batch_id })))
    .sort((first, second) => new Date(second.timestamp) - new Date(first.timestamp)), [passports.data])

  const eventChart = useMemo(() => {
    const counts = new Map()
    allEvents.forEach((event) => counts.set(event.event_type, (counts.get(event.event_type) || 0) + 1))
    return [...counts.entries()].map(([stage, count]) => ({ stage, count }))
  }, [allEvents])

  const next12Demand = demand.data ? sum(demand.data.forecast || [], 'forecast_export_volume_kg') : null
  const previous12Demand = demand.data ? sum((demand.data.history || []).slice(-12), 'export_volume_kg') : null
  const latestPrice = auction.data?.predictions?.filter((row) => row.growing_zone === (auction.data.default_zone || 'Total')).at(-1)
  const accuracy = demand.data ? 100 - Number(demand.data.metrics?.mape ?? 100) : null
  const batchCount = passports.data?.passports?.length
  const recordCount = passports.data?.ledger_records
  const latestQuantity = passports.data?.passports?.reduce((total, passport) => total + Number(passport.events.at(-1)?.quantity_kg || 0), 0)

  const kpis = canForecast || canDashboard
    ? [
      ...(canForecast ? [{
        icon: 'trend', tone: 'green', label: 'Forecast export demand · next 12 months',
        value: next12Demand == null ? (demand.error ? 'Unavailable' : '…') : `${formatCompact(next12Demand / 1000)} t`,
        trend: demand.data ? pctChange(next12Demand, previous12Demand) : null,
        hint: demand.data ? 'vs latest 12 months' : demand.error || '',
        to: '/demand-forecast',
      }] : []),
      ...(canDashboard ? [{
        icon: 'coins', tone: 'amber', label: 'Latest average auction price',
        value: latestPrice ? `LKR ${formatNumber(latestPrice.actual_avg_price_lkr, 0)}/kg` : auction.error ? 'Unavailable' : '…',
        hint: latestPrice ? formatDate(latestPrice.auction_date) : auction.error || '',
        to: '/dashboard',
      }] : []),
      ...(canForecast ? [{
        icon: 'target', tone: 'blue', label: 'Demand model test accuracy',
        value: accuracy == null ? (demand.error ? 'Unavailable' : '…') : `${formatNumber(accuracy, 1)}%`,
        hint: accuracy == null ? demand.error || '' : '100% − holdout MAPE',
        to: '/demand-forecast',
      }] : []),
      ...(canTraceability ? [{
        icon: 'shield', tone: 'teal', label: 'Traceable tea batches',
        value: batchCount == null ? (passports.error ? 'Unavailable' : '…') : batchCount,
        hint: passports.data ? `${passports.data.ledger_valid ? 'Ledger verified' : 'Integrity issue'} · ${recordCount} records` : passports.error || '',
        to: '/digital-passport',
      }] : [{
        icon: 'bars', tone: 'teal', label: 'Auction records analysed',
        value: auction.data ? auction.data.predictions.length.toLocaleString() : auction.error ? 'Unavailable' : '…',
        hint: auction.data ? `${auction.data.zones?.length || 0} growing zones` : auction.error || '',
        to: '/dashboard',
      }]),
    ]
    : [
      { icon: 'package', tone: 'teal', label: 'Your batch passports', value: batchCount == null ? (passports.error ? 'Unavailable' : '…') : batchCount, hint: 'Assigned batch records', to: '/digital-passport' },
      { icon: 'refresh', tone: 'blue', label: 'Traceability events', value: recordCount ?? (passports.error ? 'Unavailable' : '…'), hint: 'Hash-linked ledger records', to: '/digital-passport' },
      { icon: 'leaf', tone: 'amber', label: 'Latest recorded quantity', value: latestQuantity == null ? (passports.error ? 'Unavailable' : '…') : `${formatCompact(latestQuantity)} kg`, hint: 'Sum of latest batch events', to: '/digital-passport' },
      { icon: 'shield', tone: passports.data?.ledger_valid === false ? 'amber' : 'green', label: 'Ledger integrity', value: passports.data ? (passports.data.ledger_valid ? 'Verified' : 'Review needed') : passports.error ? 'Unavailable' : '…', hint: 'SHA-256 hash-chain status', to: '/digital-passport' },
    ]

  return (
    <div className="page-stack home-dashboard">
      <section className="home-hero panel role-home-hero designed-home-hero">
        <img className="hero-image" src={homeHeroImage} alt="" aria-hidden="true" />
        <div className="home-hero-copy">
          <p className="eyebrow">TeaExportAI · Sri Lanka Tea Intelligence</p>
          <h1>{timeGreeting()}, {user?.display_name || 'Tea Export Partner'}</h1>
          <p>{roleIntros[role] || 'Welcome to the Sri Lanka tea export intelligence workspace.'}</p>
          <div className="home-hero-actions">
            {actions.map((item, index) => (
              <Link key={item.key} to={item.path} className={`btn ${index === 0 ? 'btn-primary' : 'btn-secondary'}`}>
                <Icon name={item.icon} size={17} />
                {item.key === 'readiness' ? 'Check export readiness'
                  : item.key === 'forecast' ? 'View demand forecast'
                    : item.key === 'traceability' ? 'Open traceability'
                      : item.key === 'market' ? 'Explore market analysis'
                        : item.label}
              </Link>
            ))}
          </div>
          <span className="chip role-badge">{roleLabels[role]}</span>
        </div>
      </section>

      <section className="stat-grid home-kpis" aria-label="Tea export key performance indicators">
        {kpis.slice(0, 4).map((item) => <StatCard key={item.label} {...item} />)}
      </section>

      <section className="home-analytics-grid" aria-label="Tea export analytics">
        <Card
          className="home-chart-card home-chart-primary"
          icon="bars"
          title={canForecast ? 'Export demand analytics' : 'Traceability activity'}
          description={canForecast ? 'Monthly national export volume (tonnes): recent history and the 12-month ML forecast.' : 'Recorded batch stages across your accessible traceability ledger.'}
          actions={<Link className="home-details-link" to={canForecast ? '/demand-forecast' : '/digital-passport'}>Details <Icon name="arrowRight" size={15} /></Link>}
        >
          {canForecast ? demand.error
            ? <ErrorState compact message={`Demand forecast unavailable: ${demand.error}`} onRetry={demand.reload} />
            : !demand.data ? <LoadingState compact label="Loading export demand…" />
              : demandChart.length ? (
                <div className="chart-box home-chart-box">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={demandChart} margin={{ top: 8, right: 8, left: -12, bottom: 2 }}>
                      <CartesianGrid stroke={chartTheme.grid} vertical={false} />
                      <XAxis dataKey="month" minTickGap={20} stroke={chartTheme.axis} tick={{ fontSize: 11 }} />
                      <YAxis stroke={chartTheme.axis} tickFormatter={formatCompact} width={52} tick={{ fontSize: 11 }} />
                      <Tooltip content={<DemandTooltip />} />
                      <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="historical" name="Historical" fill={chartTheme.primary} radius={[3, 3, 0, 0]} maxBarSize={20} />
                      <Line type="monotone" dataKey="forecast" name="Forecast" stroke={chartTheme.primary} strokeWidth={2.5} strokeDasharray="5 4" dot={false} connectNulls />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              ) : <p className="field-hint">No export demand history or forecast is available yet.</p>
            : passports.error
              ? <ErrorState compact message={`Traceability data unavailable: ${passports.error}`} onRetry={passports.reload} />
              : !passports.data ? <LoadingState compact label="Loading traceability activity…" />
                : eventChart.length ? (
                  <div className="chart-box home-chart-box">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={eventChart} margin={{ top: 12, right: 8, left: -12, bottom: 2 }}>
                        <CartesianGrid stroke={chartTheme.grid} vertical={false} />
                        <XAxis dataKey="stage" interval={0} angle={-18} textAnchor="end" height={52} stroke={chartTheme.axis} tick={{ fontSize: 10 }} />
                        <YAxis allowDecimals={false} stroke={chartTheme.axis} width={38} tick={{ fontSize: 11 }} />
                        <Tooltip content={<EventTooltip />} />
                        <Bar dataKey="count" name="Events" fill={chartTheme.primary} radius={[4, 4, 0, 0]} maxBarSize={32} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : <p className="field-hint">No traceability events have been recorded yet.</p>}
        </Card>

        <Card className="home-readiness-card" icon="clipboard" title={canReadiness ? 'Export readiness' : 'Your workspace'} description={canReadiness ? 'Your most recent Export Readiness Index.' : 'Quick access to the tools available for your account.'}>
          {canReadiness && lastEri ? (
            <div className="home-readiness">
              <div className="home-readiness-icon"><Icon name="clipboard" size={27} /></div>
              <strong className="home-readiness-score">{lastEri.score}<small>/100</small></strong>
              <span className="chip">{lastEri.band || 'Latest assessment'}</span>
              <p>{lastEri.destination_country ? `Assessment for ${lastEri.destination_country}` : 'Latest readiness assessment'}{lastEri.saved_at ? ` · ${formatDate(lastEri.saved_at)}` : ''}</p>
              <Link className="btn btn-primary home-readiness-action" to="/export-readiness">View assessment</Link>
            </div>
          ) : canReadiness ? (
            <div className="home-readiness is-empty">
              <div className="home-readiness-icon"><Icon name="clipboard" size={27} /></div>
              <strong>No assessment yet</strong>
              <p>Combine demand evidence with your capacity, documents and quality status to get an explainable score.</p>
              <Link className="btn btn-primary home-readiness-action" to="/export-readiness">Calculate ERI</Link>
            </div>
          ) : (
            <div className="home-module-shortcuts">
              {links.slice(0, 3).map((item) => (
                <Link key={item.key} to={item.path} className="home-module-link">
                  <span className="stat-icon tone-green"><Icon name={item.icon} size={18} /></span>
                  <span><strong>{item.label}</strong><small>{item.description}</small></span>
                  <Icon name="arrowRight" size={16} />
                </Link>
              ))}
            </div>
          )}
        </Card>
      </section>

      <section className={`home-lower-grid ${canDashboard && canTraceability ? 'has-two-panels' : ''}`} aria-label="Additional intelligence">
        {canDashboard && (
          <Card
            className="home-chart-card"
            icon="trend"
            title="Auction price trend"
            description="Monthly average auction price (LKR/kg), actual history and forecast."
            actions={<Link className="home-details-link" to="/dashboard">Details <Icon name="arrowRight" size={15} /></Link>}
          >
            {auction.error
              ? <ErrorState compact message={`Auction price data unavailable: ${auction.error}`} onRetry={auction.reload} />
              : !auction.data ? <LoadingState compact label="Loading auction price data…" />
                : priceChart.length ? (
                  <div className="chart-box home-chart-box">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={priceChart} margin={{ top: 8, right: 8, left: -12, bottom: 2 }}>
                        <CartesianGrid stroke={chartTheme.grid} vertical={false} />
                        <XAxis dataKey="month" minTickGap={20} stroke={chartTheme.axis} tick={{ fontSize: 11 }} />
                        <YAxis stroke={chartTheme.axis} tickFormatter={(value) => formatCompact(value)} width={52} tick={{ fontSize: 11 }} domain={['auto', 'auto']} />
                        <Tooltip content={<PriceTooltip />} />
                        <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                        <Line type="monotone" dataKey="actual" name="Historical price" stroke={chartTheme.primary} strokeWidth={2.3} dot={false} />
                        <Line type="monotone" dataKey="forecast" name="Forecast" stroke={chartTheme.accent} strokeWidth={2.5} strokeDasharray="5 4" dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ) : <p className="field-hint">No auction price history or forecast is available yet.</p>}
          </Card>
        )}

        {canTraceability && (
          <Card
            className="home-activity-card"
            icon="shield"
            title="Recent batch activity"
            description="Latest events from the batches available to your account."
            actions={<Link className="home-details-link" to="/digital-passport">All batches <Icon name="arrowRight" size={15} /></Link>}
          >
            {passports.error
              ? <ErrorState compact message={`Traceability data unavailable: ${passports.error}`} onRetry={passports.reload} />
              : !passports.data ? <LoadingState compact label="Loading batch activity…" />
                : allEvents.length ? (
                  <ul className="home-activity-list">
                    {allEvents.slice(0, 5).map((event) => (
                      <li key={event.record_hash}>
                        <span className="activity-dot" />
                        <div><strong>{event.batch_id} · {event.event_type}</strong><small>{event.location} · {event.tea_grade}</small></div>
                        <time dateTime={event.timestamp}>{new Date(event.timestamp).toLocaleDateString()}</time>
                      </li>
                    ))}
                  </ul>
                ) : <p className="field-hint">No batches are available yet. Add an event to start a passport.</p>}
          </Card>
        )}
      </section>

      <section className="home-modules-section">
        <div className="home-section-heading">
          <div><p className="eyebrow">Your workspace</p><h2>Available modules</h2></div>
          <span>{links.length} tools for {roleLabels[role] || 'your account'}</span>
        </div>
        <div className="quick-grid">
          {links.map((item) => (
            <Link key={item.key} to={item.path} className="quick-card panel">
              <span className="stat-icon tone-green"><Icon name={item.icon} size={22} /></span>
              <strong>{item.label}</strong>
              <p>{item.description}</p>
              <span className="quick-arrow"><Icon name="arrowRight" size={18} /></span>
            </Link>
          ))}
        </div>
      </section>

      {role === 'viewer_buyer' && (
        <Card icon="shield" title="Verify a public tea passport" description="Use the public link from a batch QR code to review its published traceability timeline.">
          <p className="field-hint">Public passports are read-only and do not require sign-in. Private seller details and internal evidence are not included.</p>
        </Card>
      )}
    </div>
  )
}
