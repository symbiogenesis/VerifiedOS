# SPDX-License-Identifier: Apache-2.0
"""Template index reuse preserves sandbox bytes, pins and copy-on-write isolation.

A case's checker run stops after its rule's group, and only a survivor runs whole.
"""

import contextlib
import io
import json
import os
import stat
import subprocess
import tempfile
from concurrent.futures import Future
from pathlib import Path
from queue import Queue
from threading import Barrier, Event, Lock
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import check
from tests.harness import Case, ensure, sandbox_tree
from tests.test_checks import _REGISTER_MIN, _context, _findings_under
from vos import corpus, timings
from vos.checks import Context, meta
from vos.cli import selftest
from vos.seeded import KILLED, SURVIVED, UNSEEDED, Verdict
from vos.sharding import Shard

# Each case writes only under the sandbox tree it creates, template caches included,
# and patches only inside a `with`, so the cases share no state, and a sharded run
# spreads them over every shard (vos/cli/test.py).
INDEPENDENT_CASES = True


def _shards_cover_cases_and_repair_once() -> None:
    # The shards and --repair-only together are the unsharded run: every case once,
    # and the repair path once, in the run that selects no case.
    shards = [Shard(i, 4) for i in range(1, 5)]
    parts = [selftest._select_cases(None, shard) for shard in shards]
    ensure(sorted(id(case) for part in parts for case in part)
           == sorted(id(case) for case in selftest.CASES),
           "each authored mutant must run exactly once across shards")
    ensure(not any(selftest._needs_repair(part, shard)
                   for part, shard in zip(parts, shards, strict=True)),
           "no shard runs the repair path, whichever cases its partition holds")
    alone = selftest._select_cases(None, None, repair_only=True)
    ensure(alone == [] and selftest._needs_repair(alone, None, repair_only=True),
           "--repair-only runs the repair path and no case")
    ensure(selftest._needs_repair(selftest.CASES, None),
           "the unsharded run carries the repair path the shards leave to --repair-only")
    ensure(selftest._select_cases(None, Shard(1, 1)) == selftest.CASES,
           "one shard must select the full suite")
    for rule, shard, repair_only in (("K-01", Shard(1, 4), False), ("K-01", None, True),
                                     (None, Shard(1, 4), True)):
        try:
            selftest._select_cases(rule, shard, repair_only)
        except ValueError:
            pass
        else:
            raise AssertionError("a rule filter or a shard must not silently narrow or "
                                 "widen another selection")
    for argv in (["--repair-only", "--shard", "1/4"], ["--repair-only", "--rule", "K-01"]):
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                selftest.main(argv)
            except SystemExit as err:
                ensure(err.code == 2, f"{argv!r} must be an argument error")
            else:
                raise AssertionError(f"the CLI accepted {argv!r}")


class _Baseline:
    """An unmutated sandbox whose checker answers with one exit code."""

    def __init__(self, code: int) -> None:
        self.code = code

    def check(self, fix: bool = False,
              through: str | None = None) -> tuple[int, list[str], list[str]]:
        ensure(not fix and through is None, "the baseline is one whole read-only run")
        return self.code, ["FAIL K-01: broken before any mutant"] if self.code else [], []

    def reset(self) -> None:
        pass


def _repair_only_runs_beside_the_baseline() -> None:
    # --repair-only reports the repair path and the registry, not an empty population
    # as a vacuous pass, and a failing baseline still discards the repair report. Any
    # other run selecting no case is that vacuous pass, and is refused.
    ran: list[str] = []

    def repair(_ready: Future[selftest.Sandbox]) -> tuple[list[str], list[str]]:
        ran.append("repair")
        return [], ["--- the repair path ---", "  ok: held"]

    for code, repair_only in ((0, True), (1, True), (0, False)):
        ran.clear()
        printed = io.StringIO()
        boxes: Queue[selftest.Sandbox | BaseException] = Queue()
        with patch.object(selftest, "_repair_path", repair), \
                patch.object(selftest, "_registry_coverage", return_value=[]), \
                contextlib.redirect_stdout(printed):
            result = selftest._run([], cast("selftest.Sandbox", _Baseline(code)), boxes,
                                   Future(), 1, True, repair_only=repair_only)
        out = printed.getvalue()
        expected = code if repair_only else 1
        ensure(result == expected and ran == ["repair"],
               f"baseline exit {code}, --repair-only {repair_only}, gave {result} with the "
               f"repair path run {ran}: {out}")
        if not repair_only:
            ensure("FAIL every one of 0 mutant(s) was stillborn" in out,
                   f"an empty selection outside --repair-only is a vacuous pass: {out}")
        elif code == 0:
            ensure("FAIL" not in out and "  ok: held" in out
                   and "the repair path holds and the registry is covered" in out,
                   f"the repair path alone decides the run: {out}")
        else:
            ensure("  ok: held" not in out, f"a failing baseline discards the repair: {out}")
    no_case: list[selftest.Case] = []
    for selected, repairable in ((no_case, False), ([selftest.CASES[0]], True)):
        try:
            selftest._run(selected, cast("selftest.Sandbox", _Baseline(0)), Queue(),
                          Future(), 1, repairable, repair_only=True)
        except ValueError:
            pass
        else:
            raise AssertionError("--repair-only must run the repair path and no case, "
                                 f"not {len(selected)} case(s) with repairable {repairable}")


