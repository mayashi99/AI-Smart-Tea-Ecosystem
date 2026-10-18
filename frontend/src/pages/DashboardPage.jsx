import { useMemo, useState } from 'react'
import { Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import Icon from '../components/Icon'
import { Card, ErrorState, Link, LoadingState, PageHeader } from '../components/ui'
import { chartTheme } from '../lib/chartTheme'
import { formatDate, formatNumber, pctChange } from '../lib/format'
import { isFallbackModel, reliability, trend } from '../lib/forecast'
import { endpoints, useApi } from '../services/api'
import CombinedAuctionPriceForecast from './component04/CombinedAuctionPriceForecast'

const ZONE_HELP = {
  Total: 'All growing zones combined',
  'High Growns': 'Above 1,200 m — Nuwara Eliya, Dimbula, Uva',
  'Medium Growns': '600–1,200 m — Kandy region',
  'Low Growns': 'Below 600 m — Ruhuna, Sabaragamuwa',
}

const ZONE_ORDER = ['Total', 'High Growns', 'Medium Growns', 'Low Growns']

const lkr = (value, digits = 0) => `LKR ${formatNumber(value, digits)}`

function PriceTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const rows = payload.filter((item) => item.value != null && item.dataKey !== 'band')
  return (
    <div className="chart-tooltip">
      <strong>{label}</strong>
      {rows.map((item) => <span key={item.dataKey}><i style={{ background: item.color }} />{item.name}: <b>{lkr(item.value)}/kg</b></span>)}
    </div>
  )
}

function zoneSummary(dashboard, zone) {
  const actuals = dashboard.predictions.filter((row) => row.growing_zone === zone)
  const forecast = dashboard.future_forecast.filter((row) => row.growing_zone === zone)
  const metric = dashboard.model_metrics.find((row) => row.growing_zone === zone) || null
  const latest = actuals.at(-1)
  const next = forecast[0]
  const values = forecast.map((row) => row.lstm_forecast_avg_price_lkr)
  const average = values.length ? values.reduce((total, value) => total + value, 0) / values.length : null
  return {
    zone,
    actuals,
    forecast,
    metric,
    latest,
    next,
    nextChange: latest && next ? pctChange(next.lstm_forecast_avg_price_lkr, latest.actual_avg_price_lkr) : NaN,
    outlookChange: latest && average != null ? pctChange(average, latest.actual_avg_price_lkr) : NaN,
    average,
    high: values.length ? forecast.reduce((best, row) => (row.lstm_forecast_avg_price_lkr > best.lstm_forecast_avg_price_lkr ? row : best)) : null,
    low: values.length ? forecast.reduce((best, row) => (row.lstm_forecast_avg_price_lkr < best.lstm_forecast_avg_price_lkr ? row : best)) : null,
  }
}

