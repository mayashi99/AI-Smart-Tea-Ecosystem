import { useMemo, useState } from 'react'
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
import Icon from '../../components/Icon'
import { Card, ErrorState, Link, LoadingState, PageHeader, StatCard } from '../../components/ui'
import { chartTheme } from '../../lib/chartTheme'
import { downloadFile, formatCompact, formatDate, formatNumber, pctChange, sum, toCSV } from '../../lib/format'
import { endpoints, useApi } from '../../services/api'

const ranges = [['24', 'Last 2 years'], ['60', 'Last 5 years'], ['all', 'All history']]

export default function ExportDemandPage() {
  const { data, error, reload } = useApi(endpoints.exportDemand)
  const [range, setRange] = useState('60')

  const chartData = useMemo(() => {
    if (!data) return []
    const allHistory = Array.isArray(data.history) ? data.history : []
    const history = range === 'all' ? allHistory : allHistory.slice(-Number(range))
    const forecast = Array.isArray(data.forecast) ? data.forecast : []
    const testPredictions = Array.isArray(data.test_predictions) ? data.test_predictions : []
    const points = new Map()
    history.forEach((row) => points.set(row.date, {
      date: formatDate(row.date), actual: row.export_volume_kg, testPrediction: null, forecast: null,
    }))
    testPredictions.forEach((row) => {
      const point = points.get(row.date) || { date: formatDate(row.date), actual: null, forecast: null }
      point.testPrediction = row.predicted_export_volume_kg
      points.set(row.date, point)
    })
    forecast.forEach((row) => points.set(row.date, {
      date: formatDate(row.date), actual: null, testPrediction: null,
      forecast: row.forecast_export_volume_kg,
    }))
    return [...points.values()]
  }, [data, range])

  const testAccuracy = 100 - Number(data?.metrics?.mape ?? 100)
  const next12 = data ? sum(data.forecast || [], 'forecast_export_volume_kg') : 0
  const last12 = data ? sum((data.history || []).slice(-12), 'export_volume_kg') : 0
  const peak = data?.forecast?.length ? data.forecast.reduce((best, row) => (row.forecast_export_volume_kg > best.forecast_export_volume_kg ? row : best)) : null
  const low = data?.forecast?.length ? data.forecast.reduce((lowest, row) => (row.forecast_export_volume_kg < lowest.forecast_export_volume_kg ? row : lowest)) : null

  const header = (
    <PageHeader
      eyebrow="Component 04 · ML demand forecasting"
      title="Tea Export Demand Forecast"
      description={data ? `Monthly total export volume in kg · Data ${formatDate(data.metrics.train_start)} – ${formatDate(data.metrics.test_end)}` : 'Monthly total Sri Lankan tea export volume and 12-month ML forecast.'}
      actions={data && (
        <>
          <div className="model-chip"><span>Selected model</span><strong>{data.metrics.model}</strong></div>
          <button type="button" className="btn btn-secondary" onClick={() => downloadFile('export-demand-forecast.csv', toCSV(data.forecast || []))}><Icon name="download" size={17} />Forecast CSV</button>
        </>
      )}
    />
  )

  if (!data) return <div className="page-stack">{header}{error ? <ErrorState message={error} onRetry={reload} /> : <LoadingState label="Loading export demand forecast…" />}</div>

  return (
    <div className="page-stack">
      {header}

      <section className="stat-grid" aria-label="Forecast summary">
        <StatCard icon="trend" label="Forecast · next 12 months" value={`${formatCompact(next12 / 1000)} t`} trend={pctChange(next12, last12)} hint="vs latest 12 months" />
        <StatCard icon="bars" tone="teal" label="Average forecast month" value={`${formatCompact(next12 / 12 / 1000)} t`} hint="National aggregate" />
        <StatCard icon="target" tone="amber" label="Peak forecast month" value={peak ? formatDate(peak.date) : '—'} hint={peak ? `${formatCompact(peak.forecast_export_volume_kg / 1000)} t` : ''} />
        <StatCard icon="check" tone="blue" label="Test accuracy (100% − MAPE)" value={`${formatNumber(testAccuracy)}%`} hint="2025 holdout" />
      </section>

      <section className="stat-grid is-four is-flat" aria-label="Export demand model metrics">
        <StatCard icon="target" label="Test MAE (kg)" value={formatNumber(data.metrics.mae_kg, 0)} />
        <StatCard icon="bars" label="Test RMSE (kg)" value={formatNumber(data.metrics.rmse_kg, 0)} />
        <StatCard icon="trend" tone="amber" label="Test MAPE" value={`${formatNumber(data.metrics.mape)}%`} />
        <StatCard icon="grid" tone="teal" label="Forecast months" value={(data.forecast || []).length} />
      </section>

      <Card
        icon="trend"
        title="Monthly export volume and forecast"
        description="Last 12 months are held out for model evaluation. Accuracy is calculated from that test-period MAPE and is not a forecast confidence probability."
        actions={<div className="segmented" role="group" aria-label="History range">{ranges.map(([value, label]) => <button key={value} type="button" className={range === value ? 'active' : ''} onClick={() => setRange(value)}>{label}</button>)}</div>}
      >
        <div className="chart-box is-tall">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 12, right: 16, left: 0, bottom: 4 }}>
              <CartesianGrid stroke={chartTheme.grid} strokeDasharray="4 4" />
              <XAxis dataKey="date" minTickGap={22} stroke={chartTheme.axis} tick={{ fontSize: 12 }} />
              <YAxis stroke={chartTheme.axis} tickFormatter={formatCompact} width={56} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(value) => `${formatNumber(value)} kg`} />
              <Legend iconType="circle" />
              <Line type="monotone" dataKey="actual" name="Actual exports" stroke={chartTheme.primary} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="testPrediction" name="Test prediction (2025)" stroke={chartTheme.secondary} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="forecast" name="Export demand forecast" stroke={chartTheme.accent} strokeDasharray="6 5" strokeWidth={3} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card
        icon="globe"
        title="AI Multi-Country Export Optimizer"
        description="Use the national export forecast to plan shipment timing across your target markets."
        actions={<Link className="btn btn-secondary" to="/trade-insights">Ask the AI Export Advisor</Link>}
      >
        <section className="stat-grid" aria-label="Forecast-based export planning">
          <StatCard icon="trend" label="National forecast · next 12 months" value={`${formatCompact(next12 / 1000)} t`} hint="Planning baseline, not destination demand" />
          <StatCard icon="target" tone="amber" label="Highest forecast month" value={peak ? formatDate(peak.date) : '—'} hint={peak ? `${formatCompact(peak.forecast_export_volume_kg / 1000)} t · plan capacity ahead` : 'No forecast available'} />
          <StatCard icon="bars" tone="teal" label="Lowest forecast month" value={low ? formatDate(low.date) : '—'} hint={low ? `${formatCompact(low.forecast_export_volume_kg / 1000)} t · consider lower-volume shipments` : 'No forecast available'} />
        </section>
        <aside className="info-note optimizer-note">
          <Icon name="info" size={22} />
          <p>This forecast contains national monthly export totals only. It can guide shipment timing, but it does not include destination-level demand, import history, or price stability, so country opportunity scores and rankings cannot be calculated from it.</p>
        </aside>
      </Card>

      <div className="grid-2">
        <Card icon="doc" title="12 month forecast" description="Forecast export volume by month.">
          <div className="table-wrap is-scroll">
            <table>
              <thead><tr><th>Month</th><th>Forecast volume (kg)</th><th>Tonnes</th></tr></thead>
              <tbody>{(data.forecast || []).map((row) => (
                <tr key={row.date}><td>{formatDate(row.date)}</td><td>{formatNumber(row.forecast_export_volume_kg)} kg</td><td>{formatNumber(row.forecast_export_volume_kg / 1000, 0)} t</td></tr>
              ))}</tbody>
            </table>
          </div>
        </Card>

        <Card icon="doc" title="Test predictions" description="Actual vs predicted monthly export volume for the 2025 test period.">
          <div className="table-wrap is-scroll">
            <table>
              <thead><tr><th>Month</th><th>Actual (kg)</th><th>Predicted (kg)</th><th>Absolute error (kg)</th></tr></thead>
              <tbody>{(data.test_predictions || []).map((row) => (
                <tr key={row.date}>
                  <td>{formatDate(row.date)}</td>
                  <td>{formatNumber(row.actual_export_volume_kg)}</td>
                  <td>{formatNumber(row.predicted_export_volume_kg)}</td>
                  <td>{formatNumber(Math.abs(row.actual_export_volume_kg - row.predicted_export_volume_kg))}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </Card>
      </div>

      <Card icon="grid" title="Model comparison" description="Selected using 2025 one-step walk-forward RMSE; the model is retrained on all available data for future forecasts.">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Model</th><th>Rolling 12-month RMSE (kg)</th><th>2025 Walk-forward RMSE (kg)</th></tr></thead>
            <tbody>{(data.model_comparison || []).map((row) => (
              <tr key={row.model} className={row.model === data.metrics.model ? 'is-selected' : ''}><td>{row.model}{row.model === data.metrics.model ? ' (selected)' : ''}</td><td>{formatNumber(row.validation_rmse_kg)}</td><td>{formatNumber(row.test_rmse_kg)}</td></tr>
            ))}{!(data.model_comparison || []).length && <tr><td colSpan="3">Model comparison data unavailable. Restart the backend to reload the latest API.</td></tr>}</tbody>
          </table>
        </div>
      </Card>

      <div className="cta-banner panel">
        <span className="stat-icon tone-green"><Icon name="clipboard" size={22} /></span>
        <div><strong>Turn this forecast into an export plan</strong><p>Use the demand outlook in the Export Readiness Index, or ask the AI Export Advisor for planning guidance.</p></div>
        <div className="button-row">
          <Link className="btn btn-primary" to="/export-readiness">Check readiness</Link>
          <Link className="btn btn-secondary" to="/trade-insights">Ask the advisor</Link>
        </div>
      </div>
    </div>
  )
}
