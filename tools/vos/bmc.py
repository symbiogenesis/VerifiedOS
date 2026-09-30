# SPDX-License-Identifier: Apache-2.0
"""The bounded model-checking smoke over the curated scalar core, as a declared plan.

R-15-094 places riscv-formal/rvfi as bounded-depth evidence and the cheapest bring-up
gate, and its acceptance is that it grounds no refinement claim. This module is the
plan that gate runs against once its inputs exist: which of riscv-formal's checks it
runs, at which depth, over which instructions of the frozen dialect, and what it
waits on. It runs nothing. The harness contract is
[docs/assurance/rtl-cosimulation-harness.md](../../docs/assurance/rtl-cosimulation-harness.md).

**The instruction scope is derived, and its rule is the decision.** riscv-formal
judges an instruction against its own RV64 model, so an instruction is in scope only
where this dialect's semantics are that model's: the integer computational forms of
the base, M, bit-manipulation and conditional-zero extensions, which read and write
the integer reading of a register and raise no capability exception. The rule is
stated as the Sail constructors that carry those forms, and the mnemonics are read
out of the generated dialect table ([dialect.py](dialect.py)), which is the model's
own `encdec`. Every constructor the model files at `SITES` contribute is classified,
in scope or excluded with its reason, so a constructor the model gains is a finding
here rather than a silent gap.

**A form in scope is judged by a model, and riscv-formal's is not always one.**
Where riscv-formal carries no model for an in-scope form, or one that computes
something else, the plan names the form and what is owed in its place. A verdict
over such a form counts only against what is owed; against riscv-formal's own it
would be a counterexample on a correct core or a pass on a wrong one.

**A bound that admits no retirement decides nothing.** A pipeline deeper than the
depth retires no instruction inside it, and every instruction check then holds
vacuously; the plan therefore requires riscv-formal's cover check to reach a
retirement of the in-scope forms within the instruction depth before an instruction
verdict counts.

**Liveness is the one check that needs the memory to answer.** Every other check is
a safety property and holds or fails under any memory responses, so the predicate
leaves them unconstrained; under unconstrained responses a memory that never answers
keeps any instruction from retiring, and liveness would then fail for a reason that
is not about the core. The liveness check alone therefore carries a fairness
assumption, stated on it below as a wrapper obligation.
"""

from dataclasses import dataclass
from typing import Final

from vos import dialect


@dataclass(frozen=True)
class Check:
    """One riscv-formal check kind, the depth the smoke runs it to, and what it decides.

    The names and their meanings are riscv-formal's as its documentation states them;
    nothing of it is pinned yet, so both are re-read at the pin before a run relies on
    either. `assumes` is an assumption the wrapper adds for this check alone, beyond
    the predicate's unconstrained memory responses; empty where the check needs none.
    """

    name: str
    depth: int
    decides: str
    assumes: str = ""


# Provisional bounds, placeholders the first run replaces. No source states a depth
# for this core: R-15-094 sets none, and riscv-formal, whose own configurations would
# be the precedent, is not pinned and those configurations are unread. The first run
# sets each depth, records it with the time the check took, and the cover check
# decides whether the instruction depth admitted a retirement at all.
CHECKS: Final = (
    Check("insn", 30, "each in-scope instruction's RVFI record against its RV64 model, "
                      "riscv-formal's or the one owed in its place"),
    Check("reg", 30, "a register read returns the value the last retired write left"),
    Check("pc_fwd", 30, "a retirement's next program counter is the next retirement's "
                        "program counter"),
    Check("pc_bwd", 30, "the same continuity read backwards"),
    Check("causal", 30, "an instruction that reads a register retires after the one whose "
                        "write it reads"),
    Check("unique", 30, "no two retirements share an order"),
    Check("liveness", 40, "an instruction that entered the pipeline retires",
          assumes="every instruction and data memory request is answered within a "
                  "bounded number of cycles (fairness); without it a memory that never "
                  "answers fails this check for no reason about the core"),
    Check("cover", 30, "a retirement of the in-scope forms is reachable within the bound, "
                       "which is what makes every check above non-vacuous"),
)

# The Sail constructors whose forms riscv-formal's RV64 models judge as this dialect
# executes them.
SCOPE: Final = frozenset({
    # The base and M extensions.
    "UTYPE", "ITYPE", "SHIFTIOP", "RTYPE", "ADDIW", "SHIFTIWOP", "RTYPEW",
    "MUL", "MULW", "DIV", "DIVW", "REM", "REMW",
    # Zba, Zbb, Zbs and Zbkc's carry-less pair, which the B files carry.
    "SLLIUW", "ZBA_RTYPEUW", "ZBA_RTYPE", "ZBB_RTYPE", "ZBB_RTYPEW", "ZBB_EXTOP",
    "RORI", "RORIW", "REV8", "ORCB", "CLZ", "CLZW", "CTZ", "CTZW", "CPOP", "CPOPW",
    "ZBS_IOP", "ZBS_RTYPE", "CLMUL", "CLMULH",
    # Zbkb and Zbkx, which the K files carry.
    "ZBKB_RTYPE", "ZBKB_PACKW", "BREV8", "XPERM4", "XPERM8",
    # Zicond, the constant-time select (R-15-054).
    "ZICOND_RTYPE",
})

