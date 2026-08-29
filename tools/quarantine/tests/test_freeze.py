# SPDX-License-Identifier: Apache-2.0
"""The profile-freeze instrument: its arithmetic, its wiring, and its gate.

No checker rule reads this tool's output. K-77 holds its *enumerations* against the
contract's, which is membership; what a membership cannot decide is whether the
arithmetic is right, whether the join joins, and whether a CI predicate that reports
`pass` on today's record is capable of rejecting anything at all. That last one is
the case this module exists for: a gate of twelve predicates over a report nothing
has measured would report exactly the same twelve lines whether or not any of them
had a body, so each of the twelve is seeded a defect here and required to reject it
by name.

Three further groups. The derived arithmetic is pinned against figures the register
states in its own prose, so the slot model here and R-15-036h's there are held
together by a test rather than by a reading. The join is run twice, once over the
fixture and once over real files written at the declared paths, because a fixture
that exercised a different path from the real inputs would prove nothing about the
wiring. And the verdict sentence is pinned verbatim, for the reason `bank-dse.py`'s
is: the sentence saying the report is not a freeze is the one thing a reader takes
from the run, and nothing else holds it.
"""

import copy
import json
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path

from quarantine import freeze
from tests.harness import TOOLS, Case, ensure, sandbox_tree

# `TOOLS` is `tools/`, so the instruments this module runs are one directory below it.
QUARANTINE = TOOLS / "quarantine"

_ROOT = TOOLS.parent

# The reference instantiation R-15-036a states and R-15-036h's own figures are quoted
# at: a 128-bit bundle, a 16-bit header, seven 16-bit slots.
_REFERENCE = (16, 7)


@dataclass
class _Flow:
    contract: freeze.Contract | None = None
    record: freeze.Record | None = None


_FLOW = _Flow()


def _read() -> tuple[freeze.Contract, freeze.Record]:
    if _FLOW.contract is None or _FLOW.record is None:
        raise AssertionError("the setup case did not run or did not survive")
    return _FLOW.contract, _FLOW.record


def _setup() -> None:
    contract = freeze.read(_ROOT)
    ensure(contract.present, "the contract is in the repository")
    inputs = freeze.gather(_ROOT, {}, fixture=True)
    ensure(not inputs.error, f"the fixture join reads clean, got {inputs.error!r}")
    _FLOW.contract = contract
    _FLOW.record = freeze.build(_ROOT, contract, inputs)


def _mutated() -> freeze.Record:
    """A private copy of the record, so a seeded defect never reaches another case."""
    _, record = _read()
    return copy.deepcopy(record)


def _outcome(record: freeze.Record, predicate: str) -> freeze.Verdict:
    for verdict in freeze.run_gate(record):
        if verdict.predicate == predicate:
            return verdict
    raise AssertionError(f"the gate ran no predicate {predicate}")


def _rejects(record: freeze.Record, predicate: str, phrase: str) -> None:
    verdict = _outcome(record, predicate)
    ensure(verdict.outcome == freeze.REJECT,
           f"{predicate} must reject the seeded defect, got {verdict.outcome}: "
           f"{verdict.why}")
    ensure(phrase in verdict.why,
           f"{predicate} must name what it rejected; {phrase!r} is not in "
           f"{verdict.why!r}")


# =====================================================================================
# the arithmetic that exists without the corpus
# =====================================================================================


def _derived_bar() -> None:
    # 70% of a 32-bit canonical stream, and the pessimistic figure beside it. Both are
    # computed from their two operands rather than read out of the contract's sentence,
    # which is what makes the contract's 22.4 checkable at all.
    ensure(abs(freeze.optimistic_bar() - 22.4) < 1e-9,
           f"the bar is 22.4 bits per instruction, got {freeze.optimistic_bar()}")
    ensure(abs(freeze.pessimistic_bar() - 24.0) < 1e-9,
           f"the pessimistic figure is 24.0, got {freeze.pessimistic_bar()}")
    contract, _ = _read()
    raw = (_ROOT / freeze.CONTRACT).read_text(encoding="utf-8")
    ensure("**22.4 encoded bits per instruction**" in raw,
           "the contract states the bar this arithmetic gives")
    ensure(contract.parameter("T-enc").startswith("0.5%"),
           f"T-enc is 0.5%, got {contract.parameter('T-enc')!r}")


