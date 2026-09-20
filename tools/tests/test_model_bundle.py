# SPDX-License-Identifier: Apache-2.0
"""Bundle emission is independent of the selected opam root, but binds library bytes."""

import argparse
import io
import json
import os
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos import env, sailbundle
from vos.cli import model

_CI_LIBRARY = Path("/home/runner/verifiedos-guest/opam") / env.SAIL_SWITCH / "share/sail"


def _relocated(data: bytes, library: Path) -> bytes:
    raw = json.loads(data)
    raw["hashes"] = {
        (library.as_posix() + "/" + key.removeprefix(sailbundle.LIBRARY_PREFIX)
         if key.startswith(sailbundle.LIBRARY_PREFIX) else key): value
        for key, value in raw["hashes"].items()}
    return (json.dumps(raw, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def _portable_library_metadata() -> None:
    tracked = (TOOLS.parent / sailbundle.BUNDLE).read_bytes()
    relocated = _relocated(tracked, _CI_LIBRARY)
    ensure(relocated != tracked, "the fixture must reproduce the runner's path difference")
    ensure(sailbundle.canonicalize_library(relocated, _CI_LIBRARY) == tracked,
           "the runner and local emission must compare byte-for-byte after path relocation")
    ensure(sailbundle.canonicalize_library(tracked, Path(sailbundle.LIBRARY_PREFIX)) == tracked,
           "canonical emission must retain its exact bytes")
    raw = json.loads(relocated)
    first = next(key for key in raw["hashes"] if key.startswith("/"))
    raw["hashes"][first]["md5"] = "0" * 32
    raw["functions"]["path_literal"] = {"contents": _CI_LIBRARY.as_posix()}
    changed = json.dumps(raw).encode()
    fresh = sailbundle.canonicalize_library(changed, _CI_LIBRARY)
    ensure(fresh != tracked and json.loads(fresh)["hashes"][
        sailbundle.LIBRARY_PREFIX + first.removeprefix(_CI_LIBRARY.as_posix() + "/")][
            "md5"] == "0" * 32, "library hash changes must survive relocation")
    ensure(json.loads(fresh)["functions"]["path_literal"]["contents"] == _CI_LIBRARY.as_posix(),
           "embedded model contents must not undergo path substitution")
    for foreign in (Path("/foreign/share/sail"), _CI_LIBRARY / "../foreign"):
        try:
            sailbundle.canonicalize_library(_relocated(tracked, foreign), _CI_LIBRARY)
        except sailbundle.BundleError:
            pass
        else:
            raise AssertionError("a foreign or escaping library root must fail closed")


def _bundle_publication_and_check() -> None:
    tracked = (TOOLS.parent / sailbundle.BUNDLE).read_bytes()
    with tempfile.TemporaryDirectory(prefix="vos-test-") as temporary:
        root = Path(temporary)
        e = env.Environment(root, root / "model", root / "build", root / "logs",
                            "", 4, 4096, 2, 2)
        target = root / sailbundle.BUNDLE
        target.parent.mkdir(parents=True)
        target.write_bytes(tracked)
        emitted = _relocated(tracked, _CI_LIBRARY)

        def stage(name: str, argv: list[str], **kwargs: object) -> int:
            into = Path(argv[argv.index("-o") + 1])
            (into / sailbundle.BUNDLE_NAME).write_bytes(emitted)
            return 0

        with (patch.object(model, "_require"), patch.object(model, "_seed_tree"),
              patch.object(env, "build_lock", return_value=None),
              patch.object(env, "opam_root", return_value=_CI_LIBRARY.parents[2]),
              patch.object(env, "stage", side_effect=stage),
              redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO())):
            for check in (True, False):
                ensure(model.cmd_bundle(e, argparse.Namespace(check=check)) == 0,
                       "both checking and regeneration must accept the selected CI library")
                ensure(target.read_bytes() == tracked, "publication must use canonical metadata")
            emitted = emitted.replace(b'"md5":"', b'"md5":"changed', 1)
            ensure(model.cmd_bundle(e, argparse.Namespace(check=True)) == 1,
                   "changed library bytes must fail the comparison")
            ensure(target.read_bytes() == tracked, "failed comparison must preserve the artifact")
            emitted = _relocated(tracked, Path("/foreign/share/sail"))
            ensure(model.cmd_bundle(e, argparse.Namespace(check=False)) == 1,
                   "foreign library provenance must fail before publication")
            ensure(target.read_bytes() == tracked, "failed regeneration must preserve the artifact")
            with patch.object(env, "stage", return_value=0):
                stale = e.lane_root / "bundle" / sailbundle.BUNDLE_NAME
                stale.parent.mkdir(parents=True)
                stale.write_bytes(tracked)
                ensure(model.cmd_bundle(e, argparse.Namespace(check=False)) == 1,
                       "a missing emission must not publish a previous scratch artifact")
                ensure(target.read_bytes() == tracked, "missing emission must preserve publication")


def _real_relocated_library() -> None:
    e = env.load()
    library = env.opam_root() / env.SAIL_SWITCH / "share/sail"
    with tempfile.TemporaryDirectory(prefix="bundle-portability-", dir=e.lane_root) as temporary:
        opam = Path(temporary) / "opam"
        relocated = opam / env.SAIL_SWITCH / "share/sail"
        relocated.parent.mkdir(parents=True)
        relocated.symlink_to(library, target_is_directory=True)
        # Exercise the real emitter with another absolute library prefix, without
        # installing or modifying shared toolchain state.
        with (patch.dict(os.environ, {"SAIL_DIR": str(relocated)}),
              patch.object(env, "opam_root", return_value=opam)):
            ensure(model.cmd_bundle(e, argparse.Namespace(check=True)) == 0,
                   "real Sail emission under a relocated library must match the tracked bundle")


def cases() -> list[Case]:
    return [Case("portable-library-metadata", _portable_library_metadata),
            Case("bundle-publication-and-check", _bundle_publication_and_check),
            Case("real-relocated-library", _real_relocated_library, slow=True, lane="toolchain")]
