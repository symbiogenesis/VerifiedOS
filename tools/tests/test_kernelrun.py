# SPDX-License-Identifier: Apache-2.0
"""The M4.4 trace reader: a correct run passes and each refuting construction fails.

The reader's agreement with KernelInstance.v over generated traces is `run.py kernel
check`'s, in the guest. These cases hold what the host can decide without a prover:
the three refuting constructions PartitionContext.v names are refused by the switch
clause, the other clauses refuse their own constructions, the vector reading reports a
flipped verdict rather than absorbing it, the authored mutant tables still seed, and a
C mutant's kill is credited to the kind of expectation that decided it.
"""

import shutil
import tempfile
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import kernelrun as k
from vos.cli import kernel as cli_kernel

SWITCH = k.Extent(10, 20)
RESTORE = k.Extent(14, 20)
T0, T1, T2 = k.Extent(30, 40), k.Extent(50, 60), k.Extent(70, 80)
FRAME = k.Frame((T0, T1, T2), reserved=1)
ROSTER = (k.CsrRow(0, True, False), k.CsrRow(1, True, True), k.CsrRow(2, False, False))
SUCC = k.Image(tuple((r * 3 + 1, r % 2 == 1) for r in range(32)), {0: 11, 1: 12, 2: 13})
ATTEMPTS = (k.Attempt(0x100, 8, "R"), k.Attempt(0x104, 9, "W0"))


def i(pc: int) -> str:
    return f"I {pc:016X} 00000000"


def x(reg: int, tag: bool, value: int) -> str:
    return f"X {reg} {int(tag)} {value:016X}"


def c(csr: int, value: int) -> str:
    return f"C {csr:03X} {value:016X}"


def records(lines: list[str]) -> list[k.Record]:
    return k.parse_records(lines)


def burst(skip_register: int = 0, tagless: int = 0, low_only: bool = False,
          omit_csr: int | None = None) -> list[str]:
    out: list[str] = []
    for r in range(1, 32):
        if r == skip_register or (low_only and r >= 16):
            continue
        value, tag = SUCC.registers[r]
        out.append(x(r, tag and r != tagless, value))
    out.extend(c(row.csr, 0 if row.zeroized else SUCC.csrs[row.csr])
               for row in ROSTER if row.nameable and row.csr != omit_csr)
    return out


def confinement(kept: int | None = None) -> list[str]:
    return [i(0x100), x(8, kept == 0, 7), i(0x104), x(9, kept == 1, 7)]


def frame_trace(order: tuple[k.Extent, ...] = (T0, T1, T2)) -> list[str]:
    out: list[str] = []
    for n, extent in enumerate(order):
        out += [i(SWITCH.base + n), i(extent.base), i(extent.base + 4)]
    return out


def verdict(conf: list[str], b: list[str], f: list[str],
            attempts: tuple[k.Attempt, ...] = ATTEMPTS) -> bool:
    return k.run_answers_m44(window_count=1, attempts=attempts, roster=ROSTER, succ=SUCC,
                             switch_text=SWITCH, frame=FRAME, confinement=records(conf),
                             burst=records(b), frame_trace=records(f))


def a_correct_run_answers_all_three() -> None:
    ensure(verdict(confinement(), burst(), frame_trace()), "the correct run was refused")


def the_three_refuting_constructions_are_refused() -> None:
    for name, b in (("truncated to the low registers", burst(low_only=True)),
                    ("validity tag dropped", burst(tagless=7)),
                    ("nameable CSR exempted", burst(omit_csr=0))):
        ensure(not k.switch_is_total(ROSTER, SUCC, records(b)), f"{name} passed the switch")
        ensure(not verdict(confinement(), b, frame_trace()), f"{name} passed the run")
    # the zeroized row too: writing the saved value where the bank zeroizes
    wrong = [line if not line.startswith("C 001") else c(1, 12) for line in burst()]
    ensure(not k.csr_burst_total(ROSTER, SUCC, records(wrong)), "a zeroize read as a restore")


