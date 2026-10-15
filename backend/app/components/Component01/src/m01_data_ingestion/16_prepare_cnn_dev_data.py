"""Step 16: create a guarded DEVELOPMENT-ONLY image manifest for CNN coding.

This intentionally uses the Step 15 screened/blocked split, NOT the Step 14
split with 276 cross-split White Spot candidate edges. Step 15's severe
White Spot imbalance and unverifiable source identity mean NO FINAL EVALUATION.

Run from any working directory:
    python backend/app/components/Component01/src/m01_data_ingestion/16_prepare_cnn_dev_data.py

Optional:
    .../16_prepare_cnn_dev_data.py --verify-all-images
    .../16_prepare_cnn_dev_data.py --torch-smoke

No images modified; no CNN trained by default. No change to Step 15 files.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import sys

CLASSES = (
    "brown blight", "grey leaf", "healthy", "red rust", "red spider mite", "white spot",
)
ALLOWED_STEP15_STATUSES = {
    "BLOCKED_INSUFFICIENT_INDEPENDENT_EVALUATION_CANDIDATES",
    "SCREENED_PROVISIONAL_NOT_SOURCE_VERIFIED",
}
SPLITS = {"train": "dev_train", "val": "dev_val", "test": "dev_test"}
REQUIRED_MANIFEST_COLUMNS = {
    "class_name", "dataset_source", "relative_path", "sha256", "group_id", "split", "review_status",
}
OUTPUT_COLUMNS = [
    "class_name", "class_index", "dataset_source", "relative_path", "sha256",
    "group_id", "split", "step15_split", "review_status", "usage_restriction",
]


def read_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing prerequisite: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Columns missing in {path.name}: {sorted(missing)}")
        return list(reader)


def safe_relative_path(value: str) -> str:
    raw = value.strip().replace("\\", "/")
    parts = [p for p in raw.split("/") if p and p != "."]
    if not parts or raw.startswith("/") or ":" in raw or ".." in parts:
        raise ValueError(f"Not a safe component-relative image path: {value!r}")
    return "/".join(parts)


def write_csv(path: Path, values: list[dict[str, str]], columns: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(values)


def verify_images(root: Path, rows: list[dict[str, str]], verify_all: bool) -> int:
    """Spot-check one per split/class by default; all files with --verify-all-images."""
    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError("Install Pillow to run image checks: pip install Pillow") from error
    by_bucket: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_bucket[row["class_name"], row["split"]].append(row)
    if verify_all:
        selected = rows
    else:
        # Pick deterministic ends of each class/split bucket for a cheap smoke test.
        selected = []
        for bucket in sorted(by_bucket):
            candidates = sorted(by_bucket[bucket], key=lambda r: r["relative_path"])
            selected.append(candidates[0])
            if len(candidates) > 1:
                selected.append(candidates[-1])
    for row in selected:
        image_path = root / row["relative_path"]
        try:
            with Image.open(image_path) as image:
                image.verify()
        except Exception as error:
            raise ValueError(f"Cannot verify image {row['relative_path']}: {error}") from error
    return len(selected)


def count_step11_crossings(root: Path, source_rows: list[dict[str, str]], step15_report: dict) -> int:
    """Independent recheck of Step 11 relevant similarity edges (incl SHA aliases)."""
    pairs_file = root / "outputs/reports/white_spot_grouping_review_pairs.csv"
    audit_file = root / "outputs/reports/image_audit.csv"
    pairs = read_csv(pairs_file, {"first_path", "second_path"})
    audit = read_csv(audit_file, {"class_name", "relative_path", "sha256"})
    image_by_path = {r["relative_path"]: r for r in source_rows}
    image_by_sha = {r["sha256"].lower(): r for r in source_rows}
    for r in audit:
        aliased = image_by_sha.get(r["sha256"].lower().strip())
        if aliased is not None and aliased["class_name"] == r["class_name"].lower().strip():
            path = safe_relative_path("data/raw/images/" + r["relative_path"])
            image_by_path.setdefault(path, aliased)
    edges = set()
    for pair in pairs:
        a = image_by_path.get(safe_relative_path(pair["first_path"]))
        b = image_by_path.get(safe_relative_path(pair["second_path"]))
        if a is None or b is None or a["sha256"] == b["sha256"]:
            continue  # YOLO crops are purposely excluded, or exact same image
        if a["class_name"] != b["class_name"]:
            raise RuntimeError("Step 11 pair crosses classes: inspect dataset labels")
        edges.add(tuple(sorted((a["sha256"], b["sha256"]))))
        if a["split"] != b["split"]:
            raise RuntimeError("Step 15 has a Step 11 candidate pair across splits; stop")
    reported = step15_report.get("candidate_pairs_between_included_images")
    if reported is not None and len(edges) != reported:
        raise RuntimeError(f"Step 11 included-edge mismatch: reconstructed {len(edges)}, Step 15 recorded {reported}")
    return len(edges)


def prepare(root: Path, verify_all: bool, torch_smoke: bool) -> int:
    root = root.resolve()
    step15_report_file = root / "outputs/reports/image_split_step15_summary.json"
    if not step15_report_file.is_file():
        raise FileNotFoundError("Run Step 15 first: image_split_step15_summary.json missing")
    report = json.loads(step15_report_file.read_text(encoding="utf-8"))
    status = report.get("status")
    if status not in ALLOWED_STEP15_STATUSES:
        raise ValueError(f"Unexpected Step 15 status: {status!r}")
    if report.get("step15_candidate_edges_crossing_splits") != 0:
        raise ValueError("Step 15 reported candidate edges crossing splits. Cannot continue")
    if report.get("white_spot_yolo_crops_included") is not False:
        raise ValueError("Expected White Spot YOLO crops to be excluded")

    source = root / "data/processed" / (
        "image_split_manifest_BLOCKED_DIAGNOSTIC.csv"
        if status.startswith("BLOCKED_")
        else "image_split_manifest_SCREENED.csv"
    )
    records = read_csv(source, REQUIRED_MANIFEST_COLUMNS)
    if not records:
        raise ValueError("Empty Step 15 source manifest")
    seen_paths: set[str] = set()
    sha_split: dict[str, str] = {}
    sha_class: dict[str, str] = {}
    group_split: dict[tuple[str, str], str] = {}
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    prepared: list[dict[str, str]] = []

    for row in records:
        cls = row["class_name"].lower().strip()
        if cls not in CLASSES:
            raise ValueError(f"Unknown class: {cls}")
        rel = safe_relative_path(row["relative_path"])
        if rel in seen_paths:
            raise ValueError(f"Repeated image path: {rel}")
        seen_paths.add(rel)
        image_path = (root / rel).resolve()
        if not image_path.is_relative_to(root) or not image_path.is_file():
            raise FileNotFoundError(f"Missing/unsafe image path: {rel}")
        digest = row["sha256"].lower().strip()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"Invalid SHA256 entry: {rel}")
        split = row["split"].strip().lower()
        if split not in SPLITS:
            raise ValueError(f"Unknown Step 15 split: {split}")
        group = (cls, row["group_id"].strip())
        if not group[1]:
            raise ValueError(f"Missing source group: {rel}")
        if digest in sha_class and sha_class[digest] != cls:
            raise ValueError("Identical image bytes found in different disease classes")
        if digest in sha_split and sha_split[digest] != split:
            raise ValueError("Identical images across splits")
        if group in group_split and group_split[group] != split:
            raise ValueError("Step 15 group crosses splits")
        sha_class[digest], sha_split[digest] = cls, split
        group_split[group] = split
        counts[cls][split] += 1
        cleaned = {
            "class_name": cls, "class_index": str(CLASSES.index(cls)),
            "dataset_source": row["dataset_source"], "relative_path": rel,
            "sha256": digest, "group_id": row["group_id"],
            "split": SPLITS[split], "step15_split": split,
            "review_status": row["review_status"],
            "usage_restriction": "DEVELOPMENT_ONLY_NOT_FOR_FINAL_MODEL_EVALUATION",
        }
        prepared.append(cleaned)
    for cls in CLASSES:
        for split in SPLITS:
            if counts[cls][split] == 0:
                raise ValueError(f"Missing {split} images for {cls}")
    if report.get("files_from_step14") != len(prepared):
        raise ValueError("Manifest row count no longer matches Step 15 report")
    relevant = count_step11_crossings(root, records_normalized(records), report)
    checked = verify_images(root, prepared, verify_all)

    processed = root / "data/processed"
    reports = root / "outputs/reports"
    output_manifest = processed / "image_split_manifest_DEV_ONLY.csv"
    class_mapping = processed / "cnn_class_mapping.json"
    output_report = reports / "image_step16_development_summary.json"
    write_csv(output_manifest, prepared, OUTPUT_COLUMNS)
    class_mapping.write_text(json.dumps({
        "class_to_idx": {label: i for i, label in enumerate(CLASSES)},
        "idx_to_class": {str(i): label for i, label in enumerate(CLASSES)},
        "num_classes": len(CLASSES),
        "image_size": 224,
        "split_names": sorted(SPLITS.values()),
        "status": "DEVELOPMENT_ONLY_NOT_FOR_FINAL_EVALUATION",
    }, indent=2), encoding="utf-8")
    summary = {
        "status": "DEVELOPMENT_ONLY_NOT_FOR_FINAL_EVALUATION",
        "source_step15_status": status,
        "development_training_permitted": True,
        "final_research_evaluation_permitted": False,
        "training_handover_approved": False,
        "total_unique_images": len(prepared),
        "step11_similarity_edges_checked": relevant,
        "step11_similarity_edges_crossing_splits": 0,
        "individual_images_file_presence_checked": len(prepared),
        "image_decoding_checked": checked,
        "all_images_decoding_checked": verify_all,
        "split_counts": {cls: dict(counts[cls]) for cls in CLASSES},
        "manifest": "data/processed/image_split_manifest_DEV_ONLY.csv",
        "class_mapping": "data/processed/cnn_class_mapping.json",
        "white_spot_yolo_crops_included": False,
        "limitations": [
            "White Spot Step 15 has too few evaluation candidates and a giant 130-image similarity component: no reliable final metrics.",
            "Perceptual matching is heuristic; it does not certify independent leaves, plants, field sites or labeling correctness.",
            "Other class source independence and Kaggle healthy background bias remain unverified.",
            "dev_val/dev_test are for code checks only, not publication or final research claims.",
            "Use train-only image augmentation; never augment validation or test inputs.",
            "True independent evaluation requires separately verified/source-grouped data.",
        ],
    }
    reports.mkdir(parents=True, exist_ok=True)
    output_report.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("=" * 72)
    print("STEP 16 - CNN DEVELOPMENT DATA (NOT FINAL EVALUATION)")
    print("=" * 72)
    print(f"Input Step 15 status: {status}")
    print(f"Images: {len(prepared)} | White Spot included | YOLO White Spot excluded")
    print(f"Step 11 similarity edges verified: {relevant}; crossing new splits: 0")
    for cls in CLASSES:
        n = counts[cls]
        print(f"{cls:<20}: dev_train={n['train']:>4} dev_val={n['val']:>4} dev_test={n['test']:>4}")
    print(f"Image files verified open: {checked} | all image files present: {len(prepared)}")
    print(f"Development manifest: {output_manifest}")
    print(f"Class mapping: {class_mapping}")
    print(f"Summary: {output_report}")
    print("WARNING: dev_val and dev_test are NOT trustworthy final model metrics.")
    print("WARNING: This is NOT an approved package for scientific model evaluation.")

    if torch_smoke:
        sys.path.insert(0, str(root / "src"))
        try:
            from m02_disease_detection.cnn_dev_data import build_dev_loaders
        except ImportError as error:
            raise ImportError(
                "For --torch-smoke install torch and torchvision and include cnn_dev_data.py "
                "under src/m02_disease_detection"
            ) from error
        loaders, _ = build_dev_loaders(root, batch_size=4, num_workers=0)
        for name in ("dev_train", "dev_val", "dev_test"):
            images, labels = next(iter(loaders[name]))
            print(f"PyTorch {name}: images={tuple(images.shape)}, labels={tuple(labels.shape)}")
        print("Torch smoke-check passed; no training performed.")
    return 0


def records_normalized(records: list[dict[str, str]]) -> list[dict[str, str]]:
    """Make path matching case-agnostic to slash style without modifying originals."""
    return [{**r, "relative_path": safe_relative_path(r["relative_path"]), "sha256": r["sha256"].lower().strip()} for r in records]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2],
                        help="Optional Component01 root for testing")
    parser.add_argument("--verify-all-images", action="store_true", help="Open/verify every image (slower)")
    parser.add_argument("--torch-smoke", action="store_true", help="Verify one PyTorch batch per split; requires torch/torchvision")
    args = parser.parse_args()
    raise SystemExit(prepare(args.root, args.verify_all_images, args.torch_smoke))
