#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The curated Sail model's build loops, from the fastest to the slowest.

Core build and validation commands (executed in the WSL guest toolchain via
`[vos/env.py](../env.py)`, except host-safe commands listed in
`[vos/commands.py](../commands.py)`):
- `typecheck`: typecheck the Sail model without emitting code.
- `bundle`: emit and canonicalize the machine-readable Sail bundle (`K-88`).
- `emit`: emit C++ and validate the frozen profile against the generated schema.
- `rocq`: emit the canonical Rocq machine term and its generation-identity receipt
  (`[vos/rocqterm.py](../rocqterm.py)`).
- `dependencies`: materialize verified dependency inputs before CMake configure.
- `build`: configure, build, and run the bundled `ctest` suite (`--fast` omits `-g`;
  `--background` detaches while retaining the lane lock).
- `wait`: wait for the current lane's build lock and validate its receipt.
- `lane`: print the checkout's isolated build lane paths and active lock holder.
- `smt`: emit and discharge `$[property]` obligations in `cap_properties.sail`.
- `oracle`: build the pinned M0.4 `sail-cheri-riscv` oracle and verify its RV64 suite.
- `sweep`: classify `riscv-tests` ELFs (`PASS`, `REFUSE`, `HANG`) against the frozen profile.
- `trace-diff`: adjudicate traces between the curated model and the M0.4 oracle.
- `corpus`: assemble and run the differential corpus (`[docs/assurance/differential-corpus.md](../../../docs/assurance/differential-corpus.md)`).
- `freeze-emit`: emit the link map and per-site table for the corpus (host-safe).
- `asm`: assemble one dialect program into an ELF image (host-safe).
- `devicetree`: generate, compile with `dtc`, and size-check the attested devicetree.
- `reference`: report the frozen golden model's revision, compiler, property count, and corpus stats.
- `config-keys`, `validate-config`: compare key sets or validate a config against a schema (host-safe).
- `keepalive`: hold the WSL guest distribution up for a bounded duration.
"""

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import IO, cast

from vos import (
    asm,
    block_persistence,
    cli,
    commands,
    compose,
    config,
    differential,
    env,
    freezeschema,
    model_corpus,
    model_dependencies,
    native_build,
    python_dependencies,
    receipts,
    rocqterm,
    sailbundle,
    trace,
)

# Shared handler signature, recovered from argparse with a cast before dispatch.
type Command = Callable[[env.Environment, argparse.Namespace], int]

SCHEMA = "sail_riscv_config_schema.json"
EMIT_TARGET = "generated_sail_riscv_model"

# `sail --doc` embeds the commit and dirty flag when `git rev-parse HEAD` succeeds.
# Disable that lookup with a nonexistent GIT_DIR so identical model sources emit
# identical bundles across commits and lanes. This emitter uses Git only for metadata.
_NO_GIT = "/nonexistent/the-bundle-describes-the-model-not-the-checkout"

# Installation hint used when the required Sail binary is missing.
SAIL_HOW = env.install_line(env.SAIL_INSTALL)

# Shared format for stage exit codes written by `cmd_build` and read by `wait`.
STAGE_EXIT = re.compile(r"^\w+_EXIT=(\d+)$")

# The M0.4 oracle's pinned source, and the only submodule any model command opens.
ORACLE_SRC = "upstream/sail-cheri-riscv"

# Bind only gitlinks consumed by model commands; unrelated pins must not invalidate
# build receipts or evidence. `build_inputs` rejects a missing pin.
BUILD_GITLINKS = (ORACLE_SRC,)
# Command dispatch is dynamic; the selected command is an explicit source root.
BUILD_ENTRYPOINTS = ("tools/run.py", "tools/vos/cli/model.py")
BUILD_INPUTS = ("model", "corpus", "interfaces/block-device-contract.md",
                "tools/generated/dialect-table.json", sailbundle.BUNDLE, sailbundle.SOURCE_IDENTITY,
                "tools/pyproject.toml", "tools/uv.lock", *BUILD_GITLINKS, ".gitmodules")
BUILD_ARTIFACTS = ("c_emulator/sail_riscv_sim", "test/unit_tests/unit_tests",
                   "test/unit_tests/block_payload", "test/unit_tests/block_reset",
                   "test/unit_tests/block_image",
                   "test/unit_tests/block_receipt",
                   "CMakeCache.txt", "build.ninja")


def build_inputs(root: Path, *extra: str) -> dict[str, str]:
    """Return the model's source manifest with `extra` pathspecs bound beside it.

    Fails closed if any entry in `BUILD_GITLINKS` is missing or not a pinned gitlink.
    """
    implementation = python_dependencies.sources(root, BUILD_ENTRYPOINTS)
    manifest = receipts.inputs(root, *BUILD_INPUTS, *implementation, *extra)
    missing = set(implementation) - manifest.keys()
    if missing:
        raise ValueError("model implementation inputs are not recorded: " + ", ".join(sorted(missing)))
    for gitlink in BUILD_GITLINKS:
        if not manifest.get(gitlink, "").startswith("gitlink:"):
            raise ValueError(f"{gitlink} is not a pinned gitlink in this checkout's index, "
                             "and the model's build identity binds it")
    return manifest


def _generator_identity() -> rocqterm.GeneratorIdentity:
    sail = shutil.which("sail")
    if sail is None:
        raise ValueError("the selected Sail generator is missing")
    return rocqterm.generator_identity(sail)


def _observed_revision(e: env.Environment) -> str:
    """Observe checkout provenance without making unrelated commits stale a build."""
    version = subprocess.run(
        ["git", "describe", "--tags", "--always"],
        cwd=e.model, capture_output=True, text=True, check=False, timeout=60,
        env={**os.environ, **env.git_env(e.root)})
    if version.returncode or not version.stdout.strip():
        raise ValueError("git could not identify the model for its build receipt")
    return version.stdout.strip()


def build_identity(e: env.Environment) -> dict[str, object]:
    """Return the source closure, selected tools, and build options of a model run."""
    if e.model.resolve() != (e.root / "model").resolve():
        raise ValueError("recorded builds require this checkout's model; unset VOS_MODEL")
    compilers = [arg.split("=", 1)[1] for arg in e.compilers if "=" in arg]
    return {
        "inputs": build_inputs(e.root),
        "tools": receipts.executables("sail", "z3", "cmake", "ctest", "ninja",
                                      *(compilers or ["cc", "c++"])),
        "compiler_options": list(e.compilers), "cache_options": list(e.ccache),
        "generator_inputs": _generator_identity(),
    }


def build_artifacts(directory: Path, model_root: Path) -> dict[str, str]:
    """Return digests of `BUILD_ARTIFACTS` and the verified downloaded ELF suite inputs."""
    inputs = model_corpus.sweep_corpus(directory, model_root)
    recorded = receipts.snapshot(directory, [directory / rel for rel in BUILD_ARTIFACTS])
    base = directory.resolve()
    for path, digest in inputs.items():
        recorded[(path.parent.resolve() / path.name).relative_to(base).as_posix()] = digest
    return dict(sorted(recorded.items()))


def verified_build(e: env.Environment, *, fast: bool = False) -> dict[str, object]:
    """Read a successful build receipt and reject stale sources or artifacts."""
    log = e.log("model-build-fast" if fast else "model-build")
    path = log.with_suffix(".json")
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"invalid build receipt: {path}")
    record = cast("dict[str, object]", raw)
    if (record.get("schema") != 1 or record.get("exit_code") != 0
            or record.get("stages") != {"configure": 0, "build": 0, "ctest": 0}):
        refusal = record.get("refusal")
        raise ValueError("the build receipt does not record a successful complete build"
                         + (f": {refusal}" if isinstance(refusal, str) and refusal else ""))
    if record.get("identity") != build_identity(e):
        raise ValueError("the build receipt is stale: sources, tools or options changed")
    if record.get("artifacts") != build_artifacts(
            e.fast_build_dir if fast else e.build_dir, e.model):
        raise ValueError("the build receipt is stale: built artifacts changed")
    native_build.verify(record.get("native_inputs"),
                        e.fast_build_dir if fast else e.build_dir, e.model)
    if record.get("log_sha256") != receipts.digest(log):
        raise ValueError("the build receipt is stale: its test log changed")
    return record

ORACLE_TARGET = "c_emulator/cheri_riscv_sim_RV64"

# The oracle's embedded `sail-riscv` submodule and initialization command.
ORACLE_NESTED = "sail-riscv"
ORACLE_INIT = f"git submodule update --init --recursive {ORACLE_SRC}"

# Source stamp recording both pinned commits and byte-for-byte blob verification.
ORACLE_STAMP = ".verifiedos-oracle-source"
ORACLE_STAMP_CLAIM = "bytes"

# Receipt written beside the oracle tree after its bundled RV64 suite passes.
ORACLE_RECEIPT_SUFFIX = ".receipt.json"


def oracle_receipt(tree: Path) -> Path:
    """Return the receipt path beside `tree` for its latest passing suite run."""
    return tree.with_name(tree.name + ORACLE_RECEIPT_SUFFIX)


# The oracle's old-style C declarations require pre-C23 empty-parameter semantics.
# Passed via `C_WARNINGS` because the upstream Makefile hardcodes `gcc` and `C_FLAGS`.
ORACLE_CSTD = "-std=gnu17"


def configure_command(e: env.Environment, build_dir: Path,
                      extra: list[str] | None = None) -> list[str]:
    """Build the CMake configure argv for `build_dir`.

    Explicitly passes `TEST_DOWNLOAD_VERSION` and `SAIL_BIN` so CMake does not retain
    cached paths from an earlier release or opam switch.
    """
    test_version = model_corpus.test_corpus_version(e.model)
    sail = shutil.which("sail")
    return [
        "cmake", "-S", str(e.model), "-B", str(build_dir), "-GNinja",
        "-DCMAKE_BUILD_TYPE=RelWithDebInfo",
        "-DDOWNLOAD_GMP=FALSE",
        "-DENABLE_RISCV_TESTS=TRUE",
        "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=FALSE",
        "-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=FALSE",
        *e.compilers, *e.ccache, *(extra or []),
        f"-DTEST_DOWNLOAD_VERSION={test_version}",
        *([f"-DSAIL_BIN={sail}"] if bool(sail) else []),
    ]


def _prepared_options(e: env.Environment, build_dir: Path) -> list[str]:
    """Keep ordered loader selection in the graph as well as in the receipt."""
    options = model_dependencies.prepare(e.model, build_dir, offline=e.model_offline,
                                         cache_root=e.lane_root / "model-dependencies")
    identity = json.dumps(_generator_identity(), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return [*options, f"-DVOS_SAIL_LOADER_IDENTITY={digest}"]


def _configure(e: env.Environment, build_dir: Path,
               extra: list[str] | None = None, out: IO[str] | None = None) -> int:
    try:
        prepared = _prepared_options(e, build_dir)
        argv = configure_command(e, build_dir, [*(extra or []), *prepared])
    except (OSError, ValueError, RuntimeError) as err:
        print(f"model preparation refused: {err}", file=out or sys.stderr)
        return 1
    return env.stage("configure", argv, stdout=out, stderr=out,
                     add_env=env.git_env(e.root) or None)


def cmd_dependencies(e: env.Environment, args: argparse.Namespace) -> int:
    """Materialize verified inputs without configuring or compiling the model."""
    directory = e.fast_build_dir if args.fast else e.build_dir
    lock = env.build_lock(directory)
    try:
        flags = model_dependencies.prepare(e.model, directory, offline=e.model_offline,
                                            cache_root=e.lane_root / "model-dependencies")
    except (OSError, ValueError, RuntimeError) as err:
        print(f"model preparation refused: {err}", file=sys.stderr)
        return 1
    finally:
        if lock is not None:
            lock.close()
    print(json.dumps({"build": str(directory), "offline": e.model_offline,
                      "configure_options": flags}, indent=2))
    return 0


def cmd_simulator(e: env.Environment, args: argparse.Namespace) -> int:
    from vos import simulator_build  # noqa: PLC0415
    return simulator_build.build(e, Path(args.out))


def _require(binary: str, how: str) -> None:
    """Exit with an installation hint if `binary` is not on `PATH`."""
    if shutil.which(binary) is None:
        raise SystemExit(f"no `{binary}` on PATH; {how}")


def _missing_simulator(e: env.Environment) -> str | None:
    """Return an error message if the lane's simulator binary has not been built."""
    if e.simulator.exists():
        return None
    return f"no simulator at {e.simulator}; run `run.py model build` first"


