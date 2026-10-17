import { useEffect, useRef, useState } from "react";

const API_BASE_URL = (import.meta.env.VITE_API_URL || (import.meta.env.DEV ? "" : "http://127.0.0.1:8000")).replace(/\/$/, "");
const API_URL = `${API_BASE_URL}/component02/harvest-readiness/predict`;
const MAX_IMAGES = 10;
const MAX_IMAGE_SIZE = 10 * 1024 * 1024;
const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];

export default function HarvestReadiness() {
  const [images, setImages] = useState([]);
  const [results, setResults] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const previewUrls = useRef(new Set());
  const activeRequest = useRef(null);

  useEffect(() => {
    const urls = previewUrls.current;
    return () => {
      activeRequest.current?.abort();
      urls.forEach((url) => URL.revokeObjectURL(url));
      urls.clear();
    };
  }, []);

  function handleFileChange(event) {
    const selected = Array.from(event.target.files || []);
    event.target.value = "";
    if (loading || selected.length === 0) return;

    if (images.length + selected.length > MAX_IMAGES) {
      setError(`You can add up to ${MAX_IMAGES} images. ${images.length} already selected.`);
      return;
    }
    const invalid = selected.find((file) => !ALLOWED_TYPES.includes(file.type));
    if (invalid) {
      setError(`${invalid.name}: please upload JPG, PNG, or WEBP images only.`);
      return;
    }
    const oversized = selected.find((file) => file.size > MAX_IMAGE_SIZE);
    if (oversized) {
      setError(`${oversized.name}: each image must be 10 MB or less.`);
      return;
    }

    const additions = selected.map((file) => {
      const preview = URL.createObjectURL(file);
      previewUrls.current.add(preview);
      return { id: crypto.randomUUID(), file, preview };
    });
    setImages((current) => [...current, ...additions]);
    setResults([]);
    setError("");
  }

  function removeImage(id) {
    const image = images.find((item) => item.id === id);
    if (!image || loading) return;
    URL.revokeObjectURL(image.preview);
    previewUrls.current.delete(image.preview);
    setImages((current) => current.filter((item) => item.id !== id));
    setResults([]);
    setError("");
  }

  function clearImages() {
    previewUrls.current.forEach((url) => URL.revokeObjectURL(url));
    previewUrls.current.clear();
    setImages([]);
    setResults([]);
    setError("");
  }

  async function handlePredict() {
    if (loading || images.length === 0) return;
    const controller = new AbortController();
    activeRequest.current = controller;
    setLoading(true);
    setError("");
    setResults([]);

    try {
      // Use the existing single-image endpoint sequentially to avoid concurrent model runs.
      for (const image of images) {
        let outcome;
        try {
          const formData = new FormData();
          formData.append("file", image.file);
          const response = await fetch(API_URL, {
            method: "POST",
            body: formData,
            signal: controller.signal,
          });
          const data = await response.json().catch(() => null);
          if (!response.ok) {
            throw new Error(
              response.status === 404
                ? "Harvest endpoint not found. Please start the combined backend."
                : typeof data?.detail === "string"
                  ? data.detail
                  : `Prediction failed (HTTP ${response.status}). Please try again.`
            );
          }
          if (!data || typeof data.prediction !== "string" || typeof data.confidence_percent !== "number" || !Number.isFinite(data.confidence_percent)) {
            throw new Error("The API returned an incomplete harvest prediction.");
          }
          outcome = { ...image, data };
        } catch (err) {
          if (controller.signal.aborted) return;
          outcome = {
            ...image,
            error: err instanceof TypeError
              ? "Unable to connect to the Harvest Readiness API. Check that the backend is running."
              : err.message || "Prediction failed. Please try again.",
          };
        }
        if (controller.signal.aborted) return;
        setResults((current) => [...current, outcome]);
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
      if (activeRequest.current === controller) activeRequest.current = null;
    }
  }

  const successfulCount = results.filter((result) => !result.error).length;

  return (
    <main className="min-h-screen bg-stone-50 px-4 py-8 text-slate-800 sm:px-8">
      <div className="mx-auto max-w-5xl">
        <header className="mb-8 rounded-3xl bg-emerald-950 p-6 text-white sm:p-10">
          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.2em] text-emerald-300">AI Smart Tea Ecosystem</p>
          <h1 className="text-3xl font-bold sm:text-4xl">Harvest Readiness Detection</h1>
          <p className="mt-4 max-w-2xl leading-7 text-emerald-100">Upload up to 10 tea plantation images to check harvest readiness. Each image gets its own prediction and confidence score.</p>
        </header>

        <section className="grid items-start gap-6 md:grid-cols-2">
          <div className="min-w-0 rounded-3xl border border-emerald-100 bg-white p-6 shadow-sm sm:p-8">
            <h2 className="text-xl font-bold">Upload Images</h2>
            <p className="mt-2 text-sm text-slate-500">Up to 10 images · JPG, PNG or WEBP · Maximum 10 MB each</p>
            <label
              htmlFor="harvest-images"
              className={`mt-6 flex min-h-36 flex-col items-center justify-center rounded-2xl border-2 border-dashed border-emerald-300 bg-emerald-50/60 p-5 text-center ${loading || images.length >= MAX_IMAGES ? "cursor-not-allowed opacity-50" : "cursor-pointer hover:bg-emerald-50"}`}
            >
              <span className="text-3xl" aria-hidden="true">🌱</span>
              <span className="mt-3 font-semibold text-emerald-900">{images.length >= MAX_IMAGES ? "10 images selected" : images.length ? "Add more images" : "Choose plantation images"}</span>
              <span className="mt-1 text-sm text-slate-500">{images.length >= MAX_IMAGES ? "Remove an image to add another" : "Select multiple images or add them one at a time"}</span>
              <input
                id="harvest-images"
                type="file"
                multiple
                accept="image/jpeg,image/png,image/webp"
                aria-label="Add plantation images"
                disabled={loading || images.length >= MAX_IMAGES}
                onChange={handleFileChange}
                className="mt-3 block w-full text-xs file:mr-2 file:rounded-lg file:border-0 file:bg-emerald-100 file:px-3 file:py-2 file:font-semibold file:text-emerald-900"
              />
            </label>

            <p className="mt-4 text-sm font-semibold text-emerald-800" aria-live="polite">{images.length} / {MAX_IMAGES} images selected</p>
            {images.length > 0 && (
              <div className="mt-3 grid grid-cols-2 gap-3">
                {images.map((image, index) => (
                  <div key={image.id} className="min-w-0 overflow-hidden rounded-xl border border-emerald-100">
                    <img src={image.preview} alt={`Selected plantation ${index + 1}`} className="h-28 w-full object-cover" />
                    <div className="p-3">
                      <p className="text-xs font-semibold">Image {index + 1}</p>
                      <p className="mt-1 truncate text-xs text-slate-500" title={image.file.name}>{image.file.name}</p>
                      <button type="button" disabled={loading} onClick={() => removeImage(image.id)} aria-label={`Remove image ${index + 1}: ${image.file.name}`} className="mt-2 rounded-lg px-2 py-1 text-xs font-semibold text-red-700 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-400 disabled:opacity-50">Remove</button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-6 flex flex-wrap gap-3">
              <button type="button" onClick={handlePredict} disabled={images.length === 0 || loading} className="flex-1 rounded-xl bg-emerald-700 px-5 py-3 font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50">
                {loading ? `Analyzing ${Math.min(results.length + 1, images.length)} / ${images.length}...` : "Analyze Images"}
              </button>
              <button type="button" onClick={clearImages} disabled={loading || images.length === 0} className="rounded-xl border border-slate-300 px-5 py-3 font-semibold hover:bg-slate-50 disabled:opacity-50">Clear All</button>
            </div>
            {error && <p role="alert" className="mt-4 rounded-xl bg-red-50 p-4 text-sm text-red-700">{error}</p>}
          </div>

          <div className="min-w-0 rounded-3xl border border-emerald-100 bg-white p-6 shadow-sm sm:p-8" aria-live="polite" aria-busy={loading}>
            <h2 className="text-xl font-bold">Prediction Results</h2>
            {results.length === 0 && !loading && (
              <div className="mt-6 flex min-h-48 flex-col items-center justify-center rounded-2xl bg-stone-50 p-6 text-center">
                <span className="text-4xl" aria-hidden="true">🔍</span>
                <p className="mt-3 font-semibold">No predictions yet</p>
                <p className="mt-1 text-sm text-slate-500">Choose up to 10 images and click Analyze Images.</p>
              </div>
            )}
            {loading && <p role="status" className="mt-4 rounded-xl bg-emerald-50 p-4 text-sm font-semibold text-emerald-800">Analyzing images… {results.length} of {images.length} completed.</p>}
            {!loading && results.length > 0 && <p className="mt-3 text-sm text-slate-600">{successfulCount} successful · {results.length - successfulCount} failed. You can analyze again to retry.</p>}

            <div className="mt-6 space-y-4">
              {results.map((result, index) => (
                <article key={result.id} className={`rounded-2xl border p-4 ${result.error ? "border-red-200 bg-red-50" : "border-emerald-100 bg-emerald-50"}`}>
                  <div className="flex items-center gap-3">
                    <img src={result.preview} alt={`Analyzed plantation ${index + 1}`} className="h-16 w-16 shrink-0 rounded-lg object-cover" />
                    <div className="min-w-0">
                      <h3 className="font-semibold">Image {index + 1}</h3>
                      <p className="break-all text-xs text-slate-500">{result.file.name}</p>
                    </div>
                  </div>
                  {result.error ? <p className="mt-4 text-sm text-red-700">{result.error}</p> : (
                    <div className="mt-4">
                      <p className="text-xs font-medium text-emerald-800">Predicted Class</p>
                      <p className="mt-1 break-words text-xl font-bold text-emerald-950">{result.data.prediction.replaceAll("_", " ")}</p>
                      <p className="mt-3 text-sm text-slate-600">Model confidence <span className="font-bold text-emerald-800">{result.data.confidence_percent.toFixed(2)}%</span></p>
                      <div role="progressbar" aria-label={`Image ${index + 1} prediction confidence`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.max(0, Math.min(100, result.data.confidence_percent))} className="mt-2 h-2 overflow-hidden rounded-full bg-emerald-200">
                        <div className="h-full rounded-full bg-emerald-700" style={{ width: `${Math.max(0, Math.min(100, result.data.confidence_percent))}%` }} />
                      </div>
                    </div>
                  )}
                </article>
              ))}
            </div>
            {successfulCount > 0 && <p className="mt-5 text-xs leading-5 text-slate-500">Confidence is the model's prediction score, not a guarantee that the classification is correct.</p>}
          </div>
        </section>
        <footer className="py-8 text-center text-sm text-slate-500">AI Smart Tea Ecosystem · Harvest Readiness</footer>
      </div>
    </main>
  );
}
