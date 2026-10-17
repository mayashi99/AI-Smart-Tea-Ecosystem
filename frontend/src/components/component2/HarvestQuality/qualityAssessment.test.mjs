import test from 'node:test';
import assert from 'node:assert/strict';
import { assessQuality } from './qualityAssessment.js';
const today = '2026-10-15';
const assessment = { success: true, climate: { data_date: today }, image_analysis: { image_health_score: 90 }, stress_assessment: { overall_climate_risk: 'Low' } };
test('healthy and ready plantation with Good climate is Premium', () => assert.equal(assessQuality(assessment, today, 96).potential, 'Premium'));
test('high climate risk yields low potential', () => assert.equal(assessQuality({ ...assessment, stress_assessment: { overall_climate_risk: 'High' } }, today, 96).potential, 'Poor'));
test('fallback climate cannot confirm current quality', () => assert.equal(assessQuality({ ...assessment, climate: { data_date: '2026-10-14' } }, today, 96).potential, 'Unable to confirm'));
test('missing health is rejected rather than treated as healthy', () => assert.throws(() => assessQuality({ ...assessment, image_analysis: {} }, today, 96)));

test('91% health, 96% readiness and Good climate recommend Premium', () => {
  const result = assessQuality({ ...assessment, image_analysis: { image_health_score: 91 } }, today, 96);
  assert.equal(result.potential, 'Premium');
  assert.equal(result.climateLabel, 'Good');
  assert.match(result.reasons.join(' '), /91.0%.*96.0%/);
});
test('readiness below 60 is Poor even when health is high', () => assert.equal(assessQuality(assessment, today, 40).potential, 'Poor'));
test('readiness below Premium threshold is Moderate', () => assert.equal(assessQuality(assessment, today, 80).potential, 'Moderate'));
test('missing readiness cannot generate recommendation', () => assert.throws(() => assessQuality(assessment, today)));

test('medium climate risk limits quality to Moderate', () => assert.equal(assessQuality({ ...assessment, stress_assessment: { overall_climate_risk: 'Medium' } }, today, 96).potential, 'Moderate'));
test('missing climate cannot generate a quality result', () => assert.throws(() => assessQuality({ ...assessment, stress_assessment: {} }, today, 96)));
