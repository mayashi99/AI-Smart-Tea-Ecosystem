"""Read-only verifier of completed Step48 experiments. Does not open test split."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, mean_absolute_error

DISEASES=['Brown Blight','Grey Leaf','Red Rust','Red Spider Mite']

def verify(root: Path, run_dir: Path | None = None):
    root=root.resolve()
    parent=root/'models/spread/multidisease_step48'
    if run_dir is None:
        runs=sorted(parent.glob('*/experimental_registry.json'))
        assert runs, 'No Step48 experiments found'
        registry=runs[-1]
        run_dir=registry.parent
    else:
        registry=run_dir/'experimental_registry.json'
    assert registry.is_file(), f'Missing registry: {registry}'
    data=json.loads(registry.read_text(encoding='utf-8'))
    assert not data['test_opened'] and not data['automatically_promoted_to_step31_or_step42']
    assert data['feature_columns'] and len(data['feature_columns'])==48
    assert len(data['targets'])==data['target_count']
    report_path=Path(data['report_dir'])
    assert (report_path/'inner_cv_trials.csv').is_file()
    report=pd.read_csv(report_path/'validation_tuned_summary.csv')
    assert len(report)==data['target_count']
    columns=['Disease_Name']+data['feature_columns']+[r['target'] for r in data['targets']]
    val=pd.read_csv(root/'data/processed/multidisease_features_validation.csv',usecols=columns)
    features=val[data['feature_columns']].to_numpy(dtype=np.float32)
    count=0
    for r in data['targets']:
        file=run_dir/r['checkpoint']
        assert file.is_file(), f'Missing tuned experimental checkpoint {file}'
        est=joblib.load(file)  # ONLY trusted, locally generated project files
        X=features
        if est.__class__.__module__.startswith('lightgbm'):
            names=getattr(est,'feature_names_in_',None)
            if names is not None and len(names)==X.shape[1]:
                X=pd.DataFrame(X,columns=list(names))
        pred=np.asarray(est.predict(X))
        reg=r['task']=='regression'
        if reg:
            pred=np.clip(pred.astype(float),0,100)
        else:
            assert np.isin(pred,[0,1]).all()
        scores=[]
        for disease in DISEASES:
            m=val.Disease_Name.eq(disease).to_numpy()
            assert m.any()
            scores.append(mean_absolute_error(val.loc[m,r['target']],pred[m]) if reg
                          else f1_score(val.loc[m,r['target']],pred[m],labels=[0,1],average='macro',zero_division=0))
        mean=float(np.mean(scores))
        assert abs(mean-r['validation_2025_score'])<1e-6,(r['target'],mean,r['validation_2025_score'])
        count+=1
        print(f"PASS {count}/{data['target_count']} {r['target']} {r['model']} validation={mean:.5f}")
    print('STEP48 VERIFY - PASS; TEST NOT READ; existing deployment unaffected.')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--component-root',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--run-dir',type=Path,default=None)
    a=p.parse_args()
    verify(a.component_root,a.run_dir)
