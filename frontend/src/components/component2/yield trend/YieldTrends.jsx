import { useEffect, useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import './YieldTrends.css'

const TYPES = ['HIGH grown', 'MID grown', 'LOW grown']
const API = `${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/component02/expected-yield/trends`
const formatDate = value => new Date(`${value}-01T00:00:00`).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })
const number = value => value == null ? '—' : value.toLocaleString(undefined, { maximumFractionDigits: 1 })

export default function YieldTrends() {
  const [grown, setGrown] = useState(TYPES[0])
  const [state, setState] = useState({ loading: true })
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    fetch(`${API}?grown_type=${encodeURIComponent(grown)}`, { signal: controller.signal })
      .then(async response => {
        const data = await response.json()
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Unable to load yield predictions.')
        if (!data.points?.length) throw new Error('No yield data is available for this grown type.')
        setState({ data, loading: false })
      })
      .catch(error => {
        if (error.name !== 'AbortError') setState({ error: error.message === 'Failed to fetch' ? 'Cannot connect to the prediction service. Check that the backend is running and try again.' : error.message, loading: false })
      })
    return () => controller.abort()
  }, [grown, attempt])
  const data = state.data
  const historical = data?.points.filter(point => point.actual != null) || []
  const future = data?.points.filter(point => point.forecast != null) || []
  const latest = historical.at(-1)
  function selectType(type) {
    if (type === grown) return
    setState({ loading: true })
    setGrown(type)
  }
  return <main className="yield-trends">
    <div className="yt-toolbar"><div className="yt-tabs" role="group" aria-label="Grown type">{TYPES.map(type => <button key={type} aria-pressed={grown === type} onClick={() => selectType(type)}>{type === 'HIGH grown' ? 'High grown' : type === 'MID grown' ? 'Mid grown' : 'Low grown'}</button>)}</div></div>
    {state.loading ? <div className="yt-message" role="status">Loading yield history and generating predictions…</div> : state.error ? <div className="yt-message" role="alert"><h2>Yield data is unavailable</h2><p>{state.error}</p><button onClick={() => { setState({ loading: true }); setAttempt(value => value + 1) }}>Try again</button></div> : <>
      <section className="yt-stats" aria-label="Yield summary">
        <article><p>Latest actual yield</p><strong>{number(latest?.actual)} <small>kg/acre</small></strong><span>{latest ? formatDate(latest.date) : 'No actual records'}</span></article>
        <article><p>Next month prediction</p><strong>{number(future[0]?.forecast)} <small>kg/acre</small></strong><span>{future[0] ? formatDate(future[0].date) : 'No forecast available'}</span></article>
        <article><p>Forecast horizon</p><strong>{data.forecast_months} <small>months</small></strong><span>{data.locations.length} locations · {grown.toLowerCase()}</span></article>
      </section>
      <section className="yt-chart-card"><div className="yt-chart-heading"><div><h2>{grown.charAt(0) + grown.slice(1).toLowerCase()} yield prediction</h2><p>Monthly yield · kg per acre · average across locations</p></div><span>Historical + future outlook</span></div>
        <div className="yt-chart" role="img" aria-label={`${grown} monthly actual yield, 2025 test predictions and future forecast.`}><ResponsiveContainer width="100%" height="100%"><LineChart data={data.points} margin={{ top: 18, right: 24, left: 12, bottom: 15 }}><CartesianGrid strokeDasharray="5 5" vertical stroke="#dfe7e2" /><XAxis dataKey="date" tickFormatter={formatDate} minTickGap={65} tick={{ fill: '#75877d', fontSize: 12 }} tickMargin={12} /><YAxis domain={[0, 'auto']} tick={{ fill: '#75877d', fontSize: 12 }} tickFormatter={number} width={65} /><Tooltip labelFormatter={formatDate} formatter={(value, name) => [`${number(value)} kg/acre`, name]} /><Legend wrapperStyle={{ paddingTop: 24 }} /><Line type="monotone" dataKey="test_prediction" name="2025 test prediction" stroke="#4381b4" strokeWidth={2} dot={false} /><Line type="monotone" dataKey="actual" name="Actual monthly yield" stroke="#27765c" strokeWidth={2.5} dot={false} /><Line type="monotone" dataKey="forecast" name="Future forecast" stroke="#a34770" strokeWidth={2.5} strokeDasharray="7 5" dot={false} /></LineChart></ResponsiveContainer></div>
      </section>
    </>}
  </main>
}
