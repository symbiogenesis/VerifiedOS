#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The curated Sail model's build loops, from the fastest to the slowest.

Five loops, and each is the exit criterion for the one above it:

    typecheck   ~30 s    Sail reports every dangling reference a cut leaves behind
    bundle      ~25 s    the model's own machine-readable view of itself, regenerated
    emit        ~2 min   the full C++ emission, then the config against its schema
    build       ~15 min  emission, compile, and the bundled ctest suite
    sweep       ~1 min   the profile configuration against the downloaded riscv-tests

`typecheck` is the inner loop of a deletion batch; `build` stays the exit criterion for
every batch, and `sweep` is the number each batch reports. `bundle` sits between the
first two because it is a typecheck with a serializer on the end of it: it costs what a
typecheck costs and it writes the one artifact the host lane reads the model through. `trace-diff` is the M0.6e
differential rig, adjudicating the curated model against the M0.4 oracle, and `oracle`
builds that reference. `devicetree` generates the attested tree, compiles it, and holds
the blob against the region it is written into, which is three things the Sail emitter
cannot decide about its own output. `reference` prints what the frozen golden model is,
which is what a downstream artifact records when it says which model it was stated
against. Two more commands answer questions about the configuration alone and need no
build: `config-keys` and `validate-config`.

These run inside WSL, where the Sail toolchain lives:

    python tools/run.py model build --background
    python tools/run.py model wait
    python tools/run.py model sweep --xlen 64

Everything about the machine and the build trees comes from vos/env.py, which also
raises the OCaml stack the emission needs and puts the opam switch on PATH.

One toolchain serves as many checkouts as there are git worktrees, and each gets a
**lane**: its own build tree, its own log, and its own SMT cache, derived from the
checkout rather than declared. `lane` says which one this is. A build holds its lane
for as long as it runs, so a second one over a live one is refused rather than merged
into it, and `wait` blocks on that lock rather than on a marker or on a sleep.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import IO, cast

from vos import (
    asm,
    cli,
    compose,
    config,
    differential,
    env,
    freezeschema,
    sailbundle,
    trace,
)

# What every subcommand handler is. `main` attaches one to each subparser and
# `argparse` hands it back as an untyped attribute, so the shape is stated once
# here and asserted at the single point it is called.
type Command = Callable[[env.Environment, argparse.Namespace], int]

SCHEMA = "sail_riscv_config_schema.json"
EMIT_TARGET = "generated_sail_riscv_model"

# The emitter asks git where it is standing, and the answer must not reach the artifact.
# `sail --doc` shells out to `git rev-parse HEAD` and, where that answers, writes a
# `git` object of the commit and a dirty flag into the bundle it emits. Two things then
# follow, and both are fatal to holding the artifact byte-for-byte: the bytes would move
# on every commit, so a tracked bundle would be stale the moment it landed and the rule
# over it would report on a fact about the checkout rather than about the model; and
# whether the object appears at all would depend on whether `GIT_DIR` happened to be
# exported into the stage, which a lane's configure does and a bare emission does not,
# so one lane's bundle and another's would differ while describing one model. Pointing
# `GIT_DIR` at a path that is not there makes the question fail rather than answer, the
# emitter omits the object, and what is left is a function of the Sail sources alone.
# The stage runs one binary and that binary reads git for this and nothing else.
_NO_GIT = "/nonexistent/the-bundle-describes-the-model-not-the-checkout"

# How the one binary every Sail loop starts with is installed, for the refusal that
# names it.
SAIL_HOW = "the Sail toolchain lives in the opam default switch: opam install sail"

# What `cmd_build` writes after each stage, and what `wait` reads a finished run's
# verdict back out of. One spelling, at both ends.
STAGE_EXIT = re.compile(r"^\w+_EXIT=(\d+)$")

ORACLE_SRC = "upstream/sail-cheri-riscv"
ORACLE_TARGET = "c_emulator/cheri_riscv_sim_RV64"

# The C standard the oracle's tree is built to. gcc 15 defaults to C23, in which an
# empty parameter list declares *no* parameters rather than an unspecified one; Sail's
# `rts.h` predates that reading (`unit platform_barrier();`, `plat_get_16_random_bits()`)
# and the emitted C calls both with arguments, so the build stops on a type error that
# is neither tree's fault. It rides in on `C_WARNINGS` rather than `CC` because the
# tree's recipe hardcodes `gcc`, which makes a `CC` override silently do nothing, and
# because `C_WARNINGS` is declared `?=` and sits ahead of `$(C_FLAGS)` on the compile
# line: a command-line assignment wins there without replacing the flags the tree sets
# for itself. The curated model needs none of this, emitting C++ where the prototypes
# were never ambiguous.
ORACLE_CSTD = "-std=gnu17"

# What a Windows checkout can leave CRLF in and both `make` and `sail` then read as LF.
ORACLE_TEXT_SUFFIXES = (".sail", ".ml", ".mli", ".lem", ".sh", ".mk", ".c", ".h",
                        ".cpp", ".hpp", ".json")
ORACLE_TEXT_NAMES = ("Makefile", "opam")


def _configure(e: env.Environment, build_dir: Path,
               extra: list[str] | None = None, out: IO[str] | None = None) -> int:
    """The one cmake configure line. It was written out in two loops, which is one fact
    in two places and a pair that can silently stop agreeing.

    `GIT_DIR` rides along for a lane whose `.git` names its administrative directory in
    the host's spelling, because the `git describe` cmake runs at configure is what
    stamps the emulator with the model revision every downstream artifact records itself
    against. It is scoped to this one child and no further: see `env.git_dir`.
    """
    admin = env.git_dir(e.root)
    return env.stage("configure", [
        "cmake", "-S", str(e.model), "-B", str(build_dir), "-GNinja",
        "-DCMAKE_BUILD_TYPE=RelWithDebInfo",
        "-DDOWNLOAD_GMP=FALSE",
        "-DENABLE_RISCV_TESTS=TRUE",
        *e.compilers, *e.ccache, *(extra or []),
    ], stdout=out, stderr=out,
       add_env=None if admin is None else {"GIT_DIR": str(admin)})