def cmd_typecheck(e: env.Environment, args: argparse.Namespace) -> int:
    """Typecheck the curated model without emitting code."""
    _require("sail", SAIL_HOW)
    # Lock the lane's typecheck memo cache because Sail rewrites it whole on exit.
    with env.hold_lock(e.typecheck_cache, "a typecheck"):
        _seed_cache_file([e.primary_typecheck_cache], e.typecheck_cache)
        return subprocess.run(
            ["sail", "--strict-var", "--strict-bitvector", "--strict-exponentials",
             "--memo-z3", "--memo-z3-path", str(e.typecheck_cache),
             "--just-check", "--all-modules", "riscv.sail_project"],
            cwd=e.model / "model", check=False).returncode


def _bundle_source_identity(e: env.Environment, listed: list[str], inputs: bytes,
                            bundle_bytes: bytes) -> bytes:
    """Refuse a project or source change while the bundle emitter was reading it."""
    refreshed = rocqterm.listed_sources("sail", e.model)
    fresh = sailbundle.source_identity(e.root, refreshed, bundle_bytes)
    final_inputs = json.loads(fresh)
    final_inputs["bundle_sha256"] = hashlib.sha256(b"").hexdigest()
    if refreshed != listed or final_inputs != json.loads(inputs):
        raise sailbundle.BundleError("the model project or sources changed during bundle emission")
    sailbundle.read_source_identity(e.root, bundle_bytes, identity_bytes=fresh)
    return fresh


def cmd_bundle(e: env.Environment, args: argparse.Namespace) -> int:
    """Emit or check (`--check`) the model's machine-readable bundle (`K-88`).

    Invokes `sail --doc` directly under the lane's build lock (using the build tree's
    SMT memo cache), canonicalizes library paths via `[vos/sailbundle.py](../sailbundle.py)`,
    and verifies source provenance before updating or comparing the tracked bundle.
    """
    _require("sail", SAIL_HOW)
    build_dir = e.build_dir
    lock = env.build_lock(build_dir)
    scratch = e.lane_root / "bundle"
    try:
        _seed_tree(e, build_dir)
        tracked = e.root / sailbundle.BUNDLE
        scratch.mkdir(parents=True, exist_ok=True)
        before = tracked.read_bytes() if tracked.is_file() else None
        identity = e.root / sailbundle.SOURCE_IDENTITY
        before_identity = identity.read_bytes() if identity.is_file() else None
        listed = rocqterm.listed_sources("sail", e.model)
        inputs = sailbundle.source_identity(e.root, listed, b"")
        written = scratch / sailbundle.BUNDLE_NAME
        written.unlink(missing_ok=True)
        code = env.stage("bundle", [
            "sail",
            "--strict-var", "--strict-bitvector", "--strict-exponentials",
            "--memo-z3", "--memo-z3-path", str(build_dir / "model" / "sail_smt_cache"),
            "--doc",
            "--doc-format", "identity",
            "--doc-compact",
            "--doc-embed", "plain",
            "--doc-embed-with-location",
            "-o", str(scratch),
            "--doc-bundle", sailbundle.BUNDLE_NAME,
            "--all-modules", "riscv.sail_project",
        ], cwd=e.model / "model", add_env={"GIT_DIR": _NO_GIT})
        if code:
            return code
        if not written.is_file():
            print(f"sail exited 0 and wrote no {written}", file=sys.stderr)
            return 1
        fresh = sailbundle.canonicalize_library(
            written.read_bytes(), env.opam_root() / env.SAIL_SWITCH / "share/sail")
        written.write_bytes(fresh)
        fresh_identity = _bundle_source_identity(e, listed, inputs, fresh)
        written_identity = scratch / sailbundle.SOURCE_IDENTITY_NAME
        written_identity.write_bytes(fresh_identity)
        if not args.check:
            with receipts.atomic_path(tracked) as pending:
                pending.write_bytes(fresh)
            with receipts.atomic_path(identity) as pending:
                pending.write_bytes(fresh_identity)
        code = _bundle_verdict(written, before, check=args.check)
        identity_code = _bundle_verdict(written_identity, before_identity, check=args.check,
                                        path=sailbundle.SOURCE_IDENTITY)
        code = max(code, identity_code)
    except (OSError, sailbundle.BundleError, rocqterm.TermError) as err:
        print(str(err), file=sys.stderr)
        return 1
    finally:
        if scratch.is_dir():
            shutil.rmtree(scratch, ignore_errors=True)
        if lock is not None:
            lock.close()
    return code


def _bundle_verdict(written: Path, held: bytes | None, *, check: bool,
                    path: str = sailbundle.BUNDLE) -> int:
    """Compare emitted `written` bytes against prior `held` bytes and print the verdict."""
    fresh = written.read_bytes()
    if not check:
        moved = "unchanged" if held == fresh else "rewritten"
        print(f"ok {path}: {len(fresh)} bytes, {moved}")
        return 0
    if held is None:
        print(f"{path} is not there, so the emitter's {len(fresh)} bytes "
              "are held against nothing", file=sys.stderr)
        return 1
    if held != fresh:
        where = next((i for i, (a, b) in enumerate(zip(held, fresh, strict=False))
                      if a != b), min(len(held), len(fresh)))
        print(f"{path} is {len(held)} bytes and the emitter writes "
              f"{len(fresh)}, first differing at byte {where}; regenerate it with "
              "`run.py model bundle`", file=sys.stderr)
        return 1
    print(f"ok {path}: {len(fresh)} bytes, byte-identical after "
          "canonical library-path relocation from the model in this checkout")
    return 0


def cmd_emit(e: env.Environment, args: argparse.Namespace) -> int:
    """Run C++ emission to regenerate the config schema, then validate the frozen profile."""
    _require("sail", SAIL_HOW)
    build_dir = e.build_dir
    lock = env.build_lock(build_dir)
    try:
        _seed_tree(e, build_dir)
        if _configure(e, build_dir):
            return 1
        if env.stage("emit", ["cmake", "--build", str(build_dir), "-j", str(e.jobs),
                              "--target", EMIT_TARGET]):
            return 1
        code, lines = config.validate(build_dir / SCHEMA, e.profile)
        print("\n".join(lines))
        return code
    finally:
        if lock is not None:
            lock.close()


def _ninja_commands(build_dir: Path) -> str:
    """Return the `ninja -t commands` output for `rocqterm.TARGET`."""
    done = subprocess.run(["ninja", "-C", str(build_dir), "-t", "commands",
                           rocqterm.TARGET], capture_output=True, encoding="utf-8",
                          errors="replace", check=False, timeout=120)
    if done.returncode != 0:
        raise rocqterm.TermError(f"ninja could not list {rocqterm.TARGET}'s commands: "
                                 f"{done.stderr.strip()}")
    return done.stdout


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _settled(e: env.Environment, code: int, listed: list[str], before: rocqterm.Inputs,
             sail: str, z3: str, tools: rocqterm.Toolchain) -> None:
    """Verify that Rocq emission exited zero, wrote all outputs, and had stable inputs/tools."""
    out = rocqterm.output_dir(e.build_dir)
    if code:
        raise rocqterm.TermError(f"{rocqterm.TARGET} exited {code}")
    missing = [name for name in rocqterm.OUTPUTS if not (out / name).is_file()]
    if missing:
        raise rocqterm.TermError(f"{rocqterm.TARGET} exited 0 and wrote no "
                                 f"{', '.join(missing)} under {out}")
    if rocqterm.inputs(e.root, listed, e.profile) != before:
        raise rocqterm.TermError("the configuration or a source changed while the term "
                                 "was emitted; emit again from a still tree")
    if rocqterm.toolchain(sail, z3) != tools:
        raise rocqterm.TermError("the toolchain changed while the term was emitted")


def cmd_rocq(e: env.Environment, args: argparse.Namespace) -> int:
    """Emit the canonical Rocq machine term and write its generation-identity receipt (`[vos/rocqterm.py](../rocqterm.py)`)."""
    del args
    _require("sail", SAIL_HOW)
    if e.model.resolve() != (e.root / "model").resolve():
        print("the term's identity names this checkout's model; unset VOS_MODEL",
              file=sys.stderr)
        return 1
    build_dir = e.build_dir
    out = rocqterm.output_dir(build_dir)
    lock = env.build_lock(build_dir)
    try:
        removed = rocqterm.clear(build_dir)
        if removed:
            print(f"removed stale {', '.join(removed)} from {out}")
        if not e.profile.is_file():
            print(f"no frozen profile at {e.profile}; the Rocq target emits at it and at "
                  "nothing else", file=sys.stderr)
            return 1
        _seed_tree(e, build_dir)
        if _configure(e, build_dir):
            return 1
        sail = shutil.which("sail") or "sail"
        z3 = shutil.which("z3") or "z3"
        try:
            argv = rocqterm.target_command(_ninja_commands(build_dir))
            rocqterm.require_profile(argv, e.profile)
            listed = rocqterm.listed_sources(sail, e.model)
            before = rocqterm.inputs(e.root, listed, e.profile)
            tools = rocqterm.toolchain(sail, z3)
            checkout = rocqterm.revision(e.root, env.git_env(e.root))
        except (OSError, rocqterm.TermError) as err:
            print(str(err), file=sys.stderr)
            return 1
        started, clock = _utc(), time.perf_counter()
        code = env.stage("rocq", ["cmake", "--build", str(build_dir), "-j", "1",
                                  "--target", rocqterm.TARGET])
        elapsed, finished = time.perf_counter() - clock, _utc()
        try:
            _settled(e, code, listed, before, sail, z3, tools)
            payload = rocqterm.receipt(
                command=rocqterm.placeheld(argv, build_dir, e.root), tools=tools,
                read=before, checkout=checkout, tree=build_dir, started=started,
                finished=finished, elapsed=elapsed)
            receipts.write(out / rocqterm.RECEIPT, payload)
        except (OSError, rocqterm.TermError) as err:
            rocqterm.clear(build_dir)
            print(str(err), file=sys.stderr)
            return 1
        for name in rocqterm.OUTPUTS:
            got = rocqterm.file_identity(out / name)
            print(f"{name}: sha256 {got['sha256']}, {got['bytes']} bytes, "
                  f"{got['lines']} lines")
        names = rocqterm.axioms((out / rocqterm.OUTPUTS[0]).read_text(
            encoding="utf-8", errors="replace"))
        print(f"{len(names)} axiom(s) declared; configuration "
              f"{before['configuration']['sha256']}; sources "
              f"{before['sources']['aggregate']} over {before['sources']['files']} files")
        print(f"ok the canonical term and its receipt are under {out}")
        return 0
    finally:
        if lock is not None:
            lock.close()


