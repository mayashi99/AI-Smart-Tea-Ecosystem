"""Step47: CPU-friendly 5-class CNN benchmarking + optional best-candidate finetuning.

Uses existing Step16/19 DEVELOPMENT-ONLY dataset and Step17-compatible checkpoints.
Never opens dev_test, and refuses continued training after a run's test is sealed.
Usage: python .../47_train_compare_cnn_cpu.py --stage benchmark --run-id cpu01
       python .../47_train_compare_cnn_cpu.py --stage finetune --run-id cpu01
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import sys
import time
import warnings

import numpy as np
import torch
from torch import nn
from torch.optim import AdamW

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from cnn_dev_data import build_dev_loaders

ARCHS = ('mobilenet_v3_small', 'resnet18', 'efficientnet_b0')
DEV_STATUS = 'DEVELOPMENT_ONLY_NOT_FOR_FINAL_EVALUATION'


def load_step17():
    script = HERE / '17_train_cnn_dev.py'
    spec = importlib.util.spec_from_file_location('step17_core', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def json_write(path: Path, data: dict | list):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(temp, path)


def csv_write(path: Path, rows: list[dict]):
    if not rows:
        return
    temp = path.with_name(path.name + '.tmp')
    temp.parent.mkdir(parents=True, exist_ok=True)
    with temp.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)


def state_save(path: Path, state: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    torch.save(state, temp)
    os.replace(temp, path)


def seed_everything(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def classifier(model, arch: str):
    return model.fc if arch == 'resnet18' else model.classifier


def configure_trainable(model, arch: str, stage: str):
    """Return trainable parameter count. Frozen BN stays eval during epochs."""
    for param in model.parameters():
        param.requires_grad = False
    for param in classifier(model, arch).parameters():
        param.requires_grad = True
    if stage == 'finetune':
        block = model.layer4 if arch == 'resnet18' else model.features[-2:]
        for param in block.parameters():
            param.requires_grad = True
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def set_train_mode(model, arch: str, stage: str):
    model.eval()  # freeze backbone BN running stats for stable small-batch CPU training
    classifier(model, arch).train()
    if stage == 'finetune':
        if arch == 'resnet18':
            model.layer4.train()
        else:
            for block in model.features[-2:]:
                block.train()


def train_one_epoch(model, loader, optimizer, device, arch, stage, max_batches=None):
    set_train_mode(model, arch, stage)
    ce = nn.CrossEntropyLoss()
    n, correct, loss_sum = 0, 0, 0.
    for i, (images, labels) in enumerate(loader):
        if max_batches is not None and i >= max_batches:
            break
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = model(images)
        loss = ce(logits, labels)
        if not torch.isfinite(loss):
            raise RuntimeError('Non-finite training loss')
        loss.backward()
        optimizer.step()
        n += len(labels)
        correct += int((logits.argmax(1) == labels).sum())
        loss_sum += float(loss.detach().item()) * len(labels)
    if not n:
        raise ValueError('Empty training loader')
    return {'train_loss': round(loss_sum/n, 6), 'train_accuracy': round(correct/n, 6)}


def validate(model, loader, device, classes, max_batches=None):
    # The existing Step17 evaluator already handles five classes including absent
    # classes in a smoke batch. No dev_test is accessed here.
    return load_step17().evaluate(model, loader, device, max_batches, classes)


def make_checkpoint(model, arch, classes, mapping, sha, stage, weights, epoch, metrics):
    return {
        'model_architecture': arch,
        'model_state_dict': {k: v.detach().cpu().clone() for k, v in model.state_dict().items()},
        'num_classes': len(classes), 'class_names': list(classes),
        'class_to_idx': mapping['class_to_idx'],
        'image_size': int(mapping.get('image_size', 224)),
        'normalization': {'mean': [0.485, 0.456, 0.406], 'std': [0.229, 0.224, 0.225]},
        'epoch': int(epoch), 'dev_val_macro_f1': float(metrics['macro_f1']),
        'training_mode': 'full' if stage != 'smoke' else 'smoke',
        'training_weights': weights,
        'manifest_sha256': sha, 'dataset_status': DEV_STATUS,
        'final_research_evaluation_permitted': False,
        'step47_stage': stage,
    }


def parse():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('--stage', choices=['smoke', 'benchmark', 'finetune'], default='smoke')
    p.add_argument('--run-id', default=None, help='Use same run-id for benchmark and finetune')
    p.add_argument('--architectures', nargs='+', choices=ARCHS, default=list(ARCHS))
    p.add_argument('--epochs', type=int, default=None, help='Benchmark=3, finetune=5, smoke=1')
    p.add_argument('--batch-size', type=int, default=8)
    p.add_argument('--num-workers', type=int, default=0)
    p.add_argument('--cpu-threads', type=int, default=4)
    p.add_argument('--patience', type=int, default=3)
    p.add_argument('--weights', choices=['imagenet', 'random'], default='imagenet')
    p.add_argument('--device', choices=['cpu', 'auto', 'cuda'], default='cpu')
    p.add_argument('--resume', action='store_true', help='Resume interrupted run using saved optimizer/epoch')
    p.add_argument('--max-train-batches', type=int, default=None, help='SMOKE ONLY')
    p.add_argument('--max-val-batches', type=int, default=None, help='SMOKE ONLY')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--learning-rate', type=float, default=None)
    return p.parse_args()


def main():
    a = parse()
    if a.stage == 'smoke':
        if a.weights != 'random':
            raise ValueError('Smoke mode requires explicit --weights random; no network/download')
        if a.run_id is None:
            a.run_id = f'smoke_{datetime.now():%Y%m%d_%H%M%S}'
        a.architectures = a.architectures[:1]
    if not a.run_id:
        raise ValueError('Provide --run-id (e.g., friend_cpu01) for reproducible/resumable training')
    import re
    if not re.fullmatch('[A-Za-z0-9_-]{1,48}', a.run_id):
        raise ValueError('Invalid --run-id: letters, digits, - or _, max 48')
    if a.batch_size < 2 or a.num_workers < 0 or a.cpu_threads < 1 or a.patience < 1:
        raise ValueError('Invalid batch-size/workers/threads/patience')
    if a.stage != 'smoke' and (a.max_train_batches is not None or a.max_val_batches is not None):
        raise ValueError('Truncated batches only allowed in smoke mode')
    if a.resume and a.stage == 'smoke':
        raise ValueError('Smoke runs are not resumable')
    if a.device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA is not available')
    device = torch.device('cuda' if a.device == 'cuda' or a.device == 'auto' and torch.cuda.is_available() else 'cpu')
    epochs = a.epochs or {'smoke': 1, 'benchmark': 3, 'finetune': 5}[a.stage]
    if epochs < 1:
        raise ValueError('Epochs must be positive')
    lr = a.learning_rate or (2e-5 if a.stage == 'finetune' else 1e-3)
    if not math.isfinite(lr) or lr <= 0:
        raise ValueError('Learning rate must be positive and finite')
    torch.set_num_threads(a.cpu_threads)
    torch.backends.cudnn.benchmark = False
    seed_everything(a.seed)
    core = load_step17()
    summary, mapping, sha = core.read_step16(ROOT)
    expected = ['brown blight', 'grey leaf', 'healthy', 'red rust', 'red spider mite']
    classes = [mapping['idx_to_class'][str(i)] for i in range(5)]
    if classes != expected:
        raise RuntimeError(f'Class order mismatch: {classes}. Stop to prevent incorrect predictions.')
    model_dir = ROOT / 'models/image/development_only' / f'step17_step47_{a.run_id}'
    report_dir = ROOT / 'outputs/reports/cnn_step47' / a.run_id
    if (report_dir / 'dev_test_sealed.json').exists():
        raise RuntimeError('Dev-test already sealed for this run; do NOT tune/train on this run after test evaluation.')
    if a.stage == 'finetune':
        comparison = report_dir / 'benchmark_comparison.json'
        if not comparison.is_file():
            raise FileNotFoundError('Complete all three benchmark models before finetuning.')
        winner = json.loads(comparison.read_text(encoding='utf-8'))['best_architecture']
        choices = [winner]
        if a.weights != 'imagenet':
            raise ValueError('Finetune expects ImageNet-pretrained benchmark, use default --weights imagenet')
        if any(x.get('weights') != 'imagenet' for x in json.loads(comparison.read_text(encoding='utf-8'))['models']):
            raise ValueError('Refusing to fine-tune benchmark originally trained with random weights')
    else:
        choices = a.architectures
    if a.stage == 'benchmark' and set(choices) != set(ARCHS):
        raise ValueError('Benchmark must compare all three architectures, without partial selection')
    model_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    loaders, datasets = build_dev_loaders(ROOT, batch_size=a.batch_size, num_workers=a.num_workers, seed=a.seed)
    counts = {k: len(datasets[k]) for k in ('dev_train', 'dev_val', 'dev_test')}
    print('='*77, flush=True)
    print(f'STEP47 {a.stage.upper()} | device={device} | models={choices} | train/val/test={counts}', flush=True)
    print(f'CPU threads={a.cpu_threads}, batch={a.batch_size}, epochs={epochs}, resume={a.resume}', flush=True)
    print('DEVELOPMENT ONLY. Validation decides winner. DEV_TEST NOT LOADED FOR TRAINING.', flush=True)

    for arch in choices:
        phase = a.stage
        state_file = report_dir / f'{arch}_{phase}_training_last.pt'
        history_file = report_dir / f'{arch}_{phase}_history.csv'
        result_file = report_dir / f'{arch}_{phase}_summary.json'
        if result_file.is_file() and a.resume:
            print(f'[{arch}] completed earlier; skipping with --resume', flush=True)
            continue
        if result_file.is_file() and not a.resume:
            raise FileExistsError(f'Already completed phase, do not overwrite: {result_file}')
        if state_file.is_file() and not a.resume:
            raise FileExistsError(f'Partial prior phase exists; re-run with --resume: {state_file}')
        seed_everything(a.seed)
        print(f'[{arch}] Loading model...', flush=True)
        pretrained = a.weights == 'imagenet' and phase != 'finetune'
        if phase == 'finetune':
            previous = model_dir / f'{arch}_best_dev_only.pt'
            payload = torch.load(previous, map_location='cpu', weights_only=True)
            if payload.get('model_architecture') != arch or payload.get('manifest_sha256') != sha:
                raise ValueError('Benchmark checkpoint and current dataset are incompatible')
            if payload.get('training_weights') != 'imagenet':
                raise ValueError('Cannot finetune a randomly initialized benchmark under ImageNet protocol')
            model = core.make_model(arch, 5, pretrained=False)
            model.load_state_dict(payload['model_state_dict'], strict=True)
        else:
            try:
                model = core.make_model(arch, 5, pretrained=pretrained)
            except Exception as exc:
                if pretrained:
                    raise RuntimeError('ImageNet weights unavailable: first connect internet, then rerun with --resume if appropriate. DO NOT silently use random weights.') from exc
                raise
        count_trainable = configure_trainable(model, arch, phase)
        model = model.to(device)
        optimizer = AdamW([p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=1e-4)
        start_epoch, best_score, best_epoch, stale, history = 1, -1., 0, 0, []
        signature = {'phase': phase, 'arch': arch, 'sha': sha, 'batch': a.batch_size,
                     'lr': lr, 'seed': a.seed, 'weights': a.weights,
                     'num_workers': a.num_workers, 'cpu_threads': a.cpu_threads,
                     'epoch_goal': epochs}
        if a.resume and state_file.is_file():
            saved = torch.load(state_file, map_location='cpu', weights_only=True)
            if saved['signature'] != signature:
                raise ValueError('Resume configuration mismatch; use EXACT same arguments')
            model.load_state_dict(saved['model_state_dict'], strict=True)
            optimizer.load_state_dict(saved['optimizer_state_dict'])
            start_epoch, best_score, best_epoch, stale, history = (
                int(saved['epoch'])+1, float(saved['best_score']), int(saved['best_epoch']),
                int(saved['stale']), saved['history'])
            torch.set_rng_state(saved['torch_rng_state'])
            loaders['dev_train'].sampler.generator.set_state(saved['sampler_rng_state'])
            print(f'[{arch}] Resumed after epoch {start_epoch-1}', flush=True)
        checkpoint = model_dir / (f'{arch}_finetuned_best_dev_only.pt' if phase == 'finetune' else f'{arch}_best_dev_only.pt')
        if start_epoch > epochs and result_file.is_file():
            print(f'[{arch}] already completed; skipping', flush=True)
            continue
        if start_epoch > epochs:
            raise RuntimeError('Resume has no remaining epochs but missing summary: investigate')
        print(f'[{arch}] trainable params={count_trainable:,}, epochs={epochs}', flush=True)
        for epoch in range(start_epoch, epochs+1):
            t0 = time.monotonic()
            tr = train_one_epoch(model, loaders['dev_train'], optimizer, device, arch, phase,
                                 2 if phase == 'smoke' and a.max_train_batches is None else a.max_train_batches)
            val = validate(model, loaders['dev_val'], device, classes,
                           2 if phase == 'smoke' and a.max_val_batches is None else a.max_val_batches)
            elapsed = round(time.monotonic()-t0, 2)
            row = {'epoch':epoch, **tr, 'dev_val_loss': round(float(val['loss']),6),
                   'dev_val_accuracy': round(float(val['accuracy']),6),
                   'dev_val_macro_f1': round(float(val['macro_f1']),6),
                   'dev_val_images': val['num_images'], 'seconds': elapsed}
            history.append(row)
            improved = float(val['macro_f1']) > best_score + 1e-10
            if improved:
                best_score, best_epoch, stale = float(val['macro_f1']), epoch, 0
                state_save(checkpoint, make_checkpoint(model, arch, classes, mapping, sha,
                                                        phase, 'imagenet' if phase == 'finetune' else a.weights,
                                                        epoch, val))
            else:
                stale += 1
            csv_write(history_file, history)
            state_save(state_file, {
                'signature':signature,'epoch':epoch,'best_score':best_score,'best_epoch':best_epoch,
                'stale':stale,'history':history,
                'model_state_dict': {k:v.detach().cpu().clone() for k,v in model.state_dict().items()},
                'optimizer_state_dict':optimizer.state_dict(),
                'torch_rng_state':torch.get_rng_state(),
                'sampler_rng_state':loaders['dev_train'].sampler.generator.get_state(),
            })
            print(f'[{arch}] epoch {epoch}/{epochs} | val MacroF1={val["macro_f1"]:.4f} '
                  f'| best={best_score:.4f} | {elapsed:.1f}s', flush=True)
            if phase != 'smoke' and stale >= a.patience:
                print(f'[{arch}] early stopping after {a.patience} stale epochs', flush=True)
                break
        result = {'stage':phase,'architecture':arch,'best_dev_val_macro_f1':best_score,
                  'best_epoch':best_epoch,'epochs_completed':len(history),
                  'checkpoint':checkpoint.relative_to(ROOT).as_posix(),
                  'dataset_manifest_sha256':sha,'weights':a.weights,
                  'trainable_params':count_trainable,'test_used':False,
                  'status':'DEVELOPMENT_ONLY_NOT_FIELD_VALIDATED'}
        json_write(result_file, result)
        print(f'[{arch}] saved best checkpoint: {checkpoint}', flush=True)

    if a.stage == 'benchmark':
        summaries = []
        for arch in ARCHS:
            file = report_dir / f'{arch}_benchmark_summary.json'
            if not file.is_file():
                raise RuntimeError('Missing a benchmark summary. Re-run with --resume')
            data = json.loads(file.read_text(encoding='utf-8'))
            if data.get('weights') != a.weights or data['dataset_manifest_sha256'] != sha:
                raise RuntimeError('Do not mix checkpoint experiments or pretrained/random runs')
            summaries.append(data)
        winner = sorted(summaries, key=lambda x: (-x['best_dev_val_macro_f1'], ARCHS.index(x['architecture'])))[0]
        result = {'run_id':a.run_id,'best_architecture':winner['architecture'],
                  'winner_val_macro_f1':winner['best_dev_val_macro_f1'],
                  'models':summaries,'selection_data':'dev_val ONLY',
                  'test_used':False,'dev_only':True}
        json_write(report_dir / 'benchmark_comparison.json', result)
        print(f'STEP47 BENCHMARK PASS | best={winner["architecture"]} val MacroF1={winner["best_dev_val_macro_f1"]:.4f}', flush=True)
    elif a.stage == 'finetune':
        print('STEP47 FINETUNE PASS | Run Step47 evaluation with --approve-dev-test once; scientific status remains DEV_ONLY.', flush=True)
    else:
        print('STEP47 SMOKE PASS | random weights, two batches, NOT usable for evaluation.', flush=True)
    print(f'Models: {model_dir}\nReports: {report_dir}', flush=True)


if __name__ == '__main__':
    main()
