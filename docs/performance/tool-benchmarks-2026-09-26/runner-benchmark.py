# SPDX-License-Identifier: Apache-2.0
"""Compare bounded filesystem placement over the same immutable template."""
import argparse
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
parser.add_argument('--repetitions', type=int, default=7)
parser.add_argument('--jobs', type=int, default=8)
args = parser.parse_args()
base = '69e1d5f6322f80186a3de59e5f03bb248c84616e'
source = subprocess.check_output(['git', '-C', str(root), 'show',
                                  f'{base}:tools/vos/cli/selftest.py']).decode('utf-8')
baseline = types.ModuleType('selftest_baseline')
baseline.__file__ = str(root / 'tools' / 'vos' / 'cli' / 'selftest.py')
sys.modules[baseline.__name__] = baseline
exec(compile(source, baseline.__file__, 'exec'), baseline.__dict__)
output = root / 'out' / 'performance-20260926' / f'runner-{time.time_ns()}'
output.mkdir(parents=True)
cache = output / 'cache'
seed = output / 'seed'
# Template creation lies outside component timings. Use the same immutable input
# for both variants, including source edits not yet committed in this checkout.
candidate._cache_root = lambda _: cache
candidate.build_template(root, seed, args.jobs)
file_count = sum(len(files) for _, _, files in seed.walk())
candidate._publish(seed, cache)
template = cache / 't1'
baseline._cache_root = lambda _: cache
results = {phase: {name: [] for name in ('baseline', 'candidate')}
           for phase in ('git_store', 'first_sandbox', 'warm_template')}
modules = {'baseline': baseline, 'candidate': candidate}
for iteration in range(args.repetitions):
    order = list(modules) if iteration % 2 == 0 else list(reversed(modules))
    for phase in results:
        for name in order:
            module = modules[name]
            target = output / f'{phase}-{iteration}-{name}'
            start = time.perf_counter()
            if phase == 'git_store':
                if name == 'candidate':
                    module._link_tree(template / '.git', target, args.jobs)
                else:
                    module._link_tree(template / '.git', target)
            elif phase == 'first_sandbox':
                if name == 'candidate':
                    module.stand_up(template, target, jobs=args.jobs)
                else:
                    module.stand_up(template, target)
            else:
                module.build_template(root, target, args.jobs)
            elapsed = time.perf_counter() - start
            results[phase][name].append(elapsed)
            print(f'{iteration} {phase} {name}: {elapsed:.6f}s', flush=True)
            candidate.remove_tree(target)
report = {'baseline': base, 'candidate_head': subprocess.check_output(
          ['git', '-C', str(root), 'rev-parse', 'HEAD']).decode().strip(),
          'candidate_scope': 'bounded directory workers in selftest filesystem placement',
          'python': sys.version, 'platform': platform.platform(),
          'command': ' '.join(sys.argv), 'workers': args.jobs,
          'repetitions': args.repetitions, 'template_files_including_git': file_count,
          'machine_concurrency': 'Other isolated optimization agents were active; alternating samples share the same machine and source bytes.',
          'raw_seconds': results,
          'medians': {phase: {name: statistics.median(values) for name, values in names.items()}
                      for phase, names in results.items()}}
(output / 'results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report['medians'], indent=2), flush=True)
print(output, flush=True)