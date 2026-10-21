import { useEffect, useRef, useState } from 'react';
import { CLIMATE_LOCATIONS, getSriLankaDate, harvestPeriod, mapClimateResponse } from '../IntelligentHarvestPlanning/planningClimate';
import { summarizeHarvestReadiness, validateTeaPhotos } from '../IntelligentHarvestPlanning/harvestPhotos';
import { assessQuality } from './qualityAssessment';
const API = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
const GROWN_TYPES = { 'HIGH grown': ['Nuwara Eliya', 'Dimbula', 'Uva'], 'MID grown': ['Badulla', 'Kandy', 'Matale', 'Nawalapitiya'], 'LOW grown': ['Galle', 'Kalutara', 'Kegalle', 'Matara', 'Ratnapura'] };
const panel = "hq-card [border:1px_solid_#e0e6df] bg-[white] p-[28px] rounded-[17px] [box-shadow:0_3px_8px_#1a3e2403] min-w-[0] max-[800.01px]:p-[22px] max-[600.01px]:p-[21px]";
const display = (value, unit = '') => Number.isFinite(value) ? `${value}${unit}` : 'Unavailable';

function QualityIcon({ name = 'leaf', size = 22 }) {
  const paths = {
    leaf: <><path d="M20 4C9 3 3 9 5 15c2 7 13 7 15-11Z" /><path d="M4 21 15 10" /></>,
    upload: <><path d="M12 16V3m-5 5 5-5 5 5M4 15v5a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5" /></>,
    arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
    sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1" /></>,
    chart: <><path d="M4 3v17h17M8 16v-5m5 5V7m5 9v-7" /></>,
    check: <><circle cx="12" cy="12" r="9" /><path d="m8 12 3 3 5-6" /></>,
    calendar: <><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M8 3v4m8-4v4M4 10h16" /></>,
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
  const [imageError, setImageError] = useState('');
  const [validatingImages, setValidatingImages] = useState(false);
  const imageValidation = useRef(null);
  const request = useRef(null);
  const fileInput = useRef(null);
  const [dragging, setDragging] = useState(false);
  async function selectImages(selected) {
    if (loading || imageValidation.current || !selected.length) return;
    setFiles([]); setResult(null); setError(''); setImageError('');
    if (selected.length > 5 || selected.some(file => !['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || !file.size || file.size > 10 * 1024 * 1024)) {
      setImageError('Choose up to 5 JPG, PNG or WEBP images, no larger than 10 MB each.');
      return;
    }
    const controller = new AbortController();
    imageValidation.current = controller;
    setValidatingImages(true);
    try {
      await validateTeaPhotos(selected, API, controller.signal);
      if (!controller.signal.aborted) setFiles(selected);
    } catch (err) {
      if (!controller.signal.aborted) setImageError(err instanceof TypeError
        ? 'Unable to check images. Please make sure the backend is running and try again.'
        : err.message);
    } finally {
      if (!controller.signal.aborted) setValidatingImages(false);
      imageValidation.current = null;
    }
  }
  useEffect(() => () => {
    request.current?.abort();
    imageValidation.current?.abort();
  }, []);

  async function analyze(event) {
    event.preventDefault();
    if (loading || imageValidation.current || imageError) return;
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
      let forecast = null;
      let forecastError = '';
      try {
        const forecastParams = new URLSearchParams({ latitude, longitude });
        forecast = await fetch(`${API}/component02/harvest-forecast?${forecastParams}`, { signal: controller.signal }).then(readResponse);
      } catch (err) {
        forecastError = err.name === 'AbortError' ? 'The three-day weather forecast timed out.' : 'The three-day weather forecast is unavailable.';
      }
      const quality = assessQuality(assessment, today, readiness.readyPercent, forecast);
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
      setResult({ assessment, quality, location, readiness, forecast, forecastError, yieldData, yieldError, acres: Number(acres), period });
    } catch (err) {
      controller.abort();
      setError(err.name === 'AbortError' ? 'Analysis timed out. Please try again.' : err instanceof TypeError ? 'Cannot connect to the backend. Check that it is running on port 8000.' : err.message);
    } finally {
      clearTimeout(timeout);
      setLoading(false);
    }
  }

  const assessment = result?.assessment;
  return (
    <main className="relative bg-[linear-gradient(135deg,rgba(229,245,224,0.68),rgba(241,235,218,0.62))] text-[#243b32] min-h-[100vh] p-[28px_28px_20px] [font-family:Inter,ui-sans-serif,system-ui,sans-serif] [&_h2]:text-[21px] [&_h2]:tracking-[-.55px] [&_h2]:font-[650] [&_h2]:leading-[1.4] [&_button:focus-visible]:[outline:2px_solid_#719a56] [&_button:focus-visible]:outline-offset-[4px] max-[800.01px]:p-[20px_18px] max-[600.01px]:p-[16px_14px] motion-reduce:[&_*]:[transition:none]!">
      <div className="max-w-[1180px] m-[auto] min-[1500px]:max-w-[1240px]">
        <h1 className="sr-only">Harvest Quality Potential</h1>
        <div className="grid grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)] gap-[24px] mt-[0] items-stretch max-[800.01px]:grid-cols-[1.2fr_1fr] max-[800.01px]:gap-[16px] max-[600.01px]:grid-cols-[1fr] max-[600.01px]:mt-[0]">
        <form className="hq-card [border:1px_solid_#e0e6df] bg-[white] p-[28px] rounded-[17px] [box-shadow:0_3px_8px_#1a3e2403] min-w-[0] max-[800.01px]:p-[22px] max-[600.01px]:p-[21px] [&_fieldset]:[border:0] [&_fieldset]:m-[24px_0_0] [&_fieldset]:p-[0] [&_fieldset]:min-w-[0] [&_fieldset:disabled]:opacity-[.65] [&_label]:block [&_label]:text-[12px] [&_label]:font-[600] [&_label]:mb-[8px] [&_label]:text-[#3d5144] [&_select]:w-[100%] [&_select]:h-[45px] [&_select]:[border:1px_solid_#dce3db] [&_select]:rounded-[9px] [&_select]:bg-[#fcfdfb] [&_select]:p-[0_13px] [&_select]:text-[12px] [&_select]:text-[#344c3c] [&_select]:[outline:none] [&_input[type=number]]:w-[100%] [&_input[type=number]]:h-[45px] [&_input[type=number]]:[border:1px_solid_#dce3db] [&_input[type=number]]:rounded-[9px] [&_input[type=number]]:bg-[#fcfdfb] [&_input[type=number]]:p-[0_13px] [&_input[type=number]]:text-[12px] [&_input[type=number]]:text-[#344c3c] [&_input[type=number]]:[outline:none] [&_select:focus]:[border-color:#6e9565] [&_select:focus]:[box-shadow:0_0_0_3px_#639c6414] [&_input[type=number]:focus]:[border-color:#6e9565] [&_input[type=number]:focus]:[box-shadow:0_0_0_3px_#639c6414]" onSubmit={analyze}>
          <div className="flex justify-between items-center gap-[12px] [&_h2]:mt-[7px] max-[600.01px]:[&_h2]:text-[20px]"><div><span className="text-[9px] font-[700] tracking-[1.8px] text-[#6f8976]">01 / YOUR PLANTATION</span><h2>Set up your assessment</h2></div><span className="hq-step-icon inline-flex items-center justify-center w-[40px] h-[40px] rounded-[12px] bg-[#f0f5eb] text-[#5d7d4e] shrink-0"><QualityIcon /></span></div>
          <p className="hq-subtitle text-[12px] text-[#7a867e] leading-[1.8] mt-[8px]">A few field details. A clearer picture of your harvest.</p>
          <fieldset disabled={loading || validatingImages}>
            <legend className="sr-only">Assessment details</legend>
            <div className="grid grid-cols-[1.6fr_1fr] gap-[16px] max-[800.01px]:grid-cols-[1fr] max-[600.01px]:grid-cols-[1.5fr_1fr] max-[600.01px]:gap-[12px]">
              <div><label htmlFor="quality-location">Plantation location</label>
                <select id="quality-location" value={location} onChange={event => { setLocation(event.target.value); setResult(null); setError(''); }}>
                  {Object.entries(GROWN_TYPES).map(([type, names]) => <optgroup key={type} label={type}>{names.map(name => <option key={name}>{name}</option>)}</optgroup>)}
                </select>
              </div>
              <div><label htmlFor="quality-acres">Plantation area</label><div className="relative [&_input]:pr-[55px]! [&>span]:absolute [&>span]:right-[12px] [&>span]:top-[15px] [&>span]:text-[10px] [&>span]:text-[#819080] [&>span]:pointer-events-none"><input id="quality-acres" type="number" min="0.01" step="any" required value={acres} onChange={event => { setAcres(event.target.value); setResult(null); }} /><span>acres</span></div></div>
            </div>
            <p className="text-[10px] text-[#8a948a] mt-[11px] leading-[1.7]">Today’s assessment · Sri Lanka time · Weather uses town coordinates.</p>
            <div className="flex items-center justify-between mt-[24px] [&>span]:text-[10px] [&>span]:text-[#8b9789]"><label htmlFor="quality-images">Plantation images</label><span>{files.length} / 5 images</span></div>
            <div className={`flex flex-col items-center justify-center text-center min-h-[213px] p-[22px_16px] [border:1.5px_dashed_#cbd8c7] rounded-[12px] bg-[#fafcf8] [transition:background_.2s,border-color_.2s] [&.hq-dragging]:bg-[#eaf3e5] [&.hq-dragging]:[border-color:#57854c] [&:focus-within]:[outline:2px_solid_#72996a] [&:focus-within]:outline-offset-[3px] [&_strong]:text-[12px] [&_strong]:font-[600] [&_p]:text-[11px] [&_p]:text-[#8a9486] [&_p]:mt-[5px] [&_small]:text-[9px] [&_small]:text-[#899580] ${dragging ? "hq-dragging" : ""}`} aria-busy={validatingImages} onDragOver={event => { event.preventDefault(); if (!loading && !validatingImages) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); selectImages(Array.from(event.dataTransfer.files)); }}>
              <input ref={fileInput} id="quality-images" type="file" accept=".jpg,.jpeg,.png,.webp" multiple className="sr-only" onChange={event => { selectImages(Array.from(event.target.files || [])); event.target.value = ''; }} />
              <span className="w-[43px] h-[43px] grid place-items-center rounded-[12px] bg-[#eef3e8] text-[#6c8b55] mb-[12px]"><QualityIcon name="upload" size={25} /></span>
              <strong>Give your harvest a closer look</strong><p>Drag and drop your plantation photos here</p>
              <button className="text-[11px] font-[650] text-[#45653e] bg-[white] [border:1px_solid_#d9e2d2] rounded-[7px] p-[8px_15px] m-[13px_0] cursor-pointer flex gap-[15px] [&:hover]:bg-[#f0f5eb]" type="button" onClick={() => fileInput.current.click()}>Browse images <span>↗</span></button>
              <small>JPG, PNG or WEBP · Up to 10 MB per image</small>
            </div>
            {files.length > 0 && <div className="flex gap-[10px] mt-[13px] flex-wrap [&>div]:relative [&>div]:w-[82px] [&>div]:min-w-[0] [&_img]:h-[65px] [&_img]:w-[82px] [&_img]:object-cover [&_img]:rounded-[8px] [&_button]:absolute [&_button]:right-[3px] [&_button]:top-[3px] [&_button]:[border:0] [&_button]:rounded-[50%] [&_button]:w-[20px] [&_button]:h-[20px] [&_button]:bg-[white] [&_button]:text-[#455a45] [&_button]:cursor-pointer [&_span]:block [&_span]:text-[9px] [&_span]:overflow-hidden [&_span]:whitespace-nowrap [&_span]:text-ellipsis [&_span]:mt-[4px] [&_span]:text-[#7e8d7c]">{files.map((file, index) => <div key={`${file.name}-${index}`}><ImagePreview file={file} /><button type="button" aria-label={`Remove ${file.name}`} onClick={() => { setFiles(files.filter((_, i) => i !== index)); setResult(null); }}>×</button><span title={file.name}>{file.name}</span></div>)}</div>}
            {validatingImages && <p role="status" className="text-[10px] text-[#8a948a] mt-[11px] leading-[1.7]">Checking images for tea leaves…</p>}
            {imageError && <p role="alert" className="bg-[#fff1ed] [border:1px_solid_#f2d9cc] text-[#a24a32] rounded-[10px] p-[13px] text-[12px] mt-[15px]">{imageError}</p>}
            <button className="w-[100%] flex items-center justify-center gap-[11px] min-h-[47px] bg-[#23543b] text-[white] [border:1px_solid_#23543b] rounded-[9px] mt-[23px] text-[12px] font-[600] cursor-pointer [box-shadow:0_4px_8px_#23543b12] [transition:background_.15s] [&:hover]:bg-[#153f2a] [&>svg:last-child]:ml-[auto] [&>svg:first-child]:mr-[auto] [&:disabled]:cursor-wait" type="submit" disabled={loading || validatingImages || !!imageError || !files.length}>{validatingImages ? <><span className="h-[17px] w-[17px] shrink-0 [border:2px_solid_#a9b99d] [border-top-color:transparent] rounded-[50%] animate-spin [animation-duration:0.8s] mt-[2px] motion-reduce:animate-none" /> Checking tea images…</> : loading ? <><span className="h-[17px] w-[17px] shrink-0 [border:2px_solid_#a9b99d] [border-top-color:transparent] rounded-[50%] animate-spin [animation-duration:0.8s] mt-[2px] motion-reduce:animate-none" /> Analyzing your plantation…</> : <><QualityIcon name="chart" size={19} /> Analyze Harvest Quality <QualityIcon name="arrow" size={19} /></>}</button>
            <p className="text-center text-[#8b9589] text-[9px] mt-[11px]">Health, readiness, climate and yield — analyzed together.</p>
          </fieldset>
          {error && <p role="alert" className="bg-[#fff1ed] [border:1px_solid_#f2d9cc] text-[#a24a32] rounded-[10px] p-[13px] text-[12px] mt-[15px]">{error}</p>}
        </form>
        <aside className="p-[30px_29px_25px] bg-[#edf1e9] [border:1px_solid_#e2e8dc] rounded-[17px] flex flex-col [&&_h2]:text-[26px] [&&_h2]:tracking-[-.8px] [&&_h2]:leading-[1.25] [&&_h2]:mt-[13px] [&&_h2]:text-[#294b34] [&&>.hq-subtitle]:max-w-[300px] [&&>.hq-subtitle]:mt-[12px] max-[800.01px]:p-[22px] max-[800.01px]:[&&_h2]:text-[23px] max-[600.01px]:p-[24px] max-[600.01px]:[&&_h2_br]:hidden" aria-live="polite" aria-busy={loading}>
          {result ? <>
            <span className="text-[9px] font-[700] tracking-[1.8px] text-[#6f8976]">02 / YOUR ASSESSMENT</span>
            <h2>Your harvest results</h2>
            <p className="hq-subtitle text-[12px] text-[#7a867e] leading-[1.8] mt-[8px]">{result.location} · {result.acres} acres</p>
            <dl className="grid grid-cols-[repeat(3,minmax(0,1fr))] gap-[10px] m-[22px_0] [&>div]:p-[12px_10px] [&>div]:bg-[#ffffffa6] [&>div]:[border:1px_solid_#dce6d4] [&>div]:rounded-[10px] [&>div]:min-w-[0] [&_dt]:text-[10px] [&_dt]:text-[#6f8068] [&_dt]:leading-[1.5] [&_dd]:text-[22px] [&_dd]:font-[650] [&_dd]:tracking-[-.5px] [&_dd]:text-[#345738] [&_dd]:m-[8px_0_0] [&_small]:block [&_small]:text-[9px] [&_small]:text-[#728269] [&_small]:mt-[5px] max-[380.01px]:grid-cols-[1fr] max-[380.01px]:[&_dd]:text-[24px]">
              <div><dt>Plantation health</dt><dd>{display(assessment.image_analysis.image_health_score, '%')}</dd></div>
              <div><dt>Harvest readiness</dt><dd>{display(result.readiness.readyPercent, '%')}</dd><small>{result.readiness.label}</small></div>
              <div><dt>Climate</dt><dd>{result.quality.climateLabel}</dd></div>
            </dl>
            <div className="grid gap-[16px] [&&&_.hq-card]:p-[20px] [&&&_h2]:text-[14px] [&&&_h2]:mt-[0] [&&&_h2]:tracking-[0] [&&&_.hq-yield-result>p:first-of-type]:text-[28px] [&&&_.hq-quality-result>p:nth-child(3)]:text-[10px] [&&&_.hq-quality-result_li]:text-[11px] [&&&_.hq-quality-result>p:nth-child(2)]:text-[32px]"><section className={`${panel} hq-quality-result [&]:bg-[#eef4e8] [&]:[border-color:#d9e4cf] [&&[data-quality=Moderate]]:bg-[#fcf7e9] [&&[data-quality=Moderate]]:[border-color:#ede2c0] [&&[data-quality=Low]]:bg-[#fff2ed] [&&[data-quality=Low]]:[border-color:#f0d8cd] [&&[data-quality='Unable_to_confirm']]:bg-[#f0f2f3] [&&[data-quality='Unable_to_confirm']]:[border-color:#dde1e4] [&&_h2]:text-[14px] [&&_h2]:font-[600] [&&>p:nth-child(2)]:text-[36px] [&&>p:nth-child(2)]:tracking-[-1px] [&&>p:nth-child(2)]:text-[#3d6333] [&&[data-quality=Moderate]>p:nth-child(2)]:text-[#93712c] [&&[data-quality=Low]>p:nth-child(2)]:text-[#a9513a] [&&_li]:text-[12px] [&&_li]:leading-[1.8] [&&_li]:text-[#62705c]`} data-quality={result.quality.potential}>
              <h2 className="text-xl font-bold">Harvest Quality Potential</h2>
              <p className="mt-3 text-3xl font-bold text-emerald-800">{result.quality.potential}</p>
              <p className="mt-2 text-sm">{result.location} · Climate data date: {assessment.climate?.data_date}</p>
              <ul className="mt-4 list-disc space-y-2 pl-5">{result.quality.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
            </section>
            <section className="hq-card bg-[#fff] [border-color:#d9e4cf] p-[20px] rounded-[14px] [box-shadow:0_3px_8px_#1a3e2403]">
              <div className="flex items-start gap-[11px]">
                <span className="w-[34px] h-[34px] shrink-0 grid place-items-center rounded-[10px] bg-[#eaf3e4] text-[#4b783f]"><QualityIcon name="calendar" size={18} /></span>
                <div><p className="text-[9px] font-[700] tracking-[1.4px] text-[#6f8976]">HARVEST TIMING</p><h2 className="!mt-[3px]">{result.quality.harvestPlan.title}</h2></div>
              </div>
              {result.quality.harvestPlan.date && <p className="mt-[14px] !text-[24px] font-[700] tracking-[-.45px] text-[#315c35]">{result.quality.harvestPlan.date}</p>}
              <p className="mt-[7px] text-[11px] leading-[1.7] text-[#62705c]">{result.quality.harvestPlan.detail}</p>
              <span className="inline-flex mt-[13px] rounded-full bg-[#eef5e9] px-[10px] py-[5px] text-[10px] font-[650] text-[#537548]">{result.quality.harvestPlan.status}</span>
              {result.forecastError && <p className="mt-[10px] text-[10px] leading-[1.6] text-[#917052]">{result.forecastError}</p>}
            </section>
            </div>
          </> : <>
          <span className="text-[9px] font-[700] tracking-[1.8px] text-[#6f8976]">02 / THE BIGGER PICTURE</span><h2>One assessment.<br />Four useful insights.</h2><p className="hq-subtitle text-[12px] text-[#7a867e] leading-[1.8] mt-[8px]">From the condition of your leaves to the potential of your next harvest.</p>
          <div className="mt-[25px] grid gap-[22px] [&>div]:flex [&>div]:gap-[14px] [&>div]:items-start [&>div>span]:grid [&>div>span]:place-items-center [&>div>span]:shrink-0 [&>div>span]:w-[37px] [&>div>span]:h-[37px] [&>div>span]:bg-[#ffffffa6] [&>div>span]:[border:1px_solid_#dce6d4] [&>div>span]:rounded-[10px] [&>div>span]:text-[#6c8658] [&_h3]:text-[12px] [&_h3]:font-[650] [&_h3]:text-[#3e573d] [&_h3]:m-[1px_0_5px] [&_p]:text-[11px] [&_p]:leading-[1.7] [&_p]:text-[#83907b] [&_p]:max-w-[250px] max-[800.01px]:gap-[19px] max-[600.01px]:gap-[17px] max-[600.01px]:mb-[20px] max-[600.01px]:[&_p]:max-w-[none]">{[['leaf', 'Plantation health', 'Understand the condition of your tea plants.'], ['check', 'Harvest readiness', 'Check whether your leaves are ready to pick.'], ['sun', 'Climate conditions', 'Assess current climate conditions and plantation stress.'], ['chart', 'Yield & quality potential', 'Estimate your yield and see the reasons behind your recommendation.']].map(([icon, title, description]) => <div key={title}><span><QualityIcon name={icon} /></span><div><h3>{title}</h3><p>{description}</p></div></div>)}</div>
          </>}
          {!result && <div className={`flex gap-[10px] [border-top:1px_solid_#d6dfd0] mt-[auto] pt-[20px] items-start [&_strong]:text-[11px] [&_strong]:text-[#526c49] [&_p]:text-[10px] [&_p]:leading-[1.6] [&_p]:text-[#8a957f] [&_p]:mt-[4px] max-[800.01px]:mt-[25px] max-[600.01px]:mt-[0] ${loading ? "hq-status-loading" : ""}`}><span className={loading ? "h-[17px] w-[17px] shrink-0 [border:2px_solid_#a9b99d] [border-top-color:transparent] rounded-[50%] animate-spin [animation-duration:0.8s] mt-[2px] motion-reduce:animate-none" : "w-[6px] h-[6px] rounded-[50%] bg-[#90a871] shrink-0 mt-[7px]"} /><div><strong>{loading ? 'Building your harvest outlook' : 'Ready when you are'}</strong><p>{loading ? 'Checking plantation health, readiness, climate and yield. This may take a moment.' : 'Add your images and field details to get started.'}</p></div></div>}
        </aside>
        </div>
        <details className="[&_summary:focus-visible]:[outline:2px_solid_#719a56] [&_summary:focus-visible]:outline-offset-[4px] mt-[25px] [border:1px_solid_#e1e6db] rounded-[10px] bg-[#f0f3ec] text-[11px] text-[#7e8c74] [&_summary]:p-[15px_18px] [&_summary]:cursor-pointer [&_summary]:flex [&_summary]:gap-[10px] [&_summary]:items-center [&_summary]:font-[500] [&_summary]:text-[#65775a] [&_p]:p-[0_18px_17px] [&_p]:leading-[1.9] [&_p]:max-w-[1000px]"><summary><span>ⓘ</span> Understanding your assessment <span className="ml-[auto] text-[10px] text-[#8c9884] max-[600.01px]:hidden">Method & limitations</span></summary><p>This is a preliminary rule-based assessment, not a validated tea-quality prediction. Premium requires health ≥80%, readiness ≥85%, and Good climate. Health or readiness below 60%, or Poor climate, gives Low potential; intermediate conditions give Moderate. The displayed reasons identify the specific conditions that determined the result. These thresholds require validation against actual tea quality. Missing or outdated climate data prevents confirmation.</p></details>
        <footer className="flex justify-between gap-[15px] text-[#a1ab99] text-[9px] p-[23px_0_4px] [&_span:first-child]:font-[600] [&_span:first-child]:tracking-[.3px] max-[600.01px]:text-[8px]"><span>AI Smart Tea Ecosystem</span><span>Thoughtful decisions. Healthier harvests.</span></footer>
      </div>
    </main>
  );
}