def _shard_leaves_the_repair_path_to_repair_only() -> None:
    # A shard's closing line says whose the repair path is; a --rule run whose rule
    # carries no --fix branch says the path had nothing to prove.
    def killed(case: selftest.Case, _box: selftest.Sandbox) -> Verdict:
        return Verdict(selftest.Seeding(case[0], case[1]), KILLED,
                       f"the checker reported {case[0]}")

    for sharded, held in ((True, "the repair path is left to --repair-only"),
                          (False, "the repair path had nothing to prove")):
        printed = io.StringIO()
        boxes: Queue[selftest.Sandbox | BaseException] = Queue()
        boxes.put(cast("selftest.Sandbox", _Baseline(0)))
        with patch.object(selftest, "_verdict", killed), \
                patch.object(selftest, "_registry_coverage", return_value=[]), \
                contextlib.redirect_stdout(printed):
            result = selftest._run([selftest.CASES[0]], cast("selftest.Sandbox", _Baseline(0)),
                                   boxes, Future(), 1, False, sharded=sharded)
        out = printed.getvalue()
        ensure(result == 0 and f"killed its mutant, {held}, and the registry" in out,
               f"sharded {sharded} must close on {held!r}, got {result}: {out}")


def _baseline_overlaps_setup_and_never_enters_the_case_queue() -> None:
    setup_started, baseline_started = Event(), Event()
    seeded: list[str] = []
    checker_paths: list[Path] = []
    placed: list[selftest.Sandbox] = []
    place = selftest.stand_up

    with tempfile.TemporaryDirectory(prefix="vos-selftest-setup-") as td:
        estate = Path(td) / "estate"
        template = estate / "template"

        def build(_repo: Path, into: Path, _jobs: int) -> tuple[int, int]:
            (into / ".git").mkdir(parents=True)
            (into / "subject.txt").write_bytes(b"pristine\n")
            return 1, 0

        def stand_up(source: Path, target: Path, fix_ok: bool = False, *,
                     jobs: int = 1) -> selftest.Sandbox:
            setup_started.set()
            ensure(baseline_started.wait(10), "case setup blocked the baseline")
            box = place(source, target, fix_ok, jobs=jobs)
            placed.append(box)
            return box

        def check(box: selftest.Sandbox, fix: bool = False,
                  through: str | None = None) -> tuple[int, list[str], list[str]]:
            ensure(not fix, "this selection owns no repair sandbox")
            checker_paths.append(box.path)
            if through is None:
                ensure(box.path == template and not box.touched,
                       "the baseline must read the immutable template")
                ensure(setup_started.wait(10), "baseline started without overlapping setup")
                baseline_started.set()
                return 0, [], []
            ensure(box.path != template, "a case mutated the baseline template")
            ensure(box.read("subject.txt") == through, "a case saw another worker's mutant")
            return 1, [], [through]

        def seed(rule: str) -> selftest.Mutation:
            def apply(box: selftest.Sandbox) -> bool:
                seeded.append(rule)
                return box.write("subject.txt", rule)
            return apply

        selected = [(rule, "private bytes", seed(rule)) for rule in ("K-01", "K-02")]
        printed = io.StringIO()
        with (patch.object(selftest, "build_template", build),
              patch.object(selftest, "stand_up", stand_up),
              patch.object(selftest.Sandbox, "check", check),
              patch.object(selftest, "_select_cases", return_value=selected),
              patch.object(selftest, "_needs_repair", return_value=False),
              patch.object(selftest, "_registry_coverage", return_value=[]),
              contextlib.redirect_stdout(printed)):
            result = selftest.main(["--jobs", "2", "--sandbox", str(estate), "--keep"])
        ensure(result == 0 and sorted(seeded) == ["K-01", "K-02"],
               f"the complete selected population must run: {printed.getvalue()}")
        ensure(len(placed) == 2 and checker_paths.count(template) == 1,
               "setup needs one sandbox per case worker and one template baseline read")
        ensure((template / "subject.txt").read_bytes() == b"pristine\n"
               and all(box.read("subject.txt") == "pristine\n" and not box.touched
                       for box in placed),
               "the immutable baseline and every reset worker must retain pristine bytes")
        out = printed.getvalue()
        ensure(out.index("K-01: private bytes") < out.index("K-02: private bytes"),
               "concurrent cases must keep selection order in the report")


