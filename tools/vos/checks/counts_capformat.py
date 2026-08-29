# SPDX-License-Identifier: Apache-2.0
"""counts, the capability format: every site that restates a frozen parameter.

The format is decided in Sail and transcribed into eight other artifacts, none of
which was held against anything. What is read here is the definition, the entry that
states the parameterization normatively, both packings, and every sentence writing
the field widths out as a sum; the widths themselves are `vos/capformat.py`'s parse
and no figure is written down in this module.
"""

import re
from typing import TYPE_CHECKING

from vos import capformat

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

# K-79: R-15-007's own statement of the parameterization, which is the normative one.
# The pattern captures the figure alone and the label is what a finding names, so a
# reworded entry is a finding rather than a comparison quietly dropped.
ENTRY_WIDTHS: tuple[tuple[str, str, str], ...] = (
    (r"a (\d+)-bit address", "cap_addr_width", "the address width"),
    (r"a (\d+)-bit object type", "cap_otype_width", "the object-type width"),
    (r"(\d+)-bit encoded permissions", "cap_perms_code_width",
     "the permission-code width"),
    (r"a (\d+)-bit exponent", "cap_E_width", "the exponent width"),
    (r"(\d+)-bit base and \d+-bit top mantissas", "cap_mantissa_width",
     "the base mantissa's width"),
    (r"\d+-bit base and (\d+)-bit top mantissas", "stored_mantissa_width",
     "the stored top mantissa's width"),
)


