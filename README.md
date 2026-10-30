## **CeylonTea IQ — AI-Powered Smart Tea Ecosystem **

An AI-enabled research platform designed to support the Sri Lankan tea industry across plantation management, tea disease intelligence, tea quality assessment, and export decision-making.

The ecosystem is organized into four research components:
#### 1. Component 01 — Climate-aware tea disease intelligence.
#### 2. Component 02 — Tea Plantation Health, Harvest and Yield Intelligence.
#### 3. Component 03 — Tea Grade, Purity, Composition and Defect Analysis.
#### 4. Component 04 — AI-Powered Tea Export Intelligence Platform.

Project note: The technical details for Components 01 and 02 below are based on the supplied component README files. Components 03 and 04 are summarized from the project scope currently available; upload their latest README files to add verified setup commands, API routes, model metrics, and exact repository paths.
  
- Technology Stack
- Data and AI Approach
- Repository Structure
- Setup and Running the Project
- Evaluation and Validation
- Limitations and Responsible Use
  
### Project Overview
CeylonTea IQ aims to bring multiple AI-supported capabilities together across the tea value chain. The four components address complementary stages:
- Plantation disease monitoring: classify tea-leaf images, examine historical climate and disease context, and explore short-term disease forecasts.
- Plantation and harvest management: assess visible plantation health, classify harvest readiness, estimate yield, examine climate stress, and support harvest planning.
- Tea quality intelligence: analyse tea grades, purity, mixed composition, and visible defects using image-analysis techniques.
- Export intelligence: provide tea auction-price and export-demand forecasts, evidence-grounded export guidance, export-readiness assessment, traceability, and growing-zone intelligence.
The ecosystem is intended to support—not replace—field inspections, agricultural expertise, laboratory testing, and professional export decisions.

### Component 01 — AI-Powered Climate-Aware Tea Disease Intelligence System

TeaGuard explores tea-leaf disease classification, historical climate and disease patterns, and short-term plantation disease forecasting. It combines a React frontend, FastAPI backend, and trained machine-learning models to support field-officer decisions.

Main Features
- Tea-leaf disease detection: EfficientNet-B0 classifies eligible images into Brown Blight, Grey Leaf, Healthy, Red Rust, or Red Spider Mite.
- Explainable AI: Grad-CAM++ highlights image areas that influenced a model prediction.
- Climate and disease context: displays historical rainfall, temperature, humidity, and disease information.
- Disease forecasting: estimates disease activity, incidence, and new onset over seven days for 16 conceptual estate blocks.
- Field observations: allows officers to enter block, disease, inspected-bush, and symptomatic-bush information to preview or save a recalculated forecast.
- Alerts and guidance: presents risk indicators and rule-based disease-management suggestions.
- Multilingual interface: includes English, Sinhala, and Tamil UI resources.
  
Models and Data
- Selected image classifier: fine-tuned EfficientNet-B0.
- Development image dataset: 5,767 images across five classes.
- Reported development-test accuracy: 98.38%; macro F1: 0.9842.
- Historical climate source: NASA POWER daily data.
- Forecasting pipelines use validation-selected Random Forest, LightGBM, XGBoost, and LSTM models depending on the target and forecast day.
- Forecasts use simulated disease histories and historical climate context; they should not be interpreted as live infection tracking.
  
Main Technology
React, FastAPI, EfficientNet-B0, PyTorch, Grad-CAM++, NASA POWER, Random Forest, LightGBM, XGBoost, and LSTM.
Component 02 — Plantation and Harvest Intelligence
AI-Powered Tea Yield and Plantation Intelligence

### Component 02 combines yield forecasting, image classification, climate assessment, and harvest planning to support tea plantation operations.

