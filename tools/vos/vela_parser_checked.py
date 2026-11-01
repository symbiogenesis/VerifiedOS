# SPDX-License-Identifier: Apache-2.0
"""Qualify the bounded Menhir Rocq support prerequisite in an isolated native tree.

This builds no Vela parser and installs nothing. Abstract automaton parameters
remain visible in the recorded assumption queries; a concrete generated grammar
and its executable correspondence still need their own qualification.
"""

import hashlib
import io
import json
import re
import subprocess
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path, PurePosixPath
from typing import cast

from filelock import FileLock

from vos import proofenv
from vos.atomic import atomic_path

RELEASE = "20260209"
ARCHIVE_SHA512 = (
    "aafad186f328ae8dd4cc69af0f30c1a0b208cf5148a7a94c150099be03838503c5ec1"
    "2918de26cd7f794b5a72f114bc1bae8d81058bd0ea10372a3b06818687e"
)
ARCHIVE_URL = f"https://opam.ocaml.org/cache/sha512/aa/{ARCHIVE_SHA512}"
UPSTREAM_REPAIR = "6dedce5de5df8f139c42326f3bd95e7a1c878674"
INTERPRETER_SHA256 = "4891ad9d65843fefa4d9d424e0d065e241760f705464efc233796d445b16294f"
CANDIDATE_SHA256 = "69cfbdd086858ef37fa50eed10866379a51bd858113a9716331d88f9e46e7fde"
REFERENCE_SHA256 = "04aa7bda193a67219fea99ee6f1b86eb7db3da735b04e32f662ac1e5c041b02c"
VERSION_SHA256 = "3746feeefa899fe0d43e4db0ec53f2d7ddd72076d9fab29cdcc9ecb0250072e6"
LICENSES = {
    "LICENSE": "9c97527b92b577647880abd2a5eaf5bf0f3b3df1bd09d9f93fc4e103eb1d30d5",
    "coq-menhirlib/LICENSE": "218c42550a9b4ff6e48bf38218908755fe156b2e5c586531c2eb8893248a102d",
}
MODULES = (
    "Alphabet", "Automaton", "Grammar", "Interpreter", "Interpreter_complete",
    "Interpreter_correct", "Main", "Validator_classes", "Validator_complete",
    "Validator_safe", "Version",
)
TARGETS = ("pop", "reduce_step", "parse")
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
TIMEOUT = 180

FROZEN_QUERY = """From MenhirLib Require Import Automaton Interpreter.
Set Printing All.
Set Printing Universes.
Set Printing Depth 1000000.
Set Printing Width 1000000.
Module Probe (A: Automaton.T).
Module I := Interpreter.Make A.
Check I.pop.
Print I.pop.
Print Assumptions I.pop.
Check I.reduce_step.
Print I.reduce_step.
Print Assumptions I.reduce_step.
Check I.parse.
Print I.parse.
Print Assumptions I.parse.
End Probe.
"""
ASSUMPTIONS_QUERY = """From MenhirLib Require Import Automaton Main.
Module SupportBoundary (Aut : Automaton.T).
Module Parser := Main.Make Aut.
Print Assumptions Parser.parse_correct.
Print Assumptions Parser.parse_complete.
Print Assumptions Parser.unambiguity.
End SupportBoundary.
"""