def the_switch_clause_refuses_extra_and_repeated_writes() -> None:
    ensure(not k.burst_carries_nothing_else(ROSTER, records([*burst(), x(0, False, 0)])),
           "a zero-register write passed")
    ensure(not k.burst_carries_nothing_else(ROSTER, records([*burst(), c(2, 0)])),
           "a write to an unnameable CSR passed")
    repeated = records([x(5, False, 99), *burst()])
    ensure(k.switch_is_total(ROSTER, SUCC, repeated), "the last write is the one compared")
    ensure(not k.burst_writes_exactly_once(ROSTER, repeated), "a repeated write passed")
    with_scr = records([*burst(), "S 31 1 0000000000000007"])
    ensure(k.switch_is_total(ROSTER, SUCC, with_scr),
           "the clause reads no S record, as KernelInstance.v reading 5 states")


def the_confinement_clause_refuses_its_constructions() -> None:
    ensure(not k.root_is_the_partitions(1, ATTEMPTS, records(confinement(kept=1))),
           "a derivation that kept its tag passed")
    ensure(not k.root_is_the_partitions(1, ATTEMPTS[:1], records(confinement())),
           "a member skipping its declared window passed")
    late = [i(0x100), i(0x104), x(8, False, 7), x(9, False, 7)]
    ensure(not k.root_is_the_partitions(1, ATTEMPTS, records(late)),
           "the next retire supplied a missing result")
    ensure(not k.well_formed_attempts((k.Attempt(0x100, 8, "R"), k.Attempt(0x100, 9, "W0"))),
           "one site witnessed two targets")
    ensure(not k.well_formed_attempts((k.Attempt(0x100, 0, "R"),)),
           "the zero register was a result register")


def the_frame_clause_refuses_its_constructions() -> None:
    swapped = frame_trace((T0, T2, T1))
    ensure(not k.switches_in_table_order(SWITCH, FRAME, records(swapped)),
           "a departure from the table's order passed")
    again = frame_trace((T0, T1, T2, T0))
    ensure(not k.reserved_entered_once(SWITCH, FRAME, records(again)),
           "a reserved slot entered twice passed")
    ensure(not k.no_unnamed_switch(SWITCH, FRAME, records([*frame_trace(), i(0x200)])),
           "a retire outside every extent passed")
    split = [*frame_trace(), i(SWITCH.base), i(T2.base)]
    ensure(not k.no_unnamed_switch(SWITCH, FRAME, records(split)),
           "a switch the table names no boundary for passed")
    dwell = [line for line in frame_trace() for _ in range(3)]
    ensure(k.frame_is_the_tables(SWITCH, FRAME, records(dwell)),
           "dwell inside a slot changed the verdict")


def the_readability_clause_refuses_meeting_extents() -> None:
    ensure(k.extents_are_readable(SWITCH, FRAME), "separated extents were unreadable")
    repeated = k.Frame((T0, T1, T0), reserved=1)
    ensure(k.extents_are_readable(SWITCH, repeated), "one tenant's two slots were unreadable")
    for name, extents in (("a tenant text meeting the switch text", (T0, k.Extent(5, 15), T2)),
                          ("partially overlapping tenant texts", (T0, k.Extent(35, 45), T2))):
        frame = k.Frame(extents, reserved=1)
        ensure(not k.extents_are_readable(SWITCH, frame), f"{name} was readable")
        ensure(not k.frame_is_the_tables(SWITCH, frame, records(frame_trace(extents))),
               f"{name} passed the frame clause")
    touching = k.Frame((k.Extent(20, 30), k.Extent(30, 40), k.Extent(40, 50)), reserved=1)
    ensure(k.extents_are_readable(SWITCH, touching), "touching extents were unreadable")


def kills_are_credited_to_the_expectation_that_decided_them() -> None:
    said = ("FAIL 3 disagreement(s) between the kernel C and the Gallina definitions\n"
            "FAIL 2 release expectation(s) stated by this harness\n"
            "FAIL 1 consumer check(s)\n")
    moved = cli_kernel.movement(said)
    ensure(moved == {cli_kernel.GALLINA: 3, cli_kernel.CONTROL: 1,
                     cli_kernel.EXPECTATION: 2}, f"{moved}")
    ensure(cli_kernel.deciding_kind(moved) == cli_kernel.GALLINA, "a Gallina kill was not first")
    only_release = cli_kernel.movement("FAIL 44 release expectation(s) stated by this harness\n")
    ensure(cli_kernel.deciding_kind(only_release) == cli_kernel.EXPECTATION,
           "a release-expectation kill was credited elsewhere")
    only_control = cli_kernel.movement("FAIL 1 consumer check(s)\n")
    ensure(cli_kernel.deciding_kind(only_control) == cli_kernel.CONTROL,
           "a consumer-control kill was credited elsewhere")
    ensure(cli_kernel.deciding_kind(cli_kernel.movement("")) is None, "nothing moved")


