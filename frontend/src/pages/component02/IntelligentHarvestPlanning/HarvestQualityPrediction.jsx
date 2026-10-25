import { useEffect, useState } from 'react';
import { CLIMATE_LOCATIONS } from './planningClimate';
import { assessPlanningQuality } from './planningQuality';

async function read(response) {
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Quality analysis is unavailable. Please retry.');
  return data;
}

export default function HarvestQualityPrediction({ context, api }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const timer = setTimeout(() => controller.abort(), 120000);
    async function analyze() {
      try {
        const [latitude, longitude] = CLIMATE_LOCATIONS[context.location];
        const params = new URLSearchParams({ latitude, longitude });
        // The health endpoint accepts five files per request; include all planner photos.
        let weightedHealth = 0;
        let total = 0;
        let assessment;
        for (let start = 0; start < context.photos.length; start += 5) {
          const batch = context.photos.slice(start, start + 5);
          const body = new FormData();
          batch.forEach(photo => body.append('files', photo.file));
          const data = await fetch(`${api}/component02/assess?${params}&date=${context.today}`, { method: 'POST', body, signal: controller.signal }).then(read);
          const health = data.image_analysis?.image_health_score;
          if (!data.success || !Number.isFinite(health) || health < 0 || health > 100 || data.climate?.data_date !== context.today) throw new Error('Current plantation health and climate data are incomplete. Please retry.');
          if (assessment && data.stress_assessment?.overall_climate_risk !== assessment.stress_assessment?.overall_climate_risk) throw new Error('Climate changed during analysis. Please retry for a consistent assessment.');
          weightedHealth += health * batch.length;
          total += batch.length;
          assessment = data;
        }
        assessment = { ...assessment, image_analysis: { ...assessment.image_analysis, image_health_score: weightedHealth / total } };
        const forecast = await fetch(`${api}/component02/harvest-forecast?${params}`, { signal: controller.signal }).then(read);
        const quality = assessPlanningQuality(assessment, context.readiness, forecast, context.today);
        if (active) setResult({ ...quality, health: weightedHealth / total, forecast });
      } catch (err) {
        if (active) setError(err.name === 'AbortError' ? 'Quality analysis timed out. Please retry.' : err.message);
      } finally {
        clearTimeout(timer);
        if (active) setLoading(false);
      }
    }
    analyze();
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [context, api, retry]);

  return <section className="mt-[24px] p-[26px] [border:1px_solid_#e0e8e3] rounded-[16px] bg-[white] [&_.hp-weather-note]:mt-[18px] max-[700.01px]:p-[20px]" aria-labelledby="hp-quality-title" aria-busy={loading}>
    <div className="flex justify-between items-end gap-[20px] m-[32px_0_18px] [&_h2]:font-[700] [&_h2]:text-[22px] [&_h2]:leading-[1.3] [&_h2]:tracking-[-.6px] [&_h2]:m-[6px_0_0] max-[560.01px]:items-start max-[560.01px]:flex-col max-[560.01px]:gap-[10px]"><div><span className="block text-[10px] font-[750] tracking-[2px] text-[#087653]">HARVEST QUALITY</span><h2 id="hp-quality-title">Tea quality potential</h2></div><span className="text-[#64766e] text-[11px] max-[700.01px]:hidden">{context.location} · {context.today}</span></div>
    <div aria-live="polite">
      {loading && <p className="flex gap-[12px] items-center text-[13px] p-[20px_0]"><span className="hp-spinner inline-block w-[18px] h-[18px] [border:2px_solid_currentColor] [border-right-color:transparent] rounded-[50%] animate-spin [animation-duration:0.8s]" /> Assessing plantation health, climate and forecast alongside harvest readiness…</p>}
      {error && <div className="p-[16px_20px] bg-[#fff4f0] [border:1px_solid_#f1cabe] text-[#9a3d2c] rounded-[12px] mt-[20px] text-[12px] [&_p]:m-[5px_0_0] [&_p]:[overflow-wrap:anywhere]" role="alert"><p>{error}</p><button className="inline-flex items-center justify-center gap-[6px] [border:1px_solid_#d7e3da] rounded-[7px] bg-[white] p-[8px_10px] [font:inherit] text-[10px] font-[650] text-[#37694f] cursor-pointer [&_svg]:w-[13px] [&_svg]:h-[13px] [&:hover:not(:disabled)]:bg-[#edf7f1] [&:disabled]:opacity-[.6] [&:disabled]:cursor-wait max-[560.01px]:min-h-[36px]" type="button" onClick={() => { setLoading(true); setResult(null); setError(''); setRetry(value => value + 1); }}>Retry quality analysis</button></div>}
      {result && <>
        <div className="flex justify-between items-center gap-[24px] [border:1px_solid_#d3e6d4] bg-[#eff7ed] rounded-[12px] p-[22px] text-[#2d653b] mt-[20px] [&[data-quality=Medium]]:bg-[#fff8e8] [&[data-quality=Medium]]:[border-color:#eddfbb] [&[data-quality=Medium]]:text-[#8a641c] [&[data-quality=Low]]:bg-[#fff1ed] [&[data-quality=Low]]:[border-color:#eed6cd] [&[data-quality=Low]]:text-[#a04d35] [&_h3]:text-[34px] [&_h3]:m-[6px_0_0] [&_h3]:tracking-[-1px] [&_span]:text-[12px] [&_span]:font-[600] [&_p]:max-w-[320px] [&_p]:text-[12px] [&_p]:leading-[1.8] [&_p]:m-[0] max-[700.01px]:flex-col max-[700.01px]:items-start max-[700.01px]:gap-[12px]" data-quality={result.potential}><div><span>Harvest Quality Potential</span><h3>{result.potential}</h3></div><p>Based on plantation health, harvest readiness, climate stress and the next three days of weather.</p></div>
        <dl className="grid grid-cols-[repeat(4,minmax(0,1fr))] gap-[14px] m-[20px_0] [&>div]:[border:1px_solid_#e0e8e3] [&>div]:p-[16px] [&>div]:rounded-[10px] [&_dt]:text-[11px] [&_dt]:text-[#64766e] [&_dd]:m-[10px_0_0] [&_dd]:text-[20px] [&_dd]:font-[650] max-[700.01px]:grid-cols-[repeat(2,minmax(0,1fr))]"><div><dt>Plantation health</dt><dd>{result.health.toFixed(1)}%</dd></div><div><dt>Harvest readiness</dt><dd>{context.readiness.toFixed(1)}%</dd></div><div><dt>Climate conditions</dt><dd>{result.climateLabel}</dd></div><div><dt>Best weather match</dt><dd>{result.bestDate || 'No recommended day'}</dd></div></dl>
      </>}
    </div>
    <p className="hp-weather-note m-[15px_0_0] text-[10px] leading-[1.8] text-[#64766e] [&_a]:text-[#285d43] [&_a]:underline [&_a]:[text-underline-offset:2px]">Preliminary rule-based quality potential, not a measured tea grade. Uses current climate from the plantation assessment and Open-Meteo forecast; edited yield inputs and the selected yield period do not change this current-field assessment. Readiness is a model probability, not the percentage of leaves ready.</p>
  </section>;
}
