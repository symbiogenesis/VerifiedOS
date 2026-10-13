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


def cases() -> list[Case]:
    return [Case("main-revision-guards", revision_guards), Case("immutable-assets", asset_guards),
            Case("contained-source-symlinks", archive_guards), Case("closure-and-portability", closure_and_portability),
            Case("exact-kernel-context", exact_kernel_context), Case("cold-and-snapshot", cold_and_snapshot_guards),
            Case("failed-skipped-join", failed_and_skipped_join)]