def _repair_only_constructs_no_case_sandbox() -> None:
    placed: list[tuple[Path, bool, int]] = []
    with tempfile.TemporaryDirectory(prefix="vos-selftest-repair-setup-") as td:
        estate = Path(td) / "estate"
        template = estate / "template"

        def build(_repo: Path, into: Path, _jobs: int) -> tuple[int, int]:
            into.mkdir(parents=True)
            return 0, 0

        def stand_up(source: Path, target: Path, fix_ok: bool = False, *,
                     jobs: int = 1) -> selftest.Sandbox:
            placed.append((target, fix_ok, jobs))
            return selftest.Sandbox(target, source, fix_ok)

        def repair(ready: Future[selftest.Sandbox]) -> tuple[list[str], list[str]]:
            ensure(ready.result().fix_ok, "the repair worker must have private copies")
            return [], ["--- the repair path ---", "  ok: held"]

        def check(box: selftest.Sandbox, fix: bool = False,
                  through: str | None = None) -> tuple[int, list[str], list[str]]:
            ensure(box.path == template and not fix and through is None,
                   "repair-only still needs one complete immutable baseline")
            return 0, [], []

        with (patch.object(selftest, "build_template", build),
              patch.object(selftest, "stand_up", stand_up),
              patch.object(selftest.Sandbox, "check", check),
              patch.object(selftest, "_repair_path", repair),
              patch.object(selftest, "_registry_coverage", return_value=[]),
              contextlib.redirect_stdout(io.StringIO())):
            result = selftest.main(["--repair-only", "--jobs", "3", "--sandbox",
                                    str(estate), "--keep"])
        ensure(result == 0 and placed == [(estate / "w0", True, 3)],
               f"repair-only must construct just its repair sandbox, got {placed}")


def _failed_case_setup_wakes_every_waiting_case() -> None:
    boxes: Queue[selftest.Sandbox | BaseException] = Queue()
    boxes.put(OSError("sandbox placement failed"))
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            selftest._run(selftest.CASES[:3], cast("selftest.Sandbox", _Baseline(0)),
                          boxes, None, 3, False)
        except OSError as err:
            ensure(str(err) == "sandbox placement failed",
                   "setup failure must preserve its original diagnostic")
        else:
            raise AssertionError("a missing worker must fail rather than strand waiting cases")


def _checked_bytecode_reads_same_metadata_mutants_and_preserves_the_template() -> None:
    sources = {
        "tools/check.py": ('from vos import subject\nREPORT = "pass K-25: checker"\n'
                           'CODE = 0\ndef main():\n'
                           '    print(subject.REPORT)\n    print(REPORT)\n'
                           '    return max(CODE, subject.CODE)\n'),
        "tools/vos/__init__.py": "",
        "tools/vos/subject.py": 'REPORT = "pass K-24: subject"\nCODE = 0\n',
    }
    with tempfile.TemporaryDirectory(prefix="vos-selftest-bytecode-") as td:
        root = Path(td)
        template = root / "template"
        (template / ".git").mkdir(parents=True)
        for rel, text in sources.items():
            path = template / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="")
        ensure(selftest._warm_bytecode(template, 2) == len(sources),
               "each checker tool must receive a bytecode cache")
        caches = {path.relative_to(template): path.read_bytes()
                  for path in template.rglob("*.pyc")}
        ensure(len(caches) == len(sources)
               and all(int.from_bytes(data[4:8], "little") == 3 for data in caches.values()),
               "every prepared cache must require source-hash validation")
        box = selftest.stand_up(template, root / "worker")
        ensure(box.check()[0] == 0, "the compiled baseline must retain its verdict")

        for rule, rel in (("K-24", "tools/vos/subject.py"), ("K-25", "tools/check.py")):
            def seed(target: selftest.Sandbox, rel: str = rel) -> bool:
                path = target.path / rel
                original = path.stat()
                changed = target.write(rel, target.read(rel).replace("pass", "FAIL")
                                       .replace("CODE = 0", "CODE = 1"))
                os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
                ensure(path.stat().st_size == original.st_size
                       and path.stat().st_mtime_ns == original.st_mtime_ns,
                       "the mutant must defeat size-and-timestamp cache validation")
                return changed

            verdict = selftest._verdict((rule, "same metadata source mutant", seed), box)
            ensure(verdict.outcome == KILLED,
                   f"cached imports must read the source mutant: {verdict.detail}")
            ensure(all((template / name).read_bytes() == data
                       and (box.path / name).read_bytes() == data
                       for name, data in caches.items()),
                   "fresh imports must not replace or edit shared bytecode caches")
            box.reset()
            ensure(box.check()[0] == 0, "reset must restore the original source verdict")

        ensure(box.delete("tools/vos/subject.py"), "the imported source must be present")
        code, out, failed = box.check()
        ensure(code != 0 and not failed and any("ImportError" in line for line in out),
               "an orphaned bytecode cache must not replace a deleted source")
        box.reset()
        cache = next(path for path in box.path.rglob("*.pyc")
                     if path.name.startswith("subject."))
        cache.unlink()
        cache.write_bytes(b"invalid bytecode")
        ensure(box.check()[0] == 0 and cache.read_bytes() == b"invalid bytecode",
               "a malformed cache must fall back to source without publishing bytecode")
        ensure(all((template / name).read_bytes() == data for name, data in caches.items()),
               "cache fallback must preserve the template")


