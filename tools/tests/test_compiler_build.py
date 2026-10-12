# SPDX-License-Identifier: Apache-2.0
"""Controller policy, native containment and truthful private-driver framing."""

import json
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import compiler_build as cb
from vos import env

_DRIVER = '''import hashlib, json, pathlib, sys
p = pathlib.Path
r = json.loads(p(sys.argv[2]).read_text())
out = p(r['out'])
mode = MODE
candidate = p(r['reuse_from']) if r['reuse_from'] else None
prior = None
if candidate:
    try: prior = json.loads(candidate.read_text())
    except (ValueError, OSError): pass
explicit_bad = candidate and prior is None and r['policy'] == 'explicit'
complete = prior is not None and not prior.get('pending') and not r['profile'] and not r['fresh']
compile_reuse = prior is not None and not r['fresh']
actions = {n: ('reused' if complete or n == 'compile' and compile_reuse else 'executed')
           for n in ('compile','queries','kernel','classification')}
outcome = 'complete'
if explicit_bad or mode == 'refused':
    actions = {n:'not_run' for n in actions}; outcome = 'refused'
if r['operation'] == 'status':
    actions = {n: ('reused' if complete or n == 'compile' and compile_reuse else 'not_run') for n in actions}
    outcome = 'status' if prior else 'unavailable'
effective = ('complete-reuse' if complete else 'compilation-reuse' if compile_reuse else 'fresh')
if outcome in ('unavailable','refused'): effective = 'unavailable'
basis = hashlib.sha256(candidate.read_bytes()).hexdigest() if prior else None
phases = {n:{'action':a,'status':'not_run' if a == 'not_run' else 'passed',
             'basis':basis if a == 'reused' else None,
             'seconds': 2.0 if a == 'executed' else 0,
             'original_seconds': 7.0 if a == 'reused' else None} for n,a in actions.items()}
if mode == 'fresh-lie': phases['kernel'].update(action='reused',basis='a'*64,seconds=0,original_seconds=7)
if mode == 'pending-lie': phases['kernel'].update(action='not_run',status='not_run',seconds=0)
if mode == 'timing-lie': phases['compile']['seconds'] = 99
if mode == 'bool-seconds': phases['compile']['seconds'] = True
compiler = out / 'ccomp'
qualification = candidate if complete else out / 'qualification.json'
receipt = out / 'build-reuse-result.json'
if r['operation'] == 'build' and outcome == 'complete':
    compiler.write_text('fixture compiler')
    if not complete: qualification.write_text(json.dumps({'pending':False,'original':'fixture-producer'}))
b = {'receipt':str(candidate),'receipt_sha256':basis,'original':'fixture-producer',
     'source_revision':r['source_revision'],'producer_manifest':'b'*64,'retention_paths':[str(candidate)]} if prior else None
result = {k:r[k] for k in ('protocol','operation','source_revision','driver_manifest_sha256','policy')}
result.update(outcome=outcome,effective_policy=effective,phases=phases,compiler=str(compiler),
              receipt=str(receipt),qualification_receipt=str(qualification),cache_candidate=str(qualification),
              basis=b,inputs_stable=True,reuse_reason='fixture semantic validation')
if mode == 'protocol-lie': result['protocol'] = 'unsupported'
if r['operation'] == 'build' and outcome == 'complete': receipt.write_text(json.dumps(result))
if mode == 'driver-drift': (p(__file__).parent/'reuse.py').write_text('drift')
p(r['response_json']).write_text(json.dumps(result))
sys.exit(1 if outcome == 'refused' else 0)
'''


@contextmanager
def _session(mode: str = "ordinary") -> Iterator[tuple[cb.Settings, Path]]:
    with tempfile.TemporaryDirectory(prefix="vos-compiler-controller-") as temporary, ExitStack() as stack:
        root = Path(temporary).resolve()
        lane, source, driver, checkout = (root / name for name in ("lane", "source", "driver", "checkout"))
        for path in (lane, source, driver, checkout):
            path.mkdir()
        for name in ("build.py", "qualify.py", "audit.py", "reuse.py"):
            (driver / name).write_text(_DRIVER.replace("MODE", repr(mode)) if name == "build.py" else "# fixture\n")
        manifest = root / "driver.json"
        manifest.write_text(json.dumps({"schema": "verifiedos-contained-compiler-driver/1",
                                       "helper_root": str(driver),
                                       "files": {name: cb.digest(driver / name) for name in
                                                 ("build.py", "qualify.py", "audit.py", "reuse.py")}}))
        lock, config = root / "lock", root / "config.json"
        lock.write_text("fixture lock")
        config.write_text('{}')
        # Production uses the existing guest flock. Host fixture controls model
        # its refusal without invoking the POSIX-only native lock implementation.
        held: set[Path] = set()

        @contextmanager
        def fixture_lock(path: Path, _: str) -> Iterator[None]:
            if path in held:
                raise ValueError("fixture lock held")
            held.add(path)
            try:
                yield
            finally:
                held.remove(path)

        if sys.platform == "win32":
            stack.enter_context(patch.object(env, "hold_lock", fixture_lock))
        yield cb.Settings(source, "a" * 40, lane, lane / "first", lane / "cache", driver,
                          manifest, root / "opam", "fixture-switch", lock, config, "standard"), checkout


def _refuses(fn: Callable[[], object]) -> None:
    try:
        fn()
    except (ValueError, TypeError, OSError, SystemExit):
        return
    raise AssertionError("invalid controller operation was accepted")


