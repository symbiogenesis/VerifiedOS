#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the profile-freeze measurement instrument against the contract that defines it.

R-15-014a's second freeze act is a closed delta of nine items, six of which are
re-derived from measurement against generated output that does not exist until a
backend and a composed image do (R-18-003c).
docs/freeze-measurement-contract.md fixes what is measured, against what, and which
number separates a win from noise; this tool is the instrument it specifies.

**It cannot be run end to end and it says so.** §4's join takes three inputs, the
provenance sidecar stream from S1 and S4, the link map from S5, and the encoded
image from S7. Two of the three have a producer since M1.4-prime, `run.py model
freeze-emit` writing them; the sidecar stream is M1.2's backend and does not exist.
So no member of §2's corpus exists, no byte or cycle column is a measurement, and no
decision carries a verdict.

**Absence here is read off the build tree and the build tree is ignored output**, so a
stream with a producer reads absent until that producer has been run in this checkout.
The verdict line therefore states what *this* run found rather than what the repository
has landed, and the count in it moves with the working directory, which is what the
un-quarantine condition in this directory's README is stated against.

What runs today is the rest of it, in the shape `bank-dse.py` beside it established
at M0.17: the corpus, the recipe, the ordered act, the region classes and their
enumerated refusals, the report's two renderings, and the twelve CI predicates of §9
as predicates over the record, each able to reject a report and each naming what it
rejected. Every column whose operand does not exist prints **the symbol it waits
on** rather than a number or a blank, and the arithmetic the encoding format already
fixes is computed rather than deferred: the slot width's derivation, the hit rate
each declared bundle geometry needs to clear the derived bar, the dictionary
headroom each candidate N owes, and the site count at which outlining begins to pay
under each call form.

A fixture stands in for whatever the join does not find, so that the join is exercised
rather than merely written. Every cell it produces is marked `[fixture]`, no predicate of §9
treats a fixture cell as a measurement, and the verdict line says the report is not
a freeze.

