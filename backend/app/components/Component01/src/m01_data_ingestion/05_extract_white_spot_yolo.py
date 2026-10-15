
from pathlib import Path
from collections import Counter
from hashlib import sha256
from PIL import Image, ImageOps
from math import isfinite
import argparse
import csv

# ============================================================
# STEP 05 - EXTRACT WHITE SPOT FROM YOLO DATASET
# PROJECT: AI-Powered Climate-Aware Tea Disease Intelligence
# COMPONENT: Component01
# ============================================================

# ------------------------------------------------------------
# 01. PROJECT PATH CONFIGURATION
# ------------------------------------------------------------

COMPONENT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DATASET_DIR = (
    COMPONENT_ROOT
    / "data"
    / "external"
    / "white_spot_source"
    / "downloaded_dataset"
)

OUTPUT_DIR = (
    COMPONENT_ROOT
    / "data"
    / "external"
    / "white_spot_source"
    / "white spot"
    / "yolo_crops"
)

REPORT_DIR = COMPONENT_ROOT / "outputs" / "reports"

REPORT_PATH = (
    REPORT_DIR / "external_white_spot_yolo_crops.csv"
)

# Confirmed using data.yaml:
# 6 = White spot of tea
WHITE_SPOT_CLASS_ID = 6

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}

MIN_CROP_SIZE = 32


# ------------------------------------------------------------
# 02. HELPER FUNCTIONS
# ------------------------------------------------------------

def calculate_sha256(file_path):
    """Calculate SHA-256 hash of a source image."""

    digest = sha256()

    with file_path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024), b""
        ):
            digest.update(chunk)

    return digest.hexdigest()