def _slot_width() -> None:
    # w = 16 is derived and not swept, and each of the three constraints holds at it.
    rows = freeze.slot_width_derivation()
    ensure(len(rows) == 3 and all(ok for _, _, ok in rows),
           f"all three slot-width constraints hold at w = {freeze.SLOT_WIDTH}: {rows}")


def _slot_model() -> None:
    # R-15-036h states its own reference figures in prose: the bare model is
    # 36.6 - 18.3p, and R-15-036j's packing term reaches 1/3 at p = 0, where the model
    # gives 42.67 bits per instruction against the bare model's 36.57. The model here is
    # held to all four rather than read beside them.
    h, k = _REFERENCE
    per_slot = freeze.SLOT_WIDTH + h / k
    bare_at_zero = freeze.model_bits(per_slot, 0.0, 0.0)
    packed_at_zero = freeze.model_bits(per_slot, 0.0, 1.0 / 3.0)
    ensure(abs(bare_at_zero - 36.57) < 0.005,
           f"the bare model at p = 0 is 36.57, got {bare_at_zero:.4f}")
    ensure(abs(packed_at_zero - 42.67) < 0.005,
           f"the packed model at p = 0 is 42.67, got {packed_at_zero:.4f}")
    ensure(abs(freeze.model_bits(per_slot, 1.0, 0.0) - per_slot) < 1e-9,
           "at p = 1 with no packing loss an instruction pays for exactly one slot")
    bound = freeze.geometry(h, k, p=0.0).lambda_bound
    ensure(abs(bound - 1.0 / 3.0) < 1e-9,
           f"the packing bound at p = 0 and k = 7 is 1/3, got {bound}")


def _geometry_verdicts() -> None:
    # The one substantive result the instrument can produce today. Of the three declared
    # candidates only the 256-bit bundle clears the bar at the break-even hit rate for
    # every admissible packing term; the reference 128-bit bundle needs a realized
    # packing at most 0.029 against a bound of 0.199; and the 64-bit bundle clears it at
    # no packing term at all, its header amortizing over three slots.
    contract, _ = _read()
    scored = {g.bundle: g for g in freeze.candidate_geometries(contract)}
    ensure(set(scored) == {64, 128, 256},
           f"the declared candidates are the 64-, 128- and 256-bit bundles, got "
           f"{sorted(scored)}")
    ensure(scored[64].infeasible_at_break_even,
           "the 64-bit bundle fails the bar at the break-even hit rate for every packing")
    ensure(abs(scored[64].min_p_unpacked - 0.95) < 0.001,
           f"with no packing loss the 64-bit bundle needs p = 0.95, got "
           f"{scored[64].min_p_unpacked:.4f}")
    ensure(abs(scored[128].required_lambda - 0.029) < 0.001,
           f"the reference bundle needs a packing term at most 0.029, got "
           f"{scored[128].required_lambda:.4f}")
    ensure(abs(scored[128].lambda_bound - 0.199) < 0.001,
           f"its own bound is 0.199, got {scored[128].lambda_bound:.4f}")
    ensure(not scored[128].clears_at_break_even,
           "so the reference bundle does not clear for every admissible packing")
    ensure(scored[256].clears_at_break_even,
           "the 256-bit bundle clears the bar at the break-even for every packing")
    ensure(all(g.bundle == g.h + g.w * g.k and g.h >= g.k
               for g in scored.values()),
           "every candidate satisfies bundle = h + wk and h >= k")


def _outlining() -> None:
    # R-15-036p's own worked case: a two-instruction region pays from four sites under
    # the absolute form and never under the PC-relative one.
    rows = {row.n: row for row in freeze.outlining_break_even(range(1, 6))}
    ensure(rows[2].break_even_absolute == 4,
           f"a two-instruction region pays from four sites, got "
           f"{rows[2].break_even_absolute}")
    ensure(rows[2].break_even_pcrelative is None,
           "and never under the PC-relative form")
    ensure(rows[1].break_even_absolute is None,
           "a one-instruction region never pays under either form")
    ensure((rows[3].break_even_absolute, rows[3].break_even_pcrelative) == (3, 5),
           f"a three-instruction region pays from three and five, got "
           f"{rows[3].break_even_absolute} and {rows[3].break_even_pcrelative}")
    # the inequality itself, at the site count the table returns and one below it
    for row in rows.values():
        m = row.break_even_absolute
        if m is None:
            continue
        ensure(row.n * m > row.n + m + 1, f"n={row.n} pays at m={m}")
        ensure(row.n * (m - 1) <= row.n + (m - 1) + 1,
               f"n={row.n} does not pay at m={m - 1}, so {m} is the break-even")


