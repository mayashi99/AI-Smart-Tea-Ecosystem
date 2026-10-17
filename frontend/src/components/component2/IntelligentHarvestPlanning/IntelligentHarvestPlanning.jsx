import { useEffect, useRef, useState } from "react";
import "./IntelligentHarvestPlanning.css";
import { analyseHarvestPhotos, MAX_PHOTOS, summarizeHarvestReadiness, validatePhotoSelection, validateTeaPhotos } from "./harvestPhotos";
import { emptyClimate, fetchPlanningClimate, getSriLankaDate, harvestPeriod } from "./planningClimate";
import HarvestForecast from "./HarvestForecast";

function PlanningIcon({ type = "leaf" }) {
  const paths = {
    leaf: "M20 4C11 3 4 7 4 14a6 6 0 0 0 6 6c7 0 10-8 10-16ZM4 20 15 9",
    upload: "M12 16V4m-4 4 4-4 4 4M4 15v5h16v-5",
    arrow: "M4 12h16m-6-6 6 6-6 6",
    location: "M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0ZM15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0",
    weather: "M12 2v2m0 16v2M2 12h2m16 0h2M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2M17 12a5 5 0 1 1-10 0 5 5 0 0 1 10 0",
    chart: "M4 4v16h17M9 15v-4m5 4V7m5 8v-6",
    check: "m5 12 4 4L19 6",
    close: "m6 6 12 12M6 18 18 6",
    calendar: "M8 2v4m8-4v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z",
    refresh: "M20 7v5h-5M4 17v-5h5M6 6a8 8 0 0 1 13 3M5 15a8 8 0 0 0 13 3",
    temperature: "M9 14.5V5a3 3 0 0 1 6 0v9.5a5 5 0 1 1-6 0ZM12 9v9m5-12h3m-3 4h2",
    water: "M12 3S5 11 5 15a7 7 0 0 0 14 0c0-4-7-12-7-12ZM8 15a4 4 0 0 0 4 4",
    wind: "M3 8h12a3 3 0 1 0-3-3M3 12h16a2 2 0 1 1-2 2M3 16h8a3 3 0 1 1-3 3",
  };
  return <svg aria-hidden="true" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d={paths[type]} /></svg>;
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

const GROWN_TYPE_LOCATIONS = {
  "HIGH grown": ["Nuwara Eliya", "Dimbula", "Uva"],
  "LOW grown": ["Galle", "Kalutara", "Kegalle", "Matara", "Ratnapura"],
  "MID grown": ["Badulla", "Kandy", "Matale", "Nawalapitiya"],
};

const API = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? "" : "http://127.0.0.1:8000");

