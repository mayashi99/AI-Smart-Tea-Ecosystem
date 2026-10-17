
from pathlib import Path
import json
import csv

import matplotlib.pyplot as plt


# Keep all outputs inside harvest_readiness/evaluation
BASE_DIR = Path(__file__).resolve().parent
EVALUATION_DIR = BASE_DIR / "evaluation"

METRICS_FILE = EVALUATION_DIR / "test_metrics.json"
PREDICTIONS_FILE = EVALUATION_DIR / "test_predictions.csv"

CONFUSION_MATRIX_FILE = EVALUATION_DIR / "confusion_matrix.png"
REPORT_FILE = EVALUATION_DIR / "evaluation_report.txt"
PER_CLASS_FILE = EVALUATION_DIR / "per_class_metrics.csv"


def main():
    # Check existing evaluation results
    if not METRICS_FILE.is_file():
        raise FileNotFoundError(
            f"Metrics file not found: {METRICS_FILE}\n"
            "Run evaluate_model.py first."
        )

    if not PREDICTIONS_FILE.is_file():
        raise FileNotFoundError(
            f"Predictions file not found: {PREDICTIONS_FILE}\n"
            "Run evaluate_model.py first."
        )

    with open(METRICS_FILE, "r", encoding="utf-8") as file:
        metrics = json.load(file)

    with open(
        PREDICTIONS_FILE, "r", encoding="utf-8", newline=""
    ) as file:
        predictions = list(csv.DictReader(file))

    class_names = metrics["class_names"]
    matrix = metrics["confusion_matrix"]

    if len(class_names) != 2 or len(matrix) != 2:
        raise ValueError("Expected exactly two classes.")

    # Create confusion matrix image
    fig, ax = plt.subplots(figsize=(8, 6))
    image = ax.imshow(matrix, cmap="Blues")

    fig.colorbar(image, ax=ax)

    ax.set(
        xticks=[0, 1],
        yticks=[0, 1],
        xticklabels=class_names,
        yticklabels=class_names,
        xlabel="Predicted Class",
        ylabel="Actual Class",
        title="Harvest Readiness - Confusion Matrix",
    )

    plt.setp(
        ax.get_xticklabels(),
        rotation=15,
        ha="right",
        rotation_mode="anchor",
    )

    threshold = max(max(row) for row in matrix) / 2

    for row in range(2):
        for column in range(2):
            value = matrix[row][column]
            ax.text(
                column,
                row,
                str(value),
                ha="center",
                va="center",
                color="white" if value > threshold else "black",
                fontsize=14,
                fontweight="bold",
            )

    fig.tight_layout()
    fig.savefig(CONFUSION_MATRIX_FILE, dpi=200, bbox_inches="tight")
    plt.close(fig)

    # Save per-class metrics
    with open(
        PER_CLASS_FILE, "w", encoding="utf-8", newline=""
    ) as file:
        writer = csv.writer(file)
        writer.writerow(["Class", "Precision", "Recall", "F1-score", "Support"])

        for class_name in class_names:
            result = metrics["per_class"][class_name]
            writer.writerow([
                class_name,
                result["precision"],
                result["recall"],
                result["f1-score"],
                result["support"],
            ])

    # Build readable text report
    correct_count = sum(
        row["correct"].strip().lower() == "true"
        for row in predictions
    )
    incorrect_count = len(predictions) - correct_count

    lines = [
        "HARVEST READINESS - MODEL EVALUATION REPORT",
        "=" * 48,
        "",
        f"Model: {metrics.get('model_path', 'Not recorded')}",
        f"Test images: {metrics['test_image_count']}",
        f"Correct predictions: {correct_count}",
        f"Incorrect predictions: {incorrect_count}",
        f"Accuracy: {metrics['accuracy']:.4f} "
        f"({metrics['accuracy_percent']:.2f}%)",
        f"Macro Precision: {metrics['macro_precision']:.4f}",
        f"Macro Recall: {metrics['macro_recall']:.4f}",
        f"Macro F1-score: {metrics['macro_f1']:.4f}",
        "",
        "PER-CLASS METRICS",
        "-" * 48,
    ]

    for class_name in class_names:
        result = metrics["per_class"][class_name]
        lines.extend([
            "",
            class_name,
            f"  Precision: {result['precision']:.4f}",
            f"  Recall:    {result['recall']:.4f}",
            f"  F1-score:  {result['f1-score']:.4f}",
            f"  Support:   {result['support']}",
        ])

    lines.extend([
        "",
        "CONFUSION MATRIX",
        f"Class order: {class_names}",
        "Rows = actual class; columns = predicted class",
        str(matrix),
        "",
        "Note: Results are based on the saved test-set evaluation.",
    ])

    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\nEvaluation report generated successfully!")
    print(f"Confusion matrix : {CONFUSION_MATRIX_FILE}")
    print(f"Text report      : {REPORT_FILE}")
    print(f"Per-class metrics: {PER_CLASS_FILE}")


if __name__ == "__main__":
    main()