Main Features
- Expected-yield prediction: CatBoost estimates tea yield in kilograms per acre using location, time, and climate-related features.
- Yield trends: displays historical yields, 2025 test predictions, and future monthly forecasts.
- Plantation health: YOLO11 classifies submitted plantation images as healthy or low_health.
- Climate-stress assessment: examines heat, water, rainfall, humidity, wind, and solar indicators and presents recommendations.
- Harvest readiness: YOLO11 classifies images as Harvest_Ready or Harvest_Not_Ready, with confidence values.
- Intelligent harvest planning: combines images, readiness predictions, climate, yield, and three-day weather comparisons.
- Harvest-quality potential: provides preliminary Premium, Moderate, or Low potential using explicit rules.
- Plant-density estimation: estimates bush counts using land area, terrain, growing zone, and spacing.
  
Models and Data
- Yield model served by the API: CatBoost Regressor.
- Image models: Ultralytics YOLO11; local CLIP image screening supports image validation.
- Yield features include year, month, week, temperature, rainfall, humidity, wind speed, solar radiation, location, and growing type.
- Dataset described in the supplied README: 5,760 records, 12 locations, covering 2016–2025.
- Chronological split: 2016–2023 training, 2024 validation, and 2025 testing.
- Reported saved 2025 yield-test metrics: MAE 7.70 kg/acre, RMSE 10.12 kg/acre, and R² 0.8373.
- Reported harvest-readiness test metrics: 98.43% accuracy and 0.9842 macro F1 on 254 images.
- Weather data and forecasts use Open-Meteo, with the Asia/Colombo timezone.
  
Main Technology
React, Vite, Tailwind CSS, Recharts, FastAPI, Uvicorn, Pydantic, CatBoost, Ultralytics YOLO11, PyTorch, CLIP, Open-Meteo, Pillow, and Requests.
Component 02 API Routes
Method	Route	Purpose
GET	/component02/health	Plantation classifier status
POST	/component02/validate-images	Validate a batch of tea images
POST	/component02/predict	Predict plantation health from an image
GET	/component02/climate	Retrieve climate data by coordinates and date
POST	/component02/assess	Combined image and climate assessment
POST	/component02/harvest-readiness/predict	Predict harvest readiness
GET	/component02/expected-yield/health	Check yield-service availability
POST	/component02/expected-yield/predict	Predict yield from JSON features
GET	/component02/expected-yield/trends	Retrieve trends by growing type
GET	/component02/harvest-forecast	Retrieve a three-day forecast by coordinates


### Component 03 — Tea Grade and Defect Intelligence Tea Grade, Purity, Mixed Composition and Defect Analysis

Component 03 focuses on analysing tea samples to support the assessment of grade, purity, mixed composition, and visible defects. It is intended to use image-analysis and computer-vision methods to identify visual characteristics relevant to tea quality.
Intended Capabilities
- Tea-grade classification: classify tea samples into the grade categories supported by the labelled dataset.
- Purity analysis: support assessment of whether a sample appears consistent with its expected tea composition.
- Mixed-composition analysis: identify visible evidence of mixed material where the model and dataset support such distinctions.
- Defect analysis: identify visible defects or unwanted material in tea samples.
- Visual explanations: use image-interpretation methods to help users understand which image regions influenced predictions, where implemented.
Candidate Technologies
The project scope identifies YOLO11, Vision Transformers (ViT), OpenCV, and Grad-CAM as relevant technologies for this component. The final model selection, class labels, dataset size, metrics, and API details should be documented from the current implementation and its evaluation results.
Validation Considerations
Image-based outputs should be validated against reliable expert-labelled samples and, where applicable, established laboratory or industry quality assessments. A visual model should not be presented as a definitive purity or chemical-composition test unless supported by appropriate validation.


### Component 04 —AI-Powered Tea Export Intelligence Platform

Component 04 focuses on using historical tea export data, auction-market information, and supporting knowledge sources to assist export planning and market decisions.

Main Functional Areas
- Auction-price forecasting (/auction-price): forecasts tea auction prices using available historical auction data.
- Export-demand forecasting (/export-demand): uses an LSTM-based model to forecast monthly tea export volumes.
- Export advisor (/export-advisor): produces export-planning recommendations grounded in forecast metrics, monthly history, planning guides, and retrieved knowledge-base passages. LLM use requires the relevant API configuration.
- Export-readiness assessment (/export-readiness): calculates an evidence-based Export Readiness Index (ERI).
- Digital tea passport (/digital-passport): supports traceability information for a tea batch.
- Growing-zone intelligence (/zone-intelligence): calculates weighted growing-zone quality scores from defined factors.
- 
AI and Data Approach
The component scope identifies time-series forecasting methods such as ARIMA, LSTM, XGBoost, CatBoost, and Temporal Fusion Transformer (TFT) as relevant approaches to export and auction intelligence. Retrieval-Augmented Generation (RAG) with a large language model (LLM) supports evidence-grounded export advice.

