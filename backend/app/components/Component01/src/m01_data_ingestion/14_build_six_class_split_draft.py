"""Step 14: reproducible six-class image split DRAFT.

Uses audited original images and externally audited TeaLeafBD healthy images.
White Spot YOLO crops remain excluded until quality and provenance are approved.
Splits are proposed only: remaining perceptual/source overlaps need review.
Run from any working directory; paths are resolved relative to this file.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
import csv
import json
import random

from PIL import Image, ImageOps
import imagehash

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "outputs" / "reports"
PROCESSED = ROOT / "data" / "processed"
SOURCE_MANIFEST = PROCESSED / "image_curated_manifest.csv"
ORIGINAL_AUDIT = REPORTS / "image_audit.csv"
HEALTHY_AUDIT = REPORTS / "external_healthy_audit.csv"
REVIEWED_PAIRS = REPORTS / "white_spot_priority_review_queue.csv"
FLAGGED_PAIRS = REPORTS / "white_spot_grouping_review_pairs.csv"
OUTPUT_MANIFEST = PROCESSED / "image_split_manifest_DRAFT.csv"
OUTPUT_REPORT = REPORTS / "image_split_draft_summary.json"
OUTPUT_RISK = REPORTS / "image_split_unresolved_similarity.csv"
SEED = 42
CLASSES = [
    "brown blight", "grey leaf", "healthy", "red rust", "red spider mite", "white spot"
]


def rows(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"Missing prerequisite: {path}")
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def save_csv(path: Path, contents, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(contents)


def file_hash(path: Path):
    h = sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def normalize(value: str):
    return Path(value.replace("\\", "/")).as_posix()


class DSU:
    def __init__(self, size):
        self.parent = list(range(size))

    def find(self, index):
        while self.parent[index] != index:
            self.parent[index] = self.parent[self.parent[index]]
            index = self.parent[index]
        return index

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def main():
    manifest = rows(SOURCE_MANIFEST)
    original = rows(ORIGINAL_AUDIT)
    healthy = rows(HEALTHY_AUDIT)

    hash_lookup = {}
    for r in original:
        key = normalize("data/raw/images/" + r["relative_path"])
        hash_lookup[key] = r["sha256"]
    for r in healthy:
        key = normalize("data/external/tealeafbd/healthy/" + r["filename"])
        hash_lookup[key] = r["sha256"]

    candidates = []
    total_counts = Counter()
    for r in manifest:
        cl = r["class_name"].strip().lower()
        if cl not in CLASSES or r["include_in_training"].lower() != "yes":
            continue
        rel = normalize(r["relative_path"])
        path = ROOT / rel
        if not path.is_file():
            raise FileNotFoundError(f"Manifest references a missing file: {path}")
        if r["status"] == "corrupted":
            continue
        digest = hash_lookup.get(rel) or file_hash(path)
        if not digest:
            raise ValueError(f"No valid SHA256 for {rel}")
        total_counts[cl] += 1
        candidates.append({
            "class_name": cl, "dataset_source": r["dataset_source"],
            "relative_path": rel, "sha256": digest,
        })

    # Guard against the same file being assigned conflicting disease labels.
    hash_classes = defaultdict(set)
    for row in candidates:
        hash_classes[row["sha256"]].add(row["class_name"])
    conflicts = [digest for digest, c in hash_classes.items() if len(c) > 1]
    if conflicts:
        raise ValueError(f"Exact hashes with different classes: {len(conflicts)}; fix labels first")

    # Keep a single representative per class and exact hash without deleting files.
    unique = {}
    for row in sorted(candidates, key=lambda x: (x["class_name"], x["relative_path"])):
        unique.setdefault((row["class_name"], row["sha256"]), row)
    images = list(unique.values())
    if {r["class_name"] for r in images} != set(CLASSES):
        raise ValueError("All six classes must have usable images")

    print("Calculating pHash/dHash on unique image files (may take a few minutes)...")
    for row in images:
        path = ROOT / row["relative_path"]
        with Image.open(path) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            row["phash"] = imagehash.phash(image)
            row["dhash"] = imagehash.dhash(image)

    dsu = DSU(len(images))
    by_class = defaultdict(list)
    by_path = {}
    for i, row in enumerate(images):
        by_class[row["class_name"]].append(i)
        by_path[row["relative_path"]] = i

    # Very close perceptual matches are grouped as a precaution, not deleted.
    heuristic_links = 0
    for cls, indices in by_class.items():
        for i, a in enumerate(indices):
            ra = images[a]
            for b in indices[i + 1:]:
                rb = images[b]
                if ra["phash"] - rb["phash"] <= 4 and ra["dhash"] - rb["dhash"] <= 4:
                    dsu.union(a, b)
                    heuristic_links += 1

    # Apply manual-reviewed same-leaf ties and conservatively group uncertain
    # ties, but only if BOTH images are already approved candidates.
    reviewed_links = Counter()
    if REVIEWED_PAIRS.is_file():
        for r in rows(REVIEWED_PAIRS):
            decision = (r.get("review_decision") or "").strip().lower()
            if decision not in {"same_leaf", "uncertain"}:
                continue
            a = by_path.get(normalize(r.get("first_path", "")))
            b = by_path.get(normalize(r.get("second_path", "")))
            if a is not None and b is not None:
                if images[a]["class_name"] == images[b]["class_name"]:
                    dsu.union(a, b)
                    reviewed_links[decision] += 1

    groups = defaultdict(list)
    for i, r in enumerate(images):
        groups[(r["class_name"], dsu.find(i))].append(i)

    # Reproducible approximate 70/15/15 GROUP-aware split per class.
    # Do not split an inferred same-source group across subsets.
    rng = random.Random(SEED)
    assignments = {}
    class_summary = {}
    for cls in CLASSES:
        these = [g for (name, _), g in groups.items() if name == cls]
        rng.shuffle(these)
        these.sort(key=len, reverse=True)
        total = sum(len(g) for g in these)
        if len(these) < 3:
            raise ValueError(f"Only {len(these)} independent groups for {cls}; cannot create 3 splits")
        targets = {"test": max(1, round(total * .15)), "val": max(1, round(total * .15))}
        allocation = Counter()
        selected = defaultdict(list)
        # Assign small groups first for balanced validation/test samples.
        for g in reversed(these):
            options = [s for s in ("test", "val") if allocation[s] + len(g) <= targets[s]]
            if options:
                s = max(options, key=lambda x: targets[x] - allocation[x])
            else:
                s = "train"
            selected[s].append(g)
            allocation[s] += len(g)
        for s in ("val", "test"):
            if not selected[s]:
                raise ValueError(f"Cannot generate {s} groups for {cls}; review grouping")
        for s, gs in selected.items():
            for g in gs:
                for idx in g:
                    assignments[idx] = s
        class_summary[cls] = {s: allocation[s] for s in ("train", "val", "test")}

    group_ids = {}
    for k, group in sorted(groups.items(), key=lambda item: (item[0][0], min(item[1]))):
        label = k[0].replace(" ", "_")
        group_ids[k] = f"{label}_{min(group):05d}"

    outputs = []
    for i, row in enumerate(images):
        group_key = (row["class_name"], dsu.find(i))
        outputs.append({
            "class_name": row["class_name"],
            "dataset_source": row["dataset_source"],
            "relative_path": row["relative_path"],
            "sha256": row["sha256"],
            "group_id": group_ids[group_key],
            "split": assignments[i],
            "review_status": "DRAFT_SOURCE_GROUPING_NOT_FIELD_VERIFIED",
        })

    # Report similarities that WOULD cross a split if both are included;
    # dHash/pHash are only heuristic and should not silently certify leakage-free.
    risk_rows = []
    if FLAGGED_PAIRS.is_file():
        for pair in rows(FLAGGED_PAIRS):
            a = by_path.get(normalize(pair.get("first_path", "")))
            b = by_path.get(normalize(pair.get("second_path", "")))
            if a is None or b is None:
                continue  # excluded YOLO images should never enter this draft
            if assignments[a] != assignments[b]:
                risk_rows.append({
                    "first_path": images[a]["relative_path"],
                    "second_path": images[b]["relative_path"],
                    "first_split": assignments[a],
                    "second_split": assignments[b],
                    "screening_level": pair.get("screening_level", ""),
                    "phash_distance": pair.get("phash_distance", ""),
                    "dhash_distance": pair.get("dhash_distance", ""),
                    "review_status": pair.get("review_status", "pending"),
                })

    save_csv(OUTPUT_MANIFEST, outputs,
             ["class_name", "dataset_source", "relative_path", "sha256", "group_id", "split", "review_status"])
    save_csv(OUTPUT_RISK, risk_rows,
             ["first_path", "second_path", "first_split", "second_split", "screening_level", "phash_distance", "dhash_distance", "review_status"])

    summary = {
        "status": "DRAFT_NOT_APPROVED_FOR_FINAL_EVALUATION",
        "seed": SEED,
        "candidate_files": len(candidates),
        "exact_unique_images": len(images),
        "extra_exact_duplicate_copies_excluded": len(candidates) - len(images),
        "image_groups": len(groups),
        "heuristic_grouping_links": heuristic_links,
        "reviewed_links_applied": dict(reviewed_links),
        "class_split_counts": class_summary,
        "unresolved_review_pairs_crossing_splits": len(risk_rows),
        "yolo_white_spot_crops": "excluded_pending_crop_quality_and_source_verification",
        "limitation": "Source-level independence cannot be guaranteed without original leaf/plant IDs and additional review.",
    }
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("=" * 65)
    print("STEP 14 - SIX-CLASS IMAGE GROUPED SPLIT DRAFT")
    print("=" * 65)
    print("Candidate files:", len(candidates))
    print("Exact unique files:", len(images))
    print("Groups:", len(groups))
    for cls, counts in class_summary.items():
        print(f"{cls:<20}: train={counts['train']}, val={counts['val']}, test={counts['test']}")
    print("Unresolved flagged pairs across split boundaries:", len(risk_rows))
    print("Draft manifest:", OUTPUT_MANIFEST)
    print("Risk report:", OUTPUT_RISK)
    print("Summary:", OUTPUT_REPORT)
    print("IMPORTANT: DRAFT only. Do not claim fully leakage-free until risk review.")
    print("NO source images modified or deleted.")


if __name__ == "__main__":
    main()