export default function DashboardPage() {
  const { data: dashboard, error, loading, reload } = useApi(endpoints.trainOutput)
  const [zoneChoice, setZoneChoice] = useState('')
  const [showTest, setShowTest] = useState(false)
  const selectedZone = zoneChoice || dashboard?.default_zone || ''

  const summaries = useMemo(() => (dashboard ? Object.fromEntries(dashboard.zones.map((zone) => [zone, zoneSummary(dashboard, zone)])) : {}), [dashboard])
  const current = summaries[selectedZone]
  const rawModelName = current?.metric?.model || dashboard?.model || 'Model'
  const fallback = isFallbackModel(rawModelName)
  // The Ridge model is a statistical model on recent prices, not an emergency stand-in: in testing it beat the LSTM.
  const modelName = fallback ? 'Ridge regression' : rawModelName
  const trust = reliability(current?.metric?.mape)
  const direction = trend(current?.outlookChange)

  const chartData = useMemo(() => {
    if (!current) return []
    const rows = current.actuals.map((row) => ({ date: formatDate(row.auction_date), actual: row.actual_avg_price_lkr, test: row.lstm_predicted_avg_price_lkr, forecast: null }))
    // Join the forecast line to the last real price so the chart reads as one story.
    if (rows.length) rows[rows.length - 1].forecast = rows[rows.length - 1].actual
    const mape = Number(current.metric?.mape) || 0
    current.forecast.forEach((row) => {
      const value = row.lstm_forecast_avg_price_lkr
      rows.push({ date: formatDate(row.auction_date), actual: null, test: null, forecast: value, band: [value * (1 - mape / 100), value * (1 + mape / 100)] })
    })
    return rows
  }, [current])

  const firstForecastLabel = current?.forecast[0] ? formatDate(current.forecast[0].auction_date) : null
  const lastLabel = chartData.at(-1)?.date

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Component 04 · Auction price intelligence"
        title="Auction Price Forecast"
        description="See where Colombo tea auction prices are heading for each growing zone, how sure the model is, and what it means for your next sale."
        note="Forecasts are estimates from past auction prices. They don't account for sudden events such as weather shocks or policy changes."
      />

      {loading && !dashboard && <LoadingState label="Loading auction price forecast…" />}
      {error && <ErrorState message={`Auction price forecast unavailable: ${error}`} onRetry={reload} />}

      {dashboard && current && (
        <>

          <div className="zone-tabs" role="tablist" aria-label="Growing zone">
            {[...dashboard.zones].sort((a, b) => ZONE_ORDER.indexOf(a) - ZONE_ORDER.indexOf(b)).map((zone) => {
              const item = summaries[zone]
              return (
                <button key={zone} type="button" role="tab" aria-selected={zone === selectedZone} className={`zone-tab ${zone === selectedZone ? 'active' : ''}`} onClick={() => setZoneChoice(zone)}>
                  <span className="zone-tab-name">{zone === 'Total' ? 'All zones' : zone}</span>
                  <strong>{item.latest ? lkr(item.latest.actual_avg_price_lkr) : '—'}</strong>
                  <small className={item.nextChange >= 0 ? 'trend-up' : 'trend-down'}>
                    <Icon name={item.nextChange >= 0 ? 'arrowUp' : 'arrowDown'} size={12} strokeWidth={2.6} />
                    {Number.isFinite(item.nextChange) ? `${Math.abs(item.nextChange).toFixed(1)}% next month` : 'no forecast'}
                  </small>
                </button>
              )
            })}
          </div>

          <section className="forecast-hero panel">
            <div className="forecast-hero-main">
              <p className="eyebrow">{selectedZone === 'Total' ? 'All growing zones' : selectedZone} · {ZONE_HELP[selectedZone] || 'Growing zone'}</p>
              <div className={`trend-badge tone-${direction.tone}`}><Icon name={direction.icon} size={18} strokeWidth={2.4} />{direction.label}</div>
              <p className="forecast-sentence">
                The average auction price was <b>{lkr(current.latest?.actual_avg_price_lkr)}/kg</b> in {current.latest ? formatDate(current.latest.auction_date) : '—'}.
                {current.next && <> Next month ({formatDate(current.next.auction_date)}) is forecast at <b>{lkr(current.next.lstm_forecast_avg_price_lkr)}/kg</b>, and the 12-month average at <b>{lkr(current.average)}/kg</b>.</>}
              </p>
            </div>
            <div className="forecast-figures">
              <div><span>Latest actual price</span><strong>{lkr(current.latest?.actual_avg_price_lkr)}</strong><small>per kg · {current.latest ? formatDate(current.latest.auction_date) : '—'}</small></div>
              <div><span>Next month forecast</span><strong>{lkr(current.next?.lstm_forecast_avg_price_lkr)}</strong><small className={current.nextChange >= 0 ? 'trend-up' : 'trend-down'}>{current.nextChange >= 0 ? '▲' : '▼'} {Math.abs(current.nextChange || 0).toFixed(1)}% vs latest</small></div>
              <div><span>Expected 12-month range</span><strong>{lkr(current.low?.lstm_forecast_avg_price_lkr)} – {formatNumber(current.high?.lstm_forecast_avg_price_lkr, 0)}</strong><small>Peak {current.high ? formatDate(current.high.auction_date) : '—'}</small></div>
              <div className={`trust-figure tone-${trust.tone}`}><span>Forecast reliability</span><strong>{trust.label}</strong><small>{trust.note}</small></div>
            </div>
          </section>

          <Card
            icon="trend"
            title="Price history and forecast"
            description={`Monthly average auction price (LKR/kg). The shaded area shows the likely range around the forecast, based on past error.`}
            actions={<label className="toggle toggle-sm"><input type="checkbox" checked={showTest} onChange={(event) => setShowTest(event.target.checked)} /><span className="toggle-track" aria-hidden="true" /><span>Show how the model did on past months</span></label>}
          >
            <div className="chart-box is-tall">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 16, right: 16, left: 4, bottom: 4 }}>
                  <defs>
                    <linearGradient id="actualFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={chartTheme.primary} stopOpacity={0.22} /><stop offset="100%" stopColor={chartTheme.primary} stopOpacity={0} /></linearGradient>
                  </defs>
                  <CartesianGrid stroke={chartTheme.grid} vertical={false} />
                  {firstForecastLabel && lastLabel && <ReferenceArea x1={firstForecastLabel} x2={lastLabel} fill="#fff6e3" fillOpacity={0.7} label={{ value: 'Forecast', position: 'insideTopRight', fill: '#a8640a', fontSize: 12, fontWeight: 700 }} />}
                  <XAxis dataKey="date" minTickGap={24} stroke={chartTheme.axis} tick={{ fontSize: 12 }} />
                  <YAxis stroke={chartTheme.axis} tickFormatter={(value) => formatNumber(value, 0)} width={58} tick={{ fontSize: 12 }} domain={['auto', 'auto']} />
                  <Tooltip content={<PriceTooltip />} />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 13 }} />
                  <Area type="monotone" dataKey="band" name="Likely range" stroke="none" fill={chartTheme.accent} fillOpacity={0.18} legendType="square" isAnimationActive={false} />
                  <Area type="monotone" dataKey="actual" name="Actual price" stroke={chartTheme.primary} strokeWidth={2.6} fill="url(#actualFill)" dot={false} activeDot={{ r: 5 }} />
                  {showTest && <Line type="monotone" dataKey="test" name="Model's past prediction" stroke={chartTheme.secondary} strokeWidth={2} strokeDasharray="3 3" dot={false} />}
                  <Line type="monotone" dataKey="forecast" name="Forecast" stroke={chartTheme.accent} strokeWidth={3} strokeDasharray="7 5" dot={{ r: 3, fill: '#fff', strokeWidth: 2 }} activeDot={{ r: 6 }} />
                  {current.latest && <ReferenceLine x={formatDate(current.latest.auction_date)} stroke={chartTheme.muted} strokeDasharray="2 4" label={{ value: 'Latest', position: 'top', fill: chartTheme.axis, fontSize: 11 }} />}
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <div className="grid-2">
            <Card icon="doc" title="Month-by-month forecast" description={`Expected average price for ${selectedZone === 'Total' ? 'all zones' : selectedZone}, compared with the latest actual price.`}>
              <ul className="month-list">
                {current.forecast.map((row) => {
                  const change = pctChange(row.lstm_forecast_avg_price_lkr, current.latest?.actual_avg_price_lkr)
                  const width = current.high ? (row.lstm_forecast_avg_price_lkr / current.high.lstm_forecast_avg_price_lkr) * 100 : 0
                  return (
                    <li key={row.auction_date}>
                      <span className="month-name">{formatDate(row.auction_date)}</span>
                      <span className="month-bar"><b style={{ width: `${width}%` }} /></span>
                      <strong>{lkr(row.lstm_forecast_avg_price_lkr)}</strong>
                      <small className={change >= 0 ? 'trend-up' : 'trend-down'}>{change >= 0 ? '+' : ''}{change.toFixed(1)}%</small>
                    </li>
                  )
                })}
              </ul>
            </Card>

            <Card icon="bulb" title="What this means for you" description="Practical pointers based on this zone's forecast.">
              <ul className="advice-list">
                {direction.tone === 'green' && <li><Icon name="arrowUp" size={18} /><span>Prices are expected to rise, averaging <b>{Math.abs(current.outlookChange).toFixed(1)}%</b> above the latest price. If you can store tea well, holding some stock for later auctions may pay off.</span></li>}
                {direction.tone === 'red' && <li><Icon name="arrowDown" size={18} /><span>Prices are expected to ease, averaging <b>{Math.abs(current.outlookChange).toFixed(1)}%</b> below the latest price. Consider selling sooner or agreeing forward contracts now.</span></li>}
                {direction.tone === 'blue' && <li><Icon name="arrowRight" size={18} /><span>Prices are expected to stay close to today's level, so timing matters less — focus on quality and grade to earn a premium.</span></li>}
                {current.high && <li><Icon name="target" size={18} /><span>The highest forecast month is <b>{formatDate(current.high.auction_date)}</b> at about {lkr(current.high.lstm_forecast_avg_price_lkr)}/kg; the lowest is <b>{formatDate(current.low.auction_date)}</b>.</span></li>}
                <li><Icon name={trust.level === 'high' ? 'check' : 'alert'} size={18} /><span>{trust.level === 'high' ? 'This forecast has been accurate on past months, so it is a sound planning guide.' : 'Accuracy on past months was limited — check recent auction results before making large commitments.'}</span></li>
                <li><Icon name="globe" size={18} /><span>Compare with the national export demand outlook before deciding volumes. <Link to="/demand-forecast">Open Demand Forecast →</Link></span></li>
              </ul>
            </Card>
          </div>

          <details className="panel card details-card">
            <summary><span className="card-heading-icon"><Icon name="settings" /></span><span><strong>Model details</strong><small>Technical accuracy figures and recent test results for analysts</small></span><Icon name="chevronDown" size={18} className="details-chevron" /></summary>
            <div className="details-body">
              <div className="stat-grid is-four is-flat">
                <div className="mini-stat"><span>Model</span><strong>{modelName}</strong><small>{fallback ? 'Statistical model on recent prices' : current.metric?.model_type?.toUpperCase()} · {current.metric?.lookback_months}-month lookback</small></div>
                <div className="mini-stat"><span>Average error (MAE)</span><strong>{lkr(current.metric?.mae)}/kg</strong><small>Typical miss on test months</small></div>
                <div className="mini-stat"><span>Average % error (MAPE)</span><strong>{formatNumber(current.metric?.mape)}%</strong><small>RMSE {lkr(current.metric?.rmse)}</small></div>
                <div className="mini-stat"><span>R² score</span><strong>{formatNumber(current.metric?.r2)}</strong><small>1 = perfect · below 0 = worse than the average</small></div>
              </div>
              <p className="muted-line">Trained on {formatDate((dashboard.zone_periods[selectedZone] || dashboard.periods).train_start)} – {formatDate((dashboard.zone_periods[selectedZone] || dashboard.periods).train_end)}; tested month by month on {formatDate((dashboard.zone_periods[selectedZone] || dashboard.periods).test_start)} – {formatDate((dashboard.zone_periods[selectedZone] || dashboard.periods).test_end)}, which the model never saw in training.{fallback && ' This zone uses Ridge regression on the last months of prices and the season: in our latest comparison it was more accurate on these test months than the LSTM neural network, which tended to under-predict recent price levels.'}</p>
              <div className="table-wrap is-scroll">
                <table className="is-compact">
                  <thead><tr><th>Month</th><th>Actual</th><th>Model prediction</th><th>Difference</th><th>Error %</th></tr></thead>
                  <tbody>
                    {current.actuals.slice(-12).reverse().map((row) => (
                      <tr key={row.auction_date}>
                        <td>{formatDate(row.auction_date)}</td>
                        <td>{lkr(row.actual_avg_price_lkr, 2)}</td>
                        <td>{lkr(row.lstm_predicted_avg_price_lkr, 2)}</td>
                        <td>{formatNumber(row.lstm_error)}</td>
                        <td>{formatNumber(row.lstm_error_percent)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </details>
        </>
      )}

      <CombinedAuctionPriceForecast />
    </div>
  )
}
