import os
import random
import shutil
from pathlib import Path

# -----------------------------
# Source Dataset (Original Images)
# -----------------------------
SOURCE_DIR = Path("/Users/gayan/Desktop/SLIIT SE/RESEARCH/dataset/Harvest_readynes_data")

# -----------------------------
# Destination Dataset (YOLO Project)
# -----------------------------
DEST_DIR = Path("dataset")

# Split Ratio
TRAIN_RATIO = 0.7
VAL_RATIO = 0.2
TEST_RATIO = 0.1

random.seed(42)

classes = ["After_Harvest", "Harvest_Ready", "Not_Ready"]

for cls in classes:

    images = list((SOURCE_DIR / cls).glob("*.*"))
    random.shuffle(images)

    total = len(images)

    train_count = int(total * TRAIN_RATIO)
    val_count = int(total * VAL_RATIO)

    train_images = images[:train_count]
    val_images = images[train_count:train_count + val_count]
    test_images = images[train_count + val_count:]

    for split, split_images in {
        "train": train_images,
        "val": val_images,
        "test": test_images
    }.items():

        destination = DEST_DIR / split / cls
        destination.mkdir(parents=True, exist_ok=True)

        for image in split_images:
            shutil.copy(image, destination / image.name)

print("✅ Dataset Split Completed Successfully!")
