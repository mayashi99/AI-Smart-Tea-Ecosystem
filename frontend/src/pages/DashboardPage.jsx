import { useMemo, useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Card, ErrorState, LoadingState, PageHeader, StatCard } from '../components/ui'
import { chartTheme } from '../lib/chartTheme'
import { formatDate, formatNumber } from '../lib/format'
import { endpoints, useApi } from '../services/api'
import CombinedAuctionPriceForecast from './component04/CombinedAuctionPriceForecast'

export default function DashboardPage() {
  const { data: dashboard, error, loading, reload } = useApi(endpoints.trainOutput)
  const [zoneChoice, setZoneChoice] = useState('')
  const selectedZone = zoneChoice || dashboard?.default_zone || ''

  const selectedMetrics = useMemo(() => (dashboard ? dashboard.model_metrics.filter((metric) => metric.growing_zone === selectedZone) : []), [dashboard, selectedZone])
  const lstmMetric = selectedMetrics.find((metric) => metric.model === 'LSTM') ?? selectedMetrics[0] ?? null
  const auctionTestAccuracy = 100 - Number(lstmMetric?.mape ?? 100)
  const zonePeriods = dashboard ? dashboard.zone_periods[selectedZone] ?? dashboard.periods : null

  const chartData = useMemo(() => {
    if (!dashboard) return []
    const comparisonRows = (dashboard.test_comparison || dashboard.predictions || [])
      .filter((row) => row.growing_zone === selectedZone)
      .map((row) => ({ date: formatDate(row.auction_date), actual: row.actual_avg_price_lkr, lstm: row.lstm_predicted_avg_price_lkr, future: null }))
    const forecast = (dashboard.future_forecast || [])
      .filter((row) => row.growing_zone === selectedZone)
      .map((row) => ({ date: formatDate(row.auction_date), actual: null, lstm: null, future: row.lstm_forecast_avg_price_lkr }))
    return [...comparisonRows, ...forecast]
  }, [dashboard, selectedZone])

  const recentRows = useMemo(() => (dashboard ? dashboard.predictions.filter((row) => row.growing_zone === selectedZone).slice(-8).reverse() : []), [dashboard, selectedZone])
  const futureMonths = dashboard ? dashboard.future_forecast.filter((row) => row.growing_zone === selectedZone).length : 0

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Component 04 · Auction price intelligence"
        title="Auction Price Forecasting Dashboard"
        description={dashboard ? `LSTM model results by growing zone. Train ${formatDate(dashboard.periods.train_start)} – ${formatDate(dashboard.periods.train_end)} · Test ${formatDate(dashboard.periods.test_start)} – ${formatDate(dashboard.periods.test_end)}` : 'LSTM model results by growing zone.'}
        actions={dashboard && (
          <>
            <label className="field field-inline">
              <span>Growing zone</span>
              <select value={selectedZone} onChange={(event) => setZoneChoice(event.target.value)}>
                {dashboard.zones.map((zone) => <option key={zone} value={zone}>{zone}</option>)}
              </select>
            </label>
            <div className="model-chip"><span>{dashboard.model}</span><strong>{lstmMetric?.lookback_months ?? dashboard.lstm.lookback_months}-month lookback</strong></div>
          </>
        )}
      />

      {loading && <LoadingState label="Loading train output…" />}
      {error && <ErrorState message={`Train output unavailable: ${error}`} onRetry={reload} />}

      {dashboard && (
        <>
          <p className="muted-line">{selectedZone}: Train {formatDate(zonePeriods.train_start)} – {formatDate(zonePeriods.train_end)} · Test {formatDate(zonePeriods.test_start)} – {formatDate(zonePeriods.test_end)}</p>

          <section className="stat-grid is-six" aria-label="Training metrics">
            <StatCard icon="target" label="LSTM MAE" value={formatNumber(lstmMetric?.mae)} hint="LKR/kg" />
            <StatCard icon="bars" label="LSTM RMSE" value={formatNumber(lstmMetric?.rmse)} hint="LKR/kg" />
            <StatCard icon="trend" tone="amber" label="LSTM MAPE" value={`${formatNumber(lstmMetric?.mape)}%`} />
            <StatCard icon="check" tone="teal" label="Test accuracy (100% − MAPE)" value={`${formatNumber(auctionTestAccuracy)}%`} hint="Retrospective, not a confidence score" />
            <StatCard icon="sparkle" tone="blue" label="R² score" value={formatNumber(lstmMetric?.r2)} />
            <StatCard icon="grid" label="Future months" value={formatNumber(futureMonths)} />
          </section>

          <Card icon="trend" title="Actual vs LSTM test prediction" description="Monthly test-period comparison and future forecast for the selected growing zone (LKR/kg).">
            <div className="chart-box is-tall">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 12, right: 16, left: 0, bottom: 4 }}>
                  <CartesianGrid stroke={chartTheme.grid} strokeDasharray="4 4" />
                  <XAxis dataKey="date" minTickGap={22} stroke={chartTheme.axis} tick={{ fontSize: 12 }} />
                  <YAxis stroke={chartTheme.axis} tickFormatter={formatNumber} width={64} tick={{ fontSize: 12 }} />
                  <Tooltip formatter={(value) => `LKR ${formatNumber(value)}`} />
                  <Legend iconType="circle" />
                  <Line type="monotone" dataKey="actual" name="Actual" stroke={chartTheme.primary} strokeWidth={3} dot={false} />
                  <Line type="monotone" dataKey="lstm" name="LSTM Test Prediction" stroke={chartTheme.secondary} strokeWidth={3} dot={false} />
                  <Line type="monotone" dataKey="future" name="Future Forecast" stroke={chartTheme.accent} strokeDasharray="6 5" strokeWidth={3} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <section className="model-grid" aria-label="Model comparison">
            {selectedMetrics.map((metric) => (
              <Card key={metric.model} icon="grid" title={metric.model} description={`MAE ${formatNumber(metric.mae)} | RMSE ${formatNumber(metric.rmse)}`} />
            ))}
            <Card icon="settings" title="LSTM setup" description={`${dashboard.lstm.role}; ${dashboard.lstm.model_type} architecture, ${dashboard.lstm.lookback_months}-month lookback, ${dashboard.lstm.hidden_size} hidden units, ${dashboard.lstm.epochs} maximum epochs.`} />
          </section>

          <Card icon="doc" title="Latest test predictions" description="Last 8 months from the testing dataset.">
            <div className="table-wrap">
              <table>
                <thead><tr><th>Date</th><th>Actual</th><th>LSTM</th><th>LSTM Error</th><th>Error %</th></tr></thead>
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
          </Card>
        </>
      )}

      <CombinedAuctionPriceForecast />
    </div>
  )
}
