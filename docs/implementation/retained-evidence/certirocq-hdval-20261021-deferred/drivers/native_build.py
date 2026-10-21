import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

WORK = Path('/root/build/lane-certirocq-hdval-adopt-20261020')
BASE = Path('/root/build/fanout-retained/314f14d5fbd20fd942a6/deps-matrix-20261019/lane/certirocq')
REPO = Path('/mnt/c/Users/symbi/source/repos/VerifiedOS')
OPAM = BASE / 'bin/opam'
SWITCH = 'verifiedos-certirocq-0.9.1-ocaml-4.14.4'
PATCH_URL = 'https://github.com/CertiRocq/certirocq/commit/971c1eb1b5f0adecfc280872bd5b71b0d7f33a0f.patch'
PATCH_SHA = 'f350152fd710608b912e9584ae6ef2a005fb8f7d2fc8b7b1e4b15911c9de109b'
ROOT = WORK / 'candidate-root'
LOGS = WORK / 'logs'
LOGS.mkdir(exist_ok=True)
ENV = os.environ.copy()
ENV.update(OPAMROOT=str(ROOT), OPAMJOBS='4', OPAMKEEPBUILDDIR='true', MAKEFLAGS='-j4')
ENV.pop('OPAMNO', None)
ENV.pop('OPAMYES', None)
ENV.pop('OPAMSWITCH', None)
STEPS = []

def digest(path, algorithm='sha256'):
    return hashlib.file_digest(path.open('rb'), algorithm).hexdigest()

def save(name, value):
    (WORK/name).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')

def run(name, args, *, environment=None):
    started = time.monotonic()
    print('START', name, flush=True)
    log_path = LOGS/(name+'.log')
    with log_path.open('w') as log:
        done = subprocess.run([str(x) for x in args], cwd=WORK, env=environment or ENV,
                              stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    record = dict(name=name, argv=[str(x) for x in args], exit_code=done.returncode,
                  seconds=round(time.monotonic()-started,3), log=str(log_path), log_sha256=digest(log_path))
    STEPS.append(record)
    save('build-steps.json', STEPS)
    print('END', name, 'exit='+str(done.returncode), 'seconds='+str(record['seconds']), flush=True)
    if done.returncode:
        print(log_path.read_text()[-7000:], flush=True)
        raise SystemExit(done.returncode)

if digest(OPAM) != '8b24ef2f3f44a31763f54878454fb52afa1f2db7e00abed58b8d4e7ee7e290a6':
    raise RuntimeError('unreviewed opam')
base_env = ENV | {'OPAMROOT':str(BASE/'opam-root'), 'OPAMNO':'1'}
run('baseline-export', [OPAM,'switch','export','--switch='+SWITCH,WORK/'baseline.lock'], environment=base_env)
if (WORK/'baseline.lock').read_bytes() != (REPO/'tools/opam/certirocq.lock').read_bytes():
    raise RuntimeError('retained baseline export differs from qualified lock')
text = (WORK/'baseline.full.lock').read_text()
pattern = re.compile(r'(?ms)^package "rocq-certirocq" \{\n.*?^\}\n')
found = list(pattern.finditer(text))
if len(found) != 1:
    raise RuntimeError('CertiRocq package block not unique')
package = found[0].group()
if 'patches:' in package or 'extra-source ' in package:
    raise RuntimeError('unexpected existing package patch')
extra = ('  patches: ["hd-val-971c1eb.patch"]\n'
         '  extra-source "hd-val-971c1eb.patch" {\n'
         f'    src: "{PATCH_URL}"\n'
         f'    checksum: "sha256={PATCH_SHA}"\n'
         '  }\n')
new_package = package[:-2] + extra + '}\n'
patched = text[:found[0].start()] + new_package + text[found[0].end():]
(WORK/'candidate.input.lock').write_text(patched)
save('selection.json', dict(base_lock_sha256=digest(WORK/'baseline.lock'),
    baseline_full_sha256=digest(WORK/'baseline.full.lock'), candidate_input_sha256=digest(WORK/'candidate.input.lock'),
    base_package_sha256=hashlib.sha256(package.encode()).hexdigest(),
    candidate_package_sha256=hashlib.sha256(new_package.encode()).hexdigest(),
    patch_url=PATCH_URL, patch_sha256=PATCH_SHA, jobs=4,
    unchanged_other_metadata=(text.replace(package,'') == patched.replace(new_package,''))))
if ROOT.exists():
    raise RuntimeError('refusing existing candidate root')
run('init', [OPAM,'init','--bare','--no-setup','--no-opamrc','-y','default','https://opam.ocaml.org'])
run('add-rocq-released', [OPAM,'repository','add','rocq-released','https://rocq-prover.org/opam/released','--dont-select','-y'])
cache = ROOT/'download-cache'
if cache.exists():
    shutil.copytree(BASE/'opam-root/download-cache', cache, dirs_exist_ok=True)
else:
    shutil.copytree(BASE/'opam-root/download-cache', cache)
run('create-switch', [OPAM,'switch','create',SWITCH,'--empty','--no-switch','--repos=rocq-released,default','-y'])
run('import-candidate', [OPAM,'switch','import','--switch='+SWITCH,WORK/'candidate.input.lock','-y','-j4'])
run('set-invariant', [OPAM,'switch','set-invariant','--switch='+SWITCH,'ocaml-base-compiler.4.14.4','-y'])
run('export-candidate', [OPAM,'switch','export','--switch='+SWITCH,'--full','--freeze',WORK/'candidate.full.lock'])
run('export-candidate-ordinary', [OPAM,'switch','export','--switch='+SWITCH,WORK/'candidate.lock'])
save('candidate-build.json', dict(success=True,root=str(ROOT),switch=SWITCH,opam=str(OPAM),
    full_export_sha256=digest(WORK/'candidate.full.lock'),steps=STEPS))
print('CANDIDATE BUILD PASSED', flush=True)