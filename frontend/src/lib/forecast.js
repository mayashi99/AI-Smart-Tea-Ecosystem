// Plain-language helpers that turn model statistics into guidance a seller can act on.

// MAPE = average % error on months the model never saw during training.
export function reliability(mape) {
  const value = Number(mape)
  if (!Number.isFinite(value)) return { level: 'unknown', label: 'Unknown', tone: 'blue', note: 'Accuracy has not been measured yet.' }
  if (value <= 8) return { level: 'high', label: 'High reliability', tone: 'green', note: `On past months the forecast was typically within ±${value.toFixed(1)}% of the real price.` }
  if (value <= 15) return { level: 'moderate', label: 'Moderate reliability', tone: 'amber', note: `On past months the forecast was typically within ±${value.toFixed(1)}% — use it as a guide, not a quote.` }
  return { level: 'low', label: 'Low reliability', tone: 'red', note: `On past months the forecast missed by about ${value.toFixed(0)}% on average — treat it as a rough direction only.` }
}

export function trend(changePct) {
  if (!Number.isFinite(changePct)) return { label: 'No forecast', tone: 'blue', icon: 'trend' }
  if (changePct > 2) return { label: 'Prices expected to rise', tone: 'green', icon: 'arrowUp' }
  if (changePct < -2) return { label: 'Prices expected to fall', tone: 'red', icon: 'arrowDown' }
  return { label: 'Prices expected to stay steady', tone: 'blue', icon: 'arrowRight' }
}

export const isFallbackModel = (name = '') => /fallback|baseline/i.test(name)