# The in-scope forms whose riscv-formal model cannot stand as the reference, read at
# the revision the hardware reuse map cites (HW-12), each with what is wrong or
# missing there and what is owed in its place. Keyed by mnemonic, because one
# constructor carries both the signed and the unsigned division.
_UNSIGNED = ("the generated model computes the signed result inside a conditional whose "
             "other arms are unsigned, so outside riscv-formal's alternative-operations "
             "mode, which this core does not have, it divides unsigned (YosysHQ/riscv-"
             "formal issue 30)")
_CORRECTED = "; owed: a pin whose model corrects this, or a model the wrapper supplies"
_ABSENT = ("riscv-formal carries no model for it; owed: a model the wrapper supplies, "
           "written from the dialect's execute clause")
MODELS_OWED: Final = {
    "div": _UNSIGNED + _CORRECTED,
    "divw": _UNSIGNED + _CORRECTED,
    "rem": _UNSIGNED + _CORRECTED,
    "remw": _UNSIGNED + ", and its zero test reads all 64 bits of the divisor, so a zero "
                        "low word reaches a remainder by zero, whose Verilog result is "
                        "x" + _CORRECTED,
    "czero.eqz": _ABSENT,
    "czero.nez": _ABSENT,
}

# Every other constructor the model files at SITES contribute, with the reason
# riscv-formal's model cannot judge it here.
EXCLUDED: Final = {
    "LOAD": "authorized by a capability: the address is the capability's and a tag, "
            "seal, permission or bounds fault traps with a cause riscv-formal's model "
            "does not have (R-15-001's purecap-only ISA, with no DDC to relocate an "
            "integer address under R-15-001c)",
    "STORE": "authorized by a capability as a load is, and it also writes a tag the "
             "model does not track",
    "BTYPE": "the target is checked against PCC's bounds and a violation traps with a "
             "capability cause",
    "FENCE": "this profile collapses fence to a drain or a no-op and reads the I and O "
             "bits the base ISA ignores",
    "FENCE_TSO": "collapsed to a drain or a no-op as fence is",
    "ECALL": "a trap enters through MTCC rather than an integer vector",
    "EBREAK": "a trap enters through MTCC rather than an integer vector",
    "MRET": "returns through MEPCC and unseals a sentry",
    "WFI": "no asynchronous interrupt is delivered (R-15-099)",
}

# The model files whose constructors the classification above is closed over.
SITES: Final = ("/extensions/I/", "/extensions/M/", "/extensions/B/", "/extensions/K/",
                "/extensions/Zicond/")

# What the smoke waits on, each named so the gate refuses by name rather than
# running without it.
INPUTS: Final = (
    ("riscv-formal", "the YosysHQ framework pinned under upstream/ with its licence read "
                     "at the pin and a THIRD-PARTY.md row, before any file of it is used"),
    ("SymbiYosys", "Yosys, SymbiYosys and one SMT solver provisioned in the guest lane, "
                   "each pinned with a THIRD-PARTY.md row"),
    ("core", "the curated scalar core (R1b) read by the formal front end; it elaborates "
             "under Verilator, which does not establish that reading"),
    ("port", "the RVFI obligations the harness contract lists: an order, every synchronous "
             "trap retired with its cause, and the full register value on the probes"),
)


def _sited(row: dialect.Row) -> bool:
    return any(site in row.site for site in SITES)


def scope(table: dict[str, dialect.Row] | None = None) -> list[str]:
    """The mnemonics the instruction checks cover, read out of the dialect table."""
    rows = dialect.TABLE if table is None else table
    return sorted(name for name, row in rows.items() if _sited(row) and row.ctor in SCOPE)


def findings(table: dict[str, dialect.Row] | None = None) -> list[str]:
    """Where the classification and the dialect table disagree, each a finding.

    A constructor of the classified files neither in scope nor excluded is a form
    nobody decided about; a declared constructor no row carries is a rule that selects
    nothing; and a model owed for a form the scope does not cover is owed for nothing.
    """
    rows = dialect.TABLE if table is None else table
    carried = {row.ctor for row in rows.values() if _sited(row)}
    out = [f"the {ctor} constructor is neither in the smoke's scope nor excluded from it"
           for ctor in sorted(carried - SCOPE - set(EXCLUDED))]
    out += [f"the scope names {ctor} and no classified row of the dialect carries it"
            for ctor in sorted(SCOPE - carried)]
    out += [f"the exclusions name {ctor} and no classified row of the dialect carries it"
            for ctor in sorted(set(EXCLUDED) - carried)]
    out += [f"{ctor} is both in scope and excluded" for ctor in sorted(SCOPE & set(EXCLUDED))]
    out += [f"a model is owed for {name} and the scope does not cover it"
            for name in sorted(set(MODELS_OWED) - set(scope(rows)))]
    return out