def _headroom() -> None:
    contract, _ = _read()
    reserve = freeze.headroom_reserve(contract)
    ensure(abs(reserve - 0.125) < 1e-9, f"the declared reserve is 12.5%, got {reserve}")
    ensure(freeze.reserved_indices(1024, reserve) == 128,
           "a 1,024-entry dictionary reserves 128 indices")
    ensure(freeze.reserved_indices(1000, reserve) == 125,
           "the reserve is a floor, so the division rounds up")
    sizes = freeze.candidate_sizes(contract)
    ensure(sizes == [1 << e for e in range(10, 17)],
           f"the candidate sizes are 2^10 to 2^16, got {sizes}")


# =====================================================================================
# the join, and the fixture that stands in for it
# =====================================================================================


def _fixture_join() -> None:
    joined = freeze.fixture_join()
    ensure(joined.strata() == {"OC-1": 4, "OC-2": 3, "OC-3": 2, "OC-4": 2, "OC-5": 1},
           f"the fixture strata are 4/3/2/2/1, got {joined.strata()}")
    ensure(joined.residue == 0, f"every fixture site joins, got {joined.residue}")
    ensure(len(joined.sites) == 12, f"twelve sites join, got {len(joined.sites)}")
    ensure(joined.encoded_bytes * 8
           == freeze.FIXTURE_BUNDLES * (16 + freeze.SLOT_WIDTH * 7),
           f"three bundles at the reference instantiation are 48 bytes, got "
           f"{joined.encoded_bytes}")
    ensure("callgen" in joined.producers and "-" not in joined.producers,
           f"the producer enumeration is reprinted, got {joined.producers}")

    # The fixture's own packing is a legal one, which is what makes it a stand-in for
    # the composer's output rather than a table of plausible numbers: an escape is two
    # slots and is bundle-contained (R-15-036a, R-15-036j), so no escape may start at
    # the last slot of a bundle, and a bundle left at one free slot before one is closed
    # with a padding slot.
    slots = sum(2 if site.escape else 1 for site in joined.sites)
    ensure(slots == freeze.FIXTURE_SLOTS_USED,
           f"the fixture occupies {freeze.FIXTURE_SLOTS_USED} slots, got {slots}")
    straddling = [s.site_id for s in joined.sites if s.escape and s.slot + 1 >= 7]
    ensure(not straddling, f"no escape straddles a bundle boundary, got {straddling}")
    occupied: dict[int, int] = {}
    for site in joined.sites:
        occupied[site.bundle] = occupied.get(site.bundle, 0) + (2 if site.escape else 1)
    last = max(occupied)
    padding = sum(7 - used for bundle, used in occupied.items() if bundle != last)
    ensure(padding == freeze.FIXTURE_SLOTS_PADDING,
           f"one padding slot closes the bundle an escape could not straddle, got "
           f"{padding}")


def _fixture_is_not_a_measurement() -> None:
    # The load-bearing property of the whole design: the fixture exercises the join and
    # no predicate of §9 may read one of its cells as a value.
    _, record = _read()
    filled = [key for key, cell in record.provenance.items()
              if cell.kind == freeze.FIXTURE]
    ensure(len(filled) >= len(freeze.OPERAND_CLASSES),
           f"the fixture fills the provenance block, got {filled}")
    ensure(not any(record.provenance[key].measured for key in filled),
           "and not one of those cells is a measurement")
    ensure(record.mode == "fixture", f"the record says so, got {record.mode!r}")


def _join_residue_is_reported() -> None:
    # A sidecar record with no image site and an image site with no sidecar record are
    # both carried by name rather than dropped, which is what G-2 then rejects.
    sidecars = freeze.FIXTURE_SIDECARS + (
        "s99\tunit.c\tcomp0\tfn9\tcmove\tOC-1\tregalloc\t-\t-\t-\t-\n")
    image_sites = freeze.FIXTURE_IMAGE_SITES + "s98\t3\t0\n"
    joined = freeze.join(sidecars, freeze.FIXTURE_LINK_MAP, freeze.FIXTURE_IMAGE,
                         image_sites)
    ensure(joined.residue_sidecar_only == ["s99"],
           f"the unplaced sidecar record is named, got {joined.residue_sidecar_only}")
    ensure(joined.residue_image_only == ["s98"],
           f"the unlabelled image site is named, got {joined.residue_image_only}")
    ensure(joined.residue == 2, f"the residue is two, got {joined.residue}")


