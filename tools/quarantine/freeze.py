# SPDX-License-Identifier: Apache-2.0
"""The profile-freeze measurement instrument: what it carries, and what it waits on.

[docs/freeze-measurement-contract.md](../../docs/freeze-measurement-contract.md) is
the specification: the versioned corpus manifest, the composition recipe, the
emitter-provenance schema, the admitted region classes, the nine decisions of the
freeze's single measured act, the declared parameters, the report's two renderings,
and the twelve CI predicates that reject a report. This module is the instrument
that runs against it, read by two callers: `tools/quarantine/freeze-report.py`,
which produces the report, and the `freeze` check group beside it, which holds the
instrument's own enumerations against the contract's in both directions.

**The instrument cannot be run end to end today, and that is a schedule fact rather
than a shortfall in it.** The analyzer joins three inputs (§4): the provenance
sidecar stream from S1 and S4, the link map from S5, and the encoded image from S7.
The first is M1.2's backend and the other two are M1.4's linker and image composer,
so no member of §2's corpus exists yet and no byte or cycle column is a measurement.
What this module therefore does is exactly what `quarantine/banks.py` does for the
bank count: it computes everything the composition already fixes, and for every column
whose operand does not exist it carries **the symbol it waits on** rather than a
number or a blank.

Three things follow from that, and each is a design decision rather than a stopgap.

- **A cell has four kinds, not two.** A `value` is a measurement, `n/a` is an axis
  that does not apply, `pending` names the symbol the cell waits on, and `fixture`
  is a number the wiring produced from a synthetic input standing in for M1.2's or
  M1.4's. A `fixture` cell is never a `value`: every gate predicate in §9 treats it
  as an absent measurement and defers, so the fixture exercises the join without
  ever letting a fabricated number clear the gate.
- **The gate has three outcomes, not two.** A predicate `passes`, `REJECT`s, or
  `defers on <symbol>`. A gate that could only pass or reject would have to reject
  the whole of today's report twelve times over and would say nothing about which
  predicates are already deciding; the third outcome is what makes the report
  readable before the corpus exists.
- **Values are parsed and membership is declared.** Every number the contract
  chooses (§8's parameters, the members' feeds, the operand classes' two-way split)
  is read out of the contract at run time, so this module holds no second copy of
  one. What it *declares* is which members, steps, classes, decisions, parameters
  and predicates it implements, because that is behaviour rather than a figure, and
  K-77 holds the two sets equal in both directions.

The one substantive result the instrument can produce before the corpus exists is
the FD-2 geometry table: R-15-036h's slot model and R-15-036j's packing term are
arithmetic over `(w, h, k, p)`, so the hit rate each declared bundle geometry needs
to clear the derived 22.4-bit bar, and the realized packing term the register's own
break-even implies, are computable today and are not decisions.
"""

import math
import re
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from vos.jsonc import Json

CONTRACT = "docs/freeze-measurement-contract.md"
MODULE = "tools/quarantine/freeze.py"

# =====================================================================================
# the contract, parsed
# =====================================================================================
#
# Every table below is located by its section and read by its own row shape. Fail-closed
# is the rule the caller relies on: a section that cannot be found yields nothing, and
# the check group reports an empty enumeration rather than comparing two empty sets and
# calling them equal.

_MEMBER_RE = re.compile(r"(?m)^\| `(FM-\d+)` \| ([^|]*)\| ([^|]*)\| ([^|]*)\| ([^|]*)\|")
_STEP_RE = re.compile(r"(?m)^\| (S\d+) \| ([^|]*)\| ([^|]*)\| ([^|]*)\|")
_OPERAND_RE = re.compile(r"(?m)^\| `(OC-\d+)` \| ([^|]*)\| ([^|]*)\| ([^|]*)\|")
_REGION_RE = re.compile(r"(?m)^\| `(RC-\d+)` \| ([^|]*)\| ([^|]*)\|")
_REFUSAL_RE = re.compile(r"(?m)^- \*\*([a-z][^*]*)\*\*: ")
_DECISION_RE = re.compile(r"(?m)^### (FD-\d+) · (.+?)\s*$")
_BLOCK_RE = re.compile(r"(?m)^\| `(\w+)` \| ([^|]*)\|")
_PARAM_RE = re.compile(r"(?m)^\| ([^|]+)\| ([^|]*)\| ([^|]*)\| ([^|]*)\|")
_GATE_RE = re.compile(r"(?m)^\| `(G-\d+)` \| ([^|]*)\| ([^|]*)\|")

# `FD-4, FD-5` in a Feeds cell, and `OC-1` wherever a class is named.
_FD_TOKEN_RE = re.compile(r"\bFD-\d+\b")

# §6's FD-1 states both break-even hit rates in one sentence, the optimistic first.
_BREAK_EVEN_RE = re.compile(
    r"break-even in \*p\*, ([\d.]+) against the optimistic figure and ([\d.]+) against "
    r"the pessimistic one")


@dataclass(frozen=True)
class Row:
    """One enumerated member of the contract: its id and the cells beside it."""

    ident: str
    cells: tuple[str, ...]

    @property
    def what(self) -> str:
        return self.cells[0] if self.cells else ""


@dataclass
class Contract:
    """The contract's own enumerations, one field per table the instrument reads.

    Present is `False` where the document is not in the repository at all, which the
    caller reports once rather than as nine empty enumerations.
    """

    present: bool = False
    raw: str = ""
    members: list[Row] = field(default_factory=list)
    steps: list[Row] = field(default_factory=list)
    operand_classes: list[Row] = field(default_factory=list)
    region_classes: list[Row] = field(default_factory=list)
    refusals: list[str] = field(default_factory=list)
    decisions: list[Row] = field(default_factory=list)
    blocks: list[Row] = field(default_factory=list)
    parameters: list[Row] = field(default_factory=list)
    predicates: list[Row] = field(default_factory=list)

    def feeds(self, member: str) -> tuple[str, ...]:
        """The decisions one corpus member feeds, as §2's own Feeds column states them."""
        for row in self.members:
            if row.ident == member:
                cell = row.cells[-1] if row.cells else ""
                return tuple(m.group() for m in _FD_TOKEN_RE.finditer(cell))
        return ()

    def varying(self, operand_class: str) -> bool | None:
        """Whether an operand class is on the site-varying side of R-15-036k's two-way
        split, read from §4's own Class column rather than declared a second time."""
        for row in self.operand_classes:
            if row.ident == operand_class:
                return row.what.strip().startswith("site-varying")
        return None

    def parameter(self, key: str) -> str:
        """One declared parameter's value, as §8 states it."""
        for row in self.parameters:
            if row.ident == key:
                return row.cells[0].strip()
        return ""

    def break_even(self) -> tuple[float, float]:
        """The two break-even hit rates §6's FD-1 states, optimistic then pessimistic.

        Read rather than declared for the same reason §8's values are: the register
        fixes one of the pair and the contract restates both in one sentence, so a
        constant here would be a third copy. `(0.0, 0.0)` where the sentence moved,
        which the caller reports rather than scoring around.
        """
        m = _BREAK_EVEN_RE.search(self.raw)
        return (float(m.group(1)), float(m.group(2))) if m else (0.0, 0.0)

    def slot_width(self) -> int:
        """The slot width §8's FD-2 candidate cell fixes, which FD-2 derives rather
        than sweeps."""
        m = re.search(r"`w = (\d+)`", self.parameter("FD-2 candidate set"))
        return int(m.group(1)) if m else 0

    def decision_text(self, ident: str) -> str:
        """One decision's own §6 subsection, from its heading to the next.

        What it is for is the per-decision half of a threshold binding: §8 collects the
        values and §6 states which decision spends which, and a set comparison over the
        two cannot see FD-4 spending the 0.5% opcode floor where its own section says
        0.1%.
        """
        m = re.search(rf"(?m)^### {re.escape(ident)} ·", self.raw)
        if not m:
            return ""
        end = self.raw.find("\n### ", m.end())
        tail = self.raw.find("\n## ", m.end())
        if 0 <= tail < (end if end >= 0 else len(self.raw)):
            end = tail
        return self.raw[m.start():end if end >= 0 else len(self.raw)]

    def stated_refusal_count(self) -> str:
        """The count §5 states in words beside its own bullets, so that a reason added
        to both the document's list and the instrument's is still a finding until the
        sentence that counts them moves too."""
        m = re.search(r"\*\*([A-Za-z-]+) refusal reasons are enumerated", self.raw)
        return str(m.group(1)).lower() if m else ""


def _section(raw: str, number: str) -> str:
    """One numbered `## ` section, from its heading to the next one."""
    m = re.search(rf"(?m)^## {re.escape(number)}\. ", raw)
    if not m:
        return ""
    end = raw.find("\n## ", m.end())
    return raw[m.start():end if end >= 0 else len(raw)]


def _rows(pattern: re.Pattern[str], text: str) -> list[Row]:
    return [Row(m.group(1), tuple(c.strip() for c in m.groups()[1:]))
            for m in pattern.finditer(text)]


def _parameters(raw: str) -> list[Row]:
    """§8's declared parameters, keyed by the name their first cell opens with.

    Two of the eight are written as a backticked symbol followed by its gloss and six
    as bare prose, so the key is the first cell up to its first comma with the
    backticks taken off. That is the whole of what a reader would call the parameter's
    name, and it is stable under a reworded gloss.
    """
    rows: list[Row] = []
    for m in _PARAM_RE.finditer(raw):
        head = m.group(1).strip()
        if head == "Parameter" or head.startswith("---"):
            continue
        key = head.split(",", 1)[0].replace("`", "").strip()
        rows.append(Row(key, tuple(c.strip() for c in m.groups()[1:])))
    return rows


def read(root: Path) -> Contract:
    """One pass over the contract on disk, for the tool, which has no corpus.

    The check group reads the *index* instead, through `parse`: the checker's corpus is
    what git tracks, and a contract deleted from the index while left on disk is a
    document no reader of this repository has, which this reader would otherwise pass
    over green.
    """
    path = root / CONTRACT
    return parse(path.read_text(encoding="utf-8")) if path.is_file() else Contract()


def parse(raw: str) -> Contract:
    """Every enumeration the instrument reads, out of the contract's own text."""
    if not raw:
        return Contract()
    return Contract(
        present=True,
        raw=raw,
        members=_rows(_MEMBER_RE, _section(raw, "2")),
        steps=_rows(_STEP_RE, _section(raw, "3")),
        operand_classes=_rows(_OPERAND_RE, _section(raw, "4")),
        region_classes=_rows(_REGION_RE, _section(raw, "5")),
        refusals=[m.group(1).strip() for m in _REFUSAL_RE.finditer(_section(raw, "5"))],
        decisions=_rows(_DECISION_RE, _section(raw, "6")),
        blocks=_rows(_BLOCK_RE, _section(raw, "7")),
        parameters=_parameters(_section(raw, "8")),
        predicates=_rows(_GATE_RE, _section(raw, "9")),
    )


# =====================================================================================
# what the instrument implements
# =====================================================================================
#
# These are the memberships K-77 holds against the tables above, and they are declared
# here rather than parsed because each is behaviour: a corpus member is a producer and a
# set of pins the report records, a step is a recorded quantity, a decision is a column
# set and a threshold, and a predicate is a function. A member the contract carries and
# this table does not is a report block nobody writes; one this table carries and the
# contract does not is an instrument measuring something nothing asked for.

MEMBERS: tuple[str, ...] = ("FM-1", "FM-2", "FM-3", "FM-4", "FM-5", "FM-6")
STEPS: tuple[str, ...] = ("S1", "S2", "S3", "S4", "S5", "S6", "S7")
OPERAND_CLASSES: tuple[str, ...] = ("OC-1", "OC-2", "OC-3", "OC-4", "OC-5")
REGION_CLASSES: tuple[str, ...] = ("RC-1", "RC-2", "RC-3", "RC-4", "RC-5")
REFUSALS: tuple[str, ...] = ("crosses a compartment", "needs a frame",
                             "changes an interface", "on a balanced arm")
BLOCKS: tuple[str, ...] = ("manifest", "corpus", "recipe", "provenance", "regions",
                           "decisions", "dictionary", "opcode_ledger", "residuals")

# The milestone each corpus member's producer belongs to, which is what the report
# names in place of a hash while the member does not exist.
MEMBER_PRODUCER: dict[str, str] = {
    "FM-1": "M1.4's image composer over M1.2's backend",
    "FM-2": "the verified ASN.1 (X.691 UPER) to Narcissus front end",
    "FM-3": "the hand-written NAS grammar's generator",
    "FM-4": "the verified HAL's accessor generator over the attested devicetree",
    "FM-5": "the §4 provenance join over FM-1, derived and not built",
    "FM-6": "the formally derived stream corpus of R-15-238d",
}