def _bytecode_preparation_does_not_turn_unused_syntax_into_a_finding() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-selftest-bytecode-refusal-") as td:
        template = Path(td)
        (template / "tools/vos").mkdir(parents=True)
        (template / "tools/check.py").write_bytes(b"def main():\n    return 0\n")
        unused = template / "tools/vos/unused.py"
        unused.write_bytes(b"this is not valid Python !!!\n")
        printed = io.StringIO()
        with contextlib.redirect_stderr(printed), contextlib.redirect_stdout(printed):
            compiled = selftest._warm_bytecode(template, 2)
        ensure(compiled == 1 and not printed.getvalue()
               and selftest.Sandbox(template, template).check()[0] == 0,
               "unused malformed source must retain its ordinary import behavior")


def _git(root: Path, *args: str) -> bytes:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          check=False, timeout=60)
    ensure(done.returncode == 0, f"git {args}: {done.stderr!r}")
    return done.stdout


def _refresh_index_without_changing_snapshot() -> None:
    with sandbox_tree({".gitignore": "out/\n", ".gitattributes": "* -text\n",
                       "a.txt": "old\n", "gone.txt": "gone\n"}) as root:
        output = root / "out"
        cache = output / "cache"
        with patch.object(selftest, "_cache_root", return_value=cache):
            selftest.build_template(root, output / "first", 2)
            selftest._publish(output / "first", cache)
            snapshot = cache / "t1"
            old_index = (snapshot / ".git" / "index").read_bytes()
            (root / "a.txt").write_bytes(b"new\r\n")
            (root / "gone.txt").unlink()
            (root / "new.txt").write_bytes(b"added\n")
            with patch.object(selftest, "_link_tree", wraps=selftest._link_tree) as carry:
                selftest.build_template(root, output / "second", 2)
            ensure(carry.call_count == 1, "a changed source must still carry its Git object store")
        fresh = output / "second"
        ensure((fresh / "a.txt").read_bytes() == b"new\r\n", "template lost working-tree bytes")
        ensure(corpus.staged_bytes(fresh, "a.txt") == b"new\r\n",
               "refreshed index retained the old blob")
        ensure(corpus.staged_bytes(fresh, "new.txt") == b"added\n", "new blob was not indexed")
        ensure(corpus.staged_bytes(fresh, "gone.txt") is None, "deleted blob remained indexed")
        ensure((snapshot / "a.txt").read_bytes() == b"old\n", "refresh wrote through source links")
        ensure((snapshot / ".git" / "index").read_bytes() == old_index,
               "Git index refresh modified the prior snapshot")


def _failed_carry_rebuilds_index() -> None:
    with sandbox_tree({".gitignore": "out/\n", "a.txt": "kept\n"}) as root:
        output = root / "out"
        cache = output / "cache"
        with patch.object(selftest, "_cache_root", return_value=cache):
            selftest.build_template(root, output / "first", 2)
            selftest._publish(output / "first", cache)

            def interrupted(_source: Path, target: Path, _jobs: int = 1) -> None:
                target.mkdir(parents=True)
                (target / "partial").touch()
                raise OSError("snapshot disappeared")

            with patch.object(selftest, "_link_tree", side_effect=interrupted):
                selftest.build_template(root, output / "second", 2)
        fresh = output / "second"
        ensure(corpus.staged_bytes(fresh, "a.txt") == b"kept\n", "failed carry did not rebuild")
        ensure(not (fresh / ".git" / "partial").exists(), "partial Git store survived fallback")


