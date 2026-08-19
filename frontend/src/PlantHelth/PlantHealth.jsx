import { useEffect, useRef, useState } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? '' : 'http://127.0.0.1:8000')
const ACCEPTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']

const getLocalDate = () => {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

const formatNumber = (value, maximumFractionDigits = 2) => {
  if (value === null || value === undefined || value === '') return 'Unavailable'
  const number = Number(value)
  if (!Number.isFinite(number)) return 'Unavailable'
  return new Intl.NumberFormat('en-US', { maximumFractionDigits }).format(number)
}

const humanize = (value) =>
  String(value || 'Unknown')
    .replace(/[_-]/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase())

const normalizeHealthPrediction = (value) => {
  const normalized = String(value || '').trim().toLowerCase().replace(/[- ]/g, '_')
  return normalized === 'healthy' ? 'healthy' : 'low_health'
}

const statusTone = (value) => {
  const normalized = String(value || '').toLowerCase()
  if (normalized === 'low' || normalized === 'healthy' || normalized === 'no immediate risk') {
    return {
      badge: 'bg-emerald-100 text-emerald-800',
      dot: 'bg-emerald-500',
      panel: 'border-emerald-200 bg-emerald-50',
      text: 'text-emerald-800',
      bar: 'bg-emerald-500',
    }
  }
  if (normalized === 'medium' || normalized === 'monitor conditions') {
    return {
      badge: 'bg-amber-100 text-amber-800',
      dot: 'bg-amber-500',
      panel: 'border-amber-200 bg-amber-50',
      text: 'text-amber-800',
      bar: 'bg-amber-500',
    }
  }
  if (normalized === 'high' || normalized === 'low health' || normalized.includes('immediate action')) {
    return {
      badge: 'bg-red-100 text-red-800',
      dot: 'bg-red-500',
      panel: 'border-red-200 bg-red-50',
      text: 'text-red-800',
      bar: 'bg-red-500',
    }
  }
  return {
    badge: 'bg-slate-100 text-slate-700',
    dot: 'bg-slate-400',
    panel: 'border-slate-200 bg-slate-50',
    text: 'text-slate-700',
    bar: 'bg-slate-400',
  }
}

const healthTone = (score) => {
  if (score >= 70) return statusTone('healthy')
  if (score >= 40) return statusTone('medium')
  return statusTone('low health')
}

const riskTone = (risk) => {
  const normalized = String(risk || '').toLowerCase()
  if (normalized === 'low') return statusTone('low')
  if (normalized === 'medium') return statusTone('medium')
  if (normalized === 'high') return statusTone('high')
  return statusTone('unknown')
}

function Icon({ name, size = 20, className = '' }) {
  const paths = {
    activity: <><path d="M3 12h4l2.2-6 4.1 12L15.5 12H21" /><path d="M12 3v2" /></>,
    alert: <><path d="M10.3 4.2 2.8 17a2 2 0 0 0 1.7 3h15a2 2 0 0 0 1.7-3l-7.5-12.8a2 2 0 0 0-3.4 0Z" /><path d="M12 9v4M12 17h.01" /></>,
    calendar: <><rect x="3" y="4.5" width="18" height="16" rx="2" /><path d="M16 2.5v4M8 2.5v4M3 9h18" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    chevron: <path d="m6 9 6 6 6-6" />,
    cloud: <><path d="M17.5 19H8a5 5 0 1 1 1.3-9.8A6 6 0 0 1 21 11.5 3.5 3.5 0 0 1 17.5 19Z" /><path d="M8 22h.01M12 22h.01M16 22h.01" /></>,
    compass: <><circle cx="12" cy="12" r="9" /><path d="m15.5 8.5-2.2 4.8-4.8 2.2 2.2-4.8 4.8-2.2Z" /></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6M8 13h8M8 17h5" /></>,
    image: <><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="m21 15-5-5L5 21" /></>,
    leaf: <><path d="M20.8 3.2C12.5 3.4 5.8 6.4 4.2 12.1 3.2 15.7 5.5 19 9 19.4c5.7.7 9-5.6 11.8-16.2Z" /><path d="M4.5 19.5C7.5 14.8 11 11.8 17 8" /></>,
    location: <><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" /><circle cx="12" cy="10" r="2.5" /></>,
    minus: <path d="M5 12h14" />,
    plus: <path d="M12 5v14M5 12h14" />,
    refresh: <><path d="M20 11a8.1 8.1 0 0 0-14.7-3L3 11" /><path d="M3 5v6h6M4 13a8.1 8.1 0 0 0 14.7 3L21 13" /><path d="M21 19v-6h-6" /></>,
    sparkles: <><path d="m12 3-1.2 4.1L7 8.5l3.8 1.4L12 14l1.2-4.1L17 8.5l-3.8-1.4L12 3ZM19 14l-.7 2.3L16 17l2.3.7L19 20l.7-2.3L22 17l-2.3-.7L19 14ZM5 14l-.7 2.3L2 17l2.3.7L5 20l.7-2.3L8 17l-2.3-.7L5 14Z" /></>,
    sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
    upload: <><path d="M12 16V4M7 9l5-5 5 5" /><path d="M5 20h14" /></>,
    water: <path d="M12 2.5S5.5 10 5.5 14.5a6.5 6.5 0 0 0 13 0C18.5 10 12 2.5 12 2.5Z" />,
    wind: <><path d="M3 8h12a3 3 0 1 0-3-3" /><path d="M3 12h16a2 2 0 1 1-2 2" /><path d="M3 16h8" /></>,
  }

  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height={size}
      viewBox="0 0 24 24"
      width={size}
      xmlns="http://www.w3.org/2000/svg"
    >
      <g stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8">
        {paths[name] || paths.activity}
      </g>
    </svg>
  )
}

