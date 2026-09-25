import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
import types
root = next(path for path in Path(__file__).resolve().parents if (path / "tools" / "run.py").is_file() and (path / ".git").exists())
sys.path.insert(0, str(root / 'tools'))
from vos.cli import selftest as candidate
out = root / 'out' / 'performance-20260919' / f'replay-runner-{time.time_ns()}'
out.mkdir(parents=True, exist_ok=True)
base_source = subprocess.check_output(['git', '-C', str(root), 'show', '7a06adca:tools/vos/cli/selftest.py']).decode('utf-8')
baseline = types.ModuleType('runner_baseline')
sys.modules[baseline.__name__] = baseline
exec(compile(base_source, str(root / 'tools/vos/cli/selftest.py'), 'exec'), baseline.__dict__)
guarded = types.ModuleType('runner_guarded')
sys.modules[guarded.__name__] = guarded
guard_source = (root / 'tools/vos/cli/selftest.py').read_text(encoding='utf-8')
reset = '        (into / ".git" / "index").unlink(missing_ok=True)\n'
anchor = '    if snapshot is not None:\n        # a snapshot swept'
if reset not in guard_source or anchor not in guard_source:
    raise RuntimeError('repair source no longer matches benchmark variant')
guard_source = guard_source.replace(reset, '').replace(anchor, '    if snapshot is not None and _same_index_rules(snapshot, into, old_files, placed):\n        # a snapshot swept')
exec(compile(guard_source, str(root / 'tools/vos/cli/selftest.py'), 'exec'), guarded.__dict__)
def same_index_rules(snapshot, template, old_files, files):
    names = {name for name in files if name.rsplit('/', 1)[-1] in {'.gitattributes', '.gitignore'}}
    old_names = {name for name in old_files if name.rsplit('/', 1)[-1] in {'.gitattributes', '.gitignore'}}
    return names == old_names and all((snapshot / name).read_bytes() == (template / name).read_bytes() for name in names)
guarded._same_index_rules = same_index_rules
source = out / 'source'
baseline._cache_root = lambda repo: out / 'source-cache'
baseline.build_template(root, source, 8)
(source / baseline._MANIFEST).unlink()
modules = {'baseline': baseline, 'reset': candidate, 'guarded': guarded}
results = {name: [] for name in modules}
for name, module in modules.items():
    cache = out / f'cache-{name}'
    module._cache_root = lambda repo, cache=cache: cache
    target = out / f'initial-{name}'
    module.build_template(source, target, 8)
    module._publish(target, cache)
for iteration in range(5):
    target = source / 'README.md'
    data = target.read_bytes() + f'\nprofile edit {iteration}\n'.encode()
    target.unlink()
    target.write_bytes(data)
    names = list(modules)
    if iteration % 2:
        names.reverse()
    for name in names:
        module = modules[name]
        target = out / f'changed-{iteration}-{name}'
        start = time.perf_counter()
        counts = module.build_template(source, target, 8)
        elapsed = time.perf_counter() - start
        results[name].append(elapsed)
        module._publish(target, module._cache_root(source))
        print(f'changed {iteration} {name}: {elapsed:.3f}s {counts}', flush=True)
report = {'base': '7a06adca', 'candidate_base': 'bfc6d0d', 'candidate_scope': 'selftest index-detachment repair and regression fixtures', 'python': sys.version, 'jobs': 8, 'repetitions': 5, 'raw_seconds': results, 'medians': {name: statistics.median(times) for name, times in results.items()}}
(out / 'results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report['medians'], indent=2), flush=True)
