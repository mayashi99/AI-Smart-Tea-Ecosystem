from pathlib import Path
import json

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)
import pandas as pd


# --------------------------------------------------
# Paths: EfficientNet-B0 only
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"

TEST_DIR = DATA_DIR / "test"
MODEL_PATH = BASE_DIR / "models" / "efficientnet_b0_best.pth"
OUTPUT_DIR = BASE_DIR / "outputs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RESULTS_CSV = OUTPUT_DIR / "test_predictions.csv"
METRICS_JSON = OUTPUT_DIR / "test_metrics.json"
CONFUSION_CSV = OUTPUT_DIR / "confusion_matrix.csv"

IMAGE_SIZE = 224
BATCH_SIZE = 8

DEVICE = torch.device(
    "mps" if torch.backends.mps.is_available()
    else "cpu"
)

print("Device:", DEVICE)


# --------------------------------------------------
# Check files
# --------------------------------------------------
if not TEST_DIR.is_dir():
    raise FileNotFoundError(f"Test folder not found: {TEST_DIR}")

if not MODEL_PATH.is_file():
    raise FileNotFoundError(f"Model not found: {MODEL_PATH}")


# --------------------------------------------------
# Load test dataset
# --------------------------------------------------
test_transform = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    ),
])

test_dataset = datasets.ImageFolder(
    TEST_DIR,
    transform=test_transform,
)

print("Test classes:", test_dataset.classes)
print("Test images:", len(test_dataset))

loader = DataLoader(
    test_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=0,
)


# --------------------------------------------------
# Load trained EfficientNet-B0
# --------------------------------------------------
checkpoint = torch.load(
    MODEL_PATH,
    map_location="cpu",
    weights_only=True,
)

class_names = checkpoint["class_names"]

if class_names != test_dataset.classes:
    raise ValueError(
        f"Class mismatch. Model: {class_names}; "
        f"Test dataset: {test_dataset.classes}"
    )

model = models.efficientnet_b0(weights=None)

num_features = model.classifier[1].in_features
model.classifier[1] = nn.Linear(
    num_features,
    len(class_names),
)

model.load_state_dict(checkpoint["model_state_dict"])
model = model.to(DEVICE)
model.eval()


# --------------------------------------------------
# Predict test images
# --------------------------------------------------
y_true = []
y_pred = []
prediction_rows = []

with torch.no_grad():
    for images, labels in loader:
        images = images.to(DEVICE)

        outputs = model(images)
        predictions = outputs.argmax(dim=1).cpu().tolist()

        y_true.extend(labels.tolist())
        y_pred.extend(predictions)

        start = len(prediction_rows)
        for offset, (actual, predicted) in enumerate(
            zip(labels.tolist(), predictions)
        ):
            image_path, _ = test_dataset.samples[start + offset]

            prediction_rows.append({
                "image": str(Path(image_path).relative_to(TEST_DIR)),
                "actual_class": class_names[actual],
                "predicted_class": class_names[predicted],
                "correct": actual == predicted,
            })


# --------------------------------------------------
# Calculate metrics
# --------------------------------------------------
accuracy = accuracy_score(y_true, y_pred)

precision = precision_score(
    y_true, y_pred, average="macro", zero_division=0
)

recall = recall_score(
    y_true, y_pred, average="macro", zero_division=0
)

f1 = f1_score(
    y_true, y_pred, average="macro", zero_division=0
)

cm = confusion_matrix(
    y_true,
    y_pred,
    labels=list(range(len(class_names))),
)

report = classification_report(
    y_true,
    y_pred,
    labels=list(range(len(class_names))),
    target_names=class_names,
    output_dict=True,
    zero_division=0,
)

metrics = {
    "model": "EfficientNet-B0",
    "test_images": len(test_dataset),
    "classes": class_names,
    "accuracy": round(float(accuracy), 4),
    "macro_precision": round(float(precision), 4),
    "macro_recall": round(float(recall), 4),
    "macro_f1_score": round(float(f1), 4),
    "best_validation_accuracy": checkpoint.get(
        "best_val_accuracy"
    ),
    "classification_report": report,
}

# Save separate EfficientNet outputs only
pd.DataFrame(prediction_rows).to_csv(
    RESULTS_CSV, index=False
)

pd.DataFrame(
    cm,
    index=class_names,
    columns=class_names,
).to_csv(CONFUSION_CSV)

with open(METRICS_JSON, "w", encoding="utf-8") as file:
    json.dump(metrics, file, indent=4)


# --------------------------------------------------
# Display results
# --------------------------------------------------
print("\n===== EfficientNet-B0 Test Results =====")
print(f"Accuracy:  {accuracy:.4f} ({accuracy * 100:.2f}%)")
print(f"Precision: {precision:.4f}")
print(f"Recall:    {recall:.4f}")
print(f"F1-score:  {f1:.4f}")

print("\nClassification report:")
print(classification_report(
    y_true,
    y_pred,
    labels=list(range(len(class_names))),
    target_names=class_names,
    zero_division=0,
))

print("Confusion matrix:")
print(cm)

print("\nResults saved:")
print(RESULTS_CSV)
print(CONFUSION_CSV)
print(METRICS_JSON)