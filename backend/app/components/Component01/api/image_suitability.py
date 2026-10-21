"""Conservative appearance checks, NOT tea/species recognition or OOD detection."""
from collections import Counter
import csv
import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, ImageStat

MESSAGE = 'Unable to verify a suitable tea leaf photograph. Please upload a clear photo of a tea leaf.'
INVALID_MESSAGE = '⚠️ Invalid Image! Please upload a real tea leaf photo.'


def check_training_membership(data: bytes, root: Path):
    """Exact original-file allowlist; this is dataset membership, not recognition."""
    manifest = root / 'data/processed/image_split_manifest_DEV_ONLY.csv'
    with manifest.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not {'split', 'sha256'}.issubset(reader.fieldnames or []):
            raise ValueError('Invalid training image manifest')
        allowed = set()
        for row in reader:
            if row['split'] == 'dev_train':
                sha = row['sha256'].lower()
                if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
                    raise ValueError('Invalid training image checksum')
                allowed.add(sha)
    if not allowed:
        raise ValueError('Training image allowlist is empty')
    if hashlib.sha256(data).hexdigest() in allowed:
        return None
    return {
        'analysis_status': 'rejected',
        'message_key': 'invalidTeaImage',
        'message': INVALID_MESSAGE,
        'suitability': {
            'method': 'exact_training_sha256_allowlist_v1',
            'reason': 'NOT_AN_ORIGINAL_TRAINING_IMAGE',
            'tea_identity_verified': False,
            'limitation': 'Only exact dev_train files are allowed; unseen tea photos and edited copies are rejected.',
        },
    }


def human_face_count(image):
    """Local rejection safeguard only. No downloads, retained images or face boxes."""
    try:
        import cv2
        import numpy as np
        small = image.copy()
        small.thumbnail((1280, 1280))
        gray = cv2.cvtColor(np.asarray(small), cv2.COLOR_RGB2GRAY)
        detections = []
        for name in ('haarcascade_frontalface_default.xml', 'haarcascade_frontalface_alt2.xml'):
            cascade = Path(cv2.data.haarcascades) / name
            if not cascade.is_file():
                return None
            detector = cv2.CascadeClassifier(str(cascade))
            if detector.empty():
                return None
            detections.append(detector.detectMultiScale(gray, scaleFactor=1.1,
                                                       minNeighbors=8, minSize=(40, 40)))

        def agrees(a, b):
            x, y, w, h = map(int, a)
            u, v, s, t = map(int, b)
            intersection = max(0, min(x + w, u + s) - max(x, u)) * max(0, min(y + h, v + t) - max(y, v))
            return intersection / (w * h + s * t - intersection) >= .5

        return sum(any(agrees(a, b) for b in detections[1]) for a in detections[0])
    except (ImportError, AttributeError, OSError):
        return None
    except Exception as exc:
        # OpenCV native failures must not silently bypass this safeguard.
        if type(exc).__module__ == 'cv2':
            return None
        raise


def interface_geometry(image):
    """Require repeated long, axis-aligned boundaries AND flat panel regions."""
    image = image.copy()
    image.thumbnail((640, 640))
    width, height = image.size
    pixels = list(image.getdata())

    def different(a, b):
        return max(abs(x - y) for x, y in zip(a, b)) > 24

    horizontal = [sum(different(pixels[y * width + x], pixels[(y - 1) * width + x])
                      for x in range(width)) / width for y in range(1, height)]
    vertical = [sum(different(pixels[y * width + x], pixels[y * width + x - 1])
                    for y in range(height)) / height for x in range(1, width)]

    def groups(values):
        # Count contiguous boundary bands once, regardless of line thickness.
        return sum(value > .28 and (i == 0 or values[i - 1] <= .28)
                   for i, value in enumerate(values))

    flat_tiles = 0
    for y in range(32):
        for x in range(32):
            tile = image.crop((x * width // 32, y * height // 32,
                               (x + 1) * width // 32, (y + 1) * height // 32))
            flat_tiles += max(ImageStat.Stat(tile).stddev) <= 6
    return {'horizontal_boundary_bands': groups(horizontal),
            'vertical_boundary_bands': groups(vertical),
            'longest_horizontal_coverage': round(max(horizontal), 4),
            'longest_vertical_coverage': round(max(vertical), 4),
            'flat_tile_fraction': flat_tiles / 1024}


def assess_image(data: bytes) -> dict:
    with Image.open(BytesIO(data)) as source:
        rgb = ImageOps.exif_transpose(source).convert('RGB')
        faces = human_face_count(rgb)
        geometry = interface_geometry(rgb)
        rgb.thumbnail((192, 192))
    gray = rgb.convert('L')
    spread = ImageStat.Stat(gray).stddev[0]
    pixels = list(rgb.getdata())
    palette = Counter(tuple(v // 16 for v in p) for p in pixels)
    dominant = sum(n for _, n in palette.most_common(8)) / len(pixels)
    gray_pixels = list(gray.getdata())
    width, height = rgb.size
    pairs = [(gray_pixels[y * width + x], gray_pixels[y * width + x + 1])
             for y in range(height) for x in range(width - 1)]
    pairs += [(gray_pixels[y * width + x], gray_pixels[(y + 1) * width + x])
              for y in range(height - 1) for x in range(width)]
    flat = sum(abs(a - b) <= 2 for a, b in pairs) / len(pairs)
    white = sum(min(p) >= 235 for p in pixels) / len(pixels)
    neutral = sum(max(p) - min(p) <= 12 for p in pixels) / len(pixels)
    status, reason = 'acceptable', 'no_obvious_suitability_issue'
    if faces:
        status, reason = 'rejected', 'HUMAN_FACE_DETECTED'
    elif (geometry['horizontal_boundary_bands'] >= 4
            and geometry['vertical_boundary_bands'] >= 4
            and geometry['longest_horizontal_coverage'] > .50
            and geometry['longest_vertical_coverage'] > .50
            and geometry['flat_tile_fraction'] > .15):
        status, reason = 'rejected', 'repeated_interface_geometry_and_flat_panels'
    elif spread < 2:
        status, reason = 'rejected', 'near_empty_or_uniform'
    elif dominant > .95 and flat > .92:
        status, reason = 'rejected', 'extremely_flat_limited_palette'
    elif white > .70 and neutral > .96 and flat > .75:
        status, reason = 'uncertain', 'document_like_appearance'
    elif dominant > .82 and flat > .85 and neutral > .96:
        status, reason = 'uncertain', 'graphic_like_appearance'
    elif spread < 10 and flat > .80:
        status, reason = 'uncertain', 'insufficient_visual_detail'
    if status == 'acceptable' and faces is None:
        status, reason = 'uncertain', 'FACE_SAFEGUARD_UNAVAILABLE'
    return {
        'analysis_status': status,
        'message_key': 'invalidTeaImage' if status == 'rejected' else 'imageSuitabilityError',
        'message': INVALID_MESSAGE if status == 'rejected' else MESSAGE,
        'suitability': {
            'method': 'local_face_and_appearance_heuristics_v3', 'reason': reason,
            'face_safeguard': {'available': faces is not None, 'detected_count': faces},
            'metrics': {**geometry, 'grayscale_stddev': round(spread, 4),
                        'dominant_palette_fraction': round(dominant, 4),
                        'flat_neighbor_fraction': round(flat, 4),
                        'white_fraction': round(white, 4), 'neutral_fraction': round(neutral, 4)},
            'tea_identity_verified': False,
            'limitation': 'Appearance checks cannot reliably distinguish tea from other plants, animals or natural photographs.',
        },
    }