def _header_is_required() -> None:
    # A stream whose columns moved would otherwise be read positionally into the wrong
    # labels, which is a hit rate that is precise and mis-stratified.
    moved = freeze.FIXTURE_SIDECARS.replace("operand_class", "operand_klass", 1)
    try:
        freeze.join(moved, freeze.FIXTURE_LINK_MAP, freeze.FIXTURE_IMAGE,
                    freeze.FIXTURE_IMAGE_SITES)
    except ValueError as err:
        ensure("heads its columns" in str(err),
               f"the refusal names the header, got {err}")
        return
    raise AssertionError("a stream with a moved header must be refused, not read")


def _real_inputs_are_not_a_fixture() -> None:
    # The same wiring over files at the declared paths: the join is a measurement then,
    # the record's mode says so, and G-2 stops deferring on the strata.
    files = {
        "docs/requirements-register.md": "# register stub for find_root\n",
        freeze.CONTRACT: (_ROOT / freeze.CONTRACT).read_text(encoding="utf-8"),
        "build/freeze/sidecars.tsv": freeze.FIXTURE_SIDECARS,
        "build/freeze/link-map.tsv": freeze.FIXTURE_LINK_MAP,
        "build/freeze/image-sites.tsv": freeze.FIXTURE_IMAGE_SITES,
        "build/freeze/image.bin": "\0" * len(freeze.FIXTURE_IMAGE),
    }
    with sandbox_tree(files) as root:
        contract = freeze.read(root)
        inputs = freeze.gather(root, {}, fixture=True)
        ensure(inputs.complete and not inputs.from_fixture and not inputs.error,
               f"all four inputs are found, got {inputs.absent} / {inputs.error!r}")
        record = freeze.build(root, contract, inputs)
        ensure(record.mode == "pending",
               f"a real join is not a fixture, got {record.mode!r}")
        ensure(record.provenance["OC-1"].measured,
               "and its strata are measurements")
        ensure(_outcome(record, "G-2").outcome == freeze.PASS,
               f"so G-2 decides rather than defers, got {_outcome(record, 'G-2').why}")


# =====================================================================================
# the gate: today's outcome, and one seeded defect per predicate
# =====================================================================================


def _gate_today() -> None:
    _, record = _read()
    verdicts = {v.predicate: v.outcome for v in freeze.run_gate(record)}
    ensure(len(verdicts) == 12, f"the gate runs twelve predicates, got {len(verdicts)}")
    deciding = sorted(k for k, v in verdicts.items() if v == freeze.PASS)
    ensure(deciding == ["G-10", "G-12", "G-5", "G-8"],
           f"four predicates already decide over today's record, got {deciding}")
    ensure(not [k for k, v in verdicts.items() if v == freeze.REJECT],
           f"and none rejects, got {verdicts}")
    ensure(all(v.why for v in freeze.run_gate(record)),
           "every predicate says why, whatever it decided")


def _g1() -> None:
    record = _mutated()
    record.corpus[0] = replace(record.corpus[0], mode="absent", ground="")
    _rejects(record, "G-1", "FM-1")


def _g2() -> None:
    record = _mutated()
    del record.provenance["OC-3"]
    _rejects(record, "G-2", "OC-3")
    other = _mutated()
    other.provenance["join_residue"] = freeze.num(3)
    for name in (*freeze.OPERAND_CLASSES,):
        other.provenance[name] = freeze.num(1)
    _rejects(other, "G-2", "the join residue is 3")


def _g3() -> None:
    record = _mutated()
    record.regions[0].admitted = freeze.flag(True)
    _rejects(record, "G-3", "delta_bytes")


def _g4() -> None:
    record = _mutated()
    record.decisions = [b for b in record.decisions if b.ident != "FD-7"]
    _rejects(record, "G-4", "FD-7")
    other = _mutated()
    block = other.decision("FD-5")
    ensure(bool(block is not None and block.variants), "FD-5 carries a variant to blank")
    if block is not None:
        del block.variants[0].columns["sites_extract"]
    _rejects(other, "G-4", "sites_extract")


