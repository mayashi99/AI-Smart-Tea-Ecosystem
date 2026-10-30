# AI Smart Tea Ecosystem — Component 03

AI-powered tea grade, composition, purity, defect, and quality analysis
for the Sri Lankan tea industry.

Component 03 focuses on image-based tea sample analysis to support
preliminary quality assessment and research workflows. Results are
decision-support signals and should not be treated as official grading,
laboratory purity measurements, or export certification.

## What this component includes

| Area | Intended capability | Implementation notes |
|---|---|---|
| Tea grade classification | Predict the grade represented in a tea sample image | YOLO11 image-classification workflow; trained model weights must be available |
| Mixed tea grade identification | Identify the two grades present in a mixed sample | Requires a dedicated mixed-tea dataset and a multi-label or composition-aware approach |
| Mixed composition estimation | Estimate the proportion of each grade in a mixed sample | Requires known mixing ratios or suitable reference labels |
| Purity analysis | Estimate the proportion of tea versus non-tea material | Requires representative labelled examples and validation |
| Defect / foreign-material analysis | Identify unwanted material in a tea sample | Object detection requires labelled bounding boxes; image classification provides image-level predictions only |
| Quality assessment | Combine available outputs into a preliminary quality summary | Must distinguish model predictions from rule-based estimates |
| Explainability | Optionally explain image-classification predictions | Grad-CAM/Grad-CAM++ is not part of the strict whole-image YOLO11 inference flow unless separately implemented |

## Architecture

```text
React + Vite frontend
  └── Component 03 pages
       ├── Tea Grade Classification
       ├── Mixed Tea Analysis
       ├── Purity Analysis
       ├── Defect / Foreign-Material Analysis
       └── Quality Assessment
                |
                v
Python API (FastAPI, if configured)
  └── Component 03 inference services
       ├── Image validation and preprocessing
       ├── YOLO11 classification model
       ├── Optional mixed-composition service
       ├── Optional purity and defect services
       └── Result formatting and confidence reporting

       # Component 03 — AI-Powered Tea Grade, Purity, Mixed Composition, Defect Analysis & Explainable Quality Assessment

Part of **CeylonTea IQ / AI Smart Tea Ecosystem**, supporting intelligent tea quality assessment for the Sri Lankan tea industry.

Combines deep learning-based tea grade classification, mixed-grade identification, purity analysis, foreign-material detection and explainable quality assessment.

## Features

- **Tea Grade Classification:** YOLO11 image classification identifies Sri Lankan tea grades from uploaded tea sample images.
- **Supported Tea Grades:** BOP, BOP_1A, BP, DUST, FBOP, FBOPF_Exp, FBOPF_sp and Fngs1.
- **Mixed Tea Identification:** Designed to identify multiple tea grades present within a mixed tea sample.
- **Mixed Composition Analysis:** Aims to estimate the percentage contribution of each identified tea grade.
- **Purity Analysis:** Designed to assess tea sample purity and identify unwanted materials.
- **Foreign Material Detection:** Planned object detection functionality to identify unwanted particles and foreign materials in tea samples.
- **Quality Assessment:** Combines grade classification, purity and defect analysis to generate an overall tea quality assessment.
- **Explainable AI:** Grad-CAM++ is considered for visual explanations of model predictions.

## Technology

- Frontend: React, Vite, TypeScript and Tailwind CSS.
- Backend: Python, FastAPI and Uvicorn.
- Deep Learning: Ultralytics YOLO11, PyTorch and EfficientNet-B0.
- Image Processing: OpenCV and Pillow.
- Machine Learning: Deep learning-based image classification and evaluation.
- Development: Antigravity IDE, Python virtual environment and Git/GitHub.

## Repository Layout

- `frontend/`: Component 03 user interfaces and tea quality analysis screens.
- `backend/app/components/component3/`: Component 03 backend implementation.
- `backend/app/components/component3/api.py`: Component 03 API routes.
- `backend/app/components/component3/predict.py`: Tea image preprocessing and model inference.
- `backend/app/components/component3/__init__.py`: Component package initialization.
- `backend/app/main.py`: Shared FastAPI application and Component 03 router registration.
- `backend/test_component3_validation.py`: Component 03 backend validation script.
- `backend/`: Python backend configuration and model dependencies.

## Models and Data

### 1. Tea Grade Classification — YOLO11

- Model: Ultralytics YOLO11 Classification.
- Task: Whole-image tea grade classification.
- Dataset: Class-organized Sri Lankan tea-grade images.
- Number of classes: 8.
- Supported classes:
  - `BOP`
  - `BOP_1A`
  - `BP`
  - `DUST`
  - `FBOP`
  - `FBOPF_Exp`
  - `FBOPF_sp`
  - `Fngs1`
- Model output: Predicted tea grade and classification confidence.
- Trained model artifact: `best.pt`.

### 2. EfficientNet-B0

- Model: EfficientNet-B0.
- Purpose: Deep learning-based tea image classification and experimental mixed-grade analysis.
- Normal tea-grade classification test accuracy: 97.06% (reported test result).
- Mixed-grade identification and composition percentage estimation require separate validation.

### 3. Mixed Tea Composition Analysis

- Identifies multiple tea grades within a mixed sample.
- Aims to estimate the composition percentage of individual grades.
- Requires suitable mixed-grade datasets and reliable composition ground-truth labels.
- Composition percentages are not yet validated as quantitative measurements.

### 4. Foreign Material and Defect Analysis

- Planned detection of unwanted materials in tea samples.
- YOLO11 object detection is considered for particle-level detection.
- Requires annotated images with bounding-box labels for training and evaluation.

### 5. Overall Quality Assessment

- Combines classification, purity and defect-analysis results.
- Intended to produce a comprehensive tea quality assessment.
- Final quality scoring rules require validation against expert-assessed tea samples.

## Local Setup

Requirements:
- Python
- Compatible Node.js and npm
- Trained model artifacts
- Required Python dependencies

Run the backend from the repository root:

```bash
cd backend

