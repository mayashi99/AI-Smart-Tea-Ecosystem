#!/usr/bin/env python3
"""Offline engine self-tests: artificial drawn image/masks, no real tea-leaf truth."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from severity_inference import inspection_incidence, leaf_pixel_measurement


def png_bytes(array: np.ndarray) -> bytes:
    sink = io.BytesIO()
    Image.fromarray(array).save(sink, format='PNG')
    return sink.getvalue()


def must_fail(fn, reason: str) -> None:
    try:
        fn()
    except ValueError:
        return
    raise AssertionError(f'Unsafe invalid input accepted: {reason}')


def main() -> None:
    image = np.full((100, 100, 3), [255,255,255], dtype=np.uint8)
    # Manually specified square leaf=40x40 = 1600 px, lesion 10x10=100 px => 6.25%.
    image[30:70, 30:70, :] = [35, 145, 54]
    image[35:45, 35:45, :] = [125, 67, 29]
    leaf_mask = np.zeros((100, 100), dtype=np.uint8)
    leaf_mask[30:70,30:70] = 255
    lesion_mask = np.zeros((100,100), dtype=np.uint8)
    lesion_mask[35:45,35:45] = 255
    img = png_bytes(image)
    mask_leaf = png_bytes(leaf_mask)
    mask_lesion = png_bytes(lesion_mask)
    exact, preview = leaf_pixel_measurement(img, disease='Brown Blight',
                                            leaf_mask_bytes=mask_leaf, lesion_mask_bytes=mask_lesion)
    assert exact['candidate_lesion_area_pct'] == 6.25, exact
    assert exact['leaf_pixels'] == 1600 and exact['candidate_lesion_pixels'] == 100
    assert exact['is_field_validated_severity'] is False
    assert len(preview) > 200
    auto, _ = leaf_pixel_measurement(img, disease='Brown Blight')
    assert 0 <= auto['candidate_lesion_area_pct'] <= 100
    assert auto['method'] == 'AUTOMATIC_COLOR_HEURISTIC_UNVALIDATED_DEMO'
    assert not auto['is_field_validated_severity']
    officer = inspection_incidence('B16', 'Red Rust', 80, 20)
    assert officer['sample_incidence_pct'] == 25.0
    assert officer['is_leaf_lesion_area_severity'] is False
    must_fail(lambda: inspection_incidence('B17','Red Rust',80,20), 'B17')
    must_fail(lambda: inspection_incidence('B02','Red Rust',50,60), 'symptomatic > inspected')
    must_fail(lambda: leaf_pixel_measurement(img, leaf_mask_bytes=mask_leaf), 'missing lesion mask')
    lesion_invalid = np.zeros((100,100), dtype=np.uint8)
    lesion_invalid[0:4,0:4] = 255
    must_fail(lambda: leaf_pixel_measurement(img, leaf_mask_bytes=mask_leaf,
                                            lesion_mask_bytes=png_bytes(lesion_invalid)), 'lesion outside leaf')
    print('='*78)
    print('STEP39 SELF TEST - SYNTHETIC DRAWING (NOT ANNOTATED TEA LEAF)')
    print('='*78)
    print(f'Manual masks: 1600 leaf / 100 lesion = {exact["candidate_lesion_area_pct"]}% | PASS')
    print(f'Automatic illustrative mask candidate: {auto["candidate_lesion_area_pct"]}% | RUN PASS, NOT ACCURACY')
    print(f'Any block B16 officer sample: 20/80 = {officer["sample_incidence_pct"]}% | PASS')
    print('Input rejection: bad block, bad counts, one mask, mask outside leaf | PASS')
    print('PASS: Reusable image and officer calculation API. NO real leaf accuracy verified.')


if __name__ == '__main__':
    main()
