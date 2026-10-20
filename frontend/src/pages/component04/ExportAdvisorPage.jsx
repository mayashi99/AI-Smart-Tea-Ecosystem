import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import Icon from '../../components/Icon'
import { Card, ErrorState, LoadingState, PageHeader } from '../../components/ui'
import { chartTheme } from '../../lib/chartTheme'
import { formatCompact, formatNumber, pctChange } from '../../lib/format'
import { useSettings } from '../../lib/settings'
import { endpoints, postJSON, useApi } from '../../services/api'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const suggestions = [
  'How should we plan export volumes for the next 12 months?',
  'Which months should we build inventory ahead of peak demand?',
  'How reliable is the demand forecast for shipment planning?',
  'How should a High Grown seller prioritise export markets?',
]

function readZoneContext() {
  const zoneParams = new URLSearchParams(window.location.search)
  return zoneParams.has('zone') ? {
    zone: zoneParams.get('zone'),
    climate_suitability: Number(zoneParams.get('climate_suitability')),
    export_success_rate: Number(zoneParams.get('export_success_rate')),
  } : {}
}

function Seasonality() {
  const { data, error, reload } = useApi(endpoints.exportDemand)
  const view = useMemo(() => {
    if (!data) return null
    const history = data.history || []
    const recent = history.slice(-60)
    const byMonth = MONTHS.map((month) => ({ month, total: 0, count: 0 }))
    recent.forEach((row) => {
      const bucket = byMonth[new Date(row.date).getUTCMonth()]
      bucket.total += row.export_volume_kg
      bucket.count += 1
    })
    const seasonal = byMonth.map((bucket) => ({ month: bucket.month, tonnes: bucket.count ? bucket.total / bucket.count / 1000 : 0 }))
    const mean = seasonal.reduce((total, row) => total + row.tonnes, 0) / 12
    const ranked = [...seasonal].sort((a, b) => b.tonnes - a.tonnes)
    const years = new Map()
    history.forEach((row) => {
      const year = new Date(row.date).getUTCFullYear()
      years.set(year, (years.get(year) || 0) + row.export_volume_kg)
    })
    const annual = [...years.entries()].map(([year, kg]) => ({ year: String(year), tonnes: kg / 1000 }))
    const latest = annual.at(-1)
    const prior = annual.at(-2)
    return { seasonal, mean, peaks: ranked.slice(0, 3).map((row) => row.month), lows: ranked.slice(-2).map((row) => row.month), annual, yoy: latest && prior ? pctChange(latest.tonnes, prior.tonnes) : null, latestYear: latest?.year }
  }, [data])

  if (error) return <ErrorState message={error} onRetry={reload} />
  if (!view) return <LoadingState label="Loading trade history…" />

  return (
    <>
      <section className="insight-grid">
        <article className="insight-card panel"><span className="stat-icon tone-green"><Icon name="trend" size={20} /></span><div><strong>Peak export months</strong><p>{view.peaks.join(', ')} have the highest average volumes over the last 5 years — plan inventory and shipping space ahead of them.</p></div></article>
        <article className="insight-card panel"><span className="stat-icon tone-amber"><Icon name="arrowDown" size={20} /></span><div><strong>Softer months</strong><p>{view.lows.join(' and ')} are typically the lowest-volume months; useful for maintenance, certification renewals and buyer visits.</p></div></article>
        <article className="insight-card panel"><span className="stat-icon tone-blue"><Icon name="bars" size={20} /></span><div><strong>{view.latestYear} vs prior year</strong><p>National export volume {view.yoy >= 0 ? 'grew' : 'fell'} {formatNumber(Math.abs(view.yoy), 1)}% year on year ({formatCompact(view.annual.at(-1).tonnes)} t).</p></div></article>
      </section>
      <div className="grid-2">
        <Card icon="bars" title="Seasonal export pattern" description="Average monthly export volume over the last 5 years (tonnes). Highlighted bars are above average.">
          <div className="chart-box is-short">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={view.seasonal} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={chartTheme.grid} vertical={false} />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} stroke={chartTheme.axis} interval={0} />
                <YAxis tick={{ fontSize: 11 }} stroke={chartTheme.axis} tickFormatter={formatCompact} width={46} />
                <Tooltip formatter={(value) => `${formatNumber(value, 0)} t`} />
                <Bar dataKey="tonnes" name="Average volume" radius={[4, 4, 0, 0]} maxBarSize={28}>
                  {view.seasonal.map((row) => <Cell key={row.month} fill={row.tonnes >= view.mean ? chartTheme.primary : chartTheme.primarySoft} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card icon="trend" title="Annual export volume" description="Total national export volume per calendar year (tonnes).">
          <div className="chart-box is-short">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={view.annual} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={chartTheme.grid} vertical={false} />
                <XAxis dataKey="year" tick={{ fontSize: 11 }} stroke={chartTheme.axis} />
                <YAxis tick={{ fontSize: 11 }} stroke={chartTheme.axis} tickFormatter={formatCompact} width={46} />
                <Tooltip formatter={(value) => `${formatNumber(value, 0)} t`} />
                <Bar dataKey="tonnes" name="Annual volume" fill={chartTheme.primary} radius={[4, 4, 0, 0]} maxBarSize={34} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
    </>
  )
}

export default function ExportAdvisorPage() {
  const settings = useSettings()
  const [zoneContext] = useState(readZoneContext)
  const [question, setQuestion] = useState('How should we plan export volumes for the next 12 months?')
  const [country, setCountry] = useState(settings.defaultMarket || '')
  const [goal, setGoal] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const citedEvidence = useMemo(() => {
    if (!result) return []
    const cited = new Set((result.recommendations || []).flatMap((item) => item.evidence_ids || []))
    return (result.evidence || []).filter((item) => cited.has(item.id))
  }, [result])

  async function submit(event) {
    event.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const payload = await postJSON(endpoints.exportAdvisor, {
        question,
        destination_country: country || null,
        business_goal: goal || null,
        ...zoneContext,
      }, 'Could not generate export recommendations')
      setResult(payload)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Module 07 · Component 04 · Trade insights"
        title="Trade Insights"
        description="Seasonal trade patterns from historical export data, and an AI Export Advisor whose recommendations cite retrieved data and planning guidance."
        note="Country-specific advice needs country-level export records; the current forecast dataset is aggregate."
      />

      <Seasonality />

      <Card icon="sparkle" title="AI Export Advisor" description="Ask about aggregate demand planning. Recommendations cite retrieved data and planning guidance.">
        {zoneContext.zone && <p className="chip chip-strong">Zone score attached: {zoneContext.zone} · climate {zoneContext.climate_suitability}/100 · export success {zoneContext.export_success_rate}%</p>}
        <form className="form-grid" onSubmit={submit}>
          <label className="field">
            <span>Your export planning question</span>
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} minLength={5} maxLength={1200} required rows={3} />
          </label>
          <div className="chip-row" aria-label="Suggested questions">
            {suggestions.map((item) => <button type="button" key={item} className={`chip chip-button ${question === item ? 'active' : ''}`} onClick={() => setQuestion(item)}>{item}</button>)}
          </div>
          <div className="form-row">
            <label className="field">
              <span>Destination country (optional)</span>
              <input value={country} onChange={(event) => setCountry(event.target.value)} maxLength={100} placeholder="e.g. Japan" />
            </label>
            <label className="field">
              <span>Business goal (optional)</span>
              <input value={goal} onChange={(event) => setGoal(event.target.value)} maxLength={300} placeholder="e.g. plan seasonal inventory" />
            </label>
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading || question.trim().length < 5}>
            <Icon name="sparkle" size={17} />{loading ? 'Preparing recommendations…' : 'Get explainable recommendations'}
          </button>
        </form>
      </Card>

      {loading && <LoadingState label="Retrieving evidence and preparing recommendations…" />}
      {error && <ErrorState message={error} />}

      {result && (
        <>
          <section className="panel card advisor-summary">
            <div>
              <p className="eyebrow">
                {result.llm_status === 'llm_rag'
                  ? 'LLM + RAG'
                  : result.llm_status === 'not_configured_rule_based_rag'
                    ? 'RAG guidance · LLM not configured'
                    : 'RAG guidance · LLM unavailable'}
              </p>
              <h2>Export outlook</h2>
              <p>{result.summary}</p>
            </div>
            <div className="model-chip">
              <span>Forecast model</span>
              <strong>{result.model?.name || 'LSTM'}</strong>
              <span>Test MAPE {Number(result.model?.test_mape ?? 0).toFixed(2)}%</span>
            </div>
          </section>

          <section className="advisor-recommendations" aria-label="Recommendations">
            {(result.recommendations || []).map((item, index) => (
              <article className="panel card advisor-card" key={`${item.title}-${index}`}>
                <span className="step-number">{index + 1}</span>
                <div>
                  <h3>{item.title}</h3>
                  <p className="advisor-action">{item.action}</p>
                  <p className="advisor-reason"><strong>Why:</strong> {item.reason}</p>
                  <div className="chip-row" aria-label="Evidence citations">
                    {(item.evidence_ids || []).map((id) => <span className="chip" key={id}>{id}</span>)}
                  </div>
                </div>
              </article>
            ))}
          </section>

          <Card icon="doc" title="Retrieved evidence" description="Sources used to explain the recommendations.">
            <div className="evidence-list">
              {citedEvidence.map((item) => (
                <article className="evidence-item" key={item.id}>
                  <div><span className="chip">{item.id}</span><h3>{item.title}</h3></div>
                  <p>{item.text}</p>
                  <small>{item.source}</small>
                </article>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
