import { useState } from 'react'

const documentLabels = {
  business_registration: 'Business registration',
  tea_board_registration: 'Tea Board registration',
  quality_certificate: 'Quality certificate',
  origin_certificate: 'Certificate of origin',
  shipment_plan: 'Shipment plan',
}

export default function ExportReadinessPage() {
  const [capacity, setCapacity] = useState('10')
  const [country, setCountry] = useState('')
  const [documents, setDocuments] = useState(Object.fromEntries(Object.keys(documentLabels).map((key) => [key, false])))
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

  return (
    <main className="dashboard">
      <header className="dashboard-header"><div><p className="eyebrow">Component 04 · Readiness</p><h1>Export Readiness Index</h1><p className="subtle">An explainable readiness score combining export-demand evidence with your declared capacity and preparation status.</p></div></header>
      <section className="panel advisor-form-panel">
        <form className="advisor-form" onSubmit={calculate}>
          <div className="advisor-input-row">
            <label><span>Destination market (optional)</span><input value={country} onChange={(event) => setCountry(event.target.value)} placeholder="e.g. Japan" maxLength={100} /></label>
            <label><span>Monthly supply capacity (tonnes)</span><input type="number" min="0.1" step="0.1" required value={capacity} onChange={(event) => setCapacity(event.target.value)} /></label>
          </div>
          <fieldset className="eri-checklist"><legend>Document readiness</legend>{Object.entries(documentLabels).map(([key, label]) => <label className="eri-check" key={key}><input type="checkbox" checked={documents[key]} onChange={(event) => setDocuments({ ...documents, [key]: event.target.checked })} /><span>{label}</span></label>)}</fieldset>
          <label className="eri-check"><input type="checkbox" checked={qualityReady} onChange={(event) => setQualityReady(event.target.checked)} /><span>Batch quality controls and inspection records are ready</span></label>
          <button className="advisor-submit" type="submit" disabled={busy}>{busy ? 'Calculating…' : 'Calculate explainable ERI'}</button>
        </form>
        <p className="advisor-note">This planning index is not an official certification or destination-specific regulatory assessment. Readiness inputs are self-declared.</p>
      </section>
      {error && <section className="empty-state advisor-error" role="alert">{error}</section>}
      {result && <>
        <section className="panel eri-result"><div><p className="eyebrow">{result.index_name}</p><h2>{result.band}</h2><p>{result.method_note}</p></div><strong className="eri-score">{result.score}<small>/100</small></strong></section>
        <section className="metric-grid eri-criteria">{result.criteria.map((item) => <article className="metric-card" key={item.key}><span>{item.label} · {item.weight}%</span><strong>{Math.round(item.score)}%</strong><p>{item.evidence}</p></article>)}</section>
        <section className="panel"><div className="panel-heading"><h2>Recommended actions</h2><p>Each action is tied to the score evidence above.</p></div><div className="evidence-list">{result.recommendations.map((item, index) => <article className="evidence-item" key={`${item.criterion}-${index}`}><h3>{item.criterion}</h3><p>{item.action}</p><small>{item.evidence}</small></article>)}</div></section>
        <section className="panel"><h2>Demand forecast context</h2><p>{result.forecast_context.model} · holdout MAPE {result.forecast_context.holdout_mape_pct.toFixed(2)}% · 12-month outlook change {result.forecast_context.forecast_change_pct.toFixed(1)}%</p></section>
      </>}
    </main>
  )
}
