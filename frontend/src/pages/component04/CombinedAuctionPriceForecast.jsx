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
import { Card, ErrorState, LoadingState, StatCard } from '../../components/ui'
import { chartTheme } from '../../lib/chartTheme'
import { formatDate as month, formatNumber as number } from '../../lib/format'
import { endpoints, useApi } from '../../services/api'

export default function CombinedAuctionPriceForecast() {
  const { data, error, reload } = useApi(endpoints.combinedAuctionPrice)

  const chartData = useMemo(() => {
    if (!data) return []
    const points = new Map()
    data.history.forEach((row) => points.set(row.date, {
      date: month(row.date), actual: row.avg_price_lkr, testPrediction: null, forecast: null,
    }))
    data.test_predictions.forEach((row) => {
      const point = points.get(row.date)
      if (point) point.testPrediction = row.predicted_avg_price_lkr
    })
    data.forecast.forEach((row) => points.set(row.date, {
      date: month(row.date), actual: null, testPrediction: null, forecast: row.forecast_avg_price_lkr,
    }))
    return [...points.values()]
  }, [data])

  const testAccuracy = 100 - Number(data?.metrics?.mape ?? 100)

  if (!data) {
    return (
      <Card icon="coins" title="Combined Auction Price Forecast">
        {error ? <ErrorState compact message={error} onRetry={reload} /> : <LoadingState compact label="Loading model forecast…" />}
      </Card>
    )
  }

  return (
    <>
      <Card
        icon="coins"
        title="Combined workbook auction price forecast"
        description="Monthly average auction price (LKR/kg), using the sales and price workbook."
        actions={<div className="model-chip"><span>Selected model</span><strong>{data.metrics.model}</strong></div>}
      >
        <div className="stat-grid is-five is-flat">
          <StatCard icon="target" label="2025 Test MAE (LKR/kg)" value={number(data.metrics.mae_lkr)} />
          <StatCard icon="bars" label="2025 Test RMSE (LKR/kg)" value={number(data.metrics.rmse_lkr)} />
          <StatCard icon="trend" tone="amber" label="2025 Test MAPE" value={`${number(data.metrics.mape)}%`} />
          <StatCard icon="check" tone="teal" label="Test accuracy (100% − MAPE)" value={`${number(testAccuracy)}%`} hint="Retrospective error metric" />
          <StatCard icon="grid" tone="blue" label="Forecast horizon" value={`${data.forecast.length} months`} />
        </div>
        <div className="chart-box is-tall">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 12, right: 16, left: 0, bottom: 4 }}>
              <CartesianGrid stroke={chartTheme.grid} strokeDasharray="4 4" />
              <XAxis dataKey="date" minTickGap={22} stroke={chartTheme.axis} tick={{ fontSize: 12 }} />
              <YAxis stroke={chartTheme.axis} tickFormatter={number} width={64} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(value) => `LKR ${number(value)}/kg`} />
              <Legend iconType="circle" />
              <Line type="monotone" dataKey="actual" name="Actual monthly price" stroke={chartTheme.primary} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="testPrediction" name="2025 test prediction" stroke={chartTheme.secondary} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="forecast" name="Future forecast" stroke={chartTheme.accent} strokeDasharray="6 5" strokeWidth={3} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div className="grid-2">
        <Card icon="grid" title="Model comparison" description="Selected using rolling validation before 2025; test results use 2025.">
          <div className="table-wrap">
            <table>
              <thead><tr><th>Model</th><th>Validation RMSE</th><th>2025 Test RMSE</th></tr></thead>
              <tbody>{data.model_comparison.map((row) => (
                <tr key={row.model} className={row.model === data.metrics.model ? 'is-selected' : ''}><td>{row.model}{row.model === data.metrics.model ? ' (selected)' : ''}</td><td>LKR {number(row.validation_rmse_lkr)}/kg</td><td>LKR {number(row.test_rmse_lkr)}/kg</td></tr>
              ))}</tbody>
            </table>
          </div>
        </Card>

        <Card icon="doc" title="2025 test predictions" description="Actual and predicted monthly average auction prices.">
          <div className="table-wrap is-scroll">
            <table>
              <thead><tr><th>Month</th><th>Actual (LKR/kg)</th><th>Predicted (LKR/kg)</th><th>Absolute error</th></tr></thead>
              <tbody>{data.test_predictions.map((row) => (
                <tr key={row.date}><td>{month(row.date)}</td><td>{number(row.actual_avg_price_lkr)}</td><td>{number(row.predicted_avg_price_lkr)}</td><td>{number(Math.abs(row.actual_avg_price_lkr - row.predicted_avg_price_lkr))}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </Card>
      </div>
    </>
  )
}
