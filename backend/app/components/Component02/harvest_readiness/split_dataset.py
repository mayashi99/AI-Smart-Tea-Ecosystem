from pathlib import Path
import random
import os
import shutil

# ============================================================
# HARVEST READINESS - DATASET SPLIT
# HARD-LINK VERSION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"

ORIGINAL_DIR = DATA_DIR / "original"

TRAIN_DIR = DATA_DIR / "train"
VAL_DIR = DATA_DIR / "val"
TEST_DIR = DATA_DIR / "test"

# ============================================================
# CONFIGURATION
# ============================================================

TRAIN_RATIO = 0.70
VAL_RATIO = 0.20
TEST_RATIO = 0.10

RANDOM_SEED = 42

# ============================================================
# CLASSES
# ============================================================

CLASSES = [
    "Harvest_Ready",
    "Harvest_Not_Ready"
]

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}

# ============================================================
# VALIDATE RATIOS
# ============================================================

total_ratio = (
    TRAIN_RATIO
    + VAL_RATIO
    + TEST_RATIO
)

if abs(total_ratio - 1.0) > 0.000001:
    raise ValueError(
        "Train, validation and test ratios must add up to 1.0"
    )

# ============================================================
# RANDOM SEED
# ============================================================

random.seed(RANDOM_SEED)

# ============================================================
# REMOVE OLD SPLIT DIRECTORIES
# ============================================================

for directory in [
    TRAIN_DIR,
    VAL_DIR,
    TEST_DIR
]:

    if directory.exists():
        print(f"Removing old directory: {directory}")
        shutil.rmtree(directory)

# ============================================================
# CREATE OUTPUT DIRECTORIES
# ============================================================

for class_name in CLASSES:

    (TRAIN_DIR / class_name).mkdir(
        parents=True,
        exist_ok=True
    )

    (VAL_DIR / class_name).mkdir(
        parents=True,
        exist_ok=True
    )

    (TEST_DIR / class_name).mkdir(
        parents=True,
        exist_ok=True
    )

# ============================================================
# HEADER
# ============================================================

print()
print("=" * 70)
print("HARVEST READINESS - DATASET SPLIT")
print("HARD-LINK MODE")
print("=" * 70)

print()

print("Train      : 70%")
print("Validation : 20%")
print("Test       : 10%")
print("Random seed: 42")

print()

print("Original images will NOT be physically copied.")
print("Hard links will be created instead.")

print()

# ============================================================
# SPLIT EACH CLASS
# ============================================================

