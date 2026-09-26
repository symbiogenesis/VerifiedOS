# SPDX-License-Identifier: Apache-2.0
"""Bounded supervisor C compared by conversion with SupervisionTree.v.

The native harness computes answers. Those answers become equality examples over
the shipped Gallina definitions, compiled with the locked proof switch. Python
generates inputs and syntax; it does not compute the reference answers. This is
focused differential evidence, not proof-gate or target acceptance.
"""

import hashlib
import itertools
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from vos import env, gallina

DETECTORS: Final = (
    "PoolLow", "PoolExhausted", "OldestWaiterPastBound", "QuarantineBacklogPastBound",
    "ReleaseMissedDeadline", "RestartRatePastBound", "PopulationCeilingReached",
    "CheckpointSpaceUnavailable",
)
ACTIONS: Final = (
    "RefuseTheNewRequest", "ShedOwnerLocalState", "SuspendNamedTenant",
    "CheckpointAndTerminateNamedTenant", "TerminateOwnershipClosedGroup",
    "StepDownPopulationRung", "DisableNonessentialService", "RestartOwningSubtree",
    "FailStopOwningSubsystem", "EscalateToRotReset",
)
SOURCES: Final = ("src/supervisor.c", "src/manifest.c", "src/effects.c",
                  "test/host.c", "test/effects.c")
KERNEL_SOURCES: Final = ("src/context.c",)
KERNEL_HEADERS: Final = ("include/vos_kernel.h", "include/vos_platform.h")
CFLAGS: Final = ("-std=c11", "-O1", "-Wall", "-Wextra", "-Werror", "-pedantic")
WAITS: Final = ("Host C/reference agreement only; M1.2f's accepted backend, M4.4's "
               "kernel effect bindings and M7.1a's target boot remain open.")


@dataclass(frozen=True)
class Comparison:
    """One C input and corresponding Gallina expressions with result kinds."""

    inputs: tuple[int, ...]
    expressions: tuple[str, ...]
    kinds: tuple[str, ...]


def nat_list(values: tuple[int, ...]) -> str:
    text = "nil"
    for value in reversed(values):
        text = f"(cons {value} {text})"
    return text


def generated() -> list[Comparison]:
    """Generate start weakenings, detector boundaries, declared states and edges."""
    order = tuple(range(5))
    orders = [order]
    orders.extend((*order[:i], order[i + 1], order[i], *order[i + 2:]) for i in range(4))
    orders += [order[:i] + order[i + 1:] for i in range(5)]
    orders += [order[i:] for i in range(1, 6)]
    orders += [(*order[:i], 0, *order[i:]) for i in range(6)]
    orders += [(0, 1, 2, 3, 5), (5, *order)]
    cases = [Comparison((0, len(values), *values),
                        (f"bringup_ok demo {nat_list(values)}",), ("bool",))
             for values in orders]
    states = [(detector, signal, 0, 0, 2, 0)
              for detector in range(8) for signal in range(6)]
    states += [(index % 8, 3, attempts, interventions, dwell, boots)
               for index, (attempts, interventions, dwell, boots)
               in enumerate(itertools.product(range(7), range(5), range(4), range(4)))]
    for detector, signal, attempts, interventions, dwell, boots in states:
        state = f"(declared_at {attempts} {interventions} {dwell} {boots})"
        cases.append(Comparison(
            (1, detector, signal, attempts, interventions, dwell, boots),
            (f"spec_detect demo (fun _ => {signal}) {DETECTORS[detector]}",
             f"spec_admits demo {state}",
             f"spec_limiter demo {state} (demo_respond {DETECTORS[detector]})",
             f"spec_backoff demo {attempts}", f"spec_boot_admit demo {state}"),
            ("bool", "bool", "action", "nat", "bool")))
    cases += [Comparison((2, u, v), (f"spec_regrant demo {u} {v}",), ("bool",))
              for u in range(5) for v in range(5)]
    return cases


def comparison_source(cases: list[Comparison], output: str) -> str:
    """Refuse missing/extra/malformed answers; bind each to its Gallina expression."""
    rows = output.splitlines()
    if len(rows) != len(cases) or not cases:
        raise ValueError("C answer count differs from the nonempty generated input set")
    source = ["(* SPDX-License-Identifier: Apache-2.0 *)",
              "Require Import SupervisionTree."]
    for i, (case, row) in enumerate(zip(cases, rows, strict=True)):
        fields = row.split()
        if len(fields) != len(case.expressions) or len(case.kinds) != len(case.expressions):
            raise ValueError(f"wrong column count at C answer {i}")
        for j, (field, expression, kind) in enumerate(
                zip(fields, case.expressions, case.kinds, strict=True)):
            if not field.isascii() or not field.isdecimal():
                raise ValueError(f"non-natural C answer {i} column {j}")
            value = int(field)
            if kind == "bool" and value <= 1:
                rendered = "true" if value else "false"
            elif kind == "action" and value < len(ACTIONS):
                rendered = ACTIONS[value]
            elif kind == "nat" and value <= 100:
                # A bounded test domain keeps accidental huge unary terms out.
                rendered = str(value)
            else:
                raise ValueError(f"out-of-domain C answer {i} column {j}")
            source.append(f"Example comparison_{i}_{j} : ({expression}) = {rendered} := eq_refl.")
    return "\n".join(source) + "\n"


def c_compiler() -> str | None:
    return shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")