def cmd_build(e: env.Environment, args: argparse.Namespace) -> int:
    """Configure, build, and run the bundled `ctest` suite for the curated model.

    `--fast` selects a separate iterate build tree that omits `-g` from `RelWithDebInfo`.
    `--background` detaches the build into a child process that inherits the lane lock.
    """
    _require("sail", SAIL_HOW)
    if args.fast:
        build_dir = e.fast_build_dir
        log = e.log("model-build-fast")
        extra = ["-DCMAKE_CXX_FLAGS_RELWITHDEBINFO=-O2 -DNDEBUG",
                 "-DCMAKE_C_FLAGS_RELWITHDEBINFO=-O2 -DNDEBUG"]
    else:
        build_dir, log, extra = e.build_dir, e.log("model-build"), []

    lock = env.build_lock(build_dir)
    try:
        _seed_tree(e, build_dir)
        if args.background:
            return _detach(args, log, lock)
        return _build_locked(e, build_dir, log, extra)
    finally:
        if lock is not None:
            lock.close()


# Sail property test registered in `[model/model/CMakeLists.txt](../../../model/model/CMakeLists.txt)`.
# Uses its own memo cache (`PROPERTY_MEMO`) and depends only on configured inputs,
# so it can run alongside the C++ build when memory permits.
EARLY_TEST = "smt_properties_rv64d"
EARLY_STAGE = "ctest-early"
PROPERTY_MEMO = "sail_smt_cache_properties"
# Additional memory budget (MB) required above `e.build_budget_mb` to run `EARLY_TEST`
# concurrently with the build.
EARLY_TEST_MB = 1024
NINJA_STATUS = "[%f/%t %e] "

# `/proc` thread states in which a thread cannot spawn new processes.
_AT_REST = frozenset({"T", "t", "Z", "X"})


def _stat_fields(path: Path) -> list[str]:
    """Return `/proc/<pid>/stat` fields after the parenthesized command name."""
    try:
        record = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return record[record.rfind(")") + 1:].split()


def _children() -> dict[int, list[int]]:
    """Map parent PIDs to child PIDs from `/proc`."""
    children: dict[int, list[int]] = {}
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            fields = _stat_fields(entry / "stat")
            if len(fields) > 1 and fields[1].isdigit():
                children.setdefault(int(fields[1]), []).append(int(entry.name))
    return children


def _at_rest(pid: int) -> bool:
    """Return True if all threads of `pid` have stopped or exited."""
    try:
        threads = list(Path(f"/proc/{pid}/task").iterdir())
    except OSError:
        return True
    return all((_stat_fields(thread / "stat") or ["X"])[0] in _AT_REST for thread in threads)


def _kill_tree(root: int) -> None:
    """Stop and `SIGKILL` `root` and all descendant processes."""
    if sys.platform == "win32":
        raise RuntimeError("process trees are ended in the guest")
    tree: set[int] = set()
    found = {root}
    while found != tree or not all(_at_rest(pid) for pid in tree):
        for pid in found - tree:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGSTOP)
        tree |= found
        children = _children()
        frontier = list(tree)
        while frontier:
            for child in children.get(frontier.pop(), []):
                if child not in found:
                    found.add(child)
                    frontier.append(child)
    for pid in tree:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)


class _EarlyRun:
    """Background `EARLY_TEST` `ctest` run started alongside the C++ build."""

    def __init__(self, argv: list[str], since: float) -> None:
        self._output = tempfile.TemporaryFile(  # noqa: SIM115
            "w+", encoding="utf-8", errors="replace")
        self._since = since
        self._started = time.perf_counter()
        try:
            self._proc = subprocess.Popen(argv, stdout=self._output, stderr=self._output)
        except OSError:
            self._output.close()
            raise
        self._lock = threading.Lock()
        self._code: int | None = None
        self._cost = ""
        self._reaper = threading.Thread(target=self._reap, name="early-test-reaper",
                                        daemon=True)
        self._reaper.start()

    def _reap(self) -> None:
        """Wait for exit via `WNOWAIT`, then collect resource usage under `self._lock`."""
        if sys.platform == "win32":
            raise RuntimeError("build stages run in the guest")
        os.waitid(os.P_PID, self._proc.pid, os.WEXITED | os.WNOWAIT)
        ended = time.perf_counter()
        with self._lock:
            _, status, usage = os.wait4(self._proc.pid, 0)
            self._code = self._proc.returncode = os.waitstatus_to_exitcode(status)
            self._cost = env.stage_line(EARLY_STAGE, ended - self._started,
                                        usage.ru_utime + usage.ru_stime, usage.ru_maxrss,
                                        start=self._started - self._since)

    def wait(self) -> int:
        """Wait until the run is reaped, and give its exit code."""
        self._reaper.join()
        if self._code is None:
            raise RuntimeError(f"the {EARLY_STAGE} run was not reaped")
        return self._code

    def report(self) -> str:
        """What the reaped run printed, then what it cost."""
        self._output.seek(0)
        printed = self._output.read()
        if printed and not printed.endswith("\n"):
            printed += "\n"
        return f"{printed}{self._cost}\n"

    def kill(self) -> None:
        """Kill the process tree if still running, wait for the reaper, and close output."""
        try:
            with self._lock:
                if self._code is None:
                    if sys.platform == "win32":
                        self._proc.kill()
                    else:
                        _kill_tree(self._proc.pid)
            self._reaper.join()
        finally:
            self._output.close()


def _early_decision(e: env.Environment) -> tuple[bool, str]:
    """Decide whether available memory covers running `EARLY_TEST` beside the build."""
    wanted = e.build_budget_mb + EARLY_TEST_MB
    if e.mem_available_mb <= 0:
        return False, f"{EARLY_TEST} after the build, no memory reading"
    if e.mem_available_mb < wanted:
        return False, f"{EARLY_TEST} after the build, {wanted} MB wanted beside it"
    return True, f"{EARLY_TEST} may start beside the build within {wanted} MB"


def _ctest_stage(e: env.Environment, build_dir: Path, handle: IO[str],
                 early: _EarlyRun | None) -> int:
    """Run the bundled `ctest` suite, merging `early` output when `EARLY_TEST` ran beside the build."""
    argv = ["ctest", "--test-dir", str(build_dir), "-j", str(e.test_jobs),
            "--output-on-failure"]
    if early is None:
        return env.stage("ctest", argv, stdout=handle, stderr=handle)
    code = env.stage("ctest", [*argv, "-E", f"^{EARLY_TEST}$"], stdout=handle, stderr=handle)
    early_code = early.wait()
    handle.write(early.report())
    handle.flush()
    return code or early_code


def _native_start(e: env.Environment, directory: Path,
                  stream: IO[str]) -> native_build.Manifest:
    """Refuse stale native reuse before any compile or test can consume it."""
    if native_build.prepare(directory, e.model):
        code = env.stage("native-clean", ["cmake", "--build", str(directory),
                                          "--target", "clean"], stdout=stream, stderr=stream)
        if code:
            raise ValueError(f"native input invalidation could not clean the build: exit {code}")
    return native_build.configured(directory, e.model)


def _native_finish(e: env.Environment, directory: Path,
                   before: native_build.Manifest | None) -> native_build.Manifest:
    """Bind the used native closure and reject inputs changed during the build."""
    if before is None:
        raise ValueError("no native input identity was captured before the build")
    native_build.validate(before)
    result = native_build.capture(directory, e.model)
    native_build.validate(before)
    return result


def _build_locked(e: env.Environment, build_dir: Path, log: Path,
                  extra: list[str]) -> int:
    """Run configure, build, and `ctest` stages under the lane lock and write the build receipt."""
    record_path = log.with_suffix(".json")
    record_path.unlink(missing_ok=True)
    identity = build_identity(e)
    observed_revision = _observed_revision(e)
    stages: dict[str, int] = {}
    native_before: native_build.Manifest | None = None
    native_inputs: native_build.Manifest | None = None
    refusal = ""
    run_id = uuid.uuid4().hex
    beside, decision = _early_decision(e)

    e.log_dir.mkdir(parents=True, exist_ok=True)
    version = subprocess.run(["sail", "--version"], capture_output=True, text=True, check=False)

    print(f"== log: {log}", flush=True)
    with log.open("w", encoding="utf-8") as handle:
        handle.write(f"== sail: {version.stdout.strip()}\n")
        handle.write(f"== lane: {e.lane or 'primary'} in {build_dir}\n")
        handle.write(f"== host: {e.cpus} cpu, {e.mem_available_mb} MB available; "
                     f"build -j{e.jobs}, ctest -j{e.test_jobs}; {decision}\n")
        handle.flush()

        code = stages["configure"] = _configure(e, build_dir, extra, handle)
        if not code:
            try:
                native_before = _native_start(e, build_dir, handle)
            except (OSError, ValueError, RuntimeError) as err:
                refusal = f"native build inputs refused: {err}"
                handle.write(refusal + "\n")
                code = stages["configure"] = 1
        handle.write(f"CONFIGURE_EXIT={code}\n")
        handle.flush()
        early: _EarlyRun | None = None
        try:
            if not code:
                if beside:
                    with contextlib.suppress(OSError):
                        early = _EarlyRun(["ctest", "--test-dir", str(build_dir),
                                           "-R", f"^{EARLY_TEST}$", "--output-on-failure"],
                                          time.perf_counter())
                code = stages["build"] = env.stage(
                    "build", ["cmake", "--build", str(build_dir), "-j", str(e.jobs)],
                    stdout=handle, stderr=handle, add_env={"NINJA_STATUS": NINJA_STATUS})
                handle.write(f"BUILD_EXIT={code}\n")
                handle.flush()
                if code and early is not None:
                    early.wait()
                elif not code:
                    code = stages["ctest"] = _ctest_stage(e, build_dir, handle, early)
                    handle.write(f"CTEST_EXIT={code}\n")
                    handle.flush()
            handle.write("ALL_DONE\n")
        finally:
            if early is not None:
                early.kill()

    if code == 0 and build_identity(e) != identity:
        refusal = "the inputs changed during the build; its evidence is stale"
    artifacts: dict[str, str] = {}
    if code == 0 and not refusal:
        try:
            native_inputs = _native_finish(e, build_dir, native_before)
            receipts.write(build_dir / native_build.STAMP, native_inputs)
            artifacts = build_artifacts(build_dir, e.model)
        except (OSError, ValueError, RuntimeError) as err:
            refusal = f"the build's evidence cannot be recorded: {err}"
    if refusal:
        print(refusal, file=sys.stderr)
        code = 1
    receipts.write(record_path, {
        "schema": 1, "run_id": run_id, "exit_code": code, "stages": stages,
        "identity": identity, "artifacts": artifacts,
        "observed_revision": observed_revision,
        "native_inputs": native_inputs,
        "log_sha256": receipts.digest(log), "extra_options": extra,
        **({"refusal": refusal} if refusal else {}),
    })

    print(f"== {'green' if code == 0 else 'failed'}: {log}")
    return code