def _require(binary: str, how: str) -> None:
    """Refuse in one line naming the absent binary rather than letting the first
    subprocess that asks for it raise a FileNotFoundError traceback."""
    if shutil.which(binary) is None:
        raise SystemExit(f"no `{binary}` on PATH; {how}")


def _missing_simulator(e: env.Environment) -> str | None:
    """The refusal every loop downstream of a build shares: each reads the simulator
    back out of this lane's build tree, and an absent one means nothing has built
    here yet."""
    if e.simulator.exists():
        return None
    return f"no simulator at {e.simulator}; run `run.py model build` first"


def cmd_typecheck(e: env.Environment, args: argparse.Namespace) -> int:
    """Typecheck the curated model without emitting code."""
    _require("sail", SAIL_HOW)
    # Sail rewrites the memo cache whole at exit (see `_seed_smt_cache`), so a second
    # typecheck over a live one is refused rather than left to interleave two
    # whole-file rewrites of the one cache.
    with env.hold_lock(e.typecheck_cache, "a typecheck"):
        return subprocess.run(
            ["sail", "--strict-var", "--strict-bitvector", "--strict-exponentials",
             "--memo-z3", "--memo-z3-path", str(e.typecheck_cache),
             "--just-check", "--all-modules", "riscv.sail_project"],
            cwd=e.model / "model", check=False).returncode


def cmd_bundle(e: env.Environment, args: argparse.Namespace) -> int:
    """Regenerate the model's own machine-readable bundle into the tracked path.

    This is the generator half of K-88, and it is the half a Windows host cannot run.
    The bundle is Sail's own view of the model it just typechecked, so it is emitted by
    Sail and by nothing else here: what this function contributes is the lane, the lock,
    the warm cache and the byte comparison, never a transformation of the output. A
    tracked artifact that is not exactly what the emitter wrote would make the rule that
    holds it a rule about this function.

    **Sail is invoked directly rather than through cmake's `generated_sail_riscv_docs`
    target.** That target chains `generated_html_tgz` (model/model/CMakeLists.txt), so
    asking cmake for the JSON buys a second full Sail run and a tar of an HTML tree
    nothing here reads. The flags below are the ones that target passes, less the two
    that decide nothing about the output: `--require-version`, which asserts a floor the
    lane already meets, and the html target's own.

    The lane's build lock is held for the run, because the memo cache this reads and
    rewrites is the build tree's and Sail rewrites it whole at exit; a bundle over a live
    build in the same lane would be two writers of one cache, which is the failure
    `_seed_smt_cache` states in full. The tree is seeded first for the same reason a
    build seeds it: cold, the emission is minutes rather than seconds.

    `--check` emits to a scratch path and compares, writing nothing. That is the guest
    lane's half of K-88's claim and it is what makes the host lane's half honest: the
    host holds the tracked bytes against the index and against the sources the bundle
    itself records, and this holds them against the emitter.
    """
    _require("sail", SAIL_HOW)
    build_dir = e.build_dir
    lock = env.build_lock(build_dir)
    try:
        _seed_tree(e, build_dir)
        tracked = e.root / sailbundle.BUNDLE
        scratch = e.lane_root / "bundle"
        remove = scratch if args.check else None
        into = scratch if args.check else tracked.parent
        into.mkdir(parents=True, exist_ok=True)
        # read before the emission, because without --check the emitter writes over the
        # very path the comparison is against and every run would report itself unchanged
        before = tracked.read_bytes() if tracked.is_file() else None
        code = env.stage("bundle", [
            "sail",
            "--strict-var", "--strict-bitvector", "--strict-exponentials",
            "--memo-z3", "--memo-z3-path", str(build_dir / "model" / "sail_smt_cache"),
            "--doc",
            "--doc-format", "identity",
            "--doc-compact",
            "--doc-embed", "plain",
            "--doc-embed-with-location",
            "-o", str(into),
            "--doc-bundle", sailbundle.BUNDLE_NAME,
            "--all-modules", "riscv.sail_project",
        ], cwd=e.model / "model", add_env={"GIT_DIR": _NO_GIT})
        if code:
            return code
        written = into / sailbundle.BUNDLE_NAME
        if not written.is_file():
            print(f"sail exited 0 and wrote no {written}", file=sys.stderr)
            return 1
        code = _bundle_verdict(written, before, check=args.check)
    finally:
        if remove is not None and remove.is_dir():
            shutil.rmtree(remove, ignore_errors=True)
        if lock is not None:
            lock.close()
    return code


def _bundle_verdict(written: Path, held: bytes | None, *, check: bool) -> int:
    """Say what the emission decided, in bytes rather than in adjectives.

    Under `--check` the emitted bytes are held against the tracked ones and a
    difference is the finding; otherwise the emitted bytes *are* the tracked ones and
    what is reported is whether they moved, because a regeneration that changes nothing
    is the ordinary case and a caller wants to know which one this was. `held` is the
    tracked bytes as they stood *before* the run, which is the only reading that means
    anything on the path that overwrites them.
    """
    fresh = written.read_bytes()
    if not check:
        moved = "unchanged" if held == fresh else "rewritten"
        print(f"ok {sailbundle.BUNDLE}: {len(fresh)} bytes, {moved}")
        return 0
    if held is None:
        print(f"{sailbundle.BUNDLE} is not there, so the emitter's {len(fresh)} bytes "
              "are held against nothing", file=sys.stderr)
        return 1
    if held != fresh:
        where = next((i for i, (a, b) in enumerate(zip(held, fresh, strict=False))
                      if a != b), min(len(held), len(fresh)))
        print(f"{sailbundle.BUNDLE} is {len(held)} bytes and the emitter writes "
              f"{len(fresh)}, first differing at byte {where}; regenerate it with "
              "`run.py model bundle`", file=sys.stderr)
        return 1
    print(f"ok {sailbundle.BUNDLE}: {len(fresh)} bytes, byte-identical to what the "
          "emitter writes from the model in this checkout")
    return 0


