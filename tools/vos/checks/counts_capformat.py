# SPDX-License-Identifier: Apache-2.0
"""Check frozen capability-format parameter restatements and bit-packing budgets (`K-79`).

Reads the capability format parameters from Sail via [vos/capformat.py](../capformat.py)
and checks every registered transcription site, `R-15-007`'s normative widths, both
bit packings (Sail and SystemVerilog), and every written-out bit-width sum.
"""

import re
from typing import TYPE_CHECKING

from vos import capformat

if TYPE_CHECKING:
    from . import Context

# R-15-007's normative parameter statements: (regex, parameter_key, label).
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
    """K-79: capability-format parameters, bit packings, and written budgets match the Sail definition.

    Checks:
    1. Every registered transcription site and `R-15-007`'s normative entry state the
       widths defined in `cap_format.sail`, `cap_common.sail`, and `core/xlen.sail` (or
       their derived figures: capability bit width, stored top mantissa width, maximum
       effective exponent, and permission codepoint count).
    2. The six packed fields (`perms`, `otype`, `E`, `B`, `T`, `address`) abut in order
       and spend the capability width exactly in both the Sail and RTL package packings.
    3. Every budget sentence in [`BUDGETS`](../capformat.py#BUDGETS) states those six
       field widths term by term and sums to the capability width.

    Report-only: `model/` is `-text`, `R-15-007` is normative, and RTL/prose sites
    couple the width to surrounding slice expressions and prose claims.
    """
    rep, reg = ctx.rep, ctx.reg
    fmt = capformat.read(ctx.root, ctx.shared.get("bundle"))
    findings: list[str] = []

    moved = [key for key, value in fmt.defined.items() if value is None]
    findings += [
        (f"the model declares no {key}, which K-79 reads the capability format's "
         f"{key} from, so there is no definition to hold the sites against"
         if key in fmt.undeclared else
         f"{key} is no longer declared in a form this rule reads, so there is "
         "no definition to hold the sites against")
        for key in sorted(moved)]
    ctx.shared["cap_format_params"] = len(fmt.defined) - len(moved)

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
            continue
        elif found != want[key]:
            findings.append(f"{label} states {found} where the model fixes "
                            f"{key} at {want[key]}")
        else:
            held += 1

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
