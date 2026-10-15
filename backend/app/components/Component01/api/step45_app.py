"""Step 45 — Step43 FastAPI + five-class Step44 upload/Grad-CAM++ endpoints.

Keeps Step43's forecast/observation routes unmodified. All CNN outputs are
DEVELOPMENT-ONLY until a separately evaluated compatible checkpoint exists.
"""
from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

from fastapi import File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

# Import normally so Pydantic v2 can resolve Step43's request types.
from step43_app import app

ROOT = Path(__file__).resolve().parents[1]
XAI_DIR = ROOT / 'src' / 'm05_explainability_alerts'
if str(XAI_DIR) not in sys.path:
    sys.path.insert(0, str(XAI_DIR))
from gradcam_plus_plus import explain_leaf_image  # noqa: E402

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 16_000_000
ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.webp'}
ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP'}
ASSET_DIR = ROOT / 'outputs/dashboard/m05/image_explanations'
ASSET_RE = re.compile(r'step44_\d{8}T\d{6}Z_[a-f0-9]{8}_(?:overlay|heatmap)\.png\Z')


def _checkpoint():
    """Optional server operator override. Never accept a checkpoint from web clients."""
    raw = os.environ.get('TEA_CNN_CHECKPOINT', '').strip()
    return raw if raw else None


def _active_checkpoint_metadata():
    """Read server-selected checkpoint without accepting model paths from clients."""
    try:
        from cnn_inference import locate_latest_dev_checkpoint
    except ImportError:
        cnn_dir = ROOT / 'src' / 'm02_disease_detection'
        if str(cnn_dir) not in sys.path:
            sys.path.insert(0, str(cnn_dir))
        from cnn_inference import locate_latest_dev_checkpoint
    try:
        override = _checkpoint()
        file = (Path(override) if Path(override).is_absolute() else ROOT / override) if override else locate_latest_dev_checkpoint(ROOT)
        import torch
        payload = torch.load(file, map_location='cpu', weights_only=True)
        stage = payload.get('step47_stage', '')
        mode = payload.get('training_mode', 'smoke')
        return {
            'checkpoint': str(file),
            'training_mode': mode,
            'architecture': payload.get('model_architecture'),
            'development_trained': stage in {'benchmark', 'finetune'} or mode == 'full',
            'step47_stage': stage,
        }
    except (FileNotFoundError, ValueError, RuntimeError, KeyError, OSError):
        return {'checkpoint': None, 'training_mode': None, 'architecture': None,
                'development_trained': False, 'step47_stage': None}


def _require_valid_image(data: bytes, suffix: str) -> None:
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f'Image must contain 1..{MAX_UPLOAD_BYTES} bytes')
    if suffix.lower() not in ALLOWED_EXT:
        raise HTTPException(422, 'Upload a .jpg, .jpeg, .png or .webp image')
    try:
        with Image.open(BytesIO(data)) as im:
            if im.format not in ALLOWED_FORMATS:
                raise HTTPException(422, 'Unsupported image format')
            if im.width < 32 or im.height < 32 or im.width * im.height > MAX_PIXELS:
                raise HTTPException(422, 'Image dimensions must be >=32 px and <=16 million pixels')
            im.verify()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, 'Invalid or corrupt image data') from exc


@app.get('/api/image/status', tags=['Image CNN (development only)'])
def image_status():
    checkpoints = list((ROOT / 'models/image/development_only').glob('step17_*/*_best_dev_only.pt'))
    required_files = {
        'step44_gradcam_script': (XAI_DIR / 'gradcam_plus_plus.py').is_file(),
        'cnn_inference_script': (ROOT / 'src/m02_disease_detection/cnn_inference.py').is_file(),
        'class_mapping': (ROOT / 'data/processed/cnn_class_mapping.json').is_file(),
    }
    override = _checkpoint()
    checkpoint_present = (Path(override).is_file() if override and Path(override).is_absolute()
                          else (ROOT / override).is_file() if override else bool(checkpoints))
    meta = _active_checkpoint_metadata() if checkpoint_present else {'development_trained': False, 'architecture': None}
    development_trained = meta['development_trained']
    return {
        'image_api_available': all(required_files.values()) and checkpoint_present,
        'requirements_present': required_files,
        'checkpoint_present': checkpoint_present,
        'model_checkpoint_status': ('DEVELOPMENT_TRAINED_NOT_FIELD_VALIDATED' if development_trained
                                    else 'DEVELOPMENT_ONLY_SMOKE_UNVALIDATED'),
        'development_cnn_training_completed': development_trained,
        'model_architecture': meta.get('architecture'),
        'full_cnn_training_completed': False,  # Final independent source/field validation NOT completed.
        'forecast_api_still_available': True,
        'warning': ('Checkpoint trained on development images, NOT source-independent/field validated.'
                    if development_trained else 'Smoke checkpoint is for technical demonstration, not field diagnosis.'),
    }


