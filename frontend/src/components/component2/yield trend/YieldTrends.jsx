import { useEffect, useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
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
  return <main className="max-w-[1440px] m-[auto] p-[32px_clamp(16px,4vw,60px)_64px] text-[#203c30] bg-[#f6f8f5] min-h-[100vh] [&_button:focus-visible]:[outline:3px_solid_#6ca98a] [&_button:focus-visible]:outline-offset-[3px] [&_a:focus-visible]:[outline:3px_solid_#6ca98a] [&_a:focus-visible]:outline-offset-[3px] [&_summary:focus-visible]:[outline:3px_solid_#6ca98a] [&_summary:focus-visible]:outline-offset-[3px]">
    <div className="flex justify-between items-center gap-[16px] m-[30px_0_24px] flex-wrap"><div className="flex p-[5px] bg-[#e8eee8] rounded-[12px] gap-[4px] [&_button]:p-[11px_24px] [&_button]:rounded-[8px] [&_button]:text-[14px] [&_button]:text-[#637469] [&_button]:cursor-pointer [&_button[aria-pressed=true]]:bg-[#24664b] [&_button[aria-pressed=true]]:text-[white] [&_button[aria-pressed=true]]:[box-shadow:0_3px_8px_#224c4220] max-[700.01px]:[&_button]:p-[10px_16px]" role="group" aria-label="Grown type">{TYPES.map(type => <button key={type} aria-pressed={grown === type} onClick={() => selectType(type)}>{type === 'HIGH grown' ? 'High grown' : type === 'MID grown' ? 'Mid grown' : 'Low grown'}</button>)}</div></div>
    {state.loading ? <div className="p-[70px_24px] text-center bg-[white] [border:1px_solid_#dfe7df] rounded-[14px] [&_button]:mt-[20px] [&_button]:bg-[#24664b] [&_button]:text-[white] [&_button]:p-[10px_24px] [&_button]:rounded-[8px] [&_button]:cursor-pointer" role="status">Loading yield history and generating predictions…</div> : state.error ? <div className="p-[70px_24px] text-center bg-[white] [border:1px_solid_#dfe7df] rounded-[14px] [&_button]:mt-[20px] [&_button]:bg-[#24664b] [&_button]:text-[white] [&_button]:p-[10px_24px] [&_button]:rounded-[8px] [&_button]:cursor-pointer" role="alert"><h2>Yield data is unavailable</h2><p>{state.error}</p><button onClick={() => { setState({ loading: true }); setAttempt(value => value + 1) }}>Try again</button></div> : <>
      <section className="grid grid-cols-[repeat(3,1fr)] gap-[18px] mb-[24px] [&_article]:p-[22px_26px] [&_article]:bg-[white] [&_article]:[border:1px_solid_#e0e7df] [&_article]:rounded-[14px] [&_p]:text-[13px] [&_p]:text-[#718176] [&_p]:mb-[10px] [&_strong]:block [&_strong]:text-[30px] [&_strong]:font-[700] [&_small]:text-[13px] [&_small]:font-[400] [&_small]:text-[#718176] [&_span]:block [&_span]:text-[12px] [&_span]:text-[#7a887f] [&_span]:mt-[10px] max-[700.01px]:grid-cols-[1fr] max-[700.01px]:[&_article]:p-[18px]" aria-label="Yield summary">
        <article><p>Latest actual yield</p><strong>{number(latest?.actual)} <small>kg/acre</small></strong><span>{latest ? formatDate(latest.date) : 'No actual records'}</span></article>
        <article><p>Next month prediction</p><strong>{number(future[0]?.forecast)} <small>kg/acre</small></strong><span>{future[0] ? formatDate(future[0].date) : 'No forecast available'}</span></article>
        <article><p>Forecast horizon</p><strong>{data.forecast_months} <small>months</small></strong><span>{data.locations.length} locations · {grown.toLowerCase()}</span></article>
      </section>
      <section className="bg-[white] [border:1px_solid_#dfe7df] rounded-[14px] p-[26px_20px_20px] [box-shadow:0_4px_20px_#233e2b04] max-[700.01px]:p-[20px_4px]"><div className="flex justify-between items-center gap-[15px] p-[0_10px] [&_h2]:text-[19px] [&_h2]:font-[700] [&_p]:text-[12px] [&_p]:text-[#7c897f] [&_p]:mt-[6px] [&>span]:text-[12px] [&>span]:text-[#7c897f] [&>span]:mt-[6px] max-[700.01px]:[&>span]:hidden"><div><h2>{grown.charAt(0) + grown.slice(1).toLowerCase()} yield prediction</h2><p>Monthly yield · kg per acre · average across locations</p></div><span>Historical + future outlook</span></div>
        <div className="h-[450px] mt-[24px] max-[700.01px]:h-[350px]" role="img" aria-label={`${grown} monthly actual yield, 2025 test predictions and future forecast.`}><ResponsiveContainer width="100%" height="100%"><LineChart data={data.points} margin={{ top: 18, right: 24, left: 12, bottom: 15 }}><CartesianGrid strokeDasharray="5 5" vertical stroke="#dfe7e2" /><XAxis dataKey="date" tickFormatter={formatDate} minTickGap={65} tick={{ fill: '#75877d', fontSize: 12 }} tickMargin={12} /><YAxis domain={[0, 'auto']} tick={{ fill: '#75877d', fontSize: 12 }} tickFormatter={number} width={65} /><Tooltip labelFormatter={formatDate} formatter={(value, name) => [`${number(value)} kg/acre`, name]} /><Legend wrapperStyle={{ paddingTop: 24 }} /><Line type="monotone" dataKey="test_prediction" name="2025 test prediction" stroke="#4381b4" strokeWidth={2} dot={false} /><Line type="monotone" dataKey="actual" name="Actual monthly yield" stroke="#27765c" strokeWidth={2.5} dot={false} /><Line type="monotone" dataKey="forecast" name="Future forecast" stroke="#a34770" strokeWidth={2.5} strokeDasharray="7 5" dot={false} /></LineChart></ResponsiveContainer></div>
      </section>
    </>}
  </main>
}
