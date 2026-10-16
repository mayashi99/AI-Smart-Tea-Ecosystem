# Component01 — TeaGuard Intelligence Frontend

This package is the React/Vite frontend provided by the team with the self-contained Component01 module added at `src/components/Component01/`. Other group components can mount `Component01App.jsx` under their shared router. Only `src/App.jsx`, `src/main.jsx`, `index.html`, `vite.config.js`, and README were adjusted at the application root.

## Run

1. Start Component01 FastAPI from the group repository root in its Python virtual environment:
   ```powershell
   $env:TEA_CNN_CHECKPOINT="models/image/development_only/step17_step47_friend_laptop01/efficientnet_b0_finetuned_best_dev_only.pt"
   python -m uvicorn step45_app:app --app-dir backend/app/components/Component01/api --host 127.0.0.1 --port 8015 --workers 1
   ```
2. From the group repo's `frontend` directory:
   ```powershell
   npm install
   npm run dev
   ```
3. Browse `http://localhost:5173`.

All seven screens rely on Component01 FastAPI endpoints. No fabricated model scores, historical measurements, or forecast outputs are injected by the React app. Missing backend data produces loading, empty, or error states. The API has to have Step50B installed to support advanced recommendations. Image assets load from the API and are not prepackaged.

Language selector: English / Sinhala / Tamil. Shared UI labels and navigation are translated. Detailed agronomic recommendation prose is returned by the backend in English and **must be professionally translated and reviewed** before relying on localized treatment instructions. The interface does not translate pesticide directions automatically.

### Integration details

- Modules: `src/components/Component01/{pages,ui,services,hooks,locales,styles}`
- Entry: `src/components/Component01/Component01App.jsx`
- Navigation: `#/component01/{overview,detection,climate,forecast,observations,alerts,recommendations}`
- API URL: Vite dev proxy at `:8015`; optional `VITE_COMPONENT01_API_BASE_URL`
- Save observation: explicit `POST /api/forecast/recalculate`. Preview: `POST /api/forecast/preview` (no write).
- FastAPI server single worker only. Other group UI should integrate this component without copying its internal files into shared pages.

## Scientific and operational boundaries (internal handover, not UI labels)

The underlying block estate and historic spread targets are synthetic; origin is 2025. The CNN and advisories are not field-certified. The UI deliberately avoids invented "live" data, fresh timestamps, site maps, percentages, diagnostic certainties or chemical prescriptions. The forecast heatmap colors reuse the API's *existing* high/watch-style cutoffs for presentation only, not validated agronomic action thresholds. Risk is **not a proof of literal block-to-block transmission**. Explain this clearly to panel members and do not present historical outputs as current estate measurements. Professional review and crop registration checks are required before pesticide use.
