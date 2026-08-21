# SPDX-License-Identifier: Apache-2.0
"""banks: the second class's bank grant, in the two artifacts that state it.

The per-class bank count is item (viii) of R-15-014a's closed final-freeze delta, so
it is a decision nobody has taken written down in two places that both look like they
have taken it. `model/config/verifiedos.json` declares a number because the emulator
needs one; `docs/bank-count-dse-contract.md` declares the same number because the
instrument that will decide it has to say what it is starting from. Two copies of one
fact is the defect this repository is built to catch, and this group is that catch
applied to the one figure whose two copies are in different languages.

The second half is the harder one and is what makes this a rule rather than a
comparison. A search whose hard constraint has no operands admits nothing, and the way
that stops being true is not somebody writing *admitted* in a report: it is a
coefficient quietly acquiring a value. So the rule reads the coefficient table's own
status column and holds it against the composition's qualification flag, in the
direction that bites: while the class is unqualified, the pruning pair must be pending,
because a droop envelope with operands would mean a macro had been measured and
`qualified` is the one thing that records whether one has (R-15-247m).

What no rule here decides is whether the candidate set is the right one, or whether
the pending coefficients are the right coefficients. Those are the residue every
enumeration in this tool declares, and they are a person's.
"""

from typing import TYPE_CHECKING

from vos import banks

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== banks: the second class's bank grant, in both artifacts that state it ==="


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)

    grant = banks.read(ctx.root)
    ctx.shared["bank_candidates"] = len(grant.candidates)

    findings: list[str] = []
    if grant.banks is None:
        findings.append(f"{banks.CONFIG} no longer declares the second class's bank "
                        "count in a form this rule reads")
    if grant.declared_banks is None:
        findings.append(f"{banks.DOCUMENT} no longer states the count the composition "
                        "declares in a form this rule reads")
    if not grant.candidates:
        findings.append(f"{banks.DOCUMENT} declares no candidate set this rule reads")

    if grant.banks is not None and grant.declared_banks is not None:
        if grant.banks != grant.declared_banks:
            findings.append(f"{banks.DOCUMENT} states {grant.declared_banks:,} banks "
                            f"and {banks.CONFIG} declares {grant.banks:,}")
        elif grant.candidates and grant.banks not in grant.candidates:
            findings.append(f"the declared {grant.banks:,} banks is outside the "
                            "candidate set the contract states")

    # the tool's report and the contract's table must name the same coefficients
    known = set(grant.pending) | set(grant.stated)
    findings += [f"{banks.DOCUMENT} carries no row for {symbol}, which the report "
                 f"prints the {column} column as pending on"
                 for column, symbols in banks.PENDING_COLUMNS for symbol in symbols
                 if symbol not in known]

    # and while the class is unqualified the hard constraint has no operands
    if grant.qualified is None:
        findings.append(f"{banks.CONFIG} no longer declares the second class's "
                        "qualification state, which is what says whether a coefficient "
                        "may have a value")
    elif not grant.qualified:
        findings += [f"{symbol} is stated where the second class is unqualified, so a "
                     "droop envelope has operands that no measured macro supplied "
                     "(R-15-247m)" for symbol in banks.PRUNING if symbol in grant.stated]

    rep.report("K-58", "bank-grant disagreement(s):", findings,
               f"the contract's {grant.declared_banks:,} banks is the composition's, is "
               f"one of {len(grant.candidates)} candidates, and {len(grant.pending)} "
               "coefficients are pending, so nothing is admitted"
               if grant.declared_banks is not None else "the bank grant is readable")
    rep.line()