def _attribute_change_matches_cold_index() -> None:
    normalized = "* text=auto eol=lf\n"
    scenarios: list[tuple[str, dict[str, str], str, str | None]] = [
        ("changed", {".gitattributes": "* -text\n"}, ".gitattributes", normalized),
        ("added", {".gitattributes": "* -text\n"}, "docs/.gitattributes", normalized),
        ("deleted", {".gitattributes": normalized, "docs/.gitattributes": "* -text\n"},
         "docs/.gitattributes", None),
        ("nested", {".gitattributes": "* -text\n", "docs/.gitattributes": "* -text\n"},
         "docs/.gitattributes", normalized),
    ]
    for name, attributes, changed, after in scenarios:
        with sandbox_tree({".gitignore": "out/\n", "docs/a.txt": "first\r\nsecond\r\n",
                           **attributes}) as root:
            output = root / "out"
            cache = output / "cache"
            with patch.object(selftest, "_cache_root", return_value=cache), \
                    patch.object(selftest, "_GRACE_NS", 0):
                selftest.build_template(root, output / "first", 2)
                selftest._publish(output / "first", cache)
                if after is None:
                    (root / changed).unlink()
                else:
                    (root / changed).write_bytes(after.encode())
                selftest.build_template(root, output / "warm", 2)
            with patch.object(selftest, "_cache_root", return_value=output / "empty-cache"):
                selftest.build_template(root, output / "cold", 2)
            warm = corpus.staged_bytes(output / "warm", "docs/a.txt")
            cold = corpus.staged_bytes(output / "cold", "docs/a.txt")
            ensure(warm == cold == b"first\nsecond\n",
                   f"{name} attributes must match cold indexing: warm={warm!r}, cold={cold!r}")


def _ignore_change_matches_cold_index() -> None:
    with sandbox_tree({".gitignore": "out/\n", "a.txt": "kept on disk\n"}) as root:
        output = root / "out"
        cache = output / "cache"
        with patch.object(selftest, "_cache_root", return_value=cache), \
                patch.object(selftest, "_GRACE_NS", 0):
            selftest.build_template(root, output / "first", 2)
            selftest._publish(output / "first", cache)
            (root / ".gitignore").write_bytes(b"out/\na.txt\n")
            selftest.build_template(root, output / "warm", 2)
        with patch.object(selftest, "_cache_root", return_value=output / "empty-cache"):
            selftest.build_template(root, output / "cold", 2)
        warm, cold = corpus.read_index(output / "warm"), corpus.read_index(output / "cold")
        ensure(warm.files == cold.files and "a.txt" not in warm.indexed,
               f"ignore edits must match cold membership: warm={warm!r}, cold={cold!r}")


def _pin_changes_refresh_index() -> None:
    with sandbox_tree({".gitignore": "out/\n", "a.txt": "kept\n"}) as root:
        output = root / "out"
        cache = output / "cache"
        first, second = "a" * 40, "b" * 40
        _git(root, "update-index", "--add", "--cacheinfo", f"160000,{first},upstream/core")
        with patch.object(selftest, "_cache_root", return_value=cache), \
                patch.object(selftest, "_GRACE_NS", 0):
            selftest.build_template(root, output / "first", 2)
            selftest._publish(output / "first", cache)
            _git(root, "update-index", "--cacheinfo", f"160000,{second},upstream/core")
            selftest.build_template(root, output / "second", 2)
            ensure(corpus.load(output / "second").gitlinks == {"upstream/core": second},
                   "updated pin kept the previous object identity")
            selftest._publish(output / "second", cache)
            _git(root, "update-index", "--force-remove", "--", "upstream/core")
            selftest.build_template(root, output / "third", 2)
            ensure(not corpus.load(output / "third").gitlinks, "removed pin survived cached index")


def _missing_object_rebuilds_index() -> None:
    with sandbox_tree({".gitignore": "out/\n", "a.txt": "kept\n"}) as root:
        output = root / "out"
        cache = output / "cache"
        with patch.object(selftest, "_cache_root", return_value=cache), \
                patch.object(selftest, "_GRACE_NS", 0):
            selftest.build_template(root, output / "first", 2)
            selftest._publish(output / "first", cache)
            snapshot = cache / "t1"
            oid = _git(snapshot, "rev-parse", ":a.txt").decode().strip()
            blob = snapshot / ".git" / "objects" / oid[:2] / oid[2:]
            blob.chmod(stat.S_IWRITE)
            blob.unlink()
            selftest.build_template(root, output / "second", 2)
        ensure(corpus.staged_bytes(output / "second", "a.txt") == b"kept\n",
               "an index referring to a missing cached blob was not rebuilt")


def _snapshot_shape_falls_back() -> None:
    with sandbox_tree({".gitignore": "out/\n"}) as root:
        cache = root / "out" / "cache"
        snapshot = cache / "t1"
        snapshot.mkdir(parents=True)
        for data in ([], {"built_ns": 1, "files": {}},
                     {"built_ns": 1, "files": {}, "gitlinks": {"pin": None}}):
            (snapshot / selftest._MANIFEST).write_text(json.dumps(data), encoding="utf-8")
            ensure(selftest._newest_snapshot(cache) is None,
                   f"an unsupported snapshot must take the cold path: {data!r}")


