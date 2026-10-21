# Yield Intelligence — Component 02

This document describes the work on the `feature/yield-intelligence` branch of
the AI Smart Tea Ecosystem. It delivers Component 02: plantation-focused
decision-support tools for Sri Lankan tea growers. The tools are intended to
support field planning; they are not a replacement for agronomist inspections
or operational harvest decisions.

## What this branch includes

| Area | User-facing capability | Main implementation |
| --- | --- | --- |
| Expected yield | Estimate expected yield from plantation and climate inputs | CatBoost prediction API and comparison/training scripts for multiple models |
| Yield trends | View yield trends by grown type | `GET /component02/expected-yield/trends` and the Yield Trends page |
| Plant density | Calculate a recommended tea-bush count for land size, terrain, and zone | Client-side calculator with terrain previews |
| Plantation health | Assess tea plantation photos alongside climate conditions | FastAPI assessment service and image-content validation |
| Harvest readiness | Classify harvest readiness from a tea image | YOLOv11 API, training, leakage checks, and evaluation tools |
| Harvest quality | Combine field images and conditions into a preliminary quality assessment | Frontend rule-based assessment flow |
| Intelligent harvest planning | Compare the next three weather days and recommend the least-wet suitable option | Open-Meteo-backed FastAPI route with unit tests |
| User interface | Component 02 navigation and consistent animated tea-leaf visual treatment | React/Vite pages under `frontend/src/components/component2/` |

## Architecture

```text
React + Vite frontend (port 5173)
  └─ Component 02 pages
       ├─ Yield Prediction / Trends
       ├─ Plant Density
       ├─ Plantation Health
       ├─ Harvest Readiness
       ├─ Harvest Quality
       └─ Intelligent Harvest Planning
                │
                ▼
FastAPI backend (port 8000)
  └─ backend/app/main.py
       ├─ /component02/expected-yield/*
       ├─ /component02/assess and image validation routes
       ├─ /component02/harvest-readiness/*
       └─ /component02/harvest-forecast
```

The Vite development server proxies API calls to FastAPI. The backend permits
local development origins on `localhost` and `127.0.0.1`, including the normal
Vite fallback ports.

## Project locations

```text
backend/app/components/Component02/
├── expected_yield_prediction/     # model training, prediction, evaluation and API
├── plantation_health/             # health assessment service and ML utilities
├── harvest_readiness/YOLOv11/     # readiness API, training and evaluation
├── intelligent_harvest_planning/  # three-day weather comparison API
├── image_validation.py            # tea-image screening
└── setup_image_validation.py      # one-time local CLIP setup

frontend/src/components/component2/
├── yield prediction/
├── yield trend/
├── PlantDensity/
├── PlantHelth/
├── HarvestReadiness/
├── HarvestQuality/
└── IntelligentHarvestPlanning/
```

## Run locally

### 1. Start the backend

From the repository root:

```sh
cd backend
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

On Windows, activate the virtual environment with the equivalent
`venv\Scripts\activate` command.

### 2. Start the frontend

In a second terminal:

```sh
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite, normally `http://localhost:5173`.

### 3. Optional: enable image-content screening

Plantation Health and Harvest Quality use a local CLIP-based screen to reject
unreadable, oversized, unrelated, or uncertain image uploads. After installing
the backend dependencies, provision its weights once:

```sh
cd backend
venv/bin/python -m app.components.Component02.setup_image_validation
```

The model weights are downloaded on first setup. If the screening service is
not available, the relevant validation endpoint returns HTTP 503 instead of
accepting unverified images.

## Expected Yield API

Base path: `/component02/expected-yield`

| Method | Route | Description |
| --- | --- | --- |
| `GET` | `/health` | Confirms that the Expected Yield API is registered. |
| `POST` | `/predict` | Returns a CatBoost yield estimate in `kg/acre`. |
| `GET` | `/trends?grown_type=HIGH%20grown` | Produces historical/model-derived trend data for a grown type. |

Example request:

```json
{
  "Year": 2026,
  "Month_Number": 10,
  "Week_Number": 3,
  "Temperature": 25.4,
  "Rainfall_mm": 88.2,
  "Humidity": 79,
  "Wind_Speed": 3.1,
  "Solar_Radiation": 4.8,
  "Location": "Nuwara Eliya",
  "Grown_Type": "HIGH grown"
}
```

Example response shape:

```json
{
  "location": "Nuwara Eliya",
  "year": 2026,
  "month": 10,
  "week": 3,
  "predicted_kg_per_Acre": 0,
  "unit": "kg/acre",
  "model": "CatBoost"
}
```

`predicted_kg_per_Acre` above is only a response-shape placeholder. Actual
values depend on the model artifact and the submitted inputs.

### Yield modelling utilities

The `expected_yield_prediction` folder includes CatBoost, LightGBM, Random
Forest, Extra Trees, HistGradientBoosting, XGBoost, NGBoost, and SARIMAX
training/evaluation utilities, plus scripts for data validation, leakage
checking, comparison, feature importance, SHAP analysis, location evaluation,
and dataset splitting. Output metrics are retained in each model's `outputs/`
folder where available.

## Harvest planning API

`GET /component02/harvest-forecast?latitude=6.9271&longitude=79.8612`

The route fetches the next three days from Open-Meteo in `Asia/Colombo` time.
It rejects incomplete weather data, excludes thunderstorm days, then ranks
remaining days by rainfall, rain probability, maximum wind, and maximum
temperature. It returns the raw day values, chosen date, explanatory method,
and any cautions. It deliberately does not claim to be a calibrated agronomic
suitability model.

## Frontend pages

| Route | Page | Purpose |
| --- | --- | --- |
| `/yield-prediction` | Yield Prediction | Submit plantation and climate inputs for an expected-yield estimate. |
| `/yield-trends` | Yield Trends | Explore yield patterns by grown type. |
| `/plant-density` | Plant Density | Calculate planting density and visualize terrain choices. |
| `/plantation-health` | Plantation Health | Upload field images and review health/climate signals. |
| `/harvest-readiness` | Harvest Readiness | Check image-based readiness classification. |
| `/harvest-quality` | Harvest Quality | Get a preliminary combined quality assessment. |
| `/intelligent-harvest-planning` | Intelligent Harvest Planning | Review field signals and next-three-day harvest weather. |

These Component 02 pages use the same animated tea-leaf background system as
the traceability experience. The setting can be disabled from the application
settings; reduced-motion preferences also disable motion automatically.

## Verification

Run the frontend production build:

```sh
cd frontend
npm run build
```

Run the harvest-forecast unit tests:

```sh
cd backend
python -m unittest app.components.Component02.intelligent_harvest_planning.test_harvest_forecast
```

Before merging, also run model-specific evaluation and leakage-check scripts
when datasets or model artifacts change. Do not interpret an interface result
as a validated field recommendation without checking the input data, model
version, and local plantation conditions.

## Important limitations

- Yield, health, readiness, and quality outputs are decision-support signals,
  not guarantees of yield or product quality.
- Image screening is a preliminary zero-shot check; unrelated plants may pass
  and legitimate tea images may be rejected.
- Weather recommendations depend on an external forecast provider and can
  change after the result is returned.
- Model artifacts and local datasets must be present for model-backed API
  routes to work.
- Production deployment needs authentication, authorization, monitoring,
  dataset governance, and validation against representative field data.
