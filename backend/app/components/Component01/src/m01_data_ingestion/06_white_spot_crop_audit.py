
from pathlib import Path
from collections import Counter, defaultdict
from hashlib import sha256
from PIL import Image, ImageOps, ImageDraw
import csv
import math

# ==========================================================
# STEP 06 - WHITE SPOT CROP QUALITY & DUPLICATE AUDIT
# ==========================================================

ROOT = Path(__file__).resolve().parents[2]

REPORT_DIR = ROOT / "outputs" / "reports"
FIGURE_DIR = ROOT / "outputs" / "figures" / "white_spot_review"

SOURCE_REPORT = (
    REPORT_DIR / "external_white_spot_yolo_crops.csv"
)
ORIGINAL_AUDIT = REPORT_DIR / "image_audit.csv"
OUTPUT_REPORT = REPORT_DIR / "white_spot_crop_quality_audit.csv"

NEAR_DUPLICATE_THRESHOLD = 4  # Review flag only

FIGURE_DIR.mkdir(parents=True, exist_ok=True)


def file_hash(path):
    digest = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dhash(path):
    """64-bit difference hash for similarity screening."""
    with Image.open(path) as opened:
        img = ImageOps.exif_transpose(opened)
        img = img.convert("L").resize((9, 8))

    pixels = img.tobytes()
    result = 0

    for y in range(8):
        for x in range(8):
            left = pixels[y * 9 + x]
            right = pixels[y * 9 + x + 1]
            result = (result << 1) | int(left > right)

    return result


def hash_distance(a, b):
    return (a ^ b).bit_count()


def read_csv(path):
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ----------------------------------------------------------
# 01. LOAD ORIGINAL DATASET HASHES
# ----------------------------------------------------------

original_rows = read_csv(ORIGINAL_AUDIT)
crop_rows = read_csv(SOURCE_REPORT)

original_hash_classes = defaultdict(set)
original_white_hashes = {}

for row in original_rows:
    digest = row["sha256"]

    if not digest or row["status"] == "corrupted":
        continue

    original_hash_classes[digest].add(row["class_name"])

    if row["class_name"] == "white spot":
        path = (
            ROOT / "data" / "raw" / "images"
            / row["relative_path"]
        )

        if path.is_file() and digest not in original_white_hashes:
            original_white_hashes[digest] = path


# ----------------------------------------------------------
# 02. COMPUTE ORIGINAL WHITE SPOT PERCEPTUAL HASHES
# ----------------------------------------------------------

reference_hashes = []

for path in original_white_hashes.values():
    try:
        reference_hashes.append(dhash(path))
    except Exception as exc:
        print(f"WARNING: Original reference skipped: {exc}")


# ----------------------------------------------------------
# 03. CHECK EXTRACTED CROPS
# ----------------------------------------------------------

seen_exact = set()
previous_visual_hashes = []
source_splits = defaultdict(set)
results = []
contact_images = []

counts = Counter()

