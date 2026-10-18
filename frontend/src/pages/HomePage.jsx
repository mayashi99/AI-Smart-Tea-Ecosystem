import { useMemo } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import Icon from '../components/Icon'
import { Card, ErrorState, Link, LoadingState, StatCard } from '../components/ui'
import { chartTheme } from '../lib/chartTheme'
import { formatCompact, formatDate, formatNumber, pctChange, sum } from '../lib/format'
import { navItems, workspaceRoles } from '../lib/routes'
import { useLastEri, useSettings } from '../lib/settings'
import { endpoints, useApi } from '../services/api'
import heroImage from '../assets/home-hero.jpg'

function greeting() {
  const hour = new Date().getHours()
  return hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
}

export default function HomePage() {
  const settings = useSettings()
  const lastEri = useLastEri()
  const demand = useApi(endpoints.exportDemand)
  const price = useApi(endpoints.combinedAuctionPrice)
  const ledger = useApi(endpoints.passports)
  const zones = useApi(endpoints.zoneIntelligence)

  const demandStats = useMemo(() => {
    if (!demand.data) return null
    const history = demand.data.history || []
    const forecast = demand.data.forecast || []
    const next12 = sum(forecast, 'forecast_export_volume_kg')
    const last12 = sum(history.slice(-12), 'export_volume_kg')
    const chart = [
      ...history.slice(-24).map((row) => ({ date: formatDate(row.date), historical: row.export_volume_kg / 1000, forecast: null })),
      ...forecast.map((row) => ({ date: formatDate(row.date), historical: null, forecast: row.forecast_export_volume_kg / 1000 })),
    ]
    // Bridge the forecast line to the last observed month so the series join visually.
    const bridge = chart[Math.min(24, history.length) - 1]
    if (bridge) bridge.forecast = bridge.historical
    return { next12, last12, change: pctChange(next12, last12), accuracy: 100 - Number(demand.data.metrics?.mape ?? 100), model: demand.data.metrics?.model, chart }
  }, [demand.data])

  const priceStats = useMemo(() => {
    const history = price.data?.history || []
    if (history.length < 2) return null
    const latest = history.at(-1)
    const previous = history.at(-2)
    return { latest: latest.avg_price_lkr, month: formatDate(latest.date), change: pctChange(latest.avg_price_lkr, previous.avg_price_lkr) }
  }, [price.data])

  const recentEvents = useMemo(() => (ledger.data?.passports || [])
    .flatMap((passport) => passport.events)
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
    .slice(0, 5), [ledger.data])

  const zoneChart = (zones.data?.zones || []).map((zone) => ({ zone: zone.zone.replace(' Growns', ''), price: zone.auction_price_lkr, share: zone.buyer_preference_share_pct }))
  const quickLinks = navItems.filter((item) => !['home', 'settings'].includes(item.key))
  const firstName = (settings.displayName || '').split(' ')[0]

  return (
    <div className="page-stack">
      <section className="home-hero panel">
        <div className="home-hero-copy">
          <p className="eyebrow">TeaExportAI · Sri Lanka Tea Intelligence</p>
          <h1>{greeting()}{firstName ? `, ${firstName}` : ''}</h1>
          <p>Export planning, market intelligence and trusted batch traceability for Sri Lankan tea — powered by ML demand and auction price forecasts.</p>
          <div className="button-row">
            <Link className="btn btn-primary" to="/export-readiness"><Icon name="clipboard" size={18} />Check export readiness</Link>
            <Link className="btn btn-secondary" to="/demand-forecast"><Icon name="trend" size={18} />View demand forecast</Link>
          </div>
        </div>
        <img className="hero-image" src={heroImage} alt="" aria-hidden="true" />
      </section>

      <section className="stat-grid" aria-label="Key statistics">
        <StatCard icon="trend" label="Forecast export demand · next 12 months" value={demandStats ? `${formatCompact(demandStats.next12 / 1000)} t` : demand.error ? 'Unavailable' : '…'} trend={demandStats?.change} hint={demandStats ? 'vs latest 12 months' : demand.error} to="/demand-forecast" />
        <StatCard icon="coins" tone="amber" label="Average auction price" value={priceStats ? `LKR ${formatNumber(priceStats.latest, 0)}/kg` : price.error ? 'Unavailable' : '…'} trend={priceStats?.change} hint={priceStats ? `${priceStats.month} vs prior month` : price.error} to="/dashboard" />
        <StatCard icon="target" tone="blue" label="Demand model test accuracy" value={demandStats ? `${formatNumber(demandStats.accuracy, 1)}%` : '…'} hint={demandStats ? '100% − holdout MAPE' : demand.error} to="/demand-forecast" />
        <StatCard icon="shield" tone="teal" label="Traceable tea batches" value={ledger.data ? formatNumber(ledger.data.passports.length, 0) : ledger.error ? 'Unavailable' : '…'} hint={ledger.data ? (ledger.data.ledger_valid ? `Ledger verified · ${ledger.data.ledger_records} records` : 'Ledger integrity issue') : ledger.error} to="/digital-passport" />
      </section>

      <div className="grid-2-1">
        <Card icon="bars" title="Export demand analytics" description="Monthly national export volume (tonnes): last 24 months and the 12-month ML forecast." actions={<Link className="btn btn-ghost btn-sm" to="/demand-forecast">Details<Icon name="arrowRight" size={15} /></Link>}>
          {demand.loading ? <LoadingState compact label="Loading export demand…" /> : demand.error ? <ErrorState compact message={demand.error} onRetry={demand.reload} /> : (
            <div className="chart-box">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={demandStats.chart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke={chartTheme.grid} vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke={chartTheme.axis} minTickGap={18} />
                  <YAxis tick={{ fontSize: 11 }} stroke={chartTheme.axis} tickFormatter={formatCompact} width={48} />
                  <Tooltip formatter={(value) => `${formatNumber(value, 0)} t`} />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="historical" name="Historical" fill={chartTheme.primary} radius={[4, 4, 0, 0]} maxBarSize={18} />
                  <Line dataKey="forecast" name="Forecast" stroke={chartTheme.primary} strokeDasharray="5 4" strokeWidth={2.4} dot={{ r: 3, fill: '#fff', strokeWidth: 2 }} connectNulls={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card icon="clipboard" title="Export readiness" description="Your most recent Export Readiness Index.">
          {lastEri ? (
            <div className="eri-snapshot">
              <div className="mini-gauge" style={{ '--progress': `${lastEri.score}%` }}><div><strong>{lastEri.score}</strong><span>/ 100</span></div></div>
              <div className={`verdict ${lastEri.score >= 80 ? 'is-ready' : ''}`}><strong>{lastEri.band}</strong><span>{lastEri.destination_country} · {new Date(lastEri.saved_at).toLocaleDateString()}</span></div>
              {lastEri.criteria?.length > 0 && <ul className="snapshot-list">{lastEri.criteria.map((item) => <li key={item.key}><span>{item.label}</span><b>{Math.round(item.score)}</b></li>)}</ul>}
              <Link className="btn btn-primary btn-block" to="/export-readiness">Update assessment</Link>
            </div>
          ) : (
            <div className="eri-snapshot is-empty">
              <span className="empty-illustration"><Icon name="clipboard" size={34} /></span>
              <strong>No assessment yet</strong>
              <p>Combine demand forecast evidence with your capacity, documents and quality status to get an explainable score.</p>
              <Link className="btn btn-primary btn-block" to="/export-readiness">Calculate ERI</Link>
            </div>
          )}
        </Card>
      </div>

      <div className="grid-2">
        <Card icon="coins" title="Auction price by growing zone" description="Latest zone-level average auction price (LKR/kg) and share of auction quantity." actions={<Link className="btn btn-ghost btn-sm" to="/market-analysis">Analyse<Icon name="arrowRight" size={15} /></Link>}>
          {zones.loading ? <LoadingState compact /> : zones.error ? <ErrorState compact message={zones.error} onRetry={zones.reload} /> : (
            <>
              <div className="chart-box is-short">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={zoneChart} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
                    <CartesianGrid stroke={chartTheme.grid} horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 11 }} stroke={chartTheme.axis} tickFormatter={formatCompact} />
                    <YAxis type="category" dataKey="zone" tick={{ fontSize: 12 }} stroke={chartTheme.axis} width={64} />
                    <Tooltip formatter={(value) => `LKR ${formatNumber(value)}/kg`} />
                    <Bar dataKey="price" name="Avg price" radius={[0, 6, 6, 0]} maxBarSize={26}>
                      {zoneChart.map((item, index) => <Cell key={item.zone} fill={chartTheme.palette[index % chartTheme.palette.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="chip-row">{zoneChart.map((item) => <span className="chip" key={item.zone}>{item.zone}: {item.share}% of quantity</span>)}</div>
            </>
          )}
        </Card>

        <Card icon="shield" title="Recent traceability activity" description="Latest events in the hash-linked Digital Passport ledger." actions={<Link className="btn btn-ghost btn-sm" to="/digital-passport">Open ledger<Icon name="arrowRight" size={15} /></Link>}>
          {ledger.loading ? <LoadingState compact /> : ledger.error ? <ErrorState compact message={ledger.error} onRetry={ledger.reload} /> : recentEvents.length === 0 ? (
            <div className="state-box is-compact"><Icon name="package" size={22} /><span>No batches recorded yet.</span><Link className="btn btn-ghost btn-sm" to="/digital-passport">Register a batch</Link></div>
          ) : (
            <ul className="activity-list">
              {recentEvents.map((event) => (
                <li key={event.record_hash}>
                  <span className="activity-dot" />
                  <div><strong>{event.batch_id} · {event.event_type}</strong><small>{event.location} · {event.tea_grade} · {formatNumber(event.quantity_kg)} kg</small></div>
                  <time dateTime={event.timestamp}>{new Date(event.timestamp).toLocaleDateString()}</time>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <section>
        <div className="section-title"><h2>Quick access</h2><p>Jump into any module of the platform.</p></div>
        <div className="quick-grid">
          {quickLinks.map((item) => (
            <Link key={item.key} to={item.path} className="quick-card panel">
              <span className="stat-icon tone-green"><Icon name={item.icon} size={22} /></span>
              <strong>{item.label}</strong>
              <p>{item.description}</p>
              <span className="quick-arrow"><Icon name="arrowRight" size={18} /></span>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <div className="section-title"><h2>Workspaces</h2><p>Role-based starting points for sellers, the Tea Board and buyers.</p></div>
        <div className="quick-grid is-three">
          {Object.entries(workspaceRoles).map(([key, role]) => (
            <Link key={key} to={role.path} className={`quick-card panel workspace-card ${settings.role === key ? 'is-current' : ''}`}>
              <span className="stat-icon tone-teal"><Icon name="user" size={22} /></span>
              <strong>{role.title}{settings.role === key && <em className="chip">Your role</em>}</strong>
              <p>{role.intro}</p>
              <span className="quick-arrow"><Icon name="arrowRight" size={18} /></span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
