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

const number = (value) => new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(value ?? 0)
const month = (value) => new Intl.DateTimeFormat('en', { month: 'short', year: 'numeric' }).format(new Date(value))

export default function CombinedAuctionPriceForecast() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/component04/combined-auction-price')
      .then((response) => {
        if (!response.ok) throw new Error('Combined auction price forecast is not available. Train the model first.')
        return response.json()
      })
      .then(setData)
      .catch((err) => setError(err.message))
  }, [])

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

  if (!data) return <section className="panel"><div className="panel-heading"><h2>Combined Auction Price Forecast</h2><p>{error || 'Loading model forecast...'}</p></div></section>

  return (
    <>
      <section className="panel chart-panel">
        <div className="panel-heading">
          <div>
            <h2>Combined Workbook Auction Price Forecast</h2>
            <p>Monthly average auction price (LKR/kg), using the sales and price workbook</p>
          </div>
          <div className="model-chip"><span>Selected model</span><strong>{data.metrics.model}</strong></div>
        </div>
        <div className="metric-grid">
          <article className="metric-card"><span>2025 Test MAE (LKR/kg)</span><strong>{number(data.metrics.mae_lkr)}</strong></article>
          <article className="metric-card"><span>2025 Test RMSE (LKR/kg)</span><strong>{number(data.metrics.rmse_lkr)}</strong></article>
          <article className="metric-card"><span>2025 Test MAPE</span><strong>{number(data.metrics.mape)}%</strong></article>
          <article className="metric-card"><span>Forecast horizon</span><strong>{data.forecast.length} months</strong></article>
        </div>
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 12, right: 24, left: 0, bottom: 8 }}>
              <CartesianGrid stroke="#dbe5dc" strokeDasharray="4 4" />
              <XAxis dataKey="date" minTickGap={22} stroke="#64736a" />
              <YAxis stroke="#64736a" tickFormatter={number} width={78} />
              <Tooltip formatter={(value) => `LKR ${number(value)}/kg`} />
              <Legend />
              <Line type="monotone" dataKey="actual" name="Actual monthly price" stroke="#176f4d" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="testPrediction" name="2025 test prediction" stroke="#2f6fb0" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="forecast" name="Future forecast" stroke="#9d3a63" strokeDasharray="6 5" strokeWidth={3} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading"><h2>Model comparison</h2><p>Selected using rolling validation before 2025; test results use 2025.</p></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Model</th><th>Validation RMSE</th><th>2025 Test RMSE</th></tr></thead>
            <tbody>{data.model_comparison.map((row) => (
              <tr key={row.model}><td>{row.model}{row.model === data.metrics.model ? ' (selected)' : ''}</td><td>LKR {number(row.validation_rmse_lkr)}/kg</td><td>LKR {number(row.test_rmse_lkr)}/kg</td></tr>
            ))}</tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading"><h2>2025 Test Predictions</h2><p>Actual and predicted monthly average auction prices</p></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Month</th><th>Actual (LKR/kg)</th><th>Predicted (LKR/kg)</th><th>Absolute error</th></tr></thead>
            <tbody>{data.test_predictions.map((row) => (
              <tr key={row.date}><td>{month(row.date)}</td><td>{number(row.actual_avg_price_lkr)}</td><td>{number(row.predicted_avg_price_lkr)}</td><td>{number(Math.abs(row.actual_avg_price_lkr - row.predicted_avg_price_lkr))}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </section>
    </>
  )
}
