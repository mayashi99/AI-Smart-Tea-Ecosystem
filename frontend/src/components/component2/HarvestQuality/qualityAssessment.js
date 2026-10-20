function addDays(dateString, days) {
  const date = new Date(`${dateString}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function hasCurrentForecast(forecast, today) {
  return forecast?.success && forecast.forecast_date === today && forecast.days?.length === 3
    && forecast.days.every(day => day.complete);
}

function harvestPlan(potential, today, forecast) {
  const bestDay = hasCurrentForecast(forecast, today)
    ? forecast.days.find(day => day.date === forecast.best_date && !day.thunderstorm)
    : null;
  if (potential === 'Premium') {
    if (bestDay) {
      return {
        date: bestDay.date,
        title: 'Best day to harvest',
        detail: `${forecast.message} Confirm leaf maturity in the field before picking.`,
        status: 'Best weather match',
      };
    }
    return {
      date: today,
      title: 'Harvest today',
      detail: 'Today has the strongest quality conditions in this assessment. A current three-day weather forecast was unavailable, so confirm field conditions before picking.',
      status: 'Ready to harvest',
    };
  }
  if (potential === 'Moderate') {
    return {
      date: addDays(today, 3),
      title: 'Reassess before harvesting',
      detail: 'Quality is not yet Premium. Recheck plantation health, readiness and climate in 3 days before fixing a harvest date.',
      status: 'Review in 3 days',
    };
  }
  if (potential === 'Low') {
    return {
      date: addDays(today, 7),
      title: 'Do not schedule harvest yet',
      detail: 'Current conditions could reduce leaf quality. Improve the listed conditions and reassess in 7 days.',
      status: 'Review in 7 days',
    };
  }
  return {
    date: null,
    title: 'A current assessment is needed',
    detail: 'Refresh climate data before choosing a harvest date.',
    status: 'Date unavailable',
  };
}

export function assessQuality(assessment, today, readiness, forecast) {
  const health = assessment?.image_analysis?.image_health_score;
  const risk = assessment?.stress_assessment?.overall_climate_risk;
  if (!assessment?.success || !Number.isFinite(health) || health < 0 || health > 100 || !['Low', 'Medium', 'High'].includes(risk)) {
    throw new Error('Plantation health or climate assessment is incomplete. Please retry.');
  }
  if (!Number.isFinite(readiness) || readiness < 0 || readiness > 100) throw new Error('Harvest readiness is incomplete. Please retry.');
  const climateLabel = { Low: 'Good', Medium: 'Moderate', High: 'Poor' }[risk];
  const reasons = [`Plantation health: ${health.toFixed(1)}%. Harvest ready probability: ${readiness.toFixed(1)}%. Climate: ${climateLabel} (${risk.toLowerCase()} stress risk).`];
  if (assessment.climate?.data_date !== today) {
    reasons.push(`Unable to confirm because the climate data is from ${assessment.climate?.data_date || 'an unknown date'}, not ${today}. Refresh the assessment with current climate data.`);
    return { potential: 'Unable to confirm', reasons, climateLabel, harvestPlan: harvestPlan('Unable to confirm', today, forecast) };
  }

  const lowTriggers = [];
  if (health < 60) lowTriggers.push(`plantation health is ${health.toFixed(1)}%, below the 60% minimum`);
  if (readiness < 60) lowTriggers.push(`harvest readiness is ${readiness.toFixed(1)}%, below the 60% minimum`);
  if (risk === 'High') lowTriggers.push('climate stress risk is high');
  if (lowTriggers.length) {
    reasons.push(`Low potential because ${lowTriggers.join(' and ')}.`);
    reasons.push('Improve the listed field conditions and reassess before harvesting.');
    return { potential: 'Low', reasons, climateLabel, harvestPlan: harvestPlan('Low', today, forecast) };
  }

  const moderateTriggers = [];
  if (health < 80) moderateTriggers.push(`plantation health is ${health.toFixed(1)}%, below the 80% Premium threshold`);
  if (readiness < 85) moderateTriggers.push(`harvest readiness is ${readiness.toFixed(1)}%, below the 85% Premium threshold`);
  if (risk === 'Medium') moderateTriggers.push('climate stress risk is medium');
  if (moderateTriggers.length) {
    reasons.push(`Moderate potential because ${moderateTriggers.join(' and ')}.`);
    reasons.push('Inspect leaf maturity and climate stress in the field before harvesting.');
    return { potential: 'Moderate', reasons, climateLabel, harvestPlan: harvestPlan('Moderate', today, forecast) };
  }

  reasons.push(`Premium potential because plantation health is at least 80%, harvest readiness is at least 85%, and climate stress risk is low.`);
  reasons.push('Confirm leaf maturity and actual leaf quality in the field before harvesting.');
  return { potential: 'Premium', reasons, climateLabel, harvestPlan: harvestPlan('Premium', today, forecast) };
}