# What each recipe step records, per §3's own rightmost column. Declared as the report's
# field names because the report is what carries them.
STEP_RECORDS: dict[str, tuple[str, ...]] = {
    "S1": ("backend_commit", "provisional_profile_revision", "source_pins"),
    "S2": ("retained_closure_size", "roots_count"),
    "S3": ("merged_function_count", "specialized_site_count"),
    "S4": ("region_class_admissions", "region_class_refusals"),
    "S5": ("image_layout_hash", "reachable_region_bits"),
    "S6": ("realized_size", "entries", "policy", "per_stratum_hit_rate"),
    "S7": ("encoded_bytes", "bundles", "slots", "padding_slots", "escapes"),
}

# The threshold a decision applies where the contract derives it from a quantity the
# register already fixes rather than declaring a value for it.
DERIVED = "derived"


@dataclass(frozen=True)
class Decision:
    """One row of the freeze's single measured act, as the instrument runs it.

    `arms` are the variants §6's Procedure paragraph names, and they are what the
    report carries a row for: FD-4's two forms, FD-5's four, FD-3's baseline and one
    per region class. An empty tuple means the arms are derived from §8's declared
    candidate sets rather than named here, which is FD-1's curve and FD-2's geometry
    sweep, and `("baseline",)` means the decision builds no variant at all, which is
    FD-8's, its measured input being read off the baseline.
    """

    ident: str
    question: str
    what: str
    order: int
    joint_with: str
    corpus: tuple[str, ...]
    unit: str
    procedure: str
    thresholds: tuple[str, ...]
    default: str
    knobs: tuple[str, ...]
    arms: tuple[str, ...]
    columns: tuple[str, ...]


# §7's fifth column convention: every delta is signed from the baseline, positive
# meaning the candidate saves, and every percentage is against *that row's* baseline
# encoded text, stated in the row rather than assumed. A percentage whose denominator is
# somewhere else is a numerator without one, which is the failure the whole contract
# opens on, so every row carrying a percentage carries the bytes it is a share of.
BASELINE_BYTES = "baseline_encoded_text_bytes"
DELTA_SIGN = ("every delta is signed from the baseline, positive meaning the candidate "
              "saves")

_FD1_COLUMNS: tuple[str, ...] = (
    "N", "policy", "entries_allocated", "indices_reserved", "instructions", "bundles",
    "slots_used", "slots_padding", "escapes",
    "p_hit[OC-1]", "p_hit[OC-2]", "p_hit[OC-3]", "p_hit[OC-4]", "p_hit[OC-5]",
    "p_hit_invariant", "p_hit_varying",
    "encoded_text_bytes", "canonical_text_bytes", "bits_per_instruction",
    "bits_per_instruction_model", "model_residual", "lambda_realized",
)

_FD5_COLUMNS: tuple[str, ...] = (
    "variant", "delta_bytes", BASELINE_BYTES, "delta_pct_encoded",
    "delta_pct_encoded[FM-2]", "delta_pct_encoded[FM-3]", "delta_pct_encoded[FM-4]",
    "sites_extract", "sites_insert", "specifier_form", "wc_cycles_delta",
    "opcodes_consumed",
)

# The ordered act, in the order §1 fixes and §9's `G-6` checks. It is **not** the order
# the plan's §0 paragraph reads in, and the difference is worth naming where a reader
# meets it: §0 lists the dictionary before outlining, which is the *recipe's* order (S3's
# merge and S6's selection inside one build), while §1 orders the *decisions* and puts
# FD-3 first because it changes the corpus every later row is measured against
# (R-15-036o, R-15-036p). Both orders are real and the report carries both.
DECISIONS: tuple[Decision, ...] = (
    Decision(
        ident="FD-3",
        question="which admitted region classes the outlining and tail-merging pass is "
                 "enabled for; not a delta item, and the one code-size lever that may "
                 "not be settled on the byte column alone",
        what="outlining and tail merging, on two axes",
        order=1,
        joint_with="FD-4",
        corpus=("FM-1", "FM-5"),
        unit="bytes removed, and worst-case cycles added, per admitted region class",
        procedure="a baseline with S4 disabled and one variant per region class with "
                  "only that class enabled; cycles from the timing-annotated Sail model "
                  "over every partition containing an outlined site",
        thresholds=(DERIVED,),
        default="a region class not clearing the threshold is disabled and the disabled "
                "set is recorded",
        knobs=("outlining_region_class",),
        arms=("baseline", *REGION_CLASSES),
        columns=("regions_found", "regions_admitted", "refusal_counts", "sites_m",
                 "region_len_n", "slots_inline", "slots_outlined_abs",
                 "slots_outlined_pcrel", "delta_bytes", BASELINE_BYTES,
                 "delta_pct_encoded", "wc_cycles_delta", "slot_width_cycles",
                 "slot_headroom_cycles", "slots_widened"),
    ),
    Decision(
        ident="FD-1",
        question="the realized size N, the procedure selecting N entries from the "
                 "composed image's histogram, and the policy for the site-varying "
                 "class: selection by instance count alone, or a marginal-value rule "
                 "reserving indices for recurring forms",
        what="the realized dictionary, its entry selection, and the site-varying policy",
        order=2,
        joint_with="FD-2",
        corpus=("FM-1",),
        unit="encoded bits per instruction",
        procedure="S6 and S7 at each candidate N under each of the two site-varying "
                  "policies, at the FD-2 configuration under test; the curve is "
                  "reported and not only the chosen point",
        thresholds=(DERIVED, "FD-1 candidate set for N", "dictionary headroom reserve",
                    "model residual tolerance"),
        default="none: the dictionary is the encoding, so a configuration clearing no "
                "candidate N fails the freeze's precondition and is reported as such",
        knobs=("dictionary_size", "site_varying_policy"),
        arms=(),          # derived from §8's candidate set and the two policies
        columns=_FD1_COLUMNS,
    ),
    Decision(
        ident="FD-2",
        question="the bundle width, the header width h, and the slot count k at the "
                 "reference instantiation of 128, 16 and 7, carried as a DSE parameter; "
                 "the one structural item in the delta, allocating no opcode and "
                 "changing no instruction semantics",
        what="bundle, header, and slot widths",
        order=2,
        joint_with="FD-1",
        corpus=("FM-1",),
        unit="encoded bits per instruction",
        procedure="the cross product of the declared (h, k) candidates with FD-1's N "
                  "candidates and both policies, run once, before the one-knob variants",
        thresholds=(DERIVED, "FD-2 candidate set",
                    "indifference band for the FD-2 tie-break"),
        default="n/a: §6 states no default arm, the structural tie-break deciding among "
                "the configurations that clear the bar",
        knobs=("bundle_geometry",),
        arms=(),          # derived from §8's declared (h, k) candidates
        columns=("bundle", "h", "k", "w", "lambda_bound", *_FD1_COLUMNS),
    ),
    Decision(
        ident="FD-4",
        question="whether the emitted call and global-address-materialization forms are "
                 "PC-relative or composition-time absolute, and, if absolute, the "
                 "reachable code region its immediate can name",
        what="call and global-address materialization form",
        order=3,
        joint_with="FD-3",
        corpus=("FM-1", "FM-5"),
        unit="encoded bytes, with the OC-3, OC-4 and OC-5 site counts beside them",
        procedure="two variants over the FD-3-admitted baseline differing in the form "
                  "knob alone, each with S6 re-run",
        thresholds=("T-form",),
        default="an immaterial measured delta leaves the PC-relative forms in place "
                "(R-15-036l)",
        knobs=("call_form",),
        arms=("pc_relative", "composition_time_absolute"),
        columns=("form", "delta_bytes", BASELINE_BYTES, "delta_pct_encoded",
                 "reachable_region_bits", "fallback_sites", "oc3_sites", "oc4_sites",
                 "oc5_sites", "p_hit_varying", "slots_inline", "slots_outlined_abs",
                 "slots_outlined_pcrel"),
    ),
    Decision(
        ident="FD-5",
        question="three decisions in one row: the field-specifier form, whether the two "
                 "6-bit immediates earn their encoding bits or a register-specified "
                 "field suffices; whether the insert form `bfins` is carried; and "
                 "whether the pair is carried at all",
        what="the bitfield pair",
        order=4,
        joint_with="",
        corpus=("FM-1", "FM-2", "FM-3", "FM-4"),
        unit="encoded bytes",
        procedure="four variants over the FD-3-admitted baseline, each with S6 re-run; "
                  "the insert form is admitted on its own delta given the extract "
                  "form's admission",
        thresholds=("T-enc",),
        default="a delta immaterial against the §15 capacity budget drops the "
                "instruction at the freeze (R-15-067d)",
        knobs=("bitfield_pair",),
        arms=("neither_form", "extract_only", "extract_and_insert_immediate",
              "extract_and_insert_register"),
        columns=_FD5_COLUMNS,
    ),
    Decision(
        ident="FD-6",
        question="whether a `csetbounds` taking a large immediate length, in CHERIoT's "
                 "form, is carried; a candidate and not a commitment, and the recorded "
                 "expectation is that it is dropped",
        what="the further code-size candidate",
        order=4,
        joint_with="",
        corpus=("FM-1",),
        unit="encoded bytes",
        procedure="two variants over R-15-036p's outlined corpus, so the outliner's "
                  "own yield on RC-4 is not credited to this instrument",
        thresholds=("T-enc",),
        default="dropped",
        knobs=("csetbounds_immediate_length",),
        arms=("without", "with"),
        columns=(*_FD5_COLUMNS, "rc4_regions_admitted"),
    ),
    Decision(
        ident="FD-7",
        question="whether the shift amount in `cld rd, cs1[rs2 << imm]` and its store "
                 "form earns its encoding bits, or an unscaled index suffices because "
                 "element strides are known where the slot plan is decided",
        what="the indexed load and store's scale immediate",
        order=4,
        joint_with="",
        corpus=("FM-1", "FM-4"),
        unit="encoded bytes",
        procedure="two variants over the FD-3-admitted baseline with S6 re-run, scaled "
                  "and unscaled, with the fraction of indexed accesses whose stride is "
                  "a slot-plan constant beside the byte delta",
        thresholds=("T-form",),
        default="the unscaled form, being the smaller encoding and the smaller model "
                "(R-15-007g)",
        knobs=("indexed_scale",),
        arms=("scaled", "unscaled"),
        columns=("form", "delta_bytes", BASELINE_BYTES, "delta_pct_encoded",
                 "indexed_sites", "sites_stride_constant", "immediate_bits"),
    ),
    Decision(
        ident="FD-8",
        question="which pairs are in the frozen fusion set, selected against the "
                 "instruction mix this profile emits and not inherited from the general "
                 "RISC-V fusion literature",
        what="frozen fusion-set membership",
        order=4,
        joint_with="",
        corpus=("FM-1",),
        unit="static emitted adjacent pairs",
        procedure="the emitted adjacency histogram over FM-1 after S5, taken from the "
                  "provenance join rather than from a disassembler's pattern match; no "
                  "variant is built, the decision not being this instrument's",
        thresholds=("FD-8 candidate floor",),
        default="n/a: admission is the §15 exploration's, and the report carries the "
                "row as pending in `residuals`",
        knobs=(),
        arms=("baseline",),
        columns=("pair", "adjacent_sites", "share_of_static_pairs",
                 "legal_under_profile", "admitted"),
    ),
    Decision(
        ident="FD-9",
        question="whether the fixed-latency range-coder step is carried, decided by the "
                 "same single measured act as the byte instruments but on the cycle "
                 "axis: the decoder's worst-case cycles per frame over the conformance "
                 "streams, against the §11 slot and the ceiling that slot declares",
        what="`rcstep` carriage, on the cycle axis",
        order=4,
        joint_with="",
        corpus=("FM-6",),
        unit="worst-case cycles per frame",
        procedure="two variants of the decoder over the same streams, with and without "
                  "the instruction, at the same VLEN and the same admitted worker set "
                  "and frame pool; the worst case per frame per tuple, never the mean",
        thresholds=(DERIVED,),
        default="dropped (R-15-067h), with the opcode contention recorded either way",
        knobs=("rcstep",),
        arms=("without", "with"),
        columns=("format", "level", "resolution", "frame_rate",
                 "wc_cycles_frame_without", "wc_cycles_frame_with", "slot_width_cycles",
                 "ceiling_conforms_without", "ceiling_conforms_with", "admission_moved",
                 "bytes"),
    ),
)

DECISION_IDS: tuple[str, ...] = tuple(d.ident for d in DECISIONS)


@dataclass(frozen=True)
class Enumeration:
    """One enumeration both sides carry: what a member of it is called, the floors key
    its size is registered under, the contract's members, and the instrument's.

    `stated` keeps the contract's own order and its repeats, because a row renumbered
    onto an id another row already carries narrows the set without shortening the
    document, and a set comparison alone reports that as one member missing.
    """

    what: str
    floor: str
    stated: tuple[str, ...]
    carried: tuple[str, ...]

    @property
    def repeated(self) -> list[str]:
        return [ident for ident in dict.fromkeys(self.stated)
                if self.stated.count(ident) > 1]


