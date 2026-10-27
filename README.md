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
