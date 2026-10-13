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
if explicit_bad or mode == 'refused' or mode == 'audit-failure' and r['operation'] == 'build':
    actions = {n:'not_run' for n in actions}; outcome = 'refused'
if mode == 'failed-fresh-reuse':
    candidate = p(r['source']) / 'compilation.json'
    prior = json.loads(candidate.read_text())
    actions = {n:'reused' if n == 'compile' else 'not_run' for n in actions}
    outcome = 'refused'
if r['operation'] == 'status' and outcome != 'refused':
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
if mode == 'oversized-phase': phases['compile']['seconds'] = 10**400
if mode == 'oversized-history' and complete: phases['compile']['original_seconds'] = 10**400
if mode == 'status-lie' and r['operation'] == 'status':
    phases['queries'].update(action='not_run',status='not_run',basis=None,seconds=0,original_seconds=None)
if mode == 'basis-lie': basis = 'c'*64
if mode == 'unmeasured' and complete:
    for n in ('queries','classification'): phases[n]['original_seconds'] = None
compiler = candidate.parent / 'ccomp' if r['operation'] == 'status' and prior else out / 'ccomp'
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
              basis=b,inputs_stable=True,reuse_reason='fixture semantic validation',
              validation_seconds=0.25,operation_seconds=1.5)
if outcome == 'refused' or mode == 'unmeasured-current': result['validation_seconds'] = None
if mode == 'protocol-lie': result['protocol'] = 'unsupported'
if mode == 'oversized-validation': result['validation_seconds'] = 10**400
if mode == 'oversized-operation': result['operation_seconds'] = 10**400
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


def _failed_fresh_reuse() -> None:
    with _session("audit-failure") as (settings, checkout):
        report = cb.run(replace(settings, fresh=True), checkout)
        ensure(report["outcome"] == "refused"
               and all(phase["action"] == "not_run" for phase in report["phases"].values()),
               "a failed fresh operation may truthfully report no completed phase")
        ensure((settings.out / "controller-result.json").is_file()
               and not (settings.cache / "index.json").exists(),
               "truthful failure is recorded without a reusable index entry")
    with _session("failed-fresh-reuse") as (settings, checkout):
        _compilation_fixture(settings)
        try:
            cb.run(replace(settings, fresh=True), checkout)
        except ValueError as error:
            ensure(str(error) == "fresh request reused earlier execution",
                   "failed fresh reuse is refused by its cold-policy contradiction")
        else:
            raise AssertionError("failed fresh operation claimed compilation reuse")
        ensure(not (settings.out / "controller-result.json").exists()
               and not (settings.cache / "index.json").exists(),
               "cold-policy refusal precedes controller evidence and index publication")


def _unmeasured_and_current_timings() -> None:
    with _session("unmeasured") as (settings, checkout):
        cb.run(settings, checkout)
        warm = cb.run(replace(settings, out=settings.lane_root / "warm"), checkout)
        ensure(all(warm["phases"][name]["original_seconds"] is None
                   for name in ("queries", "classification")), "unmeasured history stays unmeasured")
        ensure(warm["validation_seconds"] == 0.25 and warm["operation_seconds"] == 1.5,
               "controller preserves backend timings")
        ensure(isinstance(warm["controller_operation_seconds"], float), "controller wall time is separate")


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
        ensure(refused["validation_seconds"] is None and refused["operation_seconds"] == 1.5,
               "failed validation may be unmeasured while actual operation time remains")
        warm = cb.run(replace(settings, out=settings.lane_root / "after-failure"), checkout)
        ensure(warm["effective_policy"] == "complete-reuse", "failure retains previous useful index")


def _index_poison_and_stale() -> None:
    with _session() as (settings, checkout):
        cb.run(settings, checkout)
        index = settings.cache / "index.json"
        raw = cb.read_json(index)
        key = next(iter(raw["entries"]))
        raw["entries"][key]["complete"]["out"] = str(settings.source)
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


def _status_consistency() -> None:
    with _session("status-lie") as (settings, checkout):
        cb.run(settings, checkout)
        _refuses(lambda: cb.run(settings, checkout, status=True))


def _compilation_fixture(settings: cb.Settings) -> Path:
    receipt = settings.source / "compilation.json"
    receipt.write_text('{"pending":true,"original":"fixture-producer"}')
    (settings.source / "ccomp").write_text("original fixture compiler")
    return receipt


