# SPDX-License-Identifier: Apache-2.0
"""Interleaved comparison of the checker's generated-group and sandbox-tree components.

Baseline modules come from `git show BASE:<path>` under other module names; the
candidate modules are this checkout's. Each operation's old and new outputs are
compared before any timing.
"""
import dataclasses
import json
import platform
import statistics
import subprocess
import sys
import time
import types
from collections.abc import Callable
from pathlib import Path

root = next(parent for parent in Path(__file__).resolve().parents
            if (parent / 'tools/vos/elastic_pool_campaign.py').is_file())
sys.path.insert(0, str(root / 'tools'))
from vos import elastic_pool_campaign as new_campaign  # noqa: E402
from vos import wire_formats as new_wire  # noqa: E402
from tests import harness as new_harness  # noqa: E402

BASE = 'd1474a46ecf5a615a69d0b4d2e5305861229c17f'
REPS = 7


def git(*args: str) -> str:
    return subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True,
                          encoding='utf-8', check=True).stdout


def baseline(name: str, rel: str, swap: dict[str, str] | None = None) -> types.ModuleType:
    src = git('show', f'{BASE}:{rel}')
    for old, new in (swap or {}).items():
        if old not in src:
            raise RuntimeError(f'{rel}: {old!r} not found')
        src = src.replace(old, new)
    module = types.ModuleType(name)
    module.__file__ = str(root / rel)
    sys.modules[name] = module
    exec(compile(src, f'{BASE}:{rel}', 'exec'), module.__dict__)
    return module


baseline('base_elastic_pool', 'tools/vos/elastic_pool.py')
old_campaign = baseline('base_elastic_pool_campaign', 'tools/vos/elastic_pool_campaign.py',
                        {'from vos import elastic_pool as p': 'import base_elastic_pool as p'})
old_wire = baseline('base_wire_formats', 'tools/vos/wire_formats.py')
old_harness = baseline('base_harness', 'tools/tests/harness.py')

if old_campaign.histories() != new_campaign.histories():
    raise RuntimeError('campaign histories differ')
if old_campaign.render() != new_campaign.render():
    raise RuntimeError('rendered campaign differs')
if ([dataclasses.asdict(e) for e in old_wire.load(root)]
        != [dataclasses.asdict(e) for e in new_wire.load(root)]):
    raise RuntimeError('wire inventory differs')
if old_wire.emit(root) != new_wire.emit(root):
    raise RuntimeError('emitted wire inventory differs')
new_harness.git_skeleton()  # the once-per-process init, outside the per-tree timing


def tree(harness: types.ModuleType) -> Callable[[], None]:
    def run() -> None:
        with harness.sandbox_tree({'x.md': ''}):
            pass
    return run


ops: dict[str, tuple[Callable[[], object], Callable[[], object]]] = {
    'elastic_pool_campaign.histories()': (old_campaign.histories, new_campaign.histories),
    'wire_formats.load(root)': (lambda: old_wire.load(root), lambda: new_wire.load(root)),
    "sandbox_tree({'x.md': ''})": (tree(old_harness), tree(new_harness)),
}
samples: dict[str, dict[str, list[list[float]]]] = {k: {'old': [], 'new': []} for k in ops}
for old_fn, new_fn in ops.values():  # one discarded warm-up each
    old_fn()
    new_fn()
for rep in range(REPS):
    for name, (old_fn, new_fn) in ops.items():
        order = (('old', old_fn), ('new', new_fn)) if rep % 2 == 0 else (('new', new_fn), ('old', old_fn))
        for side, fn in order:
            wall, cpu = time.perf_counter(), time.process_time()
            fn()
            samples[name][side].append([time.perf_counter() - wall, time.process_time() - cpu])

results: dict[str, dict[str, dict[str, object]]] = {}
for name, sides in samples.items():
    results[name] = {side: {'median_wall_s': round(statistics.median(s[0] for s in rows), 4),
                            'median_cpu_s': round(statistics.median(s[1] for s in rows), 4),
                            'wall_s': [round(s[0], 4) for s in rows]}
                     for side, rows in sides.items()}
report = {'base': BASE, 'candidate': git('rev-parse', 'HEAD').strip(),
          'interpreter': sys.version, 'machine': platform.machine(), 'platform': platform.platform(),
          'git': git('--version').strip(), 'repetitions': REPS, 'workers': 1,
          'order': 'alternating old/new per repetition', 'results': results}
output = root / 'out/checker-fixed-cost/results.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8')
print(json.dumps(report, indent=1))