def _sandbox_writes_remain_private() -> None:
    with sandbox_tree({".gitignore": "out/\n", "a.txt": "kept\n"}) as root:
        output = root / "out"
        with patch.object(selftest, "_cache_root", return_value=output / "cache"):
            template = output / "template"
            selftest.build_template(root, template, 2)
        first = selftest.stand_up(template, output / "first", jobs=2)
        second = selftest.stand_up(template, output / "second")
        repair = selftest.stand_up(template, output / "repair", fix_ok=True, jobs=2)
        ensure(first.write("a.txt", "mutant\n"), "mutation did not apply")
        (repair.path / "a.txt").write_bytes(b"repaired\n")
        ensure(second.read("a.txt") == "kept\n", "a peer saw another sandbox's mutation")
        ensure((template / "a.txt").read_bytes() == b"kept\n", "sandbox edited the template")
        first.reset()
        ensure(first.read("a.txt") == "kept\n", "reset failed to restore pristine bytes")


def _parallel_placement_matches_serial() -> None:
    with sandbox_tree({".gitignore": "out/\n", "a.txt": "root\n",
                       "docs/a.txt": "nested\n", "docs/sub/b.txt": "deep\n",
                       "model/model/riscv.sail_project": "project selection\n",
                       "model/example.sail": "model\n"}) as root:
        output = root / "out"
        template = output / "template"
        with patch.object(selftest, "_cache_root", return_value=output / "cache"):
            selftest.build_template(root, template, 2)
        (template / "empty").mkdir()
        serial = selftest.stand_up(template, output / "serial")
        with patch.object(selftest.os, "link", side_effect=OSError("no hardlinks")):
            parallel = selftest.stand_up(template, output / "parallel", jobs=3)
            selftest._link_tree(template / ".git", output / "git-copy", 3)

        def contents(path: Path) -> dict[str, bytes | None]:
            return {str(item.relative_to(path)): item.read_bytes() if item.is_file() else None
                    for item in path.rglob("*")}

        ensure(contents(serial.path) == contents(parallel.path),
               "parallel placement or hardlink fallback changed sandbox bytes or directories")
        ensure((serial.path / "model/model/riscv.sail_project").read_bytes()
               == b"project selection\n",
               "the project selection bound by source identity became an empty stand-in")
        ensure(contents(template / ".git") == contents(output / "git-copy"),
               "parallel object-store fallback changed copied bytes or directories")
        ensure(not (parallel.path / selftest._MANIFEST).exists(),
               "template metadata must remain outside the sandbox corpus")


def _parallel_work_is_complete_ordered_and_bounded() -> None:
    barrier, lock = Barrier(3, timeout=10), Lock()
    active = 0
    maximum = 0
    visited: list[int] = []

    def work(item: int) -> int:
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        barrier.wait()
        with lock:
            visited.append(item)
            active -= 1
        return item

    ensure(selftest._across(work, range(9), 3) == list(range(9)),
           "parallel results must preserve input order")
    ensure(sorted(visited) == list(range(9)) and maximum == 3,
           "every item must run once with bounded concurrency")

    def fail(item: int) -> int:
        if item == 1:
            raise OSError("placement failed")
        return item

    try:
        selftest._across(fail, range(3), 2)
    except OSError as err:
        ensure(str(err) == "placement failed", "a worker failure lost its diagnostic")
    else:
        raise AssertionError("a worker failure must propagate to its caller")


