import { useMemo, useState } from 'react'
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import Icon from '../../components/Icon'
import { Link, PageHeader, StepHeading } from '../../components/ui'
import { chartTheme } from '../../lib/chartTheme'
import { formatCompact, formatMonth, formatNumber, pctChange, sum } from '../../lib/format'
import { markets, saveLastEri, teaTypes, useSettings } from '../../lib/settings'
import { endpoints, postJSON, useApi } from '../../services/api'

const documentLabels = {
  business_registration: 'Business registration',
  tea_board_registration: 'Tea Board registration',
  quality_certificate: 'Required quality certificates',
  origin_certificate: 'Certificate of origin',
  shipment_plan: 'Shipment plan',
}

const periods = { 'Next 3 months': 3, 'Next 6 months': 6, 'Next 12 months': 12 }

const criterionIcon = (key) => (key === 'demand_outlook' || key === 'forecast_confidence' ? 'bars' : key === 'supply_capacity' ? 'factory' : key === 'documentation' ? 'doc' : 'shield')

export default function ExportReadinessPage() {
  const settings = useSettings()
  const [capacity, setCapacity] = useState(String(settings.defaultCapacity))
  const [country, setCountry] = useState(settings.defaultMarket)
  const [teaType, setTeaType] = useState(settings.defaultTeaType)
  const [forecastPeriod, setForecastPeriod] = useState('Next 3 months')
  const [documents, setDocuments] = useState({ business_registration: true, tea_board_registration: true, quality_certificate: false, origin_certificate: false, shipment_plan: true })
  const [qualityReady, setQualityReady] = useState(false)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const demand = useApi(endpoints.exportDemand)

  async function calculate(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = await postJSON(endpoints.exportReadiness, { destination_country: country || null, monthly_capacity_tonnes: Number(capacity), documents, quality_controls_ready: qualityReady }, 'Could not calculate ERI')
      setResult(payload)
      saveLastEri(payload, { capacity: Number(capacity), teaType, forecastPeriod, documents, qualityReady })
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  // Forecast evidence for step 2, sized to the selected forecast period.
  const forecastView = useMemo(() => {
    if (!demand.data) return null
    const months = periods[forecastPeriod]
    const history = demand.data.history || []
    const forecast = (demand.data.forecast || []).slice(0, months)
    const previous = history.slice(-months)
    const monthlyAvg = sum(forecast, 'forecast_export_volume_kg') / Math.max(1, forecast.length) / 1000
    const previousAvg = sum(previous, 'export_volume_kg') / Math.max(1, previous.length) / 1000
    const recent = history.slice(-6)
    const chart = [
      ...recent.map((row, index) => ({ month: formatMonth(row.date), historical: row.export_volume_kg / 1000, forecast: index === recent.length - 1 ? row.export_volume_kg / 1000 : null })),
      ...forecast.map((row) => ({ month: formatMonth(row.date), historical: null, forecast: row.forecast_export_volume_kg / 1000 })),
    ]
    return { months, monthlyAvg, change: pctChange(monthlyAvg, previousAvg), chart }
  }, [demand.data, forecastPeriod])

  const criteria = result?.criteria || []
  const readyDocs = Object.values(documents).filter(Boolean).length
  const scoreState = result?.score >= 80 ? 'Ready to export' : result?.score >= 60 ? 'Almost ready' : 'Verification required'
  const unmetRequirements = [
    ...Object.entries(documents).filter(([, ready]) => !ready).map(([key]) => documentLabels[key]),
    ...(!qualityReady ? ['Batch quality controls and inspection records'] : []),
  ]
  const weightedScore = (key) => {
    const item = criteria.find((criterion) => criterion.key === key)
    return item ? Math.round(item.score * item.weight / 100 * 10) / 10 : 0
  }
  const capacityShare = forecastView && Number(capacity) > 0 ? (Number(capacity) / forecastView.monthlyAvg) * 100 : null

  const sidebarItems = [
    { label: 'Dashboard', active: false, icon: '⌂' },
    { label: 'Market Analysis', active: false, icon: '▤' },
    { label: 'Demand Forecast', active: false, icon: '↗' },
    { label: 'Export Readiness', active: true, icon: '▣' },
    { label: 'Trade Insights', active: false, icon: '◌' },
    { label: 'Reports', active: false, icon: '▣' },
    { label: 'Settings', active: false, icon: '⚙' },
  ]

  return (
    <div className="page-stack eri-page">
      <PageHeader
        eyebrow="Component 04 · Export intelligence"
        title="Export Readiness Index"
        description="An explainable readiness score combining export-demand evidence with your declared capacity and preparation status."
        note="This is a planning index, not an official certification or regulatory assessment."
      />

      <form onSubmit={calculate} className="page-stack">
        <div className="eri-top-grid">
          <div className="eri-left-stack">
            <section className="panel card eri-input-section">
              <StepHeading number="1" title="Export Planning Inputs" description="Select a destination and provide your supply capacity details." />
              <div className="eri-input-grid">
                <label className="field"><span>Destination market</span><select value={country} onChange={(event) => setCountry(event.target.value)}><option value="">Select a market</option>{markets.map(([name, flag]) => <option key={name} value={name}>{flag} {name}</option>)}</select></label>
                <label className="field"><span>Tea type / grade</span><select value={teaType} onChange={(event) => setTeaType(event.target.value)}>{teaTypes.map((tea) => <option key={tea}>{tea}</option>)}</select></label>
                <label className="field"><span>Monthly supply capacity (tonnes)</span><div className="input-suffix"><input type="number" min="0.1" step="0.1" required value={capacity} onChange={(event) => setCapacity(event.target.value)} /><span>tonnes</span></div></label>
                <label className="field"><span>Forecast period</span><select value={forecastPeriod} onChange={(event) => setForecastPeriod(event.target.value)}>{Object.keys(periods).map((period) => <option key={period}>{period}</option>)}</select></label>
              </div>
            </section>

            <section className="panel card eri-demand-section">
              <StepHeading number="2" title="ML-based Demand Forecast" description={`Forecasted tea demand${country ? ` for the ${country} plan` : ''} using the national historical export model.`} />
              {demand.error ? (
                <div className="eri-forecast-placeholder"><Icon name="alert" size={28} /><div><strong>Forecast evidence unavailable</strong><p>{demand.error}</p></div></div>
              ) : !forecastView ? (
                <div className="eri-forecast-placeholder"><span className="spinner" aria-hidden="true" /><div><strong>Loading forecast evidence…</strong><p>Demand figures come from the trained national export forecast model.</p></div></div>
              ) : (
                <div className="eri-forecast-content">
                  <article className="eri-demand-highlight">
                    <span className="eri-highlight-icon"><Icon name="bars" size={30} /></span>
                    <div>
                      <span>Forecasted monthly demand</span>
                      <strong>{formatNumber(forecastView.monthlyAvg, 0)} tonnes</strong>
                      <small className={forecastView.change >= 0 ? 'eri-positive' : 'eri-negative'}><Icon name={forecastView.change >= 0 ? 'arrowUp' : 'arrowDown'} size={14} strokeWidth={2.6} /> {Math.abs(forecastView.change).toFixed(1)}% <span>vs previous {forecastView.months} months</span></small>
                      {capacityShare != null && <em>Your capacity ≈ {capacityShare < 0.01 ? '<0.01' : formatNumber(capacityShare, 2)}% of national monthly demand</em>}
                    </div>
                  </article>
                  <article className="eri-forecast-evidence">
                    <h3>Historical export demand &amp; forecast{country ? ` (${country} plan)` : ''}</h3>
                    <div className="chart-box is-mini">
                      <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={forecastView.chart} margin={{ top: 4, right: 6, left: -8, bottom: 0 }}>
                          <CartesianGrid stroke={chartTheme.grid} vertical={false} />
                          <XAxis dataKey="month" tick={{ fontSize: 10 }} stroke={chartTheme.axis} interval={0} />
                          <YAxis tick={{ fontSize: 10 }} stroke={chartTheme.axis} tickFormatter={formatCompact} width={40} />
                          <Tooltip formatter={(value) => `${formatNumber(value, 0)} t`} />
                          <Legend iconType="circle" verticalAlign="top" align="right" height={22} wrapperStyle={{ fontSize: 11 }} />
                          <Bar dataKey="historical" name="Historical" fill={chartTheme.primary} radius={[3, 3, 0, 0]} maxBarSize={16} />
                          <Line dataKey="forecast" name="Forecast" stroke={chartTheme.primary} strokeDasharray="4 3" strokeWidth={2} dot={{ r: 3, fill: '#fff', strokeWidth: 2 }} />
                        </ComposedChart>
                      </ResponsiveContainer>
                    </div>
                    <small>{demand.data.metrics?.model} · holdout MAPE {formatNumber(demand.data.metrics?.mape)}% · national aggregate, tonnes</small>
                    {result && <small className="eri-result-context">ERI evidence: next 12 months {(result.forecast_context.forecast_12_months_kg / 1e6).toFixed(2)}M kg vs latest 12 months {(result.forecast_context.latest_12_months_actual_kg / 1e6).toFixed(2)}M kg ({result.forecast_context.forecast_change_pct >= 0 ? '+' : ''}{result.forecast_context.forecast_change_pct.toFixed(1)}%)</small>}
                  </article>
                </div>
              )}
            </section>
          </div>

          <section className="panel card eri-documents-section">
            <StepHeading number="3" title="Document & Quality Readiness" description="Mark the status of required documents and quality preparations." />
            <div className="eri-doc-header"><span>Required document</span><span>Status</span></div>
            <div className="eri-document-list">{Object.entries(documentLabels).map(([key, label]) => <label className="eri-document-row" key={key}><input type="checkbox" checked={documents[key]} onChange={(event) => setDocuments({ ...documents, [key]: event.target.checked })} /><span className="eri-checkbox-mark" aria-hidden="true" /><span className="eri-document-name">{label}</span><span className={`status-pill ${documents[key] ? 'is-ready' : 'is-missing'}`}>{documents[key] ? 'Ready' : 'Not ready'}</span></label>)}</div>
            <label className="eri-quality-row"><input type="checkbox" checked={qualityReady} onChange={(event) => setQualityReady(event.target.checked)} /><span className="eri-checkbox-mark" aria-hidden="true" /><span className="eri-document-name">Batch quality controls and inspection records are ready</span><span className={`status-pill ${qualityReady ? 'is-ready' : 'is-missing'}`}>{qualityReady ? 'Ready' : 'Not ready'}</span></label>
            <div className="eri-readiness-count"><span>Documents marked ready</span><strong>{readyDocs} / {Object.keys(documentLabels).length}</strong></div>
          </section>
        </div>

        <section className="panel card eri-results-section">
          <div className="eri-results-main">
            <StepHeading number="4" title="Export Readiness Index (ERI)" description="Calculated using demand forecast, supply capacity, document readiness and quality status." />
            <div className="eri-score-layout">
              <div className="eri-gauge-column">
                <div className="eri-gauge" style={{ '--eri-progress': `${result?.score ?? 0}%` }}><div><strong>{result?.score ?? '—'}</strong><span>/ 100</span></div></div>
                <div className={`verdict ${result?.score >= 80 ? 'is-ready' : ''}`}><strong>{result ? scoreState : 'Ready to assess'}</strong><span>{result ? `${result.band} · ${result.destination_country}` : 'Add your preparation details and calculate your score.'}</span></div>
              </div>
              <div className="eri-breakdown">
                <h3>Score breakdown</h3>
                {criteria.length ? criteria.map((item) => (
                  <div className="eri-breakdown-row" key={item.key}>
                    <span className="eri-breakdown-icon"><Icon name={criterionIcon(item.key)} size={18} /></span>
                    <div className="eri-breakdown-detail">
                      <div><span>{item.label} ({item.weight}%)</span><strong>{weightedScore(item.key)} / {item.weight}</strong></div>
                      <i><b style={{ width: `${Math.max(0, Math.min(100, item.score))}%` }} /></i>
                      <small>{item.evidence}</small>
                    </div>
                  </div>
                )) : <p className="eri-breakdown-empty">Your score criteria and supporting evidence will appear here.</p>}
              </div>
            </div>
          </div>
          <aside className="eri-insights-column">
            <div className="eri-critical-card">
              <div className="eri-insight-title"><Icon name="alert" size={26} /><div><h3>Critical requirements</h3><p>{unmetRequirements.length ? 'Complete these items before export:' : 'All declared requirements are ready.'}</p></div></div>
              {unmetRequirements.length ? <ul>{unmetRequirements.slice(0, 4).map((item) => <li key={item}>{item}</li>)}</ul> : <p className="eri-all-clear">Your documents and quality checklist are marked ready.</p>}
            </div>
            <div className="eri-recommendations-card">
              <div className="eri-insight-title"><Icon name="bulb" size={26} /><div><h3>Recommendations</h3><p>Practical next steps based on your readiness.</p></div></div>
              {result ? <ol>{result.recommendations.map((item, index) => <li key={`${item.criterion}-${index}`}><strong>{item.criterion}:</strong> {item.action}</li>)}</ol> : <ol><li>Complete the document and quality checklist.</li><li>Confirm supply capacity for your target market.</li><li>Calculate ERI to see evidence-based next steps.</li></ol>}
            </div>
            <div className="button-row">
              <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? 'Calculating readiness…' : 'Calculate export readiness'}</button>
              {result && <Link className="btn btn-secondary" to="/reports">View in reports</Link>}
            </div>
          </aside>
        </section>
      </form>
      {error && <div className="state-box is-error" role="alert"><Icon name="alert" size={22} /><span>{error}</span></div>}
      <p className="disclaimer">Planning aid only. Inputs are self-declared and do not replace official certification or destination-specific regulatory advice. Tea type is recorded with your assessment for reference; the current demand model is a national aggregate across tea types.</p>
    </div>
  )
}
