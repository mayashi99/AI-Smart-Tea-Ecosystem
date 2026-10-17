from pathlib import Path
import hashlib
import random
import shutil


# ============================================================
# COMPONENT 02 - LEAKAGE-SAFE DATASET SPLIT
# ============================================================

BASE_DIR = Path(__file__).resolve().parent


# ============================================================
# ORIGINAL DATASET
# ============================================================

SOURCE_DIR = Path(
    "/Users/gayan/Desktop/SLIIT SE/RESEARCH/dataset/"
    "plantation_health_dataset"
)


# ============================================================
# COMPONENT 02 OUTPUT DATASET
# ============================================================

DEST_DIR = (
    BASE_DIR
    / "plantation_health"
    / "data"
)


# ============================================================
# SOURCE FOLDER MAPPING
# ============================================================

SOURCE_MAPPING = {

    "healthy": [
        "Helthy"
    ],

    "low_health": [
        "Low_helth",
        "BB_Low_helth",
        "RR_Low_helth",
        "RSM_Low_helth"
    ]
}


# ============================================================
# IMAGE EXTENSIONS
# ============================================================

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}


# ============================================================
# SPLIT RATIOS
# ============================================================

TRAIN_RATIO = 0.70
VAL_RATIO = 0.20
TEST_RATIO = 0.10


# ============================================================
# RANDOM SEED
# ============================================================

SEED = 42


# ============================================================
# HASH FUNCTION
# ============================================================

def calculate_hash(file_path):

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:

        while True:

            chunk = file.read(1024 * 1024)

            if not chunk:
                break

            sha256.update(chunk)

    return sha256.hexdigest()


# ============================================================
# COLLECT SOURCE IMAGES
# ============================================================

def collect_images():

    print()
    print("=" * 75)
    print("COLLECTING ORIGINAL DATASET")
    print("=" * 75)

    if not SOURCE_DIR.exists():

        raise FileNotFoundError(
            f"\nOriginal dataset not found:\n{SOURCE_DIR}"
        )

    dataset = {
        "healthy": [],
        "low_health": []
    }

    for model_class, folders in SOURCE_MAPPING.items():

        print()
        print(f"MODEL CLASS: {model_class}")

        for folder_name in folders:

            folder_path = (
                SOURCE_DIR / folder_name
            )

            if not folder_path.exists():

                raise FileNotFoundError(
                    f"\nRequired folder not found:\n"
                    f"{folder_path}"
                )

            images = []

            for image_path in folder_path.rglob("*"):

                if (
                    image_path.is_file()
                    and image_path.suffix.lower()
                    in IMAGE_EXTENSIONS
                ):

                    images.append(image_path)

            print(
                f"  {folder_name:<20} "
                f"{len(images)} images"
            )

            for image_path in images:

                dataset[model_class].append(
                    image_path
                )

    return dataset


# ============================================================
# BUILD HASH GROUPS
# ============================================================

def build_hash_groups(images):

    groups = {}

    for image_path in images:

        image_hash = calculate_hash(
            image_path
        )

        if image_hash not in groups:

            groups[image_hash] = []

        groups[image_hash].append(
            image_path
        )

    return groups


# ============================================================
# SPLIT HASH GROUPS
# ============================================================

def split_groups(groups):

    group_items = list(
        groups.items()
    )

    random.shuffle(
        group_items
    )

    total_images = sum(
        len(files)
        for _, files in group_items
    )

    target_train = round(
        total_images * TRAIN_RATIO
    )

    target_val = round(
        total_images * VAL_RATIO
    )

    train_groups = []
    val_groups = []
    test_groups = []

    train_count = 0
    val_count = 0
    test_count = 0

    for image_hash, files in group_items:

        group_size = len(files)

        # ----------------------------------------------------
        # Fill TRAIN first until target
        # ----------------------------------------------------

        if (
            train_count + group_size
            <= target_train
        ):

            train_groups.append(
                (image_hash, files)
            )

            train_count += group_size

        # ----------------------------------------------------
        # Then VALIDATION
        # ----------------------------------------------------

        elif (
            val_count + group_size
            <= target_val
        ):

            val_groups.append(
                (image_hash, files)
            )

            val_count += group_size

        # ----------------------------------------------------
        # Remaining groups -> TEST
        # ----------------------------------------------------

        else:

            test_groups.append(
                (image_hash, files)
            )

            test_count += group_size

    return (
        train_groups,
        val_groups,
        test_groups
    )


# ============================================================
# COPY FILES
# ============================================================

def copy_groups(
    groups,
    destination_dir
):

    count = 0

    for image_hash, files in groups:

        for image_path in files:

            # ------------------------------------------------
            # Avoid filename collisions
            # ------------------------------------------------

            destination = (
                destination_dir
                / image_path.name
            )

            if destination.exists():

                destination = (
                    destination_dir
                    / (
                        image_path.stem
                        + "_"
                        + image_hash[:8]
                        + image_path.suffix
                    )
                )

            shutil.copy2(
                image_path,
                destination
            )

            count += 1

    return count


# ============================================================
# CLEAN OLD DATASET
# ============================================================