def enumerations(contract: Contract) -> list[Enumeration]:
    """Every enumeration the contract states and this instrument implements.

    Written once here rather than in each caller: `freeze-report.py` beside it refuses
    to report about a set that is not its contract's, and the `freeze` check group holds
    the same pair on every run, and two copies of one list is exactly the drift the
    checker exists to catch.

    The declared-parameter row's instrument side is deliberately the *applied*
    thresholds rather than a copy of §8's keys, because a parameter no decision reads
    would otherwise agree with the contract while being spent by nothing.
    """
    applied = tuple(dict.fromkeys(
        key for decision in DECISIONS for key in decision.thresholds if key != DERIVED))
    rows: tuple[tuple[str, str, list[str], tuple[str, ...]], ...] = (
        ("corpus member", "freeze corpus members",
         [row.ident for row in contract.members], MEMBERS),
        ("recipe step", "freeze recipe steps",
         [row.ident for row in contract.steps], STEPS),
        ("operand class", "freeze operand classes",
         [row.ident for row in contract.operand_classes], OPERAND_CLASSES),
        ("region class", "freeze region classes",
         [row.ident for row in contract.region_classes], REGION_CLASSES),
        ("refusal reason", "freeze region-class refusal reasons",
         contract.refusals, REFUSALS),
        ("decision", "freeze decisions",
         [row.ident for row in contract.decisions], DECISION_IDS),
        ("report block", "freeze report blocks",
         [row.ident for row in contract.blocks], BLOCKS),
        ("declared parameter", "freeze declared parameters",
         [row.ident for row in contract.parameters], applied),
        ("CI predicate", "freeze CI predicates",
         [row.ident for row in contract.predicates], PREDICATE_IDS),
    )
    return [Enumeration(what, floor, tuple(stated), tuple(dict.fromkeys(carried)))
            for what, floor, stated, carried in rows]


def _memberships(contract: Contract) -> list[str]:
    """Every enumeration, in both directions, with an empty contract side stopping its
    own pair rather than agreeing with a full one."""
    findings: list[str] = []
    for enum in enumerations(contract):
        if not enum.stated:
            findings.append(
                f"{CONTRACT} states no {enum.what} in a form this tool reads, so the "
                f"instrument's {len(enum.carried)} of them are held against nothing")
            continue
        findings += [f"{CONTRACT} states the {enum.what} `{ident}` more than once, so "
                     "one of its rows carries an id another row already has"
                     for ident in enum.repeated]
        known, seen = set(enum.carried), set(enum.stated)
        findings += [f"{CONTRACT} states the {enum.what} `{ident}` and "
                     f"{MODULE} implements no such thing"
                     for ident in dict.fromkeys(enum.stated) if ident not in known]
        findings += [f"{MODULE} implements the {enum.what} `{ident}` and {CONTRACT} "
                     "states no such thing"
                     for ident in enum.carried if ident not in seen]
    return findings


def _feeds(contract: Contract) -> list[str]:
    """§2's Feeds column against the corpus each decision declares, both directions.

    Quantified over the union of the two rosters rather than over the instrument's own,
    because the failure that escapes a per-member walk is an *addition*: a decision
    naming a member neither side declares is a corpus this analyzer would go looking
    for and a stratum count taken from an image nothing built, and walking `MEMBERS`
    alone never reaches it.
    """
    findings: list[str] = []
    named = {member for decision in DECISIONS for member in decision.corpus}
    for member in sorted(set(MEMBERS) | named | {row.ident for row in contract.members}):
        stated = set(contract.feeds(member))
        carried = {d.ident for d in DECISIONS if member in d.corpus}
        if not stated:
            findings.append(
                f"{MODULE} measures {', '.join(sorted(carried))} over `{member}` and "
                f"{CONTRACT} sends it nowhere" if carried else
                f"{CONTRACT} sends `{member}` to no decision, so its Feeds cell moved")
            continue
        findings += [f"{CONTRACT} says `{member}` feeds {ident} and {MODULE} does not "
                     f"measure {ident} over it" for ident in sorted(stated - carried)]
        findings += [f"{MODULE} measures {ident} over `{member}` and {CONTRACT} does "
                     "not send it there" for ident in sorted(carried - stated)]
    return findings


# The parameter keys that name the decision spending them, which is four of the eight
# and is the half a set comparison cannot hold: FD-1's and FD-2's candidate sets are
# interchangeable to a set and are not interchangeable to a sweep.
_PARAM_DECISION_RE = re.compile(r"\bFD-\d+\b")


def _names(text: str, symbol: str) -> bool:
    """Whether a section names a declared symbol, in any of the three ways §6 writes
    one: backticked in a body sentence, bold in a threshold lead-in, or bare."""
    return re.search(rf"(?<![\w-]){re.escape(symbol)}(?![\w-])", text) is not None


def _thresholds(contract: Contract) -> list[str]:
    """Each declared parameter against the decision that spends it, not merely against
    the set of decisions that spend something.

    Two readings, because §8's keys are written two ways. A key naming an `FD-n` is
    that decision's by its own name. A key written as a backticked symbol is bound by
    §6, which states in each decision's own section which floor it applies, so the
    binding is held by containment in both directions: a decision applying `T-enc`
    whose section says `T-form` is a 0.5% opcode floor spent where the contract puts a
    0.1% one, and no set comparison over §8's keys can see it.
    """
    findings: list[str] = []
    for row in contract.parameters:
        spenders = {d.ident for d in DECISIONS if row.ident in d.thresholds}
        named = _PARAM_DECISION_RE.search(row.ident)
        if named and spenders and spenders != {named.group()}:
            findings.append(
                f"{CONTRACT} declares `{row.ident}`, which names {named.group()}, and "
                f"{MODULE} applies it at {', '.join(sorted(spenders))}")
        if " " in row.ident:          # a prose key, bound by nothing but §8's own table
            continue
        for decision in DECISIONS:
            says = _names(contract.decision_text(decision.ident), row.ident)
            spends = row.ident in decision.thresholds
            if says and not spends:
                findings.append(f"{CONTRACT}'s §6 puts `{row.ident}` in "
                                f"{decision.ident}'s section and {MODULE} does not "
                                "apply it there")
            elif spends and not says:
                findings.append(f"{MODULE} applies `{row.ident}` at {decision.ident} "
                                f"and {CONTRACT}'s §6 does not name it in that "
                                "decision's section")
    return findings


def disagreements(contract: Contract) -> list[str]:
    """Where the instrument and its contract enumerate different things.

    The memberships, then the two relations a membership alone cannot hold: §2's Feeds
    column against the corpus each decision declares, and each declared parameter
    against the decision that spends it. Last, the one count the contract states in
    words beside an enumeration of its own, which is what keeps a member added to both
    sides at once from passing while the sentence that counts them stands.
    """
    findings = _memberships(contract) + _feeds(contract) + _thresholds(contract)
    stated = contract.stated_refusal_count()
    reasons = len(contract.refusals)
    if reasons and stated and stated != _WORDS.get(reasons, str(reasons)):
        findings.append(f"{CONTRACT}'s §5 enumerates {reasons} refusal reasons and says "
                        f"in the same section that {stated} are enumerated")
    return findings


_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
          8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}


def relations(contract: Contract) -> dict[str, int]:
    """The size of each relation the rule holds, for the floors group.

    The memberships have a floor apiece already, and the relations had none: a feeds
    loop deleted from the comparison narrows the rule to nine pairs with every gate
    still green, which is the *rule* going quiet rather than the document moving, and
    it is the one narrowing a floor under the relation's own size can see.
    """
    edges = sum(len(contract.feeds(row.ident)) for row in contract.members)
    bound = sum(1 for row in contract.parameters if " " not in row.ident
                for decision in DECISIONS
                if _names(contract.decision_text(decision.ident), row.ident))
    return {"freeze corpus feeds edges": edges,
            "freeze threshold bindings in §6": bound}

# The two joint pairs the register itself fixes and §3 declares the only exceptions to
# the one-knob rule, derived from the table above rather than restated beside it.
JOINT_PAIRS: tuple[frozenset[str], ...] = tuple(dict.fromkeys(
    frozenset((d.ident, d.joint_with)) for d in DECISIONS if d.joint_with))

# The nil row: struck ahead of the freeze, carried so the strike is visible, and with
# every byte and cycle column `n/a` (R-15-036n). A *measured* row against it is an
# amendment and not a freeze, which is what `G-5` rejects.
NIL_ROW_REGION = "RC-1"
NIL_ROW_SUBJECT = "the single-check multi-register save and restore"
NIL_ROW_GOVERNING = "R-15-036n"
NIL_ROW_GROUND = ("struck ahead of the freeze: the win is halved before any "
                  "measurement sees it and the residual is substitutive with FD-3's "
                  "outlining")

# The pending row: measured here and decided elsewhere, so it is a residual and not a
# verdict (§10).
PENDING_ROW_DECISION = "FD-8"
PENDING_ROW_ARTIFACT = "the §15 design-space exploration, which is deferred"

# The one member measured on the cycle axis, whose byte columns are `n/a` throughout and
# which is reported in this report rather than in a second one.
CYCLES_ONLY_MEMBER = "FM-6"
CYCLES_ONLY_DECISION = "FD-9"

# The one member §2 derives rather than builds, and what it is derived from: it carries
# that member's hash and adds a selector, so a row of its own waiting on a build waits on
# something §2 says will never happen.
DERIVED_MEMBER = "FM-5"
DERIVED_MEMBER_OF = "FM-1"

# The decision the recipe runs a second time after every other is taken. §1's ordering
# column reads "2, and again as the closing pass" for exactly this one, and that pass's
# S6 output is the realized dictionary the freeze records and the proof is taken with.
CLOSING_RESELECTION = "FD-1"

# The two site-varying policies R-15-036k names, which are FD-1's second knob and half
# of its curve. Selection by instance count admits single-use entries whenever indices
# remain; the marginal-value rule reserves them for recurring forms.
POLICIES: tuple[str, ...] = ("instance_count", "marginal_value")

# Which columns carry cycles and which carry bytes, so the two axis rules of §7 can be
# decided over a record rather than over a reading of it.
CYCLE_COLUMNS: frozenset[str] = frozenset({
    "wc_cycles_delta", "slot_width_cycles", "slot_headroom_cycles",
    "wc_cycles_frame_without", "wc_cycles_frame_with",
})
BYTE_COLUMNS: frozenset[str] = frozenset({
    "delta_bytes", "delta_pct_encoded", "delta_pct_encoded[FM-2]",
    "delta_pct_encoded[FM-3]", "delta_pct_encoded[FM-4]", "encoded_text_bytes",
    "canonical_text_bytes", BASELINE_BYTES, "bytes",
})
# A host-timing column is inadmissible anywhere in this report (§0, `G-9`), so the gate
# refuses the vocabulary rather than a list of column names somebody might not have used.
HOST_TIMING_RE = re.compile(r"(?i)host|wall.?clock|wall.?time|elapsed|nanosecond|"
                            r"perf.?counter|seconds")


# =====================================================================================
# the arithmetic that exists without the corpus
# =====================================================================================
#
# Everything below is computed from what the format and the register already fix. None
# of it is a measurement and none of it decides anything: the acceptance test is on the
# observation, and what these produce is the shape a candidate must satisfy whatever the
# observation turns out to be.

# The `C` counterfactual R-15-036 rests the exclusion on, and the canonical stream it is
# a share of. The bar is their product and is recomputed here rather than copied from
# the contract's sentence, which is what makes the contract's 22.4 checkable.
CANONICAL_BITS = 32
OPTIMISTIC_SHARE = 0.70
PESSIMISTIC_SHARE = 0.75

# The slot width the format leaves no room in: an escape is exactly two slots carrying
# one canonical 32-bit instruction verbatim, so 2w >= 32; any wider slot wastes
# 2(w - 16) bits on every escape and buys index space above the 2^16 dictionary bound.
# The value is §8's own and is read from its FD-2 candidate cell; this is the fallback
# for a caller with no contract in hand, and `slot_width_derivation` is what says why
# the number cannot be anything else.
SLOT_WIDTH = 16
DICTIONARY_INDEX_BOUND = 16          # log2 of the entries a slot can index


def optimistic_bar() -> float:
    """The acceptance bar in encoded bits per instruction, derived and not declared."""
    return OPTIMISTIC_SHARE * CANONICAL_BITS


def pessimistic_bar() -> float:
    """The figure reported beside the bar, which is not the bar."""
    return PESSIMISTIC_SHARE * CANONICAL_BITS


def slot_width_derivation() -> list[tuple[str, str, bool]]:
    """Why `w` is derived and not swept: each constraint, its arithmetic, and whether
    the reference width satisfies it."""
    return [
        ("an escape is two slots holding one canonical instruction verbatim",
         f"2w = {2 * SLOT_WIDTH} bits against {CANONICAL_BITS} canonical bits",
         2 * SLOT_WIDTH >= CANONICAL_BITS),
        ("a wider slot wastes escape bits and buys index space the profile has no use "
         "for", f"2(w - 16) = {2 * (SLOT_WIDTH - 16)} bits wasted per escape",
         SLOT_WIDTH <= 16),
        ("a slot must index the dictionary, which is bounded at 2^16 entries",
         f"w = {SLOT_WIDTH} against log2(N) at most {DICTIONARY_INDEX_BOUND}",
         SLOT_WIDTH >= DICTIONARY_INDEX_BOUND),
    ]


