# SPDX-License-Identifier: Apache-2.0
"""Bounded model-checking (`riscv-formal`/RVFI) smoke plan for the curated scalar core (R-15-094);
see [docs/assurance/rtl-cosimulation-harness.md](../../docs/assurance/rtl-cosimulation-harness.md).

Classifies every Sail constructor from `SITES` in [dialect.py](dialect.py) as either in
`SCOPE` (integer computational forms whose semantics match RV64) or in `EXCLUDED`
(capability-authorized or profile-specific forms), and records in-scope mnemonics
requiring wrapper-supplied reference models (`MODELS_OWED`).
"""

from dataclasses import dataclass
from typing import Final

from vos import dialect


@dataclass(frozen=True)
class Check:
    """Single `riscv-formal` check kind, bound depth, obligation summary, and wrapper assumption."""

    name: str
    depth: int
    decides: str
    assumes: str = ""


# Provisional `riscv-formal` check bounds and obligations.
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

# Sail constructors whose forms match `riscv-formal`'s RV64 integer semantics.
SCOPE: Final = frozenset({
    "UTYPE", "ITYPE", "SHIFTIOP", "RTYPE", "ADDIW", "SHIFTIWOP", "RTYPEW",
    "MUL", "MULW", "DIV", "DIVW", "REM", "REMW",
    "SLLIUW", "ZBA_RTYPEUW", "ZBA_RTYPE", "ZBB_RTYPE", "ZBB_RTYPEW", "ZBB_EXTOP",
    "RORI", "RORIW", "REV8", "ORCB", "CLZ", "CLZW", "CTZ", "CTZW", "CPOP", "CPOPW",
    "ZBS_IOP", "ZBS_RTYPE", "CLMUL", "CLMULH",
    "ZBKB_RTYPE", "ZBKB_PACKW", "BREV8", "XPERM4", "XPERM8",
    "ZICOND_RTYPE",
})

# In-scope mnemonics whose upstream `riscv-formal` model is absent or defective.
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

# Constructors from `SITES` excluded from `riscv-formal` RV64 checking, with rationale.
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

# Model source-path substrings over which constructor classification is closed.
SITES: Final = ("/extensions/I/", "/extensions/M/", "/extensions/B/", "/extensions/K/",
                "/extensions/Zicond/")

# External prerequisites required before running the `riscv-formal` smoke gate.
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
    """Return sorted mnemonics from `table` whose source path matches `SITES` and constructor is in `SCOPE`."""
    rows = dialect.TABLE if table is None else table
    return sorted(name for name, row in rows.items() if _sited(row) and row.ctor in SCOPE)


def findings(table: dict[str, dialect.Row] | None = None) -> list[str]:
    """Return any classification gaps or overlaps between `SCOPE`, `EXCLUDED`, `MODELS_OWED`, and `table`."""
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
