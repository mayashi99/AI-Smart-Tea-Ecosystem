import { useState } from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import Icon from '../../components/Icon'
import { Card, ErrorState, Link, LoadingState, ProgressBar } from '../../components/ui'
import { endpoints, postJSON, useApi } from '../../services/api'

const COLORS = ['#13724f', '#5fae7f', '#d48a1c', '#a9d8bf', '#8e6c3d']
const FACTOR_LABELS = {
  auction_price: 'Auction Price',
  export_success_rate: 'Export Success Rate',
  buyer_preference: 'Buyer Preference',
  historical_demand: 'Historical Demand',
  climate_suitability: 'Climate Suitability',
}

// Zone Quality Score engine, rendered inside the Market Analysis page.
export default function ZoneIntelligencePage() {
  const { data, error: loadError, reload } = useApi(endpoints.zoneIntelligence)
  const [zone, setZone] = useState('High Growns')
  const [climate, setClimate] = useState('')
  const [climateEvidence, setClimateEvidence] = useState('')
  const [exportSuccess, setExportSuccess] = useState('')
  const [exportEvidence, setExportEvidence] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

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
      const payload = await postJSON(endpoints.zoneScore, {
        zone,
        climate_suitability: Number(climate),
        climate_evidence: climateEvidence || null,
        export_success_rate: Number(exportSuccess),
        export_success_evidence: exportEvidence || null,
      }, 'Could not calculate the zone score')
      setResult(payload)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (loadError) return <ErrorState message={loadError} onRetry={reload} />
  if (!data) return <LoadingState label="Loading zone auction data…" />

  return (
    <>
      <section className="zone-intelligence-overview">
        <Card number="1" title="How the Zone Quality Score is calculated" description="Each factor contributes to the final score according to its weight." className="zone-weight-panel">
          <div className="zone-chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={chartData} dataKey="value" nameKey="name" innerRadius="58%" outerRadius="80%" paddingAngle={2}>
                  {chartData.map((item, index) => <Cell key={item.name} fill={COLORS[index % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(value) => `${value}%`} />
              </PieChart>
            </ResponsiveContainer>
            <div className="zone-chart-center">Zone<br />Quality<br />Score</div>
          </div>
          <div className="zone-weight-legend">{chartData.map((item, index) => <div key={item.name}><span style={{ background: COLORS[index] }} /><strong>{item.name}</strong><b>{item.value}%</b></div>)}</div>
        </Card>

        <Card number="2" title="Score a growing zone" description="Auction indicators are calculated from your supplied zone records. Add evidence for the two factors not included in those datasets." className="zone-input-panel">
          <label className="field"><span>Growing zone</span><select value={zone} onChange={(event) => { setZone(event.target.value); setResult(null) }}>{(data.zones || []).map((item) => <option key={item.zone}>{item.zone}</option>)}</select></label>
          {selectedZone && <div className="zone-observed-grid">
            <article><span>Auction price · 35%</span><strong>LKR {Number(selectedZone.auction_price_lkr).toLocaleString(undefined, { maximumFractionDigits: 2 })}/kg</strong><small>Relative score: {selectedZone.auction_price_score}/100</small></article>
            <article><span>Buyer preference proxy · 20%</span><strong>{selectedZone.buyer_preference_share_pct}%</strong><small>Share of recent auction quantity</small></article>
            <article><span>Historical demand · 10%</span><strong>{selectedZone.historical_demand_change_pct == null ? 'N/A' : `${selectedZone.historical_demand_change_pct > 0 ? '+' : ''}${selectedZone.historical_demand_change_pct}%`}</strong><small>Recent vs previous auction quantity</small></article>
          </div>}
          <form className="form-grid" onSubmit={calculate}>
            <div className="form-row">
              <label className="field"><span>Export success rate · 25% (0–100)</span><input type="number" required min="0" max="100" step="0.1" value={exportSuccess} onChange={(event) => setExportSuccess(event.target.value)} placeholder="Enter a supported rate" /></label>
              <label className="field"><span>Climate suitability · 10% (0–100)</span><input type="number" required min="0" max="100" step="0.1" value={climate} onChange={(event) => setClimate(event.target.value)} placeholder="Enter an evidence-based score" /></label>
            </div>
            <div className="form-row">
              <label className="field"><span>Export success source / period</span><input maxLength="300" value={exportEvidence} onChange={(event) => setExportEvidence(event.target.value)} placeholder="e.g. zone export records, 2021–2025" /></label>
              <label className="field"><span>Climate assessment source</span><input maxLength="300" value={climateEvidence} onChange={(event) => setClimateEvidence(event.target.value)} placeholder="e.g. estate climate suitability report" /></label>
            </div>
            <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? 'Calculating score…' : 'Calculate Zone Quality Score'}</button>
          </form>
        </Card>
      </section>

      {error && <ErrorState message={error} />}
      <p className="disclaimer">{data.data_note} Auction data through {selectedZone?.latest_period}.</p>

      {result && <>
        <section className="panel card zone-score-summary">
          <div className="mini-gauge" style={{ '--progress': `${result.quality_score}%` }}><div><strong>{result.quality_score}</strong><span>/ 100</span></div></div>
          <div><p className="eyebrow">{result.zone} · Zone Quality Score</p><h2>{result.band}</h2><p>{result.recommendation}</p></div>
          <Link className="btn btn-primary" to={`/trade-insights?${advisorQuery}`}><Icon name="globe" size={17} />Use this score in Export Advisor</Link>
        </section>
        <section className="zone-factor-grid">{result.factors.map((factor) => <article className="panel card zone-factor-card" key={factor.key}><div><span className="eyebrow">{factor.weight}% weight</span><h3>{factor.label}</h3></div><strong>{Number(factor.score).toFixed(1)}<small>/100</small></strong><p>{factor.value}</p><small>{factor.source}</small><ProgressBar value={factor.score} /></article>)}</section>
      </>}
    </>
  )
}