def _g5() -> None:
    record = _mutated()
    block = record.decision("FD-3")
    ensure(bool(block is not None and block.nil_rows), "FD-3 carries the nil row")
    if block is not None:
        block.nil_rows[0].columns["delta_bytes"] = freeze.num(1024)
    _rejects(record, "G-5", "delta_bytes")
    other = _mutated()
    for candidate in other.decisions:
        candidate.nil_rows = []
    _rejects(other, "G-5", freeze.NIL_ROW_GOVERNING)


def _g6() -> None:
    record = _mutated()
    for block in record.decisions:
        if block.ident == "FD-3":
            block.order = 9
    _rejects(record, "G-6", "FD-3")
    # the second half, which is the one a reader of the order alone cannot see: a
    # byte-axis decision measured against an image S4 did not produce is one measured
    # before the transform FD-3 decides had run over it
    stale = _mutated()
    for step in stale.recipe:
        if step.step == "S4":
            step.output_hash = freeze.text("post-s4")
    for block in stale.decisions:
        block.corpus_hash = freeze.text("post-s4")
    ensure(_outcome(stale, "G-6").outcome == freeze.PASS,
           f"every byte-axis hash at S4's output passes, got "
           f"{_outcome(stale, 'G-6').why}")
    block = stale.decision("FD-5")
    ensure(block is not None, "FD-5 carries a block")
    if block is not None:
        block.corpus_hash = freeze.text("pre-s4")
    _rejects(stale, "G-6", "FD-5")


def _g7() -> None:
    # A hash recorded with no pins beside it reproduces from nothing at all, which is
    # the half of the rebuild no rebuild recovers from.
    record = _mutated()
    record.corpus[0] = replace(record.corpus[0], digest=freeze.text("abc123"), pins={})
    _rejects(record, "G-7", "FM-1")
    # and a pins map whose every entry is pending is a pin set nobody has recorded
    other = _mutated()
    other.corpus[0] = replace(other.corpus[0], digest=freeze.text("abc123"))
    _rejects(other, "G-7", "reproduces from nothing")


def _g8() -> None:
    record = _mutated()
    block = record.decision("FD-5")
    ensure(bool(block is not None and block.variants), "FD-5 carries a variant to widen")
    if block is not None:
        block.variants[0] = freeze.VariantRow(
            arm=block.variants[0].arm, diff=("bitfield_pair", "call_form"),
            columns=block.variants[0].columns,
            s6_rerun=block.variants[0].s6_rerun)
    _rejects(record, "G-8", "FD-5")
    # The exemption is the pair's and not the block's: FD-1 may move the two knobs its
    # pair with FD-2 moves and no third one, or a joint decision could move anything and
    # the delta would be unattributable while the gate reported green.
    joint = _mutated()
    inside = joint.decision("FD-1")
    ensure(bool(inside is not None and inside.variants), "FD-1 carries a variant")
    if inside is not None:
        inside.variants[0] = freeze.VariantRow(
            arm=inside.variants[0].arm,
            diff=("dictionary_size", "site_varying_policy"),
            columns=inside.variants[0].columns,
            s6_rerun=inside.variants[0].s6_rerun)
        ensure(_outcome(joint, "G-8").outcome == freeze.PASS,
               f"the pair's own two knobs are admitted, got "
               f"{_outcome(joint, 'G-8').why}")
        inside.variants[0] = freeze.VariantRow(
            arm=inside.variants[0].arm,
            diff=("dictionary_size", "site_varying_policy", "call_form"),
            columns=inside.variants[0].columns,
            s6_rerun=inside.variants[0].s6_rerun)
    _rejects(joint, "G-8", "call_form")


def _g9() -> None:
    record = _mutated()
    block = record.decision("FD-5")
    ensure(bool(block is not None and block.variants), "FD-5 carries a variant to widen")
    if block is not None:
        block.variants[0].columns["host_wall_time_ns"] = freeze.num(17)
    _rejects(record, "G-9", "host-timing")
    other = _mutated()
    region = other.regions[0]
    region.columns["wc_cycles_delta"] = freeze.num(400)
    _rejects(other, "G-9", "no Sail model revision")


def _g10() -> None:
    record = _mutated()
    del record.provenance["p_hit[OC-4]"]
    _rejects(record, "G-10", "OC-4")


def _g11() -> None:
    record = _mutated()
    del record.dictionary["config_hash"]
    _rejects(record, "G-11", "no configuration hash")
    absent = _mutated()
    del absent.manifest["admitted_config_hash"]
    _rejects(absent, "G-11", "no admitted configuration")
    # the realized dictionary selected somewhere other than the admitted configuration,
    # which is the freeze recording the sweep's answer rather than the machine's
    other = _mutated()
    other.dictionary["config_hash"] = freeze.text("deadbeef")
    other.manifest["admitted_config_hash"] = freeze.text("cafef00d")
    _rejects(other, "G-11", "artifact of the sweep")


