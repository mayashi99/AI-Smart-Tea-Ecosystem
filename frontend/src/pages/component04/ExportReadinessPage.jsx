import { useState } from 'react'

const documentLabels = {
  business_registration: 'Business registration',
  tea_board_registration: 'Tea Board registration',
  quality_certificate: 'Required quality certificates',
  origin_certificate: 'Certificate of origin',
  shipment_plan: 'Shipment plan',
}

const countries = [
  ['Japan', '🇯🇵'], ['United States', '🇺🇸'], ['United Kingdom', '🇬🇧'],
  ['Germany', '🇩🇪'], ['United Arab Emirates', '🇦🇪'], ['Australia', '🇦🇺'],
]

function StepHeading({ number, title, description }) {
  return <div className="eri-step-heading"><span className="eri-step-number">{number}</span><div><h2>{title}</h2><p>{description}</p></div></div>
}

export default function ExportReadinessPage() {
  const [capacity, setCapacity] = useState('10')
  const [country, setCountry] = useState('Japan')
  const [teaType, setTeaType] = useState('Black Tea')
  const [forecastPeriod, setForecastPeriod] = useState('Next 3 months')
  const [documents, setDocuments] = useState({ business_registration: true, tea_board_registration: true, quality_certificate: false, origin_certificate: false, shipment_plan: true })
  const [qualityReady, setQualityReady] = useState(false)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function calculate(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const response = await fetch('/api/component04/export-readiness', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ destination_country: country || null, monthly_capacity_tonnes: Number(capacity), documents, quality_controls_ready: qualityReady }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'Could not calculate ERI')
      setResult(payload)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

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

  return (
    <main className="dashboard eri-dashboard">
      <header className="eri-hero">
        <div className="eri-hero-copy"><p className="eyebrow">Component 04 · Export intelligence</p><h1>Export Readiness Index</h1><p>An explainable readiness score combining export-demand evidence with your declared capacity and preparation status.</p></div>
        <aside className="eri-info-note"><span aria-hidden="true">ⓘ</span><p>This is a planning index, not an official certification or regulatory assessment.</p></aside>
      </header>

      <form onSubmit={calculate}>
        <div className="eri-top-grid">
          <div className="eri-left-stack">
            <section className="panel eri-section eri-input-section">
              <StepHeading number="1" title="Export Planning Inputs" description="Select a destination and provide your supply capacity details." />
              <div className="eri-input-grid">
                <label><span>Destination market</span><select value={country} onChange={(event) => setCountry(event.target.value)}><option value="">Select a market</option>{countries.map(([name, flag]) => <option key={name} value={name}>{flag}　{name}</option>)}</select></label>
                <label><span>Tea type / grade</span><select value={teaType} onChange={(event) => setTeaType(event.target.value)}>{['Black Tea', 'Green Tea', 'White Tea', 'Oolong Tea'].map((tea) => <option key={tea}>{tea}</option>)}</select></label>
                <label><span>Monthly supply capacity (tonnes)</span><div className="eri-input-suffix"><input type="number" min="0.1" step="0.1" required value={capacity} onChange={(event) => setCapacity(event.target.value)} /><span>tonnes</span></div></label>
                <label><span>Forecast period</span><select value={forecastPeriod} onChange={(event) => setForecastPeriod(event.target.value)}>{['Next 3 months', 'Next 6 months', 'Next 12 months'].map((period) => <option key={period}>{period}</option>)}</select></label>
              </div>
            </section>

            <section className="panel eri-section eri-demand-section">
              <StepHeading number="2" title="ML-based Demand Forecast" description={`Forecasted tea demand${country ? ` for ${country}` : ''} using the national historical export model.`} />
              {result ? <div className="eri-forecast-content"><article className="eri-demand-highlight"><span className="eri-highlight-icon" aria-hidden="true">▥</span><div><span>Forecasted annual export volume</span><strong>{Number(result.forecast_context.forecast_12_months_kg / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 })} tonnes</strong><small className={result.forecast_context.forecast_change_pct >= 0 ? 'eri-positive' : 'eri-negative'}>{result.forecast_context.forecast_change_pct >= 0 ? '↑' : '↓'} {Math.abs(result.forecast_context.forecast_change_pct).toFixed(1)}% <span>vs latest 12 observed months</span></small></div></article><article className="eri-forecast-evidence"><h3>Export demand forecast context</h3><div className="eri-context-bars"><div><span>Latest 12 months</span><i><b style={{ width: `${Math.min(100, result.forecast_context.latest_12_months_actual_kg / Math.max(result.forecast_context.latest_12_months_actual_kg, result.forecast_context.forecast_12_months_kg) * 100)}%` }} /></i><strong>{(result.forecast_context.latest_12_months_actual_kg / 1e6).toFixed(2)}M kg</strong></div><div><span>Next 12 month forecast</span><i><b style={{ width: `${Math.min(100, result.forecast_context.forecast_12_months_kg / Math.max(result.forecast_context.latest_12_months_actual_kg, result.forecast_context.forecast_12_months_kg) * 100)}%` }} /></i><strong>{(result.forecast_context.forecast_12_months_kg / 1e6).toFixed(2)}M kg</strong></div></div><small>{result.forecast_context.model} · holdout MAPE {result.forecast_context.holdout_mape_pct.toFixed(2)}% · national aggregate</small></article></div> : <div className="eri-forecast-placeholder"><span aria-hidden="true">▥</span><div><strong>Run the readiness check to load forecast evidence</strong><p>Demand figures come from the trained national export forecast model.</p></div></div>}
            </section>
          </div>

          <section className="panel eri-section eri-documents-section">
            <StepHeading number="3" title="Document & Quality Readiness" description="Mark the status of required documents and quality preparations." />
            <div className="eri-doc-header"><span>Required document</span><span>Status</span></div>
            <div className="eri-document-list">{Object.entries(documentLabels).map(([key, label]) => <label className="eri-document-row" key={key}><input type="checkbox" checked={documents[key]} onChange={(event) => setDocuments({ ...documents, [key]: event.target.checked })} /><span className="eri-checkbox-mark" aria-hidden="true" /><span className="eri-document-name">{label}</span><span className={`eri-status-pill ${documents[key] ? 'is-ready' : 'is-missing'}`}>{documents[key] ? 'Ready' : 'Not ready'}</span></label>)}</div>
            <label className="eri-quality-row"><input type="checkbox" checked={qualityReady} onChange={(event) => setQualityReady(event.target.checked)} /><span className="eri-checkbox-mark" aria-hidden="true" /><span className="eri-document-name">Batch quality controls and inspection records are ready</span><span className={`eri-status-pill ${qualityReady ? 'is-ready' : 'is-missing'}`}>{qualityReady ? 'Ready' : 'Not ready'}</span></label>
            <div className="eri-readiness-count"><span>Documents marked ready</span><strong>{readyDocs} / {Object.keys(documentLabels).length}</strong></div>
          </section>
        </div>

        <section className="panel eri-section eri-results-section">
          <div className="eri-results-main">
            <StepHeading number="4" title="Export Readiness Index (ERI)" description="Calculated using demand forecast, supply capacity, document readiness and quality status." />
            <div className="eri-score-layout">
              <div className="eri-gauge-column"><div className="eri-gauge" style={{ '--eri-progress': `${result?.score ?? 0}%` }}><div><strong>{result?.score ?? '—'}</strong><span>/ 100</span></div></div><div className={`eri-verdict ${result?.score >= 80 ? 'is-ready' : ''}`}><strong>{result ? scoreState : 'Ready to assess'}</strong><span>{result ? `${result.band} · ${result.destination_country}` : 'Add your preparation details and calculate your score.'}</span></div></div>
              <div className="eri-breakdown"><h3>Score breakdown</h3>{criteria.length ? criteria.map((item) => <div className="eri-breakdown-row" key={item.key}><span className="eri-breakdown-icon" aria-hidden="true">{item.key === 'demand_outlook' || item.key === 'forecast_confidence' ? '▥' : item.key === 'supply_capacity' ? '▦' : item.key === 'documentation' ? '▤' : '✓'}</span><div className="eri-breakdown-detail"><div><span>{item.label} ({item.weight}%)</span><strong>{weightedScore(item.key)} / {item.weight}</strong></div><i><b style={{ width: `${Math.max(0, Math.min(100, item.score))}%` }} /></i><small>{item.evidence}</small></div></div>) : <p className="eri-breakdown-empty">Your score criteria and supporting evidence will appear here.</p>}</div>
            </div>
          </div>
          <aside className="eri-insights-column"><div className="eri-critical-card"><div className="eri-insight-title"><span aria-hidden="true">⚠</span><div><h3>Critical requirements</h3><p>{unmetRequirements.length ? 'Complete these items before export:' : 'All declared requirements are ready.'}</p></div></div>{unmetRequirements.length ? <ul>{unmetRequirements.slice(0, 4).map((item) => <li key={item}>{item}</li>)}</ul> : <p className="eri-all-clear">Your documents and quality checklist are marked ready.</p>}</div><div className="eri-recommendations-card"><div className="eri-insight-title"><span aria-hidden="true">✦</span><div><h3>Recommendations</h3><p>Practical next steps based on your readiness.</p></div></div>{result ? <ol>{result.recommendations.map((item, index) => <li key={`${item.criterion}-${index}`}><strong>{item.criterion}:</strong> {item.action}</li>)}</ol> : <ol><li>Complete the document and quality checklist.</li><li>Confirm supply capacity for your target market.</li><li>Calculate ERI to see evidence-based next steps.</li></ol>}</div><button className="eri-calculate-button" type="submit" disabled={busy}>{busy ? 'Calculating readiness…' : 'Calculate export readiness'}</button></aside>
        </section>
      </form>
      {error && <section className="empty-state advisor-error" role="alert">{error}</section>}
      <p className="eri-disclaimer">Planning aid only. Inputs are self-declared and do not replace official certification or destination-specific regulatory advice.</p>
    </main>
  )
}
