# SPDX-License-Identifier: Apache-2.0
import hashlib, itertools, json, random, statistics, subprocess, sys, time
from pathlib import Path
root = next(parent for parent in Path(__file__).resolve().parents
            if (parent / 'tools/vos/jsonc.py').is_file())
sys.path.insert(0, str(root / 'tools'))
from vos import jsonc
base = '6daf827225308987fbc885ef1196e6c3f3cca028'
baseline = subprocess.check_output(['git', '-C', str(root), 'show', f'{base}:tools/vos/jsonc.py'], text=True)
namespace = {}
exec(compile(baseline, 'baseline-jsonc.py', 'exec'), namespace)
old, new = namespace['strip_comments'], jsonc.strip_comments
count = 0
for length in range(6):
    for chars in itertools.product('"\\/*,}\n a', repeat=length):
        text = ''.join(chars)
        count += 1
        if old(text) != new(text):
            raise RuntimeError(repr((text, old(text), new(text))))
rng = random.Random(92627)
for _ in range(20000):
    text = ''.join(rng.choices('"\\/*,}]\n\r\t [abc012:\u2003\u00a0', k=rng.randrange(400)))
    count += 1
    if old(text) != new(text):
        raise RuntimeError(repr((text, old(text), new(text))))
paths = sorted((root / 'model/config').glob('*.json'))
texts = [p.read_text(encoding='utf-8') for p in paths]
for text in texts:
    if old(text) != new(text):
        raise RuntimeError('corpus output mismatch')
results = {'base': base, 'python': sys.version, 'workers': 1, 'repetitions': 9,
           'candidate_head': subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip(),
           'candidate_source_sha256': hashlib.sha256((root / 'tools/vos/jsonc.py').read_bytes()).hexdigest(),
           'batch_iterations': 40, 'differential_inputs': count,
           'input_files': [p.relative_to(root).as_posix() for p in paths],
           'input_characters': sum(map(len, texts)), 'samples': {}}
for label, decode in [('scanner', False), ('parse', True)]:
    samples = {'old': [], 'new': []}
    for repetition in range(9):
        versions = [('old', old), ('new', new)]
        for name, fn in (versions if repetition % 2 else versions[::-1]):
            start = time.perf_counter()
            for _ in range(40):
                for text in texts:
                    out = fn(text)
                    if decode:
                        json.loads(out)
            samples[name].append((time.perf_counter() - start) / 40)
    results['samples'][label] = samples
    print(label, {name: statistics.median(rows) for name, rows in samples.items()})
output = root / 'out/simplify-json/results.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
print('differential equal:', count, 'inputs; corpus files:', len(paths), 'characters:', results['input_characters'])
