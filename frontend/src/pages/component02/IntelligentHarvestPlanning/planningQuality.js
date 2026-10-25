import { assessQuality } from '../HarvestQuality/qualityAssessment.js';

export function assessPlanningQuality(assessment, readiness, forecast, today) {
  const base = assessQuality(assessment, today, readiness);
  if (!forecast?.success || forecast.forecast_date !== today || forecast.days?.length !== 3 || forecast.days.some(day => !day.complete)) {
    throw new Error('A complete, current three-day forecast is required. Please retry the analysis.');
  }
  let potential = { Premium: 'Premium', Moderate: 'Medium', Poor: 'Low', 'Unable to confirm': 'Unable to confirm' }[base.potential];
  const reasons = [...base.reasons];
  const best = forecast.days.find(day => day.date === forecast.best_date);
  if (!best || best.thunderstorm) {
    if (potential !== 'Unable to confirm') potential = 'Low';
    reasons.push('The forecast has no recommended harvest day. Wait for better weather and reassess.');
  } else if (best.rainfall_mm > 0 || best.rain_probability_percent >= 50 || best.wind_max_m_s >= 10 || best.temperature_max_c >= 35) {
    if (potential === 'Premium') potential = 'Medium';
    reasons.push('Even the best forecast day has rain, wind or heat concerns, limiting quality potential.');
  } else {
    reasons.push('The best forecast day has no flagged rain, wind or heat concerns.');
  }
  return { ...base, potential, reasons, bestDate: best?.date };
}
