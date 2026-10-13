import { useState } from 'react'
import { Link } from 'react-router-dom'
import './YieldPrediction.css'

const API_URL = 'http://127.0.0.1:8000/component02/expected-yield'
const INITIAL_FORM = {
  Year: 2026, Month_Number: 10, Week_Number: 2, Temperature: 28,
  Rainfall_mm: 100, Humidity: 85, Wind_Speed: 5, Solar_Radiation: 220,
  Location: 'Galle', Grown_Type: 'LOW grown',
}
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const LOCATIONS_BY_GROWN_TYPE = {
  'HIGH grown': ['Nuwara Eliya', 'Dimbula', 'Uva'],
  'LOW grown': ['Galle', 'Kalutara', 'Kegalle', 'Matara', 'Ratnapura'],
  'MID grown': ['Badulla', 'Kandy', 'Matale', 'Nawalapitiya'],
}
const CLIMATE_FIELDS = [
  { label: 'Temperature', name: 'Temperature', unit: '°C', icon: 'sun' },
  { label: 'Rainfall', name: 'Rainfall_mm', unit: 'mm', min: 0, icon: 'rain' },
  { label: 'Humidity', name: 'Humidity', unit: '%', min: 0, max: 100, icon: 'drop' },
  { label: 'Wind speed', name: 'Wind_Speed', min: 0, icon: 'wind' },
  { label: 'Solar radiation', name: 'Solar_Radiation', min: 0, icon: 'sun' },
]

