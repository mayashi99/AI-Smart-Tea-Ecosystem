import { useMemo } from 'react'
import { Cell, Legend, Line, LineChart, CartesianGrid, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Card, ErrorState, LoadingState, PageHeader, StatCard } from '../components/ui'
import { chartTheme } from '../lib/chartTheme'
import { formatDate, formatNumber } from '../lib/format'
import { endpoints, useApi } from '../services/api'
import ZoneIntelligencePage from './component04/ZoneIntelligencePage'

const ZONES = ['High Growns', 'Medium Growns', 'Low Growns']

export default function MarketAnalysisPage() {
  const zones = useApi(endpoints.zoneIntelligence)
  const train = useApi(endpoints.trainOutput)

  // Recent actuals plus the LSTM future forecast, one line per growing zone.
  const outlook = useMemo(() => {
    if (!train.data) return []
    const points = new Map()
    const add = (date, zone, value) => {
      const point = points.get(date) || { date, label: formatDate(date) }
      point[zone] = value
      points.set(date, point)
    }
    ZONES.forEach((zone) => {
      train.data.predictions.filter((row) => row.growing_zone === zone).slice(-12).forEach((row) => add(row.auction_date, zone, row.actual_avg_price_lkr))
      train.data.future_forecast.filter((row) => row.growing_zone === zone).forEach((row) => add(row.auction_date, zone, row.lstm_forecast_avg_price_lkr))
    })
    return [...points.values()].sort((a, b) => new Date(a.date) - new Date(b.date))
  }, [train.data])

  const firstForecast = train.data?.future_forecast?.[0]?.auction_date
  const shareData = (zones.data?.zones || []).map((zone) => ({ name: zone.zone, value: zone.buyer_preference_share_pct }))
  const fastestGrowing = (zones.data?.zones || []).reduce((best, zone) => (best == null || (zone.historical_demand_change_pct ?? -Infinity) > (best.historical_demand_change_pct ?? -Infinity) ? zone : best), null)

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Component 04 · Market analysis"
        title="Market Analysis"
        description="Compare Sri Lankan tea growing zones by auction value, buyer share and demand momentum, then score a zone for export planning."
        note="Buyer share uses auction quantity as a proxy for buyer preference."
      />

      {zones.error ? <ErrorState message={zones.error} onRetry={zones.reload} /> : !zones.data ? <LoadingState label="Loading zone market data…" /> : (
        <section className="stat-grid" aria-label="Zone market summary">
          {zones.data.zones.map((zone, index) => (
            <StatCard key={zone.zone} icon="coins" tone={['green', 'teal', 'amber'][index % 3]} label={`${zone.zone} · avg auction price`} value={`LKR ${formatNumber(zone.auction_price_lkr, 0)}/kg`} trend={zone.historical_demand_change_pct} hint="quantity vs previous period" />
          ))}
          {fastestGrowing && <StatCard icon="trend" tone="blue" label="Fastest demand growth" value={fastestGrowing.zone} hint={`+${fastestGrowing.historical_demand_change_pct}% auction quantity`} />}
        </section>
      )}

      <div className="grid-2-1">
        <Card icon="trend" title="Zone price outlook" description={`Last 12 months of actual prices and the LSTM forecast${firstForecast ? ` from ${formatDate(firstForecast)}` : ''} (LKR/kg).`}>
          {train.error ? <ErrorState compact message={train.error} onRetry={train.reload} /> : !train.data ? <LoadingState compact /> : (
            <div className="chart-box">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={outlook} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke={chartTheme.grid} strokeDasharray="4 4" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} stroke={chartTheme.axis} minTickGap={20} />
                  <YAxis tick={{ fontSize: 11 }} stroke={chartTheme.axis} tickFormatter={(value) => formatNumber(value, 0)} width={52} />
                  <Tooltip formatter={(value) => `LKR ${formatNumber(value)}/kg`} />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                  {ZONES.map((zone, index) => <Line key={zone} dataKey={zone} stroke={chartTheme.palette[index]} strokeWidth={2.2} dot={false} connectNulls />)}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card icon="globe" title="Buyer share by zone" description="Share of recent auction quantity.">
          {!zones.data ? <LoadingState compact /> : (
            <>
              <div className="chart-box is-short">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={shareData} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="85%" paddingAngle={2}>
                      {shareData.map((item, index) => <Cell key={item.name} fill={chartTheme.palette[index % chartTheme.palette.length]} />)}
                    </Pie>
                    <Tooltip formatter={(value) => `${value}%`} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="legend-list">{shareData.map((item, index) => <li key={item.name}><span style={{ background: chartTheme.palette[index % chartTheme.palette.length] }} />{item.name}<b>{item.value}%</b></li>)}</ul>
            </>
          )}
        </Card>
      </div>

      <div className="section-title"><h2>Zone Quality Score</h2><p>Zone Intelligence Engine — combine observed auction indicators with your evidence.</p></div>
      <ZoneIntelligencePage />
    </div>
  )
}
