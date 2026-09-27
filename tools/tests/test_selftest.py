# SPDX-License-Identifier: Apache-2.0
"""Template index reuse preserves sandbox bytes, pins and copy-on-write isolation.

A case's checker run stops after its rule's group, and only a survivor runs whole.
"""

import contextlib
import io
import json
import stat
import subprocess
from pathlib import Path
from threading import Barrier, Lock
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import check
from tests.harness import Case, ensure, sandbox_tree
from vos import corpus
from vos.checks import Context
from vos.cli import selftest
from vos.seeded import KILLED, SURVIVED, UNSEEDED
from vos.sharding import Shard


def _shards_cover_cases_and_repair_once() -> None:
    shards = [Shard(i, 4) for i in range(1, 5)]
    parts = [selftest._select_cases(None, shard) for shard in shards]
    ensure(sorted(id(case) for part in parts for case in part)
           == sorted(id(case) for case in selftest.CASES),
           "each authored mutant must run exactly once across shards")
    ensure([selftest._needs_repair(part, shard)
            for part, shard in zip(parts, shards, strict=True)] == [True, False, False, False],
           "the complete repair path must run on shard 1 alone")
    ensure(selftest._select_cases(None, Shard(1, 1)) == selftest.CASES,
           "one shard must select the full suite")
    try:
        selftest._select_cases("K-01", Shard(1, 4))
    except ValueError:
        pass
    else:
        raise AssertionError("a rule filter must not silently narrow CI shards")


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

    def group(name: str, *rules: str) -> SimpleNamespace:
        def run(ctx: Context) -> None:
            ran.append(name)
            for rule in rules:
                ctx.rep.report(rule, "finding(s):", ["seeded"] if rule == "K-02" else [], "held")
        return SimpleNamespace(run=run)

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


def cases() -> list[Case]:
    return [
        Case("shards-cover-cases-and-repair-once", _shards_cover_cases_and_repair_once),
        Case("checker-stops-after-the-rules-group", _checker_stops_after_the_rules_group),
        Case("case-verdict-reruns-only-survivors", _case_verdict_reruns_only_survivors),
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
