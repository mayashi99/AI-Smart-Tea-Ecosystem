from pathlib import Path
from collections import Counter, defaultdict
from hashlib import sha256
import csv
import json

from PIL import Image

# ==========================================
# STEP 01 - IMAGE DATA QUALITY AUDIT
# ==========================================

ROOT = Path(__file__).resolve().parents[2]

IMAGE_DIR = ROOT / "data" / "raw" / "images"
REPORT_DIR = ROOT / "outputs" / "reports"

REPORT_DIR.mkdir(parents=True, exist_ok=True)

EXPECTED_CLASSES = [
    "brown blight",
    "grey leaf",
    "healthy",
    "red rust",
    "red spider mite",
    "white spot",
]

VALID_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp"
}

records = []
hash_groups = defaultdict(list)

print("=" * 65)
print("STEP 01 - TEA DISEASE IMAGE DATA AUDIT")
print("=" * 65)

for class_name in EXPECTED_CLASSES:

    class_dir = IMAGE_DIR / class_name

    if not class_dir.exists():
        raise FileNotFoundError(
            f"Missing class folder: {class_dir}"
        )

    image_files = sorted([
        p for p in class_dir.rglob("*")
        if p.is_file()
        and p.suffix.lower() in VALID_EXTENSIONS
    ])

    print(f"\nClass: {class_name}")
    print(f"Images found: {len(image_files)}")

    for image_path in image_files:

        record = {
            "class_name": class_name,
            "filename": image_path.name,
            "relative_path": str(
                image_path.relative_to(IMAGE_DIR)
            ),
            "format": "",
            "width": "",
            "height": "",
            "sha256": "",
            "status": "valid",
            "error": "",
        }

        try:
            # Verify file integrity
            with Image.open(image_path) as img:
                img.verify()

            # Decode image and read dimensions
            with Image.open(image_path) as img:
                img.load()
                record["format"] = img.format
                record["width"], record["height"] = img.size

            # Hash for exact duplicate detection
            digest = sha256()

            with image_path.open("rb") as file:
                for chunk in iter(
                    lambda: file.read(1024 * 1024),
                    b""
                ):
                    digest.update(chunk)

            file_hash = digest.hexdigest()

            record["sha256"] = file_hash
            hash_groups[file_hash].append(
                record["relative_path"]
            )

            if (
                record["width"] < 64
                or record["height"] < 64
            ):
                record["status"] = "low_resolution"

        except Exception as error:
            record["status"] = "corrupted"
            record["error"] = str(error)

        records.append(record)


# ==========================================
# DUPLICATE ANALYSIS
# ==========================================

duplicate_groups = {
    digest: paths
    for digest, paths in hash_groups.items()
    if len(paths) > 1
}

cross_class_duplicates = []

for digest, paths in duplicate_groups.items():

    classes = {
        Path(path).parts[0]
        for path in paths
    }

    if len(classes) > 1:
        cross_class_duplicates.append({
            "sha256": digest,
            "paths": paths
        })


# ==========================================
# SAVE IMAGE-LEVEL AUDIT
# ==========================================

audit_path = REPORT_DIR / "image_audit.csv"

with audit_path.open(
    "w", newline="", encoding="utf-8"
) as file:

    writer = csv.DictWriter(
        file, fieldnames=records[0].keys()
    )

    writer.writeheader()
    writer.writerows(records)


# ==========================================
# SUMMARY
# ==========================================

class_counts = Counter(
    record["class_name"]
    for record in records
)

status_counts = Counter(
    record["status"]
    for record in records
)

summary = {
    "total_images": len(records),
    "class_counts": dict(class_counts),
    "status_counts": dict(status_counts),
    "exact_duplicate_groups": len(
        duplicate_groups
    ),
    "cross_class_duplicate_groups": len(
        cross_class_duplicates
    ),
    "cross_class_duplicate_details": (
        cross_class_duplicates
    ),
}

summary_path = (
    REPORT_DIR / "image_audit_summary.json"
)

with summary_path.open(
    "w", encoding="utf-8"
) as file:

    json.dump(
        summary, file, indent=4
    )


# ==========================================
# TERMINAL REPORT
# ==========================================

print("\n" + "=" * 65)
print("FINAL IMAGE AUDIT SUMMARY")
print("=" * 65)

print(f"Total images: {len(records)}")

for class_name in EXPECTED_CLASSES:
    print(
        f"{class_name:<20}: "
        f"{class_counts[class_name]}"
    )

print("\nImage status:")
for status, count in status_counts.items():
    print(f"{status}: {count}")

print(
    "\nExact duplicate groups:",
    len(duplicate_groups)
)

print(
    "Cross-class duplicate groups:",
    len(cross_class_duplicates)
)

print("\nReports saved:")
print(audit_path)
print(summary_path)

print("\nSTEP 01 AUDIT COMPLETED")