def cmd_emit(e: env.Environment, args: argparse.Namespace) -> int:
    """Run the full C++ emission, which regenerates the config schema, then hand the
    fresh schema and the frozen profile to the validator. No C++ is compiled."""
    build_dir = e.build_dir
    # The same tree `build` locks, held the same way: an emit over a live build, or a
    # second emit, would drive one cmake state in one tree from two runs.
    lock = env.build_lock(build_dir)
    try:
        if not (build_dir / "build.ninja").exists() and _configure(e, build_dir):
            return 1
        # a single-threaded stage; -j is passed for uniformity, not for speed
        if env.stage("emit", ["cmake", "--build", str(build_dir), "-j", str(e.jobs),
                              "--target", EMIT_TARGET]):
            return 1
        code, lines = config.validate(build_dir / SCHEMA, e.profile)
        print("\n".join(lines))
        return code
    finally:
        if lock is not None:
            lock.close()


def cmd_build(e: env.Environment, args: argparse.Namespace) -> int:
    """Build the curated model out of tree and run its bundled suite.

    --fast selects the iterate profile: a separate build dir whose only divergence from
    the canonical build is dropping `-g` from RelWithDebInfo. Debug info on the
    machine-generated translation unit is the single largest compile cost, 314 s against
    239 s measured in-build and so under N-way contention, and is never used;
    optimization level, assertions, and the test suite are identical. What that unit
    costs compiled alone is `vos/env.py`'s to state, because it is the same fact and it
    moves with the curation. The canonical build remains the exit criterion for every
    batch.

    --background detaches the run and returns, because a fifteen-minute build is started
    and left and the caller has other work. What it does not do is let go of the lane:
    the lock is taken here, before anything is written, and the detached child inherits
    it, so a second build over a live one is refused rather than merged into it.
    """
    _require("sail", SAIL_HOW)
    if args.fast:
        build_dir = e.fast_build_dir
        log = e.log("model-build-fast")
        extra = ["-DCMAKE_CXX_FLAGS_RELWITHDEBINFO=-O2 -DNDEBUG",
                 "-DCMAKE_C_FLAGS_RELWITHDEBINFO=-O2 -DNDEBUG"]
    else:
        build_dir, log, extra = e.build_dir, e.log("model-build"), []

    # Before the log is opened, so that a refused build cannot truncate the log of the
    # run it was refused in favour of.
    lock = env.build_lock(build_dir)
    _seed_tree(e, build_dir)
    if args.background:
        return _detach(args, log, lock)

    e.log_dir.mkdir(parents=True, exist_ok=True)
    version = subprocess.run(["sail", "--version"], capture_output=True, text=True, check=False)

    # The whole run goes to one log and the console says only where it is. A build is
    # long enough to be started and left, so the caller needs a file to come back to
    # and, at the end of it, one line saying the run is over: waiting on that marker is
    # how a caller learns the build finished, rather than by guessing at a sleep.
    print(f"== log: {log}", flush=True)
    with log.open("w", encoding="utf-8") as handle:
        handle.write(f"== sail: {version.stdout.strip()}\n")
        handle.write(f"== lane: {e.lane or 'primary'} in {build_dir}\n")
        handle.write(f"== host: {e.cpus} cpu, {e.mem_available_mb} MB available; "
                     f"build -j{e.jobs}, ctest -j{e.test_jobs}\n")
        handle.flush()

        # Each stage gates the next: a configure that failed makes the build's error a
        # second symptom of the first, and reporting both hides which one to fix.
        code = 0
        for name, argv in (
            ("configure", None),
            ("build", ["cmake", "--build", str(build_dir), "-j", str(e.jobs)]),
            ("ctest", ["ctest", "--test-dir", str(build_dir), "-j", str(e.test_jobs),
                       "--output-on-failure"]),
        ):
            code = (_configure(e, build_dir, extra, handle) if argv is None
                    else env.stage(name, argv, stdout=handle, stderr=handle))
            handle.write(f"{name.upper()}_EXIT={code}\n")
            handle.flush()
            if code:
                break
        handle.write("ALL_DONE\n")

    print(f"== {'green' if code == 0 else 'failed'}: {log}")
    return code


def _detach(args: argparse.Namespace, log: Path, lock: IO[str] | None) -> int:
    """Re-run this build as a detached child and hand it the lane's lock.

    The lock travels by inheritance rather than by being taken twice. `flock` belongs to
    the open file description, and `pass_fds` keeps the parent's descriptor open across
    the exec, so the child holds the same lock without knowing it does and the kernel
    gives it back when the child exits. `BUILD_LOCK_HELD` is what tells the child not to
    take a second one on a descriptor of its own, which would fail against the first.

    The previous run's log is removed only once the child exists, so a `Popen` that
    raises leaves that evidence standing; it is still gone before a reader can take it
    for this run's, because the child's first write sits behind its own interpreter
    start and `env.load`, and `wait` blocks on the lock before it looks at the log at
    all. Nothing else deletes it: the child recreates it.
    """
    argv = cli.entry("model", "build", *(["--fast"] if args.fast else []))
    log.parent.mkdir(parents=True, exist_ok=True)
    child = subprocess.Popen(
        argv, start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        pass_fds=() if lock is None else (lock.fileno(),),
        env={**os.environ, env.BUILD_LOCK_HELD: "1"})
    log.unlink(missing_ok=True)
    if lock is not None:
        env.record_lock_holder(lock, child.pid)
    print(f"== background: pid {child.pid}")
    print(f"== log: {log}")
    print(f"== wait: run.py model wait{' --fast' if args.fast else ''}")
    return 0