def _sha256(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _proof_openings(source: bytes, *, reference: bool = False) -> bytes:
    """Move only the three reviewed commands, or omit them in the diagnostic twin."""
    if _sha256(source) != INTERPRETER_SHA256:
        raise ValueError("unsupported Menhir Interpreter source; compatibility repair refused")
    lines = source.decode("utf-8").splitlines(keepends=True)
    for name in TARGETS:
        heads = [index for index, line in enumerate(lines)
                 if re.match(rf"^(?:Fixpoint|Definition) {name}\b", line)]
        if len(heads) != 1:
            raise ValueError(f"expected one reviewed declaration: {name}")
        start = heads[0]
        end = next(index for index in range(start + 1, len(lines))
                   if lines[index] == "Defined.\n")
        tactics = [index for index in range(start + 1, end)
                   if re.match(r"^(?:unshelve )?refine\b", lines[index])]
        proofs = [index for index in range(start + 1, end) if lines[index] == "Proof.\n"]
        if len(tactics) != 1 or len(proofs) != 1 or proofs[0] <= tactics[0]:
            raise ValueError(f"unsupported proof opening: {name}")
        command = lines.pop(proofs[0])
        if not reference:
            lines.insert(tactics[0], command)
    candidate = "".join(lines).encode("utf-8")
    wanted = REFERENCE_SHA256 if reference else CANDIDATE_SHA256
    if _sha256(candidate) != wanted:
        raise ValueError("Menhir proof-command repair differs from the reviewed candidate")
    return candidate


def _release_sources(archive: bytes) -> dict[str, bytes]:
    """Read only the needed regular files from the authenticated immutable archive."""
    if len(archive) > MAX_ARCHIVE_BYTES or hashlib.sha512(archive).hexdigest() != ARCHIVE_SHA512:
        raise ValueError("Menhir release archive digest differs from the selected source")
    selected = {f"coq-menhirlib/src/{name}.v" for name in MODULES}
    selected.update(("coq-menhirlib/src/_CoqProject", *LICENSES))
    sources: dict[str, bytes] = {}
    total = 0
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
        for ordinal, member in enumerate(bundle):
            if ordinal > 5000:
                raise ValueError("Menhir archive exceeds its member bound")
            parts = PurePosixPath(member.name).parts
            if len(parts) == 1 and member.isdir():
                continue
            if (len(parts) < 2 or PurePosixPath(member.name).is_absolute()
                    or ".." in parts or "\\" in member.name):
                raise ValueError("unsafe Menhir archive member")
            relative = PurePosixPath(*parts[1:]).as_posix()
            if relative not in selected:
                continue
            if relative in sources or not member.isfile() or member.size < 0:
                raise ValueError("ambiguous or non-regular Menhir source")
            total += member.size
            if total > MAX_ARCHIVE_BYTES:
                raise ValueError("Menhir support sources exceed their byte bound")
            stream = bundle.extractfile(member)
            if stream is None:
                raise ValueError("unreadable Menhir archive source")
            with stream:
                sources[relative] = stream.read(MAX_ARCHIVE_BYTES + 1)
    if set(sources) != selected:
        raise ValueError("Menhir archive omits selected support sources")
    for name, wanted in (*LICENSES.items(), ("coq-menhirlib/src/Version.v", VERSION_SHA256)):
        if _sha256(sources[name]) != wanted:
            raise ValueError(f"Menhir reviewed source differs: {name}")
    return sources


def _write_json(path: Path, value: dict[str, object]) -> None:
    with atomic_path(path) as pending:
        pending.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8", newline="")


def _opam(arguments: list[str]) -> list[str]:
    return ["opam", "exec", "--switch", proofenv.ROCQ_SWITCH, "--", *arguments]


def _run(arguments: list[str], directory: Path, log: Path,
         steps: list[dict[str, object]], *, refusal: str | None = None,
         source: bytes | None = None) -> str:
    started = time.monotonic()
    try:
        done = subprocess.run(arguments, cwd=directory, capture_output=True,
                              input=source, timeout=TIMEOUT, check=False)
    except subprocess.TimeoutExpired as error:
        log.write_bytes((error.stdout or b"") + (error.stderr or b""))
        steps.append({"command": arguments, "directory": str(directory),
                      "status": "timeout", "log": str(log)})
        raise RuntimeError(f"Menhir support command exceeded {TIMEOUT} seconds: {arguments[0]}") from error
    # Keep the streams separate for byte-for-byte frozen-reading comparisons.
    log.write_bytes(done.stdout)
    error_log = log.with_suffix(".stderr")
    error_log.write_bytes(done.stderr)
    steps.append({"command": arguments, "directory": str(directory), "exit": done.returncode,
                  "seconds": round(time.monotonic() - started, 6), "stdout": str(log),
                  "stderr": str(error_log), "stdout_sha256": _sha256(done.stdout),
                  "stderr_sha256": _sha256(done.stderr)})
    output = done.stdout.decode("utf-8")
    detail = done.stderr.decode("utf-8")
    if refusal is not None:
        if done.returncode != 1 or refusal not in output + detail:
            raise RuntimeError("Menhir version mismatch did not produce the expected compiler refusal")
    elif done.returncode:
        raise RuntimeError(f"Menhir support command exited {done.returncode}: {(detail or output)[-3000:]}")
    return output


def _inputs(root: Path) -> dict[str, str]:
    return {name: _sha256((root / name).read_bytes()) for name in (
        "tools/opam/rocq.lock", "tools/opam/sail.lock", "tools/vos/vela_parser_checked.py")}


def _toolchain(root: Path, directory: Path, steps: list[dict[str, object]]) -> dict[str, object]:
    sail = (root / "tools/opam/sail.lock").read_text(encoding="utf-8")
    if set(re.findall(r'"menhir\.([^"\s]+)"', sail)) != {RELEASE}:
        raise ValueError("support source does not match the Sail snapshot's Menhir generator")
    lock = (root / "tools/opam/rocq.lock").read_text(encoding="utf-8")
    if set(re.findall(r'"rocq-core\.([^"\s]+)"', lock)) != {proofenv.ROCQ_VERSION}:
        raise ValueError("support prover differs from the proof snapshot")
    version = _run(_opam(["rocq", "c", "--version"]), root,
                   directory / "toolchain.stdout", steps)
    found = re.search(r"\bversion\s+([^\s]+)", version)
    releases = {proofenv.ROCQ_VERSION, proofenv.ROCQ_VERSION.removesuffix(".0")}
    if found is None or found[1] not in releases:
        raise ValueError("Menhir support compiler differs from the locked prover")
    compiler = _run(_opam(["ocamlc", "-version"]), root,
                    directory / "ocaml.stdout", steps).strip()
    if compiler != proofenv.OCAML_VERSION:
        raise ValueError("Menhir support OCaml compiler differs from the project switch")
    binary = _run(["opam", "var", "bin", "--switch", proofenv.ROCQ_SWITCH], root,
                  directory / "tool-path.stdout", steps).strip()
    binary_dir = Path(binary)
    if not binary_dir.is_absolute():
        raise ValueError("opam returned a relative support tool directory")
    return {"switch": proofenv.ROCQ_SWITCH, "rocq": version.strip(), "ocamlc": compiler,
            "binary_sha256": {name: _sha256((binary_dir / name).read_bytes())
                              for name in ("rocq", "rocqchk", "ocamlc")}}


def _runtime(directory: Path, steps: list[dict[str, object]]) -> dict[str, object]:
    """Bind installed proof inputs, including every physical LoadPath root."""
    config = _run(_opam(["rocq", "c", "-config"]), directory,
                  directory / "runtime-config.stdout", steps)
    where = _run(_opam(["rocqchk", "-where"]), directory,
                 directory / "runtime-where.stdout", steps).strip()
    paths = _run(_opam(["rocq", "top", "-q", "-quiet"]), directory,
                 directory / "runtime-loadpath.stdout", steps, source=b"Print LoadPath.\n")
    settings = dict(line.split("=", 1) for line in config.splitlines() if "=" in line)
    if any(key not in settings or not Path(settings[key]).is_absolute()
           for key in ("COQLIB", "COQCORELIB")):
        raise ValueError("unsupported Menhir support prover library configuration")
    roots = {Path(settings[key]).resolve() for key in ("COQLIB", "COQCORELIB")}
    if not where or not Path(where).is_absolute():
        raise ValueError("unsupported Menhir support kernel library path")
    roots.add(Path(where).resolve())
    # The prover prints long load-path rows on two lines on some platforms.
    listing = re.sub(r"\n\s+(/)", r" \1", paths).splitlines()
    if not listing or listing[0] != "Installed / Logical Path / Physical path:":
        raise ValueError("unsupported Menhir support prover load-path listing")
    for line in listing[1:]:
        found = re.fullmatch(r"\s*(?:i\s+)?(?:<>|[\w.]+)\s+(/.+)", line)
        if found is None:
            raise ValueError("unsupported Menhir support prover load-path row")
        path = Path(found[1]).resolve()
        if path != directory.resolve():
            roots.add(path)
    minimal = sorted(path for path in roots
                     if not any(path != other and path.is_relative_to(other) for other in roots))
    files: dict[str, str] = {}
    for root in minimal:
        if not root.is_dir():
            raise ValueError("Menhir support installed library root is missing")
        for path in sorted(root.rglob("*")):
            if path.is_symlink() and path.is_dir():
                raise ValueError("Menhir support installed library has a directory alias")
            if path.is_file():
                files[str(path)] = _sha256(path.read_bytes())
    if not files:
        raise ValueError("Menhir support installed library inventory is empty")
    return {"config": config, "load_path": paths, "files_sha256": files}


def _stage(sources: dict[str, bytes], directory: Path, *, reference: bool) -> None:
    directory.mkdir()
    for path, source in sources.items():
        relative = path.removeprefix("coq-menhirlib/src/")
        # The selected license notices accompany every private build tree.
        if path in LICENSES:
            relative = "LICENSE.generator" if path == "LICENSE" else "LICENSE.support"
        content = _proof_openings(source, reference=reference) if relative == "Interpreter.v" else source
        (directory / relative).write_bytes(content)


def _compile(directory: Path, steps: list[dict[str, object]]) -> None:
    _run(_opam(["rocq", "makefile", "-f", "_CoqProject", "-o", "CoqMakefile"]),
         directory, directory / "makefile.stdout", steps)
    _run(_opam(["make", "-f", "CoqMakefile", "-j2"]),
         directory, directory / "compile.stdout", steps)


def _work_root(root: Path) -> Path:
    directory = proofenv.lane_root(proofenv.lane_of(root)) / "vela-parser-checked"
    kind = proofenv.filesystem(directory)
    if not kind or kind in proofenv.CROSS_OS_FILESYSTEMS | proofenv.VOLATILE_FILESYSTEMS:
        raise ValueError("Menhir support outputs require a persistent native filesystem")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _archive(path: Path | None, directory: Path) -> bytes:
    if path is not None:
        with path.open("rb") as stream:
            return stream.read(MAX_ARCHIVE_BYTES + 1)
    with urllib.request.urlopen(ARCHIVE_URL, timeout=TIMEOUT) as response:
        source = cast("bytes", response.read(MAX_ARCHIVE_BYTES + 1))
    (directory / "menhir.tar.gz").write_bytes(source)
    return source


def _observations(candidate: Path, reference: Path, guard: str,
                  steps: list[dict[str, object]]) -> dict[str, str]:
    probes = {candidate / "Frozen.v": FROZEN_QUERY, reference / "Frozen.v": FROZEN_QUERY,
              candidate / "Assumptions.v": ASSUMPTIONS_QUERY,
              candidate / "VersionAccepted.v": guard,
              candidate / "VersionRefused.v": guard.replace(f"require_{RELEASE}", "require_unreleased")}
    for path, text in probes.items():
        _require(path.read_bytes() == text.encode(), "Menhir support probe changed during qualification")
    for step in steps:
        for stream in ("stdout", "stderr"):
            _require(_sha256(Path(str(step[stream])).read_bytes()) == step[f"{stream}_sha256"],
                     "Menhir support transcript changed during qualification")
    return {str(path): _sha256(text.encode()) for path, text in probes.items()}


def qualify(root: Path, *, archive: Path | None = None) -> dict[str, object]:
    """Freshly build, compare and kernel-check the support prerequisite; install nothing."""
    work = _work_root(root)
    with FileLock(work / "qualification.lock", timeout=1):
        latest = work / "qualification.json"
        latest.unlink(missing_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="support-", dir=work))
        steps: list[dict[str, object]] = []
        attempt: dict[str, object] = {"schema": 1, "scope": "menhir-rocq-support-prerequisite",
                                      "directory": str(directory), "steps": steps, "status": "running"}
        try:
            inputs = _inputs(root)
            tools = _toolchain(root, directory, steps)
            runtime = _runtime(directory, steps)
            contents = _archive(archive, directory)
            sources = _release_sources(contents)
            candidate, reference = directory / "candidate", directory / "reference"
            _stage(sources, candidate, reference=False)
            _stage(sources, reference, reference=True)
            for tree in (candidate, reference):
                _compile(tree, steps)
                (tree / "Frozen.v").write_text(FROZEN_QUERY, encoding="utf-8", newline="")
                _run(_opam(["rocq", "c", "-R", ".", "MenhirLib", "Frozen.v"]),
                     tree, tree / "frozen.stdout", steps)
            outputs = {str(tree.name): {f"{name}.vo": _sha256((tree / f"{name}.vo").read_bytes())
                                       for name in MODULES} for tree in (candidate, reference)}
            frozen = (candidate / "frozen.stdout").read_bytes()
            _require(bool(frozen) and frozen == (reference / "frozen.stdout").read_bytes(),
                     "same-prover Menhir public types, bodies, universes or assumptions differ")
            _run(_opam(["rocqchk", "-R", ".", "MenhirLib",
                        *(f"MenhirLib.{module}" for module in MODULES)]),
                 candidate, candidate / "kernel.stdout", steps)
            (candidate / "Assumptions.v").write_text(ASSUMPTIONS_QUERY, encoding="utf-8", newline="")
            _run(_opam(["rocq", "c", "-R", ".", "MenhirLib", "Assumptions.v"]),
                 candidate, candidate / "assumptions.stdout", steps)
            guard = f"From MenhirLib Require Version.\nDefinition generator_version : unit := Version.require_{RELEASE}.\n"
            (candidate / "VersionAccepted.v").write_text(guard, encoding="utf-8", newline="")
            _run(_opam(["rocq", "c", "-R", ".", "MenhirLib", "VersionAccepted.v"]),
                 candidate, candidate / "guard-accepted.stdout", steps)
            (candidate / "VersionRefused.v").write_text(
                guard.replace(f"require_{RELEASE}", "require_unreleased"), encoding="utf-8", newline="")
            _run(_opam(["rocq", "c", "-R", ".", "MenhirLib", "VersionRefused.v"]),
                 candidate, candidate / "guard-refused.stdout", steps, refusal="require_unreleased")
            _require(_inputs(root) == inputs and _toolchain(root, directory, steps) == tools,
                     "support qualification inputs or toolchain changed during execution")
            _require(_runtime(directory, steps) == runtime,
                     "support installed library inputs changed during execution")
            for tree, wanted in ((candidate, CANDIDATE_SHA256), (reference, REFERENCE_SHA256)):
                for path, source in sources.items():
                    name = path.removeprefix("coq-menhirlib/src/")
                    if path in LICENSES:
                        name = "LICENSE.generator" if path == "LICENSE" else "LICENSE.support"
                    digest = wanted if name == "Interpreter.v" else _sha256(source)
                    _require(_sha256((tree / name).read_bytes()) == digest,
                             "Menhir support source changed during qualification")
                for name, digest in outputs[tree.name].items():
                    _require(_sha256((tree / name).read_bytes()) == digest,
                             "Menhir support compiled output changed during qualification")
            probes = _observations(candidate, reference, guard, steps)
            report: dict[str, object] = {
                **attempt, "status": "passed", "inputs": inputs, "toolchain": tools,
                "installed_libraries": runtime, "compiled_sha256": outputs, "probes_sha256": probes,
                "generator_pair_qualified": False, "checked_vela_parser": False,
                "source": {"release": RELEASE, "url": ARCHIVE_URL,
                           "sha512": ARCHIVE_SHA512, "sha256": _sha256(contents),
                           "licenses": LICENSES, "files_sha256": {
                               path: _sha256(source) for path, source in sources.items()}},
                "repair": {"upstream_commit": UPSTREAM_REPAIR,
                           "scope": "relocate-three-existing-Proof-commands",
                           "candidate_sha256": CANDIDATE_SHA256,
                           "diagnostic_reference_sha256": REFERENCE_SHA256,
                           "public_reading_equal": True, "reading_sha256": _sha256(frozen),
                           "query_sha256": _sha256(FROZEN_QUERY.encode())},
                "kernel": {"status": "passed", "recursive": True,
                           "roots": [f"MenhirLib.{module}" for module in MODULES]},
                "version_guard": {"preserved_source_sha256": VERSION_SHA256,
                                  "accepted": f"require_{RELEASE}", "refused": "require_unreleased"},
                "assumptions": {"scope": "abstract-automaton-uninstantiated",
                                "closed_assumptions_accepted": False,
                                "roots": [f"SupportBoundary.Parser.{name}" for name in (
                                    "parse_correct", "parse_complete", "unambiguity")],
                                "query_sha256": _sha256(ASSUMPTIONS_QUERY.encode()),
                                "reading": (candidate / "assumptions.stdout").read_text(encoding="utf-8"),
                                "reading_sha256": _sha256((candidate / "assumptions.stdout").read_bytes())},
                "deferred": ["concrete generated grammar and its exact assumption audit",
                             "exact generator executable and support-library pair",
                             "Vela lexing, locations, extraction and runtime correspondence",
                             "prototype migration and Python parser retirement"],
            }
            _write_json(directory / "qualification.json", report)
            _write_json(latest, report)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            attempt.update(status="failed", reason=str(error))
            _write_json(directory / "attempt.json", attempt)
            raise
        else:
            return report
