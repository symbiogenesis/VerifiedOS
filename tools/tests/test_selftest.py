# SPDX-License-Identifier: Apache-2.0
"""Template index reuse preserves sandbox bytes, pins and copy-on-write isolation."""

import json
import stat
import subprocess
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import corpus
from vos.cli import selftest
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

            def interrupted(_source: Path, target: Path) -> None:
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
        first = selftest.stand_up(template, output / "first")
        second = selftest.stand_up(template, output / "second")
        repair = selftest.stand_up(template, output / "repair", fix_ok=True)
        ensure(first.write("a.txt", "mutant\n"), "mutation did not apply")
        (repair.path / "a.txt").write_bytes(b"repaired\n")
        ensure(second.read("a.txt") == "kept\n", "a peer saw another sandbox's mutation")
        ensure((template / "a.txt").read_bytes() == b"kept\n", "sandbox edited the template")
        first.reset()
        ensure(first.read("a.txt") == "kept\n", "reset failed to restore pristine bytes")


def cases() -> list[Case]:
    return [
        Case("shards-cover-cases-and-repair-once", _shards_cover_cases_and_repair_once),
        Case("refresh-index-without-changing-snapshot", _refresh_index_without_changing_snapshot),
        Case("failed-carry-rebuilds-index", _failed_carry_rebuilds_index),
        Case("attribute-change-matches-cold-index", _attribute_change_matches_cold_index),
        Case("ignore-change-matches-cold-index", _ignore_change_matches_cold_index),
        Case("pin-changes-refresh-index", _pin_changes_refresh_index),
        Case("missing-object-rebuilds-index", _missing_object_rebuilds_index),
        Case("snapshot-shape-falls-back", _snapshot_shape_falls_back),
        Case("sandbox-writes-remain-private", _sandbox_writes_remain_private),
    ]