def _seed_tree(e: env.Environment, target: Path) -> None:
    """Give a build tree that does not exist yet the warm state of one that does, so
    that standing a lane up costs neither of the two things a cold tree pays for twice.

    The pre-downloaded test ELFs would otherwise re-download the tarball. The Sail SMT
    memo cache matters more: a cold cache re-discharges every Z3 obligation and turns
    the ~36 s emission into ~3.6 min under the pinned solver, ~4.7 min under the
    distribution's (I3, two repeats per arm, 2026-08-22; the ~25 min once measured
    here described the model before the curation deleted most of its surface).
    Standing a lane up is 202.3 s seeded under the clang `env._compiler_args` selects,
    configure 50.6 s, build 106.9 s at 329% CPU and ctest 44.8 s over 375 edges (one
    run, quiet box, 2026-08-22), which is what makes a lane cheap enough to be worth
    having.
    """
    # This lane's canonical tree first and the primary worktree's second: the fast tree
    # wants the lane it belongs to, and a lane's own first build has only the primary to
    # ask. On the primary worktree the two are the same path, which `!=` removes.
    donors = [d for d in (e.build_dir, e.primary_build_dir) if d != target and d.is_dir()]
    _seed_smt_cache(donors, target)
    _seed_test_data(donors, target)


def _seed_smt_cache(donors: list[Path], target: Path) -> None:
    """Copy a warm memo cache into a tree that has none, and never share one. This is
    the whole of the I2 finding, and it is a property of the pinned compiler rather
    than a preference.

    Sail's cache is one flat file of fixed records, a 16-byte digest of the SMT query
    and one byte of verdict, read whole into a map at startup by `load_digests` and
    rewritten whole from that map at exit by `save_digests` (libsail 0.20.2,
    `constraint.ml`). There is no lock, no atomic rename, and `open_out_bin` truncates
    in place. A tree's cache here measures 1,418,412 bytes, which is 83,436 records
    with no remainder.

    Three things follow, and each alone is enough to refuse a shared path. Concurrent
    runs do not *merge*: each writes back what it loaded plus what it learned, so the
    later writer's file is missing everything the earlier one learned during the
    overlap, and that is worst exactly when the cache is cold and the learning is
    largest. A reader arriving mid-rewrite sees a prefix, or sees one byte out of the
    verdict range and takes the invalid path, which empties both maps and then replaces
    the shared file with only this run's own entries: measured, one such byte destroyed
    77,260 of 83,436 records and Sail still exited 0. And two writers interleave at
    whatever offset each buffer flushed; records are 17 bytes and OCaml flushes at
    65,536, which is 1 modulo 17, so the sixteenth boundary falls exactly on a verdict
    byte and leaves one run's genuine digest carrying another run's answer to a
    different obligation.

    Content-keying then makes a stale *copy* cost misses and nothing worse, but only
    within one distribution and one solver: the key is the obligation, not the prover
    that discharged it, so a cache carried across either boundary hands the pinned
    solver another solver's answers to read back as its own. That is the silent
    difference `env._prepend_z3_path` exists to announce. Both donors are this
    machine's, so neither boundary is crossed, and the copy has one writer. The donor
    may have another: this read takes neither donor's build lock, so a seed arriving
    while a donor's own build is at `save_digests` copies whatever that rewrite has
    reached. What that costs stays on the copy, a lane starting from a prefix or a torn
    record paying the cold cache this seed exists to avoid and no donor paying anything.
    """
    cache = target / "model" / "sail_smt_cache"
    if cache.exists():
        return
    for donor in donors:
        source = donor / "model" / "sail_smt_cache"
        if source.exists():
            cache.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, cache)
            return


def _seed_test_data(donors: list[Path], target: Path) -> None:
    """Copy the downloaded riscv-tests and nothing else.

    The suite is recognized by holding a `riscv-tests` directory, which is the same
    thing `sweep` and `trace-diff` glob for, rather than by being any directory under
    `test/`: the rest of what is there is cmake's and ninja's, and a fresh tree that
    finds a previous tree's `CMakeFiles` under it is being configured against a state
    it did not produce.
    """
    for donor in donors:
        for suite in sorted(donor.glob("test/*/riscv-tests")):
            into = target / "test" / suite.parent.name
            if not into.exists():
                into.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(suite.parent, into)


def cmd_wait(e: env.Environment, args: argparse.Namespace) -> int:
    """Wait for this lane's build to finish, then report what it decided.

    The wait is on the lane's lock rather than on the log, because the lock is released
    by the kernel when the builder exits however it exits, where a marker is only
    written by a build that got as far as writing one. The log carries the verdict, and
    it is read while the lock is still held: read after releasing, a build started in
    that window truncates the log first and the report is about the wrong run.
    """
    log = e.log("model-build-fast" if args.fast else "model-build")
    lock = env.wait_for_build(e.fast_build_dir if args.fast else e.build_dir)
    try:
        return _report_build(log)
    finally:
        if lock is not None:
            lock.close()


def _report_build(log: Path) -> int:
    """Read a finished build's log back as a verdict.

    The exit code is the last stage's, because `cmd_build` stops at the first stage that
    fails: a run with no `ALL_DONE` is one that was killed or is still starting, and it
    is a finding rather than a silence, because the caller asked what the build decided
    and there is no answer to give.
    """
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