def _g12() -> None:
    record = _mutated()
    record.thresholds["T-enc"] = ""
    _rejects(record, "G-12", "T-enc")
    other = _mutated()
    del other.thresholds["T-form"]
    _rejects(other, "G-12", "T-form")
    # the condition §9 actually states: a threshold in force that is not §8's, with no
    # difference recorded as such. The two are separate fields precisely so that this
    # is representable rather than true by construction.
    silent = _mutated()
    silent.thresholds["T-enc"] = "5% of `FM-1` encoded text"
    _rejects(silent, "G-12", "no difference is recorded")
    declared = _mutated()
    declared.thresholds["T-enc"] = "5% of `FM-1` encoded text"
    declared.threshold_differences["T-enc"] = "raised for this report, and here is why"
    ensure(_outcome(declared, "G-12").outcome == freeze.PASS,
           "a difference recorded as such is admitted, which is what §9 asks for")


# =====================================================================================
# the shape the record carries, beyond what any one predicate reads
# =====================================================================================


def _arms_are_the_procedures() -> None:
    # §6 states each decision's variants in its Procedure paragraph, and the record
    # carries a row for each: a decision recording a chosen point and no curve is the
    # report FD-1 forbids in as many words.
    contract, record = _read()
    counts = {b.ident: len(b.variants) for b in record.decisions}
    sizes, geometries = (len(freeze.candidate_sizes(contract)),
                         len(freeze.candidate_geometries(contract)))
    expected = {"FD-1": sizes * len(freeze.POLICIES), "FD-2": geometries,
                "FD-3": 1 + len(freeze.REGION_CLASSES), "FD-4": 2, "FD-5": 4,
                "FD-6": 2, "FD-7": 2, "FD-8": 1, "FD-9": 2}
    ensure(counts == expected, f"the arms are §6's own, got {counts}")
    # the baseline moves nothing, which is what makes it the baseline
    block = record.decision("FD-3")
    ensure(block is not None, "FD-3 carries a block")
    if block is not None:
        base = [v for v in block.variants if v.arm == "baseline"]
        ensure(len(base) == 1 and not base[0].diff and base[0].s6_rerun.kind == freeze.NA,
               f"FD-3's baseline moves no knob and re-runs no S6, got {base}")
    # and every other arm records the S3 rule §3 calls the easiest one to skip
    reruns = [v for b in record.decisions for v in b.variants if v.diff]
    ensure(all(v.s6_rerun.kind == freeze.PENDING for v in reruns),
           "every variant that moves a knob records S6 running inside it")


def _derived_member_is_not_built() -> None:
    # §2 makes FM-5 the provenance join over FM-1 rather than a build, so a row waiting
    # on a build of it waits on something §2 says will never happen.
    _, record = _read()
    row = next(r for r in record.corpus if r.ident == freeze.DERIVED_MEMBER)
    ensure(row.mode == "derived", f"FM-5 is derived, got {row.mode!r}")
    ensure(freeze.DERIVED_MEMBER_OF in row.digest.shown,
           f"and carries FM-1's hash, got {row.digest.show()!r}")
    ensure(row.stratum_sites.kind == freeze.NA,
           "a derived member has no stratum of its own to count")
    ensure(all(r.pins for r in record.corpus),
           "every member records the pins §2 names, so a hash has something to "
           "reproduce from")


def _split_is_read_not_declared() -> None:
    # R-15-036k's normative split is §4's Class column, and this module holds no second
    # copy of it: a class moved from one side to the other in the contract moves here.
    contract, _ = _read()
    varying = [oc for oc in freeze.OPERAND_CLASSES if contract.varying(oc)]
    ensure(varying == ["OC-3", "OC-4", "OC-5"],
           f"the contract puts three classes on the site-varying side, got {varying}")
    moved = freeze.parse(contract.raw.replace(
        "| `OC-5` | site-varying, composition-time absolute |",
        "| `OC-5` | site-invariant, composition-time absolute |"))
    inputs = freeze.gather(_ROOT, {}, fixture=True)
    record = freeze.build(_ROOT, moved, inputs)
    ensure(record.provenance["invariant"].number == 8.0,
           f"moving OC-5 across the split moves the count with it, got "
           f"{record.provenance['invariant'].show()}")


