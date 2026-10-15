"""Read Step48B report only; verify all 21 heads and 4-disease metrics without opening TEST."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

KINDS = ('Disease_Active','Incidence_Pct','New_Onset_By')
TARGETS={f'Target_{k}_Day_{day}' for day in range(1,8) for k in KINDS}
VARIANTS={'step31_original_hybrid','step48_candidate_hybrid','step48_all_tuned_ml'}


def ensure(x,msg):
    if not x: raise ValueError(msg)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--component-root',type=Path,default=Path(__file__).resolve().parents[2])
    ap.add_argument('--report-dir',type=Path,default=None)
    a=ap.parse_args()
    root=a.component_root.resolve()
    parent=root/'outputs/reports/multidisease_step48b'
    dirs=[p for p in sorted(parent.glob('full_*')) if (p/'step48b_heldout_audit.json').exists()]
    d=a.report_dir.resolve() if a.report_dir else (dirs[-1] if dirs else None)
    ensure(d is not None and d.parent==parent and d.is_dir(),'No Step48B full report found')
    info=json.loads((d/'step48b_heldout_audit.json').read_text(encoding='utf-8'))
    summary=pd.read_csv(d/'heldout_test_hybrid_comparison.csv')
    disease=pd.read_csv(d/'heldout_test_per_disease.csv')
    ensure(info['status']=='PASS_HELDOUT_COMPARISON_SYNTHETIC','Invalid report status')
    ensure(info['test_used_to_select_models'] is False and info['models_promoted'] is False and
           info['protected_files_unchanged'] is True,'Unsafe changed model/test selection')
    ensure(len(summary)==21 and set(summary.target)==TARGETS and summary.target.nunique()==21,
           'Expected 21 unique target comparisons')
    ensure(len(disease)==3*21*4 and set(disease.variant)==VARIANTS and
           set(disease.target)==TARGETS and disease.disease.nunique()==4,
           'Expected 3 variants x 21 targets x 4 diseases')
    ensure(disease.groupby(['target','variant']).size().eq(4).all(),
           'Missing per-disease metric records')
    ensure(np.isfinite(summary[['original_step31','step48_candidate_hybrid',
                                'step48_all_tuned_ml','candidate_minus_original']].values).all(),
           'Nonfinite comparison scores')
    ensure(((summary.step48_candidate_hybrid-summary.original_step31 -
             summary.candidate_minus_original).abs()<1e-8).all(),
           'Incorrect paired difference')
    ensure(summary.test_rows.eq(info['aligned_test_records']).all(),
           'Test count mismatch by target')
    ensure(int(summary.candidate_improved.sum()) == info['per_target_improved'] and
           int(summary.equal.sum()) == info['per_target_equal'],
           'Winner count mismatch')
    print(f'STEP48B VERIFY — PASS | 21/21 heads, {len(disease)} detailed rows, '
          f'test sample count={info["aligned_test_records"]:,}',flush=True)
    print(f'Compared candidate hybrid vs frozen hybrid: improved={info["per_target_improved"]}, '
          f'worse={info["per_target_worse"]}, equal={info["per_target_equal"]}',flush=True)
    print('TEST not reopened; existing checkpoints and API untouched.',flush=True)
    print('Report:',d,flush=True)


if __name__=='__main__':
    main()