def cmd_lane(e: env.Environment, args: argparse.Namespace) -> int:
    """Say where this checkout builds, and whether anything is building there.

    One command, because the failure this exists to end is a checkout reading a
    simulator some other checkout generated, and the way that is caught is by being able
    to ask which tree this one is talking about.
    """
    holder = env.build_holder(e.build_dir)
    print(f"lane             {e.lane or 'primary (this checkout is not a linked worktree)'}")
    print(f"checkout         {e.root}")
    print(f"build tree       {e.build_dir}")
    print(f"fast tree        {e.fast_build_dir}")
    print(f"typecheck cache  {e.typecheck_cache}")
    print(f"oracle tree      {e.oracle_root} (shared by every lane)")
    print(f"build log        {e.log('model-build')}")
    print(f"building now     {f'yes, pid {holder}' if holder else 'no'}")
    return 0


def cmd_oracle(e: env.Environment, args: argparse.Namespace) -> int:
    """Build the M0.4 capability oracle, then run the RV64 suite bundled with it.

    The oracle is stock `sail-cheri-riscv` at the pinned `bb07488d`, built against the
    older `sail-riscv` embedded in it. `trace-diff` refuses to run without it, so the
    recipe belongs here rather than in a shell script on one machine: the tree is
    disposable and the machine is replaceable, and what has to survive both is how to
    build it again.

    It builds from a copy on ext4 rather than in place. The build writes generated C
    into its own source tree, and a pinned submodule working tree is not somewhere a
    build may write; the copy is also where CRLF is normalized out.

    The suite it then runs is the oracle's own acceptance and not the transplant's: it
    says the reference is a working machine before `trace-diff` is allowed to treat it
    as evidence.
    """
    _require("sail", SAIL_HOW)
    src = e.root / ORACLE_SRC
    if not (src / "Makefile").is_file():
        print(f"no oracle source at {src}; the submodule is not checked out",
              file=sys.stderr)
        return 1

    tree = e.oracle_root
    e.log_dir.mkdir(parents=True, exist_ok=True)
    log = e.log("oracle-build")
    version = subprocess.run(["sail", "--version"], capture_output=True, text=True, check=False)

    # The one tree every lane shares, so the lock sits beside it rather than in any
    # lane, and a second run, from this checkout or another, is refused rather than
    # left to rmtree the tree out from under the first's make. Taken before the log is
    # opened, so a refused run cannot truncate the log of the one it lost to.
    with env.hold_lock(tree, "an oracle build"):
        print(f"== log: {log}", flush=True)
        with log.open("w", encoding="utf-8") as handle:
            handle.write(f"== sail: {version.stdout.strip()}\n")
            handle.write(f"== tree: {tree}\n")
            if args.resync or not (tree / "Makefile").is_file():
                handle.write(f"SYNC from {src}\n")
                handle.flush()
                _sync_oracle_tree(src, tree)
            else:
                handle.write("SYNC skipped: the tree is already present\n")
            handle.flush()

            code = env.stage("oracle", ["make", "-j", str(e.jobs),
                                        f"C_WARNINGS={ORACLE_CSTD}", ORACLE_TARGET],
                             cwd=tree, stdout=handle, stderr=handle)
            handle.write(f"BUILD_EXIT={code}\n")
            handle.flush()
            if code == 0:
                code = _oracle_suite(e, tree, handle, args.timeout)
            handle.write("ALL_DONE\n")

    print(f"== {'green' if code == 0 else 'failed'}: {log}")
    return code


def _sync_oracle_tree(src: Path, tree: Path) -> None:
    """Copy the pinned tree onto ext4, then normalize the line endings in it.

    `.git` is dropped rather than copied: inside a submodule it is a file pointing back
    into the superproject, and a copy of it describes a repository that is not where it
    says it is. The nested `sail-riscv` checkout is copied like any other directory,
    because the build reads it and `git archive` would not carry it.
    """
    if tree.exists():
        shutil.rmtree(tree)
    shutil.copytree(src, tree, ignore=shutil.ignore_patterns(".git"), symlinks=True)
    for path in tree.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if path.suffix not in ORACLE_TEXT_SUFFIXES and path.name not in ORACLE_TEXT_NAMES:
            continue
        data = path.read_bytes()
        if b"\r\n" in data:
            path.write_bytes(data.replace(b"\r\n", b"\n"))