@dataclass(frozen=True)
class Geometry:
    """One `(h, k)` candidate, and the model over it.

    `per_slot` is R-15-036h's `w + h/k`, the bits an instruction pays for one slot with
    its share of the bundle header. `lambda_bound` is R-15-036j's `(2 - p)/(k - 1)`.
    `required_lambda` is the packing term the geometry may realize and still clear the
    bar at the register's break-even hit rate, and `min_p_at_bound` is the hit rate it
    would need if the packing were at its own worst case.
    """

    h: int
    k: int
    w: int
    bundle: int
    per_slot: float
    lambda_bound: float
    required_lambda: float
    min_p_at_bound: float
    min_p_unpacked: float
    legal: bool

    @property
    def clears_at_break_even(self) -> bool:
        """Whether the geometry clears the bar at the break-even hit rate for every
        packing term its own bound admits."""
        return self.required_lambda >= self.lambda_bound

    @property
    def infeasible_at_break_even(self) -> bool:
        """Whether it fails the bar at the break-even hit rate even with perfect
        packing, which no measurement can rescue."""
        return self.required_lambda < 0.0


def model_bits(per_slot: float, hit_rate: float, packing: float) -> float:
    """R-15-036h's slot model with R-15-036j's packing term: `(w + h/k)(2 - p + L)`."""
    return per_slot * (2.0 - hit_rate + packing)


def geometry(h: int, k: int, w: int = SLOT_WIDTH,
             p: float = 0.804) -> Geometry:
    """One candidate bundle geometry, scored against the derived bar.

    `legal` is FD-2's own structural constraint, `h >= k`, which holds because the
    header carries one escape-start bit per slot: a candidate below it is not a narrower
    search, it is a bundle whose header cannot say where its escapes begin.
    """
    per_slot = w + h / k
    bar = optimistic_bar()
    bound = (2.0 - p) / (k - 1) if k > 1 else float("inf")
    # the packing term that puts the model exactly on the bar at the break-even p
    required = bar / per_slot - (2.0 - p)
    # the hit rate that puts it on the bar with the packing at its own bound, and with
    # no packing loss at all; both are `2 - x` for the x each case solves to
    at_bound = bar / (per_slot * (1.0 + 1.0 / (k - 1))) if k > 1 else bar / per_slot
    return Geometry(
        h=h, k=k, w=w, bundle=h + w * k, per_slot=per_slot,
        lambda_bound=bound, required_lambda=required,
        min_p_at_bound=2.0 - at_bound, min_p_unpacked=2.0 - bar / per_slot,
        legal=h >= k,
    )


def candidate_geometries(contract: Contract) -> list[Geometry]:
    """The `(h, k)` pairs §8 declares, scored at the width and the break-even hit rate
    the contract itself states rather than at figures restated here."""
    stated = contract.parameter("FD-2 candidate set")
    pairs = [(int(a), int(b)) for a, b in re.findall(r"\((\d+),\s*(\d+)\)", stated)]
    width = contract.slot_width() or SLOT_WIDTH
    optimistic, _ = contract.break_even()
    return [geometry(h, k, width, optimistic or 0.804) for h, k in pairs]


def candidate_sizes(contract: Contract) -> list[int]:
    """The dictionary sizes §8 declares, as the powers of two its range names."""
    stated = contract.parameter("FD-1 candidate set for N")
    span = re.search(r"2\^(\d+) to 2\^(\d+)", stated)
    if not span:
        return []
    lo, hi = int(span.group(1)), int(span.group(2))
    return [1 << e for e in range(lo, hi + 1)]


def headroom_reserve(contract: Contract) -> float:
    """The share of N §8 requires be left unallocated at the freeze."""
    stated = contract.parameter("dictionary headroom reserve")
    share = re.search(r"([\d.]+)%", stated)
    return float(share.group(1)) / 100.0 if share else 0.0


def reserved_indices(size: int, reserve: float) -> int:
    """The indices a candidate N must leave unallocated. The reserve is a floor, so the
    division rounds up: a reserve rounded down is a reserve the freeze does not have."""
    return math.ceil(size * reserve)


@dataclass(frozen=True)
class Outlining:
    """One region length, and the site count at which outlining begins to pay.

    R-15-036p's arithmetic, stated as a column set by §6's FD-3: a region of `n`
    instructions at `m` site-invariant sites costs `nm` slots inline, `n + m + 1`
    outlined under a composition-time absolute call whose one target is one shared
    dictionary entry, and `n + 2m + 1` under a PC-relative one whose per-site
    displacement is a site-varying two-slot escape. `None` is *never pays*, which is a
    result and not a missing figure.
    """

    n: int
    break_even_absolute: int | None
    break_even_pcrelative: int | None


def outlining_break_even(lengths: Iterable[int]) -> list[Outlining]:
    """The site count at which each region length starts to pay, under both forms."""
    out: list[Outlining] = []
    for n in lengths:
        # nm > n + m + 1 <=> m(n - 1) > n + 1, and nm > n + 2m + 1 <=> m(n - 2) > n + 1
        absolute = (n + 1) // (n - 1) + 1 if n > 1 else None
        pcrelative = (n + 1) // (n - 2) + 1 if n > 2 else None
        out.append(Outlining(n=n, break_even_absolute=absolute,
                             break_even_pcrelative=pcrelative))
    return out


# =====================================================================================
# the three joined inputs, and the fixture that stands in for them
# =====================================================================================

# Where the analyzer looks for what §4 joins, and which of §4's three inputs each path
# carries. The paths are the instrument's own declaration rather than the contract's,
# the contract fixing the record's fields and leaving the transport to whoever streams
# it; they sit under a build tree no signing or storage path reads, because an image
# built under the provisional profile is a measurement artifact and is neither deployed
# nor stored (R-18-003c).
#
# **Three inputs arrive on four paths**, and the extra one is a circularity rather than
# a convenience: recovering a site's dictionary index or escape from the encoded image
# means decoding the bundle format, whose header width and slot count are exactly what
# FD-2 decides, so an analyzer that decoded the image would need the answer FD-1 and FD-2
# are jointly measuring. The composer knows the geometry it encoded at, so the encoded
# image is delivered as its bytes and a per-site encoding table beside them.
INPUTS: tuple[tuple[str, str, str, str, str], ...] = (
    ("sidecars", "build/freeze/sidecars.tsv",
     "the provenance sidecar stream from S1 and S4", "M1.2's backend",
     "the sidecar stream"),
    ("link_map", "build/freeze/link-map.tsv",
     "the link map from S5", "M1.4's linker", "the link map"),
    ("image", "build/freeze/image.bin",
     "the encoded image from S7", "M1.4's image composer", "the encoded image"),
    ("image_sites", "build/freeze/image-sites.tsv",
     "the composer's per-site encoding table", "M1.4's image composer",
     "the encoded image"),
)

# The three inputs §4 names, derived from the paths that carry them rather than counted
# beside them.
STREAMS: tuple[str, ...] = tuple(dict.fromkeys(row[4] for row in INPUTS))

# §4's record, in the line-oriented form this analyzer streams: one tab-separated row
# per emitted instruction site under a header naming these fields in this order, with
# `-` for a field the site does not carry.
SIDECAR_FIELDS: tuple[str, ...] = (
    "site_id", "unit", "compartment", "function", "opcode", "operand_class",
    "producer", "region_id", "region_class", "ct_arm", "knob",
)
LINK_MAP_FIELDS: tuple[str, ...] = ("site_id", "address", "bundle", "slot")
# The per-site encoding table is the composer's rather than the analyzer's, and the
# reason is a circularity worth naming: recovering a site's index or escape from the
# image means decoding the bundle format, whose header width and slot count are exactly
# what FD-2 decides, so an analyzer that decoded the image would need the answer FD-1 and
# FD-2 are jointly measuring. The composer knows the geometry it encoded at, so it emits
# the table beside the image.
IMAGE_SITE_FIELDS: tuple[str, ...] = ("site_id", "entry", "escape")


@dataclass(frozen=True)
class Site:
    """One joined emitted site: its provenance labels, its placement, its encoding.

    Two of §4's eleven fields are carried past what the join's own output needs, and
    each has a named consumer downstream: `opcode` is what FD-8's adjacency histogram
    is over, a pair being two opcodes emitted adjacently and not two words a
    disassembler matched, and `compartment` is what §5's *crosses a compartment*
    refusal is counted against. The three left behind, the unit, the enclosing
    function and the outlining region id, are the link map's and S4's business rather
    than this table's.
    """

    site_id: str
    operand_class: str
    region_class: str
    compartment: str
    opcode: str
    producer: str
    ct_arm: bool
    knob: str
    address: str
    bundle: int
    slot: int
    entry: str
    escape: bool


def _table(raw: str, fields: tuple[str, ...], what: str) -> list[dict[str, str]]:
    """A tab-separated table under a header naming exactly `fields`, in that order.

    The header is required rather than assumed: a stream whose columns moved would
    otherwise be read positionally into the wrong labels, and a mis-stratified hit rate
    that is precise is the one failure §4's whole schema exists to prevent.
    """
    lines = [line for line in raw.splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"{what} is empty")
    header = tuple(lines[0].split("\t"))
    if header != fields:
        raise ValueError(f"{what} heads its columns {header}, and this analyzer streams "
                         f"{fields}")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        cells = line.split("\t")
        if len(cells) != len(fields):
            raise ValueError(f"{what} carries a row of {len(cells)} cells under a "
                             f"{len(fields)}-column header")
        rows.append(dict(zip(fields, cells, strict=True)))
    return rows


@dataclass
class Join:
    """§4's join: one row per emitted site, and the residue that must be zero."""

    sites: list[Site] = field(default_factory=list)
    encoded_bytes: int = 0
    residue_sidecar_only: list[str] = field(default_factory=list)
    residue_image_only: list[str] = field(default_factory=list)
    producers: list[str] = field(default_factory=list)

    @property
    def residue(self) -> int:
        return len(self.residue_sidecar_only) + len(self.residue_image_only)

    def strata(self) -> dict[str, int]:
        counts = dict.fromkeys(OPERAND_CLASSES, 0)
        for site in self.sites:
            if site.operand_class in counts:
                counts[site.operand_class] += 1
        return counts

    def hits(self) -> dict[str, int]:
        counts = dict.fromkeys(OPERAND_CLASSES, 0)
        for site in self.sites:
            if site.operand_class in counts and not site.escape:
                counts[site.operand_class] += 1
        return counts


def join(sidecars: str, link_map: str, image: bytes, image_sites: str) -> Join:
    """The three inputs of §4, joined by `site_id`.

    Every site must join. A sidecar record with no image site, and an image site with no
    sidecar record, are each carried into the residue by name rather than dropped: an
    unjoined site is a stratum count that is silently wrong, which `G-2` rejects.
    """
    labels = _table(sidecars, SIDECAR_FIELDS, "the sidecar stream")
    placement = {row["site_id"]: row
                 for row in _table(link_map, LINK_MAP_FIELDS, "the link map")}
    encoding = {row["site_id"]: row
                for row in _table(image_sites, IMAGE_SITE_FIELDS,
                                  "the per-site encoding table")}

    out = Join(encoded_bytes=len(image))
    seen: set[str] = set()
    for row in labels:
        ident = row["site_id"]
        seen.add(ident)
        place, encode = placement.get(ident), encoding.get(ident)
        if place is None or encode is None:
            out.residue_sidecar_only.append(ident)
            continue
        out.sites.append(Site(
            site_id=ident,
            operand_class=row["operand_class"],
            region_class=row["region_class"],
            compartment=row["compartment"],
            opcode=row["opcode"],
            producer=row["producer"],
            ct_arm=row["ct_arm"] not in ("-", "", "0", "false"),
            knob=row["knob"],
            address=place["address"],
            bundle=int(place["bundle"]),
            slot=int(place["slot"]),
            entry=encode["entry"],
            escape=encode["escape"] not in ("-", "", "0", "false"),
        ))
    out.residue_image_only = sorted((set(encoding) | set(placement)) - seen)
    out.producers = sorted({site.producer for site in out.sites if site.producer != "-"})
    return out