The final model, features, evaluation results, data sources, and availability of each function should be verified against the latest implementation. Forecasts and recommendations should clearly distinguish observed data, model estimates, and retrieved guidance.

### User Roles
The project scope identifies roles including Admin, Export Manager, Quality & Compliance Officer, Data Analyst, Farmer / Seller, and Viewer / Buyer. Exact permissions should be checked against the current application configuration.

### Technology Stack

Frontend	React, Vite, Tailwind CSS, Recharts
Backend/API	FastAPI, Uvicorn, Pydantic
Computer Vision	EfficientNet-B0, Ultralytics YOLO11, PyTorch, CLIP
Explainability	Grad-CAM++ / Grad-CAM, where implemented
Machine Learning	CatBoost, Random Forest, LightGBM, XGBoost, LSTM
Climate and Weather	NASA POWER, Open-Meteo
Export Intelligence	ARIMA, LSTM, XGBoost, CatBoost, TFT, RAG + LLM (according to component scope)
Image Processing	Pillow, OpenCV (where used)
The technology list is a cross-component overview; not every technology is used by every component.

### Data and AI Approach

The ecosystem uses different types of data depending on the component:
- Tea-leaf and tea-bush images.
- Plantation and growing-zone information.
- Historical disease observations and climate records.
- Weather forecasts and historical weather data.
- Historical yield and harvest records.
- Tea-grade, purity, composition, and defect labels.
- Tea auction prices and export-volume records.
- Export-planning documents and knowledge-base content.
Data should be checked for missing values, duplicates, inconsistent units, incorrect labels, and possible leakage between training and test sets. Time-dependent tasks should use chronological splits. Image-based tasks should use carefully separated training, validation, and test data.

### Repository Structure
The following is an illustrative high-level structure based on the supplied component files. The exact shared repository may differ.

```text
CeylonTea-IQ/
├── frontend/
│   └── src/
│       └── pages/
│           ├── component01/      # TeaGuard – disease intelligence UI
│           ├── component02/      # Plantation, harvest and yield UI
│           ├── component03/      # Tea grade, purity and defect UI
│           └── component04/      # Tea export intelligence UI
├── backend/
│   ├── app/
│   │   └── components/
│   │       ├── Component01/      # TeaGuard API, models and forecasting
│   │       ├── Component02/      # Plantation, harvest and yield API
│   │       ├── Component03/      # Tea grade and defect analysis API
│   │       └── Component04/      # Export, auction and RAG advisor API
│   ├── ml/                       # Shared machine-learning code
│   └── DL/                       # Shared deep-learning code
├── README.md
└── ...
```

Add the confirmed folder names for Components 03 and 04 from the shared repository before treating this example as the exact project structure.
Setup and Running the Project

General Requirements
- Python and pip versions compatible with the selected component requirements.
- Node.js and npm.
- The repository's required dependencies.
- The trained model files and datasets required by the selected component.
- Environment variables configured according to the relevant .env.example file, where provided.

### Run from the shared repository root:
### Run Backend

```powershell
cd backend
.\.venv\Scripts\python.exe run.py
```

### Run Dashboard

```powershell
cd frontend
npm install
npm run dev
Open the local URL printed by Vite, typically http://localhost:5173.

Record the exact datasets, climate APIs, auction/export data sources, research papers, and knowledge-base documents used by each component. Confirm licensing and attribution requirements before publishing or redistributing data.

#### Project Status
CeylonTea IQ is a multi-component research ecosystem. Model results, implementation status, and validation quality differ between components. Refer to each component's latest documentation and evaluation outputs for the current status.
