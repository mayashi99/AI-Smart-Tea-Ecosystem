
from pathlib import Path
from collections import Counter, defaultdict
from hashlib import sha256
from PIL import Image
import csv
import json

# STEP 03 - EXTERNAL HEALTHY IMAGE AUDIT

ROOT = Path(__file__).resolve().parents[2]
EXTERNAL_DIR = ROOT / "data/external/tealeafbd/healthy"
REPORT_DIR = ROOT / "outputs/reports"
ORIGINAL_AUDIT = REPORT_DIR / "image_audit.csv"

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

if not EXTERNAL_DIR.exists():
    raise FileNotFoundError(EXTERNAL_DIR)

if not ORIGINAL_AUDIT.exists():
    raise FileNotFoundError(
        "Run 01_image_data_audit.py first."
    )

# Load hashes of original images from all six classes
original_hashes = defaultdict(set)

with ORIGINAL_AUDIT.open(
    "r", encoding="utf-8", newline=""
) as f:
    for row in csv.DictReader(f):
        if row["sha256"]:
            original_hashes[row["sha256"]].add(
                row["class_name"]
            )

def get_hash(path):
    digest = sha256()
    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024), b""
        ):
            digest.update(chunk)
    return digest.hexdigest()

images = sorted(
    p for p in EXTERNAL_DIR.rglob("*")
    if p.is_file()
    and p.suffix.lower() in VALID_EXTENSIONS
)

seen_external = set()
records = []

for path in images:

    status = "new_unique"
    file_hash = ""

    try:
        with Image.open(path) as img:
            img.verify()

        with Image.open(path) as img:
            img.load()

        file_hash = get_hash(path)

        original_classes = original_hashes.get(
            file_hash, set()
        )

        if original_classes - {"healthy"}:
            status = "conflicts_with_other_class"

        elif "healthy" in original_classes:
            status = "already_in_original_healthy"

        elif file_hash in seen_external:
            status = "duplicate_within_external"

        seen_external.add(file_hash)

    except Exception:
        status = "corrupted"

    records.append({
        "filename": str(
            path.relative_to(EXTERNAL_DIR)
        ),
        "sha256": file_hash,
        "status": status
    })

counts = Counter(row["status"] for row in records)

REPORT_DIR.mkdir(parents=True, exist_ok=True)

report_path = (
    REPORT_DIR / "external_healthy_audit.csv"
)

with report_path.open(
    "w", newline="", encoding="utf-8"
) as f:
    writer = csv.DictWriter(
        f, fieldnames=[
            "filename", "sha256", "status"
        ]
    )
    writer.writeheader()
    writer.writerows(records)

summary = {
    "total_external_images": len(images),
    "status_counts": dict(counts),
    "exact_unique_new_candidates": counts["new_unique"]
}

summary_path = (
    REPORT_DIR / "external_healthy_summary.json"
)

with summary_path.open(
    "w", encoding="utf-8"
) as f:
    json.dump(summary, f, indent=4)

print("=" * 60)
print("STEP 03 - EXTERNAL HEALTHY DATASET AUDIT")
print("=" * 60)

print(f"Total external images       : {len(images)}")
print(f"New unique candidates       : {counts['new_unique']}")
print(f"Duplicates within external  : {counts['duplicate_within_external']}")
print(f"Already in original healthy : {counts['already_in_original_healthy']}")
print(f"Conflicts with other classes: {counts['conflicts_with_other_class']}")
print(f"Corrupted images            : {counts['corrupted']}")

print("\nReports saved:")
print(report_path)
print(summary_path)

print("\nAUDIT COMPLETED - NO IMAGES MODIFIED")
