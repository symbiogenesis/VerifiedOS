# SPDX-License-Identifier: Apache-2.0
"""Source-carriage guards; fixture checks never build a switch or support package."""

import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
from collections.abc import Callable
from functools import partial
from pathlib import Path
from unittest.mock import patch

from ci import sail_support_route as route
from tests.harness import Case, ensure


def refuses(call: Callable[[], object]) -> None:
    try:
        call()
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        return
    raise AssertionError("unsupported source-carriage input accepted")


def revision_guards() -> None:
    revision = "a" * 40
    with patch.object(subprocess, "check_output", return_value=revision + "\n"), \
            patch.object(subprocess, "run") as executed:
        route.guarded_revision(Path(), revision, revision, "refs/heads/main")
        ensure(executed.call_count == 1, "main ancestry checked")
        refuses(lambda: route.guarded_revision(Path(), revision, revision, "refs/heads/work/test"))
        refuses(lambda: route.guarded_revision(Path(), "main", revision, "refs/heads/main"))
        refuses(lambda: route.guarded_revision(Path(), "b" * 40, revision, "refs/heads/main"))
        ensure(executed.call_count == 1, "invalid framing never reached ancestry check")


def asset_guards() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-route-") as directory:
        root = Path(directory)
        (root / "file").write_bytes(b"reviewed")
        entry = {"path": "file", "sha256": hashlib.sha256(b"reviewed").hexdigest()}
        ensure(route.asset(root, entry).read_bytes() == b"reviewed", "exact bytes loaded")
        refuses(lambda: route.asset(root, entry | {"path": "../file"}))
        refuses(lambda: route.asset(root, entry | {"sha256": "0" * 64}))


def archive_guards() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-archive-") as directory:
        root = Path(directory)
        for number, target in enumerate(("../src/file.v", "../../../outside")):
            archive = root / (str(number) + ".tar")
            with tarfile.open(archive, "w") as stream:
                member = tarfile.TarInfo("source/src/file.v")
                member.size = 1
                stream.addfile(member, io.BytesIO(b"x"))
                member = tarfile.TarInfo("source/src-stdpp/file.v")
                member.type, member.linkname = tarfile.SYMTYPE, target
                stream.addfile(member)
            if number == 0:
                extracted = route.extract(archive, root / "safe")
                ensure((extracted / "src-stdpp/file.v").is_symlink(), "source symlink preserved")
            else:
                refuses(partial(route.extract, archive, root / "escaping"))


def closure_and_portability() -> None:
    actual = [{"name": "rocq-core", "version": "9.3.0", "pin": ""}]
    route.same_closure(actual, {"rocq-core": "9.3.0"})
    refuses(lambda: route.same_closure(actual, {"rocq-core": "9.2.0"}))
    refuses(lambda: route.same_closure([actual[0] | {"pin": "main"}], {"rocq-core": "9.3.0"}))
    patch_bytes = b"immutable patch"
    sha = hashlib.sha256(patch_bytes).hexdigest()
    metadata = 'extra-files: [["source.patch" "sha256=' + sha + '"]] source ' + "a" * 64
    route.snapshot_metadata(metadata, {"source.patch": patch_bytes}, "a" * 64)
    refuses(lambda: route.snapshot_metadata(metadata + " file:///tmp/source", {"source.patch": patch_bytes}, "a" * 64))
    refuses(lambda: route.snapshot_metadata(metadata.replace(sha, "b" * 64), {"source.patch": patch_bytes}, "a" * 64))
    refuses(lambda: route.snapshot_metadata(metadata.replace("extra-files:", "missing:"), {"source.patch": patch_bytes}, "a" * 64))


def exact_kernel_context() -> None:
    with patch.object(route.proofaudit, "kernel_context", return_value=["Stdlib.expected"]):
        ensure(route.kernel_reading(0, "", "summary", ["Stdlib.expected"]) == ["Stdlib.expected"], "exact set accepted")
        refuses(lambda: route.kernel_reading(0, "", "summary", []))
        refuses(lambda: route.kernel_reading(1, "", "summary", ["Stdlib.expected"]))
        refuses(lambda: route.kernel_reading(0, "diagnostic", "summary", ["Stdlib.expected"]))
    refuses(lambda: route.kernel_reading(0, "", "missing summary", []))


def cold_and_snapshot_guards() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-cold-") as directory:
        root = Path(directory)
        refuses(lambda: route.Campaign(root, root, "build"))
        snapshot = root / "snapshot"
        snapshot.write_bytes(b"reviewed export")
        route.checked_import(snapshot, hashlib.sha256(snapshot.read_bytes()).hexdigest())
        refuses(lambda: route.checked_import(snapshot, "a" * 64))
        refuses(lambda: route.checked_import(None, None))
        refuses(lambda: route.join(None, root, "a" * 40, root))


def failed_and_skipped_join() -> None:
    with patch.dict(route.os.environ, {"CAMPAIGN_NEEDS": json.dumps({"plan": {"result": "success"},
                    "build": {"result": "failure"}, "import": {"result": "skipped"}})}):
        refuses(lambda: route.join(Path(), Path(), "a" * 40, Path()))


