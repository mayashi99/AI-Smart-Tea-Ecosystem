"""
Component 03: YOLO11 Tea Grade Classification Model Training Pipeline.
Allows training or fine-tuning YOLO11 whole-image classification models on Sri Lankan tea leaf datasets.
"""

import argparse
import logging
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

from app.config import PROJECT_ROOT

logger = logging.getLogger(__name__)


def train_tea_grade_model(
    data_dir: Path,
    base_model: str = "yolo11n-cls.pt",
    epochs: int = 50,
    imgsz: int = 224,
    batch: int = 32,
    project_dir: Optional[Path] = None,
    run_name: str = "tea_grade_yolo11",
    device: str = "0",
) -> Dict[str, Any]:
    """
    Trains or fine-tunes a YOLO11 whole-image classification model on the specified tea dataset.

    Args:
        data_dir: Path to the dataset root containing train/val/test folders or class folders.
        base_model: Initial model weights file or pretrained checkpoint name (e.g., 'yolo11n-cls.pt').
        epochs: Number of training epochs.
        imgsz: Image resolution (default 224 for classification).
        batch: Training batch size.
        project_dir: Directory where runs and weights will be saved.
        run_name: Subfolder name for the training run.
        device: Device to run on ('0' for GPU 0, 'cpu' for CPU).

    Returns:
        Dict containing training summary, best model weights path, and metrics.
    """
    if YOLO is None:
        raise RuntimeError(
            "Ultralytics package is not installed. Please run 'pip install ultralytics' to train YOLO11 models."
        )

    data_path = Path(data_dir).resolve()
    if not data_path.exists():
        raise FileNotFoundError(f"Training dataset directory not found: {data_path}")

    if project_dir is None:
        project_dir = PROJECT_ROOT / "runs" / "classify"
    project_dir = Path(project_dir).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"[Component 03] Initializing YOLO11 model with base weights: {base_model}")
    model = YOLO(base_model)

    logger.info(
        f"[Component 03] Starting training on {data_path} for {epochs} epochs (imgsz={imgsz}, batch={batch})..."
    )

    results = model.train(
        data=str(data_path),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        project=str(project_dir),
        name=run_name,
        device=device,
        verbose=True,
    )

    save_dir = Path(results.save_dir) if hasattr(results, "save_dir") else project_dir / run_name
    best_weights = save_dir / "weights" / "best.pt"

    return {
        "success": True,
        "component": "Component 03: AI-Powered Tea Grade Classification",
        "save_dir": str(save_dir),
        "best_weights": str(best_weights) if best_weights.is_file() else None,
        "epochs": epochs,
        "batch": batch,
        "imgsz": imgsz,
    }


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="Train YOLO11 Tea Grade Classification Model for Component 03"
    )
    parser.add_argument(
        "--data",
        type=str,
        default=r"D:\Aththama research eka\Tea_YOLO_Dataset_JPG",
        help="Path to YOLO classification dataset directory",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="yolo11n-cls.pt",
        help="Base model weights (e.g. yolo11n-cls.pt or existing checkpoint)",
    )
    parser.add_argument("--epochs", type=int, default=50, help="Number of training epochs")
    parser.add_argument("--imgsz", type=int, default=224, help="Image size")
    parser.add_argument("--batch", type=int, default=32, help="Batch size")
    parser.add_argument("--device", type=str, default="0", help="CUDA device ID or 'cpu'")
    parser.add_argument("--name", type=str, default="tea_grade_yolo11", help="Run name")

    args = parser.parse_args()
    summary = train_tea_grade_model(
        data_dir=Path(args.data),
        base_model=args.model,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        run_name=args.name,
        device=args.device,
    )
    print("\nTraining completed successfully:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