def _checker_stops_after_the_rules_group() -> None:
    ran: list[str] = []
    named: list[bool] = []

    def group(name: str, *rules: str) -> SimpleNamespace:
        def run(ctx: Context) -> None:
            ran.append(name)
            named.append(timings.ENV in timings.os.environ)
            # a part a group measures inside itself, as the generated group does its rows
            with ctx.clock.timing("row", f"{name}'s part"):
                for rule in rules:
                    ctx.rep.report(rule, "finding(s):",
                                   ["seeded"] if rule == "K-02" else [], "held")
        return SimpleNamespace(__name__=f"vos.checks.{name}", run=run)

    groups = [group("first", "K-01"), group("second", "K-02", "K-03"), group("third", "K-04")]
    expectations = {
        "K-01": (["first"], ["ok K-01: held",
                             "stopped after the group deciding K-01; "
                             "the 2 later group(s) decided nothing."]),
        "K-03": (["first", "second"], ["ok K-03: held",
                                       "stopped after the group deciding K-03; "
                                       "the 1 later group(s) decided nothing.",
                                       "1 finding(s)."]),
        "K-04": (["first", "second", "third"], ["ok K-04: held", "1 finding(s)."]),
        "K-99": (["first", "second", "third"], ["ok K-04: held", "1 finding(s)."]),
    }
    with patch.object(check, "GROUPS", groups), patch.object(check.corpus_mod, "load"), \
            patch.object(check, "read_register"), patch.object(check, "read_artifacts"):
        for through, (expected, tail) in expectations.items():
            ran.clear()
            report = check.run(Path("unused"), through=through)
            ensure(ran == expected, f"--through {through} ran {ran}, expected {expected}")
            ensure(report.out[-len(tail):] == tail, f"--through {through} ended {report.out}")
        ran.clear()
        ensure(check.run(Path("unused")).out[-1] == "1 finding(s)." and len(ran) == 3,
               "a run without --through must run every group")

        # A clock given the run records its fixed phases and the groups that ran, by
        # their modules' last names, with the parts those groups measured through the
        # run's context, and changes nothing the run reports.
        clock = timings.Clock(cpu=True)
        timed = check.run(Path("unused"), through="K-03", clock=clock)
        units = clock.units()
        ensure([(unit["kind"], unit["name"]) for unit in units]
               == [("group", "first"), ("group", "second"), ("phase", "artifacts read"),
                   ("phase", "corpus load"), ("phase", "register read"),
                   ("row", "first's part"), ("row", "second's part")],
               "the run's phases, its two groups and their parts are measured, "
               f"got {units!r}")
        ensure(all("cpu_seconds" in unit for unit in units),
               f"a CPU clock records each block's CPU seconds, got {units!r}")
        ensure(timed.out == check.run(Path("unused"), through="K-03").out,
               "measuring a run changed its report")

        # Under the gate's file, main prints the same report and records the import of
        # the groups' modules besides.
        with tempfile.TemporaryDirectory(prefix="vos-check-timings-") as td:
            path = Path(td) / "units.json"
            printed = io.StringIO()
            with (patch.dict(timings.os.environ, {timings.ENV: str(path)}),
                  contextlib.redirect_stdout(printed)):
                code = check.main(["--through", "K-03"])
            recorded = timings.read(path) or []
        ensure(not any(named), "the checker claims its file before any group can inherit it")
        ensure(code == 1 and printed.getvalue() == "\n".join(timed.out) + "\n",
               f"recording timings changed the checker's output: {printed.getvalue()!r}")
        ensure([(unit["kind"], unit["name"]) for unit in recorded]
               == [("group", "first"), ("group", "second"), ("phase", "artifacts read"),
                   ("phase", "corpus load"), ("phase", "imports"), ("phase", "register read"),
                   ("row", "first's part"), ("row", "second's part")],
               "main records the imports, the phases, the groups and their parts, "
               f"got {recorded!r}")
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                check.main(["--fix", "--through", "K-01"])
            except SystemExit as err:
                ensure(err.code == 2, "--fix with --through must be refused during parsing")
            else:
                raise AssertionError("--fix repaired a run that stops at one rule's group")


class _Scripted:
    """A sandbox whose checker answers from a script and records each run's stop."""

    def __init__(self, *answers: tuple[int, list[str], list[str]]) -> None:
        self.answers = list(answers)
        self.calls: list[str | None] = []

    def check(self, fix: bool = False,
              through: str | None = None) -> tuple[int, list[str], list[str]]:
        ensure(not fix, "a case never repairs")
        self.calls.append(through)
        return self.answers.pop(0)


def _case_verdict_reruns_only_survivors() -> None:
    scenarios: list[tuple[bool, tuple[tuple[int, list[str], list[str]], ...], str,
                          list[str | None], str]] = [
        (True, ((1, [], ["K-24"]),), KILLED, ["K-24"], "K-24"),
        (True, ((0, [], []), (1, [], ["K-24", "K-26"])), KILLED, ["K-24", None], "K-26"),
        (True, ((1, [], ["K-26"]), (1, [], ["K-26", "K-88"])), SURVIVED, ["K-24", None],
         "other rules fired: K-26, K-88"),
        (True, ((1, [selftest.OVERRAN], []),), SURVIVED, ["K-24"], "exited 1"),
        (False, (), UNSEEDED, [], "will not apply"),
    ]
    for applies, answers, outcome, calls, detail in scenarios:
        box = _Scripted(*answers)

        def seed(_box: selftest.Sandbox, applies: bool = applies) -> bool:
            return applies

        verdict = selftest._verdict(("K-24", "a seeded figure", seed),
                                    cast("selftest.Sandbox", box))
        ensure(verdict.outcome == outcome, f"{answers} gave {verdict.outcome}, expected {outcome}")
        ensure(box.calls == calls, f"{answers} ran the checker as {box.calls}, expected {calls}")
        ensure(detail in verdict.detail, f"{answers} explained itself as {verdict.detail!r}")
        ensure(not box.answers, "a scripted checker run was left unused")


