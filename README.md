## Component 01 — Disease Intelligence System
**AI-Powered Climate-Aware Tea Disease Intelligence System**  

### Overview
TeaGuard helps explore tea-leaf disease detection, historical climate and disease patterns, and short-term plantation disease forecasting. It combines a **React frontend**, **FastAPI backend**, and trained ML models to support field-officer decisions.

### Main Features
- **Disease detection:** Classifies eligible tea-leaf images as **Brown Blight, Grey Leaf, Healthy, Red Rust, or Red Spider Mite** using EfficientNet-B0.
- **Explainable AI:** **Grad-CAM++** highlights image areas influencing a prediction.
- **Climate & incidence:** Displays historical rainfall, temperature, humidity and disease context. Observed incidence (%) = symptomatic bushes / inspected bushes × 100.
- **7-day forecasting:** Estimates **disease activity, incidence and new onset** for **16 conceptual estate blocks**, separately for days 1–7.
- **Field observations:** Officers enter block, disease and inspected/symptomatic bush counts to **preview** or **save** a recalculated forecast.
- **Alerts & guidance:** Historical/demo risk indicators and rule-based disease-management suggestions.
- **Interface:** Seven pages—Dashboard, Disease Detection, Climate & Severity, Field Observations, Spread Forecast, Alerts & Risk, and Recommendations—with English, Sinhala and Tamil UI resources.

### Data, Models & Results
| Area | Implementation |
|---|---|
| Image classification | **5 classes**, **5,767 development images** (4,041 train / 863 validation / 863 test). **White Spot is not included.** |
| Selected CNN | Fine-tuned **EfficientNet-B0**; **98.38% development-test accuracy**, **0.9842 macro F1**. |
| Climate data | Historical **NASA POWER** daily data (2011-01-01 to 2026-08-09). |
| Spread forecasting | **4 disease categories**, **16 blocks**, **7 days**; uses simulated disease histories and historical climate. |
| Forecast models | Validation-selected **Random Forest, LightGBM, XGBoost and LSTM**, depending on target/day. **GCN-LSTM** was evaluated but not selected for final inference. |

For one selected disease, an officer-assisted forecast returns **16 blocks × 7 days = 112 predictions**. The submitted inspection is current input; other block/climate information comes from **historical seasonal context**, not live weather.

### Project Files
```text
backend/app/components/Component01/
├── api/                 # FastAPI (step45_app.py)
├── src/                 # M01 data, M02 CNN, M03 climate,
│                       # M04 forecasting, M05 explanations/alerts
├── data/                # Research and local runtime data
├── models/              # Saved trained model files
├── outputs/             # Reports and evaluation results
└── requirements.txt

frontend/src/components/Component01/
├── pages/               # Seven TeaGuard pages
├── services/api.js
└── Component01App.jsx
```

### Run Locally (Windows PowerShell)
**Requirements:** Python 3.13 (development setup), Node.js/npm, component data and saved model files. Run from the **group repository root**.

**Backend:**
```powershell
py -3.13 -m venv backend\app\components\Component01\.venv
.\backend\app\components\Component01\.venv\Scripts\Activate.ps1
pip install -r backend\app\components\Component01\requirements.txt
$env:TEA_CNN_CHECKPOINT = 'models/image/development_only/step17_step47_friend_laptop01/efficientnet_b0_finetuned_best_dev_only.pt'
python -m uvicorn step45_app:app --app-dir backend/app/components/Component01/api --host 127.0.0.1 --port 8015 --workers 1
```
**Frontend (new terminal):**
```powershell
cd frontend
npm install
npm run dev
```
Frontend: `http://localhost:5173` (typically) · API docs: `http://127.0.0.1:8015/docs` · Health: `http://127.0.0.1:8015/health`.

**Main API routes:** `POST /api/image/analyze`, `POST /api/forecast/assisted/preview`, `POST /api/forecast/assisted/recalculate`, `GET /api/forecast/assisted/latest`, `POST /api/severity/incidence`. See `/docs` for the full active API. These commands run **Component 01 locally**; do not replace the shared group's main backend entrypoint. Trained files/data must already be available in your checkout.

### Important Limitations
- This is a **research prototype**, not a field-validated diagnosis or production system. CNN accuracy above is from a **development test set**, not independent estate testing; the image upload allowlist may reject new photos.
- Forecast results are evaluated on **synthetic disease data** and use **historical climate proxies**, not live infection tracking or current weather forecasts. Historical dashboard/alert snapshots do not automatically update with each saved forecast.
- **Grad-CAM++ does not measure lesion severity**; bush-count incidence is not leaf-damage severity. Advisory outputs are **rule-based suggestions**, not automated treatment prescriptions.

*Component 01 section for the shared CeylonTea IQ README. Dataset licenses and the group repository license should be checked before public distribution.*