python -m venv venv
```

Activate the virtual environment on Windows:

```bash
venv\Scripts\activate
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Start the backend:

```bash
python run.py
```

The backend runs at:

`http://127.0.0.1:8000`

API documentation:

`http://127.0.0.1:8000/docs`

In a second terminal, start the frontend:

```bash
cd frontend

npm install

npm run dev
```

Frontend development server:

`http://localhost:5173`

Ensure that the trained `best.pt` model is available at the path configured in the Component 03 prediction module.

## API Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/component3/health` | Check Component 03 service and model status |
| GET | `/api/component3/info` | Retrieve Component 03 information |
| POST | `/api/component3/predict` | Upload a tea image and obtain a tea-grade prediction |

## User Workflow

1. Sign in to the CeylonTea IQ / AI Smart Tea Ecosystem application.
2. Navigate to the Component 03 tea quality analysis interface.
3. Upload a Sri Lankan tea sample image.
4. The backend validates and preprocesses the uploaded image.
5. YOLO11 performs whole-image tea-grade classification.
6. The system returns the predicted tea grade and confidence score.
7. Review the classification results.

Future integrated workflow:

8. Identify multiple tea grades in mixed tea samples.
9. Estimate individual grade composition percentages.
10. Detect foreign materials and unwanted particles.
11. Assess tea purity and overall quality.
12. Generate an explainable tea quality assessment report.

## Training and Verification

### YOLO11 Classification

Train the classification model using the prepared tea-grade dataset:

```bash
yolo classify train model=yolo11n-cls.pt data="PATH_TO_DATASET" epochs=50 imgsz=224 batch=8 device=cpu
```

### Model Evaluation

Evaluate the trained model using a separate test dataset:

```bash
yolo classify val model="PATH_TO_BEST_PT" data="PATH_TO_DATASET" split=test
```

### Backend Verification

Run the Component 03 validation script from the backend directory:

```bash
python test_component3_validation.py
```

### Frontend Verification

Run the production build from the frontend directory:

```bash
npm run build
```

## Current Implementation Notes

- YOLO11 classification is used for whole-image tea-grade prediction.
- The trained classification model supports eight Sri Lankan tea-grade classes.
- The reported normal tea-grade classification test accuracy is 97.06% using EfficientNet-B0.
- The API provides health, information and prediction endpoints.
- The current single-grade classification dataset contains one tea grade per image.
- Mixed tea composition analysis requires appropriately labelled mixed-grade samples.
- Accurate composition percentages require known grade proportions for training and testing.
- Foreign-material detection requires annotated object-detection datasets.
- Purity percentages and overall quality scores should not be presented as validated measurements until tested against reliable ground-truth data.
- Grad-CAM++ explainability is a proposed extension, not a confirmed current API output.
- Component 03 focuses exclusively on tea grade and quality intelligence, separate from plantation yield and harvest intelligence.

