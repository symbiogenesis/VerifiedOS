#!/usr/bin/env python3
"""The curated Sail model's build loops, from the fastest to the slowest.

Four loops, and each is the exit criterion for the one above it:

    typecheck   ~30 s    Sail reports every dangling reference a cut leaves behind
    emit        ~2 min   the full C++ emission, then the config against its schema
    build       ~15 min  emission, compile, and the bundled ctest suite
    sweep       ~1 min   the profile configuration against the downloaded riscv-tests

`typecheck` is the inner loop of a deletion batch; `build` stays the exit criterion for
every batch, and `sweep` is the number each batch reports. `trace-diff` is the M0.6e
differential rig, adjudicating the curated model against the M0.4 oracle. Two more
commands answer questions about the configuration alone and need no build:
`config-keys` and `validate-config`.

These run inside WSL, where the Sail toolchain lives:

    wsl -d Ubuntu -u root -e python3 tools/model.py build
    wsl -d Ubuntu -u root -e python3 tools/model.py sweep --xlen 64

Everything about the machine and the build trees comes from vos/env.py, which also
raises the OCaml stack the emission needs and puts the opam switch on PATH.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vos import config, env, trace            # noqa: E402

PROFILE_CONFIG = "config/verifiedos.json"
SCHEMA = "sail_riscv_config_schema.json"
EMIT_TARGET = "generated_sail_riscv_model"


def _configure(e: env.Environment, build_dir: Path,
               extra: list[str] | None = None, out=None) -> int:
    """The one cmake configure line. It was written out in two loops, which is one fact
    in two places and a pair that can silently stop agreeing."""
    return env.stage("configure", [
        "cmake", "-S", str(e.model), "-B", str(build_dir), "-GNinja",
        "-DCMAKE_BUILD_TYPE=RelWithDebInfo",
        "-DDOWNLOAD_GMP=FALSE",
        "-DENABLE_RISCV_TESTS=TRUE",
        *e.ccache, *(extra or []),
    ], stdout=out, stderr=out)


def cmd_typecheck(e: env.Environment, args) -> int:
    """Typecheck the curated model without emitting code."""
    return subprocess.run(
        ["sail", "--strict-var", "--strict-bitvector", "--strict-exponentials",
         "--memo-z3", "--memo-z3-path", str(e.typecheck_cache),
         "--just-check", "--all-modules", "riscv.sail_project"],
        cwd=e.model / "model").returncode


def cmd_emit(e: env.Environment, args) -> int:
    """Run the full C++ emission, which regenerates the config schema, then hand the
    fresh schema and the frozen profile to the validator. No C++ is compiled."""
    build_dir = e.build_dir
    if not (build_dir / "build.ninja").exists():
        if _configure(e, build_dir):
            return 1
    # a single-threaded stage; -j is passed for uniformity, not for speed
    if env.stage("emit", ["cmake", "--build", str(build_dir), "-j", str(e.jobs),
                          "--target", EMIT_TARGET]):
        return 1
    code, lines = config.validate(build_dir / SCHEMA, e.model / PROFILE_CONFIG)
    print("\n".join(lines))
    return code


def cmd_build(e: env.Environment, args) -> int:
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
    version = subprocess.run(["sail", "--version"], capture_output=True, text=True)

    # The whole run goes to one log and the console says only where it is. A build is
    # long enough to be started and left, so the caller needs a file to come back to
    # and, at the end of it, one line saying the run is over: waiting on that marker is
    # how a caller learns the build finished, rather than by guessing at a sleep.
    print(f"== log: {log}", flush=True)
    with open(log, "w", encoding="utf-8") as handle:
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


def cmd_sweep(e: env.Environment, args) -> int:
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
    tally = {"PASS": 0, "REFUSE": 0, "HANG": 0}
    for elf in sorted(suites[0].glob(f"rv{args.xlen}*-p-*")):
        if elf.suffix == ".dump":
            continue
        try:
            done = subprocess.run([str(sim), "--config", str(profile), str(elf)],
                                  capture_output=True, timeout=args.timeout)
            verdict = "PASS" if done.returncode == 0 else "REFUSE"
            detail = "" if verdict == "PASS" else f" rc={done.returncode}"
        except subprocess.TimeoutExpired:
            verdict, detail = "HANG", ""
        tally[verdict] += 1
        print(f"{verdict} {elf.name}{detail}")

    print(f"TOTAL pass={tally['PASS']} refuse={tally['REFUSE']} hang={tally['HANG']} "
          f"of {sum(tally.values())}")
    return 0


def cmd_trace_diff(e: env.Environment, args) -> int:
    """Run the curated model and the M0.4 oracle over the same programs and adjudicate
    their traces against each other.

    The two executors are the transplant's whole check until the purecap corpus of M0.12
    exists: the oracle implements the same ISAv9 capability format and the same
    capability instructions, so over a program both machines can run they must retire
    the same instructions and write the same values. The Sail model this repository
    curates is the reference on every divergence; the oracle is evidence, never
    authority.

    What the rig can and cannot say today is set by the corpus, not by the rig.
    `riscv-tests` is integer-addressed, exercises no capability instruction, and runs on
    two machines that differ in privilege modes, CSR bank, and boot path, so agreement
    over it is evidence about the *base* the transplant did not disturb and nothing
    more. The capability surface is exercised by the model's own `$[test]` properties
    until M0.12 versions programs both executors can run that use it.

    The figure each member reports is the agreeing prefix, and over `riscv-tests` it is
    bounded by the corpus rather than by the transplant. The regression is therefore
    that the prefix must not *shorten*, which --floor enforces.
    """
    if not e.simulator.exists():
        print(f"no curated simulator at {e.simulator}; run `model.py build` first",
              file=sys.stderr)
        return 1
    if not e.oracle.exists():
        print(f"no M0.4 oracle at {e.oracle}; see checklist M0.4", file=sys.stderr)
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
        if verdict.error:
            print(f"SHORT   {elf.name} ({verdict.error})")
            tally["SHORT"] += 1
            continue

        if shortest is None or verdict.prefix < shortest:
            shortest = verdict.prefix
        if verdict.prefix < args.floor:
            print(f"SHORT   {elf.name} ({verdict.line()}, below the floor of {args.floor})")
            for record in verdict.agreed or []:
                print(f"          agreed : {record}")
            print(f"          curated: {verdict.divergence[0]}")
            print(f"          oracle : {verdict.divergence[1]}")
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
    done = subprocess.run(argv, capture_output=True, text=True, errors="replace")
    return (done.stdout + done.stderr).splitlines()


def cmd_config_keys(e: env.Environment, args) -> int:
    code, lines = config.compare_keys(args.generated, args.profile)
    print("\n".join(lines))
    return code


def cmd_validate_config(e: env.Environment, args) -> int:
    code, lines = config.validate(args.schema, args.config)
    print("\n".join(lines))
    return code


def cmd_keepalive(e: env.Environment, args) -> int:
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
    return args.run(e, args)


if __name__ == "__main__":
    sys.exit(main())