def _detach(args: argparse.Namespace, log: Path, lock: IO[str] | None) -> int:
    """Spawn a detached build subprocess that inherits `lock` via `pass_fds` and `BUILD_LOCK_HELD`."""
    argv = cli.entry("model", "build", *(["--fast"] if args.fast else []),
                     *(["--offline"] if getattr(args, "offline", False) else []))
    log.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="previous-build-", dir=log.parent) as td:
        previous = Path(td) / log.name
        if log.exists():
            log.replace(previous)
        try:
            child = subprocess.Popen(
                argv, start_new_session=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                pass_fds=() if lock is None else (lock.fileno(),),
                env={**os.environ, env.BUILD_LOCK_HELD: "1"})
        except OSError as err:
            if previous.exists():
                previous.replace(log)
            print(f"the background build could not start: {err}", file=sys.stderr)
            return 1
    if lock is not None:
        env.record_lock_holder(lock, child.pid)
    print(f"== background: pid {child.pid}")
    print(f"== log: {log}")
    print(f"== wait: run.py model wait{' --fast' if args.fast else ''}")
    return 0


def _seed_tree(e: env.Environment, target: Path) -> None:
    """Seed `target` with warm SMT memo caches and verified test suites from donor trees."""
    donors = [d for d in (e.build_dir, e.primary_build_dir) if d != target and d.is_dir()]
    _seed_smt_cache(donors, target)
    _seed_test_data(donors, target, e.model)


def _seed_smt_cache(donors: list[Path], target: Path) -> None:
    """Seed `target`'s build and property SMT memo caches by copying from `donors`.

    Sail's `sail_smt_cache` is rewritten whole without locking on exit, so caches are
    copied into each lane and between the build and `PROPERTY_MEMO` rather than shared.
    """
    build_memo = target / "model" / "sail_smt_cache"
    _seed_cache_file([d / "model" / "sail_smt_cache" for d in donors], build_memo)
    _seed_cache_file([*(d / "model" / PROPERTY_MEMO for d in donors), build_memo],
                     target / "model" / PROPERTY_MEMO)


def _seed_cache_file(donors: list[Path], target: Path) -> None:
    """Copy the first existing donor memo cache to `target` if `target` does not yet exist."""
    if target.exists():
        return
    for source in donors:
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            return


def _seed_test_data(donors: list[Path], target: Path, model_root: Path) -> None:
    """Copy manifest-verified downloaded test suites for the declared release into `target`."""
    try:
        version = model_corpus.test_corpus_version(model_root)
        digests = model_corpus.test_corpus_digests(model_root, version)
    except ValueError as err:
        print(f"== no test corpus seeded: {err}", file=sys.stderr)
        return
    for name, digest in sorted(digests.items()):
        into = target / "test" / version / name
        if into.exists() or into.is_symlink():
            continue
        for donor in donors:
            suite = donor / "test" / version / name
            if not suite.exists():
                continue
            try:
                model_corpus.copy_verified_suite(suite, into, digest)
            except (OSError, ValueError) as err:
                print(f"== {name} not seeded from {donor}: {err}", file=sys.stderr)
                continue
            break


def cmd_wait(e: env.Environment, args: argparse.Namespace) -> int:
    """Wait on the lane's build lock, report the build log, and verify the build receipt."""
    log = e.log("model-build-fast" if args.fast else "model-build")
    lock = env.wait_for_build(e.fast_build_dir if args.fast else e.build_dir)
    try:
        code = _report_build(log)
        if code:
            return code
        try:
            verified_build(e, fast=args.fast)
        except (OSError, ValueError, TypeError, RuntimeError) as err:
            print(f"the build evidence is not current: {err}", file=sys.stderr)
            return 1
        return 0
    finally:
        if lock is not None:
            lock.close()


def _report_build(log: Path) -> int:
    """Print summary lines from `log` and return the final stage exit code (or `1` if incomplete)."""
    if not log.is_file():
        print(f"no build log at {log}: nothing has built in this lane", file=sys.stderr)
        return 1
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    exits = [int(found.group(1)) for line in lines if (found := STAGE_EXIT.match(line))]
    for line in lines:
        if line.startswith(("== ", "STAGE ")) or STAGE_EXIT.match(line):
            print(line)
    if not lines or lines[-1] != "ALL_DONE":
        print(f"{log} carries no ALL_DONE: the build it records did not finish",
              file=sys.stderr)
        return 1
    return exits[-1] if exits else 1


def _placed(path: Path) -> str:
    """Format `path` with its underlying filesystem type and OS-boundary side."""
    kind = env.filesystem(path)
    if not kind:
        return str(path)
    side = ("read across the OS boundary" if kind in env.CROSS_OS_FILESYSTEMS
            else "the guest's own filesystem")
    return f"{path} ({kind}, {side})"


def cmd_lane(e: env.Environment, args: argparse.Namespace) -> int:
    """Print this checkout's build lane paths, filesystems, and active lock holder."""
    holder = env.build_holder(e.build_dir)
    print(f"lane             {e.lane or 'primary (this checkout is not a linked worktree)'}")
    print(f"checkout         {_placed(e.root)}")
    print(f"build tree       {_placed(e.build_dir)}")
    print(f"fast tree        {e.fast_build_dir}")
    print(f"typecheck cache  {e.typecheck_cache}")
    print(f"oracle tree      {e.oracle_root} (shared by every lane)")
    print(f"build log        {_placed(e.log('model-build'))}")
    print(f"building now     {f'yes, pid {holder}' if bool(holder) else 'no'}")
    return 0


# =====================================================================================
# smt: capability-helper property suite, one solver verdict per property
# =====================================================================================

SMT_MODULE = "cap_properties"
SMT_VARIABLE = "smt_properties=true"
SMT_SOURCE = Path("model") / "unit_tests" / "cap_properties.sail"
SMT_PREFIX = "model"

PROPERTY_MARK = re.compile(r"^\$\[property\]\s*$")
FUNCTION_HEAD = re.compile(r"^(?:private\s+)?function\s+([A-Za-z_][A-Za-z0-9_']*)\s*\(")

PROVED, COUNTEREXAMPLE, UNDECIDED = "proved", "counterexample", "undecided"
SMT_SOLVERS = ("z3", "bitwuzla", "cvc5")
SMT_AUTO_SOLVERS = ("z3", "cvc5")
SOLVER_VERDICTS: dict[str, str] = {
    "unsat": PROVED, "sat": COUNTEREXAMPLE, "unknown": UNDECIDED, "timeout": UNDECIDED,
}

# Sail `--smt-auto` output markers (`Smt_exp.Counterexample.check`).
AUTO_CHECKING = re.compile(r"^Checking counterexample: (.+)$")
AUTO_FOUND = "Solver found counterexample:"
AUTO_NOT_FOUND = "Solver could not find counterexample"
AUTO_UNEXPECTED = "Unexpected solver output:"
UNRECOGNIZED = "unrecognized"

MODEL_HEAD_LINES = 12


def property_names(text: str) -> list[str]:
    """Return every `$[property]` function name in `text` in source order.

    Raises `ValueError` if a `$[property]` attribute is not followed by a function head.
    """
    names: list[str] = []
    pending: int | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        if pending is not None:
            if not line.strip() or line.lstrip().startswith("//"):
                continue
            head = FUNCTION_HEAD.match(line)
            if head is None:
                raise ValueError(f"line {pending}: $[property] is followed by no function head")
            names.append(head.group(1))
            pending = None
        elif PROPERTY_MARK.match(line):
            pending = number
    if pending is not None:
        raise ValueError(f"line {pending}: $[property] is followed by no function head")
    return names


def solver_verdict(output: str) -> tuple[str | None, list[str]]:
    """Parse solver output into `(verdict, model_lines)`, returning `(None, [])` if unrecognized."""
    lines = [line for line in output.splitlines() if line.strip()]
    if not lines:
        return None, []
    verdict = SOLVER_VERDICTS.get(lines[0].strip())
    if ((verdict in (PROVED, UNDECIDED) and len(lines) != 1)
            or any(line.lstrip().startswith("(error") for line in lines[1:])):
        return None, []
    return verdict, lines[1:]


def auto_verdicts(text: str) -> dict[str, str]:
    """Parse Sail `--smt-auto` output into `{property_name: verdict}`."""
    verdicts: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        opened = AUTO_CHECKING.match(line)
        if opened is not None:
            stem = Path(opened.group(1).strip()).stem
            current = stem.removeprefix(f"{SMT_PREFIX}_")
            verdicts[current] = UNRECOGNIZED
        elif current is not None and verdicts[current] == UNRECOGNIZED:
            if line.startswith(AUTO_FOUND):
                verdicts[current] = COUNTEREXAMPLE
            elif line.startswith(AUTO_NOT_FOUND):
                verdicts[current] = PROVED
            elif line.startswith(AUTO_UNEXPECTED):
                current = None
    return verdicts


def _solver_version(binary: str) -> str:
    done = subprocess.run([binary, "--version"], capture_output=True, text=True, check=False)
    return done.stdout.strip() or done.stderr.strip() or f"{binary}: no version"


def _solver_argv(solver: str, timeout: int, smt2: Path) -> list[str]:
    """Build the command-line argv for `solver` on `smt2` under `timeout` seconds."""
    limit_ms = max(1, timeout) * 1000
    if solver == "z3":
        return ["z3", f"-T:{timeout}", "-model", str(smt2)]
    if solver == "bitwuzla":
        return ["bitwuzla", f"--time-limit={limit_ms}", "--produce-models",
                "--print-model", str(smt2)]
    if solver == "cvc5":
        return ["cvc5", "--lang=smt2.6", f"--tlimit-per={limit_ms}",
                "--produce-models", "--dump-models", str(smt2)]
    raise ValueError(f"unsupported SMT solver: {solver}")


def cmd_smt(e: env.Environment, args: argparse.Namespace) -> int:
    """Emit and solve `$[property]` obligations in `unit_tests/cap_properties.sail`.

    Reports per-property verdicts (`proved`, `counterexample`, `undecided`) and
    timings under `--timeout`, or delegates to Sail's `--smt-auto` when `--auto` is set.
    """
    solver = str(getattr(args, "solver", "z3"))
    if args.auto and solver not in SMT_AUTO_SOLVERS:
        print(f"--auto supports {', '.join(SMT_AUTO_SOLVERS)}, not {solver}", file=sys.stderr)
        return 1
    _require("sail", SAIL_HOW)
    _require(solver, f"{solver} is the selected SMT solver for run.py model smt")

    source = e.model / SMT_SOURCE
    if not source.is_file():
        print(f"no property suite at {source}", file=sys.stderr)
        return 1
    try:
        names = property_names(source.read_text(encoding="utf-8"))
    except ValueError as defect:
        print(f"{source}: {defect}", file=sys.stderr)
        return 1
    if not names:
        print(f"{source} carries no $[property] head", file=sys.stderr)
        return 1
    unknown = sorted(set(args.property) - set(names))
    if unknown:
        print(f"no such property in {SMT_SOURCE}: {', '.join(unknown)}", file=sys.stderr)
        return 1
    picked = [n for n in names if not args.property or n in args.property]
    print(f"== {len(names)} $[property] heads in {SMT_SOURCE}, {len(picked)} selected")

    out = e.lane_root / "smt"
    cache = out / "sail_smt_cache"
    lock = env.hold_lock(cache, "an smt run")
    try:
        _seed_cache_file([e.typecheck_cache, e.primary_typecheck_cache], cache)
        e.log_dir.mkdir(parents=True, exist_ok=True)
        log = e.log("model-smt")
        print(f"== log: {log}")
        if args.reuse and not args.auto:
            print(f"== reusing the emission standing in {out}")
            code = 0
        else:
            for stale in out.glob(f"{SMT_PREFIX}_*.smt2"):
                stale.unlink()
            with log.open("w", encoding="utf-8") as handle:
                code = env.stage("emit", [
                    "sail", "--strict-var", "--strict-bitvector", "--strict-exponentials",
                    "--memo-z3", "--memo-z3-path", str(cache),
                    "--smt",
                    *(["--smt-auto", "--smt-auto-solver", solver] if args.auto else []),
                    "-o", str(out / SMT_PREFIX),
                    "--config", str(e.profile),
                    "--variable", SMT_VARIABLE,
                    "riscv.sail_project", SMT_MODULE,
                ], cwd=e.model / "model", stdout=handle, stderr=handle)
        if args.auto:
            return _report_auto(log, picked, code)
        if code:
            print(f"the emission failed with exit {code}; the log is {log}", file=sys.stderr)
            return code
        return _solve_each(out, picked, args.timeout, e, solver=solver)
    finally:
        lock.close()


