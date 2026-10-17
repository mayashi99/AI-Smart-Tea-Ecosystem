import test from 'node:test';
import assert from 'node:assert/strict';
import { analyseHarvestPhotos, summarizeHarvestReadiness, validatePhotoSelection, validateTeaPhotos } from './harvestPhotos.js';

const file = (name = 'tea.jpg', options = {}) => ({ name, size: 1024, type: 'image/jpeg', ...options });

test('accepts ten photos together or additions up to ten, rejects an eleventh', () => {
  assert.equal(validatePhotoSelection(0, Array.from({ length: 10 }, () => file())), '');
  assert.equal(validatePhotoSelection(8, [file(), file()]), '');
  assert.match(validatePhotoSelection(8, [file(), file(), file()]), /2 slots left/);
  assert.match(validatePhotoSelection(10, [file()]), /0 slots left/);
  assert.equal(validatePhotoSelection(9, [file()]), '');
});

test('validates format and size for every file in an addition', () => {
  assert.match(validatePhotoSelection(1, [file(), file('wrong.gif', { type: 'image/gif' })]), /wrong.gif/);
  assert.match(validatePhotoSelection(0, [file('large.jpg', { size: 10 * 1024 * 1024 + 1 })]), /large.jpg/);
  assert.match(validatePhotoSelection(0, [file('empty.jpg', { size: 0 })]), /empty.jpg/);
  assert.equal(validatePhotoSelection(0, [file('limit.webp', { size: 10 * 1024 * 1024, type: 'image/webp' })]), '');
});

