import { useMemo, useState } from 'react'

const zoneParams = new URLSearchParams(window.location.search)
const zoneContext = zoneParams.has('zone') ? {
  zone: zoneParams.get('zone'),
  climate_suitability: Number(zoneParams.get('climate_suitability')),
  export_success_rate: Number(zoneParams.get('export_success_rate')),
} : {}

export default function ExportAdvisorPage() {
  const [question, setQuestion] = useState('How should we plan export volumes for the next 12 months?')
  const [country, setCountry] = useState('')
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
      const response = await fetch('/api/component04/export-advisor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          destination_country: country || null,
          business_goal: goal || null,
          ...zoneContext,
        }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'Could not generate export recommendations')
      setResult(payload)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="dashboard">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Module 07 · Component 04</p>
          <h1>AI Export Advisor</h1>
          <p className="subtle">Ask about aggregate demand planning. Recommendations cite retrieved data and planning guidance.</p>
          {zoneContext.zone && <p className="citation-chip">Zone score attached: {zoneContext.zone} · climate {zoneContext.climate_suitability}/100 · export success {zoneContext.export_success_rate}%</p>}
        </div>
      </header>

      <section className="panel advisor-form-panel">
        <form className="advisor-form" onSubmit={submit}>
          <label>
            <span>Your export planning question</span>
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} minLength={5} maxLength={1200} required rows={3} />
          </label>
          <div className="advisor-input-row">
            <label>
              <span>Destination country (optional)</span>
              <input value={country} onChange={(event) => setCountry(event.target.value)} maxLength={100} placeholder="e.g. Japan" />
            </label>
            <label>
              <span>Business goal (optional)</span>
              <input value={goal} onChange={(event) => setGoal(event.target.value)} maxLength={300} placeholder="e.g. plan seasonal inventory" />
            </label>
          </div>
          <button className="advisor-submit" type="submit" disabled={loading || question.trim().length < 5}>
            {loading ? 'Preparing recommendations…' : 'Get explainable recommendations'}
          </button>
        </form>
        <p className="advisor-note">Country-specific advice needs country-level export records; the current forecast dataset is aggregate.</p>
      </section>

      {error && <section className="empty-state advisor-error" role="alert">{error}</section>}

      {result && (
        <>
          <section className="panel advisor-summary">
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
              <article className="panel advisor-card" key={`${item.title}-${index}`}>
                <p className="eyebrow">Recommendation {index + 1}</p>
                <h2>{item.title}</h2>
                <p className="advisor-action">{item.action}</p>
                <p className="advisor-reason"><strong>Why:</strong> {item.reason}</p>
                <div className="citation-list" aria-label="Evidence citations">
                  {(item.evidence_ids || []).map((id) => <span className="citation-chip" key={id}>{id}</span>)}
                </div>
              </article>
            ))}
          </section>

          <section className="panel">
            <div className="panel-heading">
              <div><h2>Retrieved evidence</h2><p>Sources used to explain the recommendations</p></div>
            </div>
            <div className="evidence-list">
              {citedEvidence.map((item) => (
                <article className="evidence-item" key={item.id}>
                  <div><span className="citation-chip">{item.id}</span><h3>{item.title}</h3></div>
                  <p>{item.text}</p>
                  <small>{item.source}</small>
                </article>
              ))}
            </div>
          </section>
        </>
      )}
    </main>
  )
}
