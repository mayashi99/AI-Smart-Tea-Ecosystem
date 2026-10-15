r"""Step 18: Check Step 17 checkpoint can load and predict one image.

From repository root (PowerShell):
 python backend\app\components\Component01\src\m02_disease_detection\18_verify_cnn_inference.py --mode smoke

Use --mode predict --image <absolute-or-Component01-relative-image> [--checkpoint ...]
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import uuid

from cnn_inference import CNNPredictor, component_root, locate_latest_dev_checkpoint


def first_train_sample(root: Path) -> Path:
    csv_path = root / "data/processed/image_split_manifest_DEV_ONLY.csv"
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for item in csv.DictReader(f):
            if item.get("split") == "dev_train":
                return root / item["relative_path"]
    raise ValueError("Could not locate a dev_train image in Step 16 manifest")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("smoke", "predict"), default="smoke")
    parser.add_argument("--checkpoint", default=None,
                        help="Optional Step17 .pt file; otherwise latest Step17 dev checkpoint")
    parser.add_argument("--image", default=None,
                        help="Required for --mode predict. Absolute or Component01-relative path")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    root = component_root()
    if args.mode == "predict" and not args.image:
        parser.error("--image is required for --mode predict")
    if args.mode == "smoke" and args.image:
        parser.error("--image can be specified only with --mode predict")
    checkpoint = args.checkpoint or locate_latest_dev_checkpoint(root)
    predictor = CNNPredictor.from_step17_checkpoint(checkpoint, root=root, device=args.device)
    image = first_train_sample(root) if args.mode == "smoke" else Path(args.image)
    if not image.is_absolute():
        image = root / image
    result = predictor.predict(image, top_k=args.top_k)
    result["mode"] = args.mode
    report_dir = root / "outputs/reports/cnn_inference_checks"
    report_dir.mkdir(parents=True, exist_ok=True)
    name = f"step18_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.json"
    report_file = report_dir / name
    report_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("=" * 72)
    print("STEP 18 - CNN CHECKPOINT / INFERENCE CHECK (DEVELOPMENT ONLY)")
    print("=" * 72)
    print(f"Loaded architecture: {result['architecture']}")
    print(f"Device: {predictor.device}")
    print(f"Image: {result['image']}")
    print(f"Prediction (SMOKE ONLY, NOT A VALIDATED DIAGNOSIS): {result['predicted_class']}")
    for item in result["top_k"]:
        print(f"  {item['class_name']:<18} | uncalibrated softmax={item['softmax_score']:.4f}")
    print(f"Saved result: {report_file}")
    print("PASS: checkpoint loaded, preprocessing applied, prediction produced.")
    print("WARNING: This result does not validate model accuracy or research evaluation.")


if __name__ == "__main__":
    main()
