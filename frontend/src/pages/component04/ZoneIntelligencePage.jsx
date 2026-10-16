import { useEffect, useState } from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

const COLORS = ['#315b40', '#7fa37b', '#c9953f', '#a9c7a6', '#927044']
const FACTOR_LABELS = {
  auction_price: 'Auction Price',
  export_success_rate: 'Export Success Rate',
  buyer_preference: 'Buyer Preference',
  historical_demand: 'Historical Demand',
  climate_suitability: 'Climate Suitability',
}

export default function ZoneIntelligencePage() {
  const [data, setData] = useState(null)
  const [zone, setZone] = useState('High Growns')
  const [climate, setClimate] = useState('')
  const [climateEvidence, setClimateEvidence] = useState('')
  const [exportSuccess, setExportSuccess] = useState('')
  const [exportEvidence, setExportEvidence] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/component04/zone-intelligence')
      .then(async (response) => {
        const payload = await response.json()
        if (!response.ok) throw new Error(payload.detail || 'Could not load zone data')
        setData(payload)
      })
      .catch((err) => setError(err.message))
  }, [])

  const selectedZone = data?.zones.find((item) => item.zone === zone)
  const weights = data?.weights || {}
  const chartData = Object.entries(weights).map(([key, value]) => ({ name: FACTOR_LABELS[key], value }))
  const advisorQuery = result ? new URLSearchParams({
    zone: result.zone,
    climate_suitability: String(climate),
    export_success_rate: String(exportSuccess),
  }).toString() : ''

  async function calculate(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const response = await fetch('/api/component04/zone-intelligence/score', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          zone,
          climate_suitability: Number(climate),
          climate_evidence: climateEvidence || null,
          export_success_rate: Number(exportSuccess),
          export_success_evidence: exportEvidence || null,
        }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'Could not calculate the zone score')
      setResult(payload)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="dashboard">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Component 04 · Zone Intelligence Engine</p>
          <h1>Zone Quality Score</h1>
          <p className="subtle">Compare tea growing zones using auction value, market demand and clearly sourced readiness factors.</p>
        </div>
      </header>

      {error && <section className="panel advisor-error" role="alert">{error}</section>}
      {!data ? <section className="panel">Loading zone auction data…</section> : <>
        <section className="zone-intelligence-overview">
          <article className="panel zone-weight-panel">
            <div className="panel-heading"><h2>How the Zone Quality Score is calculated</h2><p>Each factor contributes to the final score according to its weight.</p></div>
            <div className="zone-chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={chartData} dataKey="value" nameKey="name" innerRadius="56%" outerRadius="78%" paddingAngle={2}>
                    {chartData.map((item, index) => <Cell key={item.name} fill={COLORS[index % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(value) => `${value}%`} />
                </PieChart>
              </ResponsiveContainer>
              <div className="zone-chart-center">Zone<br />Quality<br />Score</div>
            </div>
            <div className="zone-weight-legend">{chartData.map((item, index) => <div key={item.name}><span style={{ background: COLORS[index] }} /><strong>{item.name}</strong><b>{item.value}%</b></div>)}</div>
          </article>

          <article className="panel zone-input-panel">
            <div className="panel-heading"><h2>Score a growing zone</h2><p>Auction indicators are calculated from your supplied zone records. Add evidence for the two factors not included in those datasets.</p></div>
            <label className="zone-score-field"><span>Growing zone</span><select value={zone} onChange={(event) => { setZone(event.target.value); setResult(null) }}>{(data.zones || []).map((item) => <option key={item.zone}>{item.zone}</option>)}</select></label>
            {selectedZone && <div className="zone-observed-grid">
              <article><span>Auction price · 35%</span><strong>LKR {Number(selectedZone.auction_price_lkr).toLocaleString(undefined, { maximumFractionDigits: 2 })}/kg</strong><small>Relative score: {selectedZone.auction_price_score}/100</small></article>
              <article><span>Buyer preference proxy · 20%</span><strong>{selectedZone.buyer_preference_share_pct}%</strong><small>Share of recent auction quantity</small></article>
              <article><span>Historical demand · 10%</span><strong>{selectedZone.historical_demand_change_pct == null ? 'N/A' : `${selectedZone.historical_demand_change_pct > 0 ? '+' : ''}${selectedZone.historical_demand_change_pct}%`}</strong><small>Recent vs previous auction quantity</small></article>
            </div>}
            <form className="advisor-form zone-score-form" onSubmit={calculate}>
              <div className="advisor-input-row">
                <label><span>Export success rate · 25% (0–100)</span><input type="number" required min="0" max="100" step="0.1" value={exportSuccess} onChange={(event) => setExportSuccess(event.target.value)} placeholder="Enter a supported rate" /></label>
                <label><span>Climate suitability · 10% (0–100)</span><input type="number" required min="0" max="100" step="0.1" value={climate} onChange={(event) => setClimate(event.target.value)} placeholder="Enter an evidence-based score" /></label>
              </div>
              <div className="advisor-input-row">
                <label><span>Export success source / period</span><input maxLength="300" value={exportEvidence} onChange={(event) => setExportEvidence(event.target.value)} placeholder="e.g. zone export records, 2021–2025" /></label>
                <label><span>Climate assessment source</span><input maxLength="300" value={climateEvidence} onChange={(event) => setClimateEvidence(event.target.value)} placeholder="e.g. estate climate suitability report" /></label>
              </div>
              <button className="advisor-submit" type="submit" disabled={busy}>{busy ? 'Calculating score…' : 'Calculate Zone Quality Score'}</button>
            </form>
          </article>
        </section>

        <p className="advisor-note zone-data-note">{data.data_note} Auction data through {selectedZone?.latest_period}.</p>

        {result && <>
          <section className="panel zone-score-summary"><div><p className="eyebrow">{result.zone} · Zone Quality Score</p><h2>{result.band}</h2><p>{result.recommendation}</p></div><strong>{result.quality_score}<small>/100</small></strong></section>
          <section className="zone-factor-grid">{result.factors.map((factor) => <article className="panel zone-factor-card" key={factor.key}><div><span className="eyebrow">{factor.weight}% weight</span><h3>{factor.label}</h3></div><strong>{Number(factor.score).toFixed(1)}<small>/100</small></strong><p>{factor.value}</p><small>{factor.source}</small><div className="zone-score-bar"><span style={{ width: `${Math.max(0, Math.min(100, factor.score))}%` }} /></div></article>)}</section>
          <a className="passport-qr-download zone-advisor-link" href={`/export-advisor?${advisorQuery}`}>Use this score in Export Advisor</a>
        </>}
      </>}
    </main>
  )
}
