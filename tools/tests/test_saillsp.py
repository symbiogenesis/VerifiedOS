# SPDX-License-Identifier: Apache-2.0
"""Wire framing and optional-install identities without requiring native packages."""

import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
from collections.abc import Callable, Mapping
from contextlib import nullcontext, redirect_stderr
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from jsonschema import Draft202012Validator

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from vos import env, saillsp


def _frames() -> None:
    message = {"jsonrpc": "2.0", "id": 7, "result": "lambda λ and emoji 🐚"}
    wire = saillsp.frame(message)
    header, body = wire.split(b"\r\n\r\n", 1)
    ensure(int(header.split(b": ")[1]) == len(body), "LSP lengths count encoded bytes")
    buffer = bytearray()
    for value in wire[:-1]:
        buffer.append(value)
        ensure(saillsp.decode_frame(buffer) is None, "partial frames must remain pending")
    buffer.extend(wire[-1:])
    buffer.extend(saillsp.frame({"jsonrpc": "2.0", "id": 8, "result": None}))
    ensure(saillsp.decode_frame(buffer) == message, "fragmented frames must reconstruct")
    ensure(saillsp.decode_frame(buffer) == {"jsonrpc": "2.0", "id": 8, "result": None},
           "coalesced frames must retain their boundaries")
    ensure(not buffer, "the decoder must consume exactly two frames")


def _bad_frames() -> None:
    for wire in (b"Content-Length: -1\r\n\r\n", b"Content-Length: 8388609\r\n\r\n",
                 b"Content-Length: 2\r\nContent-Length: 2\r\n\r\n{}",
                 b"banner\r\nContent-Length: 2\r\n\r\n{}",
                 b"Content-Length: 2\r\n\r\n{}", b"x" * 8193):
        try:
            saillsp.decode_frame(bytearray(wire))
        except ValueError:
            continue
        raise AssertionError(f"invalid wire accepted: {wire[:60]!r}")


def _environment(root: Path) -> env.Environment:
    return env.Environment(root=root, model=root / "model", build_root=root / "native",
                           log_root=root / "logs", lane="", cpus=1, mem_available_mb=1024,
                           jobs=1, test_jobs=1)


