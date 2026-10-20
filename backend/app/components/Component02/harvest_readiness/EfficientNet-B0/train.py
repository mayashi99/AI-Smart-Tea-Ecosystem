from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models
from torchvision.models import EfficientNet_B0_Weights


# --------------------------------------------------
# Paths: EfficientNet-B0 files only
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
HARVEST_DIR = BASE_DIR.parent
DATA_DIR = HARVEST_DIR / "data"

TRAIN_DIR = DATA_DIR / "train"
VAL_DIR = DATA_DIR / "val"

MODEL_DIR = BASE_DIR / "models"
OUTPUT_DIR = BASE_DIR / "outputs"

MODEL_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = MODEL_DIR / "efficientnet_b0_best.pth"

# MacBook Air M1: conservative settings
IMAGE_SIZE = 224
BATCH_SIZE = 8
EPOCHS = 10
LEARNING_RATE = 0.0001
NUM_WORKERS = 0

DEVICE = torch.device(
    "mps" if torch.backends.mps.is_available()
    else "cpu"
)

print(f"Device: {DEVICE}")
print(f"Dataset: {DATA_DIR}")


# --------------------------------------------------
# Validate dataset folders
# --------------------------------------------------
for folder in [TRAIN_DIR, VAL_DIR]:
    if not folder.is_dir():
        raise FileNotFoundError(
            f"Dataset folder not found: {folder}"
        )

# No test images are loaded during training.
# Test data is reserved for final evaluation.


# --------------------------------------------------
# Image preprocessing
# --------------------------------------------------
weights = EfficientNet_B0_Weights.DEFAULT

train_transforms = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(10),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    ),
])

eval_transforms = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    ),
])


# --------------------------------------------------
# Load existing train and validation splits
# --------------------------------------------------
train_dataset = datasets.ImageFolder(
    TRAIN_DIR,
    transform=train_transforms,
)

val_dataset = datasets.ImageFolder(
    VAL_DIR,
    transform=eval_transforms,
)

if train_dataset.classes != val_dataset.classes:
    raise ValueError(
        "Train and validation classes do not match."
    )

if len(train_dataset) == 0 or len(val_dataset) == 0:
    raise ValueError("Train or validation dataset is empty.")

print("Classes:", train_dataset.classes)
print("Training images:", len(train_dataset))
print("Validation images:", len(val_dataset))

train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True,
    num_workers=NUM_WORKERS,
)

val_loader = DataLoader(
    val_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=NUM_WORKERS,
)


# --------------------------------------------------
# Create EfficientNet-B0
# --------------------------------------------------
# Uses pretrained ImageNet weights.
# First run may need internet to download the weights.
model = models.efficientnet_b0(weights=weights)

num_features = model.classifier[1].in_features

model.classifier[1] = nn.Linear(
    num_features,
    len(train_dataset.classes),
)

# Freeze the pretrained feature extractor initially.
for param in model.features.parameters():
    param.requires_grad = False

model = model.to(DEVICE)

criterion = nn.CrossEntropyLoss()

optimizer = torch.optim.Adam(
    model.classifier.parameters(),
    lr=LEARNING_RATE,
)


# --------------------------------------------------
# Train and validate
# --------------------------------------------------
best_val_accuracy = 0.0

for epoch in range(EPOCHS):
    model.train()
    train_loss_sum = 0.0
    train_correct = 0
    train_total = 0

    for images, labels in train_loader:
        images = images.to(DEVICE)
        labels = labels.to(DEVICE)

        optimizer.zero_grad()

        outputs = model(images)
        loss = criterion(outputs, labels)

        loss.backward()
        optimizer.step()

        train_loss_sum += loss.item() * images.size(0)

        predictions = outputs.argmax(dim=1)
        train_correct += (predictions == labels).sum().item()
        train_total += labels.size(0)

    train_loss = train_loss_sum / train_total
    train_accuracy = train_correct / train_total

    model.eval()
    val_loss_sum = 0.0
    val_correct = 0
    val_total = 0

    with torch.no_grad():
        for images, labels in val_loader:
            images = images.to(DEVICE)
            labels = labels.to(DEVICE)

            outputs = model(images)
            loss = criterion(outputs, labels)

            val_loss_sum += loss.item() * images.size(0)

            predictions = outputs.argmax(dim=1)
            val_correct += (
                predictions == labels
            ).sum().item()
            val_total += labels.size(0)

    val_loss = val_loss_sum / val_total
    val_accuracy = val_correct / val_total

    print(
        f"Epoch [{epoch + 1}/{EPOCHS}] "
        f"Train Loss: {train_loss:.4f} "
        f"Train Acc: {train_accuracy:.4f} "
        f"Val Loss: {val_loss:.4f} "
        f"Val Acc: {val_accuracy:.4f}"
    )

    if val_accuracy > best_val_accuracy:
        best_val_accuracy = val_accuracy

        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "class_names": train_dataset.classes,
                "image_size": IMAGE_SIZE,
                "best_val_accuracy": best_val_accuracy,
            },
            MODEL_PATH,
        )

        print(f"Best model saved: {MODEL_PATH}")

print("\nTraining completed.")
print(f"Best validation accuracy: {best_val_accuracy:.4f}")
print(f"Model saved to: {MODEL_PATH}")