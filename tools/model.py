#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The curated Sail model's build loops, from the fastest to the slowest.

Four loops, and each is the exit criterion for the one above it:

    typecheck   ~30 s    Sail reports every dangling reference a cut leaves behind
    emit        ~2 min   the full C++ emission, then the config against its schema
    build       ~15 min  emission, compile, and the bundled ctest suite
    sweep       ~1 min   the profile configuration against the downloaded riscv-tests

`typecheck` is the inner loop of a deletion batch; `build` stays the exit criterion for
every batch, and `sweep` is the number each batch reports. `trace-diff` is the M0.6e
differential rig, adjudicating the curated model against the M0.4 oracle, and `oracle`
builds that reference. Two more commands answer questions about the configuration alone
and need no build: `config-keys` and `validate-config`.

These run inside WSL, where the Sail toolchain lives:

    wsl -u root -e python3 tools/model.py build
    wsl -u root -e python3 tools/model.py sweep --xlen 64

Everything about the machine and the build trees comes from vos/env.py, which also
raises the OCaml stack the emission needs and puts the opam switch on PATH.
"""

import argparse
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import IO

# The tools import `vos` without being installed, so each puts its own directory on
# the path first. Every import below this line is deliberately not at the top.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vos import config, differential, env, trace

# What every subcommand handler is. `main` attaches one to each subparser and
# `argparse` hands it back as an untyped attribute, so the shape is stated once
# here and asserted at the single point it is called.
type Command = Callable[[env.Environment, argparse.Namespace], int]

PROFILE_CONFIG = "config/verifiedos.json"
SCHEMA = "sail_riscv_config_schema.json"
EMIT_TARGET = "generated_sail_riscv_model"

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
    in two places and a pair that can silently stop agreeing."""
    return env.stage("configure", [
        "cmake", "-S", str(e.model), "-B", str(build_dir), "-GNinja",
        "-DCMAKE_BUILD_TYPE=RelWithDebInfo",
        "-DDOWNLOAD_GMP=FALSE",
        "-DENABLE_RISCV_TESTS=TRUE",
        *e.ccache, *(extra or []),
    ], stdout=out, stderr=out)


def cmd_typecheck(e: env.Environment, args: argparse.Namespace) -> int:
    """Typecheck the curated model without emitting code."""
    return subprocess.run(
        ["sail", "--strict-var", "--strict-bitvector", "--strict-exponentials",
         "--memo-z3", "--memo-z3-path", str(e.typecheck_cache),
         "--just-check", "--all-modules", "riscv.sail_project"],
        cwd=e.model / "model", check=False).returncode


def cmd_emit(e: env.Environment, args: argparse.Namespace) -> int:
    """Run the full C++ emission, which regenerates the config schema, then hand the
    fresh schema and the frozen profile to the validator. No C++ is compiled."""
    build_dir = e.build_dir
    if not (build_dir / "build.ninja").exists() and _configure(e, build_dir):
        return 1
    # a single-threaded stage; -j is passed for uniformity, not for speed
    if env.stage("emit", ["cmake", "--build", str(build_dir), "-j", str(e.jobs),
                          "--target", EMIT_TARGET]):
        return 1
    code, lines = config.validate(build_dir / SCHEMA, e.model / PROFILE_CONFIG)
    print("\n".join(lines))
    return code


def cmd_build(e: env.Environment, args: argparse.Namespace) -> int:
    """Build the curated model out of tree and run its bundled suite.

    --fast selects the iterate profile: a separate build dir whose only divergence from
    the canonical build is dropping `-g` from RelWithDebInfo. Debug info on the
    machine-generated translation unit is the single largest compile cost (314 s against
    239 s, both measured in-build and so under N-way contention; alone the -O2 -g compile
    is 150 s wall, 136 s CPU, 1.43 GB peak) and is never used; optimization level,
    assertions, and the test suite are identical. The canonical build remains the exit
    criterion for every batch.
    """
    canonical = e.build_dir
    if args.fast:
        build_dir = e.fast_build_dir
        log = e.log_dir / "model-build-fast.log"
        extra = ["-DCMAKE_CXX_FLAGS_RELWITHDEBINFO=-O2 -DNDEBUG",
                 "-DCMAKE_C_FLAGS_RELWITHDEBINFO=-O2 -DNDEBUG"]
        _seed_from_canonical(canonical, build_dir)
    else:
        build_dir, log, extra = canonical, e.log_dir / "model-build.log", []

    e.log_dir.mkdir(parents=True, exist_ok=True)
    version = subprocess.run(["sail", "--version"], capture_output=True, text=True, check=False)

    # The whole run goes to one log and the console says only where it is. A build is
    # long enough to be started and left, so the caller needs a file to come back to
    # and, at the end of it, one line saying the run is over: waiting on that marker is
    # how a caller learns the build finished, rather than by guessing at a sleep.
    print(f"== log: {log}", flush=True)
    with log.open("w", encoding="utf-8") as handle:
        handle.write(f"== sail: {version.stdout.strip()}\n")
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


