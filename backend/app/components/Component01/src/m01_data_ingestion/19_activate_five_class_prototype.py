"""Step 19: switch the DEVELOPMENT-ONLY CNN pipeline from six classes to five.

- Excludes White Spot only from the active CNN development manifest.
- Preserves original images, YOLO sources, Step 15, and old 6-class checkpoints.
- Backs up all three canonical Step 16 files BEFORE any replacement.
- Requires the accompanying Step 19 replacements for 17_train_cnn_dev.py
  and cnn_inference.py (included in Step19 package).
- Does not claim source-independent research evaluation.

From repository root in PowerShell:
  python backend/app/components/Component01/src/m01_data_ingestion/19_activate_five_class_prototype.py
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

CLASSES = ("brown blight", "grey leaf", "healthy", "red rust", "red spider mite")
STATUS = "DEVELOPMENT_ONLY_NOT_FOR_FINAL_EVALUATION"
SPLITS = ("dev_train", "dev_val", "dev_test")


def make_csv_text(rows: list[dict], fields: list[str]) -> str:
    import io
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    manifest_file = root / "data/processed/image_split_manifest_DEV_ONLY.csv"
    mapping_file = root / "data/processed/cnn_class_mapping.json"
    report_file = root / "outputs/reports/image_step16_development_summary.json"
    for path in (manifest_file, mapping_file, report_file):
        if not path.is_file():
            raise FileNotFoundError(f"Missing Step 16 prerequisite: {path}")

    mapping = json.loads(mapping_file.read_text(encoding="utf-8"))
    report = json.loads(report_file.read_text(encoding="utf-8"))
    if mapping.get("num_classes") == 5 and report.get("prototype_num_classes") == 5:
        print("Step 19 already active: five-class development dataset. No changes made.")
        return
    if mapping.get("num_classes") != 6 or report.get("status") != STATUS:
        raise ValueError("Expected original six-class Step 16 files; refuse to overwrite unknown files")
    if report.get("final_research_evaluation_permitted") is not False:
        raise ValueError("Unexpected final evaluation permission; refusing transition")
    if report.get("training_handover_approved") is not False:
        raise ValueError("Unexpected training handover approval; refusing transition")

    with manifest_file.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    required = {"class_name", "class_index", "relative_path", "split", "sha256", "group_id"}
    if not required.issubset(fields):
        raise ValueError(f"Missing manifest columns: {sorted(required - set(fields))}")
    if len(rows) != report.get("total_unique_images"):
        raise ValueError("Manifest row count differs from Step 16 report")
    if not rows or {r["class_name"].strip().lower() for r in rows} != set(CLASSES) | {"white spot"}:
        raise ValueError("Expected six original class labels")

    kept = []
    removed = []
    counts = defaultdict(Counter)
    sha_split = {}
    group_split = {}
    seen_paths = set()
    mapping_5 = {name: i for i, name in enumerate(CLASSES)}
    for row in rows:
        cls = row["class_name"].strip().lower()
        if cls == "white spot":
            removed.append(row)
            continue
        if cls not in mapping_5:
            raise ValueError(f"Unexpected class {cls!r}")
        row = dict(row)
        row["class_name"] = cls
        row["class_index"] = str(mapping_5[cls])
        rel = row["relative_path"].replace("\\", "/")
        if rel.startswith("/") or ".." in Path(rel).parts or ":" in rel:
            raise ValueError(f"Invalid image path {rel}")
        row["relative_path"] = rel
        path = (root / rel).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise FileNotFoundError(f"Missing image {rel}")
        if rel in seen_paths:
            raise ValueError(f"Repeated image path {rel}")
        seen_paths.add(rel)
        split = row["split"]
        if split not in SPLITS:
            raise ValueError(f"Unexpected split {split}")
        sha = row["sha256"].lower()
        if len(sha) != 64:
            raise ValueError(f"Invalid SHA {rel}")
        if sha in sha_split and sha_split[sha] != split:
            raise ValueError(f"Exact-duplicate cross-split conflict {rel}")
        group = (cls, row["group_id"])
        if group in group_split and group_split[group] != split:
            raise ValueError(f"Source-group cross-split conflict {rel}")
        sha_split[sha], group_split[group] = split, split
        kept.append(row)
        counts[cls][split] += 1

    if not removed or any(counts[c][s] < 1 for c in CLASSES for s in SPLITS):
        raise ValueError("Empty class/split or White Spot was not present")
    if len(kept) + len(removed) != len(rows):
        raise RuntimeError("Count inconsistency")

    new_mapping = {
        "class_to_idx": mapping_5,
        "idx_to_class": {str(i): name for i, name in enumerate(CLASSES)},
        "num_classes": 5,
        "image_size": int(mapping.get("image_size", 224)),
        "split_names": list(SPLITS),
        "status": STATUS,
        "white_spot_deferred": True,
    }
    new_summary = {
        **report,
        "total_unique_images": len(kept),
        "source_step16_six_class_images": len(rows),
        "prototype_num_classes": 5,
        "prototype_classes": list(CLASSES),
        "white_spot_deferred": True,
        "white_spot_removed_from_active_manifest": len(removed),
        "development_training_permitted": True,
        "training_handover_approved": False,
        "final_research_evaluation_permitted": False,
        "source_independent_holdout_verified": False,
        "split_counts": {c: {s: counts[c][s] for s in SPLITS} for c in CLASSES},
        "limitations": [
            "Current prototype supports five categories; White Spot deferred due to insufficient independently verified holdout candidates.",
            "Source/plant-level independence for the remaining classes has not been independently verified.",
            "Potential healthy-source background bias remains unassessed.",
            "These are DEV-ONLY splits: metrics must not be presented as final scientifically validated test performance.",
            "No files were augmented or deleted by Step 19.",
        ],
    }
    # Preserve the original full reports and manifests for research traceability.
    archive = root / "data/processed" / ("pre_step19_six_class_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6])
    archive.mkdir(parents=True, exist_ok=False)
    originals = (manifest_file, mapping_file, report_file)
    for file in originals:
        shutil.copy2(file, archive / file.name)

    new_content = {
        manifest_file: make_csv_text(kept, fields),
        mapping_file: json.dumps(new_mapping, indent=2) + "\n",
        report_file: json.dumps(new_summary, indent=2) + "\n",
    }
    staged = {}
    try:
        for destination, text in new_content.items():
            temp = destination.with_name(destination.name + ".step19_tmp")
            temp.write_text(text, encoding="utf-8")
            staged[destination] = temp
        for destination, temp in staged.items():
            os.replace(temp, destination)
    finally:
        for temp in staged.values():
            temp.unlink(missing_ok=True)

    print("=" * 70)
    print("STEP 19 - ACTIVATE FIVE-CLASS CNN DEVELOPMENT PROTOTYPE")
    print("=" * 70)
    print(f"Original Step 16 rows: {len(rows)} | White Spot held out: {len(removed)}")
    print(f"Active 5-class rows: {len(kept)}")
    for cls in CLASSES:
        print(f"{cls:<19}: train={counts[cls]['dev_train']:4d} val={counts[cls]['dev_val']:4d} test={counts[cls]['dev_test']:4d}")
    print(f"Six-class backup: {archive}")
    print(f"Active mapping: {mapping_file}")
    print(f"Active manifest: {manifest_file}")
    print("Status: DEVELOPMENT ONLY. Old six-class checkpoints remain archived, NOT usable with 5-class mapping.")
    print("IMPORTANT: Do not rerun Step 16; it would restore the six-class files.")
    print("Next: rerun Step 17 --mode smoke, then Step 18 --mode smoke.")


if __name__ == "__main__":
    main()
