"""m03 Step39 - reusable incidence + leaf pixel-area SEVERITY PROTOTYPE.

Manual masks are geometric pixel measurements, not validated agronomic ground truth.
Automatic masks are unvalidated computer-vision proposals, NOT labelled lesions.
Does not use Grad-CAM as a lesion mask or pretend source-independent validity.
"""
from __future__ import annotations

import io
import re
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

DISEASES = ('Brown Blight', 'Grey Leaf', 'Red Rust', 'Red Spider Mite')
MAX_IMAGE_PIXELS = 16_000_000
MAX_BYTES = 25_000_000


def _validate_image(data: bytes) -> np.ndarray:
    if not data or len(data) > MAX_BYTES:
        raise ValueError('Image empty or exceeds 25MB safety limit.')
    try:
        with Image.open(io.BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ValueError('Image exceeds 16 million pixels; resize first.')
            image.load()
            return np.asarray(image.convert('RGB')).copy()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError('Could not decode image using Pillow.') from exc


def _mask_from_image(data: bytes, shape: tuple[int, int]) -> np.ndarray:
    if not data or len(data) > MAX_BYTES:
        raise ValueError('Mask empty or exceeds size limit.')
    try:
        with Image.open(io.BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            if image.size != (shape[1], shape[0]):
                raise ValueError(f'Mask dimensions {image.size} do not match original image {(shape[1],shape[0])}.')
            return np.asarray(image.convert('L')) >= 128
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError('Could not decode segmentation mask.') from exc


def _band(pct: float) -> str:
    if pct == 0.0:
        return 'ZERO_IN_SAMPLE'
    if pct <= 10.0:
        return 'OVER_0_TO_10_PCT'
    if pct <= 25.0:
        return 'OVER_10_TO_25_PCT'
    return 'OVER_25_PCT'


def inspection_incidence(block_id: str, disease: str, inspected_bushes: int,
                         symptomatic_bushes: int) -> dict[str, Any]:
    """Officer input measurement; NOT leaf lesion-area severity."""
    if not re.fullmatch(r'B(?:0[1-9]|1[0-6])', str(block_id)):
        raise ValueError('Block must be B01..B16.')
    if disease not in DISEASES:
        raise ValueError(f'Disease must be one of: {", ".join(DISEASES)}')
    if (type(inspected_bushes) is not int or type(symptomatic_bushes) is not int
            or inspected_bushes < 1 or inspected_bushes > 1_000_000
            or symptomatic_bushes < 0 or symptomatic_bushes > inspected_bushes):
        raise ValueError('Require integer inspected bushes >0 and 0 <= symptomatic <= inspected.')
    pct = round(100.0 * symptomatic_bushes / inspected_bushes, 4)
    return {
        'block_id': block_id,
        'disease_name': disease,
        'inspected_bushes': inspected_bushes,
        'symptomatic_bushes': symptomatic_bushes,
        'sample_incidence_pct': pct,
        'descriptive_incidence_band': _band(pct),
        'measurement': 'SYMPTOMATIC_BUSHES_DIVIDED_BY_INSPECTED_BUSHES',
        'is_leaf_lesion_area_severity': False,
        'is_field_validated': False,
        'data_provenance': 'USER_ENTERED_OFFICER_COUNTS_NOT_YET_INDEPENDENTLY_VERIFIED',
        'band_warning': 'Descriptive bands ONLY; not agronomic severity/action cut-offs.',
    }


def _largest_contour_mask(mask: np.ndarray) -> np.ndarray:
    h, w = mask.shape
    contours, _ = cv2.findContours((mask.astype(np.uint8) * 255), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return np.zeros((h, w), dtype=bool)
    largest = max(contours, key=cv2.contourArea)
    out = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(out, [largest], -1, 255, thickness=-1)
    return out > 0


def _heuristic_leaf_mask(rgb: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """Simple foreground-from-corners extraction, suited mainly to plain backgrounds.

    Does NOT prove that foreground is a whole tea leaf.
    """
    h, w = rgb.shape[:2]
    sy, sx = max(2, h // 12), max(2, w // 12)
    corners = np.concatenate([
        rgb[:sy, :sx].reshape(-1, 3), rgb[:sy, -sx:].reshape(-1, 3),
        rgb[-sy:, :sx].reshape(-1, 3), rgb[-sy:, -sx:].reshape(-1, 3)
    ], axis=0)
    sample_bgr = cv2.cvtColor(corners.reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3)
    background_lab = np.median(sample_bgr, axis=0)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    delta = np.linalg.norm(lab - background_lab, axis=2)
    # A background from the corner should not be classified as part of the leaf.
    thresh = max(20.0, float(np.percentile(delta, 20)) + 9)
    foreground = (delta > thresh).astype(np.uint8) * 255
    kernel_n = max(3, min(11, (min(h, w) // 130) * 2 + 1))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_n, kernel_n))
    foreground = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE, kernel)
    leaf = _largest_contour_mask(foreground > 0)
    coverage = float(leaf.mean())
    flags = ['AUTOMATED_FOREGROUND_NOT_VERIFIED_LEAF']
    if coverage < 0.04 or coverage > 0.92:
        flags.append('SEGMENTATION_REVIEW_REQUIRED_UNUSUAL_FOREGROUND_COVERAGE')
    # Detect substantial mask touching an edge: likely busy outdoor background.
    edge_ratio = (float(leaf[0, :].mean()) + float(leaf[-1, :].mean())
                  + float(leaf[:, 0].mean()) + float(leaf[:, -1].mean())) / 4
    if edge_ratio > 0.1:
        flags.append('SEGMENTATION_REVIEW_REQUIRED_FOREGROUND_TOUCHES_EDGE')
    return leaf, flags


def _heuristic_lesion_mask(rgb: np.ndarray, leaf_mask: np.ndarray,
                           disease: str | None) -> np.ndarray:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    # Extremely rough symptom-color candidates; NOT reliable lesion segmentation.
    if disease == 'Red Rust':
        tentative = ((h <= 27) & (s >= 65) & (v >= 35) & (v <= 235))
    elif disease == 'Red Spider Mite':
        tentative = ((h <= 18) & (s >= 75) & (v >= 25) & (v <= 220))
    elif disease == 'Grey Leaf':
        tentative = (s <= 65) & (v >= 45) & (v <= 215)
    else:
        brown = ((h <= 28) & (s >= 50) & (v >= 20) & (v <= 220))
        pale_grey = ((s <= 55) & (v >= 55) & (v <= 180))
        tentative = brown | pale_grey
    # Ignore 2 px along foreground boundaries (edge fringing).
    kernel = np.ones((3, 3), dtype=np.uint8)
    interior = cv2.erode(leaf_mask.astype(np.uint8), kernel, iterations=1) > 0
    return tentative & interior


def leaf_pixel_measurement(image_bytes: bytes, *, disease: str | None = None,
                           leaf_mask_bytes: bytes | None = None,
                           lesion_mask_bytes: bytes | None = None
                           ) -> tuple[dict[str, Any], bytes]:
    """Return measurement metadata and PNG overlay bytes for web APIs.

    Masks must both be present or neither. With auto masks, percentages are
    unvalidated illustrative estimates and MAY be wrong for real photographs.
    """
    if disease is not None and disease not in (*DISEASES, 'Healthy'):
        raise ValueError('Unsupported disease label.')
    if (leaf_mask_bytes is None) != (lesion_mask_bytes is None):
        raise ValueError('Supply BOTH manually reviewed leaf and lesion masks, or neither.')
    rgb = _validate_image(image_bytes)
    H, W = rgb.shape[:2]
    if leaf_mask_bytes is not None:
        leaf = _mask_from_image(leaf_mask_bytes, (H, W))
        lesions = _mask_from_image(lesion_mask_bytes, (H, W))
        if np.any(lesions & ~leaf):
            raise ValueError('Lesion mask includes pixels outside the supplied leaf mask.')
        method = 'USER_SUPPLIED_MASK_PIXEL_MEASUREMENT'
        flags = ['MASKS_SUPPLIED_EXTERNALLY_ANNOTATION_QUALITY_NOT_VERIFIED']
    else:
        leaf, flags = _heuristic_leaf_mask(rgb)
        lesions = _heuristic_lesion_mask(rgb, leaf, disease)
        method = 'AUTOMATIC_COLOR_HEURISTIC_UNVALIDATED_DEMO'
        flags.append('COLOR_BASED_LESION_PROPOSAL_REQUIRES_HUMAN_REVIEW')
        if disease == 'Healthy':
            flags.append('HEALTHY_CLASSIFIER_LABEL_DOES_NOT_VALIDATE_NO_LESIONS')
    n_leaf = int(leaf.sum())
    n_lesion = int(lesions.sum())
    if n_leaf == 0:
        raise ValueError('No leaf pixels extracted. Supply masks or use plain-background image.')
    pct = round(100.0 * n_lesion / n_leaf, 4)
    # Contour/overlay PNG, for UI visual inspection not for clinical decision.
    result_image = rgb.copy()
    result_image[lesions] = np.uint8(0.55 * result_image[lesions].astype(float)
                                           + 0.45 * np.array([255, 45, 45], dtype=float))
    contours, _ = cv2.findContours(leaf.astype(np.uint8) * 255,
                                   cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(result_image, contours, -1, (60, 210, 255), thickness=max(1, min(H, W) // 250))
    file_buffer = io.BytesIO()
    Image.fromarray(result_image).save(file_buffer, format='PNG')
    valid = not any('SEGMENTATION_REVIEW_REQUIRED' in v for v in flags)
    result = {
        'disease_label_context': disease,
        'image_width': W,
        'image_height': H,
        'leaf_pixels': n_leaf,
        'candidate_lesion_pixels': n_lesion,
        'candidate_lesion_area_pct': pct,
        'method': method,
        'mask_input_provided': leaf_mask_bytes is not None,
        'measurement_status': ('UNVALIDATED_AUTO_ESTIMATE_REVIEW_REQUIRED'
                               if leaf_mask_bytes is None else 'GEOMETRIC_MASK_MEASUREMENT_ANNOTATIONS_NOT_VERIFIED'),
        'segmentation_quality_flags': flags,
        'automatic_mask_plausibility_only': valid if leaf_mask_bytes is None else None,
        'is_field_validated_severity': False,
        'is_model_trained_for_segmentation': False,
        'is_gradcam_used_as_lesion_mask': False,
        'image_overlay_is_diagnostic_visualization_only': True,
        'disclaimer': ('Percentage is candidate lesion-colored area divided by estimated/annotated leaf area. '
                       'NOT independently validated leaf disease severity. Actual severity requires '
                       'expert-reviewed lesion masks and accuracy evaluation.'),
    }
    return result, file_buffer.getvalue()
