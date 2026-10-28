"""Canonical filesystem locations for the expected-yield ML pipeline."""

from pathlib import Path


ML_ROOT = Path(__file__).resolve().parents[3]
COMPONENT = "component02"
PIPELINE = "expected_yield_prediction"

RAW_DATA_DIR = ML_ROOT / "datasets" / "raw" / COMPONENT / PIPELINE
PROCESSED_DATA_DIR = ML_ROOT / "datasets" / "processed" / COMPONENT / PIPELINE
MODEL_ROOT = ML_ROOT / "models" / COMPONENT / PIPELINE
TEST_ROOT = ML_ROOT / "tests" / COMPONENT / PIPELINE
RAW_DATA_FILE = RAW_DATA_DIR / "expected_yield.csv"


def model_dir(algorithm: str) -> Path:
    """Return the artifact directory for one expected-yield algorithm."""
    return MODEL_ROOT / algorithm


def evaluation_dir(algorithm: str) -> Path:
    """Return the evaluation-output directory for one algorithm."""
    return model_dir(algorithm) / "evaluation"