def _default_warm() -> None:
    with _session() as (settings, checkout):
        cold = cb.run(settings, checkout)
        warm = cb.run(replace(settings, out=settings.lane_root / "second", jobs=3), checkout)
        ensure(cold["effective_policy"] == "fresh" and warm["effective_policy"] == "complete-reuse", "default warms after priming")
        ensure(all(p["seconds"] == 0 and p["original_seconds"] == 7 for p in warm["phases"].values()), "historical timings stay separate")
        ensure(warm["basis"]["original"] == "fixture-producer", "original producer retained")


def _fresh_and_profile() -> None:
    with _session() as (settings, checkout):
        cb.run(settings, checkout)
        profiled = cb.run(replace(settings, out=settings.lane_root / "profile", profile=True), checkout)
        ensure(profiled["phases"]["compile"]["action"] == "reused" and profiled["phases"]["kernel"]["action"] == "executed", "profile executes new audit")
        fresh = cb.run(replace(settings, out=settings.lane_root / "fresh", fresh=True), checkout)
        ensure(all(p["action"] == "executed" for p in fresh["phases"].values()), "fresh bypasses both tiers")


def _pending_and_explicit() -> None:
    with _session() as (settings, checkout):
        pending = settings.source / "pending.json"
        pending.write_text('{"pending":true}')
        report = cb.run(replace(settings, reuse_from=pending), checkout)
        ensure(report["effective_policy"] == "compilation-reuse" and report["phases"]["kernel"]["action"] == "executed", "pending audit supplies compilation only")
        bad = settings.source / "bad.json"
        bad.write_text('not json')
        refused = cb.run(replace(settings, out=settings.lane_root / "bad", reuse_from=bad), checkout)
        ensure(refused["outcome"] == "refused", "explicit malformed candidate refuses")
        warm = cb.run(replace(settings, out=settings.lane_root / "after-failure"), checkout)
        ensure(warm["effective_policy"] == "complete-reuse", "failure retains previous useful index")


def _index_poison_and_stale() -> None:
    with _session() as (settings, checkout):
        cb.run(settings, checkout)
        index = settings.cache / "index.json"
        raw = cb.read_json(index)
        key = next(iter(raw["entries"]))
        raw["entries"][key]["out"] = str(settings.source)
        index.write_text(json.dumps(raw))
        report = cb.run(replace(settings, out=settings.lane_root / "poison"), checkout)
        ensure(report["effective_policy"] == "fresh" and "stale" in report["candidate_reason"], "poisoned index is only a rejected hint")
        settings.lock.write_text("changed lock")
        report = cb.run(replace(settings, out=settings.lane_root / "changed-lock"), checkout)
        ensure(report["effective_policy"] == "fresh", "lock drift changes candidate context")


def _status_read_only() -> None:
    with _session() as (settings, checkout):
        cb.run(settings, checkout)
        before = {str(p): p.read_bytes() for p in settings.lane_root.rglob('*') if p.is_file()}
        report = cb.run(settings, checkout, status=True)
        after = {str(p): p.read_bytes() for p in settings.lane_root.rglob('*') if p.is_file()}
        ensure(report["outcome"] == "status" and before == after, "status never changes prior lane evidence")


def _framing(mode: str) -> None:
    with _session(mode) as (settings, checkout):
        _refuses(lambda: cb.run(replace(settings, fresh=mode == "fresh-lie"), checkout))
        ensure(not (settings.cache / "index.json").exists(), "refusal publishes no reusable success")


def _containment_and_lock() -> None:
    with _session() as (settings, checkout):
        _refuses(lambda: cb.run(replace(settings, out=settings.source / 'escape'), checkout))
        _refuses(lambda: cb.run(replace(settings, source_revision='main'), checkout))
        _refuses(lambda: cb.run(replace(settings, source=checkout), checkout))
        _refuses(lambda: cb.run(replace(settings, jobs=True), checkout))
        with env.hold_lock(settings.cache, "fixture owner"):
            _refuses(lambda: cb.run(settings, checkout))
        settings.out.mkdir()
        _refuses(lambda: cb.run(settings, checkout))


def _json_and_manifest() -> None:
    with _session() as (settings, checkout):
        for payload in ('{"x":1,"x":2}', '{"x":NaN}', '[1]'):
            settings.configuration.write_text(payload)
            _refuses(lambda: cb.run(settings, checkout))
            ensure(not settings.out.exists(), "malformed request refuses before native operation")
        settings.configuration.write_text('{}')
        raw = cb.read_json(settings.driver_manifest)
        raw['files']['../escape.py'] = 'a' * 64
        settings.driver_manifest.write_text(json.dumps(raw))
        _refuses(lambda: cb.run(settings, checkout))
        ensure(not settings.out.exists(), "escaping manifest refuses before launch")


def cases() -> list[Case]:
    return [Case("default-warm-and-job-change", _default_warm),
            Case("fresh-and-new-profile", _fresh_and_profile),
            Case("pending-compile-only-and-explicit-refusal", _pending_and_explicit),
            Case("index-poison-and-lock-drift", _index_poison_and_stale),
            Case("status-read-only", _status_read_only),
            Case("native-containment-collision-lock", _containment_and_lock),
            Case("json-and-manifest-refusal", _json_and_manifest),
            *[Case(mode, lambda mode=mode: _framing(mode)) for mode in
              ("protocol-lie", "fresh-lie", "pending-lie", "driver-drift", "bool-seconds")]]
