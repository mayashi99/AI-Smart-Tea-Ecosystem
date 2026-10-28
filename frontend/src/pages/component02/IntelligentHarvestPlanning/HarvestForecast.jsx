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
    // A prop change begins a fresh forecast request, so clear stale results.
    // eslint-disable-next-line react-hooks/set-state-in-effect
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

  return <section className="mt-[24px] p-[26px] bg-[white] [border:1px_solid_#e0e8e3] rounded-[16px] max-[700.01px]:p-[20px_17px]" aria-labelledby="hp-forecast-title" aria-busy={loading}>
    <div className="flex items-center justify-between gap-[16px] mb-[20px] [&_h2]:m-[7px_0] [&_h2]:text-[22px] [&_h2]:font-[700] [&_h2]:tracking-[-.5px] [&_p]:m-[0] [&_p]:text-[12px] [&_p]:leading-[1.7] [&_p]:text-[#64766e] max-[700.01px]:items-start max-[700.01px]:flex-col"><div><span className="block text-[10px] font-[750] tracking-[2px] text-[#087653]">PLAN YOUR HARVEST</span><h2 id="hp-forecast-title">Best day to harvest</h2><p>{location} area · Next 3 days, starting tomorrow · Sri Lanka time</p></div><button type="button" className="inline-flex items-center justify-center gap-[6px] [border:1px_solid_#d7e3da] rounded-[7px] bg-[white] p-[8px_10px] [font:inherit] text-[10px] font-[650] text-[#37694f] cursor-pointer [&_svg]:w-[13px] [&_svg]:h-[13px] [&:hover:not(:disabled)]:bg-[#edf7f1] [&:disabled]:opacity-[.6] [&:disabled]:cursor-wait max-[560.01px]:min-h-[36px]" disabled={loading} onClick={() => setRefresh((value) => value + 1)}>{loading ? "Updating…" : "Refresh forecast"}</button></div>
    <div role="status">
      {loading && <p className="flex items-center gap-[12px] text-[12px] leading-[1.7] text-[#64766e] [&_.hp-spinner]:shrink-0"><span className="hp-spinner inline-block w-[18px] h-[18px] [border:2px_solid_currentColor] [border-right-color:transparent] rounded-[50%] animate-spin [animation-duration:0.8s]" /> Comparing rainfall, temperature and wind for the next three days…</p>}
      {error && <p className="m-[0] text-[#9a3d2c] text-[12px] leading-[1.7] [overflow-wrap:anywhere]">{error}</p>}
      {forecast && <>
        <div className={`p-[18px_20px] [border:1px_solid_#d5e8da] bg-[#f0f8f3] rounded-[12px] mb-[18px] [&_strong]:text-[22px] [&_strong]:font-[700] [&_strong]:text-[#227247] [&_p]:m-[7px_0_0] [&_p]:text-[12px] [&_p]:leading-[1.7] ${forecast.best_date ? "" : "[&]:bg-[#fffbf1] [&]:[border-color:#ebdfc2] [&&_strong]:text-[#967023]"}`}>
          <strong>{forecast.best_date ? formatDate(forecast.best_date) : "No recommended day yet"}</strong>
          <p>{forecast.message}</p>
          {forecast.cautions.map((caution) => <p className="[&]:text-[#956222]" key={caution}>{caution}</p>)}
        </div>
        <div className="grid grid-cols-[repeat(3,_minmax(0,_1fr))] gap-[14px] max-[700.01px]:grid-cols-[1fr]">{forecast.days.map((day) => <article className={`p-[17px] [border:1px_solid_#e0e8e3] rounded-[12px] min-w-[0] [&_h3]:m-[0] [&_h3]:text-[13px] [&_h3]:font-[650] [&_dl]:m-[15px_0_0] [&_dl_>_div]:flex [&_dl_>_div]:justify-between [&_dl_>_div]:flex-wrap [&_dl_>_div]:gap-[5px_10px] [&_dl_>_div]:p-[8px_0] [&_dl_>_div]:[border-top:1px_solid_#edf1ee] [&_dl_>_div]:text-[11px] [&_dt]:text-[#64766e] [&_dd]:m-[0] [&_dd]:font-[600] [&_dd]:tabular-nums [&_>_p]:text-[11px] [&_>_p]:m-[10px_0_0] ${day.date === forecast.best_date ? "[&]:[border-color:#47946b] [&]:bg-[#fcfefc] [&]:[box-shadow:inset_0_3px_#47946b]" : ""}`} key={day.date}>
          <div className="flex flex-wrap items-center justify-between gap-[8px] [&_>_span]:p-[4px_7px] [&_>_span]:rounded-[20px] [&_>_span]:bg-[#eaf5ed] [&_>_span]:text-[#227247] [&_>_span]:text-[10px] [&_>_span]:font-[650]"><h3><time dateTime={day.date}>{formatDate(day.date)}</time></h3>{day.date === forecast.best_date && <span>Best match</span>}</div>
          <dl>
            <div><dt>Rainfall</dt><dd>{metric(day.rainfall_mm, "mm")}</dd></div>
            <div><dt>Rain chance</dt><dd>{metric(day.rain_probability_percent, "%")}</dd></div>
            <div><dt>Temperature</dt><dd>{day.temperature_min_c === null || day.temperature_max_c === null ? "Unavailable" : `${day.temperature_min_c}–${day.temperature_max_c} °C`}</dd></div>
            <div><dt>Max. wind</dt><dd>{metric(day.wind_max_m_s, "m/s")}</dd></div>
          </dl>
          {day.thunderstorm && <p className="[&]:text-[#956222]">Thunderstorms forecast</p>}
          {!day.complete && <p className="[&]:text-[#956222]">Incomplete forecast</p>}
        </article>)}</div>
        <details className="mt-[18px] text-[#64766e] text-[11px] leading-[1.8] [&_summary]:cursor-pointer [&_summary]:text-[#37694f] [&_summary]:font-[600] [&_summary:focus-visible]:[outline:2px_solid_#087653] [&_summary:focus-visible]:outline-offset-[3px] [&_p]:m-[8px_0_0]"><summary>How is the day selected?</summary><p>{forecast.method}</p><p>This is a weather comparison, not a guarantee of harvesting conditions. Confirm leaf readiness and field conditions before harvesting.</p></details>
        <p className="hp-weather-note m-[15px_0_0] text-[10px] leading-[1.8] text-[#64766e] [&_a]:text-[#285d43] [&_a]:underline [&_a]:[text-underline-offset:2px]">Source: <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a> · Forecasts can change. Updated {new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Colombo" }).format(new Date(forecast.updated_at))} (Sri Lanka time).</p>
      </>}
    </div>
  </section>;
}