def _break_even_is_the_registers() -> None:
    # 0.804 is the register's and the contract restates it, so nothing here declares it.
    contract, _ = _read()
    optimistic, pessimistic = contract.break_even()
    ensure((optimistic, pessimistic) == (0.804, 0.728),
           f"the contract states both break-evens, got {optimistic} and {pessimistic}")
    register = (_ROOT / "docs" / "requirements-register.md").read_text(encoding="utf-8")
    ensure(f"fails below *p* = {optimistic}" in register,
           "and the optimistic one is the figure R-15-036k fixes")
    ensure(contract.slot_width() == freeze.SLOT_WIDTH,
           f"§8 fixes the slot width this module falls back to, got "
           f"{contract.slot_width()}")


def _relations_are_held() -> None:
    # The two pairs that are relations rather than memberships, each seeded a defect
    # here as well as in the selftest, because a relation dropped from the comparison
    # narrows K-77 with every gate still green.
    contract, _ = _read()
    ensure(not freeze.disagreements(contract), "the live pair agrees")
    fewer = freeze.parse(contract.raw.replace("| FD-5, FD-7 |", "| FD-5 |"))
    found = freeze.disagreements(fewer)
    ensure(any("FD-7" in f and "FM-4" in f for f in found),
           f"a Feeds cell short of a decision is a finding, got {found}")
    swapped = freeze.parse(contract.raw.replace(
        "**Threshold, declared: T-form**, the instruction being admitted",
        "**Threshold, declared: T-enc**, the instruction being admitted"))
    found = freeze.disagreements(swapped)
    ensure(any("T-enc" in f and "FD-7" in f for f in found),
           f"a floor bound to the wrong decision is a finding, got {found}")
    grown = freeze.parse(contract.raw.replace(
        "- **needs a frame**:", "- **wants a nap**: nothing\n- **needs a frame**:"))
    found = freeze.disagreements(grown)
    ensure(any("refusal reasons are enumerated" in f or "wants a nap" in f
               for f in found),
           f"a reason added to §5 moves its own count sentence, got {found}")


# =====================================================================================
# the tool, end to end
# =====================================================================================


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(root / "tools" / "quarantine" / "freeze-report.py"), *args],
        capture_output=True, encoding="utf-8", errors="replace", check=False,
        timeout=180)


def _live_run() -> None:
    done = _run(_ROOT)
    ensure(done.returncode == 0,
           f"the instrument agrees with its contract, got {done.returncode}: "
           f"{done.stderr!r}")
    ensure(done.stdout.startswith(
        "=== the profile-freeze measurement instrument, against "
        "docs/freeze-measurement-contract.md ===\n"),
        f"the header names the contract, got {done.stdout[:120]!r}")
    # The sentence a reader takes from the run, pinned because nothing else holds it.
    ensure(done.stdout.rstrip().endswith(
        "ok: the instrument is wired and cannot be run. 3 of 3 inputs the §4 join "
        "takes are absent, with a fixture standing in for them: the sidecar stream, "
        "the link map, the encoded image, of which the first is M1.2's backend and the "
        "other two are M1.4's linker and image composer. So 0 of 9 decisions carry a "
        "verdict, and of §9's 12 predicates 4 already decide, 8 defer on a named "
        "symbol and 0 reject. This report is not a freeze."),
        f"the verdict sentence must close the report verbatim, got "
        f"{done.stdout[-600:]!r}")


def _renderings_agree() -> None:
    # One report, two renderings, generated from one record and never authored apart.
    record = _run(_ROOT, "--json")
    curated = _run(_ROOT, "--markdown")
    ensure(record.returncode == 0 and curated.returncode == 0,
           "both renderings run clean")
    payload = json.loads(record.stdout)
    ensure(sorted(payload) == sorted(freeze.BLOCKS),
           f"the record carries §7's nine blocks, got {sorted(payload)}")
    ensure(payload["manifest"]["mode"] == "fixture",
           "the machine-readable rendering says the mode on its face")
    ensure("*Mode: **fixture**. This is not a freeze report.*" in curated.stdout,
           "and so does the curator's")
    for member in freeze.MEMBERS:
        ensure(f"| {member} |" in curated.stdout,
               f"the curator's rendering carries {member}")
    ensure("pending on" in curated.stdout,
           "and prints the symbol a cell waits on rather than a blank")


