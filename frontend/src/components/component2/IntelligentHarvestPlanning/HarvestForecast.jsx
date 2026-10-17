import { useEffect, useState } from "react";
import { CLIMATE_LOCATIONS } from "./planningClimate";

const formatDate = (date) => new Intl.DateTimeFormat("en-GB", {
  weekday: "short", day: "numeric", month: "short", timeZone: "Asia/Colombo",
}).format(new Date(`${date}T12:00:00+05:30`));
const metric = (value, unit) => value === null ? "Unavailable" : `${value} ${unit}`;

export default function HarvestForecast({ api, location, today }) {
  const [forecast, setForecast] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setForecast(null);
    setError("");
    const timeout = window.setTimeout(() => {
      controller.abort();
      if (active) {
        setError("The forecast is taking too long to load. Please try again.");
        setLoading(false);
      }
    }, 25000);
    const [latitude, longitude] = CLIMATE_LOCATIONS[location];
    const params = new URLSearchParams({ latitude, longitude });
    fetch(`${api}/component02/harvest-forecast?${params}`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("The three-day forecast is unavailable. Please try again.");
        const data = await response.json();
        if (!data.success || data.forecast_date !== today || data.days?.length !== 3) {
          throw new Error("An up-to-date three-day forecast is unavailable. Please refresh.");
        }
        if (active && !controller.signal.aborted) setForecast(data);
      })
      .catch((err) => { if (active && !controller.signal.aborted) setError(err.message); })
      .finally(() => {
        window.clearTimeout(timeout);
        if (active && !controller.signal.aborted) setLoading(false);
      });
    return () => { active = false; controller.abort(); window.clearTimeout(timeout); };
  }, [api, location, today, refresh]);

  return <section className="hp-forecast" aria-labelledby="hp-forecast-title" aria-busy={loading}>
    <div className="hp-forecast-heading"><div><span className="hp-overline">PLAN YOUR HARVEST</span><h2 id="hp-forecast-title">Best day to harvest</h2><p>{location} area · Next 3 days, starting tomorrow · Sri Lanka time</p></div><button type="button" className="hp-weather-refresh" disabled={loading} onClick={() => setRefresh((value) => value + 1)}>{loading ? "Updating…" : "Refresh forecast"}</button></div>
    <div role="status">
      {loading && <p className="hp-forecast-loading"><span className="hp-spinner" /> Comparing rainfall, temperature and wind for the next three days…</p>}
      {error && <p className="hp-photo-error">{error}</p>}
      {forecast && <>
        <div className={`hp-forecast-recommendation ${forecast.best_date ? "" : "hp-forecast-caution"}`}>
          <strong>{forecast.best_date ? formatDate(forecast.best_date) : "No recommended day yet"}</strong>
          <p>{forecast.message}</p>
          {forecast.cautions.map((caution) => <p className="hp-weather-warning" key={caution}>{caution}</p>)}
        </div>
        <div className="hp-forecast-days">{forecast.days.map((day) => <article className={`hp-forecast-day ${day.date === forecast.best_date ? "hp-forecast-best" : ""}`} key={day.date}>
          <div className="hp-forecast-day-title"><h3><time dateTime={day.date}>{formatDate(day.date)}</time></h3>{day.date === forecast.best_date && <span>Best match</span>}</div>
          <dl>
            <div><dt>Rainfall</dt><dd>{metric(day.rainfall_mm, "mm")}</dd></div>
            <div><dt>Rain chance</dt><dd>{metric(day.rain_probability_percent, "%")}</dd></div>
            <div><dt>Temperature</dt><dd>{day.temperature_min_c === null || day.temperature_max_c === null ? "Unavailable" : `${day.temperature_min_c}–${day.temperature_max_c} °C`}</dd></div>
            <div><dt>Max. wind</dt><dd>{metric(day.wind_max_m_s, "m/s")}</dd></div>
          </dl>
          {day.thunderstorm && <p className="hp-weather-warning">Thunderstorms forecast</p>}
          {!day.complete && <p className="hp-weather-warning">Incomplete forecast</p>}
        </article>)}</div>
        <details className="hp-forecast-method"><summary>How is the day selected?</summary><p>{forecast.method}</p><p>This is a weather comparison, not a guarantee of harvesting conditions. Confirm leaf readiness and field conditions before harvesting.</p></details>
        <p className="hp-weather-note">Source: <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a> · Forecasts can change. Updated {new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Colombo" }).format(new Date(forecast.updated_at))} (Sri Lanka time).</p>
      </>}
    </div>
  </section>;
}
