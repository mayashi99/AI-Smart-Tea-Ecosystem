import test from 'node:test';
import assert from 'node:assert/strict';
import { assessQuality } from './qualityAssessment.js';
const today = '2026-10-15';
const assessment = { success: true, climate: { data_date: today }, image_analysis: { image_health_score: 90 }, stress_assessment: { overall_climate_risk: 'Low' } };
test('healthy and ready plantation with Good climate is Premium', () => assert.equal(assessQuality(assessment, today, 96).potential, 'Premium'));
test('Premium quality recommends harvesting on the assessed date', () => {
  const result = assessQuality(assessment, today, 96);
  assert.deepEqual(result.harvestPlan, {
    date: today,
    title: 'Harvest today',
    detail: 'Today has the strongest quality conditions in this assessment. A current three-day weather forecast was unavailable, so confirm field conditions before picking.',
    status: 'Ready to harvest',
  });
});
test('Premium quality selects the best date from a complete current three-day forecast', () => {
  const forecast = {
    success: true, forecast_date: today, best_date: '2026-10-17', message: 'Lowest rainfall and wind expected.',
    days: [
      { date: '2026-10-16', complete: true, thunderstorm: false },
      { date: '2026-10-17', complete: true, thunderstorm: false },
      { date: '2026-10-18', complete: true, thunderstorm: false },
    ],
  };
  const result = assessQuality(assessment, today, 96, forecast);
  assert.equal(result.harvestPlan.date, '2026-10-17');
  assert.equal(result.harvestPlan.title, 'Best day to harvest');
  assert.equal(result.harvestPlan.status, 'Best weather match');
});
test('high climate risk yields Low potential', () => assert.equal(assessQuality({ ...assessment, stress_assessment: { overall_climate_risk: 'High' } }, today, 96).potential, 'Low'));
test('fallback climate cannot confirm current quality', () => assert.equal(assessQuality({ ...assessment, climate: { data_date: '2026-10-14' } }, today, 96).potential, 'Unable to confirm'));
test('missing health is rejected rather than treated as healthy', () => assert.throws(() => assessQuality({ ...assessment, image_analysis: {} }, today, 96)));

test('91% health, 96% readiness and Good climate recommend Premium', () => {
  const result = assessQuality({ ...assessment, image_analysis: { image_health_score: 91 } }, today, 96);
  assert.equal(result.potential, 'Premium');
  assert.equal(result.climateLabel, 'Good');
  assert.match(result.reasons.join(' '), /91.0%.*96.0%/);
});
test('readiness below 60 is Low even when health is high', () => assert.equal(assessQuality(assessment, today, 40).potential, 'Low'));
test('readiness below Premium threshold is Moderate', () => assert.equal(assessQuality(assessment, today, 80).potential, 'Moderate'));
test('missing readiness cannot generate recommendation', () => assert.throws(() => assessQuality(assessment, today)));

test('medium climate risk limits quality to Moderate', () => assert.equal(assessQuality({ ...assessment, stress_assessment: { overall_climate_risk: 'Medium' } }, today, 96).potential, 'Moderate'));
test('Moderate and Low quality plans schedule a reassessment instead of an unsupported harvest date', () => {
  assert.equal(assessQuality({ ...assessment, stress_assessment: { overall_climate_risk: 'Medium' } }, today, 96).harvestPlan.date, '2026-10-18');
  assert.equal(assessQuality({ ...assessment, stress_assessment: { overall_climate_risk: 'High' } }, today, 96).harvestPlan.date, '2026-10-22');
});
test('Moderate reason identifies medium climate risk when health and readiness are strong', () => {
  const result = assessQuality({ ...assessment, stress_assessment: { overall_climate_risk: 'Medium' } }, today, 96);
  assert.match(result.reasons[1], /climate stress risk is medium/);
  assert.doesNotMatch(result.reasons[1], /below the 80%|below the 85%/);
});
test('Low reason identifies every triggering condition', () => {
  const result = assessQuality({ ...assessment, image_analysis: { image_health_score: 50 }, stress_assessment: { overall_climate_risk: 'High' } }, today, 40);
  assert.match(result.reasons[1], /health is 50.0%.*readiness is 40.0%.*risk is high/);
});
test('missing climate cannot generate a quality result', () => assert.throws(() => assessQuality({ ...assessment, stress_assessment: {} }, today, 96)));
