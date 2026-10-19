import { useState } from 'react'
import Icon from '../components/Icon'
import { Card, ErrorState, Link, LoadingState, PageHeader } from '../components/ui'
import { downloadFile, formatCompact, formatDate, formatNumber, pctChange, sum, toCSV } from '../lib/format'
import { useLastEri } from '../lib/settings'
import { endpoints, getJSON, useApi } from '../services/api'

const round = (value, digits = 2) => (value == null ? null : Math.round(Number(value) * 10 ** digits) / 10 ** digits)

const reports = [
  { id: 'demand-forecast', group: 'Demand', icon: 'trend', title: 'Export demand forecast', description: '12-month ML forecast of national export volume.', source: endpoints.exportDemand,
    build: (data) => data.forecast.map((row) => ({ month: row.date, forecast_volume_kg: round(row.forecast_export_volume_kg), forecast_tonnes: round(row.forecast_export_volume_kg / 1000, 1) })) },
  { id: 'demand-test', group: 'Demand', icon: 'target', title: 'Demand model test predictions', description: 'Actual vs predicted volume for the 2025 holdout period.', source: endpoints.exportDemand,
    build: (data) => data.test_predictions.map((row) => ({ month: row.date, actual_kg: round(row.actual_export_volume_kg), predicted_kg: round(row.predicted_export_volume_kg), absolute_error_kg: round(Math.abs(row.actual_export_volume_kg - row.predicted_export_volume_kg)) })) },
  { id: 'demand-history', group: 'Demand', icon: 'bars', title: 'Export volume history', description: 'Monthly national export volume used to train the model.', source: endpoints.exportDemand,
    build: (data) => data.history.map((row) => ({ month: row.date, export_volume_kg: round(row.export_volume_kg) })) },
  { id: 'auction-forecast', group: 'Market', icon: 'coins', title: 'Auction price forecast by zone', description: 'LSTM future monthly auction prices per growing zone.', source: endpoints.trainOutput,
    build: (data) => data.future_forecast.map((row) => ({ zone: row.growing_zone, month: row.auction_date, forecast_price_lkr_kg: row.lstm_forecast_avg_price_lkr })) },
  { id: 'auction-metrics', group: 'Market', icon: 'grid', title: 'Auction model metrics', description: 'MAE, RMSE, MAPE and R² by zone and model.', source: endpoints.trainOutput,
    build: (data) => data.model_metrics.map((row) => ({ zone: row.growing_zone, model: row.model, mae: row.mae, rmse: row.rmse, mape_pct: row.mape, r2: row.r2, lookback_months: row.lookback_months })) },
  { id: 'combined-price', group: 'Market', icon: 'coins', title: 'Combined workbook price forecast', description: 'Best-model monthly average auction price forecast.', source: endpoints.combinedAuctionPrice,
    build: (data) => data.forecast.map((row) => ({ month: row.date, forecast_price_lkr_kg: round(row.forecast_avg_price_lkr), model: data.metrics.model })) },
  { id: 'usd-forecast', group: 'Market', icon: 'globe', title: 'USD/LKR exchange-rate forecast', description: 'Compare Ridge and Extra Trees weekday exchange-rate forecasts.', source: endpoints.usdForecast,
    build: (data) => (data.forecasts.ridge || []).map((row, index) => ({ date: row.date, ridge_lkr_per_usd: round(row.forecast_lkr_per_usd, 4), extra_trees_lkr_per_usd: round(data.forecasts.extra_trees?.[index]?.forecast_lkr_per_usd, 4), selected_model: data.metadata.best_model })) },
  { id: 'zone-summary', group: 'Market', icon: 'globe', title: 'Zone market summary', description: 'Zone prices, buyer share and demand change.', source: endpoints.zoneIntelligence,
    build: (data) => data.zones.map((row) => ({ zone: row.zone, auction_price_lkr_kg: row.auction_price_lkr, auction_price_score: row.auction_price_score, buyer_share_pct: row.buyer_preference_share_pct, demand_change_pct: row.historical_demand_change_pct, latest_period: row.latest_period })) },
  { id: 'passport-ledger', group: 'Traceability', icon: 'shield', title: 'Digital passport ledger', description: 'All traceability events with record hashes.', source: endpoints.passports,
    build: (data) => data.passports.flatMap((passport) => passport.events.map((event) => ({ batch_id: event.batch_id, event_type: event.event_type, location: event.location, tea_grade: event.tea_grade, quantity_kg: event.quantity_kg, timestamp: event.timestamp, record_hash: event.record_hash, previous_hash: event.previous_hash, note: event.note }))) },
]