def cap_format(ctx: Context) -> None:
    """K-79: the frozen capability format's parameters, wherever one is written.

    The format is decided in three Sail files, `cap_format.sail` for the packed
    fields, `cap_common.sail` for the permission bitmap and the reserved object types,
    and `core/xlen.sail` for the register width the address field sits inside, and it
    is restated across eight other artifacts. Every one of those is a hand
    transcription and none of them was held against anything, which is the K-57 shape
    one level up: there the five sites of one parameter, here many sites of ten.

    Three things under one rule, because they are three readings of the same table and
    a defect in the format shows up in whichever of them the edit happened to reach.

      * Every site states the value the definition fixes, or the figure that value
        derives. Ten parameters, and three derived figures beside them: the
        capability's width in bits, the stored top mantissa, and the maximum effective
        exponent, which is stated at five sites and derived at none of them.
      * The six packed fields spend the capability exactly, at **both** packings, and
        again at every sentence that writes the sum out. This is the claim four
        artifacts rest on when they say the table has no reserved field, no
        software-defined permission field and no room for a revocation colour, and it
        is arithmetic rather than a reading: the fields sum to the width, they abut,
        and the low one ends at zero. A field shifted by a bit elaborates, decodes,
        and is a different capability at one exponent.
      * Both readings are over digits. The object-type class count and the count of
        classes composition may allocate are stated as **count-words** at four sites
        between them, "sixteen classes" and "thirteen composition-allocatable", and
        those are outside this rule rather than held by it. It is named here because a
        rule reaching some restatements and not others reports `ok` about a subject
        larger than the one it read.

    Fail-closed on the reading in K-57's and K-76's manner: a definition this rule can
    no longer find, a site whose pattern no longer matches or has come to match twice,
    a packing it cannot read, and a budget sentence it cannot place are each one
    finding that stops the comparison for what rests on it, never a pass over nothing.

    **Report-only, on three grounds and none of them K-57's first.** The model sites
    are under the `-text` tree, where a rewrite risks the line-ending sweep the tools'
    `newline=""` convention exists to prevent; that ground reaches two sites here and
    not the rest. R-15-007 is the normative statement of the parameterization, so
    rewriting it from the tool would delete the decision rather than check it, which is
    the ground K-57 already gives for the ceiling. And the ground that decides the
    remaining sites is the package itself: a width there is not a transcription that a
    token substitution completes. `CapAddrWidth` is written once and *spent* at the six
    packed-field slices, at the reset bounds, at the null transform and inside every
    shift in the bounds algebra, none of which this rule reads and none of which is
    arithmetic it could recompute. A repair that moved the localparam and left those
    would turn a loud finding into a package that elaborates and computes a different
    format, which is worse than the finding. Every other site states its width beside a
    consequence the width fixes, "spends the 64 bits exactly", "byte-exact to 128
    bytes at any base", "6 stored, high two derived", so a token substitution would
    leave the artifact describing a format it no longer carries: the half-a-sentence
    hazard that keeps K-70 report-only.

    What this rule does not decide is whether the *algorithm* agrees, which is
    `tools/rtl.py crosscheck`'s: the model emits its own answers and the package is
    required to reproduce every line. The two are complements and the split is the
    tool's reach rather than a preference. A drifted width is caught here, on the host,
    before anything is built; a drifted expression is caught there, under a toolchain
    the checker does not have and cannot acquire.
    """
    rep, reg = ctx.rep, ctx.reg
    fmt = capformat.read(ctx.root)
    findings: list[str] = []

    moved = [key for key, value in fmt.defined.items() if value is None]
    findings += [f"{key} is no longer declared in a form this rule reads, so there is "
                 "no definition to hold the sites against" for key in sorted(moved)]
    ctx.shared["cap_format_params"] = len(fmt.defined) - len(moved)

    # The derived figures, computed from the definition rather than read anywhere. A
    # site stating one of these is stating arithmetic and not a second decision.
    want: dict[str, int] = {k: v for k, v in fmt.defined.items() if v is not None}
    if not moved:
        size, mant = want["cap_size"], want["cap_mantissa_width"]
        want["cap_width"] = 8 * size
        want["stored_mantissa_width"] = mant - 2
        want["cap_max_E"] = (want["cap_addr_width"] + 1) - mant + 1
        want["perms_codepoints"] = 2 ** want["cap_perms_code_width"]

    held = 0
    for (label, key) in sorted(fmt.sites):
        found = fmt.sites[(label, key)]
        if found is None:
            findings.append(f"{label} no longer states {key} in a form this rule "
                            "reads")
        elif key not in want:
            continue                       # its definition has moved and is reported
        elif found != want[key]:
            findings.append(f"{label} states {found} where the model fixes "
                            f"{key} at {want[key]}")
        else:
            held += 1

    # R-15-007's own prose, read from the register the run already holds rather than
    # from a second trip to disk. It is the normative statement, so a disagreement here
    # is the one that says the *decision* has moved and not a copy of it.
    entry = reg.body.get("R-15-007", "")
    if not entry:
        findings.append("R-15-007 is not declared, so the parameterization has no "
                        "normative statement to hold the transcriptions against")
    else:
        for pattern, key, what in ENTRY_WIDTHS:
            found = re.search(pattern, entry)
            if found is None:
                findings.append(f"R-15-007 no longer states {what} in a form this rule "
                                "reads")
            elif key in want and int(found.group(1)) != want[key]:
                findings.append(f"R-15-007 states {what} as {found.group(1)} where the "
                                f"model fixes {key} at {want[key]}")
            elif key in want:
                held += 1

    # The packed form, at both packings, against the widths. Held in the order the
    # declaration writes rather than as a set, because the order is what a shifted
    # field breaks while every width still checks out.
    order = [("perms", "cap_perms_code_width"), ("otype", "cap_otype_width"),
             ("E", "cap_E_width"), ("B", "cap_mantissa_width"),
             ("T", "stored_mantissa_width"), ("address", "cap_addr_width")]
    for label in ("the model's own packing", "the package's packing"):
        packing = fmt.packings.get(label)
        if packing is None:
            findings.append(f"{label} is not readable as six fields at fixed slices, "
                            "so the width the format spends is held against nothing")
            continue
        if "cap_width" not in want:
            continue
        top = want["cap_width"] - 1
        for name, key in order:
            hi, lo = packing[name]
            if hi != top:
                findings.append(f"{label} puts {name} at bit {hi} where the fields "
                                f"above it end at {top + 1}")
            if key in want and (hi - lo + 1) != want[key]:
                findings.append(f"{label} gives {name} {hi - lo + 1} bits where the "
                                f"model fixes {key} at {want[key]}")
            top = lo - 1
        if top != -1:
            findings.append(f"{label} leaves bit {top} and below unspent, so the "
                            "format has a reserved field the register says it has not")

    # The sentences that write the sum out, which are the only places the "spends the
    # bits exactly" claim is stated as arithmetic rather than asserted. Each is held
    # term by term, because a sentence whose terms have drifted and whose total still
    # adds up is the one a reader would take on trust.
    for _, label, _ in capformat.BUDGETS:
        budget = fmt.budgets.get(label)
        if budget is None:
            findings.append(f"{label} no longer writes the field widths out as a sum "
                            "this rule can place, or writes more than one")
            continue
        terms, total = budget
        for name, found in zip(capformat.BUDGET_FIELDS, terms, strict=True):
            if name in want and found != want[name]:
                findings.append(f"{label} writes {name} as {found} where the model "
                                f"fixes it at {want[name]}")
        if sum(terms) != total:
            findings.append(f"{label} sums its own terms to {sum(terms)} and states "
                            f"{total}")
        elif "cap_width" in want and total != want["cap_width"]:
            findings.append(f"{label} spends {total} bits where the capability is "
                            f"{want['cap_width']}")
        else:
            held += 1
    ctx.shared["cap_format_sites"] = held

    rep.report("K-79", "capability-format site(s) disagreeing with the Sail "
               "definition:", findings,
               f"all {held} sites restating one of the "
               f"{ctx.shared.get('cap_format_params', 0)} frozen capability-format "
               f"parameters state what {capformat.CAP_FORMAT}, "
               f"{capformat.CAP_COMMON} and {capformat.XLEN_FILE} fix, both packings "
               f"and all {len(capformat.BUDGETS)} written-out budgets spend the "
               f"capability's {want.get('cap_width', 0)} bits exactly over six "
               "abutting fields, and the figures they derive are that arithmetic")