for class_name in CLASSES:

    source_dir = ORIGINAL_DIR / class_name

    train_class_dir = TRAIN_DIR / class_name
    val_class_dir = VAL_DIR / class_name
    test_class_dir = TEST_DIR / class_name

    # --------------------------------------------------------
    # CHECK SOURCE
    # --------------------------------------------------------

    if not source_dir.exists():
        raise FileNotFoundError(
            f"Source directory not found:\n{source_dir}"
        )

    # --------------------------------------------------------
    # COLLECT IMAGES
    # --------------------------------------------------------

    images = [
        image
        for image in source_dir.iterdir()
        if (
            image.is_file()
            and image.suffix.lower() in IMAGE_EXTENSIONS
        )
    ]

    if len(images) == 0:
        raise RuntimeError(
            f"No images found in:\n{source_dir}"
        )

    # --------------------------------------------------------
    # SHUFFLE
    # --------------------------------------------------------

    random.shuffle(images)

    total = len(images)

    # --------------------------------------------------------
    # COUNTS
    # --------------------------------------------------------

    train_count = int(total * TRAIN_RATIO)

    val_count = int(total * VAL_RATIO)

    test_count = (
        total
        - train_count
        - val_count
    )

    # --------------------------------------------------------
    # SPLIT
    # --------------------------------------------------------

    train_images = images[
        :train_count
    ]

    val_images = images[
        train_count:
        train_count + val_count
    ]

    test_images = images[
        train_count + val_count:
    ]

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    print("=" * 70)
    print(class_name)
    print("=" * 70)

    print(f"Total      : {total}")
    print(f"Train      : {len(train_images)}")
    print(f"Validation : {len(val_images)}")
    print(f"Test       : {len(test_images)}")

    print()

    # --------------------------------------------------------
    # HARD LINK FUNCTION
    # --------------------------------------------------------

    def create_hard_links(
        image_list,
        destination_dir
    ):

        for image in image_list:

            destination = (
                destination_dir / image.name
            )

            os.link(
                image,
                destination
            )

    # --------------------------------------------------------
    # TRAIN
    # --------------------------------------------------------

    print("Creating train hard links...")

    create_hard_links(
        train_images,
        train_class_dir
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    print("Creating validation hard links...")

    create_hard_links(
        val_images,
        val_class_dir
    )

    # --------------------------------------------------------
    # TEST
    # --------------------------------------------------------

    print("Creating test hard links...")

    create_hard_links(
        test_images,
        test_class_dir
    )

    print(
        f"✅ {class_name} completed"
    )

    print()

# ============================================================
# FINAL COUNTS
# ============================================================

print("=" * 70)
print("FINAL DATASET COUNTS")
print("=" * 70)

print()

total_train = 0
total_val = 0
total_test = 0

for class_name in CLASSES:

    train_count = len([
        file
        for file in (TRAIN_DIR / class_name).iterdir()
        if (
            file.is_file()
            and file.suffix.lower() in IMAGE_EXTENSIONS
        )
    ])

    val_count = len([
        file
        for file in (VAL_DIR / class_name).iterdir()
        if (
            file.is_file()
            and file.suffix.lower() in IMAGE_EXTENSIONS
        )
    ])

    test_count = len([
        file
        for file in (TEST_DIR / class_name).iterdir()
        if (
            file.is_file()
            and file.suffix.lower() in IMAGE_EXTENSIONS
        )
    ])

    total_train += train_count
    total_val += val_count
    total_test += test_count

    print(class_name)

    print(f"  Train      : {train_count}")
    print(f"  Validation : {val_count}")
    print(f"  Test       : {test_count}")

    print()

# ============================================================
# TOTAL
# ============================================================

split_total = (
    total_train
    + total_val
    + total_test
)

print("-" * 70)

print(f"Total Train      : {total_train}")
print(f"Total Validation : {total_val}")
print(f"Total Test       : {total_test}")
print(f"Total Images     : {split_total}")

# ============================================================
# ORIGINAL COUNT
# ============================================================

original_total = 0

for class_name in CLASSES:

    original_total += len([
        file
        for file in (ORIGINAL_DIR / class_name).iterdir()
        if (
            file.is_file()
            and file.suffix.lower() in IMAGE_EXTENSIONS
        )
    ])

print()

print(f"Original Images  : {original_total}")

# ============================================================
# VERIFY
# ============================================================

print()

if split_total == original_total:

    print("✅ TOTAL IMAGE COUNT VERIFIED")

else:

    print("❌ IMAGE COUNT MISMATCH")

    print(f"Original : {original_total}")
    print(f"Split    : {split_total}")

# ============================================================
# EXPECTED COUNTS
# ============================================================

print()

print("=" * 70)
print("EXPECTED COUNTS")
print("=" * 70)

print()

print("Harvest_Ready")
print("  Train      : 929")
print("  Validation : 265")
print("  Test       : 134")

print()

print("Harvest_Not_Ready")
print("  Train      : 837")
print("  Validation : 239")
print("  Test       : 121")

print()

print("TOTAL")
print("  Train      : 1766")
print("  Validation : 504")
print("  Test       : 255")
print("  Total      : 2525")

print()

print("=" * 70)
print("✅ DATASET SPLIT COMPLETED")
print("=" * 70)

print()

print("Original dataset was NOT modified.")
print("Hard links used - minimal additional disk space.")

print()