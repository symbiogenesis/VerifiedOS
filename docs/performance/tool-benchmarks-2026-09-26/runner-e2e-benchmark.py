# SPDX-License-Identifier: Apache-2.0
"""Time equivalent selected-rule selftests, including setup and cleanup."""
import argparse
import contextlib
import io
import json
import platform
import statistics
import subprocess
import sys
import time
import types
from pathlib import Path
root = next(path for path in Path(__file__).resolve().parents
            if (path / 'tools' / 'run.py').is_file() and (path / '.git').exists())
sys.path.insert(0, str(root / 'tools'))
from vos.cli import selftest as candidate
parser = argparse.ArgumentParser()
parser.add_argument('--seed-cache', type=Path)
parser.add_argument('--repetitions', type=int, default=3)
parser.add_argument('--jobs', type=int, default=5)
args = parser.parse_args()
base = '69e1d5f6322f80186a3de59e5f03bb248c84616e'
source = subprocess.check_output(['git', '-C', str(root), 'show',
                                  f'{base}:tools/vos/cli/selftest.py']).decode('utf-8')
baseline = types.ModuleType('selftest_baseline')
baseline.__file__ = str(root / 'tools' / 'vos' / 'cli' / 'selftest.py')
sys.modules[baseline.__name__] = baseline
exec(compile(source, baseline.__file__, 'exec'), baseline.__dict__)
output = root / 'out' / 'performance-20260926' / f'runner-e2e-{time.time_ns()}'
output.mkdir(parents=True)
cache = output / 'cache'
if args.seed_cache:
    candidate._cache_root = lambda _: args.seed_cache
else:
    candidate._cache_root = lambda _: cache
seed = output / 'seed'
candidate.build_template(root, seed, args.jobs)
candidate._publish(seed, cache)
candidate._cache_root = baseline._cache_root = lambda _: cache
modules = {'baseline': baseline, 'candidate': candidate}
results = {name: [] for name in modules}
verdict = None
for iteration in range(args.repetitions):
    order = list(modules) if iteration % 2 == 0 else list(reversed(modules))
    for name in order:
        log = io.StringIO()
        argv = ['--rule', 'K-52', '--jobs', str(args.jobs),
                '--sandbox', str(output / f'sandbox-{iteration}-{name}')]
        start = time.perf_counter()
        with contextlib.redirect_stdout(log):
            code = modules[name].main(argv)
        elapsed = time.perf_counter()-start
        text = log.getvalue()
        (output / f'{iteration}-{name}.log').write_text(text, encoding='utf-8')
        if code:
            raise RuntimeError(f'{name} failed: see {output / f"{iteration}-{name}.log"}')
        diagnostics = text[text.index('ok: the unmutated sandbox'):]
        if verdict is None:
            verdict = diagnostics
        if verdict != diagnostics:
            raise RuntimeError('ordered mutation diagnostics differ')
        results[name].append(elapsed)
        print(f'{iteration} {name}: {elapsed:.6f}s; verdict and diagnostics equal', flush=True)
report = {'baseline': base, 'candidate_head': subprocess.check_output(
          ['git', '-C', str(root), 'rev-parse', 'HEAD']).decode().strip(),
          'candidate_scope': 'bounded directory workers in selftest filesystem placement',
          'python': sys.version, 'platform': platform.platform(),
          'command': ' '.join(sys.argv), 'scope': f'selftest --rule K-52 --jobs {args.jobs}; setup, pristine baseline, five mutants, registry coverage, cleanup',
          'workers': args.jobs, 'repetitions': args.repetitions,
          'machine_concurrency': 'Other isolated optimization agents were active; alternating samples share the same machine and source bytes.',
          'raw_seconds': results,
          'medians': {name: statistics.median(values) for name, values in results.items()},
          'diagnostics_identical': True, 'verdicts': 'all passed'}
(output / 'results.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
print(json.dumps(report['medians'], indent=2), flush=True)
print(output, flush=True)