import { useEffect, useRef, useState } from "react";
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
  const [readiness, setReadiness] = useState([]);
  const [completedPhotos, setCompletedPhotos] = useState(0);
  const [yieldResult, setYieldResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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
    // This effect starts a new request whenever its inputs change, so its UI
    // state must be reset before the new response is received.
    // eslint-disable-next-line react-hooks/set-state-in-effect
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
    <main className="bg-[#f5f7f6] text-[#193b30] min-h-[100vh] [font-family:inherit] [&_*]:box-border [&_button:focus-visible]:[outline:3px_solid_#78b792] [&_button:focus-visible]:outline-offset-[3px] motion-reduce:[&_*]:animate-none! motion-reduce:[&_*]:[transition:none]! motion-reduce:[&_*::before]:animate-none! motion-reduce:[&_*::before]:[transition:none]! motion-reduce:[&_*::after]:animate-none! motion-reduce:[&_*::after]:[transition:none]!">
      <div className="max-w-[1280px] m-[0_auto] p-[38px_32px_0] max-[1120.01px]:px-[24px] max-[560.01px]:p-[26px_16px_0]">
        <header className="flex items-center justify-between gap-[24px] mb-[30px] [&_h1]:m-[8px_0_9px] [&_h1]:text-[clamp(27px,_3vw,_36px)] [&_h1]:font-[750] [&_h1]:tracking-[-1.25px] [&_h1]:leading-[1.15] [&_p]:m-[0] [&_p]:text-[13px] [&_p]:leading-[1.7] [&_p]:text-[#64766e] max-[800.01px]:items-start max-[560.01px]:flex-col max-[560.01px]:gap-[17px] max-[560.01px]:mb-[23px] max-[560.01px]:[&_h1]:text-[30px]">
          <div><span className="block text-[10px] font-[750] tracking-[2px] text-[#087653]">FIELD INTELLIGENCE</span><h1>Harvest planning</h1><p>Assess your crop’s readiness and plan your next harvest with confidence.</p></div>
          <div className="flex items-center shrink-0 gap-[12px] [border:1px_solid_#e0e8e3] rounded-[12px] bg-[white] p-[13px_18px] [&_>_svg]:w-[20px] [&_>_svg]:text-[#087653] [&_time]:block [&_time]:text-[12px] [&_time]:font-[650] [&_span]:block [&_span]:text-[#64766e] [&_span]:text-[10px] [&_span]:mt-[4px] max-[800.01px]:p-[10px_12px] max-[800.01px]:[&_>_svg]:hidden max-[560.01px]:[border:0] max-[560.01px]:bg-[transparent] max-[560.01px]:p-[0] max-[560.01px]:[&_>_svg]:block max-[560.01px]:[&_>_svg]:w-[17px] max-[560.01px]:[&_span]:hidden"><PlanningIcon type="calendar" /><div><time dateTime={today}>{todayLabel}</time><span>Sri Lanka · Asia/Colombo</span></div></div>
        </header>

        <form onSubmit={handleSubmit}>
          <fieldset className="m-[0] p-[0] min-w-[0] [border:0] [&:disabled]:opacity-[.7]" disabled={loading || validatingPhotos}>
            <legend className="absolute w-[1px] h-[1px] p-[0] m-[-1px] overflow-hidden [clip:rect(0,0,0,0)] whitespace-nowrap [border:0]">Harvest planning inputs</legend>
            <div className="grid grid-cols-[minmax(290px,_.9fr)_minmax(0,_2fr)] gap-[22px] items-start max-[1120.01px]:grid-cols-[minmax(260px,_.85fr)_minmax(0,_1.7fr)] max-[1120.01px]:gap-[18px] max-[800.01px]:grid-cols-[1fr]">
              <section className="min-w-[0] bg-[white] [border:1px_solid_#e0e8e3] p-[25px] rounded-[16px] [box-shadow:0_3px_12px_#183b2c03] max-[1120.01px]:p-[20px] max-[560.01px]:p-[20px_17px] hp-photo-card" aria-labelledby="hp-photo-title">
                <div className="hp-section-heading flex items-center gap-[12px] mb-[23px] [&_h2]:text-[16px] [&_h2]:font-[700] [&_h2]:m-[0_0_5px] [&_h2]:leading-[1.25] [&_h2]:tracking-[-.3px] [&_p]:text-[11px] [&_p]:text-[#64766e] [&_p]:m-[0] [&_p]:leading-[1.6] max-[560.01px]:gap-[10px] max-[560.01px]:[&_h2]:text-[15px]"><span className="[flex:0_0_34px] h-[34px] grid place-items-center [border:1px_solid_#dbeae1] rounded-[10px] bg-[#f0f7f3] text-[#087653] text-[11px] font-[750]">01</span><div><h2 id="hp-photo-title">Crop photos</h2><p>One field. Multiple perspectives.</p></div></div>
                <div className="flex justify-between gap-[8px] text-[#64766e] text-[11px] mb-[9px] [&_>_span:first-child]:font-[600] [&_>_span:first-child]:text-[#3d5c4e] [&_>_span:last-child]:tabular-nums" role="status"><span>{photos.length} photos selected</span><span>{photos.length} / {MAX_PHOTOS}</span></div>
                <progress className="block appearance-none w-[100%] h-[4px] overflow-hidden [border:0] rounded-[4px] bg-[#edf2ef] text-[#087653] mb-[20px] [&::-webkit-progress-bar]:bg-[#edf2ef] [&::-webkit-progress-value]:bg-[#087653] [&::-webkit-progress-value]:rounded-[4px] [&::-moz-progress-bar]:bg-[#087653] [&::-moz-progress-bar]:rounded-[4px]" aria-label="Photo upload capacity" max={MAX_PHOTOS} value={photos.length} />
                <div className="relative">
                  {/* Keep the empty upload layout as the size reference at every screen width. */}
                  <label className={`relative flex min-h-[276px] flex-col items-center justify-center gap-[9px] p-[24px_12px] text-center bg-[#f8fbf9] [border:1.5px_dashed_#b6cec0] rounded-[12px] overflow-hidden [transition:background_.2s,_border-color_.2s] [&:hover]:bg-[#eff8f3] [&:hover]:[border-color:#087653] [&:focus-within]:[outline:3px_solid_#90bda4] [&:focus-within]:outline-offset-[3px] [&_input]:absolute [&_input]:[inset:0] [&_input]:w-[100%] [&_input]:h-[100%] [&_input]:cursor-pointer [&_input]:opacity-[0] [&_input]:z-[2] [&_strong]:text-[14px] [&_strong]:font-[650] [&_>_span:not(.hp-upload-icon):not(.hp-upload-browse)]:text-[#64766e] [&_>_span:not(.hp-upload-icon):not(.hp-upload-browse)]:text-[11px] [&_>_span:not(.hp-upload-icon):not(.hp-upload-browse)]:leading-[1.6] [&_small]:mt-[8px] [&_small]:text-[10px] [&_small]:leading-[1.6] [&_small]:text-[#64766e] [&.hp-upload-more]:min-h-[56px] [&.hp-upload-more]:shrink-0 [&.hp-upload-more]:flex-row [&.hp-upload-more]:flex-wrap [&.hp-upload-more]:p-[10px] [&.hp-upload-more]:gap-[6px_9px] max-[800.01px]:min-h-[230px] ${photos.length ? "[&]:[visibility:hidden] [&]:pointer-events-none" : ""}`} aria-hidden={photos.length > 0 ? true : undefined}>
                    <input aria-label="Add tea bush photos" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={handleImageChange} disabled={photos.length > 0} />
                    <span className="hp-upload-icon grid place-items-center w-[54px] h-[54px] mb-[8px] bg-[white] text-[#087653] [border:1px_solid_#dcebe1] rounded-[16px] [box-shadow:0_4px_8px_#184c3010]"><PlanningIcon type="upload" /></span>
                    <strong>Upload tea bush photos</strong>
                    <span>Choose up to 10 images from your field</span><span className="hp-upload-browse flex items-center gap-[10px] mt-[8px] bg-[white] [border:1px_solid_#cdded3] rounded-[7px] p-[8px_12px] text-[#087653] text-[11px] font-[650] [&_svg]:w-[15px] [&_svg]:h-[15px]">Browse photos <PlanningIcon type="arrow" /></span><small>JPG, PNG or WEBP · Up to 10 MB each</small>
                  </label>
                  {photos.length > 0 && <div className="absolute [inset:0] flex flex-col gap-[12px] min-h-[0]">
                    <div className="[flex:1] min-h-[0] [overflow-y:auto] [overflow-x:hidden] [scrollbar-gutter:stable] [overscroll-behavior-y:contain] p-[3px] rounded-[10px] [&:focus-visible]:[outline:2px_solid_#087653] [&:focus-visible]:outline-offset-[2px]" role="region" aria-label="Selected crop photos" tabIndex={loading ? -1 : 0}>
                      <div className="grid grid-cols-[repeat(2,_minmax(0,_1fr))] gap-[10px] max-[800.01px]:grid-cols-[repeat(3,_minmax(0,_1fr))] max-[560.01px]:grid-cols-[repeat(2,_minmax(0,_1fr))]">
                        {photos.map((photo, index) => <figure className="relative min-w-[0] m-[0] overflow-hidden [border:1px_solid_#e0e8e3] rounded-[10px] bg-[#f8faf9] [&_img]:block [&_img]:w-[100%] [&_img]:[aspect-ratio:1.15] [&_img]:object-cover [&_figcaption]:p-[8px] [&_figcaption]:text-[10px] [&_figcaption]:text-[#4f6a5e] [&_figcaption]:overflow-hidden [&_figcaption]:text-ellipsis [&_figcaption]:whitespace-nowrap" key={photo.id}>
                          <img src={photo.preview} alt={`Tea bush photo ${index + 1}: ${photo.file.name}`} />
                          <button type="button" className="absolute top-[6px] right-[6px] w-[30px] h-[30px] grid place-items-center [border:1px_solid_#ffffffb0] rounded-[50%] bg-[#fffffff2] text-[#34583e] cursor-pointer [box-shadow:0_2px_8px_#00000020] [&_svg]:w-[16px] [&_svg]:h-[16px] [&:hover:not(:disabled)]:bg-[#fff0eb] [&:hover:not(:disabled)]:text-[#a63e2c] [&:disabled]:cursor-wait [&:disabled]:opacity-[.6]" aria-label={`Remove photo ${index + 1}: ${photo.file.name}`} onClick={() => removePhoto(photo.id)}><PlanningIcon type="close" /></button>
                          <figcaption title={photo.file.name}>{photo.file.name}</figcaption>
                        </figure>)}
                      </div>
                    </div>
                    {photos.length < MAX_PHOTOS ? <label className="relative flex min-h-[276px] flex-col items-center justify-center gap-[9px] p-[24px_12px] text-center bg-[#f8fbf9] [border:1.5px_dashed_#b6cec0] rounded-[12px] overflow-hidden [transition:background_.2s,_border-color_.2s] [&:hover]:bg-[#eff8f3] [&:hover]:[border-color:#087653] [&:focus-within]:[outline:3px_solid_#90bda4] [&:focus-within]:outline-offset-[3px] [&_input]:absolute [&_input]:[inset:0] [&_input]:w-[100%] [&_input]:h-[100%] [&_input]:cursor-pointer [&_input]:opacity-[0] [&_input]:z-[2] [&_strong]:text-[14px] [&_strong]:font-[650] [&_>_span:not(.hp-upload-icon):not(.hp-upload-browse)]:text-[#64766e] [&_>_span:not(.hp-upload-icon):not(.hp-upload-browse)]:text-[11px] [&_>_span:not(.hp-upload-icon):not(.hp-upload-browse)]:leading-[1.6] [&_small]:mt-[8px] [&_small]:text-[10px] [&_small]:leading-[1.6] [&_small]:text-[#64766e] [&.hp-upload-more]:min-h-[56px] [&.hp-upload-more]:shrink-0 [&.hp-upload-more]:flex-row [&.hp-upload-more]:flex-wrap [&.hp-upload-more]:p-[10px] [&.hp-upload-more]:gap-[6px_9px] max-[800.01px]:min-h-[230px] hp-upload-more [&_>_svg]:w-[18px] [&_>_svg]:h-[18px] [&_>_svg]:text-[#087653] [&_strong]:text-[12px] [&_small]:m-[0]">
                      <input aria-label="Add more tea bush photos" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={handleImageChange} />
                      <PlanningIcon type="upload" /><strong>Add more photos</strong><small>{MAX_PHOTOS - photos.length} slots available</small>
                    </label> : <p className="shrink-0 m-[0] p-[10px] rounded-[8px] bg-[#f0f6f2] text-[#64766e] text-[11px] leading-[1.6] text-center">All 10 photo slots filled. Remove a photo to add another.</p>}
                  </div>}
                </div>
                {validatingPhotos && <p role="status">Checking photos for tea leaves…</p>}
                {photoError && <div className="p-[16px_20px] bg-[#fff4f0] [border:1px_solid_#f1cabe] text-[#9a3d2c] rounded-[12px] mt-[20px] text-[12px] [&_p]:m-[5px_0_0] [&_p]:[overflow-wrap:anywhere]" role="alert"><strong>Please check your photos.</strong><p>{photoError}</p></div>}
                <div className="flex gap-[10px] pt-[22px] mt-[22px] [border-top:1px_solid_#edf1ee] [&_>_svg]:w-[18px] [&_>_svg]:h-[18px] [&_>_svg]:shrink-0 [&_>_svg]:text-[#6c927d] [&_strong]:block [&_strong]:text-[11px] [&_strong]:font-[650] [&_strong]:text-[#3d5c4e] [&_ul]:m-[9px_0_0] [&_ul]:pl-[13px] [&_ul]:text-[#64766e] [&_ul]:text-[11px] [&_ul]:leading-[1.8] [&_li_+_li]:mt-[4px]"><PlanningIcon /><div><strong>For a more useful assessment</strong><ul><li>Keep tea leaves clear and in focus.</li><li>Use natural light and avoid deep shadows.</li><li>Include different areas of the same field.</li></ul></div></div>
                <div className="flex items-center gap-[10px] mt-[22px] p-[13px] rounded-[9px] bg-[#f2f6f3] [&_svg]:w-[20px] [&_svg]:shrink-0 [&_svg]:text-[#5d8a73] [&_p]:m-[0] [&_p]:text-[11px] [&_p]:leading-[1.6] [&_p]:text-[#64766e] [&_strong]:font-[600] [&_strong]:text-[#3d5c4e]"><PlanningIcon type="chart" /><p>All photos contribute to <strong>one overall readiness score.</strong></p></div>
              </section>

              <div className="grid gap-[20px] min-w-[0]">
                <section className="min-w-[0] bg-[white] [border:1px_solid_#e0e8e3] p-[25px] rounded-[16px] [box-shadow:0_3px_12px_#183b2c03] max-[1120.01px]:p-[20px] max-[560.01px]:p-[20px_17px]" aria-labelledby="hp-field-title">
                  <div className="hp-section-heading flex items-center gap-[12px] mb-[23px] [&_h2]:text-[16px] [&_h2]:font-[700] [&_h2]:m-[0_0_5px] [&_h2]:leading-[1.25] [&_h2]:tracking-[-.3px] [&_p]:text-[11px] [&_p]:text-[#64766e] [&_p]:m-[0] [&_p]:leading-[1.6] max-[560.01px]:gap-[10px] max-[560.01px]:[&_h2]:text-[15px]"><span className="[flex:0_0_34px] h-[34px] grid place-items-center [border:1px_solid_#dbeae1] rounded-[10px] bg-[#f0f7f3] text-[#087653] text-[11px] font-[750]">02</span><div><h2 id="hp-field-title">Field details</h2><p>Select your growing region and harvest period.</p></div><span className="ml-[auto] text-[#8aa297] [&_svg]:w-[21px] max-[560.01px]:hidden"><PlanningIcon type="location" /></span></div>
                  <div className="grid gap-[16px] max-[560.01px]:gap-[12px] grid-cols-[repeat(2,_minmax(0,_1fr))] max-[360.01px]:grid-cols-[1fr]">
                    <label className="flex flex-col gap-[8px] text-[11px] font-[600] text-[#4d6358] min-w-[0] [&_input]:w-[100%] [&_input]:min-w-[0] [&_input]:h-[44px] [&_input]:p-[0_12px] [&_input]:[border:1px_solid_#dbe5df] [&_input]:rounded-[8px] [&_input]:bg-[#fcfdfc] [&_input]:text-[#263f33] [&_input]:[font-family:inherit] [&_input]:text-[13px] [&_input]:font-[500] [&_input]:[transition:border-color_.2s,_box-shadow_.2s] [&_select]:w-[100%] [&_select]:min-w-[0] [&_select]:h-[44px] [&_select]:p-[0_12px] [&_select]:[border:1px_solid_#dbe5df] [&_select]:rounded-[8px] [&_select]:bg-[#fcfdfc] [&_select]:text-[#263f33] [&_select]:[font-family:inherit] [&_select]:text-[13px] [&_select]:font-[500] [&_select]:[transition:border-color_.2s,_box-shadow_.2s] [&_input:hover]:[border-color:#9abca9] [&_select:hover]:[border-color:#9abca9] [&_input:focus]:[outline:none] [&_input:focus]:[border-color:#087653] [&_input:focus]:[box-shadow:0_0_0_3px_#08765312] [&_select:focus]:[outline:none] [&_select:focus]:[border-color:#087653] [&_select:focus]:[box-shadow:0_0_0_3px_#08765312]">Grown type<select value={grownType} onChange={handleGrownTypeChange}><option value="LOW grown">Low grown</option><option value="MID grown">Mid grown</option><option value="HIGH grown">High grown</option></select></label>
                    <label className="flex flex-col gap-[8px] text-[11px] font-[600] text-[#4d6358] min-w-[0] [&_input]:w-[100%] [&_input]:min-w-[0] [&_input]:h-[44px] [&_input]:p-[0_12px] [&_input]:[border:1px_solid_#dbe5df] [&_input]:rounded-[8px] [&_input]:bg-[#fcfdfc] [&_input]:text-[#263f33] [&_input]:[font-family:inherit] [&_input]:text-[13px] [&_input]:font-[500] [&_input]:[transition:border-color_.2s,_box-shadow_.2s] [&_select]:w-[100%] [&_select]:min-w-[0] [&_select]:h-[44px] [&_select]:p-[0_12px] [&_select]:[border:1px_solid_#dbe5df] [&_select]:rounded-[8px] [&_select]:bg-[#fcfdfc] [&_select]:text-[#263f33] [&_select]:[font-family:inherit] [&_select]:text-[13px] [&_select]:font-[500] [&_select]:[transition:border-color_.2s,_box-shadow_.2s] [&_input:hover]:[border-color:#9abca9] [&_select:hover]:[border-color:#9abca9] [&_input:focus]:[outline:none] [&_input:focus]:[border-color:#087653] [&_input:focus]:[box-shadow:0_0_0_3px_#08765312] [&_select:focus]:[outline:none] [&_select:focus]:[border-color:#087653] [&_select:focus]:[box-shadow:0_0_0_3px_#08765312]">Location<select value={location} onChange={(e) => setLocation(e.target.value)}>{GROWN_TYPE_LOCATIONS[grownType].map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
                  </div>
                  <div className="grid gap-[16px] max-[560.01px]:gap-[12px] grid-cols-[repeat(3,_minmax(0,_1fr))] max-[360.01px]:grid-cols-[1fr] mt-[20px] [border-top:1px_solid_#edf1ee] pt-[19px]">
                    <label className="flex flex-col gap-[8px] text-[11px] font-[600] text-[#4d6358] min-w-[0] [&_input]:w-[100%] [&_input]:min-w-[0] [&_input]:h-[44px] [&_input]:p-[0_12px] [&_input]:[border:1px_solid_#dbe5df] [&_input]:rounded-[8px] [&_input]:bg-[#fcfdfc] [&_input]:text-[#263f33] [&_input]:[font-family:inherit] [&_input]:text-[13px] [&_input]:font-[500] [&_input]:[transition:border-color_.2s,_box-shadow_.2s] [&_select]:w-[100%] [&_select]:min-w-[0] [&_select]:h-[44px] [&_select]:p-[0_12px] [&_select]:[border:1px_solid_#dbe5df] [&_select]:rounded-[8px] [&_select]:bg-[#fcfdfc] [&_select]:text-[#263f33] [&_select]:[font-family:inherit] [&_select]:text-[13px] [&_select]:font-[500] [&_select]:[transition:border-color_.2s,_box-shadow_.2s] [&_input:hover]:[border-color:#9abca9] [&_select:hover]:[border-color:#9abca9] [&_input:focus]:[outline:none] [&_input:focus]:[border-color:#087653] [&_input:focus]:[box-shadow:0_0_0_3px_#08765312] [&_select:focus]:[outline:none] [&_select:focus]:[border-color:#087653] [&_select:focus]:[box-shadow:0_0_0_3px_#08765312]">Year<input type="number" min="2016" max="2100" value={year} onChange={(e) => setYear(e.target.value)} required /></label>
                    <label className="flex flex-col gap-[8px] text-[11px] font-[600] text-[#4d6358] min-w-[0] [&_input]:w-[100%] [&_input]:min-w-[0] [&_input]:h-[44px] [&_input]:p-[0_12px] [&_input]:[border:1px_solid_#dbe5df] [&_input]:rounded-[8px] [&_input]:bg-[#fcfdfc] [&_input]:text-[#263f33] [&_input]:[font-family:inherit] [&_input]:text-[13px] [&_input]:font-[500] [&_input]:[transition:border-color_.2s,_box-shadow_.2s] [&_select]:w-[100%] [&_select]:min-w-[0] [&_select]:h-[44px] [&_select]:p-[0_12px] [&_select]:[border:1px_solid_#dbe5df] [&_select]:rounded-[8px] [&_select]:bg-[#fcfdfc] [&_select]:text-[#263f33] [&_select]:[font-family:inherit] [&_select]:text-[13px] [&_select]:font-[500] [&_select]:[transition:border-color_.2s,_box-shadow_.2s] [&_input:hover]:[border-color:#9abca9] [&_select:hover]:[border-color:#9abca9] [&_input:focus]:[outline:none] [&_input:focus]:[border-color:#087653] [&_input:focus]:[box-shadow:0_0_0_3px_#08765312] [&_select:focus]:[outline:none] [&_select:focus]:[border-color:#087653] [&_select:focus]:[box-shadow:0_0_0_3px_#08765312]">Month<select value={month} onChange={(e) => setMonth(e.target.value)}>{MONTHS.map((name, index) => <option key={name} value={index + 1}>{name}</option>)}</select></label>
                    <label className="flex flex-col gap-[8px] text-[11px] font-[600] text-[#4d6358] min-w-[0] [&_input]:w-[100%] [&_input]:min-w-[0] [&_input]:h-[44px] [&_input]:p-[0_12px] [&_input]:[border:1px_solid_#dbe5df] [&_input]:rounded-[8px] [&_input]:bg-[#fcfdfc] [&_input]:text-[#263f33] [&_input]:[font-family:inherit] [&_input]:text-[13px] [&_input]:font-[500] [&_input]:[transition:border-color_.2s,_box-shadow_.2s] [&_select]:w-[100%] [&_select]:min-w-[0] [&_select]:h-[44px] [&_select]:p-[0_12px] [&_select]:[border:1px_solid_#dbe5df] [&_select]:rounded-[8px] [&_select]:bg-[#fcfdfc] [&_select]:text-[#263f33] [&_select]:[font-family:inherit] [&_select]:text-[13px] [&_select]:font-[500] [&_select]:[transition:border-color_.2s,_box-shadow_.2s] [&_input:hover]:[border-color:#9abca9] [&_select:hover]:[border-color:#9abca9] [&_input:focus]:[outline:none] [&_input:focus]:[border-color:#087653] [&_input:focus]:[box-shadow:0_0_0_3px_#08765312] [&_select:focus]:[outline:none] [&_select:focus]:[border-color:#087653] [&_select:focus]:[box-shadow:0_0_0_3px_#08765312]">Week<select value={week} onChange={(e) => setWeek(e.target.value)}>{[1, 2, 3, 4].map((number) => <option key={number} value={number}>Week {number}</option>)}</select></label>
                  </div>
                </section>

                <section className="min-w-[0] bg-[white] [border:1px_solid_#e0e8e3] p-[25px] rounded-[16px] [box-shadow:0_3px_12px_#183b2c03] max-[1120.01px]:p-[20px] max-[560.01px]:p-[20px_17px] max-[560.01px]:[&_.hp-section-heading]:flex-wrap" aria-labelledby="hp-climate-title" aria-busy={weatherStatus === "loading"}>
                  <div className="hp-section-heading flex items-center gap-[12px] mb-[23px] [&_h2]:text-[16px] [&_h2]:font-[700] [&_h2]:m-[0_0_5px] [&_h2]:leading-[1.25] [&_h2]:tracking-[-.3px] [&_p]:text-[11px] [&_p]:text-[#64766e] [&_p]:m-[0] [&_p]:leading-[1.6] max-[560.01px]:gap-[10px] max-[560.01px]:[&_h2]:text-[15px]"><span className="[flex:0_0_34px] h-[34px] grid place-items-center [border:1px_solid_#dbeae1] rounded-[10px] bg-[#f0f7f3] text-[#087653] text-[11px] font-[750]">03</span><div><h2 id="hp-climate-title">Climate conditions</h2><p>Today’s weather for {location}. Adjust values if needed.</p></div><span className={`inline-flex items-center gap-[6px] shrink-0 ml-[auto] [border:1px_solid_#dbece1] rounded-[20px] p-[5px_8px] text-[10px] font-[600] text-[#2b7753] bg-[#f2faf5] [&_>_span]:w-[5px] [&_>_span]:h-[5px] [&_>_span]:bg-[currentColor] [&_>_span]:rounded-[50%] max-[560.01px]:ml-[44px] ${weatherStatus === "error" || weatherStatus === "partial" ? "[&]:bg-[#fff9ed] [&]:text-[#916323] [&]:[border-color:#f0e3c8]" : ""}`}><span />{weatherStatus === "loading" ? "Updating" : weatherStatus === "error" ? "Unavailable" : weatherStatus === "partial" ? "Incomplete" : weatherEdited ? "Edited" : "Auto-filled"}</span></div>
                  <div className="flex flex-wrap items-center justify-between gap-[12px] p-[13px_15px] bg-[#f7faf8] [border:1px_solid_#e6ede8] rounded-[10px] [&_strong]:block [&_strong]:text-[12px] [&_strong]:font-[650] [&_span]:block [&_span]:mt-[4px] [&_span]:text-[10px] [&_span]:text-[#64766e] max-[560.01px]:items-start">
                    <div className="flex items-center gap-[9px] [&_>_svg]:w-[18px] [&_>_svg]:h-[18px] [&_>_svg]:text-[#5d8a73]"><PlanningIcon type="location" /><div><strong>{location} area</strong><span><time dateTime={today}>{todayLabel}</time> · Sri Lanka time</span></div></div>
                    <button type="button" className="inline-flex items-center justify-center gap-[6px] [border:1px_solid_#d7e3da] rounded-[7px] bg-[white] p-[8px_10px] [font:inherit] text-[10px] font-[650] text-[#37694f] cursor-pointer [&_svg]:w-[13px] [&_svg]:h-[13px] [&:hover:not(:disabled)]:bg-[#edf7f1] [&:disabled]:opacity-[.6] [&:disabled]:cursor-wait max-[560.01px]:min-h-[36px]" disabled={weatherStatus === "loading"} onClick={() => setWeatherRefresh((value) => value + 1)}><PlanningIcon type="refresh" />{weatherStatus === "loading" ? "Loading…" : "Refresh weather"}</button>
                  </div>
                  <p className={`m-[12px_0_16px] text-[11px] leading-[1.7] text-[#447257] ${weatherStatus === "error" ? "[&]:text-[#956222]" : ""}`} role="status">
                    {weatherStatus === "loading" ? "Getting today’s climate conditions…" : weatherStatus === "error" ? weatherError : weatherStatus === "partial" ? "Some weather values are unavailable. Please fill in the empty fields." : "Today’s weather loaded automatically."}
                    {weatherEdited && " Values manually edited."}
                  </p>
                  <div className="grid grid-cols-[repeat(5,_minmax(0,_1fr))] gap-[9px] max-[1120.01px]:grid-cols-[repeat(3,_minmax(0,_1fr))] max-[800.01px]:grid-cols-[repeat(5,_minmax(0,_1fr))] max-[560.01px]:grid-cols-[repeat(2,_minmax(0,_1fr))] max-[560.01px]:gap-[10px]">
                    {[["Temperature", "Temperature", "°C", "temperature"], ["Rainfall", "Rainfall_mm", "mm/day", "water"], ["Humidity", "Humidity", "%", "water"], ["Wind speed", "Wind_Speed", "m/s", "wind"], ["Solar radiation", "Solar_Radiation", "W/m²", "weather"]].map(([label, key, unit, icon]) => (
                      <label className="flex flex-col min-w-[0] p-[12px_10px_11px] [border:1px_solid_#e0e9e3] bg-[#fcfdfc] rounded-[10px] [transition:box-shadow_.2s,_border-color_.2s] [&:focus-within]:[border-color:#087653] [&:focus-within]:[box-shadow:0_0_0_3px_#08765312] [&_input]:w-[100%] [&_input]:min-w-[0] [&_input]:[border:0] [&_input]:[border-bottom:1px_solid_#d8e5dc] [&_input]:rounded-[0] [&_input]:bg-[transparent] [&_input]:p-[7px_0_4px] [&_input]:[font-family:inherit] [&_input]:text-[22px] [&_input]:leading-[1.3] [&_input]:tracking-[-.6px] [&_input]:font-[650] [&_input]:text-[#244b37] [&_input]:tabular-nums [&_input:focus]:[outline:none] [&_input:focus]:[border-color:#087653] [&_input:disabled]:opacity-[.5] [&_input:disabled]:cursor-wait max-[1120.01px]:[&_input]:text-[21px] max-[560.01px]:p-[13px]" key={key}><span className="flex flex-col items-start gap-[9px] text-[#5c7265] text-[10px] font-[550] whitespace-nowrap [&_svg]:w-[17px] [&_svg]:h-[17px] [&_svg]:text-[#6e927e] max-[1120.01px]:flex-row max-[1120.01px]:items-center max-[1120.01px]:gap-[5px] max-[800.01px]:flex-col max-[800.01px]:items-start max-[800.01px]:gap-[9px] max-[560.01px]:flex-row max-[560.01px]:items-center max-[560.01px]:gap-[8px] max-[560.01px]:text-[11px]"><PlanningIcon type={icon} />{label}</span><input aria-label={`${label} (${unit})`} type="number" step="any" min={key === "Temperature" ? undefined : 0} max={key === "Humidity" ? 100 : undefined} value={climate[key]} disabled={weatherStatus === "loading"} placeholder={weatherStatus === "loading" ? "…" : "—"} onChange={(e) => { setClimate((previous) => ({ ...previous, [key]: e.target.value === "" ? "" : Number(e.target.value) })); setWeatherEdited(true); setYieldResult(null); }} required /><span className="mt-[6px] text-[10px] text-[#6c8173]">{unit}</span></label>
                    ))}
                  </div>
                  <p className="hp-weather-note m-[15px_0_0] text-[10px] leading-[1.8] text-[#64766e] [&_a]:text-[#285d43] [&_a]:underline [&_a]:[text-underline-offset:2px]">Source: <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a>. Temperature, humidity and wind use current conditions when available. Rainfall is today’s forecast total; solar radiation is the daily average.</p>
                  {(Number(year) !== currentPeriod.year || Number(month) !== currentPeriod.month || Number(week) !== currentPeriod.week) && <p className="hp-weather-note m-[15px_0_0] text-[10px] leading-[1.8] text-[#64766e] [&_a]:text-[#285d43] [&_a]:underline [&_a]:[text-underline-offset:2px] [&]:text-[#956222]">Your harvest period differs from today. These values describe today; adjust them to represent your selected harvest period before predicting.</p>}
                </section>
              </div>
            </div>
          </fieldset>
          <div className="flex items-center justify-between gap-[20px] p-[18px_22px] mt-[22px] bg-[white] [border:1px_solid_#e0e8e3] rounded-[14px] [box-shadow:0_3px_12px_#183b2c03] max-[800.01px]:items-stretch max-[800.01px]:flex-col max-[800.01px]:gap-[16px] max-[560.01px]:p-[17px]">
            <div className="flex items-center gap-[12px] min-w-[0] [&_strong]:text-[12px] [&_strong]:font-[650] [&_p]:text-[#64766e] [&_p]:text-[10px] [&_p]:leading-[1.7] [&_p]:m-[3px_0_0] max-[1120.01px]:[&_strong]:text-[11px]"><span className="grid place-items-center shrink-0 w-[38px] h-[38px] bg-[#f0f6f2] rounded-[10px] text-[#437b5e] [&_svg]:w-[18px] [&_svg]:h-[18px] max-[1120.01px]:hidden max-[800.01px]:grid"><PlanningIcon type={photos.length ? "check" : "upload"} /></span><div><strong>{photos.length ? `${photos.length} ${photos.length === 1 ? "photo" : "photos"} selected for analysis` : "Start with your crop photos"}</strong><p>{photos.length ? `${location} · ${MONTHS[Number(month) - 1]} ${year} · Week ${week}` : "Add at least one photo, then review your field details."}</p></div></div>
            <div className="flex items-stretch justify-end flex-wrap gap-[10px] shrink-0 max-[800.01px]:[&_>_button]:[flex:1_1_180px] max-[560.01px]:gap-[8px] max-[560.01px]:[&_>_button]:[flex-basis:140px] max-[560.01px]:[&_>_button]:px-[10px] max-[560.01px]:[&_>_button]:text-[11px]">
              {photos.length > 0 && <button type="button" className="inline-flex items-center justify-center min-h-[46px] rounded-[9px] [font:inherit] text-[12px] font-[650] cursor-pointer [transition:background_.2s,_box-shadow_.2s] gap-[6px] m-[0] p-[12px_14px] [border:1px_solid_#dde5df] bg-[white] text-[#586a60] [&_svg]:w-[15px] [&_svg]:h-[15px] [&:hover:not(:disabled)]:bg-[#fff5ef] [&:hover:not(:disabled)]:text-[#984b32] [&:hover:not(:disabled)]:[border-color:#dfc9bf] [&:disabled]:cursor-wait [&:disabled]:opacity-[.6]" onClick={clearAllPhotos} disabled={loading}><PlanningIcon type="close" /> Clear all photos</button>}
              <button className="inline-flex items-center justify-center min-h-[46px] rounded-[9px] [font:inherit] text-[12px] font-[650] cursor-pointer [transition:background_.2s,_box-shadow_.2s] gap-[18px] [border:1px_solid_#087653] p-[12px_22px] bg-[#087653] text-[white] [box-shadow:0_3px_8px_#08765318] [&_svg]:w-[17px] [&_svg]:h-[17px] [&:hover:not(:disabled)]:bg-[#075a40] [&:hover:not(:disabled)]:[box-shadow:0_4px_12px_#08765325] [&:disabled]:cursor-wait [&:disabled]:opacity-[.6] max-[560.01px]:gap-[8px]" type="submit" disabled={loading || validatingPhotos || !!photoError || !photos.length || weatherStatus === "loading"}>{validatingPhotos ? <><span className="hp-spinner inline-block w-[18px] h-[18px] [border:2px_solid_currentColor] [border-right-color:transparent] rounded-[50%] animate-spin [animation-duration:0.8s]" /> Checking tea photos…</> : loading ? <><span className="hp-spinner inline-block w-[18px] h-[18px] [border:2px_solid_currentColor] [border-right-color:transparent] rounded-[50%] animate-spin [animation-duration:0.8s]" /> {progressLabel}</> : <>Analyse & Predict <PlanningIcon type="arrow" /></>}</button>
            </div>
          </div>
        </form>

        {error && <div className="p-[16px_20px] bg-[#fff4f0] [border:1px_solid_#f1cabe] text-[#9a3d2c] rounded-[12px] mt-[20px] text-[12px] [&_p]:m-[5px_0_0] [&_p]:[overflow-wrap:anywhere]" role="alert"><strong>Please check the following.</strong><p>{error}</p></div>}

        <section className="pt-[6px]" aria-labelledby="hp-results-title" aria-busy={loading}>
          <div className="flex justify-between items-end gap-[20px] m-[32px_0_18px] [&_h2]:font-[700] [&_h2]:text-[22px] [&_h2]:leading-[1.3] [&_h2]:tracking-[-.6px] [&_h2]:m-[6px_0_0] max-[560.01px]:items-start max-[560.01px]:flex-col max-[560.01px]:gap-[10px]"><div><span className="block text-[10px] font-[750] tracking-[2px] text-[#087653]">FIELD INSIGHTS</span><h2 id="hp-results-title">Your harvest outlook</h2></div>{readiness.length > 0 && completedPhotos === photos.length && !loading && !error && (!canPredictYield || yieldResult) && <span className="inline-flex gap-[5px] items-center text-[11px] text-[#377552] [&_svg]:w-[15px] [&_svg]:h-[15px]"><PlanningIcon type="check" /> {allPhotosSucceeded ? "Analysis complete" : "Completed with photo errors"}</span>}</div>
          <div aria-live="polite">
            {!readiness.length && !yieldResult ? <div className="[border:1px_solid_#e0e8e3] rounded-[14px] flex items-center gap-[18px] p-[28px] bg-[white] [&_h3]:font-[650] [&_h3]:text-[14px] [&_h3]:m-[0_0_6px] [&_p]:text-[12px] [&_p]:leading-[1.7] [&_p]:text-[#64766e] [&_p]:m-[0] max-[560.01px]:p-[22px] max-[560.01px]:items-start"><span className={`w-[48px] h-[48px] rounded-[13px] grid place-items-center shrink-0 bg-[#f0f6f2] text-[#7a9b87] [border:1px_solid_#e0eae3] ${loading ? "animate-planning-pulse" : ""}`}><PlanningIcon type="chart" /></span><div><h3>{loading ? "Taking a closer look at your field" : "Your next harvest starts here"}</h3><p>{loading ? progressLabel : "Add up to 10 photos and your field details, then analyse to see your harvest insights."}</p></div></div> : <div className={`grid grid-cols-[repeat(2,_minmax(0,_1fr))] gap-[22px] items-stretch max-[800.01px]:grid-cols-[1fr] max-[800.01px]:gap-[16px] ${!photosStillProcessing && !canPredictYield ? "[&]:grid-cols-[1fr]" : ""}`}>
              {readiness.length > 0 && <article className={`min-w-[0] rounded-[16px] p-[28px] [border:1px_solid_#e0e8e3] bg-[white] [&_h3]:text-[32px] [&_h3]:font-[750] [&_h3]:tracking-[-.9px] [&_h3]:leading-[1.2] [&_h3]:m-[24px_0_12px] [&_h3]:[overflow-wrap:anywhere] [&_.hp-readiness-title]:text-[20px] [&_.hp-readiness-title]:tracking-[-.4px] [&_.hp-readiness-title]:mb-[15px] max-[560.01px]:p-[23px] ${photosStillProcessing ? "" : readinessSummary.readyPercent === null ? "[&]:bg-[#fff4f0] [&]:[border-color:#f1cabe]" : readinessSummary.readyPercent > 50 ? "[&]:bg-[#f3faf5] [&]:[border-color:#d5e8da]" : "[&]:bg-[#fffbf1] [&]:[border-color:#ebdfc2] [&&_.hp-readiness-score_>_strong]:text-[#967023] [&&_.hp-confidence::-webkit-progress-value]:bg-[#b38a3f] [&&_.hp-confidence::-moz-progress-bar]:bg-[#b38a3f]"}`}>
                <div className="flex flex-wrap items-center justify-between gap-[12px] [&_>_span:first-child]:flex [&_>_span:first-child]:gap-[8px] [&_>_span:first-child]:items-center [&_>_span:first-child]:text-[12px] [&_>_span:first-child]:font-[650] [&_svg]:w-[18px] [&_svg]:h-[18px]"><span><PlanningIcon /> Overall harvest readiness</span><span className="hp-result-tag text-[9px] tracking-[1px] font-[650] text-[#65816d]">{photosStillProcessing ? "ANALYSING" : readinessSummary.failedCount ? "PARTIAL RESULT" : "ALL PHOTOS"}</span></div>
                {photosStillProcessing ? <div className="flex items-center gap-[12px] mt-[22px] text-[12px] leading-[1.7] [&_.hp-spinner]:shrink-0"><span className="hp-spinner inline-block w-[18px] h-[18px] [border:2px_solid_currentColor] [border-right-color:transparent] rounded-[50%] animate-spin [animation-duration:0.8s]" /><p>{completedPhotos} / {photos.length} photos checked. Calculating the overall average…</p></div> : <>
                  <h3 className="hp-readiness-title">{readinessSummary.label}</h3>
                  {readinessSummary.readyPercent !== null && <>
                    <div className="hp-readiness-score flex items-center gap-[18px] mb-[18px] [&_>_strong]:text-[44px] [&_>_strong]:font-[700] [&_>_strong]:leading-[1.1] [&_>_strong]:tracking-[-1.5px] [&_>_strong]:text-[#227247] [&_>_strong]:tabular-nums [&_>_strong_>_span]:text-[23px] [&_>_strong_>_span]:ml-[3px] [&_>_strong_>_span]:font-[500] [&_>_span]:text-[11px] [&_>_span]:leading-[1.6] [&_>_span]:text-[#5a7865]"><strong>{readinessSummary.readyPercent.toFixed(1)}<span>%</span></strong><span>Average harvest-ready<br />probability</span></div>
                    <progress className="hp-confidence block appearance-none [border:0] w-[100%] h-[6px] overflow-hidden rounded-[10px] bg-[#e0ebe2] text-[#42875e] [&::-webkit-progress-bar]:bg-[#e0ebe2] [&::-webkit-progress-bar]:rounded-[10px] [&::-webkit-progress-value]:bg-[#42875e] [&::-webkit-progress-value]:rounded-[10px] [&::-moz-progress-bar]:bg-[#42875e] [&::-moz-progress-bar]:rounded-[10px]" aria-label="Average harvest-ready probability across analysed photos" max="100" value={readinessSummary.readyPercent} />
                    <p className="hp-weather-note m-[15px_0_0] text-[10px] leading-[1.8] text-[#64766e] [&_a]:text-[#285d43] [&_a]:underline [&_a]:[text-underline-offset:2px]">Average of {successfulPhotos} {successfulPhotos === 1 ? "photo" : "photos"}, with each photo weighted equally.</p>
                  </>}
                  <p className="hp-weather-note m-[15px_0_0] text-[10px] leading-[1.8] text-[#64766e] [&_a]:text-[#285d43] [&_a]:underline [&_a]:[text-underline-offset:2px]">{successfulPhotos} / {photos.length} photos analysed successfully.</p>
                  {readinessSummary.failedCount > 0 && <p className="m-[0] text-[#9a3d2c] text-[12px] leading-[1.7] [overflow-wrap:anywhere] [&]:mt-[12px]">{readinessSummary.failedCount} {readinessSummary.failedCount === 1 ? "photo could" : "photos could"} not be analysed. {successfulPhotos ? "This average includes only successful photos. " : ""}Please retry to include all photos.</p>}
                </>}
              </article>}
              {canPredictYield && yieldResult ? <article className="min-w-[0] rounded-[16px] p-[28px] [border:1px_solid_#e0e8e3] bg-[white] [&_h3]:text-[32px] [&_h3]:font-[750] [&_h3]:tracking-[-.9px] [&_h3]:leading-[1.2] [&_h3]:m-[24px_0_12px] [&_h3]:[overflow-wrap:anywhere] [&_.hp-readiness-title]:text-[20px] [&_.hp-readiness-title]:tracking-[-.4px] [&_.hp-readiness-title]:mb-[15px] max-[560.01px]:p-[23px] [&]:bg-[#154c3b] [&]:[border-color:#154c3b] [&]:text-[white] [&&_.hp-result-tag]:text-[#b5d6b1] [&&_h3]:text-[46px] [&&_h3]:text-[#d3ecb9] [&&_h3]:tabular-nums [&&_h3_>_span]:text-[16px] [&&_h3_>_span]:font-[500] [&&_h3_>_span]:tracking-[0] [&&_h3_>_span]:ml-[10px] [&&_h3_>_span]:text-[#d0dfc7] [&&_.hp-result-description]:text-[#bdd1c5] max-[560.01px]:[&&_h3]:text-[40px]"><div className="flex flex-wrap items-center justify-between gap-[12px] [&_>_span:first-child]:flex [&_>_span:first-child]:gap-[8px] [&_>_span:first-child]:items-center [&_>_span:first-child]:text-[12px] [&_>_span:first-child]:font-[650] [&_svg]:w-[18px] [&_svg]:h-[18px]"><span><PlanningIcon type="chart" /> Expected yield</span><span className="hp-result-tag text-[9px] tracking-[1px] font-[650] text-[#65816d]">YIELD ESTIMATE</span></div><h3>{Number(yieldResult.predicted_kg_per_Acre).toLocaleString(undefined, { maximumFractionDigits: 2 })}<span>kg / acre</span></h3><p className="inline-block m-[0_0_16px] p-[7px_10px] [border:1px_solid_#d0edb530] rounded-[7px] bg-[#ffffff08] text-[#d3e3d7] text-[11px] leading-[1.5] [&_strong]:text-[#d0edb5] [&_strong]:font-[650]">Planning margin: <strong>±7 kg / acre</strong></p><p className="hp-result-description m-[0_0_22px] text-[11px] leading-[1.7]">One field estimate for your selected harvest period</p><div className="flex flex-wrap items-center gap-[10px_20px] [border-top:1px_solid_#ffffff25] pt-[17px] text-[11px] text-[#d3e3d7] [&_>_span:first-child]:flex [&_>_span:first-child]:items-center [&_>_span:first-child]:gap-[5px] [&_svg]:w-[15px] [&_svg]:h-[15px]"><span><PlanningIcon type="location" />{yieldResult.location}</span><span>{MONTHS[Number(yieldResult.month) - 1]} {yieldResult.year} · Week {yieldResult.week}</span></div></article> : loading && !photosStillProcessing && canPredictYield && <div className="min-w-[0] rounded-[16px] p-[28px] [border:1px_solid_#e0e8e3] bg-[white] [&_h3]:text-[32px] [&_h3]:font-[750] [&_h3]:tracking-[-.9px] [&_h3]:leading-[1.2] [&_h3]:m-[24px_0_12px] [&_h3]:[overflow-wrap:anywhere] [&_.hp-readiness-title]:text-[20px] [&_.hp-readiness-title]:tracking-[-.4px] [&_.hp-readiness-title]:mb-[15px] max-[560.01px]:p-[23px] flex items-center justify-center gap-[12px] text-[13px] text-[#52725d]"><span className="hp-spinner inline-block w-[18px] h-[18px] [border:2px_solid_currentColor] [border-right-color:transparent] rounded-[50%] animate-spin [animation-duration:0.8s]" /><p>{progressLabel}</p></div>}
            </div>}
          </div>
        </section>
        {canPredictYield && !photosStillProcessing && <HarvestForecast key={`${location}:${today}`} api={API} location={location} today={today} />}
        <footer className="flex items-center gap-[8px] text-[#768a7d] text-[10px] p-[24px_0] mt-[30px] [border-top:1px_solid_#e0e8e3] [&_svg]:w-[16px] [&_svg]:h-[16px] [&_>_span:last-child]:ml-[auto] max-[560.01px]:flex-wrap max-[560.01px]:[&_>_span:last-child]:w-[100%] max-[560.01px]:[&_>_span:last-child]:ml-[24px]"><PlanningIcon /><span>AI Smart Tea Ecosystem</span><span>Intelligent harvest planning</span></footer>
      </div>
    </main>
  );
}
