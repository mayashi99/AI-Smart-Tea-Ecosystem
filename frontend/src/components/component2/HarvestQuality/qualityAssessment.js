export function assessQuality(assessment, today, readiness) {
  const health = assessment?.image_analysis?.image_health_score;
  const risk = assessment?.stress_assessment?.overall_climate_risk;
  if (!assessment?.success || !Number.isFinite(health) || health < 0 || health > 100 || !['Low', 'Medium', 'High'].includes(risk)) {
    throw new Error('Plantation health or climate assessment is incomplete. Please retry.');
  }
  if (!Number.isFinite(readiness) || readiness < 0 || readiness > 100) throw new Error('Harvest readiness is incomplete. Please retry.');
  const climateLabel = { Low: 'Good', Medium: 'Moderate', High: 'Poor' }[risk];
  const reasons = [`Plantation health: ${health.toFixed(1)}%. Harvest ready probability: ${readiness.toFixed(1)}%. Climate: ${climateLabel} (${risk.toLowerCase()} stress risk).`];
  let potential = 'Premium';
  if (health < 60 || readiness < 60 || risk === 'High') {
    potential = 'Poor';
    reasons.push('Health or readiness is below 60%, or climate risk is high. Improve these conditions and reassess before harvesting.');
  } else if (health < 80 || readiness < 85 || risk === 'Medium') {
    potential = 'Moderate';
    reasons.push('Health is below 80%, readiness is below 85%, or climate risk is moderate. Inspect leaf maturity and climate stress before harvesting.');
  } else {
    reasons.push('Health is at least 80%, readiness is at least 85%, and climate is Good. These meet the preliminary Premium criteria.');
  }
  if (assessment.climate?.data_date !== today) {
    potential = 'Unable to confirm';
    reasons.push('Current climate data is unavailable; the assessment uses an earlier date.');
  }
  reasons.push('Confirm leaf maturity and actual leaf quality in the field.');
  return { potential, reasons, climateLabel };
}