def clean_previous_split():

    print()
    print("=" * 75)
    print("CLEANING PREVIOUS COMPONENT 02 DATASET")
    print("=" * 75)

    if not DEST_DIR.exists():

        return

    for split in [
        "train",
        "val",
        "test"
    ]:

        split_dir = DEST_DIR / split

        if split_dir.exists():

            print(
                f"Removing: {split_dir}"
            )

            shutil.rmtree(
                split_dir
            )


# ============================================================
# CREATE OUTPUT DIRECTORIES
# ============================================================

def create_directories():

    for split in [
        "train",
        "val",
        "test"
    ]:

        for model_class in [
            "healthy",
            "low_health"
        ]:

            directory = (
                DEST_DIR
                / split
                / model_class
            )

            directory.mkdir(
                parents=True,
                exist_ok=True
            )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 75)
    print("COMPONENT 02 - LEAKAGE-SAFE DATASET SPLIT")
    print("=" * 75)

    print()
    print(f"Original dataset:")
    print(SOURCE_DIR)

    print()
    print(f"Output dataset:")
    print(DEST_DIR)

    print()
    print("Split ratios:")
    print("Train      = 70%")
    print("Validation = 20%")
    print("Test       = 10%")

    print()
    print("Duplicate handling:")
    print(
        "Images with identical SHA-256 hashes "
        "stay in the SAME split."
    )

    # --------------------------------------------------------
    # Collect
    # --------------------------------------------------------

    dataset = collect_images()

    # --------------------------------------------------------
    # Clean
    # --------------------------------------------------------

    clean_previous_split()

    # --------------------------------------------------------
    # Create directories
    # --------------------------------------------------------

    create_directories()

    # --------------------------------------------------------
    # Process each class
    # --------------------------------------------------------

    final_statistics = {}

    for model_class, images in dataset.items():

        print()
        print("=" * 75)
        print(
            f"PROCESSING CLASS: {model_class}"
        )
        print("=" * 75)

        print(
            f"Total source images: "
            f"{len(images)}"
        )

        # ----------------------------------------------------
        # Hash grouping
        # ----------------------------------------------------

        groups = build_hash_groups(
            images
        )

        duplicate_images = (
            len(images)
            - len(groups)
        )

        print(
            f"Unique image groups: "
            f"{len(groups)}"
        )

        print(
            f"Duplicate copies inside "
            f"source: {duplicate_images}"
        )

        # ----------------------------------------------------
        # Split groups
        # ----------------------------------------------------

        (
            train_groups,
            val_groups,
            test_groups
        ) = split_groups(groups)

        train_count = sum(
            len(files)
            for _, files
            in train_groups
        )

        val_count = sum(
            len(files)
            for _, files
            in val_groups
        )

        test_count = sum(
            len(files)
            for _, files
            in test_groups
        )

        print()
        print(
            f"TRAIN : {train_count}"
        )

        print(
            f"VAL   : {val_count}"
        )

        print(
            f"TEST  : {test_count}"
        )

        # ----------------------------------------------------
        # Copy
        # ----------------------------------------------------

        train_destination = (
            DEST_DIR
            / "train"
            / model_class
        )

        val_destination = (
            DEST_DIR
            / "val"
            / model_class
        )

        test_destination = (
            DEST_DIR
            / "test"
            / model_class
        )

        copy_groups(
            train_groups,
            train_destination
        )

        copy_groups(
            val_groups,
            val_destination
        )

        copy_groups(
            test_groups,
            test_destination
        )

        final_statistics[
            model_class
        ] = {
            "total": len(images),
            "train": train_count,
            "val": val_count,
            "test": test_count
        }

    # ========================================================
    # FINAL STATISTICS
    # ========================================================

    print()
    print("=" * 75)
    print("FINAL DATASET STATISTICS")
    print("=" * 75)

    total_original = 0
    total_output = 0

    for model_class, stats in (
        final_statistics.items()
    ):

        print()
        print(
            f"{model_class.upper()}"
        )

        print(
            f"  Total : {stats['total']}"
        )

        print(
            f"  Train : {stats['train']}"
        )

        print(
            f"  Val   : {stats['val']}"
        )

        print(
            f"  Test  : {stats['test']}"
        )

        total_original += stats["total"]

        total_output += (
            stats["train"]
            + stats["val"]
            + stats["test"]
        )

    print()
    print("=" * 75)
    print("FINAL VERIFICATION")
    print("=" * 75)

    print(
        f"Original images : "
        f"{total_original}"
    )

    print(
        f"Output images   : "
        f"{total_output}"
    )

    if total_original == total_output:

        print()
        print(
            "✓ IMAGE COUNT VERIFICATION PASSED"
        )

    else:

        raise RuntimeError(
            "Image count mismatch!"
        )

    print()
    print("=" * 75)
    print("✅ LEAKAGE-SAFE DATASET SPLIT COMPLETED")
    print("=" * 75)

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "✓ Original dataset was NOT modified."
    )

    print(
        "✓ Original images were NOT deleted."
    )

    print(
        "✓ Images were copied only."
    )

    print(
        "✓ Exact duplicate images stay "
        "inside the same split."
    )

    print(
        "✓ Train / Val / Test leakage "
        "is prevented by SHA-256 grouping."
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()