def _report_auto(log: Path, picked: list[str], code: int) -> int:
    """Read Sail `--smt-auto` verdicts from `log` and report one line per property."""
    verdicts = auto_verdicts(log.read_text(encoding="utf-8", errors="replace"))
    failed = 0
    for name in picked:
        verdict = verdicts.get(name, "missing")
        failed += verdict != PROVED
        print(f"{verdict:<15} {name}")
    print(f"== {len(picked)} properties under --auto: {len(picked) - failed} proved, "
          f"{failed} not; sail exit {code}; counterexamples are rendered in {log}")
    return 1 if failed or code else 0


def _solve_each(
    out: Path,
    picked: list[str],
    timeout: int,
    e: env.Environment,
    *,
    solver: str = "z3",
) -> int:
    """Run `solver` on each emitted `.smt2` file under `timeout` seconds."""
    counts = dict.fromkeys((PROVED, COUNTEREXAMPLE, UNDECIDED, UNRECOGNIZED), 0)
    for name in picked:
        smt2 = out / f"{SMT_PREFIX}_{name}.smt2"
        if not smt2.is_file():
            print(f"{'missing':<15} {name}  (the emission wrote no {smt2.name})")
            counts[UNRECOGNIZED] += 1
            continue
        started = time.perf_counter()
        said = ""
        try:
            done = subprocess.run(_solver_argv(solver, timeout, smt2),
                                  capture_output=True, text=True, check=False,
                                  timeout=timeout + 60)
            said = f"{done.stdout}\n{done.stderr}".strip()
            if done.returncode != 0 or done.stderr.strip():
                verdict, model = None, []
                said = f"{solver} exited {done.returncode}: {said}"
            else:
                verdict, model = solver_verdict(done.stdout)
        except subprocess.TimeoutExpired:
            verdict, model = UNDECIDED, []
        except OSError as err:
            verdict, model = None, []
            said = f"{solver} could not run: {err}"
        wall = time.perf_counter() - started
        label = verdict or UNRECOGNIZED
        counts[label] += 1
        print(f"{label:<15} {name:<34} {wall:8.1f} s  ({smt2.stat().st_size} bytes)")
        if verdict == COUNTEREXAMPLE:
            witness = smt2.with_suffix(".model")
            witness.write_text("\n".join(model) + "\n", encoding="utf-8")
            for line in model[:MODEL_HEAD_LINES]:
                print(f"    {line}")
            if len(model) > MODEL_HEAD_LINES:
                print(f"    ... {len(model)} lines in {witness}; `--auto` renders it "
                      f"in Sail values")
        elif verdict is None:
            for line in said.splitlines()[:3]:
                print(f"    {line}")
    print(f"== {len(picked)} properties: {counts[PROVED]} proved, "
          f"{counts[COUNTEREXAMPLE]} counterexample, {counts[UNDECIDED]} undecided at "
          f"--timeout {timeout} s, {counts[UNRECOGNIZED]} unrecognized or missing; "
          f"{_solver_version('sail')}; {_solver_version(solver)}; "
          f"lane {e.lane or 'primary'} in {out}")
    return 0 if picked and counts[PROVED] == len(picked) else 1


def cmd_oracle(e: env.Environment, args: argparse.Namespace) -> int:
    """Build the pinned M0.4 `sail-cheri-riscv` oracle on native guest storage and run its RV64 suite."""
    _require("sail", SAIL_HOW)
    sail = shutil.which("sail") or "sail"
    src = e.root / ORACLE_SRC
    if not (src / "Makefile").is_file() or not (src / ORACLE_NESTED / "model").is_dir():
        print(f"no oracle source at {src}: the submodule or its nested {ORACLE_NESTED} "
              f"is not checked out; run `{ORACLE_INIT}`", file=sys.stderr)
        return 1
    try:
        pins = _oracle_pins(e.root, src)
    except ValueError as err:
        print(str(err), file=sys.stderr)
        return 1

    tree = e.oracle_root
    e.log_dir.mkdir(parents=True, exist_ok=True)
    log = e.log("oracle-build")
    version = subprocess.run([sail, "--version"], capture_output=True, text=True, check=False)

    # Lock the shared oracle tree exclusively so concurrent builds or `trace-diff` runs
    # cannot overlap with syncing or linking.
    with env.hold_lock(tree, "an oracle build"):
        oracle_receipt(tree).unlink(missing_ok=True)
        print(f"== log: {log}", flush=True)
        with log.open("w", encoding="utf-8") as handle:
            handle.write(f"== sail: {version.stdout.strip()} at {sail}\n")
            handle.write(f"== tree: {tree}\n")
            handle.write(f"== source: {ORACLE_SRC} at {pins[0]}, "
                         f"{ORACLE_NESTED} at {pins[1]}\n")
            refusal = _stand_oracle_tree(src, tree, pins, handle, resync=args.resync)
            if refusal:
                handle.write(f"SYNC refused: {refusal}\nALL_DONE\n")
                print(refusal, file=sys.stderr)
                print(f"== failed: {log}")
                return 1
            handle.flush()

            code = env.stage("oracle", ["make", "-j", str(e.jobs), f"SAIL={sail}",
                                        f"C_WARNINGS={ORACLE_CSTD}", ORACLE_TARGET],
                             cwd=tree, stdout=handle, stderr=handle)
            handle.write(f"BUILD_EXIT={code}\n")
            handle.flush()
            if code == 0:
                code = _vouch_for_oracle(e, tree, handle, args.timeout)
            handle.write("ALL_DONE\n")

    print(f"== {'green' if code == 0 else 'failed'}: {log}")
    return code


def _stand_oracle_tree(src: Path, tree: Path, pins: tuple[str, str], handle: IO[str], *,
                       resync: bool) -> str:
    """Sync and verify `tree` against `pins`, returning `""` on success or a refusal string."""
    stamp = tree / ORACLE_STAMP
    claim = [*pins, ORACLE_STAMP_CLAIM]
    if not resync and (tree / "Makefile").is_file():
        recorded = stamp.read_text(encoding="utf-8").split() if stamp.is_file() else []
        if recorded != claim:
            if recorded[:2] == list(pins):
                return (f"{tree} is stamped with these pins by a sync that did not "
                        "restore their bytes; rerun with --resync")
            return (f"{tree} is stamped {' '.join(recorded) or 'with nothing'}, not "
                    f"{' '.join(claim)}: not these pins; rerun with --resync")
        handle.write("SYNC skipped: the tree is already present at these pins\n")
        return ""
    handle.write(f"SYNC from {src}\n")
    handle.flush()
    _sync_oracle_tree(src, tree)
    try:
        _verify_oracle_copy(src, tree, pins)
    except ValueError as err:
        shutil.rmtree(tree, ignore_errors=True)
        return str(err)
    stamp.write_text("".join(f"{line}\n" for line in claim), encoding="utf-8", newline="")
    handle.write("SYNC verified: the copy is the pinned commits' files\n")
    return ""