for row in crop_rows:

    path = ROOT / row["crop_path"]
    counts["total"] += 1

    result = {
        "crop_path": row["crop_path"],
        "original_split": row["original_split"],
        "source_image": row["source_image"],
        "source_image_sha256": row["source_image_sha256"],
        "status": "pending_visual_review",
        "exact_original_match": "no",
        "exact_original_classes": "",
        "exact_crop_duplicate": "no",
        "near_original_white_spot": "no",
        "near_other_yolo_crop": "no",
        "nearest_original_distance": "",
        "nearest_crop_distance": "",
    }

    try:
        if not path.is_file():
            raise FileNotFoundError(path)

        with Image.open(path) as opened:
            opened.verify()

        with Image.open(path) as opened:
            opened.load()
            thumb = opened.convert("RGB").copy()

        exact = file_hash(path)
        visual = dhash(path)

        # Exact matches against original six classes
        matched_classes = original_hash_classes.get(exact, set())

        if matched_classes:
            result["exact_original_match"] = "yes"
            result["exact_original_classes"] = ", ".join(
                sorted(matched_classes)
            )
            counts["exact_original_matches"] += 1

        if exact in seen_exact:
            result["exact_crop_duplicate"] = "yes"
            counts["exact_crop_duplicates"] += 1

        seen_exact.add(exact)

        # Possible near-duplicates against original White Spot
        if reference_hashes:
            distance = min(
                hash_distance(visual, ref)
                for ref in reference_hashes
            )
            result["nearest_original_distance"] = distance

            if distance <= NEAR_DUPLICATE_THRESHOLD:
                result["near_original_white_spot"] = "yes"
                counts["near_original_flags"] += 1

        # Possible near-duplicates within YOLO crops
        if previous_visual_hashes:
            distance = min(
                hash_distance(visual, other)
                for other in previous_visual_hashes
            )
            result["nearest_crop_distance"] = distance

            if distance <= NEAR_DUPLICATE_THRESHOLD:
                result["near_other_yolo_crop"] = "yes"
                counts["near_crop_flags"] += 1

        previous_visual_hashes.append(visual)

        source_splits[row["source_image_sha256"]].add(
            row["original_split"]
        )

        contact_images.append((
            thumb, row["original_split"], path.name
        ))

        counts["readable"] += 1

    except Exception as exc:
        result["status"] = "corrupted_or_missing"
        counts["failed"] += 1
        print(f"WARNING: {path.name}: {exc}")

    results.append(result)


# ----------------------------------------------------------
# 04. CHECK SOURCE IMAGE OVERLAP BETWEEN SPLITS
# ----------------------------------------------------------

cross_split_sources = sum(
    len(splits) > 1
    for splits in source_splits.values()
)


# ----------------------------------------------------------
# 05. SAVE CSV REPORT
# ----------------------------------------------------------

with OUTPUT_REPORT.open(
    "w", encoding="utf-8", newline=""
) as f:
    writer = csv.DictWriter(
        f, fieldnames=list(results[0].keys())
    )
    writer.writeheader()
    writer.writerows(results)


# ----------------------------------------------------------
# 06. GENERATE VISUAL CONTACT SHEETS
# ----------------------------------------------------------

COLUMNS = 5
ROWS = 8
CELL_W = 165
CELL_H = 175
PER_SHEET = COLUMNS * ROWS

num_sheets = math.ceil(len(contact_images) / PER_SHEET)

for page in range(num_sheets):

    subset = contact_images[
        page * PER_SHEET:(page + 1) * PER_SHEET
    ]

    sheet = Image.new(
        "RGB",
        (COLUMNS * CELL_W, ROWS * CELL_H),
        "white"
    )
    draw = ImageDraw.Draw(sheet)

    for index, (img, split, filename) in enumerate(subset):
        x = (index % COLUMNS) * CELL_W
        y = (index // COLUMNS) * CELL_H

        thumbnail = ImageOps.contain(img, (150, 135))
        sheet.paste(thumbnail, (x + 5, y + 5))

        draw.text(
            (x + 5, y + 143),
            f"{split}: {filename[:16]}",
            fill="black"
        )

    sheet.save(
        FIGURE_DIR / f"contact_sheet_{page + 1:02d}.png"
    )


# ----------------------------------------------------------
# 07. FINAL SUMMARY
# ----------------------------------------------------------

print("=" * 65)
print("STEP 06 - WHITE SPOT CROP QUALITY AUDIT")
print("=" * 65)

print(f"Total extracted crops     : {counts['total']}")
print(f"Readable crops            : {counts['readable']}")
print(f"Corrupted/missing crops   : {counts['failed']}")
print(f"Exact original matches    : {counts['exact_original_matches']}")
print(f"Exact duplicates in crops : {counts['exact_crop_duplicates']}")
print(f"Near-original review flags: {counts['near_original_flags']}")
print(f"Near-crop review flags    : {counts['near_crop_flags']}")
print(f"Cross-split source hashes : {cross_split_sources}")

print(f"\nQuality report: {OUTPUT_REPORT}")
print(f"Contact sheets : {FIGURE_DIR}")
print(f"Contact sheets generated: {num_sheets}")

print("\nAll valid crops remain pending visual review.")
print("Near-duplicate flags are NOT confirmed duplicates.")
print("No source images were modified or deleted.")
print("\nSTEP 06 COMPLETED")