export default function IntelligentHarvestPlanning() {
  const [photos, setPhotos] = useState([]);
  const previewUrls = useRef(new Set());
  const validationController = useRef(null);
  const [validatingPhotos, setValidatingPhotos] = useState(false);
  const [photoError, setPhotoError] = useState("");

  useEffect(() => {
    const urls = previewUrls.current;
    return () => {
      validationController.current?.abort();
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  function clearResults() {
    setReadiness([]);
    setYieldResult(null);
    setError("");
    setCompletedPhotos(0);
  }

  async function handleImageChange(event) {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    if (!files.length || loading || validationController.current) return;
    clearResults();
    setPhotoError("");
    const validationError = validatePhotoSelection(photos.length, files);
    if (validationError) {
      setPhotoError(validationError);
      return;
    }
    const controller = new AbortController();
    validationController.current = controller;
    setValidatingPhotos(true);
    try {
      await validateTeaPhotos(files, API, controller.signal);
      if (controller.signal.aborted) return;
      const added = files.map((file) => {
        const preview = URL.createObjectURL(file);
        previewUrls.current.add(preview);
        return { id: crypto.randomUUID(), file, preview };
      });
      setPhotos((previous) => [...previous, ...added]);
    } catch (err) {
      if (!controller.signal.aborted) {
        setPhotoError(err instanceof TypeError
          ? "Unable to check photos. Please make sure the backend is running and try again."
          : err.message);
      }
    } finally {
      if (!controller.signal.aborted) setValidatingPhotos(false);
      validationController.current = null;
    }
  }

  function removePhoto(id) {
    if (loading || validatingPhotos) return;
    setPhotoError("");
    const photo = photos.find((item) => item.id === id);
    if (!photo) return;
    URL.revokeObjectURL(photo.preview);
    previewUrls.current.delete(photo.preview);
    setPhotos((previous) => previous.filter((item) => item.id !== id));
    clearResults();
  }

  function clearAllPhotos() {
    if (loading || validatingPhotos) return;
    setPhotoError("");
    previewUrls.current.forEach((url) => URL.revokeObjectURL(url));
    previewUrls.current.clear();
    setPhotos([]);
    clearResults();
  }

  const [location, setLocation] = useState("Galle");
  const [grownType, setGrownType] = useState("LOW grown");
  const [today, setToday] = useState(getSriLankaDate);
  const currentPeriod = harvestPeriod(today);
  const [year, setYear] = useState(currentPeriod.year);
  const [month, setMonth] = useState(currentPeriod.month);
  const [week, setWeek] = useState(currentPeriod.week);
  const [climate, setClimate] = useState(emptyClimate);
  const [weatherStatus, setWeatherStatus] = useState("loading");
  const [weatherError, setWeatherError] = useState("");
  const [weatherRefresh, setWeatherRefresh] = useState(0);
  const [weatherEdited, setWeatherEdited] = useState(false);

  useEffect(() => {
    const updateDate = () => setToday(getSriLankaDate());
    const timer = window.setInterval(updateDate, 60000);
    window.addEventListener("focus", updateDate);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", updateDate);
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setClimate(emptyClimate());
    setWeatherStatus("loading");
    setWeatherError("");
    setWeatherEdited(false);
    setYieldResult(null);
    const timeout = window.setTimeout(() => {
      controller.abort();
      if (active) {
        setWeatherStatus("error");
        setWeatherError("Weather is taking too long to load. Retry or enter your field conditions manually.");
      }
    }, 35000);
    fetchPlanningClimate(API, location, today, controller.signal)
      .then((values) => {
        if (!active || controller.signal.aborted) return;
        setClimate(values);
        setWeatherStatus(Object.values(values).some((value) => value === "") ? "partial" : "ready");
      })
      .catch((err) => {
        if (!active || controller.signal.aborted) return;
        setWeatherStatus("error");
        setWeatherError(err.message);
      })
      .finally(() => window.clearTimeout(timeout));
    return () => {
      active = false;
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, [location, today, weatherRefresh]);

  const [readiness, setReadiness] = useState([]);
  const [completedPhotos, setCompletedPhotos] = useState(0);
  const [yieldResult, setYieldResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function handleGrownTypeChange(event) {
    const nextGrownType = event.target.value;
    const locations = GROWN_TYPE_LOCATIONS[nextGrownType];
    setGrownType(nextGrownType);
    setLocation((previous) => locations.includes(previous) ? previous : locations[0]);
    setYieldResult(null);
  }

  async function handleSubmit(e) {
    e.preventDefault();

    if (weatherStatus === "loading" || loading || validationController.current || photoError) return;

    if (!photos.length) {
      setError("Please add at least one tea bush photo.");
      return;
    }

    setLoading(true);
    setError("");
    setReadiness([]);
    setCompletedPhotos(0);
    setYieldResult(null);

    try {
      const photoResults = await analyseHarvestPhotos(photos, API, (result, completed) => {
        setReadiness((previous) => [...previous, result]);
        setCompletedPhotos(completed);
      });

      const summary = summarizeHarvestReadiness(photoResults);
      if (summary.label !== "Harvest Ready") return;

      // Step 2: Call the existing CatBoost Expected Yield API.
      const yieldResponse = await fetch(
        `${API}/component02/expected-yield/predict`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            Year: Number(year),
            Month_Number: Number(month),
            Week_Number: Number(week),
            ...climate,
            Location: location,
            Grown_Type: grownType,
          }),
        }
      );

      const yieldData = await yieldResponse.json();

      if (!yieldResponse.ok) {
        throw new Error(
          yieldData.detail || "Expected yield prediction failed."
        );
      }

      setYieldResult(yieldData);
    } catch (err) {
      setError(err.message || "Unable to complete harvest planning.");
    } finally {
      setLoading(false);
    }
  }

  const readinessSummary = summarizeHarvestReadiness(readiness);
  const canPredictYield = readinessSummary.label === "Harvest Ready";
  const successfulPhotos = readinessSummary.successfulCount;
  const photosStillProcessing = loading && completedPhotos < photos.length;
  const allPhotosSucceeded = readiness.length === photos.length && successfulPhotos === photos.length;
  const progressLabel = completedPhotos < photos.length
    ? `Analysing photo ${completedPhotos + 1} of ${photos.length}…`
    : canPredictYield ? "Estimating expected yield…" : "Completing readiness analysis…";
  const todayLabel = new Intl.DateTimeFormat("en-GB", {
    day: "numeric", month: "long", year: "numeric", timeZone: "Asia/Colombo",
  }).format(new Date(`${today}T12:00:00+05:30`));

  return (
    <main className="harvest-planner">
      <div className="hp-container">
        <header className="hp-page-heading">
          <div><span className="hp-overline">FIELD INTELLIGENCE</span><h1>Harvest planning</h1><p>Assess your crop’s readiness and plan your next harvest with confidence.</p></div>
          <div className="hp-date-label"><PlanningIcon type="calendar" /><div><time dateTime={today}>{todayLabel}</time><span>Sri Lanka · Asia/Colombo</span></div></div>
        </header>

        <form onSubmit={handleSubmit}>
          <fieldset className="hp-form-fields" disabled={loading || validatingPhotos}>
            <legend className="hp-sr-only">Harvest planning inputs</legend>
            <div className="hp-workspace">
              <section className="hp-card hp-photo-card" aria-labelledby="hp-photo-title">
                <div className="hp-section-heading"><span className="hp-step">01</span><div><h2 id="hp-photo-title">Crop photos</h2><p>One field. Multiple perspectives.</p></div></div>
                <div className="hp-photo-counter" role="status"><span>{photos.length} photos selected</span><span>{photos.length} / {MAX_PHOTOS}</span></div>
                <progress className="hp-photo-capacity" aria-label="Photo upload capacity" max={MAX_PHOTOS} value={photos.length} />
                <div className="hp-photo-area">
                  {/* Keep the empty upload layout as the size reference at every screen width. */}
                  <label className={`hp-upload ${photos.length ? "hp-upload-placeholder" : ""}`} aria-hidden={photos.length > 0 ? true : undefined}>
                    <input aria-label="Add tea bush photos" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={handleImageChange} disabled={photos.length > 0} />
                    <span className="hp-upload-icon"><PlanningIcon type="upload" /></span>
                    <strong>Upload tea bush photos</strong>
                    <span>Choose up to 10 images from your field</span><span className="hp-upload-browse">Browse photos <PlanningIcon type="arrow" /></span><small>JPG, PNG or WEBP · Up to 10 MB each</small>
                  </label>
                  {photos.length > 0 && <div className="hp-selected-photos">
                    <div className="hp-photo-scroll" role="region" aria-label="Selected crop photos" tabIndex={loading ? -1 : 0}>
                      <div className="hp-photo-grid">
                        {photos.map((photo, index) => <figure className="hp-photo-tile" key={photo.id}>
                          <img src={photo.preview} alt={`Tea bush photo ${index + 1}: ${photo.file.name}`} />
                          <button type="button" className="hp-remove-photo" aria-label={`Remove photo ${index + 1}: ${photo.file.name}`} onClick={() => removePhoto(photo.id)}><PlanningIcon type="close" /></button>
                          <figcaption title={photo.file.name}>{photo.file.name}</figcaption>
                        </figure>)}
                      </div>
                    </div>
                    {photos.length < MAX_PHOTOS ? <label className="hp-upload hp-upload-more">
                      <input aria-label="Add more tea bush photos" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={handleImageChange} />
                      <PlanningIcon type="upload" /><strong>Add more photos</strong><small>{MAX_PHOTOS - photos.length} slots available</small>
                    </label> : <p className="hp-photo-limit">All 10 photo slots filled. Remove a photo to add another.</p>}
                  </div>}
                </div>
                {validatingPhotos && <p role="status">Checking photos for tea leaves…</p>}
                {photoError && <div className="hp-error" role="alert"><strong>Please check your photos.</strong><p>{photoError}</p></div>}
                <div className="hp-photo-tip"><PlanningIcon /><div><strong>For a more useful assessment</strong><ul><li>Keep tea leaves clear and in focus.</li><li>Use natural light and avoid deep shadows.</li><li>Include different areas of the same field.</li></ul></div></div>
                <div className="hp-photo-summary"><PlanningIcon type="chart" /><p>All photos contribute to <strong>one overall readiness score.</strong></p></div>
              </section>

              <div className="hp-details">
                <section className="hp-card" aria-labelledby="hp-field-title">
                  <div className="hp-section-heading"><span className="hp-step">02</span><div><h2 id="hp-field-title">Field details</h2><p>Select your growing region and harvest period.</p></div><span className="hp-section-icon"><PlanningIcon type="location" /></span></div>
                  <div className="hp-field-grid hp-grid-two">
                    <label className="hp-field">Grown type<select value={grownType} onChange={handleGrownTypeChange}><option value="LOW grown">Low grown</option><option value="MID grown">Mid grown</option><option value="HIGH grown">High grown</option></select></label>
                    <label className="hp-field">Location<select value={location} onChange={(e) => setLocation(e.target.value)}>{GROWN_TYPE_LOCATIONS[grownType].map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
                  </div>
                  <div className="hp-field-grid hp-grid-three hp-period-fields">
                    <label className="hp-field">Year<input type="number" min="2016" max="2100" value={year} onChange={(e) => setYear(e.target.value)} required /></label>
                    <label className="hp-field">Month<select value={month} onChange={(e) => setMonth(e.target.value)}>{MONTHS.map((name, index) => <option key={name} value={index + 1}>{name}</option>)}</select></label>
                    <label className="hp-field">Week<select value={week} onChange={(e) => setWeek(e.target.value)}>{[1, 2, 3, 4].map((number) => <option key={number} value={number}>Week {number}</option>)}</select></label>
                  </div>
                </section>

                <section className="hp-card hp-climate-card" aria-labelledby="hp-climate-title" aria-busy={weatherStatus === "loading"}>
                  <div className="hp-section-heading"><span className="hp-step">03</span><div><h2 id="hp-climate-title">Climate conditions</h2><p>Today’s weather for {location}. Adjust values if needed.</p></div><span className={`hp-data-badge ${weatherStatus === "error" || weatherStatus === "partial" ? "hp-data-badge-warning" : ""}`}><span />{weatherStatus === "loading" ? "Updating" : weatherStatus === "error" ? "Unavailable" : weatherStatus === "partial" ? "Incomplete" : weatherEdited ? "Edited" : "Auto-filled"}</span></div>
                  <div className="hp-weather-summary">
                    <div className="hp-weather-place"><PlanningIcon type="location" /><div><strong>{location} area</strong><span><time dateTime={today}>{todayLabel}</time> · Sri Lanka time</span></div></div>
                    <button type="button" className="hp-weather-refresh" disabled={weatherStatus === "loading"} onClick={() => setWeatherRefresh((value) => value + 1)}><PlanningIcon type="refresh" />{weatherStatus === "loading" ? "Loading…" : "Refresh weather"}</button>
                  </div>
                  <p className={`hp-weather-status ${weatherStatus === "error" ? "hp-weather-warning" : ""}`} role="status">
                    {weatherStatus === "loading" ? "Getting today’s climate conditions…" : weatherStatus === "error" ? weatherError : weatherStatus === "partial" ? "Some weather values are unavailable. Please fill in the empty fields." : "Today’s weather loaded automatically."}
                    {weatherEdited && " Values manually edited."}
                  </p>
                  <div className="hp-climate-grid">
                    {[["Temperature", "Temperature", "°C", "temperature"], ["Rainfall", "Rainfall_mm", "mm/day", "water"], ["Humidity", "Humidity", "%", "water"], ["Wind speed", "Wind_Speed", "m/s", "wind"], ["Solar radiation", "Solar_Radiation", "W/m²", "weather"]].map(([label, key, unit, icon]) => (
                      <label className="hp-climate-field" key={key}><span className="hp-climate-label"><PlanningIcon type={icon} />{label}</span><input aria-label={`${label} (${unit})`} type="number" step="any" min={key === "Temperature" ? undefined : 0} max={key === "Humidity" ? 100 : undefined} value={climate[key]} disabled={weatherStatus === "loading"} placeholder={weatherStatus === "loading" ? "…" : "—"} onChange={(e) => { setClimate((previous) => ({ ...previous, [key]: e.target.value === "" ? "" : Number(e.target.value) })); setWeatherEdited(true); setYieldResult(null); }} required /><span className="hp-climate-unit">{unit}</span></label>
                    ))}
                  </div>
                  <p className="hp-weather-note">Source: <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a>. Temperature, humidity and wind use current conditions when available. Rainfall is today’s forecast total; solar radiation is the daily average.</p>
                  {(Number(year) !== currentPeriod.year || Number(month) !== currentPeriod.month || Number(week) !== currentPeriod.week) && <p className="hp-weather-note hp-weather-warning">Your harvest period differs from today. These values describe today; adjust them to represent your selected harvest period before predicting.</p>}
                </section>
              </div>
            </div>
          </fieldset>
          <div className="hp-action-bar">
            <div className="hp-action-context"><span className="hp-action-icon"><PlanningIcon type={photos.length ? "check" : "upload"} /></span><div><strong>{photos.length ? `${photos.length} ${photos.length === 1 ? "photo" : "photos"} selected for analysis` : "Start with your crop photos"}</strong><p>{photos.length ? `${location} · ${MONTHS[Number(month) - 1]} ${year} · Week ${week}` : "Add at least one photo, then review your field details."}</p></div></div>
            <div className="hp-action-buttons">
              {photos.length > 0 && <button type="button" className="hp-clear-photos" onClick={clearAllPhotos} disabled={loading}><PlanningIcon type="close" /> Clear all photos</button>}
              <button className="hp-submit" type="submit" disabled={loading || validatingPhotos || !!photoError || !photos.length || weatherStatus === "loading"}>{validatingPhotos ? <><span className="hp-spinner" /> Checking tea photos…</> : loading ? <><span className="hp-spinner" /> {progressLabel}</> : <>Analyse & Predict <PlanningIcon type="arrow" /></>}</button>
            </div>
          </div>
        </form>

        {error && <div className="hp-error" role="alert"><strong>Please check the following.</strong><p>{error}</p></div>}

        <section className="hp-results" aria-labelledby="hp-results-title" aria-busy={loading}>
          <div className="hp-workspace-heading"><div><span className="hp-overline">FIELD INSIGHTS</span><h2 id="hp-results-title">Your harvest outlook</h2></div>{readiness.length > 0 && completedPhotos === photos.length && !loading && !error && (!canPredictYield || yieldResult) && <span className="hp-complete"><PlanningIcon type="check" /> {allPhotosSucceeded ? "Analysis complete" : "Completed with photo errors"}</span>}</div>
          <div aria-live="polite">
            {!readiness.length && !yieldResult ? <div className="hp-empty"><span className={`hp-empty-icon ${loading ? "hp-pulse" : ""}`}><PlanningIcon type="chart" /></span><div><h3>{loading ? "Taking a closer look at your field" : "Your next harvest starts here"}</h3><p>{loading ? progressLabel : "Add up to 10 photos and your field details, then analyse to see your harvest insights."}</p></div></div> : <div className={`hp-result-grid ${!photosStillProcessing && !canPredictYield ? "hp-result-grid-single" : ""}`}>
              {readiness.length > 0 && <article className={`hp-result-card ${photosStillProcessing ? "" : readinessSummary.readyPercent === null ? "hp-photo-failed" : readinessSummary.readyPercent > 50 ? "hp-ready" : "hp-review"}`}>
                <div className="hp-result-top"><span><PlanningIcon /> Overall harvest readiness</span><span className="hp-result-tag">{photosStillProcessing ? "ANALYSING" : readinessSummary.failedCount ? "PARTIAL RESULT" : "ALL PHOTOS"}</span></div>
                {photosStillProcessing ? <div className="hp-readiness-loading"><span className="hp-spinner" /><p>{completedPhotos} / {photos.length} photos checked. Calculating the overall average…</p></div> : <>
                  <h3 className="hp-readiness-title">{readinessSummary.label}</h3>
                  {readinessSummary.readyPercent !== null && <>
                    <div className="hp-readiness-score"><strong>{readinessSummary.readyPercent.toFixed(1)}<span>%</span></strong><span>Average harvest-ready<br />probability</span></div>
                    <progress className="hp-confidence" aria-label="Average harvest-ready probability across analysed photos" max="100" value={readinessSummary.readyPercent} />
                    <p className="hp-weather-note">Average of {successfulPhotos} {successfulPhotos === 1 ? "photo" : "photos"}, with each photo weighted equally.</p>
                  </>}
                  <p className="hp-weather-note">{successfulPhotos} / {photos.length} photos analysed successfully.</p>
                  {readinessSummary.failedCount > 0 && <p className="hp-photo-error hp-readiness-error">{readinessSummary.failedCount} {readinessSummary.failedCount === 1 ? "photo could" : "photos could"} not be analysed. {successfulPhotos ? "This average includes only successful photos. " : ""}Please retry to include all photos.</p>}
                </>}
              </article>}
              {canPredictYield && yieldResult ? <article className="hp-result-card hp-yield"><div className="hp-result-top"><span><PlanningIcon type="chart" /> Expected yield</span><span className="hp-result-tag">YIELD ESTIMATE</span></div><h3>{Number(yieldResult.predicted_kg_per_Acre).toLocaleString(undefined, { maximumFractionDigits: 2 })}<span>kg / acre</span></h3><p className="hp-yield-margin">Planning margin: <strong>±7 kg / acre</strong></p><p className="hp-result-description">One field estimate for your selected harvest period</p><div className="hp-yield-meta"><span><PlanningIcon type="location" />{yieldResult.location}</span><span>{MONTHS[Number(yieldResult.month) - 1]} {yieldResult.year} · Week {yieldResult.week}</span></div></article> : loading && !photosStillProcessing && canPredictYield && <div className="hp-result-card hp-pending"><span className="hp-spinner" /><p>{progressLabel}</p></div>}
            </div>}
          </div>
        </section>
        {canPredictYield && !photosStillProcessing && <HarvestForecast key={`${location}:${today}`} api={API} location={location} today={today} />}
        <footer className="hp-footer"><PlanningIcon /><span>AI Smart Tea Ecosystem</span><span>Intelligent harvest planning</span></footer>
      </div>
    </main>
  );
}
