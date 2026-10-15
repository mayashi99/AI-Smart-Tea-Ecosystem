# Component01 — Officer Reporting + Seven-Day Block Spread (training data)

## Placement in your existing repository

Your group repository is `Smart Tea Eco System/`. Extract this ZIP **inside `backend/app/components/`** and merge its `Component01/` with your existing `Component01/`. Do not delete or replace existing component code.

Files are structured as:

```
backend/app/components/Component01/
├── data/
│   ├── raw/climate/nasa_power_daily.csv
│   └── synthetic/
│       ├── estate_blocks.csv
│       ├── block_adjacency.csv
│       ├── officer_disease_observations.csv
│       ├── synthetic_block_records.csv
│       ├── block_layout.json
│       └── provenance.json
├── src/m04_disease_spread/
│   ├── generate_officer_spread_data.py
│   └── validate_officer_spread_data.py
└── README_7DAY_SPREAD.md
```

## Data fields and interpretation

`officer_disease_observations.csv` simulates an officer inspecting a random sample of bushes in a block on a given date. `Inspected_Bushes` and `Symptomatic_Bushes` are simulated sampled counts. `Sample_Incidence_Pct = 100 * Symptomatic_Bushes / Inspected_Bushes`. This is not a verified whole-block infection estimate. **No leaf image filenames or real officer reports are invented.**

`synthetic_block_records.csv` contains 16 blocks for each date from 2023-01-01 to 2026-08-09. It has:
- Real NASA POWER historical `T2M`, `RH2M`, `PRECTOTCORR`, `ALLSKY_SFC_SW_DWN` from a **single geographic point**, repeated as shared climate context across the dummy blocks.
- Synthetic inspection indicators, observed counts (blank on days not inspected), latest observed incidence, days since inspection, and observed-neighbor summaries.
- `Target_Disease_Active_Day_1` through `Target_Disease_Active_Day_7` for seven distinct forecast target dates. These 0/1 labels are *simulated disease activity*, not actual observed disease or a percentage of the block infected.
- `Target_Incidence_Pct_Day_1` through `Target_Incidence_Pct_Day_7` are *synthetic underlying prevalence* labels (NOT officer-observed values); optional experimental regression targets only.
- `Target_New_Onset_By_Day_1` through `Target_New_Onset_By_Day_7` indicate simulated emergence of a new outbreak since forecast origin at blocks not infected at origin; a separate experimental target, not equivalent to active risk.
- `Split`: `train`, `validation`, `test`, `gap`, `warmup`, or `inference_only`. Train only on `train`; tune/choose on `validation`; test only on `test`. Ignore the others for supervised validation. The last 7 dates have missing future targets.

**Important leakage rule:** NO `Target_*` column, future target date, `Split`, or provenance field may be used as a model input. Current observed (reported) incidence is usable as a known-at-origin input. Randomly shuffling time-series rows across splits is prohibited. Graph adjacency is known in advance; the dummy block layout is not georeferenced.

## How to regenerate and validate (from repository root)

```powershell
python backend/app/components/Component01/src/m04_disease_spread/generate_officer_spread_data.py
python backend/app/components/Component01/src/m04_disease_spread/validate_officer_spread_data.py
```

Uses only Python standard library. No model training is included in this package: prepare RF, XGBoost, LightGBM, LSTM and GCN+LSTM scripts next, train and evaluate separately. The model needs a **per-horizon** prediction result per block for Day 1...Day 7.

## Provenance and scope

The panel-approved dummy estate/block structure is an illustrative 4-by-4 grid. **All disease histories, inspections, observed counts and future labels are synthetic**, built from an illustrative stochastic spread-and-recovery model with neighbor influence and weather pressure; the exact assumptions are in the generator. This supports pipeline testing, **not validated real-world tea disease forecasting performance**. The CSV only models *Red Rust spread*, not spread of all six image-classification labels.

The weather dataset ends 2026-08-09. December 2026 operational forecasting will need fresh weather/current field inputs or an explicitly identified synthetic future scenario; this data alone cannot supply them. The actual dynamic frontend should append real confirmed officer reports to a separate database table instead of claiming they are part of these synthetic historical observations.
