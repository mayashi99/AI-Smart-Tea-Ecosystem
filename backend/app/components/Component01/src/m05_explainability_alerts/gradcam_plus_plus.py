"""Step 47 extends Step 44 Grad-CAM++ to three compatible torchvision CNN architectures.

This highlights locations contributing to a selected CNN class logit. It is
NOT lesion segmentation, a lesion-severity percentage, diagnostic evidence,
or proof of CNN prediction accuracy. Uses Step 19's validated five-class
checkpoint through the existing cnn_inference.CNNPredictor interface.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import uuid

import cv2
import numpy as np
from PIL import Image, ImageOps
import torch
import torch.nn.functional as F


def component_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _cnn_loader(root: Path):
    # Numerical script names prevent package import; import public reusable module.
    folder = root / 'src' / 'm02_disease_detection'
    if not (folder / 'cnn_inference.py').is_file():
        raise FileNotFoundError(f'Missing existing CNN inference module: {folder}')
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
    from cnn_inference import CNNPredictor, locate_latest_dev_checkpoint
    return CNNPredictor, locate_latest_dev_checkpoint


def choose_target(class_names: list[str], selector: str | int | None, predicted_idx: int) -> int:
    if selector is None:
        return predicted_idx
    if isinstance(selector, int) and not isinstance(selector, bool):
        if 0 <= selector < len(class_names):
            return selector
        raise ValueError(f'Target class index must be between 0 and {len(class_names)-1}')
    if isinstance(selector, str):
        matches = [i for i, name in enumerate(class_names) if name.casefold() == selector.strip().casefold()]
        if len(matches) == 1:
            return matches[0]
    raise ValueError(f'Unknown target class {selector!r}; use one of {class_names}')


def compute_gradcam_pp(model: torch.nn.Module, normalized_tensor: torch.Tensor,
                       *, target_idx: int, target_layer: torch.nn.Module) -> tuple[np.ndarray, torch.Tensor]:
    """Grad-CAM++ channel weighting with positive gradients, evaluated on raw logit.

    Uses standard gradient-power weighting approximation: a_ij^k =
    (dY/dA_ij^k)^2 / (2(dY/dA)^2 + (sum_ij A_ij^k)(dY/dA)^3 + eps).
    Only nonnegative gradients contribute to channel weights.
    """
    captured: list[torch.Tensor] = []
    hook = target_layer.register_forward_hook(lambda _layer, _inputs, output: captured.append(output))
    try:
        model.eval()
        with torch.enable_grad():
            # Do NOT use torch.inference_mode/no_grad here; a CAM requires gradients.
            logits = model(normalized_tensor)
            if logits.ndim != 2 or logits.size(0) != 1 or not (0 <= target_idx < logits.size(1)):
                raise ValueError('Unexpected CNN output dimensions or class index')
            if len(captured) != 1 or captured[0].ndim != 4:
                raise RuntimeError('Target layer must produce one [N,C,H,W] activation tensor')
            activations = captured[0]
            gradients = torch.autograd.grad(logits[0, target_idx], activations,
                                            retain_graph=False, create_graph=False)[0]
            if not torch.isfinite(activations).all() or not torch.isfinite(gradients).all():
                raise RuntimeError('Non-finite activations or gradients')

            # Float64 powers improve numerical behavior with small gradient magnitudes.
            grad = gradients.detach().to(torch.float64)
            act = activations.detach().to(torch.float64)
            grad2 = grad.pow(2)
            grad3 = grad2 * grad
            sum_act = act.sum(dim=(2, 3), keepdim=True)
            denominator = 2.0 * grad2 + sum_act * grad3
            eps = 1e-12
            alpha = torch.where(
                (grad > 0) & (denominator > eps),
                grad2 / denominator.clamp_min(eps),
                torch.zeros_like(grad2),
            )
            weights = (alpha * grad.clamp_min(0)).sum(dim=(2, 3), keepdim=True)
            cam = (weights * act).sum(dim=1, keepdim=True).clamp_min(0)
            cam = F.interpolate(cam.float(), size=normalized_tensor.shape[-2:],
                                mode='bilinear', align_corners=False)
            heat = cam[0, 0].cpu().numpy()
            high = float(np.max(heat))
            low = float(np.min(heat))
            if high - low > 1e-12:
                heat = (heat - low) / (high - low)
            else:
                heat = np.zeros_like(heat)
            if not np.isfinite(heat).all():
                raise RuntimeError('Non-finite Grad-CAM++ heatmap')
            return heat.astype(np.float32), logits.detach().cpu()
    finally:
        hook.remove()


def explain_leaf_image(image: str | Path, *, checkpoint: str | Path | None = None,
                       target_class: str | int | None = None, device: str = 'auto',
                       root: Path | None = None, output_dir: str | Path | None = None,
                       overlay_alpha: float = 0.45) -> dict:
    root = (root or component_root()).resolve()
    if not (0.0 <= overlay_alpha <= 1.0):
        raise ValueError('overlay_alpha must be between 0 and 1')
    CNNPredictor, locate_latest = _cnn_loader(root)
    checkpoint_file = checkpoint or locate_latest(root)
    predictor = CNNPredictor.from_step17_checkpoint(checkpoint_file, root=root, device=device)
    arch = predictor.checkpoint_info['model_architecture']
    if arch not in {'mobilenet_v3_small', 'resnet18', 'efficientnet_b0'}:
        raise ValueError('Unsupported Step47 architecture for Grad-CAM++: ' + str(arch))
    file = Path(image)
    if not file.is_absolute():
        file = root / file
    file = file.resolve()
    if not file.is_file():
        raise FileNotFoundError(f'Image does not exist: {file}')
    with Image.open(file) as source:
        rgb = ImageOps.exif_transpose(source).convert('RGB')
        rgb.load()
    model_input = predictor.transform(rgb).unsqueeze(0).to(predictor.device)

    # First forward pass chooses predicted class without building a graph.
    with torch.no_grad():
        logits_0 = predictor.model(model_input)
    predicted_idx = int(logits_0.argmax(dim=1).item())
    idx = choose_target(predictor.classes, target_class, predicted_idx)
    # Run separate differentiable pass for selected class explanation.
    layer = (predictor.model.layer4[-1] if arch == 'resnet18'
             else predictor.model.features[-1])
    heat, logits = compute_gradcam_pp(predictor.model, model_input,
                                      target_idx=idx, target_layer=layer)
    scores = torch.softmax(logits[0], dim=0).numpy()
    rank = np.argsort(-scores)

    output = Path(output_dir) if output_dir else root / 'outputs/dashboard/m05/image_explanations'
    if not output.is_absolute():
        output = root / output
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    run_name = f'step44_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:8]}'
    heat_img = Image.fromarray(np.uint8(np.clip(heat, 0, 1) * 255), 'L')
    heat_original = heat_img.resize(rgb.size, Image.Resampling.BILINEAR)
    heat_u8 = np.asarray(heat_original)
    bgr = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
    colored = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    original = np.asarray(rgb, dtype=np.float32)
    overlaid = np.uint8(np.clip((1.0 - overlay_alpha) * original + overlay_alpha * colored, 0, 255))
    heat_path, overlay_path, report_path = (
        output / f'{run_name}_heatmap.png', output / f'{run_name}_overlay.png', output / f'{run_name}_metadata.json')
    heat_original.save(heat_path)
    Image.fromarray(overlaid, 'RGB').save(overlay_path)
    sha = hashlib.sha256(file.read_bytes()).hexdigest()
    report = {
        'schema_version': 'step44-gradcam-pp-v1',
        'method': 'Grad-CAM++ gradient-power weighting on target class logit',
        'input_image': str(file),
        'input_sha256': sha,
        'image_width': rgb.width,
        'image_height': rgb.height,
        'checkpoint': str(predictor.checkpoint_path),
        'architecture': arch,
        'training_mode': predictor.checkpoint_info.get('training_mode'),
        'class_names': predictor.classes,
        'predicted_class': predictor.classes[predicted_idx],
        'explained_class': predictor.classes[idx],
        'explained_class_index': idx,
        'uncalibrated_softmax_score': round(float(scores[idx]), 6),
        'top_k': [{'class_name': predictor.classes[int(j)], 'softmax_score': round(float(scores[j]), 6)} for j in rank[:3]],
        'heatmap_signal_present': bool(heat.max() > 0),
        'heatmap_png': str(heat_path),
        'overlay_png': str(overlay_path),
        'model_checkpoint_development_only': True,
        'scientific_status': 'DEVELOPMENT_ONLY_NOT_FIELD_VALIDATED',
        'is_leaf_lesion_segmentation': False,
        'is_leaf_area_severity_percentage': False,
        'is_disease_diagnosis_verified': False,
        'warning': ('Explanation shows model-influential pixels, NOT verified lesion regions, field accuracy or severity. '
                    + ('Smoke weights are random and untrained.' if predictor.checkpoint_info.get('training_mode') == 'smoke'
                       else 'Model training on development images does not establish field accuracy.')),
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    report['metadata_json'] = str(report_path)
    return report