def _no_fixture_leaves_the_join_pending() -> None:
    done = _run(_ROOT, "--no-fixture", "--json")
    ensure(done.returncode == 0, f"a run with no fixture is clean, got {done.returncode}")
    payload = json.loads(done.stdout)
    ensure(payload["manifest"]["mode"] == "pending",
           f"and its mode is pending, got {payload['manifest']['mode']}")
    ensure("pending" in payload["provenance"]["OC-1"],
           f"with the strata pending, got {payload['provenance']['OC-1']}")


def _membership_is_an_instrument_error() -> None:
    # A contract stating a predicate the analyzer cannot make is not a pending
    # measurement: it is an instrument that would report about the wrong set.
    raw = (_ROOT / freeze.CONTRACT).read_text(encoding="utf-8")
    files = {
        "docs/requirements-register.md": "# register stub for find_root\n",
        freeze.CONTRACT: raw.replace("| `G-12` | a threshold value",
                                     "| `G-13` | a threshold value"),
        "tools/quarantine/freeze-report.py": (QUARANTINE / "freeze-report.py").read_text(
            encoding="utf-8"),
    }
    for rel in ("__init__.py", "freeze.py"):
        files[f"tools/quarantine/{rel}"] = (QUARANTINE / rel).read_text(encoding="utf-8")
    for rel in ("__init__.py", "jsonc.py", "corpus.py"):
        files[f"tools/vos/{rel}"] = (TOOLS / "vos" / rel).read_text(encoding="utf-8")
    with sandbox_tree(files) as root:
        done = _run(root)
        ensure(done.returncode == 1,
               f"a membership disagreement is an instrument error, got "
               f"{done.returncode}: {done.stdout!r}")
        ensure("states the CI predicate `G-13`" in done.stdout
               and "implements the CI predicate `G-12`" in done.stdout,
               f"and both directions are named, got {done.stdout!r}")


def cases() -> list[Case]:
    # the first case reads the contract and builds the record every later case copies
    return [
        Case("setup", _setup, lane="host"),
        Case("derived-bar", _derived_bar, lane="host"),
        Case("slot-width-derivation", _slot_width, lane="host"),
        Case("slot-model-reference-figures", _slot_model, lane="host"),
        Case("geometry-verdicts", _geometry_verdicts, lane="host"),
        Case("outlining-break-even", _outlining, lane="host"),
        Case("dictionary-headroom", _headroom, lane="host"),
        Case("fixture-join", _fixture_join, lane="host"),
        Case("fixture-is-not-a-measurement", _fixture_is_not_a_measurement,
             lane="host"),
        Case("join-residue-is-reported", _join_residue_is_reported, lane="host"),
        Case("sidecar-header-is-required", _header_is_required, lane="host"),
        Case("real-inputs-are-not-a-fixture", _real_inputs_are_not_a_fixture,
             lane="host"),
        Case("gate-over-todays-record", _gate_today, lane="host"),
        Case("G-1-rejects", _g1, lane="host"),
        Case("G-2-rejects", _g2, lane="host"),
        Case("G-3-rejects", _g3, lane="host"),
        Case("G-4-rejects", _g4, lane="host"),
        Case("G-5-rejects", _g5, lane="host"),
        Case("G-6-rejects", _g6, lane="host"),
        Case("G-7-rejects", _g7, lane="host"),
        Case("G-8-rejects", _g8, lane="host"),
        Case("G-9-rejects", _g9, lane="host"),
        Case("G-10-rejects", _g10, lane="host"),
        Case("G-11-rejects", _g11, lane="host"),
        Case("G-12-rejects", _g12, lane="host"),
        Case("arms-are-the-procedures", _arms_are_the_procedures, lane="host"),
        Case("derived-member-is-not-built", _derived_member_is_not_built, lane="host"),
        Case("split-is-read-not-declared", _split_is_read_not_declared, lane="host"),
        Case("break-even-is-the-registers", _break_even_is_the_registers, lane="host"),
        Case("relations-are-held", _relations_are_held, lane="host"),
        Case("live-run", _live_run, lane="host"),
        Case("renderings-agree", _renderings_agree, lane="host"),
        Case("no-fixture-leaves-the-join-pending", _no_fixture_leaves_the_join_pending,
             lane="host"),
        Case("membership-is-an-instrument-error", _membership_is_an_instrument_error,
             lane="host"),
    ]
