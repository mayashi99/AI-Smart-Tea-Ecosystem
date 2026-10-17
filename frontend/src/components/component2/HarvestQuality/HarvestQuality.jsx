import { useEffect, useRef, useState } from 'react';
import { CLIMATE_LOCATIONS, getSriLankaDate, harvestPeriod, mapClimateResponse } from '../IntelligentHarvestPlanning/planningClimate';
import { summarizeHarvestReadiness } from '../IntelligentHarvestPlanning/harvestPhotos';
import { assessQuality } from './qualityAssessment';
import './HarvestQuality.css';

const API = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
const GROWN_TYPES = { 'HIGH grown': ['Nuwara Eliya', 'Dimbula', 'Uva'], 'MID grown': ['Badulla', 'Kandy', 'Matale', 'Nawalapitiya'], 'LOW grown': ['Galle', 'Kalutara', 'Kegalle', 'Matara', 'Ratnapura'] };
const panel = 'hq-card';
const display = (value, unit = '') => Number.isFinite(value) ? `${value}${unit}` : 'Unavailable';

function QualityIcon({ name = 'leaf', size = 22 }) {
  const paths = {
    leaf: <><path d="M20 4C9 3 3 9 5 15c2 7 13 7 15-11Z" /><path d="M4 21 15 10" /></>,
    upload: <><path d="M12 16V3m-5 5 5-5 5 5M4 15v5a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5" /></>,
    arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
    sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1" /></>,
    chart: <><path d="M4 3v17h17M8 16v-5m5 5V7m5 9v-7" /></>,
    check: <><circle cx="12" cy="12" r="9" /><path d="m8 12 3 3 5-6" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function ImagePreview({ file }) {
  const image = useRef(null);
  useEffect(() => {
    const url = URL.createObjectURL(file);
    image.current.src = url;
    return () => URL.revokeObjectURL(url);
  }, [file]);
  return <img ref={image} alt={file.name} />;
}

async function readResponse(response) {
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Analysis failed. Please retry.');
  return data;
}

export default function HarvestQuality() {
  const [location, setLocation] = useState('Nuwara Eliya');
  const [acres, setAcres] = useState('1');
  const [files, setFiles] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const request = useRef(null);
  const fileInput = useRef(null);
  const [dragging, setDragging] = useState(false);
  function selectImages(selected) {
    if (loading) return;
    if (selected.length > 5 || selected.some(file => !['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || !file.size || file.size > 10 * 1024 * 1024)) {
      setError('Choose up to 5 JPG, PNG or WEBP images, no larger than 10 MB each.');
      return;
    }
    setFiles(selected); setResult(null); setError('');
  }
  useEffect(() => () => request.current?.abort(), []);

  async function analyze(event) {
    event.preventDefault();
    setResult(null);
    setError('');
    if (!files.length || files.length > 5 || files.some(file => !/\.(jpg|jpeg|png|webp)$/i.test(file.name) || file.size === 0 || file.size > 10 * 1024 * 1024)) {
      setError('Upload 1–5 non-empty JPG, PNG or WEBP plantation images, up to 10 MB each.');
      return;
    }
    if (!Number.isFinite(Number(acres)) || Number(acres) <= 0) { setError('Enter a plantation area greater than zero.'); return; }
    const controller = new AbortController();
    request.current = controller;
    const timeout = setTimeout(() => controller.abort(), 120000);
    setLoading(true);
    try {
      const today = getSriLankaDate();
      const [latitude, longitude] = CLIMATE_LOCATIONS[location];
      const params = new URLSearchParams({ latitude, longitude });
      const form = new FormData();
      files.forEach(file => form.append('files', file));
      const assessment = await fetch(`${API}/component02/assess?${params}&date=${today}`, {
        method: 'POST', body: form, signal: controller.signal,
      }).then(readResponse);
      const readinessResults = [];
      for (const file of files) {
        const body = new FormData();
        body.append('file', file);
        const data = await fetch(`${API}/component02/harvest-readiness/predict`, { method: 'POST', body, signal: controller.signal }).then(readResponse);
        readinessResults.push({ data });
      }
      const readiness = summarizeHarvestReadiness(readinessResults);
      if (readiness.failedCount) throw new Error('Some harvest readiness results are incomplete. Please retry.');
      const quality = assessQuality(assessment, today, readiness.readyPercent);
      let yieldData = null;
      let yieldError = '';
      const period = harvestPeriod(today);
      if (readiness.label === 'Harvest Ready') {
        try {
          const climateInputs = mapClimateResponse({ success: true, climate_data_date: assessment.climate?.data_date, climate: assessment.climate }, today);
          if (Object.values(climateInputs).some(value => !Number.isFinite(value))) throw new Error('Complete current climate data is required for yield prediction.');
          const grownType = Object.keys(GROWN_TYPES).find(type => GROWN_TYPES[type].includes(location));
          yieldData = await fetch(`${API}/component02/expected-yield/predict`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
            body: JSON.stringify({ Year: period.year, Month_Number: period.month, Week_Number: period.week, ...climateInputs, Location: location, Grown_Type: grownType }),
          }).then(readResponse);
          if (!Number.isFinite(yieldData.predicted_kg_per_Acre) || yieldData.predicted_kg_per_Acre < 0) throw new Error('The yield model returned an invalid estimate.');
        } catch (err) {
          yieldData = null;
          yieldError = err.name === 'AbortError' ? 'Yield prediction timed out. Please retry.' : err.message;
        }
      }
      setResult({ assessment, quality, location, readiness, yieldData, yieldError, acres: Number(acres), period });
    } catch (err) {
      controller.abort();
      setError(err.name === 'AbortError' ? 'Analysis timed out. Please try again.' : err instanceof TypeError ? 'Cannot connect to the backend. Check that it is running on port 8000.' : err.message);
    } finally {
      clearTimeout(timeout);
      setLoading(false);
    }
  }

  const assessment = result?.assessment;
  const isHarvestReady = result?.readiness.label === 'Harvest Ready';
  return (
    <main className="hq-page">
      <div className="hq-container">
        <h1 className="sr-only">Harvest Quality Potential</h1>
        <div className="hq-workspace">
        <form className="hq-card hq-form" onSubmit={analyze}>
          <div className="hq-section-heading"><div><span className="hq-overline">01 / YOUR PLANTATION</span><h2>Set up your assessment</h2></div><span className="hq-step-icon"><QualityIcon /></span></div>
          <p className="hq-subtitle">A few field details. A clearer picture of your harvest.</p>
          <fieldset disabled={loading}>
            <legend className="sr-only">Assessment details</legend>
            <div className="hq-fields">
              <div><label htmlFor="quality-location">Plantation location</label>
                <select id="quality-location" value={location} onChange={event => { setLocation(event.target.value); setResult(null); setError(''); }}>
                  {Object.entries(GROWN_TYPES).map(([type, names]) => <optgroup key={type} label={type}>{names.map(name => <option key={name}>{name}</option>)}</optgroup>)}
                </select>
              </div>
              <div><label htmlFor="quality-acres">Plantation area</label><div className="hq-unit-input"><input id="quality-acres" type="number" min="0.01" step="any" required value={acres} onChange={event => { setAcres(event.target.value); setResult(null); }} /><span>acres</span></div></div>
            </div>
            <p className="hq-field-note">Today’s assessment · Sri Lanka time · Weather uses town coordinates.</p>
            <div className="hq-upload-heading"><label htmlFor="quality-images">Plantation images</label><span>{files.length} / 5 images</span></div>
            <div className={`hq-dropzone ${dragging ? 'hq-dragging' : ''}`} onDragOver={event => { event.preventDefault(); if (!loading) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); selectImages(Array.from(event.dataTransfer.files)); }}>
              <input ref={fileInput} id="quality-images" type="file" accept=".jpg,.jpeg,.png,.webp" multiple className="sr-only" onChange={event => { selectImages(Array.from(event.target.files || [])); event.target.value = ''; }} />
              <span className="hq-upload-icon"><QualityIcon name="upload" size={25} /></span>
              <strong>Give your harvest a closer look</strong><p>Drag and drop your plantation photos here</p>
              <button className="hq-browse" type="button" onClick={() => fileInput.current.click()}>Browse images <span>↗</span></button>
              <small>JPG, PNG or WEBP · Up to 10 MB per image</small>
            </div>
            {files.length > 0 && <div className="hq-previews">{files.map((file, index) => <div key={`${file.name}-${index}`}><ImagePreview file={file} /><button type="button" aria-label={`Remove ${file.name}`} onClick={() => { setFiles(files.filter((_, i) => i !== index)); setResult(null); }}>×</button><span title={file.name}>{file.name}</span></div>)}</div>}
            <button className="hq-submit" type="submit" disabled={loading}>{loading ? <><span className="hq-spinner" /> Analyzing your plantation…</> : <><QualityIcon name="chart" size={19} /> Analyze Harvest Quality <QualityIcon name="arrow" size={19} /></>}</button>
            <p className="hq-submit-note">Health, readiness, climate and yield — analyzed together.</p>
          </fieldset>
          {error && <p role="alert" className="hq-error">{error}</p>}
        </form>
        <aside className="hq-insight-panel" aria-live="polite" aria-busy={loading}>
          {result ? <>
            <span className="hq-overline">02 / YOUR ASSESSMENT</span>
            <h2>Your harvest results</h2>
            <p className="hq-subtitle">{result.location} · {result.acres} acres</p>
            <dl className="hq-summary-metrics">
              <div><dt>Plantation health</dt><dd>{display(assessment.image_analysis.image_health_score, '%')}</dd></div>
              <div><dt>Harvest readiness</dt><dd>{display(result.readiness.readyPercent, '%')}</dd><small>{result.readiness.label}</small></div>
              <div><dt>Climate</dt><dd>{result.quality.climateLabel}</dd></div>
            </dl>
            <div className="hq-side-outcome"><section className={`${panel} hq-quality-result`} data-quality={result.quality.potential}>
              <h2 className="text-xl font-bold">Harvest Quality Potential</h2>
              <p className="mt-3 text-3xl font-bold text-emerald-800">{result.quality.potential}</p>
              <p className="mt-2 text-sm">{result.location} · Climate data date: {assessment.climate?.data_date}</p>
              <ul className="mt-4 list-disc space-y-2 pl-5">{result.quality.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
            </section>
            {isHarvestReady && <section className={`${panel} hq-yield-result`}><span className="hq-step-icon"><QualityIcon name="chart" /></span><h2 className="text-xl font-bold">Expected Tea Yield</h2>
              {result.yieldData ? <><p className="mt-3 text-3xl font-bold text-emerald-800">{(result.yieldData.predicted_kg_per_Acre * result.acres).toLocaleString(undefined, { maximumFractionDigits: 2 })} kg total</p><p className="mt-2">{result.yieldData.predicted_kg_per_Acre} kg/acre × {result.acres} acres</p></> : <p className="mt-3 text-amber-800">Yield unavailable: {result.yieldError}</p>}
              <p className="mt-3 text-sm text-slate-500">CatBoost estimate · {result.period.year}, month {result.period.month}, week bucket {result.period.week}. Uses today's climate as model inputs; this is not a measured harvest quantity or a weekly weather forecast. Total assumes similar conditions across the entered area.</p>
            </section>}
            </div>
          </> : <>
          <span className="hq-overline">02 / THE BIGGER PICTURE</span><h2>One assessment.<br />Four useful insights.</h2><p className="hq-subtitle">From the condition of your leaves to the potential of your next harvest.</p>
          <div className="hq-insight-list">{[['leaf', 'Plantation health', 'Understand the condition of your tea plants.'], ['check', 'Harvest readiness', 'Check whether your leaves are ready to pick.'], ['sun', 'Climate conditions', 'Assess current climate conditions and plantation stress.'], ['chart', 'Yield & quality potential', 'Estimate your yield and see the reasons behind your recommendation.']].map(([icon, title, description]) => <div key={title}><span><QualityIcon name={icon} /></span><div><h3>{title}</h3><p>{description}</p></div></div>)}</div>
          </>}
          {!result && <div className={`hq-status ${loading ? 'hq-status-loading' : ''}`}><span className={loading ? 'hq-spinner' : 'hq-status-dot'} /><div><strong>{loading ? 'Building your harvest outlook' : 'Ready when you are'}</strong><p>{loading ? 'Checking plantation health, readiness, climate and yield. This may take a moment.' : 'Add your images and field details to get started.'}</p></div></div>}
        </aside>
        </div>
        <details className="hq-method"><summary><span>ⓘ</span> Understanding your assessment <span className="hq-method-toggle">Method & limitations</span></summary><p>This is a preliminary rule-based assessment, not a validated tea-quality prediction. Premium requires health ≥80%, readiness ≥85%, Good climate. Health or readiness below 60%, or Poor climate, gives Poor potential; intermediate conditions give Moderate. These thresholds require validation against actual tea quality. Missing or outdated climate data prevents confirmation.</p></details>
        <footer className="hq-footer"><span>AI Smart Tea Ecosystem</span><span>Thoughtful decisions. Healthier harvests.</span></footer>
      </div>
    </main>
  );
}