function Badge({ children, tone = 'bg-emerald-100 text-emerald-800' }) {
  return <span className={`inline-flex items-center rounded-full px-3 py-1 text-[11px] font-bold uppercase tracking-[0.12em] ${tone}`}>{children}</span>
}

function SectionTitle({ eyebrow, title, description, icon = 'activity' }) {
  return (
    <div className="mb-5 flex items-start gap-3">
      <div className="mt-0.5 rounded-xl bg-emerald-100 p-2 text-emerald-700">
        <Icon name={icon} size={20} />
      </div>
      <div>
        {eyebrow && <p className="mb-1 text-[11px] font-bold uppercase tracking-[0.16em] text-emerald-700">{eyebrow}</p>}
        <h2 className="text-xl font-black tracking-tight text-slate-900">{title}</h2>
        {description && <p className="mt-1 text-sm leading-6 text-slate-500">{description}</p>}
      </div>
    </div>
  )
}

function ProgressBar({ value, tone, label }) {
  const safeValue = Math.max(0, Math.min(100, Number(value) || 0))
  return (
    <div className="mt-3">
      <div className="mb-1.5 flex justify-between gap-3 text-xs font-bold text-slate-600">
        <span>{label}</span><span>{formatNumber(value)}%</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full transition-all ${tone.bar}`} style={{ width: `${safeValue}%` }} />
      </div>
    </div>
  )
}

function MetricCard({ icon, label, value, unit, note }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-bold uppercase tracking-[0.1em] text-slate-500">{label}</p>
        <div className="rounded-lg bg-emerald-50 p-2 text-emerald-700"><Icon name={icon} size={18} /></div>
      </div>
      <p className="mt-5 text-2xl font-black tracking-tight text-slate-900">
        {value} <span className="text-sm font-bold text-slate-500">{unit}</span>
      </p>
      {note && <p className="mt-1 text-xs text-slate-400">{note}</p>}
    </div>
  )
}

function PlantHealth() {
  const [selectedFiles, setSelectedFiles] = useState([])
  const [previewUrls, setPreviewUrls] = useState([])
  const [latitude, setLatitude] = useState('6.9497')
  const [longitude, setLongitude] = useState('80.7891')
  const [date, setDate] = useState(getLocalDate)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const fileInputRef = useRef(null)

  useEffect(() => () => {
    previewUrls.forEach((previewUrl) => URL.revokeObjectURL(previewUrl))
  }, [previewUrls])

  const fieldClass = 'h-12 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 text-sm font-medium text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-600/10'

  const setImages = (fileList) => {
    const files = Array.from(fileList || [])
    if (files.length === 0) return
    if (files.length > 5) {
      setError('Please choose a maximum of 5 plantation images.')
      return
    }
    if (files.some((file) => !ACCEPTED_IMAGE_TYPES.includes(file.type))) {
      setError('Please choose JPG, JPEG, PNG, or WEBP plantation images only.')
      return
    }
    previewUrls.forEach((previewUrl) => URL.revokeObjectURL(previewUrl))
    setSelectedFiles(files)
    setPreviewUrls(files.map((file) => URL.createObjectURL(file)))
    setError('')
    setResult(null)
  }

  const removeImage = () => {
    previewUrls.forEach((previewUrl) => URL.revokeObjectURL(previewUrl))
    setSelectedFiles([])
    setPreviewUrls([])
    setResult(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleDrop = (event) => {
    event.preventDefault()
    setImages(event.dataTransfer.files)
  }

  const validate = () => {
    if (selectedFiles.length === 0) return 'Please upload at least one plantation image before starting the analysis.'
    if (latitude.trim() === '') return 'Latitude is required.'
    if (longitude.trim() === '') return 'Longitude is required.'
    if (date.trim() === '') return 'Analysis date is required.'
    const parsedLatitude = Number(latitude)
    const parsedLongitude = Number(longitude)
    if (!Number.isFinite(parsedLatitude) || parsedLatitude < -90 || parsedLatitude > 90) return 'Latitude must be between -90 and 90.'
    if (!Number.isFinite(parsedLongitude) || parsedLongitude < -180 || parsedLongitude > 180) return 'Longitude must be between -180 and 180.'
    return ''
  }

  const handleAnalyze = async (event) => {
    event.preventDefault()
    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }

    setError('')
    setLoading(true)
    try {
      const formData = new FormData()
      selectedFiles.forEach((selectedFile) => formData.append('files', selectedFile))
      const query = new URLSearchParams({ latitude, longitude, date })
      const response = await fetch(`${API_BASE_URL}/component02/assess?${query.toString()}`, {
        method: 'POST',
        body: formData,
      })
      let payload = null
      try {
        payload = await response.json()
      } catch {
        payload = null
      }
      if (!response.ok) {
        const detail = typeof payload?.detail === 'string' ? payload.detail : ''
        throw new Error(detail)
      }
      if (!payload || typeof payload !== 'object' || payload.success === false || !payload.image_analysis || !payload.climate || !payload.stress_assessment) {
        throw new Error('The API returned an incomplete assessment.')
      }
      setResult(payload)
    } catch {
      setResult(null)
      setError('Unable to connect to the Plantation Health API. Please make sure the FastAPI backend is running on port 8000.')
    } finally {
      setLoading(false)
    }
  }

  const handleNewAnalysis = () => {
    removeImage()
    setResult(null)
    setError('')
    setLatitude('6.9497')
    setLongitude('80.7891')
    setDate(getLocalDate())
  }

  const imageAnalysis = result?.image_analysis
  const analyzedImages = imageAnalysis?.images || []
  const location = result?.location
  const climate = result?.climate
  const stress = result?.stress_assessment
  const displayedPrediction = normalizeHealthPrediction(imageAnalysis?.prediction)
  const score = Number(imageAnalysis?.image_health_score)
  const healthScoreTone = healthTone(score)
  const climateRiskTone = riskTone(stress?.overall_climate_risk)
  const stressItems = [
    ['Heat Stress', stress?.heat_stress, 'sun'],
    ['Water Stress', stress?.water_stress, 'water'],
    ['Rainfall Stress', stress?.rainfall_stress, 'cloud'],
    ['Humidity Stress', stress?.humidity_stress, 'cloud'],
    ['Wind Condition', stress?.wind_condition, 'wind'],
    ['Solar Condition', stress?.solar_condition, 'sun'],
  ]

  return (
    <main className="min-h-screen bg-[#f4f8f4] text-slate-900">
      <div className="mx-auto w-full max-w-7xl px-4 py-7 sm:px-6 sm:py-10 lg:px-8">
        <div className="mb-8 max-w-3xl">
          <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-emerald-700">Climate intelligence for tea cultivation</p>
          <h2 className="text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">AI-Powered Plantation Health &amp; Climate Stress Assessment</h2>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-500">Combine visual crop assessment with live climate indicators to understand plantation health and act early on emerging stress.</p>
        </div>

        <section aria-label="Plantation Analysis" className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
          <SectionTitle eyebrow="Start an assessment" title="Plantation Analysis" description="Upload up to 5 field images and provide their observation details." icon="sparkles" />
          <form onSubmit={handleAnalyze}>
            <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
              <div>
                <label className="mb-2 block text-sm font-bold text-slate-800" htmlFor="plantation-image">Plantation Image</label>
                {previewUrls.length > 0 ? (
                  <div className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-3">
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                      {previewUrls.map((previewUrl, index) => (
                        <div className="overflow-hidden rounded-xl border border-emerald-100 bg-white" key={previewUrl}>
                          <img alt={`Selected tea plantation ${index + 1}`} className="h-28 w-full object-cover" src={previewUrl} />
                          <div className="px-2 py-2"><p className="truncate text-xs font-bold text-slate-700">Image {index + 1}</p><p className="truncate text-[10px] text-slate-400">{selectedFiles[index]?.name}</p></div>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-bold text-emerald-800">{selectedFiles.length} image{selectedFiles.length === 1 ? '' : 's'} selected (maximum 5)</p><div className="flex gap-2"><button className="rounded-lg bg-white px-3 py-2 text-xs font-bold text-emerald-800 shadow-sm transition hover:bg-emerald-100" onClick={() => fileInputRef.current?.click()} type="button">Change Images</button><button aria-label="Remove selected images" className="rounded-lg bg-red-500 px-3 py-2 text-xs font-bold text-white transition hover:bg-red-600" onClick={removeImage} type="button">Remove All</button></div></div>
                  </div>
                ) : (
                  <label className="flex min-h-64 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-emerald-200 bg-emerald-50/50 px-5 text-center transition hover:border-emerald-500 hover:bg-emerald-50 focus-within:ring-4 focus-within:ring-emerald-600/10" htmlFor="plantation-image" onDragOver={(event) => event.preventDefault()} onDrop={handleDrop}>
                    <div className="mb-4 rounded-2xl bg-white p-4 text-emerald-700 shadow-sm"><Icon name="upload" size={26} /></div>
                    <p className="font-bold text-slate-800">Upload up to 5 Plantation Images</p>
                    <p className="mt-1 text-sm text-slate-500">Select multiple field images for a more reliable health result</p>
                    <p className="mt-3 text-xs font-medium text-slate-400">JPG, JPEG, PNG or WEBP · maximum 5 images</p>
                  </label>
                )}
                <input ref={fileInputRef} accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" className="sr-only" id="plantation-image" multiple onChange={(event) => setImages(event.target.files)} type="file" />
              </div>
              <div className="grid content-start gap-4 sm:grid-cols-2 lg:grid-cols-1">
                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-800" htmlFor="latitude">Latitude</label>
                  <div className="relative"><Icon className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" name="compass" size={18} /><input className={`${fieldClass} pl-11`} id="latitude" inputMode="decimal" onChange={(event) => setLatitude(event.target.value)} value={latitude} /></div>
                </div>
                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-800" htmlFor="longitude">Longitude</label>
                  <div className="relative"><Icon className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" name="location" size={18} /><input className={`${fieldClass} pl-11`} id="longitude" inputMode="decimal" onChange={(event) => setLongitude(event.target.value)} value={longitude} /></div>
                </div>
                <div className="sm:col-span-2 lg:col-span-1">
                  <label className="mb-2 block text-sm font-bold text-slate-800" htmlFor="analysis-date">Analysis Date</label>
                  <div className="relative"><Icon className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" name="calendar" size={18} /><input className={`${fieldClass} pl-11`} id="analysis-date" onChange={(event) => setDate(event.target.value)} type="date" value={date} /></div>
                </div>
              </div>
            </div>
            {error && <div aria-live="assertive" className="mt-5 flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-800"><Icon className="mt-0.5 shrink-0" name="alert" size={18} /><p>{error}</p></div>}
            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              {result && <button className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-slate-200 px-5 text-sm font-bold text-slate-700 transition hover:border-emerald-300 hover:bg-emerald-50 focus:outline-none focus:ring-4 focus:ring-emerald-600/10" onClick={handleNewAnalysis} type="button"><Icon name="refresh" size={17} /> New Analysis</button>}
              <button className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-emerald-700 px-6 text-sm font-bold text-white shadow-lg shadow-emerald-900/15 transition hover:bg-emerald-800 focus:outline-none focus:ring-4 focus:ring-emerald-600/20 disabled:cursor-wait disabled:opacity-70" disabled={loading} type="submit"><Icon name={loading ? 'activity' : 'sparkles'} size={18} />{loading ? 'Analyzing Plantation...' : 'Analyze Plantation'}</button>
            </div>
          </form>
        </section>

        {!result && !loading && (
          <section className="mt-7 flex flex-col items-center justify-center rounded-3xl border border-dashed border-emerald-200 bg-white px-6 py-14 text-center shadow-sm" aria-live="polite">
            <div className="rounded-2xl bg-emerald-100 p-4 text-emerald-700"><Icon name="leaf" size={30} /></div>
            <h2 className="mt-5 text-xl font-black text-slate-900">Ready for Plantation Analysis</h2>
            <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">Upload a plantation image, provide the location and date, then run AI analysis.</p>
          </section>
        )}

        {loading && <div className="mt-7 flex items-center justify-center gap-3 rounded-3xl border border-emerald-100 bg-white px-6 py-10 text-sm font-bold text-emerald-800 shadow-sm" aria-live="polite"><span className="h-5 w-5 animate-spin rounded-full border-2 border-emerald-200 border-t-emerald-700" />Analyzing {selectedFiles.length} images and climate conditions...</div>}

        {result && (
          <div className="mt-7 space-y-7" aria-live="polite">
            <section className="grid gap-7 lg:grid-cols-[0.9fr_1.1fr]">
              <div className="overflow-hidden rounded-3xl border border-slate-200 bg-slate-950 shadow-sm">
                <div className="flex items-center justify-between px-5 py-4 text-white"><p className="font-bold">Analyzed Plantation Images</p><Badge tone="bg-white/10 text-white">{imageAnalysis?.image_count || selectedFiles.length} Images</Badge></div>
                <div className="grid grid-cols-2 gap-2 p-3 sm:grid-cols-3">{previewUrls.map((previewUrl, index) => <img alt={`Analyzed tea plantation ${index + 1}`} className="h-32 w-full rounded-xl object-cover sm:h-36" key={previewUrl} src={previewUrl} />)}</div>
              </div>
              <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
                <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="mb-1 text-xs font-bold uppercase tracking-[0.15em] text-emerald-700">AI visual assessment</p><h2 className="text-2xl font-black tracking-tight text-slate-950">Plantation Health</h2></div><Badge tone={healthScoreTone.badge}>{humanize(displayedPrediction)}</Badge></div>
                <div className="mt-8 grid gap-6 sm:grid-cols-[auto_1fr] sm:items-center">
                  <div className="relative flex h-40 w-40 items-center justify-center rounded-full" style={{ background: `conic-gradient(${score >= 70 ? '#10b981' : score >= 40 ? '#f59e0b' : '#ef4444'} ${Math.max(0, Math.min(100, score))}%, #e2e8f0 0)` }}>
                    <div className="flex h-32 w-32 flex-col items-center justify-center rounded-full bg-white"><span className="text-3xl font-black text-slate-950">{formatNumber(score)}</span><span className="text-xs font-bold text-slate-400">/ 100 score</span></div>
                  </div>
                  <div><p className="text-sm font-bold text-slate-500">Health confidence</p><p className="mt-1 text-4xl font-black text-slate-950">{formatNumber(imageAnalysis?.confidence)}<span className="text-xl text-slate-400">%</span></p><p className="mt-2 text-sm leading-6 text-slate-500">The visual model classified this plantation as <span className="font-bold text-slate-700">{humanize(displayedPrediction).toLowerCase()}</span>.</p></div>
                </div>
                <div className="mt-8 border-t border-slate-100 pt-5"><p className="text-sm font-bold text-slate-800">Combined AI Classification Confidence</p><ProgressBar label="Healthy" tone={statusTone('healthy')} value={imageAnalysis?.class_probabilities?.healthy} /><ProgressBar label="Low Health" tone={statusTone('low health')} value={imageAnalysis?.class_probabilities?.low_health} /></div>
                {displayedPrediction === 'low_health' && <div className="mt-6 rounded-2xl border border-red-200 bg-red-50 p-4"><div className="flex items-start gap-3"><div className="rounded-lg bg-white p-2 text-red-600"><Icon name="alert" size={18} /></div><div><p className="text-xs font-bold uppercase tracking-wide text-red-700">Why low health?</p><p className="mt-2 text-sm leading-6 text-red-900">{imageAnalysis?.health_reason || 'The AI model detected visual patterns associated with reduced tea plant health. Please inspect the affected area in the field.'}</p></div></div></div>}
                {analyzedImages.length > 0 && <div className="mt-6 border-t border-slate-100 pt-5"><p className="text-sm font-bold text-slate-800">Individual Image Results</p><div className="mt-3 grid gap-2 sm:grid-cols-2">{analyzedImages.map((image, index) => { const tone = healthTone(image.image_health_score); return <div className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2" key={`${image.file_name}-${index}`}><div className="min-w-0"><p className="truncate text-xs font-bold text-slate-700">Image {index + 1}</p><p className="truncate text-[10px] text-slate-400">{image.file_name}</p></div><Badge tone={tone.badge}>{humanize(image.prediction)}</Badge></div> })}</div></div>}
              </div>
            </section>

            <section className="grid gap-5">
              <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6"><SectionTitle title="Plantation Location" description="Observation coordinates and date." icon="location" /><div className="grid grid-cols-2 gap-3"><div className="rounded-2xl bg-slate-50 p-4"><p className="text-xs font-bold uppercase tracking-wide text-slate-400">Latitude</p><p className="mt-2 text-lg font-black text-slate-900">{formatNumber(location?.latitude, 4)}</p></div><div className="rounded-2xl bg-slate-50 p-4"><p className="text-xs font-bold uppercase tracking-wide text-slate-400">Longitude</p><p className="mt-2 text-lg font-black text-slate-900">{formatNumber(location?.longitude, 4)}</p></div><div className="col-span-2 flex items-center gap-3 rounded-2xl bg-slate-50 p-4"><Icon className="text-emerald-700" name="calendar" size={20} /><div><p className="text-xs font-bold uppercase tracking-wide text-slate-400">Analysis Date</p><p className="mt-1 font-black text-slate-900">{result.date || 'Unavailable'}</p></div></div></div></div>
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7"><SectionTitle eyebrow="Environmental conditions" title="Climate Conditions" description="Climate observations returned by the assessment service." icon="cloud" /><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5"><MetricCard icon="sun" label="Temperature" value={formatNumber(climate?.temperature_c)} unit="°C" /><MetricCard icon="water" label="Rainfall" value={formatNumber(climate?.rainfall_mm)} unit="mm" /><MetricCard icon="cloud" label="Humidity" value={formatNumber(climate?.humidity_percent)} unit="%" /><MetricCard icon="wind" label="Wind Speed" value={formatNumber(climate?.wind_speed_m_s)} unit="m/s" /><MetricCard icon="sun" label="Solar Radiation" value={formatNumber(climate?.solar_radiation_kwh_m2_day)} unit={climate?.solar_radiation_kwh_m2_day === null || climate?.solar_radiation_kwh_m2_day === undefined ? '' : 'kWh/m²/day'} note={climate?.solar_radiation_kwh_m2_day === null || climate?.solar_radiation_kwh_m2_day === undefined ? 'Unavailable for this observation' : ''} /></div><p className="mt-5 flex items-center gap-2 text-xs font-bold text-slate-400"><Icon name="cloud" size={15} /> Source: {climate?.source || 'Unavailable'}</p></section>

            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7"><SectionTitle eyebrow="Six indicator review" title="Climate Stress Assessment" description="Status indicators derived from the available climate variables." icon="alert" /><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{stressItems.map(([label, value, icon]) => { const tone = statusTone(value); return <div className={`flex items-center justify-between gap-3 rounded-2xl border p-4 ${tone.panel}`} key={label}><div className="flex items-center gap-3"><div className={`rounded-xl bg-white/80 p-2 ${tone.text}`}><Icon name={icon} size={18} /></div><p className="text-sm font-bold text-slate-800">{label}</p></div><Badge tone={tone.badge}>{humanize(value)}</Badge></div> })}</div></section>

            <section className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
              <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7"><div className="flex flex-wrap items-start justify-between gap-4"><SectionTitle eyebrow="Risk overview" title="Climate Risk Assessment" description="A combined risk score based on the climate stress assessment." icon="alert" /><Badge tone={climateRiskTone.badge}>{humanize(stress?.overall_climate_risk)}</Badge></div><div className="mt-3 flex items-end justify-between gap-4"><div><p className="text-4xl font-black text-slate-950">{formatNumber(stress?.climate_risk_score)}<span className="text-xl text-slate-400"> / 100</span></p><p className="mt-1 text-sm font-bold text-slate-500">Climate risk score</p></div><p className={`text-right text-sm font-black ${climateRiskTone.text}`}>{humanize(stress?.overall_climate_risk)} risk</p></div><div className="mt-5 h-3 overflow-hidden rounded-full bg-slate-100"><div className={`h-full rounded-full ${climateRiskTone.bar}`} style={{ width: `${Math.max(0, Math.min(100, Number(stress?.climate_risk_score) || 0))}%` }} /></div></div>
              <div className={`rounded-3xl border p-5 shadow-sm sm:p-7 ${statusTone(stress?.early_warning).panel}`}><div className="flex items-center gap-3"><div className={`rounded-xl bg-white/75 p-2 ${statusTone(stress?.early_warning).text}`}><Icon name="alert" size={21} /></div><p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Early Warning</p></div><p className={`mt-5 text-2xl font-black ${statusTone(stress?.early_warning).text}`}>{stress?.early_warning || 'Unavailable'}</p><p className="mt-2 text-sm leading-6 text-slate-600">Use this signal alongside field observations when planning the next plantation action.</p></div>
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7"><SectionTitle eyebrow="Next best actions" title="AI Recommendations" description="Recommendations generated from this assessment." icon="sparkles" /><div className="grid gap-3 md:grid-cols-2">{Array.isArray(result.recommendations) && result.recommendations.length > 0 ? result.recommendations.map((recommendation, index) => <article className="rounded-2xl border border-emerald-100 bg-emerald-50/70 p-4" key={`${recommendation}-${index}`}><div className="flex items-start gap-3"><div className="mt-0.5 rounded-lg bg-white p-2 text-emerald-700"><Icon name="check" size={17} /></div><div><p className="text-xs font-bold uppercase tracking-wide text-emerald-700">AI Recommendation</p><p className="mt-2 text-sm leading-6 text-slate-700">{recommendation}</p></div></div></article>) : <p className="text-sm text-slate-500">No recommendations were returned for this assessment.</p>}</div></section>

            <section className="rounded-3xl bg-emerald-950 p-5 text-white shadow-sm sm:p-7"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="mb-1 text-xs font-bold uppercase tracking-[0.16em] text-emerald-300">Assessment complete</p><h2 className="text-2xl font-black tracking-tight">Analysis Summary</h2></div><Icon className="text-emerald-300" name="leaf" size={27} /></div><div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">{[['Plantation Health', humanize(displayedPrediction)], ['Climate Risk', humanize(stress?.overall_climate_risk)], ['Early Warning', stress?.early_warning || 'Unavailable'], ['Data Source', climate?.source || 'Unavailable'], ['AI Model', imageAnalysis?.model || 'Unavailable']].map(([label, value]) => <div className="rounded-2xl bg-white/10 p-4" key={label}><p className="text-xs font-bold uppercase tracking-wide text-emerald-300">{label}</p><p className="mt-2 text-sm font-bold text-white">{value}</p></div>)}</div></section>
          </div>
        )}
      </div>
    </main>
  )
}

export default PlantHealth
