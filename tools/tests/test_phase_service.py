# SPDX-License-Identifier: Apache-2.0
"""Check joint acceptance and closure beyond the first schedule frame."""

import json
from contextlib import redirect_stdout
from io import StringIO

from tests.harness import Case, ensure
from vos.cli import phase_service as cli
from vos.phase_service import Contract, check, scenarios


def _counterexamples() -> None:
    contracts = scenarios()
    gap = check(contracts["average-gap"])
    ensure(not gap.zero_wait and gap.failure == (1, (0,)), "grant gap must fail")
    joint = check(contracts["joint-bank-conflict"])
    ensure(not joint.zero_wait and len(joint.trace[-1]) == 2, "joint grant overspend")
    wrap = check(contracts["frame-wrap"])
    ensure(not wrap.zero_wait and len(wrap.trace) == 3
           and wrap.failure == (0, (1,)), "occupancy must survive frame wrap")
    ensure(check(contracts["restricted-arrivals"]).zero_wait, "checked quiet phase allows drain")
    ensure(check(contracts["independent-banks"]).zero_wait, "independent banks issue together")


def _long_residue() -> None:
    # A three-cycle write must conflict with the next write two cycles later,
    # even when the intervening phase excludes arrivals.
    result = check(Contract((1, 1), (((),), (((0, 3),),))))
    ensure(not result.zero_wait and len(result.trace) == 4, "multi-frame residue lost")
    ensure(not check(Contract((1,), ((((0, 1), (1, 1)),),), banks=2)).zero_wait,
           "independent banks still share injection capacity")


def _invalid() -> None:
    for contract in (Contract((), ()), Contract((1,), ((),)),
                     Contract((1,), ((((1, 1),),),)),
                     Contract((1,), ((((0, 0),),),))):
        try:
            check(contract)
        except ValueError:
            continue
        raise AssertionError(f"invalid contract accepted: {contract}")


def _report() -> None:
    output = StringIO()
    with redirect_stdout(output):
        code = cli.main(["--json"])
    report = json.loads(output.getvalue())
    ensure(code == 0 and report["passed"], "synthetic regression verdict")
    ensure(report["target_comparison"] == "open", "no target qualification from fixtures")
    ensure(report["cases"]["frame-wrap"]["failure"] == [0, [1]], "trace evidence retained")


def cases() -> list[Case]:
    return [Case("counterexamples", _counterexamples), Case("long-residue", _long_residue),
            Case("invalid", _invalid), Case("report", _report)]