# The fixture standing in for M1.2's and M1.4's outputs. It is deliberately tiny and
# deliberately unflattering: twelve sites cannot amortize a bundle header, so its
# encoded size equals its canonical size and it clears no bar. What it is for is the
# *wiring*, that the join runs, that the strata are stratified, that the residue is
# zero, and that every number it produces is marked `fixture` and refused by the gate.
FIXTURE_SIDECARS = "\n".join([
    "\t".join(SIDECAR_FIELDS),
    *[f"s{i:02d}\tunit.c\tcomp0\tfn{i // 4}\t{op}\t{cls}\t{prod}\t{region}\t{rc}\t"
      f"{arm}\t-"
      for i, (op, cls, prod, region, rc, arm) in enumerate((
          ("cmove", "OC-1", "regalloc", "-", "-", "-"),
          ("cmove", "OC-1", "regalloc", "r0", "RC-3", "-"),
          ("nop", "OC-1", "align", "-", "-", "-"),
          ("cincoffset", "OC-1", "framegen", "r0", "RC-3", "-"),
          ("csc", "OC-2", "framegen", "r1", "RC-1", "-"),
          ("csc", "OC-2", "framegen", "r1", "RC-1", "-"),
          ("addi", "OC-2", "constgen", "-", "-", "1"),
          ("cjal", "OC-3", "callgen", "-", "-", "-"),
          ("beq", "OC-3", "branchgen", "-", "-", "1"),
          ("auipcc", "OC-4", "globalgen", "-", "-", "-"),
          ("auipcc", "OC-4", "globalgen", "-", "-", "-"),
          ("cjal", "OC-5", "callgen", "-", "-", "-"),
      ), start=1)],
]) + "\n"

FIXTURE_LINK_MAP = "\n".join([
    "\t".join(LINK_MAP_FIELDS),
    *[f"s{i:02d}\t0x{0x80000000 + i * 4:08x}\t{bundle}\t{slot}"
      for i, (bundle, slot) in enumerate((
          (0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6),
          (1, 0), (1, 2), (1, 4), (2, 0), (2, 2),
      ), start=1)],
]) + "\n"

FIXTURE_IMAGE_SITES = "\n".join([
    "\t".join(IMAGE_SITE_FIELDS),
    *[f"s{i:02d}\t{entry}\t{escape}"
      for i, (entry, escape) in enumerate((
          ("7", "0"), ("7", "0"), ("0", "0"), ("11", "0"), ("23", "0"), ("23", "0"),
          ("4", "0"), ("-", "1"), ("-", "1"), ("-", "1"), ("-", "1"), ("31", "0"),
      ), start=1)],
]) + "\n"

# Three bundles at the reference instantiation, 128 bits each: sixteen slots used, one
# padding slot where the third escape could not straddle a bundle boundary, and four
# free slots at the end of the last bundle.
FIXTURE_BUNDLES = 3
FIXTURE_SLOTS_USED = 16
FIXTURE_SLOTS_PADDING = 1
FIXTURE_IMAGE = bytes(FIXTURE_BUNDLES * (16 + SLOT_WIDTH * 7) // 8)


def fixture_join() -> Join:
    """The join over the fixture, which is the wiring exercised end to end."""
    return join(FIXTURE_SIDECARS, FIXTURE_LINK_MAP, FIXTURE_IMAGE, FIXTURE_IMAGE_SITES)


@dataclass
class Inputs:
    """Where each of §4's three inputs came from, and what stood in where it did not."""

    found: dict[str, Path] = field(default_factory=dict)
    absent: list[str] = field(default_factory=list)
    joined: Join | None = None
    from_fixture: bool = False
    error: str = ""

    @property
    def complete(self) -> bool:
        return not self.absent

    @property
    def absent_streams(self) -> list[str]:
        """The §4 inputs short of a path, which is what a reader counts: the encoded
        image arrives on two and is one input either way."""
        short = {row[4] for row in INPUTS if row[0] in self.absent}
        return [stream for stream in STREAMS if stream in short]


def discover(root: Path, overrides: dict[str, Path | None]) -> Inputs:
    """Which of the joined inputs exist today, at the declared paths or an override."""
    out = Inputs()
    for name, default, _, _, _ in INPUTS:
        path = overrides.get(name) or (root / default)
        if path.is_file():
            out.found[name] = path
        else:
            out.absent.append(name)
    return out


def gather(root: Path, overrides: dict[str, Path | None], fixture: bool) -> Inputs:
    """The join, from the real inputs where they all exist and from the fixture where
    they do not. The two are never mixed: a stratum count half measured and half
    invented is precisely the mis-stratification §4 exists to refuse."""
    out = discover(root, overrides)
    try:
        if out.complete:
            out.joined = join(
                out.found["sidecars"].read_text(encoding="utf-8"),
                out.found["link_map"].read_text(encoding="utf-8"),
                out.found["image"].read_bytes(),
                out.found["image_sites"].read_text(encoding="utf-8"),
            )
        elif fixture:
            out.joined, out.from_fixture = fixture_join(), True
    except (OSError, ValueError) as exc:
        out.error = str(exc)
    return out


# =====================================================================================
# the record of §7, and its cells
# =====================================================================================

VALUE, FIXTURE, NA, PENDING = "value", "fixture", "n/a", "pending"


@dataclass(frozen=True)
class Cell:
    """One report cell, in one of the four states a cell can honestly be in.

    A `fixture` cell is a number the wiring produced from a synthetic input, and it is
    deliberately not a `value`: every predicate of §9 reads `measured` and not `shown`,
    so a fixture exercises the instrument without ever clearing the gate.
    """

    kind: str
    shown: str
    number: float | None = None
    ground: str = ""

    @property
    def measured(self) -> bool:
        return self.kind == VALUE

    @property
    def stated(self) -> bool:
        """Whether the cell says anything at all: a measurement, a fixture, or `n/a`.
        A pending cell states the symbol it waits on and no value."""
        return self.kind in (VALUE, FIXTURE, NA)

    def json(self) -> Json:
        if self.kind == NA:
            return "n/a"
        if self.kind == PENDING:
            return {"pending": self.shown}
        payload: Json = self.number if self.number is not None else self.shown
        return payload if self.kind == VALUE else {"fixture": payload}

    def show(self) -> str:
        if self.kind == PENDING:
            return f"pending on {self.shown}"
        return f"{self.shown} [fixture]" if self.kind == FIXTURE else self.shown


def num(value: float, digits: int = 0, fixture: bool = False) -> Cell:
    return Cell(FIXTURE if fixture else VALUE, f"{value:,.{digits}f}", float(value))


def text(value: str, fixture: bool = False) -> Cell:
    return Cell(FIXTURE if fixture else VALUE, value)


def flag(value: bool, fixture: bool = False) -> Cell:
    return Cell(FIXTURE if fixture else VALUE, "true" if value else "false",
                1.0 if value else 0.0)


def na(ground: str) -> Cell:
    """A cell whose axis does not apply. The ground travels with it, because `n/a` and
    a blank are indistinguishable to a reader who cannot see why."""
    return Cell(NA, "n/a", None, ground)


def pending(symbol: str) -> Cell:
    return Cell(PENDING, symbol)


# What a lookup finds where the record states nothing at all, so a reader of a block
# never has to tell a missing key from a pending one by its absence.
UNSTATED = Cell(PENDING, "nothing in this report states it")


@dataclass
class CorpusRow:
    """One §2 member, in the shape §7's `corpus` block asks for: hash, producer, pins,
    the mode, and the ground where the mode is not a build.

    `mode` is one of `in_place`, `standalone`, `derived`, `pending` or `absent`. §2 fixes
    the first two by the roster and the third for `FM-5`, which carries `FM-1`'s hash and
    adds a selector rather than a build; `pending` is a member the roster admits and no
    producer has built, and `absent` is the rejection `G-1` makes when no roster ground
    stands beside it.
    """

    ident: str
    member: str
    mode: str
    ground: str
    producer: str
    feeds: tuple[str, ...]
    digest: Cell
    pins: dict[str, Cell]
    stratum_sites: Cell

    def json(self) -> Json:
        return {"id": self.ident, "member": self.member, "mode": self.mode,
                "ground": self.ground, "producer": self.producer,
                "feeds": list(self.feeds), "hash": self.digest.json(),
                "pins": {k: v.json() for k, v in self.pins.items()},
                "stratum_sites": self.stratum_sites.json()}

    @property
    def pinned(self) -> bool:
        """Whether anything stands to rebuild the artifact from, which is the half of
        `G-7` a rebuild cannot recover from."""
        return bool(self.pins) and any(cell.stated for cell in self.pins.values())


@dataclass
class RecipeRow:
    step: str
    what: str
    tool: Cell
    input_hash: Cell
    output_hash: Cell
    records: dict[str, Cell]

    def json(self) -> Json:
        return {"step": self.step, "what": self.what, "tool": self.tool.json(),
                "in": self.input_hash.json(), "out": self.output_hash.json(),
                "recorded": {k: v.json() for k, v in self.records.items()}}


@dataclass
class RegionRow:
    ident: str
    what: str
    admitted: Cell
    refused: dict[str, Cell]
    columns: dict[str, Cell]
    struck: str = ""
    region_class: str = ""

    def json(self) -> Json:
        # the pair R-15-036p requires and the widening the schedule refuses are named
        # beside `refused` rather than buried in `columns`, which is §7's own skeleton
        return {"id": self.ident, "what": self.what, "admitted": self.admitted.json(),
                "delta_bytes": self.columns.get("delta_bytes", UNSTATED).json(),
                "wc_cycles_delta": self.columns.get("wc_cycles_delta", UNSTATED).json(),
                "slots_widened": self.columns.get("slots_widened", UNSTATED).json(),
                "refused": {k: v.json() for k, v in self.refused.items()},
                "columns": {k: v.json() for k, v in self.columns.items()
                            if k not in ("delta_bytes", "wc_cycles_delta",
                                         "slots_widened")},
                "struck": self.struck, "region_class": self.region_class}


@dataclass
class VariantRow:
    """One arm of a decision's procedure: the recipe at one setting of its knobs.

    `arm` is the variant §6's Procedure names, `diff` is the configuration diff `G-8`
    reads, and `s6_rerun` records the rule §3 calls its single most consequential and
    easiest to skip, S6 running inside the variant rather than the baseline's dictionary
    being inherited.
    """

    arm: str
    diff: tuple[str, ...]
    columns: dict[str, Cell]
    s6_rerun: Cell

    def json(self) -> Json:
        return {"arm": self.arm, "diff": list(self.diff),
                "s6_rerun": self.s6_rerun.json(),
                "columns": {k: v.json() for k, v in self.columns.items()}}


@dataclass
class DecisionBlock:
    ident: str
    question: str
    what: str
    order: int
    joint_with: str
    closing_pass: bool
    thresholds: tuple[str, ...]
    threshold_values: dict[str, str]
    default: str
    corpus_hash: Cell
    verdict: Cell
    variants: list[VariantRow]
    nil_rows: list[RegionRow] = field(default_factory=list)

    def json(self) -> Json:
        return {"id": self.ident, "question": self.question, "what": self.what,
                "order": self.order, "joint_with": self.joint_with,
                "closing_pass": self.closing_pass,
                "threshold": list(self.thresholds),
                "threshold_values": dict(self.threshold_values),
                "default": self.default, "corpus_hash": self.corpus_hash.json(),
                "verdict": self.verdict.json(),
                "variants": [v.json() for v in self.variants],
                "nil_rows": [r.json() for r in self.nil_rows]}


@dataclass
class Residual:
    what: str
    decided_by: str

    def json(self) -> Json:
        return {"what": self.what, "decided_by": self.decided_by}


@dataclass
class Record:
    """The report of §7, in its machine-readable rendering. The Markdown rendering is
    generated from this and never authored beside it."""

    mode: str
    manifest: dict[str, Cell]
    thresholds: dict[str, str]
    declared: dict[str, str]
    threshold_differences: dict[str, str]
    consumed: dict[str, Cell]
    corpus: list[CorpusRow]
    recipe: list[RecipeRow]
    provenance: dict[str, Cell]
    producers: list[str]
    regions: list[RegionRow]
    decisions: list[DecisionBlock]
    dictionary: dict[str, Cell]
    opcode_ledger: dict[str, Cell]
    residuals: list[Residual]

    def json(self) -> Json:
        return {
            "manifest": {**{k: v.json() for k, v in self.manifest.items()},
                         "mode": self.mode,
                         "thresholds": dict(self.thresholds),
                         "thresholds_declared": dict(self.declared),
                         "threshold_differences": dict(self.threshold_differences)},
            "corpus": [r.json() for r in self.corpus],
            "recipe": [r.json() for r in self.recipe],
            "provenance": {**{k: v.json() for k, v in self.provenance.items()},
                           "producers": list(self.producers)},
            "regions": [r.json() for r in self.regions],
            "decisions": [d.json() for d in self.decisions],
            "dictionary": {k: v.json() for k, v in self.dictionary.items()},
            "opcode_ledger": {
                "consumed": [{"instrument": k, "encodings": v.json()}
                             for k, v in self.consumed.items()],
                **{k: v.json() for k, v in self.opcode_ledger.items()}},
            "residuals": [r.json() for r in self.residuals],
        }

    def decision(self, ident: str) -> DecisionBlock | None:
        for block in self.decisions:
            if block.ident == ident:
                return block
        return None


def analyzer_version(root: Path) -> Cell:
    """The analyzer's own commit, which is what §7's manifest identifies it by.

    A working tree under edit names the commit it was read at with `-dirty` after it, the
    same way the emulator's revision stamp does (M0.10): a report generated from an
    edited checkout is not one a third party could reproduce, and saying so is cheaper
    than discovering it.
    """
    try:
        rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root,
                             capture_output=True, text=True, encoding="utf-8",
                             check=False, timeout=30)
        if rev.returncode != 0:
            return pending("a commit; this checkout has no HEAD to name one from")
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                               capture_output=True, text=True, encoding="utf-8",
                               check=False, timeout=60)
        mark = "-dirty" if dirty.returncode == 0 and dirty.stdout.strip() else ""
        return text(rev.stdout.strip() + mark)
    except (OSError, subprocess.SubprocessError):
        return pending("a commit; git did not answer")


