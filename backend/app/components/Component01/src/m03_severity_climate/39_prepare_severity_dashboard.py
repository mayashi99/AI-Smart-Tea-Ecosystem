#!/usr/bin/env python3
"""Step 39 - operational incidence dashboard and optional leaf-area demo.

With no arguments: export all historical Step35 4-disease x 16-block
synthetic incidence rows without fabricating image lesion severity.

With --image: calculate a candidate LESION-AREA pixel fraction; optional
human-supplied leaf and lesion masks (both required). Automatic mode is an
UNVALIDATED color heuristic, not a trained/validated lesion segmentation model.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from severity_inference import DISEASES, inspection_incidence, leaf_pixel_measurement


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding='utf-8')


def export_historical(root: Path) -> dict:
    """Read Step35 only; do not read future labels, m04 test, or images."""
    src = root / 'outputs/dashboard/climate/step35_block_incidence_snapshot.csv'
    meta_path = root / 'outputs/dashboard/climate/step35_historical_context_summary.json'
    if not src.exists() or not meta_path.exists():
        raise FileNotFoundError('Run Step35 first. Expected 64-row historical incidence snapshot and metadata.')
    metadata = json.loads(meta_path.read_text(encoding='utf-8'))
    if metadata.get('status') != 'PASS_HISTORICAL_SIMULATION_CONTEXT_ONLY' or metadata.get('test_rows_used') is not False:
        raise ValueError('Step35 historical simulation provenance not valid.')
    columns = ['forecast_origin_date', 'disease_name', 'block_id', 'block_name',
               'last_inspection_date', 'days_since_inspection', 'inspected_bushes',
               'symptomatic_bushes', 'sample_incidence_pct', 'descriptive_incidence_band',
               'observation_type', 'is_lesion_area_severity']
    df = pd.read_csv(src)
    if not set(columns).issubset(df.columns):
        raise ValueError(f'Step35 missing columns: {sorted(set(columns)-set(df.columns))}')
    if len(df) != 64 or df['block_id'].nunique() != 16 or set(df['disease_name']) != set(DISEASES):
        raise ValueError('Expected 4 diseases x 16 blocks = 64 unique Step35 rows.')
    if df.duplicated(['forecast_origin_date', 'block_id', 'disease_name']).any():
        raise ValueError('Duplicate block/disease/origin rows in Step35.')
    if df['is_lesion_area_severity'].astype(str).str.lower().ne('false').any():
        raise ValueError('Refusing to misrepresent Step35 incidence as lesion-area severity.')
    if df['observation_type'].ne('SIMULATED_INSPECTION_NOT_FIELD_MEASURED').any():
        raise ValueError('Step35 source is not marked simulation only.')
    df['inspected_bushes'] = pd.to_numeric(df['inspected_bushes'], errors='raise').astype('int64')
    df['symptomatic_bushes'] = pd.to_numeric(df['symptomatic_bushes'], errors='raise').astype('int64')
    if not ((df.inspected_bushes > 0) & (df.symptomatic_bushes >= 0) &
            (df.symptomatic_bushes <= df.inspected_bushes)).all():
        raise ValueError('Invalid simulation bush counts.')
    values = 100 * df.symptomatic_bushes / df.inspected_bushes
    if ((df['sample_incidence_pct'] - values).abs() > 0.000051).any():
        raise ValueError('Step35 incidence percentage does not match inspected bush counts.')
    if len(df.forecast_origin_date.unique()) != 1 or str(df.forecast_origin_date.iloc[0]) != str(metadata['forecast_origin_date']):
        raise ValueError('Step35 forecast origin mismatch.')
    for r in df.itertuples(index=False):
        expected = inspection_incidence(r.block_id, r.disease_name, r.inspected_bushes, r.symptomatic_bushes)
        if expected['descriptive_incidence_band'] != r.descriptive_incidence_band.replace('ZERO_SYMPTOMATIC_BUSHES_IN_SAMPLE', 'ZERO_IN_SAMPLE'):
            raise ValueError(f'Incidence band mismatch: {r.disease_name}, {r.block_id}')
    dst = df[columns].copy()
    dst['measurement_type'] = 'SAMPLED_BUSH_INCIDENCE_NOT_LEAF_AREA_SEVERITY'
    dst['leaf_lesion_area_pct'] = None  # Missing verified leaf masks. DO NOT invent.
    dst['leaf_area_severity_status'] = 'NOT_MEASURED_NO_VERIFIED_LEAF_AND_LESION_MASKS'
    dst['is_field_validated'] = False
    dst['is_simulated'] = True
    outfile = root / 'outputs/dashboard/severity/step39_incidence_dashboard.csv'
    reportfile = root / 'outputs/reports/step39_m03_severity_audit.json'
    metafile = root / 'outputs/dashboard/severity/step39_metadata.json'
    outfile.parent.mkdir(parents=True, exist_ok=True)
    dst.to_csv(outfile, index=False)
    audit = {
        'step': 39,
        'status': 'PASS_INCIDENT_BUSH_PROPORTION_EXPORT_AND_IMAGE_ENGINE_AVAILABLE',
        'source': 'Step35 historical simulated officer observations',
        'historical_origin': str(df.forecast_origin_date.iloc[0]),
        'rows': len(dst),
        'blocks': sorted(df.block_id.unique().tolist()),
        'diseases': sorted(df.disease_name.unique().tolist()),
        'synthetic_inspections_only': True,
        'independent_field_validation': False,
        'leaf_lesion_area_measurements_in_historical_export': 0,
        'image_lesion_area_heuristic_available_on_uploaded_image': True,
        'expert_reviewed_leaf_lesion_segmentation_masks_included': False,
        'baseline_manual_masks_mode_available': True,
        'locked_test_used': False,
        'future_targets_used': False,
        'source_rows_or_models_modified': False,
        'limitation': 'Incidence is proportion of inspected bushes symptomatic. It is not leaf lesion-area severity. Color heuristic estimates are unvalidated and require manual review.',
        'dashboard_file': str(outfile.relative_to(root)),
    }
    write_json(metafile, audit)
    write_json(reportfile, audit)
    print('=' * 81)
    print('STEP 39 - m03 INCIDENCE + LEAF PIXEL-AREA PROTOTYPE | HISTORICAL SIMULATION')
    print('=' * 81)
    print(f'Historical origin: {audit["historical_origin"]} | diseases=4 blocks=16 rows={len(dst)}')
    print(f'Incidence dashboard: {outfile}')
    print(f'Metadata: {metafile}\nAudit: {reportfile}')
    print('PASS: Incidence verified from sampled bush counts. Zero invented leaf-area results.')
    print('WARNING: No verified image lesion masks; automatic image segmentation is DEMO ONLY.')
    return audit


def run_image(root: Path, args: argparse.Namespace) -> dict:
    if not args.image.is_file():
        raise FileNotFoundError(args.image)
    leaf_mask_bytes = args.leaf_mask.read_bytes() if args.leaf_mask else None
    lesion_mask_bytes = args.lesion_mask.read_bytes() if args.lesion_mask else None
    prediction, png = leaf_pixel_measurement(args.image.read_bytes(),
                                             disease=args.disease,
                                             leaf_mask_bytes=leaf_mask_bytes,
                                             lesion_mask_bytes=lesion_mask_bytes)
    if any(v is not None for v in [args.block, args.inspected, args.symptomatic]):
        if args.block is None or args.disease is None or args.inspected is None or args.symptomatic is None:
            raise ValueError('To add officer observations, provide all --block --disease --inspected --symptomatic.')
        prediction['officer_inspection'] = inspection_incidence(args.block, args.disease, args.inspected, args.symptomatic)
    prediction['source_image_name'] = args.image.name
    prediction['image_upload_processed_utc'] = datetime.now(timezone.utc).isoformat()
    prediction['image_and_masks_are_not_exported_as_verified_training_labels'] = True
    out_dir = root / 'outputs/dashboard/severity/user_image_demo'
    out_dir.mkdir(parents=True, exist_ok=True)
    base = args.image.stem.replace(' ', '_')[:40]
    # Prefix safely; overwritten for repeated same image (NOT a persistent multi-user store).
    overlay_path = out_dir / f'{base}_lesion_candidate_overlay.png'
    report_path = out_dir / f'{base}_lesion_candidate_measurement.json'
    overlay_path.write_bytes(png)
    prediction['overlay_path'] = str(overlay_path.relative_to(root)).replace('\\', '/')
    write_json(report_path, prediction)
    print('=' * 81)
    print('STEP 39 - UPLOADED IMAGE CANDIDATE LESION PIXEL-AREA MEASUREMENT')
    print('=' * 81)
    print('Method:', prediction['method'])
    print('Candidate lesion/leaf area:', prediction['candidate_lesion_area_pct'], '%')
    print('Status:', prediction['measurement_status'])
    print('Overlay:', overlay_path)
    print('JSON:', report_path)
    if 'officer_inspection' in prediction:
        print('Officer sampled bush incidence:', prediction['officer_inspection']['sample_incidence_pct'], '%')
    print('WARNING: NOT field-validated disease severity, not verified mask annotation.')
    return prediction


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--component-root', type=Path, default=ROOT)
    ap.add_argument('--image', type=Path, help='Optional RGB tea leaf image to analyze.')
    ap.add_argument('--leaf-mask', type=Path, help='Optional binary image: white=leaf, black=not leaf.')
    ap.add_argument('--lesion-mask', type=Path, help='Optional binary image: white=lesion, black=not lesion.')
    ap.add_argument('--disease', choices=(*DISEASES, 'Healthy'))
    ap.add_argument('--block', type=str)
    ap.add_argument('--inspected', type=int)
    ap.add_argument('--symptomatic', type=int)
    args = ap.parse_args()
    root = args.component_root.resolve()
    if args.image is None:
        if any(x is not None for x in (args.leaf_mask, args.lesion_mask, args.disease, args.block, args.inspected, args.symptomatic)):
            raise ValueError('Without --image, run plain Step39 snapshot command (no other arguments).')
        export_historical(root)
    else:
        run_image(root, args)


if __name__ == '__main__':
    main()