def timeout_preserves_diagnostics() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-timeout-") as directory:
        root = Path(directory)
        side = root / "side"
        (side / "tools/opam").mkdir(parents=True)
        (side / route.RECIPE).write_text('{}', encoding="utf-8")
        with patch.dict(route.os.environ, {"TESTED_REVISION": "a" * 40, "GITHUB_SHA": "a" * 40}), \
                patch.object(subprocess, "Popen") as launched, \
                patch.object(route.os, "killpg", create=True):
            process = launched.return_value.__enter__.return_value
            process.communicate.side_effect = [subprocess.TimeoutExpired(["fixture"], 1),
                                               ("retained stdout", "retained stderr")]
            campaign = route.Campaign(root / "fresh", side, "build")
            refuses(lambda: campaign.run("bounded", ["fixture"], root, timeout=1))
            command = campaign.report["commands"][-1]
            ensure(command["timed_out"] and command["exit"] == 124, "deadline supplies no passing exit")
            ensure((campaign.upload / "bounded.log").read_text() == "retained stdoutretained stderr",
                   "timed-out operation preserves diagnostic bytes")


def complete_join_and_missing_steps() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-join-") as directory:
        root = Path(directory)
        side, artifacts = root / "side", root / "artifacts"
        (side / "tools/opam").mkdir(parents=True)
        frozen = side / "frozen.json"
        frozen.write_text('{"queries":[{}]}', encoding="utf-8")
        license_bytes = b"reviewed BSD license fixture"
        recipe = {"frozen_inventory": {"path": "frozen.json", "sha256": route.receipts.digest(frozen)},
                  "source_license_sha256": hashlib.sha256(license_bytes).hexdigest(),
                  "support_axioms": [], "probes": {name: {"expected_axioms": []}
                                                      for name in ("term", "eqdep", "real", "notation")}}
        route.write(side / route.RECIPE, recipe)
        environment = {"CAMPAIGN_NEEDS": json.dumps({name: {"result": "success"}
                       for name in ("plan", "build", "import")}), "GITHUB_SHA": "a" * 40,
                       "GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "2"}
        for phase in ("build", "import"):
            lane = artifacts / phase
            lane.mkdir(parents=True)
            (lane / "sail-support.lock").write_bytes(b"same reviewed export")
            (lane / "Sail-Support-LICENSE").write_bytes(license_bytes)
            route.write(lane / "input-identities.json", {"/fixture/source.v": "a" * 64})
            route.write(lane / "native-assumptions.json", {"fixture": []})
            (lane / "package-metadata.txt").write_text("package metadata fixture", encoding="utf-8")
            evidence = {name: {"sha256": route.receipts.digest(lane / name), "bytes": (lane / name).stat().st_size}
                        for name in ("input-identities.json", "native-assumptions.json", "package-metadata.txt",
                                     "Sail-Support-LICENSE", "sail-support.lock")}
            commands = []
            for label in sorted(route.required_labels(phase, 1)):
                log = lane / (label + ".log")
                log.write_bytes(b"kernel fixture" if label.startswith("kernel-") else b"")
                commands.append({"label": label, "log": log.name, "log_sha256": route.receipts.digest(log),
                                 "exit": 0, "strict": label.startswith("strict-")})
            receipt = {"phase": phase, "status": "passed", "cold": True, "revision": "a" * 40,
                       "dispatch_revision": "a" * 40, "run_id": "1", "run_attempt": "2",
                       "recipe_sha256": route.receipts.digest(side / route.RECIPE), "commands": commands,
                       "export_sha256": route.receipts.digest(lane / "sail-support.lock"),
                       "reexport_identical": phase == "import", "evidence": evidence}
            route.write(lane / "receipt.json", receipt)
        with patch.dict(route.os.environ, environment), patch.object(route, "kernel_reading", return_value=[]):
            route.join(artifacts, side, "a" * 40, root / "result")
            ensure(route.load(root / "result/report.json")["status"] == "passed", "complete independent pair accepted")
            for phase in ("build", "import"):
                path = artifacts / phase / "receipt.json"
                original = route.load(path)
                for label in route.required_labels(phase, 1):
                    route.write(path, original | {"commands": [row for row in original["commands"] if row["label"] != label]})
                    refuses(partial(route.join, artifacts, side, "a" * 40, root / "result"))
                route.write(path, original | {"cold": False})
                refuses(partial(route.join, artifacts, side, "a" * 40, root / "result"))
                route.write(path, original)
                for name in original["evidence"]:
                    member = path.parent / name
                    data = member.read_bytes()
                    member.unlink()
                    refuses(partial(route.join, artifacts, side, "a" * 40, root / "result"))
                    member.write_bytes(data)


def cases() -> list[Case]:
    return [Case("main-revision-guards", revision_guards), Case("immutable-assets", asset_guards),
            Case("contained-source-symlinks", archive_guards), Case("closure-and-portability", closure_and_portability),
            Case("exact-kernel-context", exact_kernel_context), Case("cold-and-snapshot", cold_and_snapshot_guards),
            Case("failed-skipped-join", failed_and_skipped_join),
            Case("timeout-retains-diagnostics", timeout_preserves_diagnostics),
            Case("complete-join-required-steps", complete_join_and_missing_steps)]