def _oracle_suite(e: env.Environment, tree: Path, handle: IO[str], timeout: int) -> int:
    """The RV64 programs bundled with the oracle's own embedded sail-riscv, run against
    the simulator just built. Each is one short single-threaded process sharing nothing,
    so the width is the core count for the same reason `sweep`'s is."""
    elves = sorted((tree / "sail-riscv" / "test" / "riscv-tests").glob("rv64*.elf"))
    if not elves:
        handle.write("no bundled rv64 ELFs found under sail-riscv/test/riscv-tests\n")
        return 1

    def passed(elf: Path) -> bool:
        try:
            done = subprocess.run([str(e.oracle), "-p", str(elf)], capture_output=True,
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
    return 1 if failed else 0


def cmd_sweep(e: env.Environment, args: argparse.Namespace) -> int:
    """Run the downloaded riscv-tests physical-variant ELFs against the *profile*
    configuration rather than the max configuration the bundled ctest suite uses, and
    classify each one.

    The two runs answer different questions. ctest asks whether the curated model is
    still a correct RISC-V implementation of everything it still implements; this sweep
    asks what the frozen profile refuses, which is the number each curation batch
    reports and every refusal is owed an explanation.

        PASS    the test runs to completion and signals success
        REFUSE  the sim exits non-zero: the test executes surface the profile deletes
        HANG    the test neither passes nor exits within the timeout, which is a refusal
                that blocks rather than fails (c3's `si-p-dirty` finding), so it is
                classified rather than left to a ctest timeout
    """
    if (missing := _missing_simulator(e)) is not None:
        print(missing, file=sys.stderr)
        return 1
    sim = e.simulator
    suites = sorted(e.build_dir.glob("test/*/riscv-tests"))
    if not suites:
        print(f"no downloaded riscv-tests under {e.build_dir}/test", file=sys.stderr)
        return 1

    profile = e.profile
    elves = [p for p in sorted(suites[0].glob(f"rv{args.xlen}*-p-*"))
             if p.suffix != ".dump"]

    def classify(elf: Path) -> tuple[str, str]:
        try:
            done = subprocess.run([str(sim), "--config", str(profile), str(elf)],
                                  capture_output=True, timeout=args.timeout, check=False)
        except subprocess.TimeoutExpired:
            return "HANG", ""
        return ("PASS", "") if done.returncode == 0 else ("REFUSE", f" rc={done.returncode}")

    # Each program is one single-threaded process reading its own ELF and sharing
    # nothing, which is what the bundled ctest suite already parallelises across; the
    # sweep is as wide as ctest is, and for the same reason. The width is the core count
    # rather than more, because a hang is classified by wall clock: sized to the cores
    # the runs do not slow each other down, and a program classified HANG is one that
    # would hang alone.
    tally = {"PASS": 0, "REFUSE": 0, "HANG": 0}
    with ThreadPoolExecutor(max_workers=e.test_jobs) as pool:
        # `map` answers in the order the programs were listed, so the report reads as it
        # always has while the runs behind it overlap
        for elf, (verdict, detail) in zip(elves, pool.map(classify, elves), strict=True):
            tally[verdict] += 1
            print(f"{verdict} {elf.name}{detail}")

    print(f"TOTAL pass={tally['PASS']} refuse={tally['REFUSE']} hang={tally['HANG']} "
          f"of {sum(tally.values())}")
    return 0


def cmd_trace_diff(e: env.Environment, args: argparse.Namespace) -> int:
    """Run the curated model and the M0.4 oracle over the same programs and adjudicate
    their traces against each other.

    The oracle is not a reference for the frozen profile: it implements ISAv9's 128-bit
    encoding with a hybrid mode and a default data capability, where the curated model
    carries the 64+1-bit purecap dialect (M0.6f), so the two executors are different
    machines and the prefix is read as a fact about how far they happen to agree. The
    module docstring of vos/trace.py holds the rig's standing: its second executor for
    the frozen profile is the RTL under Verilator co-simulation (R2), M2's fork having
    been struck, and its corpus is M0.12's purecap programs.

    Over `riscv-tests` the two part company inside the test prologue, at the first load
    through an integer base register, which a purecap machine reads as an untagged
    capability and faults on; the prefix is therefore bounded by the corpus rather than
    by either model. The regression is that the prefix must not *shorten*, which
    --floor enforces.
    """
    if (missing := _missing_simulator(e)) is not None:
        print(missing, file=sys.stderr)
        return 1
    if not e.oracle.exists():
        print(f"no M0.4 oracle at {e.oracle}; run `run.py model oracle` first",
              file=sys.stderr)
        return 1

    elves = [Path(p) for p in args.elf]
    if args.corpus:
        suites = sorted(e.build_dir.glob("test/*/riscv-tests"))
        if not suites:
            print(f"no downloaded riscv-tests under {e.build_dir}/test", file=sys.stderr)
            return 1
        elves = sorted(p for p in suites[0].glob("rv64ui-p-*") if p.suffix != ".dump")
    if not elves:
        print("nothing to compare: pass one or more ELFs, or --corpus", file=sys.stderr)
        return 1

    profile = e.profile
    tally = {"AGREE": 0, "PREFIX": 0, "SHORT": 0, "SKIP": 0}
    shortest = None

    # Deliberately one program at a time, where `sweep` runs the machine wide. The two
    # executors here run one after the other and each is milliseconds, so a corpus pass
    # is seconds already and nearly all of it is this process reading traces rather than
    # either executor producing them: that work holds the interpreter lock, so threads
    # would divide the waiting and not the work. If the M0.12 purecap corpus makes a
    # program's run long enough to dominate its adjudication, this becomes the same
    # `ThreadPoolExecutor` the sweep uses, measured first.
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
            # the profile refuses the program outright, which `run.py model sweep` already
            # classifies; there is no trace to adjudicate
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

        # Neither clean nor errored, so `Verdict.ok` leaves only a divergence. That
        # is read off the two branches above rather than stated anywhere, so it is
        # named here: the alternative is a `None` subscript at the point the tool
        # is reporting the finding it exists to report.
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
    """Both executors print their trace to stdout and their diagnostics to stderr, and
    the normalizer reads either, so the two are merged as the shell rig merged them.
    `None` is an executor that never exited: a partial trace would adjudicate as a
    divergence and blame the wrong machine, so a hang is the caller's finding to word.
    """
    try:
        done = subprocess.run(argv, capture_output=True, text=True, errors="replace",
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return None
    return (done.stdout + done.stderr).splitlines()


def cmd_corpus(e: env.Environment, args: argparse.Namespace) -> int:
    """Assemble the differential corpus and run it on the curated emulator.

    Each member is asked two questions in one run. The first is its own: a
    program reports through HTIF, so the verdict is the exit code it wrote, and
    a failure names the check that failed because `gp` carries it. The second is
    the rig's: the run emits the capability-widened commit trace, and its digest
    is held against the manifest's, so a model change that alters what a program
    does is a finding here rather than a surprise later
    (docs/differential-corpus.md).

    The programs are purecap and hand-written, and the assembler that reads them
    is [vos/asm.py](vos/asm.py) rather than a toolchain: none exists until M1.4,
    which is downstream of everything this corpus gates.
    """
    corpus = differential.load(e.root)
    # Lane-scoped like the build trees, so two lanes' runs cannot write one ELF path;
    # the manifest's digests are over the traces, not the paths, so nothing downstream
    # cares where the images landed.
    out_dir = Path(args.out) if args.out else e.lane_root / "corpus"
    wanted = set(args.member)
    members = [m for m in corpus.members if not wanted or m.name in wanted]
    if wanted - {m.name for m in members}:
        print(f"no such member: {', '.join(sorted(wanted - {m.name for m in members}))}",
              file=sys.stderr)
        return 1

    profile = e.profile
    tally = {"PASS": 0, "FAIL": 0}
    # checks, records, digest: the three fields the manifest holds per member, and
    # the three `differential.rewrite` writes back. The annotation carried two of
    # them until the commit trace widened, which nothing noticed because nothing
    # read it.
    measured: dict[str, tuple[int, int, str]] = {}
    for member in members:
        try:
            elf = differential.assemble(corpus, member, out_dir)
        except Exception as exc:                       # an assembler diagnostic
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
    return 1 if tally["FAIL"] else 0


def cmd_freeze_emit(e: env.Environment, args: argparse.Namespace) -> int:
    """Emit the two of §4's three inputs M1.4-prime's composer produces.

    Host-runnable, and that is a property of what it does rather than a convenience: the
    assembler and the composer are pure host Python and no emulator is involved, so this
    answers on either lane exactly as `model asm` does.

    **Two things this run states about itself rather than leaving to be inferred.** The
    geometry is a declared parameter and not a freeze verdict, FD-2 having no default
    arm at all; and the dictionary is empty, so every site is a verbatim escape and the
    hit rate is zero, which is a true statement about a machine no dictionary has been
    selected for rather than a measurement of one.
    """
    corpus = differential.load(e.root)
    wanted = set(args.member)
    members = [m for m in corpus.members if not wanted or m.name in wanted]
    if wanted - {m.name for m in members}:
        print(f"no such member: {', '.join(sorted(wanted - {m.name for m in members}))}",
              file=sys.stderr)
        return 1

    into = Path(args.out) if args.out else e.root / freezeschema.BUILD_DIR
    geometry = compose.Geometry(header=args.header, slots=args.slots, width=args.width)
    sites: list[asm.Site] = []
    blob = bytearray()
    with tempfile.TemporaryDirectory() as scratch:
        for member in members:
            # The ELF is a container this run does not keep: what §4 joins is the
            # encoded image's *bytes*, which the analyzer reads for their count alone,
            # and the sections are what those bytes are.
            elf = Path(scratch) / f"{member.name}.elf"
            here: list[asm.Site] = []
            try:
                asm.assemble_file(corpus.source(member), elf, here)
            except Exception as exc:                   # an assembler diagnostic
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
    """Hold a member's commit trace against the manifest's record of it."""
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
    try:
        done = subprocess.run([str(e.simulator), "--config", str(profile),
                               "--trace-commit", "--inst-limit", "1000000", str(elf)],
                              capture_output=True, text=True, errors="replace",
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return "FAIL", " (no HTIF write within the timeout)", None
    output = done.stdout + done.stderr
    records = trace.normalize_commit(output.splitlines())
    if "SUCCESS" in output:
        return "PASS", "", records
    failure = re.search(r"FAILURE: (\d+)", output)
    if failure:
        # The corpus's own convention: the exit code is the number the program
        # left in `gp`, which names the check that failed.
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
    """Generate the attested devicetree, compile it, and hold the blob against the
    region it is written into.

    Three things can go wrong here and only the third is visible from inside the model.
    A devicetree *source* is a grammar rather than a rendering, so a property written
    after a subnode and juxtaposed cell arrays are both errors `dtc` reports and the
    Sail emitter, which is string concatenation, cannot: it typechecks either way.
    And the blob has a size, which the region declared for `memory.dtb_address` bounds.

    The emulator does carry that bound, but only on the `--device-tree-blob` path, so a
    *generated* tree that outgrew its region was silent on every ordinary run. This is
    that check moved to where it is taken: the tree is generated, compiled, measured,
    and then handed back through the emulator's own bound rather than through a second
    implementation of it here.
    """
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
        # A warning is a finding here rather than a note, because the class of defect
        # this catches is a tree that renders, compiles, and describes the machine
        # wrongly. `dtc` has no global warnings-as-errors flag, its `-W` naming one
        # check at a time, so the test is that it said nothing at all.
        if built.stderr.strip():
            print(f"dtc compiled the generated tree with warnings:\n{built.stderr}",
                  file=sys.stderr)
            return 1
        size = blob.stat().st_size

        # The emulator's own bound rather than a copy of it. That bound lives on the
        # `--device-tree-blob` path and `--validate-config` exits before reaching it,
        # which is exactly why a generated tree could outgrow its region in silence:
        # the check existed and no ordinary run took the path to it. Getting there
        # costs one program, because the tree is written into memory just ahead of the
        # ELF load, so a member of the corpus stands in as the thing that makes the
        # emulator get that far.
        corpus = differential.load(e.root)
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
    """What the frozen golden model *is*, in the form a downstream artifact records.

    The Sail-generated emulator is the executable ISA reference, and everything below
    it is stated against a particular one: a freeze report carries the model revision
    its cycle columns came from, a WCET table is a projection of one timing
    annotation, and a commit-trace digest is a fingerprint of one model's behaviour.
    None of that means anything unless the reference can say which model it is, and
    until M0.10 it could not: the out-of-tree build ran `git describe` in the build
    directory, which is not a repository, so every emulator this tree has ever built
    stamped itself `unknown commit`.

    So this prints the identity rather than computing anything: the revision the
    emulator carries, the compiler that generated it, and the two corpora that say
    what it does. A `-dirty` suffix is printed and not refused, because a working tree
    under edit is the normal case and a gate that failed on it would be turned off; an
    *unknown* revision is refused, because that is the state this exists to end.
    """
    if (missing := _missing_simulator(e)) is not None:
        print(missing, file=sys.stderr)
        return 1

    info = subprocess.run([str(e.simulator), "--build-info"],
                          capture_output=True, text=True, check=False)
    fields = dict(
        line.split(": ", 1) for line in info.stdout.splitlines() if ": " in line)
    revision = fields.get("Sail RISC-V git", "unknown commit")

    corpus = differential.load(e.root)
    records = sum(m.records for m in corpus.members)
    checks = sum(m.checks for m in corpus.members)

    # The model's own property harness, which is the other half of what "ISA tests
    # green" means here: the bundled riscv-tests went with the default data capability
    # at M0.6f, every one of its programs addressing memory through an integer base
    # register that a purecap machine faults on, so the corpus below and this harness
    # are what remains and both are this repository's own.
    harness = e.build_dir / "test" / "unit_tests" / "unit_tests"
    properties = 0
    if harness.exists():
        try:
            run = subprocess.run([str(harness)], capture_output=True, text=True,
                                 timeout=300, check=False)
        except subprocess.TimeoutExpired:
            print(f"the property harness at {harness} did not exit within 300 s",
                  file=sys.stderr)
            return 1
        properties = sum(1 for line in run.stdout.splitlines()
                         if line.startswith("Testing "))

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
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("typecheck", help="Sail typecheck only, no emission").set_defaults(
        run=cmd_typecheck)

    bundle = sub.add_parser(
        "bundle", help="regenerate the model's machine-readable bundle")
    bundle.add_argument("--check", action="store_true",
                        help="emit to a scratch path and hold the tracked bundle "
                             "against it, writing nothing")
    bundle.set_defaults(run=cmd_bundle)

    sub.add_parser("emit", help="emit C++, then validate the profile config").set_defaults(
        run=cmd_emit)

    build = sub.add_parser("build", help="configure, build, and run the bundled suite")
    build.add_argument("--fast", action="store_true",
                       help="the iterate profile: the canonical build without -g")
    build.add_argument("--background", action="store_true",
                       help="detach the run and return; wait on it with `run.py model wait`")
    build.set_defaults(run=cmd_build)

    wait = sub.add_parser("wait", help="wait for this lane's build, then report it")
    wait.add_argument("--fast", action="store_true", help="the iterate profile's build")
    wait.set_defaults(run=cmd_wait)

    sub.add_parser("lane", help="where this checkout builds, and what is building there"
                   ).set_defaults(run=cmd_lane)

    oracle = sub.add_parser("oracle",
                            help="build the M0.4 capability oracle and run its suite")
    oracle.add_argument("--resync", action="store_true",
                        help="re-copy the pinned tree before building")
    oracle.add_argument("--timeout", type=int, default=5,
                        help="seconds before a bundled test counts as failed")
    oracle.set_defaults(run=cmd_oracle)

    sweep = sub.add_parser("sweep", help="classify riscv-tests against the frozen profile")
    sweep.add_argument("--xlen", default="64")
    sweep.add_argument("--timeout", type=int, default=10,
                       help="seconds before a test is classified as a hang")
    sweep.set_defaults(run=cmd_sweep)

    td = sub.add_parser("trace-diff",
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

    cp = sub.add_parser("corpus", help="assemble and run the differential corpus")
    cp.add_argument("member", nargs="*", help="the members to run (default: all)")
    cp.add_argument("--assemble-only", action="store_true",
                    help="write the images and do not run them")
    cp.add_argument("--out", help="where to write the images")
    cp.add_argument("--refresh", action="store_true",
                    help="rewrite the manifest's record counts and trace digests")
    cp.add_argument("--timeout", type=int, default=30,
                    help="seconds before a member counts as never having reported")
    cp.set_defaults(run=cmd_corpus)

    fz = sub.add_parser("freeze-emit",
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

    asm_cmd = sub.add_parser("asm", help="assemble one dialect program")
    asm_cmd.add_argument("source")
    asm_cmd.add_argument("elf")
    asm_cmd.set_defaults(run=cmd_asm)

    sub.add_parser("reference",
                   help="print the frozen golden model's identity"
                   ).set_defaults(run=cmd_reference)
    sub.add_parser("devicetree",
                   help="generate, compile, and size-check the attested devicetree"
                   ).set_defaults(run=cmd_devicetree)
    ck = sub.add_parser("config-keys", help="compare two configurations' key sets")
    ck.add_argument("generated", type=Path)
    ck.add_argument("profile", type=Path)
    ck.set_defaults(run=cmd_config_keys)

    vc = sub.add_parser("validate-config", help="validate a config against a schema")
    vc.add_argument("schema", type=Path)
    vc.add_argument("config", type=Path)
    vc.set_defaults(run=cmd_validate_config)

    ka = sub.add_parser("keepalive", help="hold the WSL distribution up for a bounded time")
    ka.add_argument("--hours", type=int, default=env.keepalive_hours())
    ka.add_argument("--stop", action="store_true")
    ka.set_defaults(run=cmd_keepalive)

    args = parser.parse_args(argv)
    # Which subcommands answer on either lane is `cli.COMMANDS`'s and is asked rather
    # than restated: a second list here would be the two-copies defect inside the table
    # that exists to prevent it, and it would drift the first time one is added.
    hosted = next((c.host_ok for c in cli.COMMANDS if c.name == "model"), frozenset())
    needs_guest = args.command not in hosted
    e = env.load(toolchain=needs_guest)
    if args.command != "keepalive" and needs_guest:
        # every loop holds the distribution up while it runs, so a long build does not
        # lose the VM underneath it; the keepalive command manages that lease directly
        env.keepalive()
    # `set_defaults(run=...)` puts the handler on the namespace, where its type is
    # gone: named here so that the exit code this returns is checked to be one, and
    # so that a handler with the wrong shape is a finding rather than a TypeError on
    # whichever subcommand nobody ran lately.
    run = cast("Command", args.run)
    return run(e, args)