def _prime_default_compilation() -> None:
    with _session() as (settings, checkout):
        historical = _compilation_fixture(settings)
        original = historical.read_bytes()
        primed = cb.run(replace(settings, reuse_from=historical), checkout, prime=True)
        ensure(primed["status"] == "compilation-validated", "prime authenticates compilation only")
        ensure(primed["phases"]["compile"]["action"] == "reused"
               and all(primed["phases"][name]["action"] == "not_run"
                       for name in ("queries", "kernel", "classification")), "prime executes no qualification")
        ensure(historical.read_bytes() == original and not (settings.out / "ccomp").exists(),
               "prime preserves native compiler evidence")
        warm = cb.run(replace(settings, out=settings.lane_root / "warm"), checkout)
        ensure(warm["effective_policy"] == "compilation-reuse"
               and warm["phases"]["kernel"]["action"] == "executed", "default revalidates compilation before full audit")
        ensure(warm["basis"]["receipt"] == str(historical) and warm["basis"]["original"] == "fixture-producer",
               "default retains original compilation receipt and producer")
        fresh = cb.run(replace(settings, out=settings.lane_root / "fresh", fresh=True), checkout)
        ensure(all(phase["action"] == "executed" for phase in fresh["phases"].values()), "fresh bypasses primed compilation")


def _prime_failure_preserves_basis() -> None:
    with _session("audit-failure") as (settings, checkout):
        historical = _compilation_fixture(settings)
        cb.run(replace(settings, reuse_from=historical), checkout, prime=True)
        index = settings.cache / "index.json"
        retained = settings.out / "controller-compilation.json"
        before = index.read_bytes(), retained.read_bytes(), historical.read_bytes()
        report = cb.run(replace(settings, out=settings.lane_root / "audit-failed"), checkout)
        ensure(report["outcome"] == "refused", "fixture qualification fails")
        ensure(before == (index.read_bytes(), retained.read_bytes(), historical.read_bytes()), "audit failure preserves useful immutable basis")
        inspected = cb.run(replace(settings, out=settings.lane_root / "inspection"), checkout, status=True)
        ensure(inspected["effective_policy"] == "compilation-reuse" and not (settings.lane_root / "inspection").exists(),
               "default remains compilation-only after failure; status stays read-only")


def _prime_refusals_and_stale() -> None:
    with _session() as (settings, checkout):
        _refuses(lambda: cb.run(settings, checkout, prime=True))
        ensure(not settings.out.exists(), "prime requires explicit candidate before output creation")
        malformed = settings.source / "malformed.json"
        malformed.write_text('not json')
        _refuses(lambda: cb.run(replace(settings, reuse_from=malformed), checkout, prime=True))
        ensure(not (settings.cache / "index.json").exists(), "malformed prime supplies no indexed evidence")
        historical = _compilation_fixture(settings)
        owned = replace(settings, out=settings.lane_root / "primed", reuse_from=historical)
        cb.run(owned, checkout, prime=True)
        historical.write_text('changed invalid evidence')
        report = cb.run(replace(settings, out=settings.lane_root / "stale"), checkout)
        ensure(report["effective_policy"] == "fresh", "backend revalidation refuses stale primed bytes")


def _tier_precedence_and_fallback() -> None:
    with _session() as (settings, checkout):
        cb.run(settings, checkout)
        historical = _compilation_fixture(settings)
        cb.run(replace(settings, out=settings.lane_root / "primed", reuse_from=historical), checkout, prime=True)
        index = cb.read_json(settings.cache / "index.json")
        ensure(set(next(iter(index["entries"].values()))) == {"complete", "compilation"}, "both useful bases retained")
        warm = cb.run(replace(settings, out=settings.lane_root / "warm"), checkout, status=True)
        ensure(warm["effective_policy"] == "complete-reuse", "successful qualification takes precedence")
        (settings.out / "controller-result.json").write_text('damaged receipt')
        fallback = cb.run(replace(settings, out=settings.lane_root / "fallback"), checkout, status=True)
        ensure(fallback["effective_policy"] == "compilation-reuse", "damaged complete hint falls back to authenticated compilation hint")


def _legacy_index() -> None:
    with _session() as (settings, checkout):
        cb.run(settings, checkout)
        path = settings.cache / "index.json"
        current = cb.read_json(path)
        path.write_text(json.dumps({"protocol": cb.LEGACY_INDEX_PROTOCOL,
                                    "entries": {key: row["complete"] for key, row in current["entries"].items()}}))
        report = cb.run(replace(settings, out=settings.lane_root / "warm"), checkout)
        ensure(report["effective_policy"] == "complete-reuse", "original complete index remains usable")
        ensure(cb.read_json(path)["protocol"] == cb.INDEX_PROTOCOL, "successful build migrates index atomically")