def _member_mode(ident: str) -> tuple[str, str]:
    """A member's mode and the ground for it.

    Every buildable member is `pending` today and the ground is its producer's
    milestone, which is a different fact from `absent`: absent means the roster does not
    admit it and the report records the roster's ground, where these are admitted and
    unbuilt. `G-1` reads the difference, defers on the first and rejects the second.
    Which of `in_place` and `standalone` an admitted member takes is the roster's, and
    the roster arrives with `FM-1`.

    `FM-5` is the one member that is never any of those: §2 makes it the §4 provenance
    join applied to `FM-1`, so it carries `FM-1`'s hash and adds a selector rather than
    a build, and a row waiting on a build of it would wait on something §2 says will
    never happen.
    """
    if ident == DERIVED_MEMBER:
        return "derived", (f"the §4 provenance join over {DERIVED_MEMBER_OF}, which "
                           f"carries {DERIVED_MEMBER_OF}'s hash and adds a selector "
                           "rather than a build")
    return "pending", f"produced by {MEMBER_PRODUCER[ident]}, which has not run"


def build(root: Path, contract: Contract, inputs: Inputs) -> Record:
    """The report record, filled from what exists and pending on what does not."""
    fixture = inputs.from_fixture
    joined = inputs.joined
    declared = {row.ident: contract.parameter(row.ident) for row in contract.parameters}
    # in force is §8's own until something records a difference, which is what `G-12`
    # decides: the two are separate fields so that a report may state a threshold other
    # than the declared one and say so, rather than the difference being unrepresentable
    thresholds = dict(declared)

    manifest = {
        "corpus_id": pending("a built corpus; no member of §2 exists"),
        "corpus_hash": pending("every member's hash, the pins, and the tool versions"),
        "analyzer_version": analyzer_version(root),
        "backend_commit": pending("M1.2's re-homed backend"),
        "composer_commit": pending("M1.4's image composer"),
        "sail_model_revision": pending("a cycle column; none is measured"),
        "provisional_profile_revision": pending("a provisional-profile build"),
        "admitted_config_hash": pending("every decision in §6 taken, which is what the "
                                        "closing pass runs at"),
        "closing_pass_hash": pending("the closing pass, whose S6 output is the realized "
                                     "dictionary the freeze records (§3)"),
    }

    corpus: list[CorpusRow] = []
    for ident in MEMBERS:
        mode, ground = _member_mode(ident)
        derived = mode == "derived"
        corpus.append(CorpusRow(
            ident=ident,
            member=next((r.what for r in contract.members if r.ident == ident), ""),
            mode=mode, ground=ground, producer=MEMBER_PRODUCER[ident],
            feeds=contract.feeds(ident),
            digest=pending(f"{DERIVED_MEMBER_OF}'s hash, which this member carries"
                           if derived else f"a build of {ident}"),
            pins={pin: pending(f"a build of {ident}") for pin in _pins(contract, ident)},
            stratum_sites=(na("this member is derived from FM-1 by a selector")
                           if derived else
                           pending("the §4 join, which says which sites are this "
                                   "member's stratum of the composed image")),
        ))

    recipe = [
        RecipeRow(step=step,
                  what=next((r.what for r in contract.steps if r.ident == step), ""),
                  tool=pending("M1.2's backend" if step == "S1" else "M1.4's composer"),
                  input_hash=pending("a run of this step"),
                  output_hash=pending("a run of this step"),
                  records={name: pending("a run of this step")
                           for name in STEP_RECORDS[step]})
        for step in STEPS
    ]

    provenance = _provenance_block(contract, joined, fixture)

    regions = [
        RegionRow(
            ident=ident,
            what=next((r.what for r in contract.region_classes if r.ident == ident), ""),
            admitted=pending("a build with S4 enabled for this class alone"),
            refused={reason: pending("a run of S4") for reason in REFUSALS},
            columns={col: pending(_region_symbol(col))
                     for col in _decision("FD-3").columns if col != "refusal_counts"},
        )
        for ident in REGION_CLASSES
    ]

    decisions = [_decision_block(d, contract, thresholds) for d in DECISIONS]

    dictionary = {
        "N": pending("the closing pass at the admitted configuration"),
        "policy": pending("FD-1's selection policy, once a curve exists"),
        "entries_allocated": pending("a run of S6"),
        "indices_reserved": pending("a run of S6"),
        "trapping_range": pending("the realized N; indices above it trap (R-15-014)"),
        "config_hash": pending("the admitted configuration"),
        **{f"p_hit[{oc}]": provenance[f"p_hit[{oc}]"] for oc in OPERAND_CLASSES},
        "p_hit_invariant": provenance["p_hit_invariant"],
        "p_hit_varying": provenance["p_hit_varying"],
        "p_hit_aggregate": provenance["p_hit_aggregate"],
    }

    # §7's ledger is a list of the encodings each admitted instrument consumed, and the
    # list is empty because nothing is admitted; the two rows beside it are the profile's
    # own ledger, which this instrument reads rather than restates.
    ledger = {
        "remaining": pending("the profile's own custom-opcode ledger"),
        "trapping_range": pending("R-15-014's unallocated encodings, once one is spent"),
    }
    consumed = {d.ident: pending(f"a verdict at {d.ident}") for d in DECISIONS
                if "opcodes_consumed" in d.columns or d.ident == CYCLES_ONLY_DECISION}

    residuals = [
        Residual(f"{PENDING_ROW_DECISION}'s fusion-set admission",
                 PENDING_ROW_ARTIFACT),
        Residual("the realized packing term the density claim needs",
                 "a run of S7 at the admitted geometry"),
        Residual("the emitted adjacency histogram FD-8 selects against",
                 "the provenance join, once M1.2 emits the sidecar stream"),
    ]

    return Record(
        mode="fixture" if fixture else "pending",
        manifest=manifest, thresholds=thresholds, declared=declared,
        threshold_differences={}, consumed=consumed, corpus=corpus, recipe=recipe,
        provenance=provenance,
        producers=joined.producers if joined else [],
        regions=regions, decisions=decisions, dictionary=dictionary,
        opcode_ledger=ledger, residuals=residuals,
    )


def _region_symbol(column: str) -> str:
    if column in CYCLE_COLUMNS:
        return "the timing-annotated Sail model over an outlined partition"
    return "a build with S4 enabled for this class alone"


# §2's Pinned by column is prose per member, so what the report records is one cell per
# pin rather than one cell saying pins are pending: a hash recorded with no pins beside
# it reproduces from nothing, which is the half of `G-7` no rebuild recovers from.
_PIN_SPLIT_RE = re.compile(r",\s+(?![^(]*\))")


def _pins(contract: Contract, member: str) -> list[str]:
    """The pins §2 names for one member, read off its own Pinned by cell."""
    for row in contract.members:
        if row.ident == member and len(row.cells) >= 3:
            return [pin.strip() for pin in _PIN_SPLIT_RE.split(row.cells[2])
                    if pin.strip()]
    return []


def _decision(ident: str) -> Decision:
    for d in DECISIONS:
        if d.ident == ident:
            return d
    raise KeyError(f"no decision {ident} in this instrument")


