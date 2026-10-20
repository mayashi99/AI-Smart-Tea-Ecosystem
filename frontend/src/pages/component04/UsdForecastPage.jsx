import { useMemo } from 'react'
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
import { Card, ErrorState, LoadingState, PageHeader, StatCard } from '../../components/ui'
import { chartTheme } from '../../lib/chartTheme'
import { formatNumber as number } from '../../lib/format'
import { endpoints, useApi } from '../../services/api'

const modelLabels = {
  ridge: 'Ridge',
  extra_trees: 'Extra Trees',
}

const dateLabel = (value) => new Intl.DateTimeFormat('en', {
  month: 'short',
  day: 'numeric',
  year: '2-digit',
}).format(new Date(`${value}T00:00:00`))

export default function UsdForecastPage() {
  const { data, error, reload } = useApi(endpoints.usdForecast)

  const chartData = useMemo(() => {
    if (!data) return []
    const points = new Map()
    Object.entries(data.test_predictions).forEach(([model, rows]) => {
      rows.forEach((row) => {
        const point = points.get(row.date) || {
          date: dateLabel(row.date),
          actual: row.actual_lkr_per_usd,
        }
        point[`${model}Test`] = row.predicted_lkr_per_usd
        points.set(row.date, point)
      })
    })
    Object.entries(data.forecasts).forEach(([model, rows]) => {
      rows.forEach((row) => {
        const point = points.get(row.date) || { date: dateLabel(row.date) }
        point[`${model}Forecast`] = row.forecast_lkr_per_usd
        points.set(row.date, point)
      })
    })
    return [...points.values()]
  }, [data])

  if (!data) {
    return (
      <div className="page-stack">
        <PageHeader eyebrow="Market intelligence" title="USD/LKR Forecast" description="Compare daily exchange-rate forecasts from two models." />
        <Card icon="globe" title="USD/LKR model results">
          {error ? <ErrorState compact message={error} onRetry={reload} /> : <LoadingState compact label="Loading USD/LKR forecasts…" />}
        </Card>
      </div>
    )
  }

  const selectedModel = data.metadata.best_model
  const selectedMetrics = data.model_comparison.find((row) => row.model === selectedModel)
  const latestActual = data.test_predictions[selectedModel]?.at(-1)

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Market intelligence"
        title="USD/LKR Forecast"
        description="Daily Sri Lankan rupees per US dollar. Compare two model forecasts and review their chronological validation and test results."
        note={`Training data: ${dateLabel(data.metadata.training_start)} – ${dateLabel(data.metadata.training_end)} · Forecast: ${data.metadata.forecast_horizon_business_days} weekdays. Forecast dates do not account for public holidays.`}
      />

      <Card
        icon="globe"
        title="USD/LKR exchange-rate forecast"
        description="The chart shows historical test-period actuals and predictions, followed by both model forecasts."
        actions={<div className="model-chip"><span>Selected on validation</span><strong>{modelLabels[selectedModel] || selectedModel}</strong></div>}
      >
        <div className="stat-grid is-five is-flat">
          <StatCard icon="coins" label="Latest actual (LKR/USD)" value={number(latestActual?.actual_lkr_per_usd)} hint={latestActual ? dateLabel(latestActual.date) : ''} />
          <StatCard icon="target" label="Validation MAE (LKR/USD)" value={number(selectedMetrics?.validation_mae_lkr_per_usd)} />
          <StatCard icon="bars" label="Test MAE (LKR/USD)" value={number(selectedMetrics?.test_mae_lkr_per_usd)} />
          <StatCard icon="trend" tone="amber" label="Test RMSE (LKR/USD)" value={number(selectedMetrics?.test_rmse_lkr_per_usd)} />
          <StatCard icon="grid" tone="blue" label="Forecast horizon" value={`${data.metadata.forecast_horizon_business_days} weekdays`} />
        </div>
        <div className="chart-box is-tall">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 12, right: 16, left: 0, bottom: 4 }}>
              <CartesianGrid stroke={chartTheme.grid} strokeDasharray="4 4" />
              <XAxis dataKey="date" minTickGap={30} stroke={chartTheme.axis} tick={{ fontSize: 11 }} />
              <YAxis stroke={chartTheme.axis} tickFormatter={number} width={68} tick={{ fontSize: 12 }} domain={['auto', 'auto']} />
              <Tooltip formatter={(value) => `LKR ${number(value)} per USD`} />
              <Legend iconType="circle" />
              <Line type="monotone" dataKey="actual" name="Actual exchange rate" stroke={chartTheme.primary} strokeWidth={2} dot={false} connectNulls />
              <Line type="monotone" dataKey="ridgeTest" name="Ridge test prediction" stroke={chartTheme.secondary} strokeWidth={1.5} dot={false} connectNulls />
              <Line type="monotone" dataKey="extra_treesTest" name="Extra Trees test prediction" stroke={chartTheme.accent} strokeWidth={1.5} dot={false} connectNulls />
              <Line type="monotone" dataKey="ridgeForecast" name="Ridge forecast" stroke={chartTheme.secondary} strokeDasharray="6 5" strokeWidth={3} dot={false} connectNulls />
              <Line type="monotone" dataKey="extra_treesForecast" name="Extra Trees forecast" stroke={chartTheme.accent} strokeDasharray="6 5" strokeWidth={3} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div className="grid-2">
        <Card icon="grid" title="Model comparison" description="Models are ranked by validation MAE; test metrics are from the separate later test period. Lower errors are better.">
          <div className="table-wrap">
            <table>
              <thead><tr><th>Rank</th><th>Model</th><th>Validation MAE</th><th>Test MAE</th><th>Test RMSE</th></tr></thead>
              <tbody>{data.model_comparison.map((row) => (
                <tr key={row.model} className={row.model === selectedModel ? 'is-selected' : ''}>
                  <td>{row.rank}</td>
                  <td>{modelLabels[row.model] || row.model}{row.model === selectedModel ? ' (selected)' : ''}</td>
                  <td>{number(row.validation_mae_lkr_per_usd)}</td>
                  <td>{number(row.test_mae_lkr_per_usd)}</td>
                  <td>{number(row.test_rmse_lkr_per_usd)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </Card>

        <Card icon="trend" title="Future exchange-rate forecasts" description="Projected LKR for one US dollar on each weekday in the forecast horizon.">
          <div className="table-wrap is-scroll">
            <table>
              <thead><tr><th>Date</th><th>Ridge (LKR/USD)</th><th>Extra Trees (LKR/USD)</th></tr></thead>
              <tbody>{(data.forecasts.ridge || []).map((row, index) => (
                <tr key={row.date}>
                  <td>{dateLabel(row.date)}</td>
                  <td>{number(row.forecast_lkr_per_usd)}</td>
                  <td>{number(data.forecasts.extra_trees?.[index]?.forecast_lkr_per_usd)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  )
}
