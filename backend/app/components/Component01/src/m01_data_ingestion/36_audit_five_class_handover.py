"""Step 36. Read-only final DEVELOPMENT dataset handover audit for five-class CNN.

Checks the active Step19 five-class manifest and mapping, exact duplicate/group
split conflicts, all referenced file locations, and optionally file decoding and
on-disk SHA256. Reports unresolved similarity candidates separately.

This cannot certify source/leaf/plant independence, labels, or field performance.
No source files, manifests, checkpoints, or splits are modified.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

CLASSES = ("brown blight", "grey leaf", "healthy", "red rust", "red spider mite")
SPLITS = ("dev_train", "dev_val", "dev_test")
NEEDED = {"class_name", "class_index", "dataset_source", "relative_path", "sha256", "group_id", "split", "usage_restriction"}
DEV_STATUS = "DEVELOPMENT_ONLY_NOT_FOR_FINAL_EVALUATION"
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def fail(message: str):
    raise ValueError(message)


def load_csv(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def secure_relpath(text: str) -> str:
    rel = text.strip().replace("\\", "/")
    parts = rel.split("/")
    if not rel or rel.startswith("/") or ":" in rel or any(p in ("", ".", "..") for p in parts):
        fail(f"Unsafe/malformed relative file path: {text!r}")
    return rel


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def evaluate(root: Path, verify_all_images: bool = False, hash_all: bool = False) -> dict:
    root = root.resolve()
    manifest_path = root / "data/processed/image_split_manifest_DEV_ONLY.csv"
    mapping_path = root / "data/processed/cnn_class_mapping.json"
    summary_path = root / "outputs/reports/image_step16_development_summary.json"
    rows = load_csv(manifest_path)
    for path in (mapping_path, summary_path):
        if not path.is_file():
            raise FileNotFoundError(f"Prerequisite missing: {path}")
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    existing_summary = json.loads(summary_path.read_text(encoding="utf-8"))

    if not rows:
        fail("Empty active image manifest")
    if not NEEDED.issubset(rows[0]):
        fail(f"Missing manifest fields: {sorted(NEEDED - set(rows[0]))}")
    expected_mapping = {name: i for i, name in enumerate(CLASSES)}
    if (mapping.get("num_classes") != 5
            or mapping.get("class_to_idx") != expected_mapping
            or mapping.get("idx_to_class") != {str(i): c for c, i in expected_mapping.items()}
            or mapping.get("status") != DEV_STATUS):
        fail("Active mapping is not the expected Step19 five-class development mapping")
    if (existing_summary.get("prototype_num_classes") != 5
            or existing_summary.get("total_unique_images") != len(rows)
            or existing_summary.get("white_spot_deferred") is not True
            or existing_summary.get("final_research_evaluation_permitted") is not False):
        fail("Step19 development summary does not match active manifest/mapping")

    by_class_split = defaultdict(Counter)
    seen_paths = set()
    seen_sha = {}
    group_splits = {}
    image_paths = {}
    for row in rows:
        cls = row["class_name"].strip().lower()
        split = row["split"].strip()
        rel = secure_relpath(row["relative_path"])
        digest = row["sha256"].strip().lower()
        group = row["group_id"].strip()
        if cls not in CLASSES or split not in SPLITS:
            fail(f"Unexpected class/split at {rel}: {cls!r}, {split!r}")
        if row["class_index"].strip() != str(expected_mapping[cls]):
            fail(f"Class index mismatch at {rel}")
        if "DEVELOPMENT_ONLY" not in row["usage_restriction"]:
            fail(f"Development-only restriction missing at {rel}")
        if not group:
            fail(f"Missing grouping ID at {rel}")
        if not SHA256_PATTERN.fullmatch(digest):
            fail(f"Invalid SHA256 in manifest for {rel}")
        if rel in seen_paths:
            fail(f"Repeated file path: {rel}")
        if digest in seen_sha:
            fail(f"Exact duplicate SHA256 remains in active unique manifest: {rel}, {seen_sha[digest]}")
        seen_paths.add(rel)
        seen_sha[digest] = rel
        key = (cls, group)
        if key in group_splits and group_splits[key] != split:
            fail(f"Group crosses splits: class={cls} group={group}")
        group_splits[key] = split
        absolute = (root / rel).resolve()
        if not absolute.is_relative_to(root) or not absolute.is_file():
            raise FileNotFoundError(f"Missing or outside-component image: {rel}")
        image_paths[rel] = absolute
        by_class_split[cls][split] += 1

    for cls in CLASSES:
        for split in SPLITS:
            if by_class_split[cls][split] < 1:
                fail(f"Class/split has no images: {cls}/{split}")

    # Deterministically check at least two file decodes per disease/split.
    sample = []
    if verify_all_images:
        sample = rows
    else:
        buckets = defaultdict(list)
        for row in rows:
            buckets[(row["class_name"], row["split"])].append(row)
        for bucket in sorted(buckets):
            members = sorted(buckets[bucket], key=lambda r: r["relative_path"])
            sample.append(members[0])
            if len(members) > 1:
                sample.append(members[-1])

    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required: python -m pip install pillow") from exc
    for row in sample:
        rel = secure_relpath(row["relative_path"])
        with Image.open(image_paths[rel]) as im:
            im.verify()
    if hash_all:
        for row in rows:
            rel = secure_relpath(row["relative_path"])
            if sha256(image_paths[rel]) != row["sha256"].strip().lower():
                fail(f"Image SHA256 differs from source manifest: {rel}")

    # Optional heuristic review candidates from the OLD Step14 draft report.
    # Only score pairs where both files are in the current five-class manifest,
    # against their CURRENT split assignments, not old draft assignments.
    risk_path = root / "outputs/reports/image_split_unresolved_similarity.csv"
    current_split = {row["relative_path"].replace("\\", "/"): row["split"] for row in rows}
    active_risks = set()
    if risk_path.is_file():
        risks = load_csv(risk_path)
        for item in risks:
            a = item.get("first_path", "").replace("\\", "/")
            b = item.get("second_path", "").replace("\\", "/")
            if a in current_split and b in current_split and current_split[a] != current_split[b]:
                active_risks.add(tuple(sorted((a, b))))

    active_counts = {cls: {split: by_class_split[cls][split] for split in SPLITS} for cls in CLASSES}
    return {
        "audit_status": "PASS_DEVELOPMENT_ONLY_WITH_LIMITATIONS",
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "active_class_names": list(CLASSES),
        "total_images": len(rows),
        "split_totals": {split: sum(by_class_split[c][split] for c in CLASSES) for split in SPLITS},
        "class_split_counts": active_counts,
        "unique_sha256_in_manifest": len(seen_sha),
        "unique_source_group_ids_scoped_by_class": len(group_splits),
        "all_file_paths_verified": len(image_paths),
        "image_files_decode_checked": len(sample),
        "recomputed_all_image_sha256": hash_all,
        "heuristic_cross_split_review_candidates_from_old_draft": len(active_risks),
        "source_independent_holdout_verified": False,
        "final_research_evaluation_permitted": False,
        "white_spot_deferred": True,
        "limitations": [
            "This audit checks manifest integrity and local files, not leaf/plant/source independence.",
            "Potential near-duplicates and source/background bias require expert/source review.",
            "The original Step14 similarity report is heuristic; any remaining candidate pairs are not confirmed duplicates.",
            "Five-class labels and evaluation are development-only, not field-validated scientific performance.",
            "White Spot was deferred; do not claim six-class diagnosis.",
        ],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--verify-all-images", action="store_true", help="Decode/verify every active image")
    ap.add_argument("--hash-all", action="store_true", help="Recalculate on-disk SHA256 for every active image")
    args = ap.parse_args()
    root = args.root.resolve()
    result = evaluate(root, args.verify_all_images, args.hash_all)
    dest = root / "outputs/reports/step36_m01_five_class_audit.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("=" * 73)
    print("STEP 36 - m01 FIVE-CLASS CNN DATA HANDOVER AUDIT (DEV ONLY)")
    print("=" * 73)
    print(f"Images={result['total_images']} | Classes=5 | Exact SHA duplicates=0 | Group cross-split conflicts=0")
    print(f"Split totals: {result['split_totals']}")
    for cls, counts in result["class_split_counts"].items():
        print(f"  {cls:<19} train={counts['dev_train']:4d} val={counts['dev_val']:3d} test={counts['dev_test']:3d}")
    print(f"All files present={result['all_file_paths_verified']} | Pillow verified={result['image_files_decode_checked']}")
    print(f"Heuristic cross-split review candidates (old Step14 report): {result['heuristic_cross_split_review_candidates_from_old_draft']}")
    print(f"Status: {result['audit_status']}")
    print(f"Report: {dest}")
    print("WARNING: Source-independent final test NOT verified; results are development-only.")
    print("NO input files, images, splits or models modified.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError, RuntimeError, OSError) as exc:
        print(f"AUDIT FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
