export const MAX_PHOTOS = 10;

export function validatePhotoSelection(existingCount, files) {
  if (existingCount + files.length > MAX_PHOTOS) {
    return `You can add up to ${MAX_PHOTOS} photos. You have ${MAX_PHOTOS - existingCount} slots left.`;
  }
  const invalid = files.find((file) =>
    !["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
    file.size === 0 || file.size > 10 * 1024 * 1024
  );
  return invalid ? `${invalid.name}: choose a non-empty JPG, PNG or WEBP image up to 10 MB.` : "";
}

function harvestReadyProbability(data) {
  if (!["Harvest_Ready", "Harvest_Not_Ready"].includes(data?.prediction)) return null;
  const confidence = typeof data.confidence === "number"
    ? data.confidence
    : typeof data.confidence_percent === "number" ? data.confidence_percent / 100 : null;
  if (confidence === null || !Number.isFinite(confidence) || confidence < 0 || confidence > 1) return null;
  // This model has two classes. A not-ready confidence of 90% means 10% ready.
  return data.prediction === "Harvest_Ready" ? confidence : 1 - confidence;
}

export function summarizeHarvestReadiness(results) {
  const probabilities = results
    .filter((result) => !result.error)
    .map((result) => harvestReadyProbability(result.data))
    .filter((probability) => probability !== null);
  const average = probabilities.length
    ? probabilities.reduce((sum, probability) => sum + probability, 0) / probabilities.length
    : null;
  const readyPercent = average === null ? null : Math.round(average * 1000) / 10;
  return {
    readyPercent,
    successfulCount: probabilities.length,
    failedCount: results.length - probabilities.length,
    label: readyPercent === null ? "Readiness unavailable"
      : readyPercent === 50 ? "Mixed readiness"
      : readyPercent > 50 ? "Harvest Ready" : "Harvest Not Ready",
  };
}

// Keep inference sequential so a ten-photo selection does not overload the model.
export async function analyseHarvestPhotos(photos, api, onResult, request = fetch) {
  const results = [];
  for (const photo of photos) {
    let result;
    try {
      const body = new FormData();
      body.append("file", photo.file);
      const response = await request(`${api}/component02/harvest-readiness/predict`, {
        method: "POST", body,
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Harvest readiness prediction failed.");
      }
      if (harvestReadyProbability(data) === null) {
        throw new Error("The model returned an invalid readiness result. Please try again.");
      }
      result = { ...photo, data };
    } catch (error) {
      result = { ...photo, error: error.message || "Unable to analyse this photo." };
    }
    results.push(result);
    onResult(result, results.length);
  }
  return results;
}
