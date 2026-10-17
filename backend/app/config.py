from pathlib import Path
import os

# Base paths
APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

# Default model path to the trained YOLO11 classification model
DEFAULT_MODEL_PATH = Path(r"D:\Aththama research eka\Tea_Project\runs\classify\tea_grade_yolo11-2\weights\best.pt")

# Candidate model paths to inspect in priority order
CANDIDATE_MODEL_PATHS = [
    # 1. Custom path set by environment variable
    Path(os.getenv("TEA_MODEL_PATH", "")) if os.getenv("TEA_MODEL_PATH") else None,
    # 2. User's trained model path from evaluate_test.py
    DEFAULT_MODEL_PATH,
    # 3. Model file located in project backend/models/
    BACKEND_DIR / "models" / "best.pt",
    # 4. Project-level runs directory
    PROJECT_ROOT / "runs" / "classify" / "tea_grade_yolo11-2" / "weights" / "best.pt",
    PROJECT_ROOT / "runs" / "classify" / "weights" / "best.pt",
    # 5. Nearby Tea_Project directory alternatives
    Path(r"D:\Aththama research eka\Tea_Project\weights\best.pt"),
    Path(r"D:\Aththama research eka\Tea_Project\runs\classify\weights\best.pt"),
]

# Clean up candidates list
CANDIDATE_MODEL_PATHS = [p for p in CANDIDATE_MODEL_PATHS if p is not None]

# Allowed file extensions for leaf images
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
MAX_FILE_SIZE_MB = 15

# Known tea grades and descriptions
TEA_GRADES_INFO = {
    "BOP": {
        "name": "Broken Orange Pekoe",
        "description": "Standard medium-sized broken leaf particles, popular for brisk and strong liquor.",
        "category": "Broken Leaf",
    },
    "BOP_1A": {
        "name": "Broken Orange Pekoe 1A",
        "description": "Bold, well-cut particles without tips, renowned for balanced strength and appearance.",
        "category": "Broken Leaf",
    },
    "BP": {
        "name": "Broken Pekoe",
        "description": "Chunky and bold leaf fragments offering substantial body and deep amber color.",
        "category": "Broken Leaf",
    },
    "DUST": {
        "name": "Tea Dust",
        "description": "Smallest fine particles producing instantaneous dark brew and maximum strength.",
        "category": "Dust / Off-grades",
    },
    "FBOP": {
        "name": "Flowery Broken Orange Pekoe",
        "description": "Semi-broken leaf particles containing golden tips with pleasant aromatic liquor.",
        "category": "Flowery Grade",
    },
    "FBOPF_Exsp": {
        "name": "Flowery Broken Orange Pekoe Fannings Extra Special",
        "description": "Finely textured fannings with exceptionally high content of delicate silver/golden tips.",
        "category": "Tippy Premium",
    },
    "FBOPF_sp": {
        "name": "Flowery Broken Orange Pekoe Fannings Special",
        "description": "Medium fannings containing attractive tips, producing bright and fragrant liquor.",
        "category": "Tippy Premium",
    },
    "Fngs1": {
        "name": "Fannings 1",
        "description": "Uniform fine-grained leaf particles larger than dust, widely prized for rapid brewing.",
        "category": "Fannings",
    },
}

# CORS Allowed Origins
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "*",
]