def build_host(source: Path, binary: Path, compiler: str) -> subprocess.CompletedProcess[str]:
    binary.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [compiler, *CFLAGS, "-I", str(source / "include"),
         "-I", str(source.parent / "kernel" / "include"),
         *(str(source / name) for name in SOURCES),
         *(str(source.parent / "kernel" / name) for name in KERNEL_SOURCES),
         "-o", str(binary)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60, check=False)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root: Path, work: Path) -> tuple[int, list[str]]:
    """Run one focused native/reference comparison, retaining artifacts in its lane."""
    work.mkdir(parents=True, exist_ok=True)
    logs = env.log_root() / env.lane_of(root) / "supervisor"
    logs.mkdir(parents=True, exist_ok=True)
    # A failed rerun must not leave yesterday's passing receipt in this slot.
    (work / "report.json").write_text(
        json.dumps({"schema": 1, "comparison": "incomplete", "milestone_acceptance": "open"})
        + "\n", encoding="utf-8", newline="")
    out = ["== executable supervisor host core"]
    compiler = c_compiler()
    found = gallina.prover(env.ROCQ_SWITCH)
    if compiler is None or found is None:
        return 1, [f"FAIL requires native C compiler and locked switch {env.ROCQ_SWITCH}", WAITS]
    identities = [root / "proofs" / "SupervisionTree.v",
                  root / "tools" / "vos" / "supervisor.py",
                  root / "supervisor" / "include" / "vos_supervisor.h",
                  root / "supervisor" / "include" / "vos_supervisor_effects.h",
                  *(root / "kernel" / name for name in (*KERNEL_SOURCES, *KERNEL_HEADERS)),
                  *(root / "supervisor" / name for name in SOURCES)]
    inputs_before = {path.relative_to(root).as_posix(): _digest(path) for path in identities}
    compiler_before = _digest(Path(compiler))
    prover_before = _digest(Path(found.argv[0]))
    binary = work / "supervisor-host"
    built = build_host(root / "supervisor", binary, compiler)
    (logs / "compile.log").write_text(built.stdout + built.stderr, encoding="utf-8", newline="")
    if built.returncode:
        return 1, ["FAIL supervisor C compile", built.stderr, WAITS]
    controls = subprocess.run([str(binary), "controls"], capture_output=True,
                              text=True, encoding="utf-8", timeout=60, check=False)
    (logs / "controls.log").write_text(controls.stdout + controls.stderr,
                                       encoding="utf-8", newline="")
    if controls.returncode:
        return 1, ["FAIL fixed consumer controls", controls.stderr, WAITS]
    out.append(controls.stderr.strip())
    cases = generated()
    inputs = "\n".join(" ".join(map(str, case.inputs)) for case in cases) + "\n"
    (work / "inputs.txt").write_text(inputs, encoding="utf-8", newline="")
    answers = subprocess.run([str(binary)], input=inputs, capture_output=True,
                             text=True, encoding="utf-8", timeout=60, check=False)
    (work / "answers.txt").write_text(answers.stdout, encoding="utf-8", newline="")
    if answers.returncode:
        return 1, ["FAIL C input/answer harness", answers.stderr, WAITS]
    try:
        source = comparison_source(cases, answers.stdout)
    except ValueError as error:
        return 1, [f"FAIL {error}", WAITS]
    # Fresh temporary child prevents stale .vo reuse without deleting an old run.
    with tempfile.TemporaryDirectory(prefix="comparison-", dir=work) as temporary:
        scratch = Path(temporary)
        (scratch / "proofs").mkdir()
        (scratch / "harness").mkdir()
        reference = scratch / "proofs" / "SupervisionTree.v"
        shutil.copyfile(root / "proofs" / "SupervisionTree.v", reference)
        harness = scratch / "harness" / "SupervisorComparison.v"
        harness.write_text(source, encoding="utf-8", newline="")
        shutil.copyfile(harness, work / harness.name)
        for artifact in (reference, harness):
            compiled = gallina.compile_one(found, scratch, artifact)
            (logs / f"{artifact.stem}.log").write_text(
                compiled.stdout + compiled.stderr, encoding="utf-8", newline="")
            if compiled.returncode:
                return 1, [f"FAIL locked Gallina comparison at {artifact.name}",
                           compiled.stderr, WAITS]
    if (inputs_before != {path.relative_to(root).as_posix(): _digest(path) for path in identities}
            or compiler_before != _digest(Path(compiler))
            or prover_before != _digest(Path(found.argv[0]))):
        return 1, ["FAIL source or tool bytes changed during the comparison", WAITS]
    report = {
        "schema": 1, "comparison": "passed", "milestone_acceptance": "open",
        "cases": len(cases), "equalities": sum(len(case.expressions) for case in cases),
        "prover": gallina.version(found), "prover_sha256": prover_before,
        "compiler": compiler, "compiler_sha256": compiler_before, "cflags": CFLAGS,
        "inputs": inputs_before, "logs": str(logs),
        "binary_sha256": _digest(binary), "answers_sha256": _digest(work / "answers.txt"),
        "effect_controls": controls.stderr.strip(),
        "comparison_sha256": _digest(work / "SupervisorComparison.v"),
        "limits": WAITS,
    }
    (work / "report.json").write_text(json.dumps(report, indent=2) + "\n",
                                      encoding="utf-8", newline="")
    out += [f"ok locked Gallina conversion agrees with {len(cases)} generated C answers "
            f"({report['equalities']} equalities)", f"report: {work / 'report.json'}",
            f"logs: {logs}", WAITS]
    return 0, out
