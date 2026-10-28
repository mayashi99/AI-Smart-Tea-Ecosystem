"""Canonical filesystem paths for Component 02 deep-learning pipelines."""

from pathlib import Path


DL_ROOT = Path(__file__).resolve().parents[2]
COMPONENT = "component02"

RAW_DATA_ROOT = DL_ROOT / "datasets" / "raw" / COMPONENT
PROCESSED_DATA_ROOT = DL_ROOT / "datasets" / "processed" / COMPONENT
TEST_DATA_ROOT = DL_ROOT / "datasets" / "tests" / COMPONENT
MODEL_ROOT = DL_ROOT / "models" / COMPONENT

HARVEST_RAW_DIR = RAW_DATA_ROOT / "harvest_readiness" / "original"
HARVEST_PROCESSED_DIR = PROCESSED_DATA_ROOT / "harvest_readiness"
HARVEST_TEST_DIR = TEST_DATA_ROOT / "harvest_readiness" / "test"
HARVEST_MODEL_ROOT = MODEL_ROOT / "harvest_readiness"
HARVEST_EFFICIENTNET_DIR = HARVEST_MODEL_ROOT / "efficientnet_b0"
HARVEST_EFFICIENTNET_MODEL = HARVEST_EFFICIENTNET_DIR / "efficientnet_b0_best.pth"
HARVEST_EFFICIENTNET_EVALUATION_DIR = HARVEST_EFFICIENTNET_DIR / "evaluation"
HARVEST_YOLO_DIR = HARVEST_MODEL_ROOT / "yolo11"
HARVEST_YOLO_RUNS_DIR = HARVEST_YOLO_DIR / "runs"
HARVEST_YOLO_MODEL = (
    HARVEST_YOLO_RUNS_DIR
    / "harvest_readiness_yolo11n_50epochs"
    / "weights"
    / "best.pt"
)
HARVEST_YOLO_EVALUATION_DIR = HARVEST_YOLO_DIR / "evaluation"

PLANTATION_RAW_DIR = RAW_DATA_ROOT / "plantation_health" / "original"
PLANTATION_PROCESSED_DIR = PROCESSED_DATA_ROOT / "plantation_health"
PLANTATION_TEST_DIR = TEST_DATA_ROOT / "plantation_health" / "test"
PLANTATION_MODEL_ROOT = MODEL_ROOT / "plantation_health" / "yolo11"
PLANTATION_RUNS_DIR = PLANTATION_MODEL_ROOT / "runs"
PLANTATION_BASE_MODEL = PLANTATION_MODEL_ROOT / "yolo11n-cls.pt"
PLANTATION_PRODUCTION_RUN = "plantation_health_yolo11n_updated_50epochs_v2"
PLANTATION_PRODUCTION_MODEL = (
    PLANTATION_RUNS_DIR / PLANTATION_PRODUCTION_RUN / "weights" / "best.pt"
)