def _holder_seeds_survive_changed_completion_prose() -> None:
    distractor = "```markdown\n* Exit evidence: example only\nLanded: Tier B under **K-79**.\n```\n"
    sections = ("## Second\nShortened narrative with no exit-evidence sentence.\n"
                "  * Landed: Tier B, held by **K-00** and **K-12**.\n",
                "## First\nA reordered completed item.\nLanded: Tier B under **K-12**.\n")
    for prose in (distractor + "\n".join(sections),
                  "\n".join(reversed(sections)) + distractor):
        for seed, fragment in ((selftest._k84_unregistered_holder, "names K-64"),
                               (selftest._k84, "lands at Tier B and names no rule")):
            with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN,
                               selftest.RULES: "# Rules\n", selftest.PLAN: "# Plan\n",
                               selftest.LOG: "# Completion log\n\n" + prose}) as root:
                before = (root / selftest.LOG).read_text(encoding="utf-8")
                ctx = _context(root)
                meta._landings(ctx, {"K-00", "K-12"})
                ensure(not _findings_under(ctx, "K-84"), "the independent fixture must begin valid")
                box = selftest.Sandbox(root, root)
                ensure(seed(box), "the holder mutant did not apply after narrative edits")
                after = box.read(selftest.LOG)
                ensure(after != before and distractor in after and box.touched == {selftest.LOG},
                       "the seed must change real declaration bytes and preserve fenced examples")
                ctx = _context(root)
                meta._landings(ctx, {"K-00", "K-12"})
                found = _findings_under(ctx, "K-84")
                ensure(len(found) == 1 and fragment in found[0],
                       f"the seeded defect must independently provoke its K-84 direction: {found}")


def _holder_seeds_refuse_absent_structural_targets() -> None:
    for seed, prose in (
            (selftest._k84_unregistered_holder, "K-00 is plain discussion.\n```\n**K-00**\n```\n"),
            (selftest._k84, "A fact is held by **K-00**.\nLanded: Tier A.\n"),
            (selftest._k84, "Landed: Tier B.\n"),
            (selftest._k84, "```\nLanded: Tier B under **K-00**.\n```\n")):
        with sandbox_tree({selftest.LOG: "# Completion log\n\n" + prose}) as root:
            box = selftest.Sandbox(root, root)
            before = box.read(selftest.LOG)
            with patch.object(box, "check", side_effect=AssertionError("an unseeded case ran its checker")):
                result = selftest._verdict(("K-84", "absent structural target", seed), box)
            ensure(result.outcome == UNSEEDED and not box.touched and box.read(selftest.LOG) == before,
                   "a missing target must remain an unchanged, explicitly unseeded mutant")


def cases() -> list[Case]:
    return [
        Case("shards-cover-cases-and-repair-once", _shards_cover_cases_and_repair_once),
        Case("repair-only-runs-beside-the-baseline", _repair_only_runs_beside_the_baseline),
        Case("shard-leaves-the-repair-path-to-repair-only",
             _shard_leaves_the_repair_path_to_repair_only),
        Case("baseline-overlaps-setup-and-never-enters-the-case-queue",
             _baseline_overlaps_setup_and_never_enters_the_case_queue),
        Case("repair-only-constructs-no-case-sandbox", _repair_only_constructs_no_case_sandbox),
        Case("failed-case-setup-wakes-every-waiting-case", _failed_case_setup_wakes_every_waiting_case),
        Case("checked-bytecode-reads-same-metadata-mutants-and-preserves-the-template",
             _checked_bytecode_reads_same_metadata_mutants_and_preserves_the_template),
        Case("bytecode-preparation-does-not-turn-unused-syntax-into-a-finding",
             _bytecode_preparation_does_not_turn_unused_syntax_into_a_finding),
        Case("checker-stops-after-the-rules-group", _checker_stops_after_the_rules_group),
        Case("case-verdict-reruns-only-survivors", _case_verdict_reruns_only_survivors),
        Case("holder-seeds-survive-changed-completion-prose", _holder_seeds_survive_changed_completion_prose),
        Case("holder-seeds-refuse-absent-structural-targets", _holder_seeds_refuse_absent_structural_targets),
        Case("refresh-index-without-changing-snapshot", _refresh_index_without_changing_snapshot),
        Case("failed-carry-rebuilds-index", _failed_carry_rebuilds_index),
        Case("attribute-change-matches-cold-index", _attribute_change_matches_cold_index),
        Case("ignore-change-matches-cold-index", _ignore_change_matches_cold_index),
        Case("pin-changes-refresh-index", _pin_changes_refresh_index),
        Case("missing-object-rebuilds-index", _missing_object_rebuilds_index),
        Case("snapshot-shape-falls-back", _snapshot_shape_falls_back),
        Case("sandbox-writes-remain-private", _sandbox_writes_remain_private),
        Case("parallel-placement-matches-serial", _parallel_placement_matches_serial),
        Case("parallel-work-is-complete-ordered-and-bounded",
             _parallel_work_is_complete_ordered_and_bounded),
    ]
