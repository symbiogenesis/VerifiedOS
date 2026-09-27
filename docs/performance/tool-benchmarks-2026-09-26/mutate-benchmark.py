# SPDX-License-Identifier: Apache-2.0
"""Compare mutation populations against the historical scanner on identical text."""
import argparse
import dataclasses
import hashlib
import json
import platform
import random
import statistics
import subprocess
import sys
import time
import types
from pathlib import Path

BASE = '69e1d5f6322f80186a3de59e5f03bb248c84616e'
ROOT = next(p for p in Path(__file__).resolve().parents if (p/'tools/vos/mutate.py').is_file())
sys.path.insert(0, str(ROOT/'tools'))
from vos import mutate


def historical():
    code = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{BASE}:tools/vos/mutate.py'])
    module = types.ModuleType('baseline_mutate')
    sys.modules[module.__name__] = module
    exec(compile(code, 'baseline_mutate.py', 'exec'), module.__dict__)
    return module


def fields(population):
    return [dataclasses.astuple(site) for site in population]


def measure(inputs, repeat, old):
    wanted = [fields(old.mutants(text, mutate.lane_of(name), name)) for name, text in inputs]
    actual = [fields(mutate.mutants(text, mutate.lane_of(name), name)) for name, text in inputs]
    if wanted != actual:
        raise AssertionError('mutation populations differ')
    samples = {'baseline': [], 'candidate': []}
    for turn in range(repeat):
        order = [('baseline', old), ('candidate', mutate)]
        for label, module in order if turn % 2 == 0 else reversed(order):
            start = time.perf_counter()
            for name, text in inputs:
                module.mutants(text, mutate.lane_of(name), name)
            samples[label].append(time.perf_counter() - start)
    return {'sources': len(inputs), 'characters': sum(len(s) for _, s in inputs),
            'mutants': sum(map(len, actual)), 'equal': True, 'samples_seconds': samples,
            'median_seconds': {k: statistics.median(v) for k, v in samples.items()}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repeat', type=int, default=7)
    parser.add_argument('--out', type=Path, default=ROOT/'out/performance-20260926/replay-mutate-results.json')
    args = parser.parse_args()
    old = historical()
    rng = random.Random(260926)
    alphabet = 'a/*()"\\\n\r '
    for _ in range(20000):
        source = ''.join(rng.choices(alphabet, k=rng.randrange(100)))
        for lane in (*mutate.LANES, 'unknown'):
            if old.mask(source, lane) != mutate.mask(source, lane):
                raise AssertionError(f'masks differ: {lane} {source!r}')
    tracked = subprocess.check_output(['git','-C',str(ROOT),'ls-files','proofs','model'], text=True).splitlines()
    inputs = [(name, (ROOT/name).read_text(encoding='utf-8')) for name in tracked if name.endswith(('.v','.sail'))]
    report = {'baseline_revision': BASE, 'candidate_revision': subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
              'candidate_sha256': hashlib.sha256((ROOT/'tools/vos/mutate.py').read_bytes()).hexdigest(),
              'python': sys.version, 'platform': platform.platform(), 'workers': 1,
              'command': 'python docs/performance/tool-benchmarks-2026-09-26/mutate-benchmark.py --repeat 7',
              'repetitions': args.repeat, 'fuzz_masks': 60000,
              'inputs': {name: hashlib.sha256(text.encode()).hexdigest() for name,text in inputs},
              'corpus': measure(inputs,args.repeat,old),
              'scaling': {str(n): measure([('synthetic.v','Definition f := true + 1.\n'*n)],args.repeat,old) for n in (2000,8000)}}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'inputs'},indent=2))

if __name__ == '__main__':
    main()
