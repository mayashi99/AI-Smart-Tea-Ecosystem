// Representative town coordinates, not individual plantation GPS positions.
export const CLIMATE_LOCATIONS = {
  Galle: [6.0341, 80.2155],
  Matara: [5.95, 80.55],
  Ratnapura: [6.6858, 80.4036],
  Kegalle: [7.2523, 80.3436],
  Kalutara: [6.5831, 79.9593],
  Kandy: [7.2966, 80.6384],
  Matale: [7.4676, 80.6232],
  Badulla: [6.9802, 81.0577],
  "Uda Pussellawa": [7.0167, 80.9],
  Nawalapitiya: [7.05, 80.5333],
  Dimbula: [6.9333, 80.65], // Talawakelle reference
  "Nuwara Eliya": [6.9708, 80.7829],
  Uva: [6.7657, 80.951], // Haputale reference
};

export function getSriLankaDate(now = new Date()) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Colombo", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(now);
  const part = (type) => parts.find((item) => item.type === type).value;
  return `${part("year")}-${part("month")}-${part("day")}`;
}

export function harvestPeriod(date) {
  const [year, month, day] = date.split("-").map(Number);
  // The yield model uses four week buckets per month; week 4 includes days 22–31.
  return { year, month, week: Math.min(4, Math.ceil(day / 7)) };
}

export function emptyClimate() {
  return { Temperature: "", Rainfall_mm: "", Humidity: "", Wind_Speed: "", Solar_Radiation: "" };
}

export function mapClimateResponse(payload, date) {
  if (!payload?.success || payload.climate_data_date !== date || !payload.climate) {
    throw new Error("Weather for today is unavailable. Retry or enter your field conditions manually.");
  }
  const climate = payload.climate;
  const value = (input, multiplier = 1) => typeof input === "number" && Number.isFinite(input)
    ? Math.round(input * multiplier * 100) / 100 : "";
  return {
    Temperature: value(climate.temperature_c),
    Rainfall_mm: value(climate.rainfall_mm),
    Humidity: value(climate.humidity_percent),
    Wind_Speed: value(climate.wind_speed_m_s),
    // Daily energy (kWh/m²/day) expressed as 24-hour mean irradiance (W/m²).
    Solar_Radiation: value(climate.solar_radiation_kwh_m2_day, 1000 / 24),
  };
}

export async function fetchPlanningClimate(api, location, date, signal) {
  const [latitude, longitude] = CLIMATE_LOCATIONS[location];
  const params = new URLSearchParams({ latitude, longitude, date, allow_fallback: "false" });
  const response = await fetch(`${api}/component02/climate?${params}`, { signal });
  if (!response.ok) throw new Error("Could not load today’s weather. Retry or enter your field conditions manually.");
  return mapClimateResponse(await response.json(), date);
}
