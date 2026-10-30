#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""M1.2f's two acceptance loops over the contained purecap backend.

    tools/run.py compiler-diff program --ccomp PATH (SOURCE.c ... | --generate N [--perturb]
                                       [--pattern NAME]) [--interp] [--simulator PATH | --lane]
    tools/run.py compiler-diff component (--wasm MODULE | --host-record FILE)
                                         (--c SOURCE --ccomp PATH | --elf FILE
                                          | --purecap-record FILE) [--simulator PATH | --lane]
    tools/run.py compiler-diff generate --out DIR [--count N] [--seed S] [--perturb]

**The program level** preprocesses C once with `ccomp -E`, then feeds its exact `.i`
bytes through `ccomp -S` in a fresh directory and hands the emitted
stream to the in-tree assembler ([vos/asm.py](../asm.py)) and the image composer
([vos/image.py](../image.py)) under the harness stated below, and runs the image on the
golden emulator with the invocation `run.py model corpus` makes, asking the two questions
[differential-corpus.md](../../../docs/assurance/differential-corpus.md) §6 asks of a
member: the program's own, its HTIF verdict, and the rig's, the digest of its normalized
commit trace. The compiler is never in the tree: `--ccomp` names an executable outside every
checkout, which is M1.1a's containment, and the driver records the path and the digest of
what it found there rather than carrying either. `--ccomp-arg` passes the backend's own
flags, `-fverifiedos-typed` selecting its typed purecap route. `--interp` also runs the
same frozen `.i` through the compiler's reference interpreter, and an image whose `main`
returned something else is `source-disagrees`; a narrowing program has no such reading.
Preprocessing runs beside the original source, so quoted and transitive includes retain
their meaning; its argv and working directory are recorded. The preprocessed digest
binds the effective include closure, including macro expansion, and `--against` refuses
missing or changed identities even when outputs agree. An incoming `.i`, including a
plan-bound narrowing input, is preserved byte for byte. `--keep` retains that unit.

**The generated campaign** is deterministic in its seed and stays inside the selected
scalar source profile: pointers through stack memory, struct fields and whole-struct
copies, calls in both directions, arguments past the eight argument registers, a pointer
or null chosen on a branch, more live pointers across calls than registers, and a local
array narrowed through the plan-bound `csetbounds` primitive against an independent plan
the driver writes for that program. Every expected constant is computed by the generator;
`--pattern` selects a subset. `--perturb` is its negative control: each program moves
one check's constant off by one and must fail at exactly that check.

**The refusal verdict.** A stream the dialect does not spell is scanned before it is
assembled, and every mnemonic, directive and section the assembler refuses is reported by
name and by line of the emitted stream, never as an opaque failure. Stock `ccomp -S`
writes lp64d RV64, which R-18-002 forbids as a target; `--expect-refusal` makes that
verdict the green one. A refused *mnemonic* is the backend's to close, and a refused
*directive* is the seam between CompCert's printer and the assembler's vocabulary, which
the driver reports and does not translate.

**The harness.** A stream that assembles is wrapped before it is composed: `_start` moves
the store-side root out of `c1` into the reserved `c4` and derives the stack and the
`tohost` authority from it,
the way every corpus member derives an authority (R-15-001c), installs a trap handler
through MTCC, calls `main`, and folds the return into the exit code the corpus convention
reads back: `1` for success, `(code << 1) | 1` otherwise, where a code below `0x100` is
`main`'s return masked to a byte (a nonzero return with a zero low byte reads as `0xFF`)
and a code at or above it is `0x100 | mcause` for a trap that reached the handler. The
frame `main` itself expects is the backend's. The harness supplies a bounded local stack
with store-local permission under the selected scalar convention in `purecap-abi.md`.
It is a test composition; the firmware handoff remains a separate acceptance input.