test('sends all ten photos sequentially and retains photo/result identity and progress', async () => {
  const photos = Array.from({ length: 10 }, (_, index) => ({
    id: String(index), file: new File(['tea'], `${index}.jpg`, { type: 'image/jpeg' }), preview: `blob:${index}`,
  }));
  const completed = [];
  let active = 0;
  let call = 0;
  const results = await analyseHarvestPhotos(photos, 'http://api', (result, count) => {
    completed.push(count);
    assert.equal(result.id, String(count - 1));
  }, async (url, options) => {
    assert.equal(url, 'http://api/component02/harvest-readiness/predict');
    assert.equal(options.method, 'POST');
    assert.equal(options.body.get('file').name, `${call++}.jpg`);
    assert.equal(++active, 1);
    await Promise.resolve();
    active--;
    return { ok: true, json: async () => ({ prediction: 'Harvest_Ready', confidence_percent: 98 }) };
  });
  assert.equal(call, 10);
  assert.deepEqual(completed, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
  assert.equal(results[9].data.confidence_percent, 98);
  assert.equal(results[9].preview, 'blob:9');
});

test('continues after HTTP, network and malformed response errors', async () => {
  const photos = Array.from({ length: 4 }, (_, index) => ({ id: index, file: new File(['tea'], `${index}.jpg`) }));
  let call = 0;
  const results = await analyseHarvestPhotos(photos, 'http://api', () => {}, async () => {
    switch (call++) {
      case 0: return { ok: false, json: async () => ({ detail: 'Invalid image' }) };
      case 1: throw new Error('Connection lost');
      case 2: return { ok: false, json: async () => { throw new Error('Invalid JSON'); } };
      default: return { ok: true, json: async () => ({ prediction: 'Harvest_Not_Ready', confidence: 0.9 }) };
    }
  });
  assert.equal(results.length, 4);
  assert.equal(results[0].error, 'Invalid image');
  assert.equal(results[1].error, 'Connection lost');
  assert.equal(results[2].error, 'Invalid JSON');
  assert.equal(results[3].data.prediction, 'Harvest_Not_Ready');
});

const prediction = (label, confidence) => ({ data: { prediction: label, confidence } });

test('averages all ready probabilities equally, including a single photo', () => {
  const summary = summarizeHarvestReadiness([
    prediction('Harvest_Ready', 0.9), prediction('Harvest_Ready', 0.8), prediction('Harvest_Ready', 1),
  ]);
  assert.equal(summary.readyPercent, 90);
  assert.equal(summary.label, 'Harvest Ready');
  assert.equal(summary.successfulCount, 3);
  assert.equal(summarizeHarvestReadiness([prediction('Harvest_Ready', 0.876)]).readyPercent, 87.6);
});

test('opposing confident predictions produce mixed readiness, not high readiness', () => {
  const summary = summarizeHarvestReadiness([
    prediction('Harvest_Ready', 0.9), prediction('Harvest_Not_Ready', 0.9),
  ]);
  assert.equal(summary.readyPercent, 50);
  assert.equal(summary.label, 'Mixed readiness');
});

test('not-ready confidence is complemented before averaging', () => {
  const summary = summarizeHarvestReadiness([
    prediction('Harvest_Not_Ready', 1),
    { data: { prediction: 'Harvest_Not_Ready', confidence_percent: 80 } },
  ]);
  assert.equal(summary.readyPercent, 10);
  assert.equal(summary.label, 'Harvest Not Ready');
});

test('failed and malformed results are excluded and counted without diluting the average', () => {
  const summary = summarizeHarvestReadiness([
    prediction('Harvest_Ready', 0.8), { error: 'Network error' },
    prediction('Other', 0.9), prediction('Harvest_Ready', null),
    prediction('Harvest_Ready', NaN), prediction('Harvest_Ready', 1.5),
  ]);
  assert.equal(summary.readyPercent, 80);
  assert.equal(summary.successfulCount, 1);
  assert.equal(summary.failedCount, 5);
});

test('empty or fully failed batches have no average or readiness classification', () => {
  for (const results of [[], [{ error: 'Invalid image' }]]) {
    const summary = summarizeHarvestReadiness(results);
    assert.equal(summary.readyPercent, null);
    assert.equal(summary.label, 'Readiness unavailable');
    assert.equal(summary.successfulCount, 0);
  }
});

test('invalid successful API responses become photo errors and processing continues', async () => {
  const photos = [0, 1].map((id) => ({ id, file: new File(['tea'], `${id}.jpg`) }));
  let call = 0;
  const results = await analyseHarvestPhotos(photos, '', () => {}, async () => ({
    ok: true,
    json: async () => call++ === 0 ? {} : { prediction: 'Harvest_Ready', confidence: 0.9 },
  }));
  assert.match(results[0].error, /invalid readiness result/);
  assert.equal(summarizeHarvestReadiness(results).readyPercent, 90);
  assert.equal(summarizeHarvestReadiness(results).failedCount, 1);
});


test('validates all ten photos in batches supported by the shared API', async () => {
  const files = Array.from({ length: 10 }, (_, i) => new File(['image'], `tea-${i}.jpg`, { type: 'image/jpeg' }));
  const seen = [];
  await validateTeaPhotos(files, '', undefined, async (url, options) => {
    assert.equal(url, '/component02/validate-images');
    const batch = options.body.getAll('files');
    assert.equal(batch.length, 5);
    seen.push(...batch.map(file => file.name));
    return { ok: true, json: async () => ({ success: true }) };
  });
  assert.deepEqual(seen, files.map(file => file.name));
});

test('rejects a selection when the second batch contains a non-tea image', async () => {
  let calls = 0;
  const files = Array.from({ length: 6 }, () => new File(['image'], 'photo.jpg'));
  await assert.rejects(validateTeaPhotos(files, '', undefined, async () => {
    calls++;
    return calls === 1
      ? { ok: true, json: async () => ({ success: true }) }
      : { ok: false, json: async () => ({ detail: 'Could not identify tea leaves in car.jpg' }) };
  }), /car.jpg/);
  assert.equal(calls, 2);
});

test('fails closed when the image validation server returns invalid JSON', async () => {
  await assert.rejects(validateTeaPhotos([new File(['image'], 'tea.jpg')], '', undefined, async () => ({
    ok: true, json: async () => { throw new Error('invalid JSON'); },
  })), /Could not validate/);
});