def _provenance_block(contract: Contract, joined: Join | None,
                      fixture: bool) -> dict[str, Cell]:
    """§7's provenance block: the strata, the two-way split, and the join residue.

    This is the one block the join fills, because it is the one the wiring alone
    produces. Every cell it fills from the fixture is marked, and the gate reads the
    mark.

    **The two-way split is read and not declared.** R-15-036k's normative split is
    site-invariant against site-varying, and §4's Class column says which side each of
    the five strata is on, so a class moved from one side to the other in the contract
    moves here rather than agreeing with a tuple in this file.
    """
    if joined is None:
        symbol = "the provenance join of §4, over inputs M1.2 and M1.4 owe"
        return {
            **{oc: pending(symbol) for oc in OPERAND_CLASSES},
            "encoded_text_bytes": pending(symbol),
            "canonical_text_bytes": pending(symbol),
            "bits_per_instruction": pending(symbol),
            "invariant": pending(symbol), "varying": pending(symbol),
            "join_residue": pending(symbol), "instructions": pending(symbol),
            **{f"p_hit[{oc}]": pending(symbol) for oc in OPERAND_CLASSES},
            "p_hit_invariant": pending(symbol), "p_hit_varying": pending(symbol),
            "p_hit_aggregate": pending(symbol),
        }

    strata, hits = joined.strata(), joined.hits()
    varying = [oc for oc in OPERAND_CLASSES if contract.varying(oc)]
    invariant = [oc for oc in OPERAND_CLASSES if contract.varying(oc) is False]
    total = sum(strata.values())

    def rate(members: list[str]) -> Cell:
        seen = sum(strata[oc] for oc in members)
        if not seen:
            return na("no site in this stratum")
        return num(sum(hits[oc] for oc in members) / seen, 3, fixture)

    block: dict[str, Cell] = {oc: num(strata[oc], 0, fixture) for oc in OPERAND_CLASSES}
    block["invariant"] = num(sum(strata[oc] for oc in invariant), 0, fixture)
    block["varying"] = num(sum(strata[oc] for oc in varying), 0, fixture)
    block["join_residue"] = num(joined.residue, 0, fixture)
    block["instructions"] = num(total, 0, fixture)
    # The three the join alone gives: the encoder's output is an observation (§0's
    # third consequence), and its size and the canonical stream it is a share of are
    # the two figures the bar is stated over.
    block["encoded_text_bytes"] = num(joined.encoded_bytes, 0, fixture)
    block["canonical_text_bytes"] = num(total * CANONICAL_BITS // 8, 0, fixture)
    block["bits_per_instruction"] = (
        num(joined.encoded_bytes * 8 / total, 3, fixture) if total
        else na("no site joined, so there is nothing to divide by"))
    for oc in OPERAND_CLASSES:
        block[f"p_hit[{oc}]"] = rate([oc])
    block["p_hit_invariant"] = rate(invariant)
    block["p_hit_varying"] = rate(varying)
    block["p_hit_aggregate"] = rate(list(OPERAND_CLASSES))
    return block


def _arms(decision: Decision, contract: Contract) -> list[str]:
    """The variants §6's Procedure names for one decision, in the order it names them.

    FD-1's and FD-2's are derived from §8's declared candidate sets rather than named
    in the decision table, because they *are* those sets: FD-1's arms are the curve the
    freeze records, one per candidate N under each of the two site-varying policies, and
    FD-2's are the declared `(h, k)` geometries. A decision recording a chosen point and
    no curve is the report §6 forbids.
    """
    if decision.ident == "FD-1":
        return [f"N={size}/{policy}" for size in candidate_sizes(contract)
                for policy in POLICIES]
    if decision.ident == "FD-2":
        return [f"bundle={g.bundle}" for g in candidate_geometries(contract)]
    return list(decision.arms)


def _decision_block(decision: Decision, contract: Contract,
                    thresholds: dict[str, str]) -> DecisionBlock:
    variants = [
        VariantRow(arm=arm,
                   # the baseline moves nothing, which is what makes it the baseline,
                   # and every other arm moves the decision's own knobs and no others
                   diff=() if arm == "baseline" else decision.knobs,
                   columns={col: _column_cell(decision, col)
                            for col in decision.columns},
                   s6_rerun=(na("the baseline is what the variants are measured against")
                             if arm == "baseline"
                             else pending("a run of S6 inside this variant (§3)")))
        for arm in _arms(decision, contract)
    ]
    nil: list[RegionRow] = []
    if decision.ident == "FD-3":
        nil.append(RegionRow(
            # keyed by the requirement that struck it rather than by the region class
            # it would have been measured over, which the same report carries as a live
            # row: one id under two opposite treatments is a reader's trap
            ident=NIL_ROW_GOVERNING, what=NIL_ROW_SUBJECT,
            admitted=na(NIL_ROW_GROUND),
            refused={reason: na(NIL_ROW_GROUND) for reason in REFUSALS},
            columns={col: na(NIL_ROW_GROUND) for col in decision.columns
                     if col != "refusal_counts"},
            struck=NIL_ROW_GOVERNING, region_class=NIL_ROW_REGION,
        ))
    # FD-8's verdict is pending on a different thing from every other row's, and the
    # difference is the point: the others wait on a measurement this instrument will
    # take, and that one waits on an exploration whose decision is not this report's
    # (§10). Both are pending cells, because a verdict nobody has taken is not a value.
    verdict = pending(PENDING_ROW_ARTIFACT
                      if decision.ident == PENDING_ROW_DECISION
                      else "a measured variant pair")
    return DecisionBlock(
        ident=decision.ident, question=decision.question, what=decision.what,
        order=decision.order, joint_with=decision.joint_with,
        closing_pass=decision.ident == CLOSING_RESELECTION,
        thresholds=decision.thresholds,
        threshold_values={k: thresholds.get(k, "") for k in decision.thresholds
                          if k != DERIVED},
        default=decision.default,
        corpus_hash=pending("a post-S4 build of FM-1"),
        verdict=verdict, variants=variants, nil_rows=nil,
    )


def _column_cell(decision: Decision, column: str) -> Cell:
    """What a column carries today: `n/a` where its axis does not apply, and otherwise
    the symbol it waits on rather than a blank.

    The axis rule is decided per decision and not per column name, because the same
    `delta_bytes` is a measurement on FD-5 and an inapplicable cell on FD-9: `rcstep`'s
    carriage is decided on the cycle axis over a stream corpus that is not an image, and
    its byte columns are `n/a` throughout (§2, §6).
    """
    if decision.ident == CYCLES_ONLY_DECISION and column in BYTE_COLUMNS:
        return na(f"{CYCLES_ONLY_DECISION} is decided on the cycle axis over "
                  f"{CYCLES_ONLY_MEMBER}, which is not an image")
    stratum = _STRATUM_RE.search(column)
    if stratum and stratum.group(1) not in decision.corpus:
        return na(f"§2 does not send `{stratum.group(1)}` to {decision.ident}, so this "
                  "stratum is not one of its corpus")
    if column in CYCLE_COLUMNS:
        return pending("the timing-annotated Sail model (M0.9) over "
                       + _CYCLE_SUBJECT.get(decision.ident, "a built partition"))
    if column in ("bits_per_instruction_model", "model_residual"):
        return pending("R-15-036h's slot model over a measured p and packing term")
    return pending(f"a built {decision.corpus[0]} and a variant pair")


# What a decision's cycle columns are taken over, which is not one thing: FD-3's are the
# partitions an outlined site lands in, FD-9's are the decoder over the conformance
# streams, and FD-5's is recorded and never scored, R-15-067b saying in as many words
# that the insert form's dependent chain is not what admits the instruction.
_CYCLE_SUBJECT: dict[str, str] = {
    "FD-3": "every partition containing an outlined site",
    "FD-5": "the insert form's dependent chain, recorded and not scored (R-15-067b)",
    "FD-6": "the collapsed bounds-then-use sequence, recorded and not scored",
    "FD-9": f"the decoder over {CYCLES_ONLY_MEMBER}'s streams at each admitted tuple",
}

# A column measuring one corpus member as a stratum of another names it in brackets.
_STRATUM_RE = re.compile(r"\[(FM-\d+)\]")


# =====================================================================================
# the gate of §9
# =====================================================================================

PASS, REJECT, DEFERS = "pass", "REJECT", "defers"


@dataclass(frozen=True)
class Verdict:
    """One predicate's answer: what it decided, and why in one clause."""

    predicate: str
    outcome: str
    why: str


type Predicate = Callable[[Record], Verdict]


def _verdict(ident: str, outcome: str, why: str) -> Verdict:
    return Verdict(ident, outcome, why)


def _cells(record: Record) -> list[tuple[str, str, Cell]]:
    """Every cell of the record, with the block and the column name it sits under.

    Total over the record rather than over the blocks a column rule usually reads,
    because `G-9`'s host-timing prohibition is over the whole report (§0) and a column
    added to a recipe step's recorded quantities is a column the report carries exactly
    as one added to a decision's variant is.
    """
    out: list[tuple[str, str, Cell]] = [("manifest", k, v)
                                        for k, v in record.manifest.items()]
    for row in record.corpus:
        out += [(f"corpus/{row.ident}", "hash", row.digest),
                (f"corpus/{row.ident}", "stratum_sites", row.stratum_sites)]
        out += [(f"corpus/{row.ident}", f"pins[{k}]", v) for k, v in row.pins.items()]
    for step in record.recipe:
        out += [(f"recipe/{step.step}", k, v) for k, v in step.records.items()]
        out += [(f"recipe/{step.step}", "tool", step.tool),
                (f"recipe/{step.step}", "in", step.input_hash),
                (f"recipe/{step.step}", "out", step.output_hash)]
    for row in record.regions:
        out += [(f"regions/{row.ident}", k, v) for k, v in row.columns.items()]
        out += [(f"regions/{row.ident}", f"refused[{k}]", v)
                for k, v in row.refused.items()]
    for block in record.decisions:
        for variant in block.variants:
            out += [(f"decisions/{block.ident}/{variant.arm}", k, v)
                    for k, v in variant.columns.items()]
            out.append((f"decisions/{block.ident}/{variant.arm}", "s6_rerun",
                        variant.s6_rerun))
        for nil in block.nil_rows:
            out += [(f"decisions/{block.ident}/nil", k, v)
                    for k, v in nil.columns.items()]
    out += [("provenance", k, v) for k, v in record.provenance.items()]
    out += [("dictionary", k, v) for k, v in record.dictionary.items()]
    out += [("opcode_ledger", k, v) for k, v in record.opcode_ledger.items()]
    return out


def g1(record: Record) -> Verdict:
    """A corpus member some decision feeds, absent with no roster ground recorded."""
    fed = {member for d in DECISIONS for member in d.corpus}
    missing = [row.ident for row in record.corpus
               if row.ident in fed and row.mode == "absent" and not row.ground]
    if missing:
        return _verdict("G-1", REJECT,
                        f"{', '.join(missing)} feed a decision, are absent, and record "
                        "no roster ground for the absence (R-18-003c)")
    unbuilt = [row.ident for row in record.corpus if row.mode == "pending"]
    if unbuilt:
        return _verdict("G-1", DEFERS,
                        f"{len(unbuilt)} of {len(record.corpus)} members are admitted "
                        "and unbuilt, each naming the producer that has not run; which "
                        "of in_place and standalone each takes is the roster's, and the "
                        "roster arrives with FM-1")
    return _verdict("G-1", PASS, "every member a decision feeds is present or grounded")


def g2(record: Record) -> Verdict:
    """A provenance stratum with no count, or a nonzero join residue."""
    absent = [oc for oc in OPERAND_CLASSES if oc not in record.provenance]
    if absent:
        return _verdict("G-2", REJECT,
                        f"the provenance block carries no count for {', '.join(absent)}; "
                        "a zero is a value and an absence is a rejection (R-15-036k)")
    residue = record.provenance.get("join_residue")
    if residue is not None and residue.measured and residue.number:
        return _verdict("G-2", REJECT,
                        f"the join residue is {residue.shown} and every site must join")
    unmeasured = [oc for oc in OPERAND_CLASSES if not record.provenance[oc].measured]
    if unmeasured or residue is None or not residue.measured:
        return _verdict("G-2", DEFERS,
                        "the strata and the residue come from the §4 join, whose three "
                        "inputs M1.2 and M1.4 owe")
    return _verdict("G-2", PASS, "every stratum carries a count and the residue is zero")


def g3(record: Record) -> Verdict:
    """An admitted region class lacking either half of its bytes-and-cycles pair."""
    broken: list[str] = []
    deferred = 0
    for row in record.regions:
        if not row.admitted.measured:
            deferred += 1
            continue
        if row.admitted.number != 1.0:
            continue
        for half in ("delta_bytes", "wc_cycles_delta"):
            cell = row.columns.get(half)
            if cell is None or not cell.measured:
                broken.append(f"{row.ident} is admitted and carries no {half}")
    if broken:
        return _verdict("G-3", REJECT, "; ".join(broken) + " (R-15-036p)")
    if deferred:
        return _verdict("G-3", DEFERS,
                        f"{deferred} region classes carry no admission yet, S4 not "
                        "having run")
    return _verdict("G-3", PASS, "every admitted region class carries both halves")


def g4(record: Record) -> Verdict:
    """A decision row with no block, or a block carrying a blank where §6 wants a
    column. The delta-item half of `G-4` is K-70's, which holds R-15-014a's closed
    enumeration against §1 and §10; what is decided here is the record's own shape."""
    missing = [d.ident for d in DECISIONS if record.decision(d.ident) is None]
    if missing:
        return _verdict("G-4", REJECT,
                        f"{', '.join(missing)} has no decision row (R-15-014a)")
    blanks: list[str] = []
    deferred = 0
    for decision in DECISIONS:
        block = record.decision(decision.ident)
        if block is None:
            continue
        for variant in block.variants:
            for column in decision.columns:
                cell = variant.columns.get(column)
                if cell is None:
                    blanks.append(f"{decision.ident}/{variant.arm} carries a blank "
                                  f"where §6 requires `{column}`")
                elif not cell.stated:
                    deferred += 1
    if blanks:
        return _verdict("G-4", REJECT,
                        "; ".join(blanks[:3]) + (" (and more)" if len(blanks) > 3 else ""))
    if deferred:
        return _verdict("G-4", DEFERS,
                        f"{deferred} required columns name the symbol they wait on, "
                        "which is not a blank and not a measurement")
    return _verdict("G-4", PASS, "every column §6 requires carries a value or `n/a`")


def g5(record: Record) -> Verdict:
    """A measured multi-register save and restore, which is an amendment (R-18-034).

    §9 states two halves and only one of them is a property of a report: whether a
    decision row names a choice outside R-15-014a's closed delta is a question about the
    *register's* enumeration, and K-70 already decides it, holding every delta item
    against the contract's §1 and §10 on every checker run. What is left here is the
    half the register singles out, the struck candidate, and the verdict says so rather
    than claiming the whole condition.
    """
    measured: list[str] = []
    for block in record.decisions:
        for nil in block.nil_rows:
            measured += [f"{block.ident}'s nil row states `{name}`"
                         for name, cell in nil.columns.items()
                         if name in BYTE_COLUMNS | CYCLE_COLUMNS and cell.stated
                         and cell.kind != NA]
    if measured:
        return _verdict("G-5", REJECT,
                        "; ".join(measured) + f", and {NIL_ROW_GOVERNING} struck the "
                        "candidate ahead of the freeze, so this is an amendment")
    carried = sum(len(block.nil_rows) for block in record.decisions)
    if not carried:
        return _verdict("G-5", REJECT,
                        f"the report carries no nil row for {NIL_ROW_SUBJECT}, so the "
                        f"strike {NIL_ROW_GOVERNING} took is recorded nowhere")
    return _verdict("G-5", PASS,
                    f"the strike is carried as {carried} nil row with every byte and "
                    "cycle column `n/a`; whether a row names a choice outside the closed "
                    "delta is K-70's, over the register's own enumeration")


def g6(record: Record) -> Verdict:
    """FD-3 not first, or a byte-axis decision measured against a pre-S4 corpus.

    Both halves, and the second is decided against the post-S4 image S4's own step
    records rather than against nothing: every byte-axis decision but FD-3 is measured
    over the corpus S4 produced, so its recorded corpus hash is that step's output hash
    and a decision recording another image's is one measured before the transform that
    changes it (§3's second binding rule, R-15-036p).
    """
    ordered = sorted(record.decisions, key=lambda b: (b.order, b.ident))
    if not ordered or ordered[0].ident != "FD-3":
        first = ordered[0].ident if ordered else "nothing"
        return _verdict("G-6", REJECT,
                        f"the recorded order takes {first} first where §1 fixes FD-3, "
                        "whose transform changes the corpus every later row is measured "
                        "against (R-15-036p)")
    post_s4 = next((step.output_hash for step in record.recipe if step.step == "S4"),
                   UNSTATED)
    byte_axis = [b for b in record.decisions
                 if b.ident not in ("FD-3", CYCLES_ONLY_DECISION)]
    if post_s4.measured:
        wrong = [b.ident for b in byte_axis
                 if b.corpus_hash.measured and b.corpus_hash.shown != post_s4.shown]
        if wrong:
            return _verdict("G-6", REJECT,
                            f"{', '.join(wrong)} is measured on the byte axis against a "
                            "corpus that is not S4's output, so the transform FD-3 "
                            "decides had not run over it (R-15-036p)")
    unmeasured = [b.ident for b in byte_axis if not b.corpus_hash.measured]
    if unmeasured or not post_s4.measured:
        return _verdict("G-6", DEFERS,
                        f"FD-3 is first as §1 fixes; {len(unmeasured)} of "
                        f"{len(byte_axis)} byte-axis corpus hashes and S4's own output "
                        "hash wait on a build")
    return _verdict("G-6", PASS, "FD-3 is first and every byte-axis decision's corpus "
                                 "hash is S4's output")


def g7(record: Record) -> Verdict:
    """A recorded artifact hash that does not reproduce from its recorded pins.

    The rebuild is the CI gate's act rather than this analyzer's, so the half decided
    here is the half a rebuild cannot recover from: a hash recorded with no pins beside
    it reproduces from nothing at all, and a corpus nobody can rebuild is a corpus nobody
    can re-measure at the next amendment (§3).
    """
    unpinned = [row.ident for row in record.corpus
                if row.digest.measured and not row.pinned]
    if unpinned:
        return _verdict("G-7", REJECT,
                        f"{', '.join(unpinned)} records a hash and no pins, so the "
                        "artifact reproduces from nothing (main-spec §9)")
    stated = [row.ident for row in record.corpus if row.digest.measured]
    if not stated:
        return _verdict("G-7", DEFERS,
                        "no artifact hash is recorded, so there is nothing to rebuild "
                        "and re-hash")
    return _verdict("G-7", DEFERS,
                    f"{len(stated)} recorded hashes are pinned and want a rebuild, "
                    "which is the CI gate's own act and not this analyzer's")


def g8(record: Record) -> Verdict:
    """A variant pair whose recorded diff names more than one knob.

    The exemption is the *pair's* and not the block's. §3 declares exactly two joint
    pairs, so a decision inside one may move the two knobs that pair moves and no
    others; reading the exemption as a licence for any number of knobs at any of the
    four decisions in those pairs would let a joint decision move a third knob and
    still pass, which is a delta nobody can attribute.
    """
    allowed = {ident: {knob for member in pair
                       for knob in _decision(member).knobs}
               for pair in JOINT_PAIRS for ident in pair}
    offenders: list[str] = []
    for block in record.decisions:
        licence = allowed.get(block.ident, set(_decision(block.ident).knobs))
        for variant in block.variants:
            stray = [knob for knob in variant.diff if knob not in licence]
            if stray:
                offenders.append(f"{block.ident}/{variant.arm} moves "
                                 f"{', '.join(stray)}, which is no knob of its own "
                                 "decision or of the pair it is joint with")
            elif len(variant.diff) > 1 and block.ident not in allowed:
                offenders.append(f"{block.ident}/{variant.arm} moves "
                                 f"{len(variant.diff)} knobs")
    if offenders:
        return _verdict("G-8", REJECT, "; ".join(offenders[:3]) + " (§3, one knob per "
                                                                  "variant)")
    total = sum(len(block.variants) for block in record.decisions)
    return _verdict("G-8", PASS,
                    f"all {total} declared variants move one knob, or the two knobs of "
                    f"the {len(JOINT_PAIRS)} joint pairs the register fixes and no "
                    "others")


def g9(record: Record) -> Verdict:
    """A cycle column with no Sail model revision, or a host-timing column anywhere."""
    host = [f"{where}/{name}" for where, name, _ in _cells(record)
            if HOST_TIMING_RE.search(name)]
    if host:
        return _verdict("G-9", REJECT,
                        f"{', '.join(host[:3])} is a host-timing column, which is "
                        "inadmissible anywhere in this report")
    revision = record.manifest.get("sail_model_revision")
    measured = [name for _, name, cell in _cells(record)
                if name in CYCLE_COLUMNS and cell.measured]
    if measured and (revision is None or not revision.measured):
        return _verdict("G-9", REJECT,
                        f"{len(measured)} cycle columns are measured and the manifest "
                        "names no Sail model revision")
    if revision is None or not revision.measured:
        return _verdict("G-9", DEFERS,
                        "no host-timing column stands anywhere; the model revision "
                        "arrives with the first measured cycle column")
    return _verdict("G-9", PASS,
                    "every cycle column names the model revision and no host-timing "
                    "column stands")


def g10(record: Record) -> Verdict:
    """An aggregate hit rate in a row carrying no stratified split (R-15-036k)."""
    for where, block in (("provenance", record.provenance),
                         ("dictionary", record.dictionary)):
        aggregate = block.get("p_hit_aggregate")
        if aggregate is None or not aggregate.stated:
            continue
        absent = [oc for oc in OPERAND_CLASSES
                  if not block.get(f"p_hit[{oc}]", UNSTATED).stated]
        if absent:
            return _verdict("G-10", REJECT,
                            f"the {where} block states an aggregate hit rate and no "
                            f"split for {', '.join(absent)}")
    return _verdict("G-10", PASS,
                    "no aggregate hit rate stands without its stratified split")


def g11(record: Record) -> Verdict:
    """A frozen dictionary block selected at other than the admitted configuration.

    The two things held are a *configuration* hash apiece, and that is the whole of the
    predicate: §3's closing pass runs the recipe once more at the admitted knob settings
    and its S6 output is the realized dictionary, so what the dictionary block records is
    the configuration it was selected at and what the manifest records is the admitted
    one. A corpus hash is an image and is neither, which is why they are separate fields.
    """
    block_hash = record.dictionary.get("config_hash")
    admitted = record.manifest.get("admitted_config_hash")
    if block_hash is None:
        return _verdict("G-11", REJECT,
                        "the dictionary block records no configuration hash, so the "
                        "realized dictionary is the sweep's and not the machine's")
    if admitted is None:
        return _verdict("G-11", REJECT,
                        "the manifest records no admitted configuration, so the frozen "
                        "dictionary is held against nothing (R-15-036i)")
    if not (block_hash.measured and admitted.measured):
        return _verdict("G-11", DEFERS,
                        "the closing pass has not run, so there is no realized "
                        "dictionary to hold against an admitted configuration")
    if block_hash.shown != admitted.shown:
        return _verdict("G-11", REJECT,
                        "the frozen dictionary was selected at a configuration that is "
                        "not the admitted one, so it is an artifact of the sweep "
                        "(R-15-036i)")
    return _verdict("G-11", PASS,
                    "the frozen dictionary is the closing pass's at the admitted "
                    "configuration")


def g12(record: Record) -> Verdict:
    """A threshold in the report differing from §8 without the difference recorded.

    Held as the contract states it: the values *in force* and the values §8 *declares*
    are two fields, so a report may run at a threshold other than the declared one and
    say so, and one that runs at another value silently is the rejection. `build` sets
    the two equal and records no difference, which is what a report taken at §8's own
    numbers looks like.
    """
    blank = [key for key, value in record.thresholds.items() if not value]
    if blank:
        return _verdict("G-12", REJECT,
                        f"the manifest reprints no value for {', '.join(blank)}, which "
                        "§8 declares")
    silent = [f"`{key}` is in force at '{value}' where §8 declares "
              f"'{record.declared.get(key, '')}'"
              for key, value in record.thresholds.items()
              if value != record.declared.get(key, value)
              and key not in record.threshold_differences]
    if silent:
        return _verdict("G-12", REJECT, "; ".join(silent[:3])
                        + ", and no difference is recorded as such")
    applied = {k for d in DECISIONS for k in d.thresholds if k != DERIVED}
    unread = sorted(applied - set(record.thresholds))
    if unread:
        return _verdict("G-12", REJECT,
                        f"{', '.join(unread)} is applied by a decision and §8 declares "
                        "no such parameter")
    return _verdict("G-12", PASS,
                    f"all {len(record.thresholds)} thresholds in force are §8's own, and "
                    f"the {len(applied)} a decision applies are among them")


# Every predicate of §9, in the order the contract states them, each with what it
# rejects in the contract's own words. The table is the gate: a predicate the contract
# states and this table does not carry is a rejection nobody can make, which K-77
# reports in both directions.
PREDICATES: tuple[tuple[str, str, Predicate], ...] = (
    ("G-1", "a corpus member some decision feeds is absent with no roster ground", g1),
    ("G-2", "a provenance stratum has no count, or the join residue is nonzero", g2),
    ("G-3", "an admitted region class lacks either half of its pair", g3),
    ("G-4", "a delta item has no decision row, or a row carries a blank", g4),
    ("G-5", "a decision row names a choice outside the closed delta", g5),
    ("G-6", "the recorded order violates §1", g6),
    ("G-7", "a recorded artifact hash does not reproduce from its pins", g7),
    ("G-8", "a variant pair's configuration diff names more than one knob", g8),
    ("G-9", "a cycle column carries no model revision, or host timing appears", g9),
    ("G-10", "an aggregate hit rate appears with no stratified split", g10),
    ("G-11", "the frozen dictionary is not the closing pass's", g11),
    ("G-12", "a threshold differs from §8 without the difference recorded", g12),
)

PREDICATE_IDS: tuple[str, ...] = tuple(ident for ident, _, _ in PREDICATES)


def run_gate(record: Record) -> list[Verdict]:
    """Every predicate of §9 over one record, in the order the contract states them."""
    return [fn(record) for _, _, fn in PREDICATES]


# =====================================================================================
# the Markdown rendering, generated from the record
# =====================================================================================


def _md_row(cells: Iterable[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _md_table(header: tuple[str, ...], rows: Iterable[Iterable[str]]) -> list[str]:
    out = [_md_row(header), _md_row(["---"] * len(header))]
    out += [_md_row(row) for row in rows]
    return out


def markdown(record: Record, verdicts: list[Verdict], sentence: str) -> str:
    """The curator's rendering, generated from the record so the two cannot drift.

    §7 requires one report in two renderings generated together. This is the second, and
    it is generated from the first rather than written beside it: every cell it shows is
    `Cell.show()` over the same record the gate of §9 read.
    """
    out: list[str] = [
        "# The Profile-Freeze Measurement Report",
        "",
        f"*Mode: **{record.mode}**. This is not a freeze report.* {sentence}",
        "",
        "## manifest",
        "",
        *_md_table(("Field", "Value"),
                   [[k, v.show()] for k, v in record.manifest.items()]),
        "",
        *_md_table(("Threshold in force", "Value (§8)"),
                   [[k, v or "n/a"] for k, v in record.thresholds.items()]),
        "",
        "## corpus",
        "",
        # §7 asks this block for hash, producer, pins, and the mode or the ground that
        # excludes it, so all of them are here: a rendering thinner than the record is
        # two reports rather than two renderings of one
        *_md_table(("Id", "Member", "Producer", "Mode", "Ground", "Feeds", "Hash",
                    "Pins", "Stratum sites"),
                   [[r.ident, r.member, r.producer, r.mode, r.ground or "n/a",
                     ", ".join(r.feeds) or "n/a", r.digest.show(),
                     "; ".join(f"{k}: {v.show()}" for k, v in r.pins.items()) or "n/a",
                     r.stratum_sites.show()] for r in record.corpus]),
        "",
        "## recipe",
        "",
        *_md_table(("Step", "What it does", "Tool", "In", "Out", "Recorded"),
                   [[r.step, r.what, r.tool.show(), r.input_hash.show(),
                     r.output_hash.show(),
                     "; ".join(f"{k}: {v.show()}" for k, v in r.records.items())]
                    for r in record.recipe]),
        "",
        "## provenance",
        "",
        *_md_table(("Stratum", "Sites"),
                   [[k, v.show()] for k, v in record.provenance.items()]),
        "",
        f"Producers: {', '.join(record.producers) or 'n/a'}",
        "",
        "## regions",
        "",
        *_md_table(("Id", "Region class", "Admitted", "delta_bytes",
                    "wc_cycles_delta", "slots_widened", *REFUSALS),
                   [[r.ident, r.what, r.admitted.show(),
                     r.columns.get("delta_bytes", UNSTATED).show(),
                     r.columns.get("wc_cycles_delta", UNSTATED).show(),
                     r.columns.get("slots_widened", UNSTATED).show(),
                     *[r.refused.get(reason, UNSTATED).show() for reason in REFUSALS]]
                    for r in record.regions]),
        "",
        "## decisions",
        "",
        *_md_table(("Order", "Id", "What is decided", "Threshold", "Verdict"),
                   [[str(b.order), b.ident, b.what,
                     ", ".join(b.thresholds), b.verdict.show()]
                    for b in sorted(record.decisions, key=lambda b: (b.order, b.ident))]),
        "",
    ]
    for block in sorted(record.decisions, key=lambda b: (b.order, b.ident)):
        out += [f"### {block.ident}", "",
                f"Question: {block.question}", "",
                f"Default: {block.default}", ""]
        if block.closing_pass:
            out += ["This decision is taken again as the closing pass: after every "
                    "decision in §6 is taken, the recipe runs once more at the admitted "
                    "configuration, and *that* pass's S6 output is the realized "
                    "dictionary the freeze records.", ""]
        for nil in block.nil_rows:
            out += [f"Nil row ({nil.struck}): {nil.what}. {NIL_ROW_GROUND}. Every byte "
                    "and cycle column is `n/a`.", ""]
        if block.variants:
            columns = sorted({c for v in block.variants for c in v.columns})
            out += _md_table(("Arm", "Diff", "S6 re-run", *columns),
                             [[v.arm, ", ".join(v.diff) or "n/a", v.s6_rerun.show(),
                               *[v.columns[c].show() for c in columns]]
                              for v in block.variants])
            out.append("")
    out += [
        "## dictionary",
        "",
        *_md_table(("Field", "Value"),
                   [[k, v.show()] for k, v in record.dictionary.items()]),
        "",
        "## opcode_ledger",
        "",
        *_md_table(("Field", "Value"),
                   [[k, v.show()] for k, v in record.opcode_ledger.items()]),
        "",
        "## residuals",
        "",
        *_md_table(("Measured and not decided", "Decided by"),
                   [[r.what, r.decided_by] for r in record.residuals]),
        "",
        "## the gate of §9",
        "",
        *_md_table(("Predicate", "Outcome", "Why"),
                   [[v.predicate, v.outcome, v.why] for v in verdicts]),
        "",
    ]
    return "\n".join(out) + "\n"