@app.post('/api/image/analyze', tags=['Image CNN (development only)'])
async def image_analyze(
    file: UploadFile = File(..., description='Tea-leaf photo: JPEG, PNG or WEBP, <=8 MiB'),
    target_class: str | None = Form(None, description='Optional explained class among the five active classes'),
):
    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in ALLOWED_EXT:
        raise HTTPException(422, 'Image filename must end with .jpg, .jpeg, .png or .webp')
    if file.content_type not in {'image/jpeg', 'image/png', 'image/webp', 'application/octet-stream'}:
        raise HTTPException(422, 'Invalid image content type')
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    _require_valid_image(data, suffix)

    # Only a transient input file is written; output heatmap/overlay are saved
    # independently. This does not modify training data or officer CSV files.
    with TemporaryDirectory(prefix='tea_leaf_step45_') as tmp:
        candidate = Path(tmp) / f'upload{suffix}'
        candidate.write_bytes(data)
        try:
            result = await run_in_threadpool(
                explain_leaf_image, candidate, checkpoint=_checkpoint(),
                root=ROOT, target_class=target_class, device='cpu', output_dir=ASSET_DIR,
            )
        except ValueError as exc:
            # Only target-class input problems are returned as 422.
            if target_class and ('Unknown target class' in str(exc)):
                raise HTTPException(422, str(exc)) from exc
            raise HTTPException(503, 'CNN development checkpoint/format mismatch') from exc
        except (FileNotFoundError, ImportError, RuntimeError, KeyError, OSError) as exc:
            raise HTTPException(503, f'CNN pipeline not available: {type(exc).__name__}') from exc

    def url_for_asset(key: str) -> str:
        path = Path(result[key]).resolve()
        if path.parent != ASSET_DIR.resolve() or not ASSET_RE.fullmatch(path.name):
            raise HTTPException(503, 'Unexpected image output path')
        return f'/api/image/artifacts/{path.name}'

    dev_trained = result.get('training_mode') == 'full'
    return {
        'mode': 'DEVELOPMENT_ONLY_CNN_GRADCAM_PP',
        'predicted_class': result['predicted_class'],
        'explained_class': result['explained_class'],
        'class_names': result['class_names'],
        'top_k': result['top_k'],
        'uncalibrated_softmax_score': result['uncalibrated_softmax_score'],
        'image_width': result['image_width'],
        'image_height': result['image_height'],
        'heatmap_signal_present': result['heatmap_signal_present'],
        'heatmap_url': url_for_asset('heatmap_png'),
        'overlay_url': url_for_asset('overlay_png'),
        'is_leaf_lesion_segmentation': False,
        'is_leaf_area_severity_percentage': False,
        'is_disease_diagnosis_verified': False,
        'full_cnn_training_completed': False,  # No independent field validation.
        'development_cnn_training_completed': dev_trained,
        'simulation_only': True,
        'warning': ('Development-trained CNN; Grad-CAM++ is attribution, not validated diagnosis or lesion severity.'
                    if dev_trained else 'Random/smoke CNN; not validated diagnosis or lesion severity.'),
    }


@app.get('/api/image/artifacts/{filename}', tags=['Image CNN (development only)'])
def image_artifact(filename: str):
    if not ASSET_RE.fullmatch(filename):
        raise HTTPException(404, 'Image output not found')
    image_path = ASSET_DIR / filename
    if not image_path.is_file():
        raise HTTPException(404, 'Image output not found')
    return FileResponse(image_path, media_type='image/png', headers={'Cache-Control': 'no-store'})
