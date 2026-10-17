import test from 'node:test';
import assert from 'node:assert/strict';
import { getSriLankaDate, harvestPeriod, mapClimateResponse, fetchPlanningClimate } from './planningClimate.js';

const response = (climate = {}) => ({
  success: true, climate_data_date: '2026-10-14',
  climate: { temperature_c: 28, rainfall_mm: 0, humidity_percent: 85, wind_speed_m_s: 2, solar_radiation_kwh_m2_day: 4.8, ...climate },
});

test('Sri Lanka date rolls over at 18:30 UTC, including year boundaries', () => {
  assert.equal(getSriLankaDate(new Date('2026-10-13T18:29:59Z')), '2026-10-13');
  assert.equal(getSriLankaDate(new Date('2026-10-13T18:30:00Z')), '2026-10-14');
  assert.equal(getSriLankaDate(new Date('2026-12-31T18:30:00Z')), '2027-01-01');
});

test('initial harvest period fits the model’s four week buckets', () => {
  assert.deepEqual(harvestPeriod('2026-10-14'), { year: 2026, month: 10, week: 2 });
  assert.equal(harvestPeriod('2026-10-15').week, 3);
  assert.equal(harvestPeriod('2026-10-31').week, 4);
});

test('preserves zero rainfall and converts solar daily energy into mean power', () => {
  assert.deepEqual(mapClimateResponse(response(), '2026-10-14'), {
    Temperature: 28, Rainfall_mm: 0, Humidity: 85, Wind_Speed: 2, Solar_Radiation: 200,
  });
});

test('missing values remain empty rather than becoming fabricated zeros', () => {
  const values = mapClimateResponse(response({ temperature_c: null, rainfall_mm: undefined, solar_radiation_kwh_m2_day: NaN }), '2026-10-14');
  assert.equal(values.Temperature, '');
  assert.equal(values.Rainfall_mm, '');
  assert.equal(values.Solar_Radiation, '');
});

test('rejects previous-day fallback data and failed responses', () => {
  assert.throws(() => mapClimateResponse(response(), '2026-10-15'), /unavailable/);
  assert.throws(() => mapClimateResponse({ success: false }, '2026-10-14'), /unavailable/);
});

test('requests the selected location and exact date with cancellation support', async (t) => {
  const controller = new AbortController();
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    const request = new URL(url, 'http://localhost');
    assert.equal(request.pathname, '/component02/climate');
    assert.equal(request.searchParams.get('latitude'), '6.0341');
    assert.equal(request.searchParams.get('longitude'), '80.2155');
    assert.equal(request.searchParams.get('date'), '2026-10-14');
    assert.equal(request.searchParams.get('allow_fallback'), 'false');
    assert.equal(options.signal, controller.signal);
    return { ok: true, json: async () => response() };
  });
  assert.equal((await fetchPlanningClimate('', 'Galle', '2026-10-14', controller.signal)).Temperature, 28);
});
