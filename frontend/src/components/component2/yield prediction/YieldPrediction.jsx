import { useState } from 'react'
import { Link } from '../../ui'
const API_URL = `${(import.meta.env.VITE_API_URL || '').replace(/\/$/, '')}/component02/expected-yield`
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

  const predictedYield = result ? Number(result.predicted_kg_per_Acre) : null
  const planningMargin = Number.isFinite(predictedYield) ? Math.max(1, Math.round(predictedYield * 0.06)) : null

  return (
    <main className="relative min-h-[calc(100vh_-_88px)] bg-[linear-gradient(135deg,rgba(229,245,224,0.40),rgba(241,235,218,0.34))] text-[#203b32] [font-family:inherit] [&_:is(input,_select,_button,_a):focus-visible]:[outline:3px_solid_#80b892] [&_:is(input,_select,_button,_a):focus-visible]:outline-offset-[3px] motion-reduce:[&_*]:animate-none! motion-reduce:[&_*]:[transition:none]! motion-reduce:[&_*::before]:animate-none! motion-reduce:[&_*::before]:[transition:none]! motion-reduce:[&_*::after]:animate-none! motion-reduce:[&_*::after]:[transition:none]!">
      <div className="max-w-[1200px] m-[0_auto] p-[26px_32px_0] max-[760.01px]:p-[22px_20px_0] max-[420.01px]:pr-[16px] max-[420.01px]:pl-[16px]">
        <div className="flex gap-[12px] items-center text-[12px] text-[#6f7e75] [&_a]:text-[#526459] [&_a:hover]:text-[#087d58]"><Link to="/">Home</Link><span>/</span><span>Yield prediction</span></div>
        <header className="flex items-center justify-between gap-[24px] p-[35px_0_33px] [&_h1]:text-[clamp(29px,_3.3vw,_42px)] [&_h1]:leading-[1.2] [&_h1]:tracking-[-.045em] [&_h1]:font-[750] [&_h1]:text-[#153d2e] max-[760.01px]:p-[28px_0] max-[760.01px]:[&_h1]:text-[34px]">
          <div>
            <p className="flex items-center gap-[8px] text-[#227353] text-[10px] tracking-[.18em] font-[800] mb-[12px] [&_>_span]:w-[6px] [&_>_span]:h-[6px] [&_>_span]:bg-[#388962] [&_>_span]:rounded-[50%]"><span /> PLANTATION INTELLIGENCE</p>
            <h1>Plan ahead.<br className="hidden max-[420.01px]:block" /> Grow with insight.</h1>
            <p className="text-[14px] leading-[1.8] mt-[13px] text-[#6a7b70]">Predict your tea yield with plantation and climate data.<br />A clearer outlook for your next harvest.</p>
          </div>
          <div className="flex gap-[16px] items-center text-[#61806c] pr-[10px] [&_>_svg]:p-[15px] [&_>_svg]:box-content [&_>_svg]:bg-[#e8eee3] [&_>_svg]:rounded-[50%] [&_span]:text-[9px] [&_span]:font-[700] [&_span]:leading-[1.9] [&_span]:tracking-[.14em] max-[1000.01px]:hidden" aria-hidden="true"><Icon name="leaf" size={44} /><span>ROOTED IN DATA.<br />GROWN WITH CARE.</span></div>
        </header>

        <div className="grid grid-cols-[minmax(0,_1.65fr)_minmax(0,_1fr)] gap-[26px] items-start max-[1000.01px]:grid-cols-[minmax(0,_1.4fr)_minmax(0,_1fr)] max-[1000.01px]:gap-[20px] max-[760.01px]:grid-cols-[1fr]">
          <form className="[border:1px_solid_#e2e8de] rounded-[18px] bg-[white] overflow-hidden [box-shadow:0_5px_22px_#193b2404]" onSubmit={handleSubmit}>
            <div className="p-[25px_28px_22px] flex justify-between items-center gap-[16px] [border-bottom:1px_solid_#eef1eb] [&_h2]:text-[19px] [&_h2]:font-[750] [&_h2]:tracking-[-.025em] [&_p]:text-[12px] [&_p]:text-[#7a877c] [&_p]:mt-[4px] max-[420.01px]:p-[22px_20px] max-[420.01px]:items-start"><div><h2>Yield prediction</h2><p>Set the conditions for your forecast.</p></div><span className="text-[10px] whitespace-nowrap text-[#6b796e] [border:1px_solid_#e7ebe3] rounded-[5px] p-[5px_8px] max-[420.01px]:max-w-[68px] max-[420.01px]:whitespace-normal max-[420.01px]:text-center">All fields required</span></div>
            <fieldset disabled={loading} className="m-[0] p-[0] [border:0] min-w-[0] [&:disabled]:opacity-[.65] [&:disabled_button]:cursor-wait">
              <section className="yield-section m-[0_28px] p-[23px_0] [&_+_.yield-section]:[border-top:1px_solid_#edf0e9] [&_h3]:text-[14px] [&_h3]:font-[750] max-[420.01px]:m-[0_20px]" aria-labelledby="plantation-heading">
                <div className="flex gap-[12px] items-center mb-[19px] [&_p]:text-[#7b887f] [&_p]:text-[11px] [&_p]:mt-[3px]"><span className="bg-[#edf3e9] [border:1px_solid_#e4ecde] text-[#54744a] text-[11px] font-[750] rounded-[9px] w-[32px] h-[32px] grid place-items-center shrink-0">01</span><div><h3 id="plantation-heading">Plantation details</h3><p>Choose a grown type, then select a matching location.</p></div></div>
                <div className="grid grid-cols-[repeat(2,_minmax(0,_1fr))] gap-[17px] max-[420.01px]:gap-[14px_12px]">
                  <label className="flex flex-col gap-[8px] text-[#536357] text-[11px] font-[650] min-w-[0] [&_input]:w-[100%] [&_input]:min-w-[0] [&_input]:h-[44px] [&_input]:[border:1px_solid_#dfe6db] [&_input]:rounded-[8px] [&_input]:bg-[#fcfdfb] [&_input]:text-[#263e2f] [&_input]:p-[0_12px] [&_input]:[font-family:inherit] [&_input]:text-[13px] [&_input]:font-[500] [&_input]:[transition:border-color_.15s,_box-shadow_.15s] [&_select]:w-[100%] [&_select]:min-w-[0] [&_select]:h-[44px] [&_select]:[border:1px_solid_#dfe6db] [&_select]:rounded-[8px] [&_select]:bg-[#fcfdfb] [&_select]:text-[#263e2f] [&_select]:p-[0_12px] [&_select]:[font-family:inherit] [&_select]:text-[13px] [&_select]:font-[500] [&_select]:[transition:border-color_.15s,_box-shadow_.15s] [&_select]:cursor-pointer [&_input:hover]:[border-color:#a2b9a0] [&_select:hover]:[border-color:#a2b9a0] [&_input:focus]:[border-color:#419464] [&_input:focus]:[box-shadow:0_0_0_3px_#438c5a12] [&_select:focus]:[border-color:#419464] [&_select:focus]:[box-shadow:0_0_0_3px_#438c5a12]">Grown type<select name="Grown_Type" value={form.Grown_Type} onChange={handleChange} required><option value="LOW grown">Low grown</option><option value="MID grown">Mid grown</option><option value="HIGH grown">High grown</option></select></label>
                  <label className="flex flex-col gap-[8px] text-[#536357] text-[11px] font-[650] min-w-[0] [&_input]:w-[100%] [&_input]:min-w-[0] [&_input]:h-[44px] [&_input]:[border:1px_solid_#dfe6db] [&_input]:rounded-[8px] [&_input]:bg-[#fcfdfb] [&_input]:text-[#263e2f] [&_input]:p-[0_12px] [&_input]:[font-family:inherit] [&_input]:text-[13px] [&_input]:font-[500] [&_input]:[transition:border-color_.15s,_box-shadow_.15s] [&_select]:w-[100%] [&_select]:min-w-[0] [&_select]:h-[44px] [&_select]:[border:1px_solid_#dfe6db] [&_select]:rounded-[8px] [&_select]:bg-[#fcfdfb] [&_select]:text-[#263e2f] [&_select]:p-[0_12px] [&_select]:[font-family:inherit] [&_select]:text-[13px] [&_select]:font-[500] [&_select]:[transition:border-color_.15s,_box-shadow_.15s] [&_select]:cursor-pointer [&_input:hover]:[border-color:#a2b9a0] [&_select:hover]:[border-color:#a2b9a0] [&_input:focus]:[border-color:#419464] [&_input:focus]:[box-shadow:0_0_0_3px_#438c5a12] [&_select:focus]:[border-color:#419464] [&_select:focus]:[box-shadow:0_0_0_3px_#438c5a12]">Location<select name="Location" value={form.Location} onChange={handleChange} required>{LOCATIONS_BY_GROWN_TYPE[form.Grown_Type].map(location => <option key={location}>{location}</option>)}</select></label>
                </div>
              </section>
              <section className="yield-section m-[0_28px] p-[23px_0] [&_+_.yield-section]:[border-top:1px_solid_#edf0e9] [&_h3]:text-[14px] [&_h3]:font-[750] max-[420.01px]:m-[0_20px]" aria-labelledby="period-heading">
                <div className="flex gap-[12px] items-center mb-[19px] [&_p]:text-[#7b887f] [&_p]:text-[11px] [&_p]:mt-[3px]"><span className="bg-[#edf3e9] [border:1px_solid_#e4ecde] text-[#54744a] text-[11px] font-[750] rounded-[9px] w-[32px] h-[32px] grid place-items-center shrink-0">02</span><div><h3 id="period-heading">Prediction period</h3><p>Select the year, month, and week to estimate.</p></div></div>
                <div className="grid grid-cols-[repeat(2,_minmax(0,_1fr))] gap-[17px] max-[420.01px]:gap-[14px_12px] [&]:grid-cols-[repeat(3,_minmax(0,_1fr))] max-[420.01px]:[&]:grid-cols-[1fr_1fr] max-[420.01px]:[&_>_:first-child]:[grid-column:1_/_-1]">
                  <label className="flex flex-col gap-[8px] text-[#536357] text-[11px] font-[650] min-w-[0] [&_input]:w-[100%] [&_input]:min-w-[0] [&_input]:h-[44px] [&_input]:[border:1px_solid_#dfe6db] [&_input]:rounded-[8px] [&_input]:bg-[#fcfdfb] [&_input]:text-[#263e2f] [&_input]:p-[0_12px] [&_input]:[font-family:inherit] [&_input]:text-[13px] [&_input]:font-[500] [&_input]:[transition:border-color_.15s,_box-shadow_.15s] [&_select]:w-[100%] [&_select]:min-w-[0] [&_select]:h-[44px] [&_select]:[border:1px_solid_#dfe6db] [&_select]:rounded-[8px] [&_select]:bg-[#fcfdfb] [&_select]:text-[#263e2f] [&_select]:p-[0_12px] [&_select]:[font-family:inherit] [&_select]:text-[13px] [&_select]:font-[500] [&_select]:[transition:border-color_.15s,_box-shadow_.15s] [&_select]:cursor-pointer [&_input:hover]:[border-color:#a2b9a0] [&_select:hover]:[border-color:#a2b9a0] [&_input:focus]:[border-color:#419464] [&_input:focus]:[box-shadow:0_0_0_3px_#438c5a12] [&_select:focus]:[border-color:#419464] [&_select:focus]:[box-shadow:0_0_0_3px_#438c5a12]">Year<input type="number" name="Year" value={form.Year} onChange={handleChange} min="2016" max="2100" required /></label>
                  <label className="flex flex-col gap-[8px] text-[#536357] text-[11px] font-[650] min-w-[0] [&_input]:w-[100%] [&_input]:min-w-[0] [&_input]:h-[44px] [&_input]:[border:1px_solid_#dfe6db] [&_input]:rounded-[8px] [&_input]:bg-[#fcfdfb] [&_input]:text-[#263e2f] [&_input]:p-[0_12px] [&_input]:[font-family:inherit] [&_input]:text-[13px] [&_input]:font-[500] [&_input]:[transition:border-color_.15s,_box-shadow_.15s] [&_select]:w-[100%] [&_select]:min-w-[0] [&_select]:h-[44px] [&_select]:[border:1px_solid_#dfe6db] [&_select]:rounded-[8px] [&_select]:bg-[#fcfdfb] [&_select]:text-[#263e2f] [&_select]:p-[0_12px] [&_select]:[font-family:inherit] [&_select]:text-[13px] [&_select]:font-[500] [&_select]:[transition:border-color_.15s,_box-shadow_.15s] [&_select]:cursor-pointer [&_input:hover]:[border-color:#a2b9a0] [&_select:hover]:[border-color:#a2b9a0] [&_input:focus]:[border-color:#419464] [&_input:focus]:[box-shadow:0_0_0_3px_#438c5a12] [&_select:focus]:[border-color:#419464] [&_select:focus]:[box-shadow:0_0_0_3px_#438c5a12]">Month<select name="Month_Number" value={form.Month_Number} onChange={handleChange} required>{MONTHS.map((month, i) => <option key={month} value={i + 1}>{month}</option>)}</select></label>
                  <label className="flex flex-col gap-[8px] text-[#536357] text-[11px] font-[650] min-w-[0] [&_input]:w-[100%] [&_input]:min-w-[0] [&_input]:h-[44px] [&_input]:[border:1px_solid_#dfe6db] [&_input]:rounded-[8px] [&_input]:bg-[#fcfdfb] [&_input]:text-[#263e2f] [&_input]:p-[0_12px] [&_input]:[font-family:inherit] [&_input]:text-[13px] [&_input]:font-[500] [&_input]:[transition:border-color_.15s,_box-shadow_.15s] [&_select]:w-[100%] [&_select]:min-w-[0] [&_select]:h-[44px] [&_select]:[border:1px_solid_#dfe6db] [&_select]:rounded-[8px] [&_select]:bg-[#fcfdfb] [&_select]:text-[#263e2f] [&_select]:p-[0_12px] [&_select]:[font-family:inherit] [&_select]:text-[13px] [&_select]:font-[500] [&_select]:[transition:border-color_.15s,_box-shadow_.15s] [&_select]:cursor-pointer [&_input:hover]:[border-color:#a2b9a0] [&_select:hover]:[border-color:#a2b9a0] [&_input:focus]:[border-color:#419464] [&_input:focus]:[box-shadow:0_0_0_3px_#438c5a12] [&_select:focus]:[border-color:#419464] [&_select:focus]:[box-shadow:0_0_0_3px_#438c5a12]">Week<select name="Week_Number" value={form.Week_Number} onChange={handleChange} required>{[1, 2, 3, 4].map(week => <option key={week} value={week}>Week {week}</option>)}</select></label>
                </div>
              </section>
              <section className="yield-section m-[0_28px] p-[23px_0] [&_+_.yield-section]:[border-top:1px_solid_#edf0e9] [&_h3]:text-[14px] [&_h3]:font-[750] max-[420.01px]:m-[0_20px]" aria-labelledby="climate-heading">
                <div className="flex gap-[12px] items-center mb-[19px] [&_p]:text-[#7b887f] [&_p]:text-[11px] [&_p]:mt-[3px]"><span className="bg-[#edf3e9] [border:1px_solid_#e4ecde] text-[#54744a] text-[11px] font-[750] rounded-[9px] w-[32px] h-[32px] grid place-items-center shrink-0">03</span><div><h3 id="climate-heading">Climate conditions</h3><p>Enter the conditions for the selected period.</p></div></div>
                <div className="grid grid-cols-[repeat(2,_minmax(0,_1fr))] gap-[17px] max-[420.01px]:gap-[14px_12px] [&]:grid-cols-[repeat(3,_minmax(0,_1fr))] max-[1000.01px]:[&]:grid-cols-[repeat(2,_minmax(0,_1fr))]">
                  {CLIMATE_FIELDS.map(field => <label key={field.name} className="flex flex-col gap-[8px] text-[#536357] text-[11px] font-[650] min-w-[0] [&_input]:w-[100%] [&_input]:min-w-[0] [&_input]:h-[44px] [&_input]:[border:1px_solid_#dfe6db] [&_input]:rounded-[8px] [&_input]:bg-[#fcfdfb] [&_input]:text-[#263e2f] [&_input]:p-[0_12px] [&_input]:[font-family:inherit] [&_input]:text-[13px] [&_input]:font-[500] [&_input]:[transition:border-color_.15s,_box-shadow_.15s] [&_select]:w-[100%] [&_select]:min-w-[0] [&_select]:h-[44px] [&_select]:[border:1px_solid_#dfe6db] [&_select]:rounded-[8px] [&_select]:bg-[#fcfdfb] [&_select]:text-[#263e2f] [&_select]:p-[0_12px] [&_select]:[font-family:inherit] [&_select]:text-[13px] [&_select]:font-[500] [&_select]:[transition:border-color_.15s,_box-shadow_.15s] [&_select]:cursor-pointer [&_input:hover]:[border-color:#a2b9a0] [&_select:hover]:[border-color:#a2b9a0] [&_input:focus]:[border-color:#419464] [&_input:focus]:[box-shadow:0_0_0_3px_#438c5a12] [&_select:focus]:[border-color:#419464] [&_select:focus]:[box-shadow:0_0_0_3px_#438c5a12]"><span className="flex items-center gap-[6px] [&_svg]:text-[#7d917b]"><Icon name={field.icon} size={16} />{field.label}</span><span className="relative block [&:has(.yield-unit)_input]:pr-[45px] [&_input::-webkit-inner-spin-button]:[-webkit-appearance:none]"><input type="number" name={field.name} value={form[field.name]} min={field.min} max={field.max} step="any" required onChange={handleChange} />{field.unit && <span className="yield-unit absolute right-[12px] top-[50%] [transform:translateY(-50%)] text-[#7a897a] text-[11px] pointer-events-none">{field.unit}</span>}</span></label>)}
                </div>
              </section>
              <div className="p-[21px_28px] bg-[#fafbf8] [border-top:1px_solid_#eaf0e5] flex items-center gap-[21px] max-[1000.01px]:flex-wrap max-[1000.01px]:gap-[14px] max-[420.01px]:p-[20px]"><button className="inline-flex items-center justify-center gap-[10px] p-[13px_18px] [border:1px_solid_#17663e] rounded-[9px] bg-[#17663e] text-[white] text-[12px] font-[700] cursor-pointer [box-shadow:0_3px_8px_#17663e15] [transition:background_.15s] [&:hover]:bg-[#104e2e] max-[420.01px]:w-[100%]" type="submit">{loading ? <><span className="w-[17px] h-[17px] [border:2px_solid_#ffffff55] [border-top-color:white] rounded-[50%] animate-spin [animation-duration:0.8s]" />Generating forecast…</> : <><Icon name="chart" />Predict expected yield<Icon name="arrow" /></>}</button><button className="text-[#6a7969] bg-[transparent] text-[11px] font-[600] cursor-pointer [&:hover]:text-[#17663e] max-[420.01px]:m-[0_auto] max-[420.01px]:p-[5px]" type="button" onClick={resetForm}>Reset inputs</button></div>
            </fieldset>
          </form>

          <aside className="flex flex-col gap-[20px]">
            <section className="relative overflow-hidden rounded-[28px] bg-[#14523f] [background-image:radial-gradient(ellipse_at_top_right,_#367a6255,_transparent_64%)] p-[34px_36px] text-[#f5f7ef] [box-shadow:0_12px_28px_#163f3018] max-[600.01px]:rounded-[22px] max-[600.01px]:p-[27px_24px]" aria-labelledby="forecast-heading" aria-busy={loading}>
              {result ? <div aria-live="polite">
                <div className="flex items-start justify-between gap-[20px]">
                  <div>
                    <div className="flex items-center gap-[13px] text-white"><span className="grid h-[38px] w-[38px] place-items-center rounded-[10px] bg-white/10"><Icon name="chart" size={23} /></span><h2 id="forecast-heading" className="m-0 text-[23px] font-[700] tracking-[-.03em]">Expected yield</h2></div>
                    <p className="mt-[11px] flex flex-wrap items-baseline gap-x-[16px] text-[clamp(66px,_7.8vw,_98px)] font-[750] leading-none tracking-[-.08em] text-white max-[420.01px]:text-[58px]"><span>{predictedYield.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span><span className="text-[clamp(30px,_4vw,_46px)] font-[500] tracking-[-.035em] text-[#d5e1cf] max-[420.01px]:text-[27px]">kg / acre</span></p>
                  </div>
                  <span className="pt-[5px] text-right text-[11px] font-[800] tracking-[.15em] text-[#c8d9af] max-[420.01px]:hidden">YIELD ESTIMATE</span>
                </div>
                <div className="mt-[22px] inline-flex items-center rounded-[13px] border border-[#b5cda466] bg-[#ffffff0b] px-[17px] py-[13px] text-[16px] text-[#d7e4d0] max-[420.01px]:text-[14px]">Planning margin: <strong className="ml-[6px] font-[750] text-[#d6eba9]">±{planningMargin} kg / acre</strong></div>
                <p className="mt-[35px] text-[16px] leading-[1.6] text-[#d2ddd0]">One field estimate for your selected harvest period</p>
                <div className="mt-[48px] h-px bg-[#d9e8d040]" />
                <div className="mt-[24px] flex flex-wrap items-center gap-x-[28px] gap-y-[10px] text-[16px] text-[#dce7d8] max-[420.01px]:text-[14px]"><span className="inline-flex items-center gap-[10px]"><Icon name="pin" size={22} />{result.location ?? form.Location}</span><span>{MONTHS[Number(result.month ?? form.Month_Number) - 1]} {result.year ?? form.Year} · Week {result.week ?? form.Week_Number}</span></div>
              </div> : <div className="flex min-h-[340px] flex-col items-center justify-center p-[26px_4px] text-center max-[760.01px]:min-h-[260px]" aria-live="polite" role="status">
                <div className={`grid h-[74px] w-[74px] place-items-center rounded-[50%] border border-[#aace9529] bg-[#ffffff07] text-[#bed7a3] ${loading ? "animate-yield-pulse" : ""}`}><Icon name={loading ? 'chart' : 'leaf'} size={34} /></div><h2 id="forecast-heading" className="mt-[21px] text-[20px] font-[650] tracking-[-.025em] text-[#e2ebd9]">{loading ? 'Calculating your outlook' : 'Your next harvest, in focus'}</h2><p className="mt-[9px] max-w-[255px] text-[12px] leading-[1.85] text-[#b3c8b7]">{loading ? 'Analysing the plantation and climate conditions you provided.' : 'Add your plantation details and generate a forecast to see your expected yield here.'}</p>
              </div>}
            </section>
            {error && <div className="p-[17px] [border:1px_solid_#eec6be] rounded-[12px] bg-[#fff3ef] text-[#9f392c] text-[12px] leading-[1.7] [overflow-wrap:anywhere] [&_strong]:block [&_strong]:mb-[5px] [&_span]:block [&_span]:mt-[7px]" role="alert"><strong>We couldn’t generate your forecast</strong><p>{error}</p><span>Review your inputs and try again.</span></div>}
            <section className="flex items-start gap-[13px] [border:1px_solid_#e1e7d7] rounded-[12px] bg-[#edf1e5] p-[20px] [&_h3]:text-[#465b35] [&_h3]:text-[12px] [&_h3]:font-[750] [&_h3]:mb-[7px] [&_p]:text-[11px] [&_p]:leading-[1.85] [&_p]:text-[#6a775c]"><span className="grid place-items-center p-[9px] text-[#67804b] rounded-[9px] bg-[#e1e9d5]"><Icon name="leaf" /></span><div><h3>Better inputs. Better insights.</h3><p>Use climate values that represent your selected location and period for a more useful estimate.</p></div></section>
            <p className="text-[10px] leading-[1.85] p-[0_8px] text-[#7c897e]">Use this forecast as a planning aid. Actual yield may vary with field conditions and cultivation practices.</p>
          </aside>
        </div>
        <footer className="flex justify-between items-center gap-[16px] mt-[33px] p-[22px_0] [border-top:1px_solid_#e3e9de] text-[10px] text-[#7c887b] [&_a]:inline-flex [&_a]:items-center [&_a]:gap-[8px] [&_a]:text-[#60715e] [&_a]:font-[600] max-[760.01px]:items-start max-[760.01px]:flex-col"><Link to="/"><Icon name="back" size={16} />Back to overview</Link><span>AI Smart Tea Ecosystem <span aria-hidden="true">·</span> Cultivating smarter decisions</span></footer>
      </div>
    </main>
  )
}