def _plain_git(argv: list[str], cwd: Path, overlay: dict[str, str] | None = None,
               stdin: bytes | None = None) -> bytes:
    """Run `git` in `cwd` after scrubbing inherited `GIT_*` environment variables."""
    scrubbed = {name: value for name, value in os.environ.items()
                if name not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    done = subprocess.run(["git", *argv], cwd=cwd, input=stdin, capture_output=True,
                          check=False, timeout=900, env={**scrubbed, **(overlay or {})})
    if done.returncode:
        raise ValueError(f"`git {' '.join(argv)}` in {cwd} failed: "
                         f"{done.stderr.decode('utf-8', errors='replace').strip()}")
    return done.stdout


def _gitlink(listing: bytes, path: str, where: str) -> str:
    """Extract the commit SHA recorded for mode `160000` gitlink `path` in `listing`."""
    for line in listing.decode("utf-8", errors="replace").splitlines():
        meta, _, named = line.partition("\t")
        fields = meta.split()
        if named == path and fields and fields[0] == "160000":
            commit = next((f for f in fields[1:] if re.fullmatch(r"[0-9a-f]{40,64}", f)), "")
            if commit:
                return commit
    raise ValueError(f"{where} records no gitlink for {path}; run `{ORACLE_INIT}`")


def _indexed_oracle_pin(root: Path) -> str:
    """Return the commit SHA pinned for `ORACLE_SRC` in `root`'s Git index."""
    return _gitlink(_plain_git(["ls-files", "--stage", "--", ORACLE_SRC], root,
                               env.git_env(root) or None), ORACLE_SRC, "this checkout's index")


def _oracle_pins(root: Path, src: Path) -> tuple[str, str]:
    """Return `(outer_pin, inner_pin)` for `ORACLE_SRC` and its nested `sail-riscv` submodule."""
    outer = _indexed_oracle_pin(root)
    head = _plain_git(["rev-parse", "HEAD"], src).decode().strip()
    if head != outer:
        raise ValueError(f"{ORACLE_SRC} is checked out at {head}, not at its pin {outer}; "
                         f"run `{ORACLE_INIT}`")
    inner = _gitlink(_plain_git(["ls-tree", outer, "--", ORACLE_NESTED], src),
                     ORACLE_NESTED, f"{ORACLE_SRC} at {outer}")
    nested = src / ORACLE_NESTED
    answer = _plain_git(["rev-parse", "--show-toplevel", "HEAD"], nested).decode().splitlines()
    try:
        own = len(answer) == 2 and Path(answer[0]).samefile(nested)
    except OSError:
        own = False
    if not own or answer[1] != inner:
        raise ValueError(f"{ORACLE_SRC}/{ORACLE_NESTED} is not checked out at its pin "
                         f"{inner}; run `{ORACLE_INIT}`")
    return outer, inner


def _read_blobs(repo: Path, oids: list[str]) -> dict[str, bytes]:
    """Read `oids` from `repo` in a single `git cat-file --batch` call."""
    out = _plain_git(["cat-file", "--batch"], repo, stdin="".join(f"{o}\n" for o in oids).encode())
    blobs: dict[str, bytes] = {}
    at = 0
    for oid in oids:
        end = out.index(b"\n", at)
        header = out[at:end].decode("utf-8", errors="replace").split()
        if len(header) != 3 or header[0] != oid or header[1] != "blob":
            raise ValueError(f"{repo} cannot supply {oid}: {' '.join(header)}")
        size = int(header[2])
        blobs[oid] = out[end + 1:end + 1 + size]
        at = end + 1 + size + 1
    return blobs


def _verify_oracle_copy(src: Path, tree: Path, pins: tuple[str, str]) -> None:
    """Verify that `tree` matches the pinned commits' blobs (normalizing CRLF to LF)."""
    expected: dict[str, tuple[str, str]] = {}
    owners: dict[str, Path] = {}
    for repo, prefix, commit in ((src, "", pins[0]),
                                 (src / ORACLE_NESTED, f"{ORACLE_NESTED}/", pins[1])):
        listing = _plain_git(["ls-tree", "-r", "-z", "--full-tree", commit], repo)
        for entry in listing.decode("utf-8", errors="surrogateescape").split("\0"):
            if not entry:
                continue
            meta, _, path = entry.partition("\t")
            mode, kind, oid = meta.split()
            if kind == "blob":
                expected[prefix + path] = (mode, oid)
                owners[oid] = repo
            elif kind != "commit":
                raise ValueError(f"{prefix + path} is a {kind}, which the copy cannot hold")
    present = {path.relative_to(tree).as_posix() for path in tree.rglob("*")
               if path.is_symlink() or path.is_file()}
    faults = [f"{rel} is in the copy and not in the pinned commits"
              for rel in sorted(present - expected.keys())]
    faults += [f"{rel} is missing" for rel in sorted(expected.keys() - present)]
    blobs: dict[str, bytes] = {}
    for repo in (src, src / ORACLE_NESTED):
        blobs.update(_read_blobs(repo, sorted({oid for oid, owner in owners.items()
                                                if owner == repo})))
    restore: list[tuple[Path, bytes]] = []
    for rel, (mode, oid) in sorted(expected.items()):
        path = tree / rel
        if rel not in present:
            continue
        if mode == "120000":
            same = path.is_symlink() and os.fsencode(path.readlink()) == blobs[oid]
        else:
            held = b"" if path.is_symlink() else path.read_bytes()
            same = (not path.is_symlink() and held.replace(b"\r\n", b"\n")
                    == blobs[oid].replace(b"\r\n", b"\n"))
            if same and held != blobs[oid]:
                restore.append((path, blobs[oid]))
        if not same:
            faults.append(f"{rel} differs from its pinned content")
    if faults:
        raise ValueError(f"the copy of {ORACLE_SRC} is not its pinned commits, "
                         f"{len(faults)} difference(s): {'; '.join(faults[:5])}; "
                         f"remove the local changes or run `{ORACLE_INIT}`")
    for path, blob in restore:
        path.write_bytes(blob)


def _sync_oracle_tree(src: Path, tree: Path) -> None:
    """Copy `src` (including nested `sail-riscv`, excluding `.git`) into `tree`."""
    if tree.exists():
        shutil.rmtree(tree)
    shutil.copytree(src, tree, ignore=shutil.ignore_patterns(".git"), symlinks=True)


def _vouch_for_oracle(e: env.Environment, tree: Path, handle: IO[str], timeout: int) -> int:
    """Run the bundled RV64 suite on the built oracle simulator and write `oracle_receipt`."""
    simulator = tree / ORACLE_TARGET
    try:
        simulator_sha256 = receipts.digest(simulator)
        stamp = (tree / ORACLE_STAMP).read_text(encoding="utf-8").split()
    except OSError as err:
        handle.write(f"cannot read the built simulator and its stamp: {err}\n")
        return 1
    passed, failed = _oracle_suite(e, simulator, tree, handle, timeout)
    if failed or not passed:
        return 1
    receipt = oracle_receipt(tree)
    receipts.write(receipt, {"schema": 1, "stamp": stamp, "simulator": ORACLE_TARGET,
                             "simulator_sha256": simulator_sha256,
                             "suite": {"pass": passed, "fail": failed}})
    handle.write(f"RECEIPT {receipt}\n")
    return 0


def _oracle_suite(e: env.Environment, simulator: Path, tree: Path, handle: IO[str],
                  timeout: int) -> tuple[int, int]:
    """Run the RV64 ELFs bundled under `sail-riscv/test/riscv-tests` and return `(passed, failed)`."""
    elves = sorted((tree / "sail-riscv" / "test" / "riscv-tests").glob("rv64*.elf"))
    if not elves:
        handle.write("no bundled rv64 ELFs found under sail-riscv/test/riscv-tests\n")
        return 0, 0

    def passed(elf: Path) -> bool:
        try:
            done = subprocess.run([str(simulator), "-p", str(elf)], capture_output=True,
                                  text=True, errors="replace", timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            return False
        return done.returncode == 0 and "SUCCESS" in (done.stdout + done.stderr)

    failed = 0
    with ThreadPoolExecutor(max_workers=e.test_jobs) as pool:
        for elf, ok in zip(elves, pool.map(passed, elves), strict=True):
            if not ok:
                failed += 1
                handle.write(f"FAILED: {elf.name}\n")
    handle.write(f"TESTS pass={len(elves) - failed} fail={failed}\n")
    return len(elves) - failed, failed


def cmd_sweep(e: env.Environment, args: argparse.Namespace) -> int:
    """Run downloaded `riscv-tests` physical-variant ELFs against the frozen profile and classify each (`PASS`, `REFUSE`, `HANG`)."""
    if (missing := _missing_simulator(e)) is not None:
        print(missing, file=sys.stderr)
        return 1
    sim = e.simulator
    try:
        elves = model_corpus.sweep_inputs(e.build_dir, e.model, args.xlen)
    except ValueError as err:
        print(str(err), file=sys.stderr)
        return 1

    profile = e.profile

    def classify(elf: Path) -> tuple[str, str]:
        try:
            done = subprocess.run([str(sim), "--config", str(profile), str(elf)],
                                  capture_output=True, timeout=args.timeout, check=False)
        except subprocess.TimeoutExpired:
            return "HANG", ""
        return ("PASS", "") if done.returncode == 0 else ("REFUSE", f" rc={done.returncode}")

    tally = {"PASS": 0, "REFUSE": 0, "HANG": 0}
    with ThreadPoolExecutor(max_workers=e.test_jobs) as pool:
        for elf, (verdict, detail) in zip(elves, pool.map(classify, elves), strict=True):
            tally[verdict] += 1
            print(f"{verdict} {elf.name}{detail}")

    print(f"TOTAL pass={tally['PASS']} refuse={tally['REFUSE']} hang={tally['HANG']} "
          f"of {sum(tally.values())}")
    return 0


def cmd_trace_diff(e: env.Environment, args: argparse.Namespace) -> int:
    """Run the curated model and the M0.4 oracle over `elves` (or `--corpus`) and adjudicate their traces.

    Holds a shared lock on `e.oracle_root` and verifies that the oracle simulator
    matches its passing receipt before running.
    """
    if (missing := _missing_simulator(e)) is not None:
        print(missing, file=sys.stderr)
        return 1
    if (missing := _missing_oracle(e)) is not None:
        print(missing, file=sys.stderr)
        return 1

    elves = [Path(p) for p in args.elf]
    if args.corpus:
        try:
            verified = model_corpus.pinned_suite(e.build_dir, e.model)
        except ValueError as err:
            print(str(err), file=sys.stderr)
            return 1
        elves = list(model_corpus.verified_inputs(verified, "rv64ui-p-*"))
    if not elves:
        print("nothing to compare: pass one or more ELFs, or --corpus", file=sys.stderr)
        return 1

    with env.hold_lock(e.oracle_root, "a trace-diff", shared=True):
        if (missing := _missing_oracle(e) or _unvouched_oracle(e)) is not None:
            print(missing, file=sys.stderr)
            return 1
        return _adjudicate(e, args, elves)


def _missing_oracle(e: env.Environment) -> str | None:
    """Return an error string if the M0.4 oracle simulator does not exist."""
    if e.oracle.exists():
        return None
    return f"no M0.4 oracle at {e.oracle}; run `run.py model oracle` first"


def _unvouched_oracle(e: env.Environment) -> str | None:
    """Verify that `e.oracle_root`'s source stamp, suite receipt, and simulator SHA-256 all match."""
    tree = e.oracle_root
    resync = "run `run.py model oracle --resync`"
    try:
        recorded = (tree / ORACLE_STAMP).read_text(encoding="utf-8").split()
    except OSError:
        recorded = []
    if len(recorded) != 3 or recorded[-1] != ORACLE_STAMP_CLAIM:
        return (f"{tree} is stamped {' '.join(recorded) or 'with nothing'}, which does "
                f"not vouch for the pinned sources' bytes; {resync}")
    try:
        pin = _indexed_oracle_pin(e.root)
    except ValueError as err:
        return str(err)
    if recorded[0] != pin:
        return (f"{tree} is stamped for {ORACLE_SRC} at {recorded[0]}, not at this "
                f"checkout's pin {pin}; {resync}")
    receipt = oracle_receipt(tree)
    rerun = f"run `run.py model oracle`, whose suite writes {receipt.name} once it passes"
    try:
        raw: object = json.loads(receipt.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return f"no readable receipt of a passing oracle suite at {receipt}; {rerun}"
    record = cast("dict[str, object]", raw) if isinstance(raw, dict) else {}
    suite = record.get("suite")
    tally = cast("dict[str, object]", suite) if isinstance(suite, dict) else {}
    passed = tally.get("pass")
    if (record.get("stamp") != recorded or tally.get("fail") != 0
            or not isinstance(passed, int) or passed < 1):
        return f"{receipt} does not record a passing suite under {tree}'s stamp; {rerun}"
    try:
        held = receipts.digest(e.oracle)
    except OSError as err:
        return f"cannot read {e.oracle}: {err}"
    if record.get("simulator_sha256") != held:
        return f"{e.oracle} is not the simulator {receipt} records the suite passing on; {rerun}"
    return None


def _adjudicate(e: env.Environment, args: argparse.Namespace, elves: list[Path]) -> int:
    """Run both executors over `elves` and adjudicate their normalized traces."""
    profile = e.profile
    tally = {"AGREE": 0, "PREFIX": 0, "SHORT": 0, "SKIP": 0}
    shortest = None

    for elf in elves:
        curated_lines = _run_trace(
            [str(e.simulator), "--config", str(profile), "--trace-instr", "--trace-gpr",
             "--trace-mem", "--inst-limit", str(args.limit), str(elf)], args.timeout)
        if curated_lines is None:
            print(f"SHORT   {elf.name} (curated executor: no exit within {args.timeout}s)")
            tally["SHORT"] += 1
            continue
        curated = trace.normalize(curated_lines, "curated")
        if not curated:
            print(f"SKIP    {elf.name} (curated model retired nothing)")
            tally["SKIP"] += 1
            continue

        oracle_lines = _run_trace(
            [str(e.oracle), "-v", "-l", str(args.limit), str(elf)], args.timeout)
        if oracle_lines is None:
            print(f"SHORT   {elf.name} (oracle executor: no exit within {args.timeout}s)")
            tally["SHORT"] += 1
            continue
        oracle = trace.normalize(oracle_lines, "oracle")
        verdict = trace.adjudicate(curated, oracle, args.context)

        if verdict.ok:
            print(f"AGREE   {elf.name} ({verdict.line()})")
            tally["AGREE"] += 1
            continue
        if verdict.error is not None:
            print(f"SHORT   {elf.name} ({verdict.error})")
            tally["SHORT"] += 1
            continue

        divergence = verdict.divergence
        if divergence is None:
            raise AssertionError(f"{elf.name}: a verdict that is neither clean, "
                                 f"errored, nor divergent")

        if shortest is None or verdict.prefix < shortest:
            shortest = verdict.prefix
        if verdict.prefix < args.floor:
            print(f"SHORT   {elf.name} ({verdict.line()}, below the floor of {args.floor})")
            for record in verdict.agreed:
                print(f"          agreed : {record}")
            print(f"          curated: {divergence[0]}")
            print(f"          oracle : {divergence[1]}")
            print("          the Sail model is the reference: a divergence is a fault "
                  "in the transplant unless the oracle is shown to be the one at fault.")
            tally["SHORT"] += 1
        else:
            print(f"PREFIX  {elf.name} ({verdict.line()})")
            tally["PREFIX"] += 1

    print(f"TOTAL agree={tally['AGREE']} prefix={tally['PREFIX']} short={tally['SHORT']} "
          f"skip={tally['SKIP']} of {sum(tally.values())}; "
          f"shortest prefix {shortest if shortest is not None else 'n/a'}")
    return 1 if tally["SHORT"] else 0


def _run_trace(argv: list[str], timeout: int) -> list[str] | None:
    """Run `argv` and return merged stdout/stderr lines, or `None` on timeout."""
    try:
        done = subprocess.run(argv, capture_output=True, text=True, errors="replace",
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return None
    return (done.stdout + done.stderr).splitlines()


def _corpus_persistence(e: env.Environment, out: Path, timeout: int) -> int:
    """Run the architectural persistent-device reopen campaign (`[vos/block_persistence.py](../block_persistence.py)`)."""
    output = out / f"persistence-{uuid.uuid4().hex}"
    try:
        report = block_persistence.run(e.root, e.simulator, e.profile, output, timeout)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"PERSISTENCE FAIL ({exc})", file=sys.stderr)
        return 1
    passed = report.get("passed") is True
    print(f"PERSISTENCE {'PASS' if passed else 'FAIL'} (receipt {output / 'results.json'})")
    if not passed and report.get("error"):
        print(f"PERSISTENCE {report['error']}", file=sys.stderr)
    return 0 if passed else 1


def cmd_corpus(e: env.Environment, args: argparse.Namespace) -> int:
    """Assemble and run the differential corpus (`[docs/assurance/differential-corpus.md](../../../docs/assurance/differential-corpus.md)`)."""
    if getattr(args, "persistence_only", False):
        if args.member or args.assemble_only or args.refresh:
            print("--persistence-only cannot combine with members, --assemble-only or --refresh",
                  file=sys.stderr)
            return 1
        out = Path(args.out) if args.out else e.lane_root / "corpus"
        return _corpus_persistence(e, out, args.timeout)
    corpus = differential.load(e.root)
    if not corpus.members:
        print("the differential corpus contains no member to execute", file=sys.stderr)
        return 1
    out_dir = Path(args.out) if args.out else e.lane_root / "corpus"
    wanted = set(args.member)
    members = [m for m in corpus.members if not wanted or m.name in wanted]
    if wanted - {m.name for m in members}:
        print(f"no such member: {', '.join(sorted(wanted - {m.name for m in members}))}",
              file=sys.stderr)
        return 1

    profile = e.profile
    tally = {"PASS": 0, "FAIL": 0}
    measured: dict[str, tuple[int, int, str]] = {}
    for member in members:
        try:
            elf = differential.assemble(corpus, member, out_dir)
        except Exception as exc:
            print(f"FAIL    {member.name} ({exc})")
            tally["FAIL"] += 1
            continue
        if args.assemble_only:
            print(f"BUILT   {member.name} ({elf.stat().st_size} bytes)")
            continue
        verdict, detail, records = _run_member(e, profile, elf, args.timeout)
        if records is not None:
            checks = differential.count_checks(
                corpus.source(member).read_text(encoding="utf-8"))
            measured[member.name] = (checks, len(records), trace.digest(records))
            if not args.refresh and verdict == "PASS":
                verdict, detail = _check_trace(member, measured[member.name])
        print(f"{verdict:<7} {member.name}{detail}")
        tally[verdict] = tally.get(verdict, 0) + 1

    if args.assemble_only:
        print(f"TOTAL built={len(members)}")
        return 0
    if args.refresh and measured:
        differential.rewrite(corpus, measured)
        print(f"REFRESH {len(measured)} manifest rows rewritten")
    print(f"TOTAL pass={tally['PASS']} fail={tally['FAIL']} of {len(members)} "
          f"(corpus v{corpus.version}, trace schema v{corpus.trace_schema})")
    persistence = _corpus_persistence(e, out_dir, args.timeout) if not wanted else 0
    return 1 if tally["FAIL"] or persistence else 0


def cmd_freeze_emit(e: env.Environment, args: argparse.Namespace) -> int:
    """Emit the link map and per-site table for the differential corpus (`[vos/compose.py](../compose.py)`)."""
    try:
        geometry = compose.Geometry(header=args.header, slots=args.slots, width=args.width)
    except ValueError as exc:
        print(f"FAIL freeze-emit: {exc}", file=sys.stderr)
        return 1
    corpus = differential.load(e.root)
    wanted = set(args.member)
    members = [m for m in corpus.members if not wanted or m.name in wanted]
    if wanted - {m.name for m in members}:
        print(f"no such member: {', '.join(sorted(wanted - {m.name for m in members}))}",
              file=sys.stderr)
        return 1

    into = Path(args.out) if args.out else e.root / freezeschema.BUILD_DIR
    sites: list[asm.Site] = []
    blob = bytearray()
    with tempfile.TemporaryDirectory() as scratch:
        for member in members:
            elf = Path(scratch) / f"{member.name}.elf"
            here: list[asm.Site] = []
            try:
                asm.assemble_file(corpus.source(member), elf, here)
            except Exception as exc:
                print(f"FAIL    {member.name} ({exc})", file=sys.stderr)
                return 1
            sites += here
            blob += elf.read_bytes()
            print(f"EMIT    {member.name} ({len(here)} site(s))")

    composed = compose.compose(sites, bytes(blob), geometry)
    written = compose.emit(composed, into)
    for path, size in written:
        print(f"WROTE   {path} ({size} bytes)")
    print(f"TOTAL   {len(sites)} site(s) over {len(members)} member(s) in "
          f"{composed.placed[-1].bundle + 1 if composed.placed else 0} bundle(s) at "
          f"h={geometry.header} k={geometry.slots} w={geometry.width} "
          f"({geometry.bits} bits), a declared parameter and not a freeze verdict; "
          f"the dictionary is empty, so every site is a {geometry.escape_slots}-slot "
          f"verbatim escape and the hit rate is "
          f"{composed.hit_rate:.0%}")
    print("        the sidecar stream is M1.2's backend's and is not written here: its "
          "operand and producer labels are the emitter's intent (§4)")
    return 0


def _check_trace(member: differential.Member, measured: tuple[int, int, str]) -> tuple[str, str]:
    """Compare a member's measured check count, record count, and trace digest against the manifest."""
    checks, records, digest = measured
    if not member.digest:
        return "FAIL", f" (no trace digest in the manifest; {records} records, {digest})"
    if member.digest != digest:
        return "FAIL", (f" (trace digest {digest} over {records} records against the "
                        f"manifest's {member.digest} over {member.records})")
    if member.checks != checks:
        return "FAIL", f" ({checks} checks against the manifest's {member.checks})"
    return "PASS", f" ({checks} checks, {records} records)"


def _run_member(e: env.Environment, profile: Path, elf: Path,
                timeout: int) -> tuple[str, str, list[str] | None]:
    if (missing := _missing_simulator(e)) is not None:
        return "FAIL", f" ({missing})", None
    terminal = elf.with_suffix(".terminal.log")
    terminal.unlink(missing_ok=True)
    try:
        done = subprocess.run([str(e.simulator), "--config", str(profile),
                               "--trace-commit", "--terminal-log", str(terminal),
                               "--inst-limit", "1000000", str(elf)],
                              capture_output=True, text=True, errors="replace",
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return "FAIL", " (no HTIF write within the timeout)", None
    output = done.stdout + done.stderr
    records = trace.normalize_commit(output.splitlines())
    if "SUCCESS" in output and done.returncode == 0:
        return "PASS", "", records
    failure = re.search(r"FAILURE: (\d+)", output)
    if failure:
        return "FAIL", f" (check {failure.group(1)} failed)", records
    return "FAIL", f" (rc={done.returncode}, no HTIF verdict)", records


def cmd_asm(e: env.Environment, args: argparse.Namespace) -> int:
    """Assemble one dialect program into an image the emulator loads."""
    try:
        size = asm.assemble_file(Path(args.source), Path(args.elf))
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"ok {args.elf}: {size} bytes")
    return 0


def cmd_devicetree(e: env.Environment, args: argparse.Namespace) -> int:
    """Generate the attested devicetree, compile it with `dtc` (zero warnings), and verify it fits its memory region."""
    if (missing := _missing_simulator(e)) is not None:
        print(missing, file=sys.stderr)
        return 1
    _require("dtc", "apt install device-tree-compiler")
    sim = e.simulator
    profile = e.profile

    dts = subprocess.run([str(sim), "--config", str(profile), "--print-device-tree"],
                         capture_output=True, text=True, check=False)
    if dts.returncode:
        print(f"the model would not generate a devicetree:\n{dts.stderr}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        source, blob = Path(tmp) / "vos.dts", Path(tmp) / "vos.dtb"
        source.write_text(dts.stdout, encoding="utf-8")
        built = subprocess.run(["dtc", "-I", "dts", "-O", "dtb",
                                "-o", str(blob), str(source)],
                               capture_output=True, text=True, check=False)
        if built.returncode:
            print(f"dtc refused the generated tree:\n{built.stderr}", file=sys.stderr)
            return 1
        if built.stderr.strip():
            print(f"dtc compiled the generated tree with warnings:\n{built.stderr}",
                  file=sys.stderr)
            return 1
        size = blob.stat().st_size

        corpus = differential.load(e.root)
        if not corpus.members:
            print("the differential corpus contains no member for the devicetree check",
                  file=sys.stderr)
            return 1
        elf = differential.assemble(corpus, corpus.members[0], Path(tmp))
        try:
            fits = subprocess.run([str(sim), "--config", str(profile),
                                   "--device-tree-blob", str(blob), str(elf)],
                                  capture_output=True, text=True, timeout=120, check=False)
        except subprocess.TimeoutExpired:
            print(f"the emulator did not exit within 120 s running "
                  f"{corpus.members[0].name} with the generated blob loaded",
                  file=sys.stderr)
            return 1
        said = fits.stdout + fits.stderr
        if "does not fit" in said:
            print(f"the generated devicetree does not fit the region it is written "
                  f"into at {size} bytes:\n{said}", file=sys.stderr)
            return 1
        if fits.returncode:
            print(f"the devicetree fits at {size} bytes, but the emulator would not "
                  f"run {corpus.members[0].name} with it loaded:\n{said}",
                  file=sys.stderr)
            return 1

    print(f"ok the generated devicetree compiles with no warning at {size} bytes, "
          "inside the region it is written to")
    return 0


def cmd_reference(e: env.Environment, args: argparse.Namespace) -> int:
    """Print the frozen golden model's revision, compiler, property count, and differential corpus summary."""
    if (missing := _missing_simulator(e)) is not None:
        print(missing, file=sys.stderr)
        return 1

    info = subprocess.run([str(e.simulator), "--build-info"],
                          capture_output=True, text=True, check=False)
    if info.returncode:
        print(f"the emulator's build-info probe failed: {info.stderr.strip()}",
              file=sys.stderr)
        return 1
    fields = dict(
        line.split(": ", 1) for line in info.stdout.splitlines() if ": " in line)
    revision = fields.get("Sail RISC-V git", "unknown commit")

    corpus = differential.load(e.root)
    records = sum(m.records for m in corpus.members)
    checks = sum(m.checks for m in corpus.members)

    harness = e.build_dir / "test" / "unit_tests" / "unit_tests"
    properties = 0
    if not harness.is_file():
        print(f"the property harness is missing: {harness}", file=sys.stderr)
        return 1
    try:
        run = subprocess.run([str(harness)], capture_output=True, text=True,
                             timeout=300, check=False)
    except subprocess.TimeoutExpired:
        print(f"the property harness at {harness} did not exit within 300 s",
              file=sys.stderr)
        return 1
    except OSError as err:
        print(f"the property harness could not run: {err}", file=sys.stderr)
        return 1
    if run.returncode:
        print(f"the property harness failed (exit {run.returncode}):\n"
              f"{run.stdout}\n{run.stderr}", file=sys.stderr)
        return 1
    properties = sum(1 for line in run.stdout.splitlines()
                     if line.startswith("Testing "))
    if not properties:
        print("the property harness reported no tests", file=sys.stderr)
        return 1

    print(f"model revision   {revision}")
    print(f"sail compiler    {fields.get('Sail', 'unknown')}")
    print(f"upstream release {fields.get('Sail RISC-V release', 'unknown')}")
    print(f"properties       {properties}")
    print(f"corpus           v{corpus.version}, {len(corpus.members)} members, "
          f"{checks} checks, {records} records")

    if "unknown" in revision:
        print("the emulator cannot name the model it was generated from, so nothing "
              "downstream can record which reference it was stated against",
              file=sys.stderr)
        return 1
    return 0


def cmd_config_keys(e: env.Environment, args: argparse.Namespace) -> int:
    code, lines = config.compare_keys(args.generated, args.profile)
    print("\n".join(lines))
    return code


def cmd_validate_config(e: env.Environment, args: argparse.Namespace) -> int:
    code, lines = config.validate(args.schema, args.config)
    print("\n".join(lines))
    return code


def cmd_keepalive(e: env.Environment, args: argparse.Namespace) -> int:
    if args.stop:
        env.keepalive_stop()
    else:
        env.keepalive(args.hours)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(suggest_on_error=True, description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("typecheck", suggest_on_error=True, help="Sail typecheck only, no emission").set_defaults(
        run=cmd_typecheck)

    bundle = sub.add_parser(
        "bundle", suggest_on_error=True, help="regenerate the model's machine-readable bundle")
    bundle.add_argument("--check", action="store_true",
                        help="emit to a scratch path and hold the tracked bundle "
                             "against it, writing nothing")
    bundle.set_defaults(run=cmd_bundle)

    emit = sub.add_parser("emit", suggest_on_error=True, help="emit C++, then validate the profile config")
    emit.add_argument("--offline", action="store_true", help="require already verified dependency inputs")
    emit.set_defaults(run=cmd_emit)

    rocq = sub.add_parser("rocq", suggest_on_error=True, help="emit the canonical Rocq term through the model's own "
                                "target and write its generation-identity receipt"
                   )
    rocq.add_argument("--offline", action="store_true", help="require already verified dependency inputs")
    rocq.set_defaults(run=cmd_rocq)

    dependencies = sub.add_parser("dependencies", suggest_on_error=True,
                                  help="prepare verified dependency inputs before configuration")
    dependencies.add_argument("--offline", action="store_true", help="verify cached inputs without downloading")
    dependencies.add_argument("--fast", action="store_true", help="prepare the iterate build tree")
    dependencies.set_defaults(run=cmd_dependencies)

    build = sub.add_parser("build", suggest_on_error=True, help="configure, build, and run the bundled suite")
    build.add_argument("--fast", action="store_true",
                       help="the iterate profile: the canonical build without -g")
    build.add_argument("--background", action="store_true",
                       help="detach the run and return; wait on it with `run.py model wait`")
    build.add_argument("--offline", action="store_true", help="require already verified dependency inputs")
    build.set_defaults(run=cmd_build)

    simulator = sub.add_parser("simulator", suggest_on_error=True, help="build only the Q39 replay simulator dependency")
    simulator.add_argument("--out", required=True,
                           help="fresh absolute native output directory in this checkout's lane")
    simulator.add_argument("--offline", action="store_true", help="require already verified dependency inputs")
    simulator.set_defaults(run=cmd_simulator)

    wait = sub.add_parser("wait", suggest_on_error=True, help="wait for this lane's build, then report it")
    wait.add_argument("--fast", action="store_true", help="the iterate profile's build")
    wait.set_defaults(run=cmd_wait)

    sub.add_parser("lane", suggest_on_error=True, help="where this checkout builds, and what is building there"
                   ).set_defaults(run=cmd_lane)

    smt = sub.add_parser("smt", suggest_on_error=True, help="the capability-helper property suite under the "
                                     "SMT target, one verdict and one time per property")
    smt.add_argument("--property", action="append", default=[], metavar="NAME",
                     help="run this property alone (repeatable; default: every one)")
    smt.add_argument("--timeout", type=int, default=600,
                     help="seconds the solver gets per property before it is undecided")
    smt.add_argument("--solver", choices=SMT_SOLVERS, default="z3",
                     help="SMT-LIB2 solver for emitted properties (default: z3)")
    smt.add_argument("--auto", action="store_true",
                     help="Sail's own --smt-auto instead, which renders and replays a "
                          "counterexample in Sail values and has no per-property timeout")
    smt.add_argument("--reuse", action="store_true",
                     help="solve the files the last run emitted rather than emitting again")
    smt.set_defaults(run=cmd_smt)

    oracle = sub.add_parser("oracle", suggest_on_error=True,
                            help="build the M0.4 capability oracle and run its suite")
    oracle.add_argument("--resync", action="store_true",
                        help="re-copy the pinned tree before building")
    oracle.add_argument("--timeout", type=int, default=5,
                        help="seconds before a bundled test counts as failed")
    oracle.set_defaults(run=cmd_oracle)

    sweep = sub.add_parser("sweep", suggest_on_error=True, help="classify riscv-tests against the frozen profile")
    sweep.add_argument("--xlen", default="64")
    sweep.add_argument("--timeout", type=int, default=10,
                       help="seconds before a test is classified as a hang")
    sweep.set_defaults(run=cmd_sweep)

    td = sub.add_parser("trace-diff", suggest_on_error=True,
                        help="adjudicate the curated model against the M0.4 oracle")
    td.add_argument("elf", nargs="*", help="the programs to run on both executors")
    td.add_argument("--corpus", action="store_true",
                    help="every rv64ui-p-* in the downloaded suite")
    td.add_argument("--floor", type=int, default=0,
                    help="the agreeing prefix below which a member is a regression")
    td.add_argument("--limit", type=int, default=100000, help="instruction limit per run")
    td.add_argument("--timeout", type=int, default=60,
                    help="seconds before an executor counts as hung")
    td.add_argument("--context", type=int, default=4,
                    help="records of agreement to print before a divergence")
    td.set_defaults(run=cmd_trace_diff)

    cp = sub.add_parser("corpus", suggest_on_error=True, help="assemble and run the differential corpus")
    cp.add_argument("member", nargs="*", help="the members to run (default: all)")
    cp.add_argument("--assemble-only", action="store_true",
                    help="write the images and do not run them")
    cp.add_argument("--persistence-only", action="store_true",
                    help="run only the architectural persistent-device reopen campaign")
    cp.add_argument("--out", help="where to write the images")
    cp.add_argument("--refresh", action="store_true",
                    help="rewrite the manifest's record counts and trace digests")
    cp.add_argument("--timeout", type=int, default=30,
                    help="seconds before a member counts as never having reported")
    cp.set_defaults(run=cmd_corpus)

    fz = sub.add_parser("freeze-emit", suggest_on_error=True,
                        help="emit §4's link map and per-site table for the corpus")
    fz.add_argument("member", nargs="*", help="the members to emit (default: all)")
    fz.add_argument("--out", help=f"where to write them (default: "
                                  f"{freezeschema.BUILD_DIR})")
    fz.add_argument("--header", type=int, default=compose.Geometry().header,
                    help="bundle header bits (FD-2 declares no default arm)")
    fz.add_argument("--slots", type=int, default=compose.Geometry().slots,
                    help="slots per bundle (FD-2 declares no default arm)")
    fz.add_argument("--width", type=int, default=compose.Geometry().width,
                    help="slot width in bits")
    fz.set_defaults(run=cmd_freeze_emit)

    asm_cmd = sub.add_parser("asm", suggest_on_error=True, help="assemble one dialect program")
    asm_cmd.add_argument("source")
    asm_cmd.add_argument("elf")
    asm_cmd.set_defaults(run=cmd_asm)

    sub.add_parser("reference", suggest_on_error=True,
                   help="print the frozen golden model's identity"
                   ).set_defaults(run=cmd_reference)
    sub.add_parser("devicetree", suggest_on_error=True,
                   help="generate, compile, and size-check the attested devicetree"
                   ).set_defaults(run=cmd_devicetree)
    ck = sub.add_parser("config-keys", suggest_on_error=True, help="compare two configurations' key sets")
    ck.add_argument("generated", type=Path)
    ck.add_argument("profile", type=Path)
    ck.set_defaults(run=cmd_config_keys)

    vc = sub.add_parser("validate-config", suggest_on_error=True, help="validate a config against a schema")
    vc.add_argument("schema", type=Path)
    vc.add_argument("config", type=Path)
    vc.set_defaults(run=cmd_validate_config)

    ka = sub.add_parser("keepalive", suggest_on_error=True, help="hold the WSL distribution up for a bounded time")
    ka.add_argument("--hours", type=int, default=env.keepalive_hours())
    ka.add_argument("--stop", action="store_true")
    ka.set_defaults(run=cmd_keepalive)

    args = parser.parse_args(argv)
    # Read host-compatible subcommands from the shared command table.
    hosted = next((c.host_ok for c in commands.COMMANDS if c.name == "model"), frozenset())
    needs_guest = args.command not in hosted
    e = env.load(toolchain=needs_guest)
    e.model_offline = e.model_offline or getattr(args, "offline", False)
    if args.command != "keepalive" and needs_guest:
        # every loop holds the distribution up while it runs, so a long build does not
        # lose the VM underneath it; the keepalive command manages that lease directly
        env.keepalive()
    # Restore the signature erased by argparse so the call and return type are checked.
    run = cast("Command", args.run)
    return run(e, args)