function Icon({ name, size = 20 }) {
  const paths = {
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    back: <path d="M19 12H5m5-5-5 5 5 5" />,
    pin: <><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z" /><circle cx="12" cy="10" r="2" /></>,
    leaf: <><path d="M20 4C9 3 3 9 5 15c2 7 13 7 15-11Z" /><path d="M4 21 15 10" /></>,
    sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" /></>,
    rain: <><path d="M6 15a5 5 0 1 1 1-10 6 6 0 0 1 11 2 4 4 0 0 1 0 8M8 18l-1 3m6-3-1 3m6-3-1 3" /></>,
    drop: <path d="M12 3S5 11 5 15a7 7 0 0 0 14 0c0-4-7-12-7-12Z" />,
    wind: <><path d="M3 8h12a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h6a3 3 0 1 1-3 3" /></>,
    chart: <><path d="M4 4v16h16M8 15v-4m5 4V7m5 8v-6" /></>,
    check: <path d="m5 12 4 4L19 6" />,
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}

export default function YieldPrediction() {
  const [form, setForm] = useState({ ...INITIAL_FORM })
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  function handleChange(e) {
    const { name, value } = e.target
    setForm(prev => {
      if (name === 'Grown_Type') {
        const locations = LOCATIONS_BY_GROWN_TYPE[value]
        return {
          ...prev,
          Grown_Type: value,
          Location: locations.includes(prev.Location) ? prev.Location : locations[0],
        }
      }
      return { ...prev, [name]: value }
    })
    setResult(null)
    setError('')
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)
    const payload = Object.fromEntries(Object.entries(form).map(([key, value]) =>
      [key, ['Location', 'Grown_Type'].includes(key) ? value : Number(value)]))
    try {
      const response = await fetch(`${API_URL}/predict`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Prediction failed. Please check the input values.')
      setResult(data)
    } catch (err) {
      setError(err.message === 'Failed to fetch' ? 'Unable to connect. Please try again in a moment.' : err.message)
    } finally {
      setLoading(false)
    }
  }

  function resetForm() {
    setForm({ ...INITIAL_FORM })
    setResult(null)
    setError('')
  }

  return (
    <main className="yield-page">
      <div className="yield-container">
        <div className="yield-breadcrumb"><Link to="/">Home</Link><span>/</span><span>Yield prediction</span></div>
        <header className="yield-header">
          <div>
            <p className="yield-eyebrow"><span /> PLANTATION INTELLIGENCE</p>
            <h1>Plan ahead.<br className="yield-mobile-break" /> Grow with insight.</h1>
            <p className="yield-intro">Predict your tea yield with plantation and climate data.<br />A clearer outlook for your next harvest.</p>
          </div>
          <div className="yield-header-mark" aria-hidden="true"><Icon name="leaf" size={44} /><span>ROOTED IN DATA.<br />GROWN WITH CARE.</span></div>
        </header>

        <div className="yield-workspace">
          <form className="yield-form" onSubmit={handleSubmit}>
            <div className="yield-form-heading"><div><h2>Yield prediction</h2><p>Set the conditions for your forecast.</p></div><span className="yield-required">All fields required</span></div>
            <fieldset disabled={loading} className="yield-fields">
              <section className="yield-section" aria-labelledby="plantation-heading">
                <div className="yield-section-heading"><span className="yield-step">01</span><div><h3 id="plantation-heading">Plantation details</h3><p>Choose a grown type, then select a matching location.</p></div></div>
                <div className="yield-input-grid">
                  <label className="yield-field">Grown type<select name="Grown_Type" value={form.Grown_Type} onChange={handleChange} required><option value="LOW grown">Low grown</option><option value="MID grown">Mid grown</option><option value="HIGH grown">High grown</option></select></label>
                  <label className="yield-field">Location<select name="Location" value={form.Location} onChange={handleChange} required>{LOCATIONS_BY_GROWN_TYPE[form.Grown_Type].map(location => <option key={location}>{location}</option>)}</select></label>
                </div>
              </section>
              <section className="yield-section" aria-labelledby="period-heading">
                <div className="yield-section-heading"><span className="yield-step">02</span><div><h3 id="period-heading">Prediction period</h3><p>Select the year, month, and week to estimate.</p></div></div>
                <div className="yield-input-grid yield-period-grid">
                  <label className="yield-field">Year<input type="number" name="Year" value={form.Year} onChange={handleChange} min="2016" max="2100" required /></label>
                  <label className="yield-field">Month<select name="Month_Number" value={form.Month_Number} onChange={handleChange} required>{MONTHS.map((month, i) => <option key={month} value={i + 1}>{month}</option>)}</select></label>
                  <label className="yield-field">Week<select name="Week_Number" value={form.Week_Number} onChange={handleChange} required>{[1, 2, 3, 4].map(week => <option key={week} value={week}>Week {week}</option>)}</select></label>
                </div>
              </section>
              <section className="yield-section" aria-labelledby="climate-heading">
                <div className="yield-section-heading"><span className="yield-step">03</span><div><h3 id="climate-heading">Climate conditions</h3><p>Enter the conditions for the selected period.</p></div></div>
                <div className="yield-input-grid yield-climate-grid">
                  {CLIMATE_FIELDS.map(field => <label key={field.name} className="yield-field"><span className="yield-field-title"><Icon name={field.icon} size={16} />{field.label}</span><span className="yield-input-wrap"><input type="number" name={field.name} value={form[field.name]} min={field.min} max={field.max} step="any" required onChange={handleChange} />{field.unit && <span className="yield-unit">{field.unit}</span>}</span></label>)}
                </div>
              </section>
              <div className="yield-form-actions"><button className="yield-submit" type="submit">{loading ? <><span className="yield-spinner" />Generating forecast…</> : <><Icon name="chart" />Predict expected yield<Icon name="arrow" /></>}</button><button className="yield-reset" type="button" onClick={resetForm}>Reset inputs</button></div>
            </fieldset>
          </form>

          <aside className="yield-sidebar">
            <section className={`yield-result ${result ? 'yield-result-ready' : ''}`} aria-labelledby="forecast-heading" aria-busy={loading}>
              <div className="yield-result-top"><span className="yield-result-label">YOUR FORECAST</span><Icon name="chart" /></div>
              <h2 id="forecast-heading">Expected tea yield</h2>
              <p className="yield-result-subtitle">An estimate for your selected conditions.</p>
              <div className="yield-result-body" aria-live="polite" role="status">
                {result ? <><span className="yield-result-status"><Icon name="check" size={14} />Prediction complete</span><div className="yield-result-number">{Number(result.predicted_kg_per_Acre).toLocaleString(undefined, { maximumFractionDigits: 2 })}</div><p className="yield-result-unit">kilograms per acre</p></> : <><div className={`yield-empty-icon ${loading ? 'yield-pulse' : ''}`}><Icon name={loading ? 'chart' : 'leaf'} size={34} /></div><h3>{loading ? 'Calculating your outlook' : 'Your next harvest, in focus'}</h3><p>{loading ? 'Analysing the plantation and climate conditions you provided.' : 'Add your plantation details and generate a forecast to see your estimated yield here.'}</p></>}
              </div>
              <dl className="yield-result-details"><div><dt><Icon name="pin" size={15} />Location</dt><dd>{result?.location ?? form.Location}</dd></div><div><dt>Period</dt><dd>{MONTHS[Number(result?.month ?? form.Month_Number) - 1]} {result?.year ?? form.Year} · Week {result?.week ?? form.Week_Number}</dd></div></dl>
              <div className="yield-result-footer"><span className="yield-status-dot" />{result ? 'Forecast generated' : loading ? 'Forecast in progress' : 'Ready when you are'}</div>
            </section>
            {error && <div className="yield-error" role="alert"><strong>We couldn’t generate your forecast</strong><p>{error}</p><span>Review your inputs and try again.</span></div>}
            <section className="yield-guide"><span className="yield-guide-icon"><Icon name="leaf" /></span><div><h3>Better inputs. Better insights.</h3><p>Use climate values that represent your selected location and period for a more useful estimate.</p></div></section>
            <p className="yield-disclaimer">Use this forecast as a planning aid. Actual yield may vary with field conditions and cultivation practices.</p>
          </aside>
        </div>
        <footer className="yield-footer"><Link to="/"><Icon name="back" size={16} />Back to overview</Link><span>AI Smart Tea Ecosystem <span aria-hidden="true">·</span> Cultivating smarter decisions</span></footer>
      </div>
    </main>
  )
}
