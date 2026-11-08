# SPDX-License-Identifier: Apache-2.0
"""banks: check the second-class bank grant across configuration and DSE contract (K-58).

[model/config/verifiedos.json](../../../model/config/verifiedos.json) and
[docs/hardware/bank-count-dse-contract.md](../../../docs/hardware/bank-count-dse-contract.md)
both state the placeholder bank count for item (viii) of R-15-014a's closed final-freeze
delta. K-58 checks that:
- both artifacts declare the same bank count and it belongs to the contract's candidate set,
- every coefficient symbol referenced by [banks.py](../banks.py#PENDING_COLUMNS) appears in
  the contract's coefficient table, and
- while the second memory class is `qualified: false` (R-15-247m), the droop-envelope
  pruning coefficients (`I_bank_peak`, `I_pdn_max`) remain `pending`.
"""

from typing import TYPE_CHECKING

from quarantine import banks

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