Exit 0 where the instrument agrees with its contract, 1 on an instrument error: a
contract that will not parse, an enumeration this tool cannot read, or a membership
the two do not share. It may be run from anywhere: the repository root is found from
this file, never from the working directory.
"""

# ruff: noqa: N999
# The one rule this file has to differ on, and the reason: every command-line tool in
# this repository is named with a hyphen, and every one of them sat in `tools/`, which
# is not a package, so the name was never a module name. The quarantine is a package,
# because K-83 holds an import of it and an import needs something to name, so ruff now
# reads this script's filename as a module name and refuses the hyphen. The alternative
# was to rename the command, which would be the tool's user-facing name changed to suit
# a lint rule about a module nothing imports.

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# The tools import `vos` without being installed, so each puts `tools/` on the path
# first; a tool inside the quarantine puts the directory *above* its own there, which
# is the one that carries both `vos` and this package. Every import below this line is
# deliberately not at the top.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quarantine import freeze
from vos.corpus import find_root

# The region lengths the outlining break-even is tabulated over. One instruction can
# never pay and eight is already well past every idiom RC-1 and RC-2 name, so the table
# is short on purpose: what it shows is where the inequality turns, not a survey.
_REGION_LENGTHS = range(1, 9)


def _pending_inputs(inputs: freeze.Inputs) -> list[str]:
    lines: list[str] = []
    for name, default, what, producer, stream in freeze.INPUTS:
        found = inputs.found.get(name)
        where = str(found) if found else default
        state = "present" if found else "absent"
        lines.append(f"  {name:<12} {state:<8} {where:<28} {what}")
        lines.append(f"  {'':<12} {'':<8} {'':<28} carries {stream}"
                     + ("" if found else f", supplied by {producer}"))
    return lines


def _geometry_table(contract: freeze.Contract, out: list[str]) -> None:
    """The one substantive result the instrument can produce before the corpus exists.

    R-15-036h's slot model and R-15-036j's packing term are arithmetic over the
    geometry and the hit rate, so each declared `(h, k)` candidate can be scored against
    the derived bar at the break-even hit rate R-15-036k fixes, before anything is
    measured. This is a diagnostic and not the acceptance test: the bar is on the
    encoder's observed output and the model is reported beside it.
    """
    bar = freeze.optimistic_bar()
    p, pessimistic_p = contract.break_even()
    out.append(f"--- the bundle geometry, against the derived bar of {bar:.1f} bits per "
               f"instruction ---")
    out.append(f"  the bar is {freeze.OPTIMISTIC_SHARE:.0%} of a "
               f"{freeze.CANONICAL_BITS}-bit canonical stream (R-15-036), with the "
               f"pessimistic {freeze.PESSIMISTIC_SHARE:.0%} figure at "
               f"{freeze.pessimistic_bar():.1f} beside it and not the bar")
    out.append(f"  the break-even hit rates §6 states are {p} against the optimistic "
               f"figure and {pessimistic_p} against the pessimistic one; the columns "
               f"below are at {p}")
    out.append("")
    out.append("  w is derived and not swept, on three constraints the format fixes:")
    out.extend(f"    {'holds' if ok else 'FAILS':>5}  {why:<74}  {how}"
               for why, how, ok in freeze.slot_width_derivation())
    out.append("")
    out.append(f"  {'bundle':>7}  {'h':>3}  {'k':>3}  {'w':>3}  {'w+h/k':>7}  "
               f"{'L bound':>8}  {'L needed':>9}  {'min p, L=0':>11}  "
               f"{'min p, L at bound':>18}  at p={p}")
    for g in freeze.candidate_geometries(contract):
        needed = ("none" if g.infeasible_at_break_even else f"{g.required_lambda:.3f}")
        if not g.legal:
            standing = "illegal: h < k, so the header cannot carry one escape-start bit "\
                       "per slot"
        elif g.infeasible_at_break_even:
            standing = "fails for every packing term"
        elif g.clears_at_break_even:
            standing = "clears for every packing term"
        else:
            standing = f"clears while L is at most {g.required_lambda:.3f}"
        out.append(f"  {g.bundle:>7}  {g.h:>3}  {g.k:>3}  {g.w:>3}  {g.per_slot:>7.3f}  "
                   f"{g.lambda_bound:>8.3f}  {needed:>9}  {g.min_p_unpacked:>11.3f}  "
                   f"{g.min_p_at_bound:>18.3f}  {standing}")
    out.append("")
    out.append("  L is R-15-036j's expected padding slots per instruction, bounded above "
               "by (2 - p)/(k - 1); a 'min p' above 1 is a geometry no hit rate saves.")
    out.append(f"  'L needed' is the packing a geometry may realize and still clear the "
               f"bar at the p = {p} break-even R-15-036k fixes, and the two 'min p' "
               f"columns are the hit rate it would need with no packing loss at all and "
               f"with the loss at its own bound.")
    out.append("  This is R-15-036h's model and so a diagnostic: the acceptance test is "
               "on the encoder's observed output, which no build has produced.")


def _dictionary_table(contract: freeze.Contract, out: list[str]) -> None:
    reserve = freeze.headroom_reserve(contract)
    sizes = freeze.candidate_sizes(contract)
    out.append(f"--- the dictionary's candidate sizes, at the {reserve:.1%} headroom "
               f"reserve §8 declares ---")
    out.append(f"  {'N':>7}  {'index bits':>10}  {'reserved at least':>17}  "
               f"{'allocated at most':>17}  {'hit rate':>12}  {'entries':>12}")
    for n in sizes:
        reserved = freeze.reserved_indices(n, reserve)
        out.append(f"  {n:>7,}  {n.bit_length() - 1:>10}  {reserved:>17,}  "
                   f"{n - reserved:>17,}  {'pending on S6':>12}  "
                   f"{'pending on S6':>12}")
    out.append("")
    out.append("  Indices above the realized size trap (R-15-014, R-15-036i), so the "
               "reserve is cheap and its absence is not recoverable.")


def _outlining_table(out: list[str]) -> None:
    out.append("--- outlining, at the site count where R-15-036p's inequality turns ---")
    out.append("  a region of n instructions at m site-invariant sites costs n*m slots "
               "inline, n+m+1 outlined under a")
    out.append("  composition-time absolute call whose one target is one shared "
               "dictionary entry, and n+2m+1 under a")
    out.append("  PC-relative one whose per-site displacement is a site-varying two-slot "
               "escape.")
    out.append("")
    out.append(f"  {'region n':>9}  {'pays from m (absolute)':>23}  "
               f"{'slots inline':>13}  {'slots outlined':>15}  "
               f"{'pays from m (pc-relative)':>26}")
    for row in freeze.outlining_break_even(_REGION_LENGTHS):
        n, m = row.n, row.break_even_absolute
        absolute = str(m) if m else "never"
        pcrel = (str(row.break_even_pcrelative) if row.break_even_pcrelative
                 else "never")
        inline = f"{n * m:,}" if m else "n/a"
        outlined = f"{n + m + 1:,}" if m else "n/a"
        out.append(f"  {n:>9}  {absolute:>23}  {inline:>13}  {outlined:>15}  "
                   f"{pcrel:>26}")
    out.append("")
    out.append("  The realized n and m per region class are FD-3's to measure; what is "
               "computed here is where the inequality turns, which is not a measurement.")


def _act_table(record: freeze.Record, out: list[str]) -> None:
    out.append("--- the ordered act, in the order §1 fixes and G-6 checks ---")
    out.append(f"  {'order':>5}  {'id':<5}  {'joint':<6}  {'arms':>5}  "
               f"{'threshold':<38}  {'verdict'}")
    for block in sorted(record.decisions, key=lambda b: (b.order, b.ident)):
        thresholds = ", ".join(block.thresholds)
        out.append(f"  {block.order:>5}  {block.ident:<5}  "
                   f"{block.joint_with or 'n/a':<6}  {len(block.variants):>5}  "
                   f"{thresholds[:38]:<38}  {block.verdict.show()}")
    closing = [b.ident for b in record.decisions if b.closing_pass]
    out.append(f"  {'close':>5}  {', '.join(closing) or 'n/a':<5}  {'n/a':<6}  "
               f"{'1':>5}  {'the admitted configuration':<38}  "
               f"pending on every decision above being taken")
    out.append("")
    out.append("  The recipe's own order is S1 to S7, so a build composes and merges "
               "(S2, S3) before it selects a dictionary (S6); the order above is the "
               "*decisions'*, and FD-3 leads it because its transform changes the corpus "
               "every later row is measured against (R-15-036o, R-15-036p).")
    out.append("  The closing row is the same recipe run once more at the admitted "
               "configuration, whose S6 output is the realized dictionary the freeze "
               "records and the proof is taken with (§3).")


def _join_block(record: freeze.Record, inputs: freeze.Inputs, out: list[str]) -> None:
    source = ("the fixture standing in for M1.2's and M1.4's outputs"
              if inputs.from_fixture else "the inputs found at their declared paths")
    out.append(f"--- the provenance join of §4, over {source} ---")
    if record.provenance["OC-1"].kind == freeze.PENDING:
        out.append("  no join: " + record.provenance["OC-1"].shown)
        out.append("")
        return
    shown = (*freeze.OPERAND_CLASSES, "invariant", "varying", "instructions",
             "join_residue", *[f"p_hit[{oc}]" for oc in freeze.OPERAND_CLASSES],
             "p_hit_invariant", "p_hit_varying", "p_hit_aggregate")
    out.extend(f"  {key:<16} {record.provenance[key].show()}" for key in shown)
    out.append(f"  {'producers':<16} {', '.join(record.producers) or 'n/a'}")
    out.append("")
    out.append("  Every figure above is the wiring's and none is a measurement: no "
               "predicate of §9 reads a fixture cell as a value.")


def _gate_block(verdicts: list[freeze.Verdict], out: list[str]) -> None:
    out.append(f"--- the gate of §9, {len(verdicts)} predicates over the record above "
               f"---")
    out.extend(f"  {v.predicate:<5} {v.outcome:<8} {v.why}" for v in verdicts)


@dataclass
class Run:
    """One whole run, as data: the exit code, the console lines, and the record, gate
    and verdict sentence the other two renderings are generated from."""

    code: int
    out: list[str] = field(default_factory=list)
    record: freeze.Record | None = None
    verdicts: list[freeze.Verdict] = field(default_factory=list)
    sentence: str = ""


def report(root: Path, fixture: bool, overrides: dict[str, Path | None]) -> Run:
    """The instrument, run once against the contract that defines it."""
    out: list[str] = []
    contract = freeze.read(root)
    if not contract.present:
        return Run(1, [f"FAIL: {freeze.CONTRACT} is not in the repository, so this "
                       "instrument has no specification to run against"])

    # K-77 is the standing hold and reports the same disagreement on every run of this
    # directory's own gate;
    # this is the tool refusing to report about a set that is not its contract's,
    # because a report block nobody writes and an instrument measuring what nothing
    # asked for are both instrument errors rather than pending measurements. The
    # comparison itself lives beside the parse, so the two callers cannot come to ask
    # different questions of one document.
    findings = freeze.disagreements(contract)
    if findings:
        out.append(f"FAIL: the instrument and {freeze.CONTRACT} enumerate different "
                   f"things, in {len(findings)} place(s)")
        out.extend(f"       {f}" for f in findings)
        return Run(1, out)

    inputs = freeze.gather(root, overrides, fixture)
    if inputs.error:
        return Run(1, [f"FAIL: the §4 join could not be read: {inputs.error}"])

    record = freeze.build(root, contract, inputs)
    verdicts = freeze.run_gate(record)
    sentence = verdict_sentence(record, inputs, verdicts)

    out.append(f"=== the profile-freeze measurement instrument, against "
               f"{freeze.CONTRACT} ===")
    out.append("")
    out.append(f"--- the {len(freeze.STREAMS)} inputs §4 joins, on the "
               f"{len(freeze.INPUTS)} paths they arrive over ---")
    out.extend(_pending_inputs(inputs))
    out.append("  the encoded image arrives on two, because a site's index or escape "
               "cannot be recovered from the")
    out.append("  bundles before FD-2 fixes their geometry, and the composer knows the "
               "geometry it encoded at")
    out.append("")

    out.append(f"--- the corpus, {len(record.corpus)} members ---")
    out.append(f"  {'id':<5}  {'mode':<8}  {'feeds':<48}  {'hash'}")
    for row in record.corpus:
        out.append(f"  {row.ident:<5}  {row.mode:<8}  "
                   f"{', '.join(row.feeds) or 'n/a':<48}  {row.digest.show()}")
        out.append(f"  {'':<5}  {'':<8}  {'produced by ' + row.producer:<48}  "
                   f"pins: {', '.join(row.pins) or 'n/a'}")
    out.append("")

    out.append(f"--- the composition recipe, {len(record.recipe)} steps ---")
    for step in record.recipe:
        out.append(f"  {step.step:<3} {step.what}")
        out.append(f"      records {', '.join(step.records)}; "
                   f"{step.output_hash.show()}")
    out.append("")

    _act_table(record, out)
    out.append("")
    _geometry_table(contract, out)
    out.append("")
    _dictionary_table(contract, out)
    out.append("")
    _outlining_table(out)
    out.append("")
    _join_block(record, inputs, out)
    out.append("")

    out.append(f"--- the region classes, and the {len(freeze.REFUSALS)} enumerated "
               f"refusal reasons each carries a count for ---")
    out.extend(f"  {row.ident:<5}  admitted {row.admitted.show()}"
               for row in record.regions)
    out.append(f"  refusal reasons: {'; '.join(freeze.REFUSALS)}")
    out.append("")

    out.append("--- the rows that carry no measurement, and why each carries none ---")
    out.append(f"  nil row      {freeze.NIL_ROW_SUBJECT} ({freeze.NIL_ROW_GOVERNING}): "
               f"{freeze.NIL_ROW_GROUND}; every byte and cycle column n/a, and a "
               "measured row against it is an amendment (R-18-034)")
    out.append(f"  pending row  {freeze.PENDING_ROW_DECISION}'s fusion set: the "
               f"instrument owes it the emitted adjacency histogram, and admission is "
               f"{freeze.PENDING_ROW_ARTIFACT}")
    out.append(f"  cycles only  {freeze.CYCLES_ONLY_DECISION} over "
               f"{freeze.CYCLES_ONLY_MEMBER}: worst-case cycles per frame, byte columns "
               "n/a throughout, reported here rather than in a second report")
    out.append("")

    _gate_block(verdicts, out)
    out.append("")

    out.append("--- residuals ---")
    out.extend(f"  {r.what}: {r.decided_by}" for r in record.residuals)
    out.append("")

    out.append(sentence)
    return Run(0, out, record, verdicts, sentence)


def verdict_sentence(record: freeze.Record, inputs: freeze.Inputs,
                     verdicts: list[freeze.Verdict]) -> str:
    """What the run decided, and what it plainly cannot decide yet."""
    passed = sum(1 for v in verdicts if v.outcome == freeze.PASS)
    rejected = sum(1 for v in verdicts if v.outcome == freeze.REJECT)
    deferred = sum(1 for v in verdicts if v.outcome == freeze.DEFERS)
    measured = sum(1 for block in record.decisions if block.verdict.measured)
    absent = inputs.absent_streams
    source = ("a fixture standing in for them" if inputs.from_fixture
              else "nothing standing in for them")
    # The producers are read off §4's own input table rather than written out here.
    # They were written out, back when all three were absent and the sentence could name
    # all three at once; M1.4-prime landing two of them made that clause a claim about a
    # state the run was no longer in, which is the shape of stale statement no rule
    # reads and every reader believes. They are named as the schema's producers rather
    # than as who *owes* them for the same reason one step on: a stream is absent here
    # because nothing has written it into this checkout's ignored build tree, which says
    # nothing about whether its producer has landed.
    owed = ", ".join(dict.fromkeys(
        producer for _n, _p, _w, producer, stream in freeze.INPUTS
        if stream in absent))
    return (
        f"ok: the instrument is wired and cannot be run. {len(absent)} of "
        f"{len(freeze.STREAMS)} inputs the §4 join takes are absent, with {source}: "
        f"{', '.join(absent)}, whose producers are {owed}. So {measured} of "
        f"{len(record.decisions)} decisions carry a verdict, and of §9's "
        f"{len(verdicts)} predicates {passed} already decide, {deferred} defer on a "
        f"named symbol and {rejected} reject. This report is not a freeze."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the profile-freeze measurement instrument.")
    parser.add_argument("--json", action="store_true",
                        help="print the machine-readable record of §7 instead")
    parser.add_argument("--markdown", action="store_true",
                        help="print the curator's rendering, generated from that record")
    parser.add_argument("--no-fixture", action="store_true",
                        help="leave the §4 join pending rather than exercising it "
                             "against the fixture")
    for name, default, what, _, _ in freeze.INPUTS:
        parser.add_argument(f"--{name.replace('_', '-')}", type=Path, default=None,
                            metavar="PATH", help=f"{what} (default {default})")
    args = parser.parse_args(argv)

    overrides: dict[str, Path | None] = {
        name: getattr(args, name) for name, _, _, _, _ in freeze.INPUTS}
    run = report(find_root(), not args.no_fixture, overrides)

    if run.record is not None and args.json:
        # ensure_ascii off: the record quotes the contract's own section signs, and a
        # record whose text is escaped is a record a reader has to decode
        print(json.dumps(run.record.json(), indent=2, sort_keys=False,
                         ensure_ascii=False))
    elif run.record is not None and args.markdown:
        print(freeze.markdown(run.record, run.verdicts, run.sentence), end="")
    else:
        print("\n".join(run.out))
    return run.code


if __name__ == "__main__":
    sys.exit(main())