def get_image_paths(images_dir):
    """Return supported image files in sorted order."""

    return sorted(
        path
        for path in images_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def parse_yolo_box(line):
    """
    Parse one YOLO detection annotation.

    Expected format:
    class_id x_center y_center box_width box_height
    """

    parts = line.strip().split()

    if len(parts) != 5:
        return None, "unsupported_annotation"

    try:
        class_id = int(parts[0])
        values = [float(value) for value in parts[1:]]

    except ValueError:
        return None, "invalid_annotation_value"

    if not all(isfinite(value) for value in values):
        return None, "non_finite_box"

    xc, yc, bw, bh = values

    if not (
        0 <= xc <= 1
        and 0 <= yc <= 1
        and 0 < bw <= 1
        and 0 < bh <= 1
    ):
        return None, "invalid_box"

    return (class_id, xc, yc, bw, bh), None


# ------------------------------------------------------------
# 03. MAIN EXTRACTION PIPELINE
# ------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Extract White Spot tea leaf regions "
            "from a YOLO detection dataset."
        )
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help=(
            "YOLO dataset root. Defaults to the "
            "Component01 external dataset folder."
        )
    )

    args = parser.parse_args()

    dataset_root = args.dataset.expanduser().resolve()

    print("=" * 70)
    print("STEP 05 - WHITE SPOT YOLO DATA EXTRACTION")
    print("=" * 70)

    print(f"\nComponent Root : {COMPONENT_ROOT}")
    print(f"Dataset Root   : {dataset_root}")
    print(f"Target Class   : {WHITE_SPOT_CLASS_ID} - White spot of tea")

    if not dataset_root.is_dir():
        raise FileNotFoundError(
            f"\nYOLO dataset not found:\n{dataset_root}\n"
            "Place train/, valid/, test/ and data.yaml "
            "inside the default dataset folder."
        )

    if not (dataset_root / "data.yaml").is_file():
        raise FileNotFoundError(
            f"Missing YOLO configuration: {dataset_root / 'data.yaml'}"
        )

    # Confirm the expected YOLO folder structure
    for split in ["train", "valid", "test"]:

        images_dir = dataset_root / split / "images"
        labels_dir = dataset_root / split / "labels"

        if not images_dir.is_dir():
            raise FileNotFoundError(images_dir)

        if not labels_dir.is_dir():
            raise FileNotFoundError(labels_dir)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    records = []

    counts = Counter()
    skipped = Counter()

    # --------------------------------------------------------
    # 04. PROCESS ALL ORIGINAL DATASET SPLITS
    # --------------------------------------------------------

    for split in ["train", "valid", "test"]:

        print("\n" + "-" * 70)
        print(f"PROCESSING: {split.upper()}")
        print("-" * 70)

        images_dir = dataset_root / split / "images"
        labels_dir = dataset_root / split / "labels"

        split_output_dir = OUTPUT_DIR / split
        split_output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        image_paths = get_image_paths(images_dir)

        print(f"Images available: {len(image_paths)}")

        for image_path in image_paths:

            relative_image_path = (
                image_path.relative_to(images_dir)
            )

            label_path = (
                labels_dir / relative_image_path
            ).with_suffix(".txt")

            if not label_path.is_file():
                skipped["missing_label_file"] += 1
                continue

            try:
                annotations = label_path.read_text(
                    encoding="utf-8"
                ).splitlines()

                with Image.open(image_path) as opened:

                    image = ImageOps.exif_transpose(opened)
                    image = image.convert("RGB")

                image_width, image_height = image.size

                source_key = (
                    f"{split}/"
                    f"{relative_image_path.as_posix()}"
                )

                # Hash the source image for future
                # duplicate and leakage analysis.
                source_file_hash = calculate_sha256(
                    image_path
                )

                source_key_hash = sha256(
                    source_key.encode("utf-8")
                ).hexdigest()[:16]

                valid_crops_from_image = 0

                for annotation_index, line in enumerate(
                    annotations
                ):

                    if not line.strip():
                        continue

                    parsed_box, error = parse_yolo_box(
                        line
                    )

                    if error:
                        skipped[error] += 1
                        continue

                    class_id, xc, yc, bw, bh = parsed_box

                    # Extract White Spot only.
                    if class_id != WHITE_SPOT_CLASS_ID:
                        continue

                    x1 = max(
                        0,
                        round(
                            (xc - bw / 2) * image_width
                        )
                    )

                    y1 = max(
                        0,
                        round(
                            (yc - bh / 2) * image_height
                        )
                    )

                    x2 = min(
                        image_width,
                        round(
                            (xc + bw / 2) * image_width
                        )
                    )

                    y2 = min(
                        image_height,
                        round(
                            (yc + bh / 2) * image_height
                        )
                    )

                    crop_width = x2 - x1
                    crop_height = y2 - y1

                    if (
                        crop_width < MIN_CROP_SIZE
                        or crop_height < MIN_CROP_SIZE
                    ):
                        skipped["small_crop"] += 1
                        continue

                    crop = image.crop(
                        (x1, y1, x2, y2)
                    )

                    output_filename = (
                        f"white_spot_{source_key_hash}"
                        f"_{annotation_index}.jpg"
                    )

                    output_path = (
                        split_output_dir / output_filename
                    )

                    crop.save(
                        output_path,
                        format="JPEG",
                        quality=95
                    )

                    records.append({

                        "source_dataset": "external_yolo",

                        "original_split": split,

                        "source_image": source_key,

                        "source_image_sha256": source_file_hash,

                        "crop_path": str(
                            output_path.relative_to(
                                COMPONENT_ROOT
                            )
                        ),

                        "class_id": WHITE_SPOT_CLASS_ID,

                        "class_name": "white spot",

                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,

                        "crop_width": crop_width,

                        "crop_height": crop_height,

                        "status": "pending_visual_review"

                    })

                    valid_crops_from_image += 1
                    counts[f"{split}_crops"] += 1

                if valid_crops_from_image > 0:
                    counts[f"{split}_source_images"] += 1

            except Exception as error:

                skipped["processing_error"] += 1

                print(
                    f"WARNING: {image_path.name}: "
                    f"{error}"
                )

        print(
            "White Spot source images:",
            counts[f"{split}_source_images"]
        )

        print(
            "White Spot crops:",
            counts[f"{split}_crops"]
        )

    # --------------------------------------------------------
    # 05. SAVE EXTRACTION REPORT
    # --------------------------------------------------------

    fieldnames = [

        "source_dataset",
        "original_split",
        "source_image",
        "source_image_sha256",
        "crop_path",
        "class_id",
        "class_name",
        "x1",
        "y1",
        "x2",
        "y2",
        "crop_width",
        "crop_height",
        "status"

    ]

    with REPORT_PATH.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(records)

    # --------------------------------------------------------
    # 06. FINAL TERMINAL SUMMARY
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("FINAL WHITE SPOT EXTRACTION SUMMARY")
    print("=" * 70)

    total_source_images = sum(
        counts[f"{split}_source_images"]
        for split in ["train", "valid", "test"]
    )

    print(f"\nTotal source images : {total_source_images}")
    print(f"Total crops created : {len(records)}")

    print("\nSplit-wise summary:")

    for split in ["train", "valid", "test"]:

        print(
            f"{split:<6} | "
            f"Source images: "
            f"{counts[f'{split}_source_images']:<6} | "
            f"Crops: "
            f"{counts[f'{split}_crops']}"
        )

    print(f"\nSkipped annotations/files: {dict(skipped)}")

    print("\nGenerated report:")
    print(REPORT_PATH)

    print("\nExtracted images:")
    print(OUTPUT_DIR)

    print("\nIMPORTANT:")
    print(
        "All extracted crops are pending visual review."
    )
    print(
        "Duplicate and leakage checks are required "
        "before training."
    )

    print("\nNO ORIGINAL IMAGES MODIFIED")
    print("STEP 05 COMPLETED")


if __name__ == "__main__":
    main()