def _prime_basis_and_tier_refusal() -> None:
    with _session("basis-lie") as (settings, checkout):
        historical = _compilation_fixture(settings)
        _refuses(lambda: cb.run(replace(settings, reuse_from=historical), checkout, prime=True))
        ensure(not (settings.cache / "index.json").exists(), "digest-mismatched validation cannot prime")
    with _session() as (settings, checkout):
        complete = settings.source / "qualified.json"
        complete.write_text('{"pending":false}')
        (settings.source / "ccomp").write_text("fixture compiler")
        _refuses(lambda: cb.run(replace(settings, reuse_from=complete), checkout, prime=True))
        ensure(not (settings.cache / "index.json").exists(), "compilation-only prime never introduces a complete tier")


def _compilation_hint_poison_and_damage() -> None:
    for mutation in ("escaping-output", "damaged-controller-receipt", "unsupported-tier"):
        with _session() as (settings, checkout):
            historical = _compilation_fixture(settings)
            cb.run(replace(settings, reuse_from=historical), checkout, prime=True)
            index = settings.cache / "index.json"
            raw = cb.read_json(index)
            key = next(iter(raw["entries"]))
            if mutation == "escaping-output":
                raw["entries"][key]["compilation"]["out"] = str(settings.source)
                index.write_text(json.dumps(raw))
            elif mutation == "unsupported-tier":
                raw["entries"][key]["pending"] = raw["entries"][key]["compilation"]
                index.write_text(json.dumps(raw))
            else:
                (settings.out / "controller-compilation.json").write_text('damaged')
            report = cb.run(replace(settings, out=settings.lane_root / "inspection"), checkout, status=True)
            ensure(report["outcome"] == "unavailable" and all(phase["action"] == "not_run" for phase in report["phases"].values()),
                   "malformed compilation hints supply no execution or qualification credit")


def _framing(mode: str) -> None:
    with _session(mode) as (settings, checkout):
        _refuses(lambda: cb.run(replace(settings, fresh=mode == "fresh-lie"), checkout))
        ensure(not (settings.cache / "index.json").exists(), "refusal publishes no reusable success")


def _oversized_timing(surface: str) -> None:
    with _session("oversized-" + surface) as (settings, checkout):
        index = settings.cache / "index.json"
        previous: tuple[bytes, bytes] | None = None
        if surface == "history":
            cb.run(settings, checkout)
            previous = index.read_bytes(), (settings.out / "controller-result.json").read_bytes()
        attempted = replace(settings, out=settings.lane_root / "oversized")
        _refuses(lambda: cb.run(attempted, checkout))
        ensure(not (attempted.out / "controller-result.json").exists(),
               "oversized timing refuses before publishing current controller evidence")
        if previous is None:
            ensure(not index.exists(), "oversized timing supplies no reusable index entry")
        else:
            ensure(previous == (index.read_bytes(), (settings.out / "controller-result.json").read_bytes()),
                   "oversized historical timing preserves the previous useful basis")


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
        for payload in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}', '[1]'):
            settings.configuration.write_text(payload)
            _refuses(lambda: cb.run(settings, checkout))
            ensure(not settings.out.exists(), "malformed request refuses before native operation")
        settings.configuration.write_text('{}')
        raw = cb.read_json(settings.driver_manifest)
        raw['files']['../escape.py'] = 'a' * 64
        settings.driver_manifest.write_text(json.dumps(raw))
        _refuses(lambda: cb.run(settings, checkout))
        ensure(not settings.out.exists(), "escaping manifest refuses before launch")


def _unreviewed_imports() -> None:
    for form in ("module", "package", "dynamic", "invalid-python"):
        with _session() as (settings, checkout):
            if form == "module":
                (settings.driver_root / "pathlib.py").write_text("raise RuntimeError('unreviewed')\n")
            elif form == "package":
                package = settings.driver_root / "pathlib"
                package.mkdir()
                (package / "__init__.py").write_text("raise RuntimeError('unreviewed')\n")
            else:
                driver = settings.driver_root / "build.py"
                driver.write_text(driver.read_text() + ("\n__import__(target)\n" if form == "dynamic" else "\nif (\n"))
                manifest = cb.read_json(settings.driver_manifest)
                manifest["files"]["build.py"] = cb.digest(driver)
                settings.driver_manifest.write_text(json.dumps(manifest))
            with patch.object(cb.subprocess, "run", side_effect=AssertionError("unreviewed driver launched")):
                _refuses(lambda: cb.run(settings, checkout))
            ensure(not settings.out.exists(), "import closure refuses before creating output or launching")