def restore_bursts_are_cut_by_the_declared_extent() -> None:
    trace = [i(0x40), x(3, True, 1), i(RESTORE.base), x(1, False, 2), i(RESTORE.base + 4),
             c(0, 5), i(0x40), x(2, False, 3), i(RESTORE.base), x(4, False, 4)]
    cut = k.restore_bursts(records(trace), RESTORE)
    ensure(len(cut) == 2, f"{len(cut)} bursts where two visits were made")
    ensure(cut[0] == records([x(1, False, 2), c(0, 5)]), f"first burst {cut[0]}")
    ensure(cut[1] == records([x(4, False, 4)]), f"second burst {cut[1]}")


def records_are_read_in_the_normalized_grammar() -> None:
    raw = ["tohost located at 0x80001000", "I 7 0000000080000000 00000013",
           "X 5 1 0000000000000007", "C 300 0000000000000008"]
    parsed = k.read_emulator_trace(raw)
    ensure(parsed[0] == ("I", (0x80000000, 0x13)), f"{parsed[0]}")
    ensure(parsed[2] == ("C", (0x300, 8)), f"{parsed[2]}")
    try:
        k.parse_record("I 7 0000000080000000 00000013")
    except k.TraceError:
        pass
    else:
        raise AssertionError("an I record keeping its order field was read as normalized")


def a_flipped_vector_verdict_is_reported() -> None:
    regs = " ".join(f"{v}/{int(t)}" for v, t in SUCC.registers)
    head = ["kt d 0 1 10:20 0:30:40 1:50:60 2:70:80",
            "kt r 0:1:0 1:1:1 2:0:0",
            f"kt s 1 {regs} | 11 12 13"]
    good = f"kt b 1 {';'.join(burst())} -> 1 1 1 1 1"
    flipped = f"kt b 1 {';'.join(burst())} -> 1 1 1 1 0"
    _, found = k.check_vectors([*head, good])
    ensure(not found, f"a correct verdict disagreed: {found}")
    _, found = k.check_vectors([*head, flipped])
    ensure(len(found) == 1 and found[0].column == "exactly_once",
           f"a flipped verdict was not reported: {found}")
    try:
        k.check_vectors(["kt z 0 -> 1"])
    except k.TraceError:
        pass
    else:
        raise AssertionError("an unknown kt family was skipped")


def the_authored_mutants_still_seed() -> None:
    kernel = TOOLS.parent / cli_kernel.KERNEL
    for mutant in cli_kernel.C_MUTANTS:
        text = (kernel / mutant.path).read_text(encoding="utf-8")
        ensure(text.count(mutant.old) == 1,
               f"{mutant.what}: the seed occurs {text.count(mutant.old)} times")
    for reader in cli_kernel.READER_MUTANTS:
        ensure(hasattr(k, reader.attribute), f"{reader.what}: no such attribute")


def the_harness_closure_is_its_requires_only() -> None:
    root = TOOLS.parent
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        shutil.copytree(root / "proofs", work / "proofs",
                        ignore=shutil.ignore_patterns("*.json"))
        shutil.copytree(root / "tools" / "quickchick", work / "harness")
        harness = work / "harness" / cli_kernel.HARNESS
        names = [p.stem for wave in cli_kernel.closure(work, harness) for p in wave]
    ensure(names[-1] == "KernelVectors", f"the harness is not last: {names}")
    ensure(set(names) == {"PartitionContext", "BoundaryCost", "CyclicExecutive",
                          "KernelInstance", "Probe", "KernelVectors"},
           f"closure {names}")


def cases() -> list[Case]:
    return [Case(fn.__name__, fn) for fn in (
        a_correct_run_answers_all_three,
        the_three_refuting_constructions_are_refused,
        the_switch_clause_refuses_extra_and_repeated_writes,
        the_confinement_clause_refuses_its_constructions,
        the_frame_clause_refuses_its_constructions,
        the_readability_clause_refuses_meeting_extents,
        kills_are_credited_to_the_expectation_that_decided_them,
        restore_bursts_are_cut_by_the_declared_extent,
        records_are_read_in_the_normalized_grammar,
        a_flipped_vector_verdict_is_reported,
        the_authored_mutants_still_seed,
        the_harness_closure_is_its_requires_only,
    )]
