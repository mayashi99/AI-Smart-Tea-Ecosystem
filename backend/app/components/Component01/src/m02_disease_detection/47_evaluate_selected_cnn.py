"""One-time DEV-TEST diagnostic for a CNN chosen ONLY on dev-validation.

The 863-image 'dev_test' split has unresolved dataset source independence.
This is not independent field validation or a final scientific accuracy score.
Run only after benchmark + finetune, with --approve-dev-test.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

import numpy as np
import torch
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support, f1_score

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from cnn_dev_data import build_dev_loaders


def core_loader():
    spec = importlib.util.spec_from_file_location('cnn_step17', HERE/'17_train_cnn_dev.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def dump(path, val):
    path.write_text(json.dumps(val, indent=2, ensure_ascii=False), encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-id', required=True)
    p.add_argument('--approve-dev-test', action='store_true', help='Explicitly allow one-time diagnostic test')
    p.add_argument('--batch-size', type=int, default=8)
    p.add_argument('--cpu-threads', type=int, default=4)
    p.add_argument('--device', choices=['cpu','auto','cuda'], default='cpu')
    a = p.parse_args()
    import re
    if not re.fullmatch('[A-Za-z0-9_-]{1,48}', a.run_id):
        raise ValueError('Invalid run ID')
    if a.batch_size < 2 or a.cpu_threads < 1:
        raise ValueError('Batch-size must be >=2 and threads >=1')
    report = ROOT / 'outputs/reports/cnn_step47' / a.run_id
    model_dir = ROOT / 'models/image/development_only' / ('step17_step47_' + a.run_id)
    comparison = report / 'benchmark_comparison.json'
    if not comparison.is_file():
        raise FileNotFoundError('First finish benchmarking three architectures')
    ranked = json.loads(comparison.read_text(encoding='utf-8'))
    winner = ranked['best_architecture']
    finetune = report / f'{winner}_finetune_summary.json'
    if not finetune.is_file():
        raise FileNotFoundError('First finish selected-model fine-tuning')
    if not a.approve_dev_test:
        print('PREFLIGHT PASS: benchmark and finetune exist, dev-test NOT opened.')
        print('WARNING: development test is NOT source-independent. To run once, pass --approve-dev-test')
        return
    seal = report / 'dev_test_sealed.json'
    if seal.exists():
        raise RuntimeError('Development test already evaluated/sealed for this run. Never re-evaluate for selection.')
    original = next(x for x in ranked['models'] if x['architecture'] == winner)
    fine = json.loads(finetune.read_text(encoding='utf-8'))
    if original.get('weights') != 'imagenet' or fine.get('weights') != 'imagenet':
        raise RuntimeError('Final test evaluation requires ImageNet transfer-learning benchmark')
    choice = max((original, fine), key=lambda x: x['best_dev_val_macro_f1'])
    chosen = (ROOT / choice['checkpoint']).resolve()
    if not chosen.is_relative_to(model_dir.resolve()):
        raise RuntimeError('Checkpoint outside selected run')
    if not chosen.is_file():
        raise FileNotFoundError(chosen)
    core = core_loader()
    _, mapping, sha = core.read_step16(ROOT)
    payload = torch.load(chosen, map_location='cpu', weights_only=True)
    classes = [mapping['idx_to_class'][str(i)] for i in range(5)]
    if payload.get('manifest_sha256') != sha or payload.get('class_names') != classes:
        raise ValueError('Checkpoint class names/manifest changed')
    if payload.get('model_architecture') != winner:
        raise ValueError('Architecture mismatch')
    if a.device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA not available')
    device = torch.device('cuda' if a.device == 'cuda' or (a.device == 'auto' and torch.cuda.is_available()) else 'cpu')
    torch.set_num_threads(a.cpu_threads)
    model = core.make_model(winner, 5, pretrained=False)
    model.load_state_dict(payload['model_state_dict'], strict=True)
    model.to(device).eval()
    # Seal BEFORE opening the dev-test image files. Failure requires human audit,
    # not repeated trial-and-error peeking at test results.
    seal_data = {'status': 'SEALED_BEFORE_ONE_TIME_DEV_TEST', 'created_utc': datetime.now(timezone.utc).isoformat(),
                 'winner_architecture': winner, 'selection_stage': choice['stage'],
                 'selection_metric': 'dev_val_macro_f1', 'validation_score': choice['best_dev_val_macro_f1'],
                 'checkpoint': chosen.relative_to(ROOT).as_posix(),
                 'checkpoint_sha256': hashlib.sha256(chosen.read_bytes()).hexdigest(),
                 'manifest_sha256': sha, 'test_source_independence_verified': False,
                 'evaluation_not_for_field_accuracy_claim': True}
    with seal.open('x', encoding='utf-8') as fh:
        json.dump(seal_data, fh, indent=2)
    loaders, datasets = build_dev_loaders(ROOT, batch_size=a.batch_size, num_workers=0, seed=42)
    true, pred = [], []
    with torch.inference_mode():
        for batch, labels in loaders['dev_test']:
            prediction = model(batch.to(device)).argmax(1).cpu().tolist()
            true.extend(labels.tolist()); pred.extend(prediction)
    labels = list(range(5))
    precision, recall, f1, support = precision_recall_fscore_support(true, pred, labels=labels,
                                                                      average=None, zero_division=0)
    matrix = confusion_matrix(true, pred, labels=labels)
    with (report/'dev_test_confusion_matrix.csv').open('w', encoding='utf-8', newline='') as fh:
        writer = csv.writer(fh)
        writer.writerow(['actual\\predicted', *classes])
        for name, counts in zip(classes, matrix.tolist()):
            writer.writerow([name, *counts])
    class_scores = [dict(class_name=cls, precision=float(precision[i]), recall=float(recall[i]),
                         f1=float(f1[i]), support=int(support[i])) for i, cls in enumerate(classes)]
    with (report/'dev_test_per_class_metrics.csv').open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(class_scores[0]))
        writer.writeheader(); writer.writerows(class_scores)
    evaluation = {'dataset': 'dev_test', 'scientific_status': 'DEVELOPMENT_DIAGNOSTIC_NOT_SOURCE_INDEPENDENT',
                  'source_independent': False, 'num_images': len(true), 'classes': classes,
                  'selected_model': winner, 'selected_training_stage': choice['stage'],
                  'checkpoint': chosen.relative_to(ROOT).as_posix(),
                  'selected_validation_macro_f1': choice['best_dev_val_macro_f1'],
                  'accuracy': float(accuracy_score(true, pred)),
                  'macro_precision': float(np.mean(precision)), 'macro_recall': float(np.mean(recall)),
                  'macro_f1': float(f1_score(true, pred, labels=labels, average='macro', zero_division=0)),
                  'weighted_f1': float(f1_score(true, pred, labels=labels, average='weighted', zero_division=0)),
                  'per_class': class_scores, 'confusion_matrix': matrix.tolist(),
                  'evaluated_once': True, 'real_world_field_accuracy_established': False}
    dump(report/'dev_test_evaluation.json', evaluation)
    dump(report/'final_selected_checkpoint.json', {
        'checkpoint': chosen.relative_to(ROOT).as_posix(),
        'architecture':winner,'stage':choice['stage'],
        'checkpoint_sha256': seal_data['checkpoint_sha256'],
        'validation_macro_f1':choice['best_dev_val_macro_f1'],
        'scientific_status':evaluation['scientific_status'],
        'instruction':'Set TEA_CNN_CHECKPOINT to this path in the FastAPI terminal',
    })
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(9, 7))
        ax.imshow(matrix)
        ax.set_xticks(range(5), classes, rotation=35, ha='right')
        ax.set_yticks(range(5), classes)
        ax.set_xlabel('Predicted class'); ax.set_ylabel('Actual class')
        ax.set_title('Development-only test: confusion matrix')
        for i in range(5):
            for j in range(5):
                ax.text(j,i,str(int(matrix[i,j])),ha='center',va='center',color='white' if matrix[i,j] > matrix.max()/2 else 'black')
        fig.tight_layout()
        fig.savefig(report/'dev_test_confusion_matrix.png', dpi=140)
        plt.close(fig)
    except ImportError:
        print('matplotlib absent; confusion matrix CSV saved (PNG optional)')
    print('='*75)
    print(f'STEP47 DEV-TEST DIAGNOSTIC PASS | architecture={winner} stage={choice["stage"]}')
    print(f'Accuracy={evaluation["accuracy"]:.4f}, Macro F1={evaluation["macro_f1"]:.4f}, n={len(true)}')
    print(f'Final API checkpoint: {chosen.relative_to(ROOT)}')
    print(f'Reports: {report}')
    print('LIMITATION: Development images only; not field-independent scientific accuracy.')


if __name__ == '__main__':
    main()
