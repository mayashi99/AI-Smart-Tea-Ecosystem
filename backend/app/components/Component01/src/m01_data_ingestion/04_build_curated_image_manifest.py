from pathlib import Path
import csv
import json
from collections import Counter

# ==========================================================
# STEP 04 - BUILD CURATED IMAGE MANIFEST
# ==========================================================

ROOT = Path(__file__).resolve().parents[2]

REPORT_DIR = ROOT / "outputs" / "reports"
PROCESSED_DIR = ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

ORIGINAL_AUDIT = REPORT_DIR / "image_audit.csv"
EXTERNAL_HEALTHY_AUDIT = REPORT_DIR / "external_healthy_audit.csv"

MANIFEST_PATH = PROCESSED_DIR / "image_curated_manifest.csv"
SUMMARY_PATH = PROCESSED_DIR / "image_curated_manifest_summary.json"

if not ORIGINAL_AUDIT.exists():
    raise FileNotFoundError(
        f"Missing original audit file: {ORIGINAL_AUDIT}"
    )

if not EXTERNAL_HEALTHY_AUDIT.exists():
    raise FileNotFoundError(
        f"Missing external healthy audit file: {EXTERNAL_HEALTHY_AUDIT}"
    )

records = []

# ----------------------------------------------------------
# ORIGINAL DATASET
# ----------------------------------------------------------
with ORIGINAL_AUDIT.open("r", encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        if row["status"] in {"valid", "low_resolution"}:
            records.append({
                "dataset_source": "original",
                "class_name": row["class_name"],
                "relative_path": str(
                    Path("data/raw/images") / row["relative_path"]
                ),
                "status": row["status"],
                "include_in_training": "yes",
                "notes": ""
            })

# ----------------------------------------------------------
# EXTERNAL HEALTHY DATASET
# ----------------------------------------------------------
with EXTERNAL_HEALTHY_AUDIT.open("r", encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        if row["status"] == "new_unique":
            records.append({
                "dataset_source": "external_tealeafbd",
                "class_name": "healthy",
                "relative_path": str(
                    Path("data/external/tealeafbd/healthy") / row["filename"]
                ),
                "status": row["status"],
                "include_in_training": "yes",
                "notes": "external healthy candidate"
            })

# ----------------------------------------------------------
# SAVE MANIFEST
# ----------------------------------------------------------
with MANIFEST_PATH.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "dataset_source",
            "class_name",
            "relative_path",
            "status",
            "include_in_training",
            "notes"
        ]
    )
    writer.writeheader()
    writer.writerows(records)

# ----------------------------------------------------------
# SUMMARY
# ----------------------------------------------------------
class_counts = Counter()
source_counts = Counter()

for r in records:
    class_counts[r["class_name"]] += 1
    source_counts[r["dataset_source"]] += 1

summary = {
    "total_training_candidates": len(records),
    "class_counts": dict(class_counts),
    "source_counts": dict(source_counts)
}

with SUMMARY_PATH.open("w", encoding="utf-8") as f:
    json.dump(summary, f, indent=4)

# ----------------------------------------------------------
# TERMINAL OUTPUT
# ----------------------------------------------------------
print("=" * 65)
print("STEP 04 - CURATED IMAGE MANIFEST BUILD")
print("=" * 65)

print(f"Total training candidates: {len(records)}")

print("\nClass counts:")
for cls, count in sorted(class_counts.items()):
    print(f"{cls:<20}: {count}")

print("\nSource counts:")
for src, count in sorted(source_counts.items()):
    print(f"{src:<20}: {count}")

print("\nSaved files:")
print(MANIFEST_PATH)
print(SUMMARY_PATH)

print("\nSTEP 04 COMPLETED")