def _provenance() -> None:
    files = {saillsp.LOCK: "{}", "tools/opam/sail.lock": 'installed: ["ocaml.5.4.1"]',
             "tools/vos/saillsp.py": "recipe", "tools/sail-lsp/dependency-refresh.patch": "patch"}
    with sandbox_tree(files) as root:
        environment = _environment(root)
        ensure(saillsp.status(environment)["installed"] is False, "absence must be explicit")
        location = saillsp.home(environment)
        binary = location / "prefix/bin/sail_lsp"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"pinned executable")
        receipt = {"lock_sha256": saillsp.lock_identity(root), "elapsed_seconds": 1.0,
                   "log": "build.log", "artifacts": {"prefix/bin/sail_lsp": saillsp.sha256(binary)}}
        (location / "installation.json").write_text(json.dumps(receipt), encoding="utf-8")
        result = saillsp.status(environment)
        ensure(result["installed"] is True, "matching artifacts must be usable")
        schema = json.loads((TOOLS / "sail-lsp.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(result)
        binary.write_bytes(b"changed executable")
        try:
            saillsp.status(environment)
        except ValueError as exc:
            ensure("artifact changed" in str(exc), "artifact mismatch needs a concrete error")
        else:
            raise AssertionError("modified native executable accepted")
        (root / saillsp.LOCK).write_text('{"changed":true}', encoding="utf-8")
        try:
            saillsp.status(environment)
        except ValueError as exc:
            ensure("stale" in str(exc), "changed recipe must invalidate installation")
        else:
            raise AssertionError("stale optional installation accepted")


def _archive_confinement() -> None:
    with sandbox_tree({"marker": "unchanged"}) as root:
        directory = root / "sources"
        directory.mkdir()
        archive = directory / "test.archive"
        with tarfile.open(archive, "w") as output:
            member = tarfile.TarInfo("../marker")
            member.size = 7
            output.addfile(member, io.BytesIO(b"changed"))
        spec = {"name": "test", "directory": "test", "sha256": saillsp.sha256(archive)}
        try:
            saillsp._source(spec, directory)
        except tarfile.FilterError:
            pass
        else:
            raise AssertionError("archive escaped its source directory")
        ensure((root / "marker").read_text() == "unchanged", "rejected source must not overwrite outside its directory")


def _tar(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as output:
        for name, data in members.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            output.addfile(member, io.BytesIO(data))
    return buffer.getvalue()


def _superseded_archive() -> None:
    with sandbox_tree({"marker": "unchanged"}) as root:
        directory = root / "sources"
        directory.mkdir()
        archive = directory / "test.archive"
        archive.write_bytes(_tar({"test-1/old.ml": b"earlier pin"}))
        stale = directory / "test-1/old.ml"
        stale.parent.mkdir()
        stale.write_bytes(b"earlier pin")
        current = _tar({"test-1/new.ml": b"current pin"})
        spec = {"name": "test", "directory": "test-1", "url": "https://example.invalid/test.tbz",
                "sha256": hashlib.sha256(current).hexdigest()}
        with patch.object(saillsp.urllib.request, "urlopen", return_value=io.BytesIO(current)) as fetch:
            target = saillsp._source(spec, directory)
        ensure(fetch.call_count == 1, "an archive whose digest differs from the tracked pin must be fetched again")
        ensure(archive.read_bytes() == current and not archive.with_name("test.archive.part").exists(),
               "the verified download must replace the superseded archive")
        ensure((target / "new.ml").read_bytes() == b"current pin" and not (target / "old.ml").exists(),
               "no member of the superseded archive may survive into the build tree")
        with patch.object(saillsp.urllib.request, "urlopen") as fetch:
            saillsp._source(spec, directory)
        ensure(not fetch.called, "an archive matching its pin must be reused without a download")
        stale_bytes = _tar({"test-1/old.ml": b"earlier pin"})
        archive.write_bytes(stale_bytes)
        with patch.object(saillsp.urllib.request, "urlopen", return_value=io.BytesIO(b"not the pin")):
            try:
                saillsp._source(spec, directory)
            except ValueError as exc:
                ensure("digest mismatch" in str(exc), "a mismatched download needs a concrete error")
            else:
                raise AssertionError("a download differing from its pin was accepted")
        ensure(archive.read_bytes() == stale_bytes and not archive.with_name("test.archive.part").exists(),
               "a mismatched download must neither replace the archive nor remain as a partial file")
        for escaped in ("..", "../outside", ""):
            try:
                saillsp._source({**spec, "directory": escaped}, directory)
            except ValueError:
                continue
            raise AssertionError(f"source directory {escaped!r} escaped its lane directory")
        ensure((root / "marker").read_text() == "unchanged", "a refused directory must not be removed")


_BUILD_SPECS = [{"name": "lsp", "directory": "lsp-1", "license_file": "LICENSE"},
                {"name": "sail", "directory": "sail-1", "license_file": "LICENSE"}]
_BUILD_RECIPE = {saillsp.LOCK: json.dumps({"sources": _BUILD_SPECS}),
                 "tools/opam/sail.lock": 'installed: ["ocaml.5.4.1"]',
                 "tools/vos/saillsp.py": "recipe", "tools/sail-lsp/dependency-refresh.patch": "patch"}


def _mock_source(spec: dict[str, Any], directory: Path) -> Path:
    target = directory / str(spec["directory"])
    (target / "lib").mkdir(parents=True, exist_ok=True)
    (target / spec["license_file"]).write_text("license", encoding="utf-8")
    (target / "lib/prelude.sail").write_text("prelude", encoding="utf-8")
    return target


def _mock_build(argv: list[str], cwd: Path, environ: dict[str, str], log: Path) -> None:
    if argv[:2] == ["dune", "install"]:
        prefix = Path(argv[argv.index("--prefix") + 1])
        installed = prefix / ("bin/sail_lsp" if cwd.name == "sail_lsp" else f"lib/{cwd.name}/META")
        installed.parent.mkdir(parents=True, exist_ok=True)
        installed.write_text("current", encoding="utf-8")


def _mock_install(environment: env.Environment, build: Callable[..., None] = _mock_build,
                  stderr: io.StringIO | None = None) -> dict[str, Any]:
    """install with the switch inventory, source fetches and build commands mocked."""
    with (patch.object(saillsp.env, "hold_lock", side_effect=lambda *_: nullcontext()),
          patch.object(saillsp, "_base_inventory", return_value=["ocaml.5.4.1"]),
          patch.object(saillsp, "_source", side_effect=_mock_source),
          patch.object(saillsp, "_run", side_effect=build),
          redirect_stderr(io.StringIO() if stderr is None else stderr)):
        return saillsp.install(environment)


def _rebuild_uses_fresh_prefix() -> None:
    with sandbox_tree(_BUILD_RECIPE) as root:
        environment = _environment(root)
        location = saillsp.home(environment)
        stale_library = location / "prefix/lib/superseded/META"
        stale_config = location / "config/sail_lsp/superseded.json"

        def plant() -> None:
            for path in (stale_library, stale_config):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("superseded", encoding="utf-8")
            (location / "installation.json").write_text(json.dumps({"lock_sha256": "0" * 64}), encoding="utf-8")

        run = _mock_build

        def install(build: Callable[..., None] = run) -> dict[str, Any]:
            return _mock_install(environment, build)

        def artifacts() -> dict[str, str]:
            receipt = json.loads((location / "installation.json").read_text(encoding="utf-8"))
            return cast(dict[str, str], receipt["artifacts"])

        plant()
        ensure(install()["installed"] is True, "a rebuilt installation must be usable")
        ensure("prefix/bin/sail_lsp" in artifacts() and "prefix/lib/sail-1/META" in artifacts(),
               "the rebuilt receipt must hash what the current recipe installed")
        ensure("prefix/lib/superseded/META" not in artifacts() and not stale_library.exists(),
               "a file a superseded recipe installed must leave the prefix and the receipt")
        ensure(not stale_config.exists(), "a rebuild must not keep a superseded configuration")

        def kept(directory: Path) -> Path:
            """The superseded recipe's `prefix.mkdir(exist_ok=True)`, as the control."""
            directory.mkdir(parents=True, exist_ok=True)
            return directory

        plant()
        with patch.object(saillsp, "_fresh", side_effect=kept):
            install()
        ensure("prefix/lib/superseded/META" in artifacts() and stale_config.exists(),
               "control: reusing the prefix hashes a superseded file as an artifact of the new build")

        def interrupted(argv: list[str], cwd: Path, environ: dict[str, str], log: Path) -> None:
            if cwd.name == "sail_lsp":
                raise ValueError("build command exited 1")
            run(argv, cwd, environ, log)

        plant()
        try:
            install(interrupted)
        except ValueError:
            pass
        else:
            raise AssertionError("an interrupted rebuild reported success")
        ensure(not (location / "installation.json").exists() and not stale_library.exists()
               and saillsp.status(environment)["installed"] is False,
               "an interrupted rebuild must leave no receipt describing a removed prefix")


def _refused_installation_rebuilt() -> None:
    """status refuses an installation of the current recipe whose receipt or artifacts
    changed, and names install as the repair; install then rebuilds instead of repeating
    the refusal."""
    with sandbox_tree(_BUILD_RECIPE) as root:
        environment = _environment(root)
        location = saillsp.home(environment)
        binary = location / "prefix/bin/sail_lsp"
        receipt = location / "installation.json"
        builds: list[list[str]] = []

        def counted(argv: list[str], cwd: Path, environ: dict[str, str], log: Path) -> None:
            builds.append(argv)
            _mock_build(argv, cwd, environ, log)

        ensure(_mock_install(environment)["installed"] is True, "the first build must be usable")
        good: dict[str, Any] = json.loads(receipt.read_text(encoding="utf-8"))
        ensure(_mock_install(environment, counted)["installed"] is True and not builds,
               "control: an installation status accepts must be returned without a rebuild")

        def rewritten(fields: Mapping[str, object]) -> Callable[[], object]:
            """The first build's receipt, of the current recipe, with `fields` replaced."""
            return lambda: receipt.write_text(json.dumps({**good, **fields}), encoding="utf-8")

        damages: tuple[tuple[str, Callable[[], object]], ...] = (
            ("changed", lambda: binary.write_text("edited", encoding="utf-8")),
            ("missing", binary.unlink),
            ("unreadable", lambda: receipt.write_text(receipt.read_text(encoding="utf-8")[:40],
                                                      encoding="utf-8")),
            # JSON of the current recipe that lacks the fields status reports.
            ("unreadable", lambda: receipt.write_text(
                json.dumps({"lock_sha256": saillsp.lock_identity(root)}), encoding="utf-8")),
            ("unreadable", lambda: receipt.write_text("[]", encoding="utf-8")),
            # A field status reports, present with the wrong shape: an artifacts object
            # without the server, artifacts as a list, an elapsed time that is negative
            # or a boolean, and a log that is not a path.
            *(("unreadable", rewritten(fields)) for fields in (
                {"artifacts": {}}, {"artifacts": ["prefix/bin/sail_lsp"]},
                {"elapsed_seconds": -1}, {"elapsed_seconds": True}, {"log": None})))
        for problem, damage in damages:
            damage()
            try:
                saillsp.status(environment)
            except ValueError as exc:
                ensure(problem in str(exc) and str(exc).endswith("run sail-lsp install"),
                       f"status must refuse a {problem} installation and name its repair: {exc}")
            else:
                raise AssertionError(f"status accepted a {problem} installation")
            builds.clear()
            report = io.StringIO()
            result = _mock_install(environment, counted, report)
            ensure(bool(builds) and result["installed"] is True
                   and binary.read_text(encoding="utf-8") == "current",
                   f"install must rebuild an installation status refuses as {problem}")
            ensure(problem in report.getvalue(), f"install must report why it rebuilt: {report.getvalue()!r}")


def _unreadable_recipe_keeps_installation() -> None:
    """An OSError reading the checkout's recipe inputs is not a refused installation:
    install stops before removing the receipt or prefix, even when status would refuse
    the receipt, and status accepts the installation again once the checkout is
    restored. A receipt or an artifact status cannot read remains a refusal install
    repairs."""
    with sandbox_tree(_BUILD_RECIPE) as root:
        environment = _environment(root)
        location = saillsp.home(environment)
        binary = location / "prefix/bin/sail_lsp"
        receipt = location / "installation.json"
        builds: list[list[str]] = []

        def counted(argv: list[str], cwd: Path, environ: dict[str, str], log: Path) -> None:
            builds.append(argv)
            _mock_build(argv, cwd, environ, log)

        ensure(_mock_install(environment)["installed"] is True, "the first build must be usable")
        recorded = receipt.read_bytes()
        refresh = root / "tools/sail-lsp/dependency-refresh.patch"
        refresh.unlink()
        try:
            _mock_install(environment, counted)
        except OSError:
            pass
        else:
            raise AssertionError("install proceeded without a recipe input it could read")
        ensure(not builds and receipt.is_file() and receipt.read_bytes() == recorded and binary.is_file(),
               "an unreadable recipe input must leave the receipt and prefix in place")
        refresh.write_text(_BUILD_RECIPE["tools/sail-lsp/dependency-refresh.patch"], encoding="utf-8")
        ensure(saillsp.status(environment)["installed"] is True,
               "restoring the checkout must restore the installation without a rebuild")
        read_text = Path.read_text

        def denied(path: Path, encoding: str | None = None, errors: str | None = None,
                   newline: str | None = None) -> str:
            if path == receipt:
                raise PermissionError(13, "Permission denied", str(path))
            return read_text(path, encoding, errors, newline)

        with patch.object(Path, "read_text", denied):
            try:
                saillsp.status(environment)
            except ValueError as exc:
                ensure("unreadable" in str(exc) and str(exc).endswith("run sail-lsp install"),
                       f"a receipt status cannot read must be refused with its repair: {exc}")
            else:
                raise AssertionError("status accepted a receipt it could not read")

        def unreadable(path: Path) -> str:
            if path == binary:
                raise PermissionError(13, "Permission denied", str(path))
            return hashlib.sha256(path.read_bytes()).hexdigest()

        with patch.object(saillsp, "sha256", side_effect=unreadable):
            try:
                saillsp.status(environment)
            except ValueError as exc:
                ensure("changed" in str(exc) and str(exc).endswith("run sail-lsp install"),
                       f"an artifact status cannot read must be refused with its repair: {exc}")
            else:
                raise AssertionError("status accepted an artifact it could not read")

        # install reads the recipe before it asks status, so a receipt status refuses
        # does not carry it past an unreadable input into removing the installation,
        # nor into reporting a repair it never starts.
        receipt.write_text("{", encoding="utf-8")
        refresh.unlink()
        builds.clear()
        report = io.StringIO()
        try:
            _mock_install(environment, counted, report)
        except OSError:
            pass
        else:
            raise AssertionError("install proceeded without a recipe input it could read")
        ensure(not builds and not report.getvalue()
               and receipt.read_text(encoding="utf-8") == "{" and binary.is_file(),
               "an unreadable recipe input must stop install before it asks status or "
               f"repairs a refused receipt: {report.getvalue()!r}")


def _base_lock() -> None:
    files = {"tools/opam/sail.lock": 'installed: ["ocaml.5.4.1" "dune.3.24.2" "sail.0.20.3"]',
             saillsp.LOCK: json.dumps({"sources": [{"name": "lsp", "version": "1.27.0"},
                                                   {"name": "sail", "version": "0.20.3"}]})}
    listing = "dune 3.24.2\nocaml 5.4.1\nsail 0.20.3\n"
    with sandbox_tree(files) as root:
        with patch.object(saillsp.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, listing)):
            ensure(saillsp._base_inventory(root) == ["dune.3.24.2", "ocaml.5.4.1", "sail.0.20.3"],
                   "the complete base lock must match")
        with patch.object(saillsp.subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, listing.replace("5.4.1", "5.5.0"))):
            try:
                saillsp._base_inventory(root)
            except ValueError:
                pass
            else:
                raise AssertionError("compiler drift was accepted")
        (root / saillsp.LOCK).write_text(files[saillsp.LOCK].replace("0.20.3", "0.20.4"), encoding="utf-8")
        with patch.object(saillsp.subprocess, "run") as run:
            try:
                saillsp._base_inventory(root)
            except ValueError as exc:
                ensure("not the Sail release" in str(exc), "a foreign Sail pin needs a concrete error")
            else:
                raise AssertionError("a Sail archive pin the locked compiler does not install was accepted")
            ensure(not run.called, "the Sail pin must be refused before the switch is inspected")


def _base_listing_answers_no_question() -> None:
    """The base switch's `opam list`, its output captured, reads no standard input and
    inherits no answer from the caller's environment, in any case the caller names it,
    so a format upgrade it would ask about is declined rather than left on a prompt the
    caller cannot see or answered by the caller's settings; the rest of the environment,
    the root among it, is passed on."""
    files = {"tools/opam/sail.lock": 'installed: ["sail.0.20.3"]',
             saillsp.LOCK: json.dumps({"sources": [{"name": "sail", "version": "0.20.3"}]})}
    answers = {"OPAMYES": "1", "OpamConfirmLevel": "unsafe-yes", "OPAMROOT": "/elsewhere"}
    with (sandbox_tree(files) as root, patch.dict(os.environ, answers),
          patch.object(saillsp.subprocess, "run",
                       return_value=subprocess.CompletedProcess([], 0, "sail 0.20.3\n")) as run):
        ensure(saillsp._base_inventory(root) == ["sail.0.20.3"], "the base lock must match")
    passed = run.call_args.kwargs.get("env") or {}
    ensure(run.call_args.args[0][:2] == ["opam", "list"]
           and run.call_args.kwargs.get("stdin") is subprocess.DEVNULL,
           f"opam list's standard input is closed: {run.call_args}")
    ensure(not {key.upper() for key in passed} & set(env.OPAM_ANSWERS)
           and passed.get("OPAMROOT") == "/elsewhere",
           f"opam list is passed no answer and keeps the root: {sorted(passed)}")


def _tool_sail_pins_agree() -> None:
    lsp = next(spec for spec in json.loads((TOOLS / "sail-lsp/sources.lock.json").read_text(encoding="utf-8"))
               ["sources"] if spec["name"] == "sail")
    isla = json.loads((TOOLS / "sail-isla/lock.json").read_text(encoding="utf-8"))["sail"]
    fields = ("version", "revision", "url", "sha256", "directory")
    ensure({key: lsp[key] for key in fields} == {key: isla[key] for key in fields},
           "the LSP and Isla tools must pin one Sail release archive")
    locked = (TOOLS / "opam/sail.lock").read_text(encoding="utf-8")
    block = re.search(r"installed:\s*\[(.*?)\]", locked, re.DOTALL)
    ensure(block is not None and f'"sail.{lsp["version"]}"' in block[1],
           "the tools' Sail archive must be the release the locked compiler installs")


def cases() -> list[Case]:
    return [Case("standard-framing-fragments-and-coalescing", _frames),
            Case("malformed-and-unbounded-frames", _bad_frames),
            Case("optional-installation-provenance", _provenance),
            Case("archive-extraction-confinement", _archive_confinement),
            Case("superseded-archive-fetched-verified-and-replaced", _superseded_archive),
            Case("rebuild-installs-into-a-fresh-prefix", _rebuild_uses_fresh_prefix),
            Case("refused-installation-is-rebuilt", _refused_installation_rebuilt),
            Case("unreadable-recipe-input-keeps-the-installation", _unreadable_recipe_keeps_installation),
            Case("locked-base-dependency-closure", _base_lock),
            Case("base-listing-answers-no-question", _base_listing_answers_no_question),
            Case("tool-sail-pins-are-the-locked-release", _tool_sail_pins_agree)]
