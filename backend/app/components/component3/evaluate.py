"""
Component 03: YOLO11 Tea Grade Classification Evaluation Pipeline.
Evaluates model performance across test dataset classes and outputs confusion matrix,
precision, recall, and F1-score metrics.
"""

import argparse
import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

from app.config import DEFAULT_MODEL_PATH, ALLOWED_EXTENSIONS
from app.components.component3.predict import resolve_model_path

logger = logging.getLogger(__name__)


def evaluate_tea_model(
    test_dir: Path,
    model_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    imgsz: int = 224,
    batch: int = 32,
) -> Dict[str, Any]:
    """
    Evaluates a trained YOLO11 classification model against a test dataset directory.

    Args:
        test_dir: Directory containing test images grouped in class folders.
        model_path: Path to the trained YOLO11 model weights (defaults to resolved model).
        output_dir: Optional directory to save evaluation metrics reports and CSV files.
        imgsz: Inference image size.
        batch: Evaluation batch size.

    Returns:
        Dict containing top1_accuracy, class_metrics, confusion_matrix, and report text.
    """
    if YOLO is None:
        raise RuntimeError("Ultralytics package is not installed.")

    dataset = Path(test_dir).resolve()
    if not dataset.exists():
        raise FileNotFoundError(f"Test dataset directory does not exist: {dataset}")

    if model_path is None:
        model_path = resolve_model_path() or DEFAULT_MODEL_PATH
    model_path = Path(model_path).resolve()
    if not model_path.is_file():
        raise FileNotFoundError(f"Trained model weights not found at: {model_path}")

    logger.info(f"[Component 03] Evaluating model: {model_path} on {dataset}")
    model = YOLO(str(model_path))
    class_names = [model.names[i] for i in sorted(model.names)]

    # Collect images
    images = sorted(
        p for p in dataset.rglob("*") if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS
    )
    if not images:
        raise ValueError(f"No test images found in {dataset} matching extensions: {ALLOWED_EXTENSIONS}")

    actual_labels = [p.parent.name for p in images]

    # Run predictions in batches
    results = model.predict(
        source=[str(p) for p in images],
        imgsz=imgsz,
        batch=batch,
        verbose=False,
    )

    predicted_labels = [model.names[int(r.probs.top1)] for r in results]

    labels = class_names
    matrix = {a: {b: 0 for b in labels} for a in labels}

    for a, p in zip(actual_labels, predicted_labels):
        if a in matrix and p in matrix[a]:
            matrix[a][p] += 1

    correct = sum(a == p for a, p in zip(actual_labels, predicted_labels))
    total_samples = len(images)
    accuracy = correct / total_samples if total_samples else 0.0

    class_metrics = {}
    report_lines = [
        "COMPONENT 03: TEA GRADE CLASSIFICATION EVALUATION REPORT",
        "=" * 60,
        f"Model: {model_path.name}",
        f"Test Images: {total_samples}",
        f"Correct Predictions: {correct}",
        f"Incorrect Predictions: {total_samples - correct}",
        f"Top-1 Accuracy: {accuracy:.4%}",
        "",
        "CLASS-LEVEL PERFORMANCE METRICS",
        f"{'Class':15} {'Precision':>10} {'Recall':>10} {'F1-score':>10} {'Support':>10}",
        "-" * 60,
    ]

    for c in labels:
        tp = matrix[c][c]
        predicted_count = sum(matrix[a][c] for a in labels)
        support = sum(matrix[c].values())
        precision = tp / predicted_count if predicted_count else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

        class_metrics[c] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "support": support,
        }
        report_lines.append(f"{c:15} {precision:10.4f} {recall:10.4f} {f1:10.4f} {support:10}")

    report_lines += ["", "CONFUSION MATRIX (rows=Actual, columns=Predicted)", "-" * 60]
    report_lines.append("Actual\\Predicted," + ",".join(labels))
    for a in labels:
        report_lines.append(a + "," + ",".join(str(matrix[a][b]) for b in labels))

    full_report = "\n".join(report_lines)

    # Save reports if output_dir provided
    if output_dir:
        out = Path(output_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)
        (out / "tea_test_report.txt").write_text(full_report, encoding="utf-8")

        with (out / "tea_confusion_matrix.csv").open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["Actual/Predicted"] + labels)
            for a in labels:
                writer.writerow([a] + [matrix[a][b] for b in labels])

        with (out / "tea_predictions.csv").open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["image", "actual_grade", "predicted_grade", "correct"])
            for img_path, a, p in zip(images, actual_labels, predicted_labels):
                writer.writerow([str(img_path), a, p, a == p])

        logger.info(f"[Component 03] Reports and confusion matrix saved to: {out}")

    return {
        "success": True,
        "component": "Component 03: AI-Powered Tea Grade Classification",
        "total_samples": total_samples,
        "correct_predictions": correct,
        "accuracy": round(accuracy, 4),
        "accuracy_percentage": round(accuracy * 100, 2),
        "class_metrics": class_metrics,
        "confusion_matrix": matrix,
        "report": full_report,
    }


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="Evaluate YOLO11 Tea Grade Model for Component 03"
    )
    parser.add_argument(
        "--test-dir",
        type=str,
        default=r"D:\Aththama research eka\Tea_YOLO_Dataset_JPG\test",
        help="Path to test images directory",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Path to trained YOLO11 model weights (best.pt)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save evaluation reports",
    )
    args = parser.parse_args()

    results = evaluate_tea_model(
        test_dir=Path(args.test_dir),
        model_path=Path(args.model) if args.model else None,
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )
    print("\n" + results["report"])


if __name__ == "__main__":
    main()