function eriRows(eri) {
  return (eri?.criteria || []).map((item) => ({ criterion: item.label, weight_pct: item.weight, score: round(item.score, 1), weighted_points: round(item.score * item.weight / 100, 1), evidence: item.evidence }))
}

function ExecutiveSummary() {
  const demand = useApi(endpoints.exportDemand)
  const price = useApi(endpoints.combinedAuctionPrice)
  const ledger = useApi(endpoints.passports)
  const eri = useLastEri()
  const next12 = demand.data ? sum(demand.data.forecast, 'forecast_export_volume_kg') : null
  const last12 = demand.data ? sum(demand.data.history.slice(-12), 'export_volume_kg') : null
  const latestPrice = price.data?.history?.at(-1)

  const rows = [
    ['Export demand · next 12 months', next12 != null ? `${formatCompact(next12 / 1000)} tonnes (${pctChange(next12, last12) >= 0 ? '+' : ''}${formatNumber(pctChange(next12, last12), 1)}% vs latest 12 months)` : demand.error || 'Loading…'],
    ['Demand model', demand.data ? `${demand.data.metrics.model} · test MAPE ${formatNumber(demand.data.metrics.mape)}%` : '…'],
    ['Average auction price', latestPrice ? `LKR ${formatNumber(latestPrice.avg_price_lkr)}/kg (${formatDate(latestPrice.date)})` : price.error || 'Loading…'],
    ['Traceability ledger', ledger.data ? `${ledger.data.passports.length} batches · ${ledger.data.ledger_records} records · ${ledger.data.ledger_valid ? 'verified' : 'integrity issue'}` : ledger.error || 'Loading…'],
    ['Export Readiness Index', eri ? `${eri.score}/100 · ${eri.band} · ${eri.destination_country} (${new Date(eri.saved_at).toLocaleDateString()})` : 'Not assessed yet'],
  ]

  return (
    <Card icon="doc" title="Executive summary" description={`Generated ${new Date().toLocaleString()}`} actions={<button type="button" className="btn btn-secondary btn-sm no-print" onClick={() => window.print()}><Icon name="printer" size={15} />Print / save PDF</button>} className="print-area">
      <dl className="summary-list">{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    </Card>
  )
}

function Preview({ report }) {
  const { data, error, reload } = useApi(report.source)
  if (error) return <ErrorState compact message={error} onRetry={reload} />
  if (!data) return <LoadingState compact label="Loading report data…" />
  const rows = report.build(data)
  const columns = Object.keys(rows[0] || {})
  return (
    <>
      <p className="muted-line">{rows.length} rows · showing first {Math.min(rows.length, 12)}</p>
      <div className="table-wrap is-scroll">
        <table className="is-compact">
          <thead><tr>{columns.map((column) => <th key={column}>{column.replace(/_/g, ' ')}</th>)}</tr></thead>
          <tbody>{rows.slice(0, 12).map((row, index) => <tr key={index}>{columns.map((column) => <td key={column} title={String(row[column] ?? '')}>{typeof row[column] === 'number' ? formatNumber(row[column]) : String(row[column] ?? '').slice(0, 48)}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </>
  )
}

export default function ReportsPage() {
  const [selected, setSelected] = useState(reports[0].id)
  const [status, setStatus] = useState('')
  const eri = useLastEri()
  const report = reports.find((item) => item.id === selected)

  async function download(item, format) {
    setStatus(`Preparing ${item.title}…`)
    try {
      const data = await getJSON(item.source)
      const rows = item.build(data)
      if (format === 'json') downloadFile(`${item.id}.json`, JSON.stringify(rows, null, 2), 'application/json')
      else downloadFile(`${item.id}.csv`, toCSV(rows))
      setStatus(`Downloaded ${item.title} (${rows.length} rows).`)
    } catch (error) {
      setStatus(`Could not download ${item.title}: ${error.message}`)
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Platform · Reports"
        title="Reports"
        description="Download model outputs, market data and traceability records as CSV or JSON, or print an executive summary."
        note="Reports are generated in your browser from the live API outputs."
      />

      <ExecutiveSummary />

      <div className="reports-layout">
        <Card icon="file" title="Available reports" description="Select a report to preview it.">
          <ul className="report-list">
            {reports.map((item) => (
              <li key={item.id} className={item.id === selected ? 'active' : ''}>
                <button type="button" className="report-select" onClick={() => setSelected(item.id)} aria-pressed={item.id === selected}>
                  <span className="stat-icon tone-green"><Icon name={item.icon} size={18} /></span>
                  <span><strong>{item.title}</strong><small>{item.group} · {item.description}</small></span>
                </button>
                <div className="report-actions">
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => download(item, 'csv')} aria-label={`Download ${item.title} as CSV`}><Icon name="download" size={15} />CSV</button>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => download(item, 'json')} aria-label={`Download ${item.title} as JSON`}>JSON</button>
                </div>
              </li>
            ))}
            <li className={selected === 'eri' ? 'active' : ''}>
              <button type="button" className="report-select" onClick={() => setSelected('eri')} aria-pressed={selected === 'eri'}>
                <span className="stat-icon tone-amber"><Icon name="clipboard" size={18} /></span>
                <span><strong>Latest ERI assessment</strong><small>Readiness · {eri ? `${eri.score}/100 for ${eri.destination_country}` : 'No assessment saved yet'}</small></span>
              </button>
              <div className="report-actions">
                <button type="button" className="btn btn-ghost btn-sm" disabled={!eri} onClick={() => downloadFile('export-readiness.csv', toCSV(eriRows(eri)))}><Icon name="download" size={15} />CSV</button>
                <button type="button" className="btn btn-ghost btn-sm" disabled={!eri} onClick={() => downloadFile('export-readiness.json', JSON.stringify(eri, null, 2), 'application/json')}>JSON</button>
              </div>
            </li>
          </ul>
          {status && <p className="muted-line" role="status">{status}</p>}
        </Card>

        <Card icon="doc" title={report ? report.title : 'Latest ERI assessment'} description={report ? report.description : 'Criteria, weights and evidence from your most recent Export Readiness Index.'}
          actions={report && <button type="button" className="btn btn-primary btn-sm" onClick={() => download(report, 'csv')}><Icon name="download" size={15} />Download CSV</button>}>
          {report ? <Preview key={report.id} report={report} /> : eri ? (
            <div className="table-wrap">
              <table className="is-compact">
                <thead><tr><th>Criterion</th><th>Weight</th><th>Score</th><th>Points</th></tr></thead>
                <tbody>{eriRows(eri).map((row) => <tr key={row.criterion}><td>{row.criterion}</td><td>{row.weight_pct}%</td><td>{row.score}</td><td>{row.weighted_points}</td></tr>)}</tbody>
              </table>
            </div>
          ) : <div className="state-box is-compact"><Icon name="clipboard" size={22} /><span>No ERI assessment saved yet.</span><Link className="btn btn-ghost btn-sm" to="/export-readiness">Calculate ERI</Link></div>}
        </Card>
      </div>
    </div>
  )
}