def _seed_from_canonical(canonical: Path, fast: Path) -> None:
    """Seed the fast tree from the canonical one so its first configure pays neither
    cost twice.

    The pre-downloaded test ELFs would otherwise re-download the tarball. The Sail SMT
    memo cache matters more: a cold cache re-discharges every Z3 obligation and turns
    the ~2 min emission into ~25 min (measured once). The cache is content-keyed, so a
    stale copy only costs misses.
    """
    for source, target in ((canonical / "model" / "sail_smt_cache",
                            fast / "model" / "sail_smt_cache"),):
        if source.exists() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    tests = canonical / "test"
    if tests.is_dir():
        for downloaded in tests.iterdir():
            target = fast / "test" / downloaded.name
            if downloaded.is_dir() and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(downloaded, target)


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
    src = e.root / ORACLE_SRC
    if not (src / "Makefile").is_file():
        print(f"no oracle source at {src}; the submodule is not checked out",
              file=sys.stderr)
        return 1

    tree = e.oracle_root
    e.log_dir.mkdir(parents=True, exist_ok=True)
    log = e.log_dir / "oracle-build.log"
    version = subprocess.run(["sail", "--version"], capture_output=True, text=True, check=False)

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
    build_dir = e.build_dir
    sim = build_dir / "c_emulator" / "sail_riscv_sim"
    if not sim.exists():
        print(f"no simulator at {sim}; run `model.py build` first", file=sys.stderr)
        return 1
    suites = sorted(build_dir.glob("test/*/riscv-tests"))
    if not suites:
        print(f"no downloaded riscv-tests under {build_dir}/test", file=sys.stderr)
        return 1

    profile = e.model / PROFILE_CONFIG
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
    the frozen profile is M2's CHERI-QEMU fork, and its corpus is M0.12's purecap
    programs.

    Over `riscv-tests` the two part company inside the test prologue, at the first load
    through an integer base register, which a purecap machine reads as an untagged
    capability and faults on; the prefix is therefore bounded by the corpus rather than
    by either model. The regression is that the prefix must not *shorten*, which
    --floor enforces.
    """
    if not e.simulator.exists():
        print(f"no curated simulator at {e.simulator}; run `model.py build` first",
              file=sys.stderr)
        return 1
    if not e.oracle.exists():
        print(f"no M0.4 oracle at {e.oracle}; run `model.py oracle` first",
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

    profile = e.model / PROFILE_CONFIG
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
        curated = trace.normalize(_run_trace(
            [str(e.simulator), "--config", str(profile), "--trace-instr", "--trace-gpr",
             "--trace-mem", "--inst-limit", str(args.limit), str(elf)]), "curated")
        if not curated:
            # the profile refuses the program outright, which `model.py sweep` already
            # classifies; there is no trace to adjudicate
            print(f"SKIP    {elf.name} (curated model retired nothing)")
            tally["SKIP"] += 1
            continue

        oracle = trace.normalize(_run_trace(
            [str(e.oracle), "-v", "-l", str(args.limit), str(elf)]), "oracle")
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


def _run_trace(argv: list[str]) -> list[str]:
    """Both executors print their trace to stdout and their diagnostics to stderr, and
    the normalizer reads either, so the two are merged as the shell rig merged them."""
    done = subprocess.run(argv, capture_output=True, text=True, errors="replace", check=False)
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
    out_dir = Path(args.out) if args.out else e.build_root / "corpus"
    wanted = set(args.member)
    members = [m for m in corpus.members if not wanted or m.name in wanted]
    if wanted - {m.name for m in members}:
        print(f"no such member: {', '.join(sorted(wanted - {m.name for m in members}))}",
              file=sys.stderr)
        return 1

    profile = e.model / PROFILE_CONFIG
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
    if not e.simulator.exists():
        return "FAIL", f" (no simulator at {e.simulator}; run `model.py build` first)", None
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
    from vos import asm
    try:
        size = asm.assemble_file(Path(args.source), Path(args.elf))
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"ok {args.elf}: {size} bytes")
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

    sub.add_parser("emit", help="emit C++, then validate the profile config").set_defaults(
        run=cmd_emit)

    build = sub.add_parser("build", help="configure, build, and run the bundled suite")
    build.add_argument("--fast", action="store_true",
                       help="the iterate profile: the canonical build without -g")
    build.set_defaults(run=cmd_build)

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

    asm_cmd = sub.add_parser("asm", help="assemble one dialect program")
    asm_cmd.add_argument("source")
    asm_cmd.add_argument("elf")
    asm_cmd.set_defaults(run=cmd_asm)

    ck = sub.add_parser("config-keys", help="compare two configurations' key sets")
    ck.add_argument("generated", type=Path)
    ck.add_argument("profile", type=Path)
    ck.set_defaults(run=cmd_config_keys)

    vc = sub.add_parser("validate-config", help="validate a config against a schema")
    vc.add_argument("schema", type=Path)
    vc.add_argument("config", type=Path)
    vc.set_defaults(run=cmd_validate_config)

    ka = sub.add_parser("keepalive", help="hold the WSL distribution up for a bounded time")
    ka.add_argument("--hours", type=int, default=env.KEEPALIVE_HOURS)
    ka.add_argument("--stop", action="store_true")
    ka.set_defaults(run=cmd_keepalive)

    args = parser.parse_args(argv)
    e = env.load()
    if args.command != "keepalive":
        # every loop holds the distribution up while it runs, so a long build does not
        # lose the VM underneath it; the keepalive command manages that lease directly
        env.keepalive()
    # `set_defaults(run=...)` puts the handler on the namespace, where its type is
    # gone: named here so that the exit code this returns is checked to be one, and
    # so that a handler with the wrong shape is a finding rather than a TypeError on
    # whichever subcommand nobody ran lately.
    run: Command = args.run
    return run(e, args)


if __name__ == "__main__":
    sys.exit(main())
