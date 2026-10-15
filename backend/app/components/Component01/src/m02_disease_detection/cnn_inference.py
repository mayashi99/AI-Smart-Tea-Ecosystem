"""Step 18. Reusable inference for Step 17 development-only CNN checkpoints.

Strictly smoke/integration development. Does NOT certify accuracy or deployment.
Uses checkpoint architecture, class order and normalization saved during training.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

import torch
from PIL import Image, ImageOps
from torchvision import transforms

ARCHITECTURES = {
    "mobilenet_v3_small", "efficientnet_b0", "resnet18", "densenet121"
}
DEV_STATUS = "DEVELOPMENT_ONLY_NOT_FOR_FINAL_EVALUATION"


def component_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _training_module():
    """Use exact same model constructors as Step 17 (numerical filename)."""
    script = Path(__file__).with_name("17_train_cnn_dev.py")
    if not script.is_file():
        raise FileNotFoundError(f"Missing Step 17 model definitions: {script}")
    spec = importlib.util.spec_from_file_location("cnn_step17_training", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot import Step 17 training architecture")
    folder = str(script.parent)
    if folder not in sys.path:
        sys.path.insert(0, folder)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def locate_latest_dev_checkpoint(root: Path) -> Path:
    model_root = root / "models" / "image" / "development_only"
    paths = sorted(model_root.glob("step17_*/*_best_dev_only.pt"),
                   key=lambda p: (p.stat().st_mtime_ns, p.as_posix()), reverse=True)
    mapping_file = root / "data/processed/cnn_class_mapping.json"
    manifest_file = root / "data/processed/image_split_manifest_DEV_ONLY.csv"
    if not mapping_file.is_file() or not manifest_file.is_file():
        raise FileNotFoundError("Missing active five-class mapping or manifest; run Step 19")
    mapping = json.loads(mapping_file.read_text(encoding="utf-8"))
    if mapping.get("num_classes") != 5:
        raise ValueError("Active mapping is not five-class; run Step 19")
    manifest_sha = hashlib.sha256(manifest_file.read_bytes()).hexdigest()
    for path in paths:
        # Older six-class smoke checkpoints must not be selected accidentally.
        payload = torch.load(path, map_location="cpu", weights_only=True)
        if (isinstance(payload, dict) and payload.get("num_classes") == 5
                and payload.get("class_to_idx") == mapping.get("class_to_idx")
                and payload.get("manifest_sha256") == manifest_sha):
            return path
    raise FileNotFoundError(
        "No compatible five-class checkpoint. Run Step 17 --mode smoke AFTER Step 19."
    )


@dataclass
class CNNPredictor:
    model: torch.nn.Module
    classes: list[str]
    transform: transforms.Compose
    device: torch.device
    checkpoint_path: Path
    checkpoint_info: dict

    @classmethod
    def from_step17_checkpoint(cls, checkpoint: Path | str,
                               *, root: Path | None = None,
                               device: str = "auto") -> "CNNPredictor":
        root = (Path(root) if root is not None else component_root()).resolve()
        file = Path(checkpoint)
        if not file.is_absolute():
            file = root / file
        file = file.resolve()
        if not file.is_file():
            raise FileNotFoundError(f"Checkpoint does not exist: {file}")
        if device not in {"cpu", "cuda", "auto"}:
            raise ValueError("Device must be cpu, cuda, or auto")
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested, but CUDA is not available")
        selected = torch.device("cuda" if device == "cuda" or
                                (device == "auto" and torch.cuda.is_available())
                                else "cpu")
        # weights_only=True avoids arbitrary Python pickle objects in checkpoints.
        payload = torch.load(file, map_location="cpu", weights_only=True)
        if not isinstance(payload, dict):
            raise ValueError("Expected Step 17 checkpoint dictionary")
        if payload.get("dataset_status") != DEV_STATUS or payload.get("final_research_evaluation_permitted") is not False:
            raise ValueError("This tool accepts only Step 17 development-only checkpoints")
        architecture = payload.get("model_architecture")
        if architecture not in ARCHITECTURES:
            raise ValueError(f"Unknown/unapproved architecture in checkpoint: {architecture}")
        classes = payload.get("class_names")
        if not isinstance(classes, list) or len(classes) != 5 or len(set(classes)) != 5 or not all(isinstance(c,str) and c for c in classes):
            raise ValueError("Checkpoint must contain five distinct class labels")
        if payload.get("num_classes") != len(classes):
            raise ValueError("Invalid checkpoint num_classes")
        mapping_path = root / "data" / "processed" / "cnn_class_mapping.json"
        if not mapping_path.is_file():
            raise FileNotFoundError(f"Missing class mapping file: {mapping_path}")
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        if (mapping.get("status") != DEV_STATUS
                or mapping.get("num_classes") != 5
                or [mapping["idx_to_class"][str(i)] for i in range(5)] != classes
                or mapping.get("class_to_idx") != payload.get("class_to_idx")):
            raise ValueError("Saved CNN class mapping differs from checkpoint")
        manifest_path = root / "data/processed/image_split_manifest_DEV_ONLY.csv"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Missing development manifest: {manifest_path}")
        if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != payload.get("manifest_sha256"):
            raise ValueError("Dataset manifest checksum differs from training checkpoint")
        norm = payload.get("normalization")
        if not isinstance(norm,dict) or len(norm.get("mean",[])) != 3 or len(norm.get("std",[])) != 3:
            raise ValueError("Checkpoint missing RGB normalization")
        if any((not isinstance(x,(int,float)) or x <= 0) for x in norm["std"]):
            raise ValueError("Invalid normalization std")
        image_size = payload.get("image_size")
        if not isinstance(image_size,int) or not (32 <= image_size <= 1024):
            raise ValueError("Invalid image_size")
        make_model = _training_module().make_model
        model = make_model(architecture, num_classes=len(classes), pretrained=False)
        model.load_state_dict(payload["model_state_dict"], strict=True)
        model = model.to(selected).eval()
        transform = transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=norm["mean"], std=norm["std"]),
        ])
        return cls(model, classes, transform, selected, file,
                   {k:payload.get(k) for k in (
                       "model_architecture", "epoch", "training_mode", "training_weights",
                       "dev_val_macro_f1", "manifest_sha256", "dataset_status",
                   )})

    @torch.inference_mode()
    def predict(self, image: Path | str, *, top_k: int = 3) -> dict:
        if not (1 <= top_k <= len(self.classes)):
            raise ValueError(f"top_k must be 1..{len(self.classes)}")
        file = Path(image).resolve()
        if not file.is_file():
            raise FileNotFoundError(f"Image not found: {file}")
        with Image.open(file) as picture:
            rgb = ImageOps.exif_transpose(picture).convert("RGB")
            tensor = self.transform(rgb).unsqueeze(0).to(self.device)
        logits = self.model(tensor)
        probs = torch.softmax(logits, dim=1).squeeze(0).cpu()
        indices = torch.argsort(probs, descending=True)[:top_k].tolist()
        return {
            "scientific_status": "DEVELOPMENT_ONLY_NOT_VALIDATED_FOR_CLINICAL_OR_FIELD_USE",
            "image": str(file),
            "checkpoint": str(self.checkpoint_path),
            "architecture": self.checkpoint_info["model_architecture"],
            "predicted_class": self.classes[indices[0]],
            "score_type": "uncalibrated_softmax_not_a_validated_confidence",
            "top_k": [{"class_name": self.classes[idx], "softmax_score": round(float(probs[idx]), 6)}
                      for idx in indices],
        }
