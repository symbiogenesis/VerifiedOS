# SPDX-License-Identifier: Apache-2.0
"""The second class's bank grant, and the schedule the composition wraps around it.

One parse, read by two callers: `tools/bank-dse.py`, which scores candidate bank
counts against the arithmetic that exists today, and the `banks` check group, which
holds the contract's declared point against the configuration's.

Everything here is a parse and never a decision, as everywhere else in this package.
What is admissible is `docs/bank-count-dse-contract.md`'s and the check group's; what
is *stated* is the model configuration's, and the configuration says on its own face
that every one of these figures is a placeholder until R-15-247m measures it.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config
from .jsonc import Json

CONFIG = "model/config/verifiedos.json"
DOCUMENT = "docs/bank-count-dse-contract.md"

SECOND_CLASS = ("memory", "classes", "second")
SEQUENCER = ("platform", "memory_sequencer")

# Every column of the report that wants a coefficient, and the symbols it waits on.
# Declared here rather than in the tool that prints it, because the check group holds
# these symbols against the contract's own table: the tool and the document naming
# different coefficients is exactly the drift a second copy of a list produces.
PENDING_COLUMNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("droop headroom", ("I_bank_peak", "I_pdn_max")),
    ("island bandwidth", ("W_bank", "s_island")),
    ("read energy per bit", ("C_bl_per_row",)),
)

# The pair the hard constraint is stated over. While the class is unqualified these
# must be pending, because a droop envelope with operands would mean a macro had been
# measured, which is the one thing `qualified` records (R-15-247m).
PRUNING = PENDING_COLUMNS[0][1]

# the contract's own declared point and candidate set, in the two forms it writes them.
# Case-insensitive because either may open a sentence, which is the sentence's business
# and not the figure's.
DECLARED_RE = re.compile(r"(?i)the configuration declares \*\*(\d[\d,]*) banks\*\*")
CANDIDATE_RE = re.compile(
    r"(?i)the candidate set is \*\*([\d,]+ through [\d,]+)\*\* banks")
# one row of the coefficient table: the symbol, three cells, and its status
PENDING_RE = re.compile(
    r"(?m)^\| `([A-Za-z_]+)` \|[^|]*\|[^|]*\|[^|]*\| (pending|stated) \|")


@dataclass
class Grant:
    """What the composition declares about the second class, one field per figure."""

    banks: int | None = None
    qualified: bool | None = None
    retention_floor_us: int | None = None
    refresh_cycles: int | None = None
    discharge_cycles: int | None = None
    banks_per_refresh_phase: int | None = None
    refresh_phase_cycles: int | None = None
    banks_per_discharge_phase: int | None = None
    discharge_phase_cycles: int | None = None
    clock_hz: int | None = None
    region_bytes: int | None = None

    # the contract's side
    declared_banks: int | None = None
    candidates: list[int] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    stated: list[str] = field(default_factory=list)

    def complete(self) -> bool:
        """Whether every figure the arithmetic below needs was found. A grant that is
        short of one is reported as such rather than scored around."""
        return None not in (self.banks, self.retention_floor_us,
                            self.banks_per_refresh_phase, self.refresh_phase_cycles,
                            self.banks_per_discharge_phase, self.discharge_phase_cycles,
                            self.clock_hz, self.region_bytes)


def _region_bytes(path: Path, which: str) -> int | None:
    """The size of the region a class is assigned, read out of the region list.

    The list is walked rather than indexed, because a region's position in it is not a
    fact about the class: what names the class is the `memory_class` attribute, which
    is the same option the model reads.
    """
    regions = config.value(path, "memory", "regions")
    if not isinstance(regions, list):
        return None
    total = 0
    found = False
    for region in regions:
        if not isinstance(region, dict):
            continue
        attributes: Json = region.get("attributes")
        if not isinstance(attributes, dict):
            continue
        assignment = attributes.get("memory_class")
        if not (isinstance(assignment, dict) and assignment.get("Some") == which):
            continue
        size = region.get("size")
        if not (isinstance(size, dict) and isinstance(size.get("value"), str)):
            return None
        found = True
        total += int(str(size["value"]), 0)
    return total if found else None


def read(root: Path) -> Grant:
    """One pass over the configuration and the contract."""
    path = root / CONFIG
    grant = Grant()

    for name in ("banks", "retention_floor_us", "refresh_cycles", "discharge_cycles"):
        setattr(grant, name, config.integer(path, *SECOND_CLASS, name))
    qualified = config.value(path, *SECOND_CLASS, "qualified")
    grant.qualified = qualified if isinstance(qualified, bool) else None

    for name in ("banks_per_refresh_phase", "refresh_phase_cycles",
                 "banks_per_discharge_phase", "discharge_phase_cycles"):
        setattr(grant, name, config.integer(path, *SEQUENCER, name))
    grant.clock_hz = config.integer(path, "platform", "clock_frequency")
    grant.region_bytes = _region_bytes(path, "SecondClass")

    doc = root / DOCUMENT
    text = doc.read_text(encoding="utf-8") if doc.is_file() else ""
    declared = DECLARED_RE.search(text)
    if declared:
        grant.declared_banks = int(declared.group(1).replace(",", ""))
    span = CANDIDATE_RE.search(text)
    if span:
        low, high = (int(tok.replace(",", "")) for tok in span.group(1).split(" through "))
        grant.candidates = [b for e in range(64) if low <= (b := 1 << e) <= high]
    for m in PENDING_RE.finditer(text):
        (grant.pending if m.group(2) == "pending" else grant.stated).append(m.group(1))
    return grant


@dataclass
class Score:
    """One candidate, and the arithmetic that exists today over it."""

    banks: int
    bank_bytes: int
    region_bytes: int
    refresh_phases: int
    refresh_sweep_cycles: int
    refresh_deadline_cycles: int
    discharge_phases: int
    discharge_dwell_cycles: int

    @property
    def meets_deadline(self) -> bool:
        return self.refresh_sweep_cycles < self.refresh_deadline_cycles

    @property
    def divides_region(self) -> bool:
        return self.bank_bytes * self.banks == self.region_bytes


def score(grant: Grant, banks: int) -> Score | None:
    """The arithmetic a candidate can be put through without a coefficient.

    Four figures, and not one of them is an objective: the bank's own size, the refresh
    sweep against the deadline the retention floor sets (R-15-247c), and the mode-exit
    discharge dwell (R-15-247q, R-15-247f). The two objectives R-15-247p names and the
    hard constraint that prunes against them all want a coefficient nobody has
    measured, which is why this returns a shape and never a verdict.

    Each figure is bound before it is used rather than asserted after: `python -O`
    deletes an assertion, and a tool whose output is evidence must not be one flag away
    from dividing by a `None`.
    """
    per_refresh, refresh_cycles = grant.banks_per_refresh_phase, grant.refresh_phase_cycles
    per_discharge = grant.banks_per_discharge_phase
    discharge_cycles, clock = grant.discharge_phase_cycles, grant.clock_hz
    floor_us, region = grant.retention_floor_us, grant.region_bytes
    if (banks < 1 or not per_refresh or not refresh_cycles or not per_discharge
            or not discharge_cycles or not clock or not region or floor_us is None):
        return None

    refresh_phases = -(-banks // per_refresh)                        # ceiling division
    discharge_phases = -(-banks // per_discharge)
    return Score(
        banks=banks,
        bank_bytes=region // banks,
        region_bytes=region,
        refresh_phases=refresh_phases,
        refresh_sweep_cycles=refresh_phases * refresh_cycles,
        # microseconds into cycles rather than cycles into microseconds: the deadline is
        # a floor and dividing down would round a cadence into a compliance it lacks
        refresh_deadline_cycles=floor_us * clock // 1_000_000,
        discharge_phases=discharge_phases,
        discharge_dwell_cycles=discharge_phases * discharge_cycles,
    )
