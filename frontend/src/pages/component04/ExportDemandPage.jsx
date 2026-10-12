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

const formatNumber = (value) => new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(value ?? 0)
const formatDate = (value) => new Intl.DateTimeFormat('en', { month: 'short', year: 'numeric' }).format(new Date(value))

export default function ExportDemandPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/component04/export-demand')
      .then((response) => {
        if (!response.ok) throw new Error('Export demand forecast is not available yet')
        return response.json()
      })
      .then(setData)
      .catch((err) => setError(err.message))
  }, [])

  const chartData = useMemo(() => {
    if (!data) return []
    const history = Array.isArray(data.history) ? data.history : []
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
  }, [data])

  if (!data) return <main className="screen">{error || 'Loading export demand forecast...'}</main>

  return (
    <main className="dashboard">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Component 04</p>
          <h1>Tea Export Demand Forecast</h1>
          <p className="subtle">
            Monthly total export volume in kg | Data {formatDate(data.metrics.train_start)} - {formatDate(data.metrics.test_end)}
          </p>
        </div>
        <div className="model-chip">
          <span>Selected model</span>
          <strong>{data.metrics.model}</strong>
        </div>
      </header>

      <section className="metric-grid" aria-label="Export demand model metrics">
        <article className="metric-card"><span>Test MAE (kg)</span><strong>{formatNumber(data.metrics.mae_kg)}</strong></article>
        <article className="metric-card"><span>Test RMSE (kg)</span><strong>{formatNumber(data.metrics.rmse_kg)}</strong></article>
        <article className="metric-card"><span>Test MAPE</span><strong>{formatNumber(data.metrics.mape)}%</strong></article>
        <article className="metric-card"><span>Forecast months</span><strong>{(data.forecast || []).length}</strong></article>
      </section>

      <section className="panel chart-panel">
        <div className="panel-heading">
          <h2>Monthly export volume and forecast</h2>
          <p>Last 12 months are held out for model evaluation; forecast continues beyond the observed data.</p>
        </div>
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 12, right: 24, left: 0, bottom: 8 }}>
              <CartesianGrid stroke="#dbe5dc" strokeDasharray="4 4" />
              <XAxis dataKey="date" minTickGap={22} stroke="#64736a" />
              <YAxis stroke="#64736a" tickFormatter={formatNumber} width={88} />
              <Tooltip formatter={(value) => `${formatNumber(value)} kg`} />
              <Legend />
              <Line type="monotone" dataKey="actual" name="Actual exports" stroke="#176f4d" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="testPrediction" name="Test prediction (2025)" stroke="#2f6fb0" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="forecast" name="Export demand forecast" stroke="#9d3a63" strokeDasharray="6 5" strokeWidth={3} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>Test predictions</h2>
          <p>Actual vs predicted monthly export volume for the 2025 test period</p>
        </div>
        <div className="table-wrap">
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
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>Model comparison</h2>
          <p>Selected using 2025 one-step walk-forward RMSE; the model is retrained on all available data for future forecasts.</p>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Model</th><th>Rolling 12-month RMSE (kg)</th><th>2025 Walk-forward RMSE (kg)</th></tr></thead>
            <tbody>{(data.model_comparison || []).map((row) => (
              <tr key={row.model}><td>{row.model}{row.model === data.metrics.model ? ' (selected)' : ''}</td><td>{formatNumber(row.validation_rmse_kg)}</td><td>{formatNumber(row.test_rmse_kg)}</td></tr>
            ))}{!(data.model_comparison || []).length && <tr><td colSpan="3">Model comparison data unavailable. Restart the backend to reload the latest API.</td></tr>}</tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>12 month forecast</h2>
          <p>Forecast export volume by month</p>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Month</th><th>Forecast volume (kg)</th></tr></thead>
            <tbody>{(data.forecast || []).map((row) => (
              <tr key={row.date}><td>{formatDate(row.date)}</td><td>{formatNumber(row.forecast_export_volume_kg)} kg</td></tr>
            ))}</tbody>
          </table>
        </div>
      </section>
    </main>
  )
}
