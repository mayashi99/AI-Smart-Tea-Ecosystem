import random
import shutil
from pathlib import Path

# ============================================================
# COMPONENT 02 - PLANTATION HEALTH DATASET
# ============================================================

# Original dataset
SOURCE_DIR = Path(
    "/Users/gayan/Desktop/SLIIT SE/RESEARCH/Project/"
    "AI-Smart-Tea-Ecosystem/backend/plantation_health_dataset"
)

# Component02-only training dataset
BASE_DIR = Path(__file__).resolve().parent
DEST_DIR = BASE_DIR / "plantation_health" / "data"

# Split ratios
TRAIN_RATIO = 0.70
VAL_RATIO = 0.20
TEST_RATIO = 0.10

# Classes
CLASSES = [
    "healthy",
    "low_health"
]

random.seed(42)


# ============================================================
# CHECK SOURCE DATASET
# ============================================================

if not SOURCE_DIR.exists():
    raise FileNotFoundError(
        f"Dataset not found:\n{SOURCE_DIR}"
    )


# ============================================================
# SPLIT DATASET
# ============================================================

for cls in CLASSES:

    source_class_dir = SOURCE_DIR / cls

    if not source_class_dir.exists():
        raise FileNotFoundError(
            f"Class folder not found:\n{source_class_dir}"
        )

    # Supported image formats
    images = [
        image
        for image in source_class_dir.iterdir()
        if image.is_file()
        and image.suffix.lower()
        in [".jpg", ".jpeg", ".png", ".webp"]
    ]

    if len(images) == 0:
        print(f"⚠️ No images found in {cls}")
        continue

    # Shuffle
    random.shuffle(images)

    total = len(images)

    # Calculate split
    train_count = int(total * TRAIN_RATIO)
    val_count = int(total * VAL_RATIO)

    train_images = images[:train_count]

    val_images = images[
        train_count:
        train_count + val_count
    ]

    test_images = images[
        train_count + val_count:
    ]

    splits = {
        "train": train_images,
        "val": val_images,
        "test": test_images
    }

    # Copy images
    for split, split_images in splits.items():

        destination = (
            DEST_DIR
            / split
            / cls
        )

        destination.mkdir(
            parents=True,
            exist_ok=True
        )

        for image in split_images:

            shutil.copy2(
                image,
                destination / image.name
            )

    # Print statistics
    print()
    print("=" * 50)
    print(f"Class: {cls}")
    print(f"Total: {total}")
    print(f"Train: {len(train_images)}")
    print(f"Validation: {len(val_images)}")
    print(f"Test: {len(test_images)}")
    print("=" * 50)


print()
print("✅ Component02 Plantation Health Dataset Split Completed!")
print()
print(f"Dataset location:")
print(DEST_DIR)