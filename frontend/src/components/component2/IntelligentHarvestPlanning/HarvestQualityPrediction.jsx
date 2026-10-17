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

  return <section className="hp-quality" aria-labelledby="hp-quality-title" aria-busy={loading}>
    <div className="hp-workspace-heading"><div><span className="hp-overline">HARVEST QUALITY</span><h2 id="hp-quality-title">Tea quality potential</h2></div><span className="hp-quality-location">{context.location} · {context.today}</span></div>
    <div aria-live="polite">
      {loading && <p className="hp-quality-loading"><span className="hp-spinner" /> Assessing plantation health, climate and forecast alongside harvest readiness…</p>}
      {error && <div className="hp-error" role="alert"><p>{error}</p><button className="hp-weather-refresh" type="button" onClick={() => { setLoading(true); setResult(null); setError(''); setRetry(value => value + 1); }}>Retry quality analysis</button></div>}
      {result && <>
        <div className="hp-quality-summary" data-quality={result.potential}><div><span>Harvest Quality Potential</span><h3>{result.potential}</h3></div><p>Based on plantation health, harvest readiness, climate stress and the next three days of weather.</p></div>
        <dl className="hp-quality-factors"><div><dt>Plantation health</dt><dd>{result.health.toFixed(1)}%</dd></div><div><dt>Harvest readiness</dt><dd>{context.readiness.toFixed(1)}%</dd></div><div><dt>Climate conditions</dt><dd>{result.climateLabel}</dd></div><div><dt>Best weather match</dt><dd>{result.bestDate || 'No recommended day'}</dd></div></dl>
      </>}
    </div>
    <p className="hp-weather-note">Preliminary rule-based quality potential, not a measured tea grade. Uses current climate from the plantation assessment and Open-Meteo forecast; edited yield inputs and the selected yield period do not change this current-field assessment. Readiness is a model probability, not the percentage of leaves ready.</p>
  </section>;
}