def _import_fromlist_closure() -> None:
    for module, expression in (("helpers", "__import__('helpers', fromlist=['hidden'])"),
                               ("helpers", "__import__('helpers', {}, {}, ('hidden',))"),
                               ("helpers.nested", "__import__('helpers.nested', fromlist=['hidden'])"),
                               ("helpers.nested", "__import__('helpers', fromlist=['nested.hidden'])")):
        with _session() as (settings, checkout):
            outer = settings.driver_root / "helpers"
            outer.mkdir()
            (outer / "__init__.py").write_text("# reviewed outer package\n")
            package = settings.driver_root.joinpath(*module.split("."))
            if package != outer:
                package.mkdir()
            (package / "__init__.py").write_text("# reviewed package\n")
            marker = package / "imported"
            (package / "hidden.py").write_text(
                "from pathlib import Path\n(Path(__file__).parent / 'imported').write_text('executed')\n")
            driver = settings.driver_root / "build.py"
            driver.write_text(expression + "\n" + driver.read_text())
            manifest = cb.read_json(settings.driver_manifest)
            member = package.relative_to(settings.driver_root).as_posix()
            manifest["files"].update({"build.py": cb.digest(driver),
                                      "helpers/__init__.py": cb.digest(outer / "__init__.py"),
                                      member + "/__init__.py": cb.digest(package / "__init__.py"),
                                      member + "/hidden.py": cb.digest(package / "hidden.py")})
            settings.driver_manifest.write_text(json.dumps(manifest))
            report = cb.run(settings, checkout)
            ensure(report["outcome"] == "complete" and marker.read_text() == "executed",
                   "reviewed fromlist member actually executes in the fixture driver")
            marker.unlink()
            del manifest["files"][member + "/hidden.py"]
            settings.driver_manifest.write_text(json.dumps(manifest))
            attempted = replace(settings, out=settings.lane_root / "unreviewed")
            with patch.object(cb.subprocess, "run", side_effect=AssertionError("unreviewed fromlist driver launched")):
                _refuses(lambda: cb.run(attempted, checkout))
            ensure(not attempted.out.exists() and not marker.exists(),
                   "fromlist import closure refuses before output creation or launch")


def _unsupported_import_fromlists() -> None:
    for arguments in ("fromlist=members", "fromlist=['*']", "fromlist=[member]",
                      "fromlist=['hidden'], level=1", "{}, {}, ('hidden',), 1",
                      "**{'fromlist':['hidden']}"):
        with _session() as (settings, checkout):
            driver = settings.driver_root / "build.py"
            driver.write_text("__import__('helpers', " + arguments + ")\n" + driver.read_text())
            manifest = cb.read_json(settings.driver_manifest)
            manifest["files"]["build.py"] = cb.digest(driver)
            settings.driver_manifest.write_text(json.dumps(manifest))
            with patch.object(cb.subprocess, "run", side_effect=AssertionError("unsupported fromlist driver launched")):
                _refuses(lambda: cb.run(settings, checkout))
            ensure(not settings.out.exists(), "unsupported import arguments refuse before output creation or launch")


def cases() -> list[Case]:
    return [Case("default-warm-and-job-change", _default_warm),
            Case("unmeasured-history-and-current-timing", _unmeasured_and_current_timings),
            Case("fresh-and-new-profile", _fresh_and_profile),
            Case("failed-fresh-reuse-before-publication", _failed_fresh_reuse),
            Case("pending-compile-only-and-explicit-refusal", _pending_and_explicit),
            Case("index-poison-and-lock-drift", _index_poison_and_stale),
            Case("status-read-only", _status_read_only),
            Case("status-phase-consistency", _status_consistency),
            Case("prime-default-compilation-and-fresh", _prime_default_compilation),
            Case("prime-audit-failure-preserves-basis", _prime_failure_preserves_basis),
            Case("prime-refusal-and-stale-backend-validation", _prime_refusals_and_stale),
            Case("both-tier-precedence-and-damaged-fallback", _tier_precedence_and_fallback),
            Case("legacy-complete-index-migration", _legacy_index),
            Case("prime-original-basis-and-tier-refusal", _prime_basis_and_tier_refusal),
            Case("compilation-hint-poison-and-damage", _compilation_hint_poison_and_damage),
            Case("native-containment-collision-lock", _containment_and_lock),
            Case("json-and-manifest-refusal", _json_and_manifest),
            Case("unreviewed-imports-before-launch", _unreviewed_imports),
            Case("import-fromlist-closure-before-launch", _import_fromlist_closure),
            Case("unsupported-import-fromlists-before-launch", _unsupported_import_fromlists),
            *[Case("oversized-" + surface + "-timing", lambda surface=surface: _oversized_timing(surface))
              for surface in ("phase", "history", "validation", "operation")],
            *[Case(mode, lambda mode=mode: _framing(mode)) for mode in
              ("protocol-lie", "fresh-lie", "pending-lie", "driver-drift", "bool-seconds", "unmeasured-current")]]