**The third reading of the trace** is M1.7's own test that a capability went through
memory rather than only through the register file: one aligned eight-byte `W` whose tag
is set, read back by an `R` at the same address with the same value and tag before any
overlapping write. It is reported beside the digest; a frame's saved return capability
satisfies it as well as a program's own pointer store does.

**The component level** holds one Gallina component's host run on the CertiCoq-to-Wasm
oracle against its purecap run under one declared output encoding: the side's exit
verdict, which is the Wasm host's process status on one side and the image's HTIF exit
code on the other, plus the SHA-256 and the length of the bytes the component emitted,
the runner's standard output on one side and the emulator's terminal log, the HTIF console,
on the other. `--c` lowers the component's C through the backend and runs it under the
component harness, which reads `main`'s result as the one boolean `run_demo.mjs` reads
from the Wasm module: it prints `true` or `false` on the HTIF console and exits 0 or 1.
Either side is written as a record that the other side's run is later held against, the
report binds the module, source, compiler, stream, image, emulator and profile by digest,
and the comparator names the first field that disagrees, or the first byte where both
sides' bytes are in hand.

**What this does not decide, stated rather than implied.** A green run says this machine,
this compiler and these programs agree; it never says a lowering is correct, R-05-023a's
instrument being deferred hardening. A component's C is a hand-written refinement of its
Gallina, so agreement is differential evidence over its battery and not a refinement
proof. Every report carries `milestone_acceptance: open`, because a report is evidence for
one run and the milestone closes on a reviewed reading of recorded runs.
"""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Final, cast

from vos import compiler_diff as cd
from vos import compiler_provenance, env
from vos import corpus as corpus_mod
from vos.cli import Table, dispatch
from vos.jsonc import Json

# How the Wasm oracle is run, relative to the repository root: the pinned Node through the
# script that verifies it, then the host that decodes one boolean (tools/wasm-oracle).
NODE_RUNNER: Final[tuple[str, ...]] = (
    "sh", "tools/wasm-oracle/node.sh", "--stack-size=10000000",
    "tools/wasm-oracle/run_demo.mjs")

# What a run's evidence is a function of, beside the compiler it was pointed at.
SOURCES: Final[tuple[str, ...]] = (
    "tools/vos/cli/compiler_diff.py", "tools/vos/compiler_diff.py", "tools/vos/asm.py", "tools/vos/image.py",
    "tools/generated/dialect-table.json", "docs/assurance/differential-corpus.md",
    "docs/implementation/contracts/purecap-abi.md", "model/model/core/cap_common.sail")

# The verdict a program can end in. Listed once, in the order the summary counts them.
VERDICTS: Final[tuple[str, ...]] = (
    "ccomp-refused", "dialect-refused", "assembled", "pass", "fail", "trap",
    "source-disagrees", "no-verdict")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sources(root: Path) -> dict[str, Json]:
    return {name: _sha256((root / name).read_bytes()) for name in SOURCES
            if (root / name).is_file()}


def _executable_identity(spelled: str) -> dict[str, Json]:
    """The compiler or emulator as the caller named it, with the digest of the file where
    the spelling is one; the digest is what a completion note quotes."""
    path = Path(spelled)
    return {"path": spelled,
            "sha256": _sha256(path.read_bytes()) if path.is_file() else None}


def _compiler_identity(spelled: str) -> dict[str, Json]:
    """Include the source build and locked native tools, or explicit receipt absence."""
    result = _executable_identity(spelled)
    provenance, files = compiler_provenance.read(Path(spelled), required=False)
    file_bindings: dict[str, Json] = {name: cast("Json", digest) for name, digest in files.items()}
    result.update({"provenance": provenance, "receipts_sha256": file_bindings})
    return result


def _require_compiler_unchanged(spelled: str, expected: dict[str, Json]) -> None:
    """Refuse persistent producer drift before publishing campaign evidence."""
    if _compiler_identity(spelled) != expected:
        raise ValueError("compiler executable, source, receipts or lock changed during campaign")


def _profile(args: argparse.Namespace, root: Path) -> Path:
    return Path(args.profile) if args.profile else root / "model" / env.PROFILE_CONFIG


def _simulator(args: argparse.Namespace) -> tuple[list[str] | None, str]:
    """The emulator to run images on, or `None` and the sentence saying what waits."""
    if args.simulator:
        return [str(args.simulator)], ""
    if args.lane:
        lane = env.load(toolchain=False).simulator
        if lane.is_file():
            return [str(lane)], ""
        return None, (f"the emulator half waits: no simulator at {lane} (this lane has "
                      f"not built; `run.py model build`)")
    return None, "the emulator half waits: pass --simulator PATH or --lane"


def _file_identity(path: Path) -> dict[str, Json]:
    return {"path": str(path),
            "sha256": _sha256(path.read_bytes()) if path.is_file() else None}


def _inputs(args: argparse.Namespace) -> list[cd.Program]:
    """The programs to run: the sources named, then the generated campaign."""
    out: list[cd.Program] = []
    for spelled in args.source:
        path = Path(spelled)
        text = path.read_text(encoding="utf-8")
        out.append(cd.Program(path.stem, "given", text, 0, source_path=path.resolve()))
    if args.generate:
        out += cd.programs(args.seed, args.generate, args.perturb, args.pattern or None)
    if len({program.name for program in out}) != len(out):
        raise ValueError("program names must be unique, including generated programs")
    return out


def _print_report(report: cd.Report) -> None:
    label = report.verdict.upper()
    print(f"{label:<16} {report.name}: {report.detail}")
    if report.compiled is not None and report.verdict != "ccomp-refused":
        print(f"{'':<16}   ccomp exited 0 with {report.compiled.lines} line(s), "
              f"sha256 {report.compiled.stream_sha256[:16]}")
    for kind, name, lines in cd.grouped(report.refusals):
        where = ", ".join(str(n) for n in lines if n) or "(the stream)"
        note = next((r.detail for r in report.refusals
                     if r.kind == kind and r.name == name and r.detail), "")
        print(f"{'':<16}   {kind:<9} {name:<16} line(s) {where}"
              + (f": {note}" if note else ""))
    if report.ran is not None:
        print(f"{'':<16}   {report.ran.records} records, digest {report.ran.digest}, "
              f"capability round trip: {'yes' if report.ran.cap_roundtrip else 'no'}")
    if report.interpreted is not None:
        print(f"{'':<16}   interpreter: main returned {report.interpreted.code}"
              + (f", expected {report.expect}" if report.expect else ""))


def _program(args: argparse.Namespace) -> int:
    root = corpus_mod.find_root()
    try:
        inputs = _inputs(args)
        compiler_identity = _compiler_identity(args.ccomp)
    except (OSError, ValueError, TypeError) as err:
        print(f"FAIL compiler-diff: unreadable input: {err}", file=sys.stderr)
        return 2
    if not inputs:
        print("nothing to compile: name a C source, or --generate N", file=sys.stderr)
        return 2
    simulator, waits = _simulator(args)
    profile = _profile(args, root)
    against: dict[str, Json] | None = None
    if args.against:
        try:
            loaded: object = json.loads(Path(args.against).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as err:
            print(f"FAIL compiler-diff: the recorded run is unreadable: {err}",
                  file=sys.stderr)
            return 2
        against = cast("dict[str, Json]", loaded) if isinstance(loaded, dict) else {}

    ccomp = [str(args.ccomp), *args.ccomp_arg]
    keep = Path(args.keep) if args.keep else None
    with tempfile.TemporaryDirectory(prefix="vos-compiler-diff-") as scratch:
        workdir = keep or Path(scratch)
        workdir.mkdir(parents=True, exist_ok=True)
        reports = [cd.run_program(program, ccomp, workdir, simulator, profile, waits,
                               compile_timeout=args.timeout, run_timeout=args.run_timeout,
                               inst_limit=args.inst_limit, interp=args.interp)
                   for program in inputs]

    try:
        _require_compiler_unchanged(args.ccomp, compiler_identity)
    except (OSError, ValueError, TypeError) as err:
        print(f"FAIL compiler-diff: {err}", file=sys.stderr)
        return 2

    differs = cd.disagreements(reports, against) if against is not None else []
    tally = {verdict: sum(1 for r in reports if r.verdict == verdict) for verdict in VERDICTS}
    closed = all(cd.as_expected(r) for r in reports) and not differs
    expected = (all(r.verdict == "dialect-refused" for r in reports) and not differs
                if args.expect_refusal else closed)

    if args.json:
        summary: dict[str, Json] = {}
        for verdict in VERDICTS:
            summary[verdict] = tally[verdict]
        recorded: Json = None if against is None else {"disagreements": list(differs)}
        payload: dict[str, Json] = {
            "scope": "program-level", "milestone_acceptance": "open",
            "sources_sha256": _sources(root),
            "ccomp": compiler_identity,
            "simulator": None if simulator is None else _executable_identity(simulator[0]),
            "profile": _file_identity(profile),
            "campaign": {"seed": args.seed, "generated": args.generate,
                         "perturb": args.perturb,
                         "patterns": cast("list[Json]", args.pattern or cd.pattern_names()),
                         "given": [p.name for p in inputs if p.pattern == "given"]},
            "interp": args.interp,
            "expect": ("refusal" if args.expect_refusal
                       else "perturbed" if args.perturb else "pass"),
            "programs": [cd.report_json(r) for r in reports],
            "summary": summary,
            "against": recorded,
            "green": expected,
        }
        print(json.dumps(payload, indent=2))
        return 0 if expected else 1

    for report in reports:
        _print_report(report)
    for line in differs:
        print(f"{'DISAGREE':<16} {line}")
    counts = " ".join(f"{verdict}={tally[verdict]}" for verdict in VERDICTS)
    print(f"TOTAL {counts} of {len(reports)}"
          + (f"; {len(differs)} disagreement(s) with the recorded run" if bool(against) else "")
          + (f"; {waits}" if simulator is None else ""))
    if closed:
        print(("every perturbed program failed at its moved check"
               if args.perturb else "every program answered both questions")
              + ("; the source interpreter agreed with every image" if args.interp else "")
              + "; a run is evidence for this campaign and decides no milestone alone")
    elif args.expect_refusal:
        print("the refusal is the expected verdict ahead of the backend (R-18-002): "
              + ("every stream was refused" if expected
                 else "the refusals or the recorded comparison did not meet the expectation"))
    else:
        print("the acceptance loop is open: not every program ended where its source says")
    return 0 if expected else 1


def _component(args: argparse.Namespace) -> int:
    root = corpus_mod.find_root()
    host: cd.Output | None = None
    purecap: cd.Output | None = None
    host_bytes: bytes | None = None
    purecap_bytes: bytes | None = None
    bindings: dict[str, Json] = {}
    interpreted: cd.Interpreted | None = None
    simulator: list[str] | None = None
    compiler_identity: dict[str, Json] | None = None
    if args.c and not args.purecap_record:
        simulator, waits = _simulator(args)
        refused = ("--c needs --ccomp, the contained compiler" if not args.ccomp
                   else waits if simulator is None else "")
        if refused:
            print(f"FAIL compiler-diff component: {refused}", file=sys.stderr)
            return 2
    try:
        if args.host_record:
            host = cd.read_output(Path(args.host_record), "wasm-host")
        elif args.wasm:
            runner = list(args.runner) if args.runner else list(NODE_RUNNER)
            bindings["wasm_module"] = _file_identity(Path(args.wasm))
            host, host_bytes = cd.wasm_output(Path(args.wasm), runner, root, args.timeout)
        if args.purecap_record:
            purecap = cd.read_output(Path(args.purecap_record), "purecap")
        elif args.c and simulator is not None:
            source, profile = Path(args.c), _profile(args, root)
            ccomp = [str(args.ccomp), *args.ccomp_arg]
            compiler_identity = _compiler_identity(args.ccomp)
            with tempfile.TemporaryDirectory(prefix="vos-compiler-diff-") as scratch:
                workdir = Path(args.keep) if args.keep else Path(scratch)
                workdir.mkdir(parents=True, exist_ok=True)
                lowered, elf = cd.lower_component(source, ccomp, workdir, args.compile_timeout)
                if elf is None:
                    stage = (f"ccomp exited {lowered.compiled.exit_code}: "
                             f"{lowered.compiled.said}" if lowered.compiled.stream is None
                             else "the assembler refused " + "; ".join(
                                 f"{r.kind} {r.name} line {r.line}" for r in lowered.refusals))
                    purecap = cd.output_of("purecap", None, b"", f"lowering stopped: {stage}")
                else:
                    purecap, purecap_bytes = cd.purecap_output(
                        elf, simulator, profile, workdir, args.timeout, args.inst_limit)
                if args.interp and lowered.compiled.stream is not None:
                    interpreted = cd.interpret_c(ccomp, lowered.compiled.preprocessed.path,
                                              workdir / f"{source.stem}.interp",
                                              args.compile_timeout,
                                              expected_sha256=lowered.compiled.preprocessed.sha256)
            bindings.update({
                "c_source": {"path": str(source),
                             "sha256": lowered.compiled.preprocessed.source_sha256 or None},
                "ccomp": compiler_identity,
                "ccomp_args": list(args.ccomp_arg),
                "compilation": cd.compiled_json(lowered.compiled),
                "stream_sha256": lowered.compiled.stream_sha256 or None,
                "refusals": [cd.refusal_json(r) for r in lowered.refusals],
                "elf_sha256": lowered.elf_sha256,
                "simulator": _executable_identity(simulator[0]),
                "profile": _file_identity(profile),
            })
        elif args.elf and args.simulator:
            with tempfile.TemporaryDirectory(prefix="vos-compiler-diff-") as scratch:
                purecap, purecap_bytes = cd.purecap_output(
                    Path(args.elf), [str(args.simulator)], _profile(args, root),
                    Path(scratch), args.timeout, args.inst_limit)
        if compiler_identity is not None:
            _require_compiler_unchanged(args.ccomp, compiler_identity)
    except (OSError, ValueError, TypeError) as err:
        # `json.JSONDecodeError` is a `ValueError`, so a record that is not JSON at all
        # is refused by the same arm as one whose fields are wrong
        print(f"FAIL compiler-diff component: {err}", file=sys.stderr)
        return 2
    if host is None and purecap is None:
        print("nothing to compare: name a Wasm module or a host record, and a C source or "
              "an image with a simulator, or a purecap record", file=sys.stderr)
        return 2

    for spelled, side in ((args.write_host, host), (args.write_purecap, purecap)):
        if spelled and side is not None:
            Path(spelled).write_text(json.dumps(side.to_json(), indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    verdict = (cd.compare_outputs(host, purecap, host_bytes, purecap_bytes)
               if host is not None and purecap is not None else None)
    incomplete = any(side is not None and side.verdict is None for side in (host, purecap))
    # The interpreter's reading of the same C, as the harness would print it: 0 is true.
    source_verdict = (None if interpreted is None or interpreted.code is None
                      else 0 if interpreted.code == 0 else 1)
    source_differs = interpreted is not None and (
        purecap is None or source_verdict is None or source_verdict != purecap.verdict)
    if interpreted is not None:
        bindings["interp"] = {"argv": list(interpreted.argv), "exit": interpreted.exit_code,
                              "code": interpreted.code, "verdict": source_verdict}
    failed = verdict is not None or incomplete or source_differs

    if args.json:
        payload: dict[str, Json] = {
            "scope": "component-level", "milestone_acceptance": "open",
            "encoding": cd.ENCODING, "sources_sha256": _sources(root),
            "bindings": bindings,
            "host": None if host is None else host.to_json(),
            "purecap": None if purecap is None else purecap.to_json(),
            "compared": host is not None and purecap is not None,
            "disagreement": None if verdict is None else verdict.line(),
            "source_disagrees": source_differs,
        }
        print(json.dumps(payload, indent=2))
        return 1 if failed else 0

    for side in (host, purecap):
        if side is not None:
            print(f"{side.side.upper():<9} verdict {side.verdict}, {side.output_length} "
                  f"byte(s), sha256 {side.output_sha256[:16]}, head {side.output_head!r}")
            print(f"{'':<9} produced by: {side.produced_by}")
    for key in ("wasm_module", "c_source", "ccomp", "simulator", "profile"):
        if isinstance(bindings.get(key), dict):
            bound = cast("dict[str, Json]", bindings[key])
            print(f"{'BOUND':<9} {key} {bound.get('path')} sha256 {bound.get('sha256')}")
    for key in ("stream_sha256", "elf_sha256"):
        if key in bindings:
            print(f"{'BOUND':<9} {key} {bindings[key]}")
    if interpreted is not None:
        print(f"{'SOURCE':<9} the interpreter reports main returned {interpreted.code}"
              + (": it disagrees with the image" if source_differs else ""))
    if host is None or purecap is None:
        if incomplete:
            print("FAIL      the requested side did not produce an exit verdict")
            return 1
        missing = "purecap" if purecap is None else "host"
        print(f"WAITS     the {missing} side: no record and no run was named for it")
        return 1 if source_differs else 0
    if verdict is None and not source_differs:
        print(f"AGREE     both sides under {cd.ENCODING}: verdict {host.verdict} and "
              f"{host.output_length} byte(s)")
        return 0
    if verdict is not None:
        print(f"DISAGREE  {verdict.line()}")
    return 1


def _generate(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows: list[Json] = []
    try:
        generated = cd.programs(args.seed, args.count, args.perturb, args.pattern or None)
    except ValueError as err:
        print(f"FAIL compiler-diff generate: {err}", file=sys.stderr)
        return 2
    for program in generated:
        path = out / f"{program.name}.c"
        path.write_text(program.source, encoding="utf-8", newline="\n")
        rows.append({"name": program.name, "pattern": program.pattern,
                     "checks": program.checks, "expect": program.expect,
                     "sha256": _sha256(path.read_bytes())})
        print(f"WROTE   {path} ({program.pattern}, {program.checks} checks)")
    manifest: dict[str, Json] = {"seed": args.seed, "count": args.count,
                                 "perturb": args.perturb,
                                 "patterns": cast("list[Json]", args.pattern or cd.pattern_names()),
                                 "programs": rows}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                       encoding="utf-8", newline="\n")
    print(f"TOTAL   {len(rows)} program(s) from seed {args.seed}, FP-free, over "
          f"{len(cd.PATTERNS)} pattern(s); a failure names its check through main's return")
    return 0


def _flags(name: str, sub: argparse.ArgumentParser) -> None:
    if name == "program":
        sub.add_argument("source", nargs="*", help="C sources to feed through the loop")
        sub.add_argument("--ccomp", required=True, metavar="PATH",
                         help="the contained ccomp executable, outside every checkout")
        sub.add_argument("--generate", type=int, default=0, metavar="N",
                         help="also run N generated programs (see `generate`)")
        sub.add_argument("--seed", type=int, default=1, help="the generator's seed")
        sub.add_argument("--perturb", action="store_true",
                         help="the negative control: each generated program moves one "
                              "check's constant and must fail at that check")
        sub.add_argument("--pattern", action="append", default=[], metavar="NAME",
                         help="generate only this pattern (repeatable; default: all)")
        sub.add_argument("--against", metavar="FILE",
                         help="a --json report of an earlier run to hold this one against")
        sub.add_argument("--expect-refusal", action="store_true",
                         help="green iff every stream is refused by the dialect")
        sub.add_argument("--timeout", type=int, default=cd.COMPILE_TIMEOUT,
                         help="seconds the compiler gets per program")
        sub.add_argument("--run-timeout", type=int, default=cd.RUN_TIMEOUT,
                         help="seconds the emulator gets per image")
    if name == "component":
        sub.add_argument("--wasm", metavar="MODULE", help="a module the oracle compiled")
        sub.add_argument("--runner", action="append", metavar="ARG",
                         help="the Wasm host's argv, one argument per flag (default: "
                              "the pinned Node through tools/wasm-oracle)")
        sub.add_argument("--host-record", metavar="FILE", help="the host side, recorded")
        sub.add_argument("--c", metavar="SOURCE",
                         help="the component's C, lowered through --ccomp and run under "
                              "the component harness")
        sub.add_argument("--ccomp", metavar="PATH",
                         help="the contained ccomp executable, outside every checkout")
        sub.add_argument("--elf", metavar="FILE", help="the component's lowered image")
        sub.add_argument("--purecap-record", metavar="FILE",
                         help="the purecap side, recorded")
        sub.add_argument("--write-host", metavar="FILE", help="record the host side here")
        sub.add_argument("--write-purecap", metavar="FILE",
                         help="record the purecap side here")
        sub.add_argument("--timeout", type=int, default=cd.RUN_TIMEOUT,
                         help="seconds either side gets to run")
        sub.add_argument("--compile-timeout", type=int, default=cd.COMPILE_TIMEOUT,
                         help="seconds the compiler and its interpreter get")
    if name in ("program", "component"):
        sub.add_argument("--ccomp-arg", action="append", default=[], metavar="ARG",
                         help="pass one compiler argument unchanged (repeatable; use "
                              "--ccomp-arg=-flag for an option)")
        sub.add_argument("--interp", action="store_true",
                         help="also run the source through the same compiler's -interp "
                              "and require the image to agree with it")
        sub.add_argument("--keep", metavar="DIR",
                         help="keep the streams and images here rather than in scratch")
        sub.add_argument("--simulator", metavar="PATH",
                         help="the golden emulator, a lane's c_emulator/sail_riscv_sim")
        sub.add_argument("--lane", action="store_true",
                         help="use this checkout's own lane's simulator (guest only)")
        sub.add_argument("--profile", metavar="FILE",
                         help=f"the configuration (default: model/{env.PROFILE_CONFIG})")
        sub.add_argument("--inst-limit", type=int, default=cd.INST_LIMIT,
                         help="the emulator's instruction bound per run")
        sub.add_argument("--json", action="store_true",
                         help="emit the report as one JSON object")
    if name == "generate":
        sub.add_argument("--out", required=True, metavar="DIR", help="where to write them")
        sub.add_argument("--count", type=int, default=6, help="how many programs")
        sub.add_argument("--seed", type=int, default=1, help="the generator's seed")
        sub.add_argument("--perturb", action="store_true",
                         help="write the negative-control twins instead")
        sub.add_argument("--pattern", action="append", default=[], metavar="NAME",
                         help="generate only this pattern (repeatable; default: all)")


TABLE: Table = {
    "program": (_program, "C through ccomp, the assembler, the composer and the emulator"),
    "component": (_component, "one Gallina component's Wasm-host run against its "
                              "purecap run, under the declared output encoding"),
    "generate": (_generate, "write the deterministic FP-free C campaign"),
}


def main(argv: list[str] | None = None) -> int:
    return dispatch(__doc__, TABLE, argv, _flags, prog="run.py compiler-diff")
