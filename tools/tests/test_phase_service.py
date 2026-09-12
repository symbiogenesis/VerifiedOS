# SPDX-License-Identifier: Apache-2.0
"""Check joint acceptance, ordering and closure beyond the first schedule frame."""

import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from tests.harness import Case, ensure
from vos.cli import phase_service as cli
from vos.phase_service import Contract, check, scenarios


def _counterexamples() -> None:
    contracts = scenarios()
    gap = check(contracts["average-gap"])
    ensure(not gap.zero_wait and gap.failure == (1, (0,), ()), "grant gap must fail")
    joint = check(contracts["joint-bank-conflict"])
    ensure(not joint.zero_wait and len(joint.trace[-1]) == 2, "joint grant overspend")
    wrap = check(contracts["frame-wrap"])
    ensure(not wrap.zero_wait and len(wrap.trace) == 3
           and wrap.failure == (0, (1,), ()), "occupancy must survive frame wrap")
    quiet = check(contracts["restricted-arrivals"])
    ensure(quiet.zero_wait and quiet.drain == 0, "checked quiet phase allows drain")
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
                     Contract((1,), ((((0, 0),),),)),
                     Contract((1,), ((((0, 1, -1),),),)),
                     Contract((1,), ((((0, 1, 0, 0),),),)),
                     Contract((1,), ((((0,),),),)),
                     Contract((1,), (((),),), refresh=((), ())),
                     Contract((1,), (((),),), refresh=(((1, 1),),)),
                     Contract((1,), (((),),), refresh=(((0, 0),),)),
                     Contract((1,), (((),),), refresh=(((0, 1, 0),),)),
                     Contract((1,), (((),),), refresh=(((0, 1), (0, 1)),)),
                     Contract((1,), (((),),), paths=(0, 0)),
                     Contract((1,), (((),),), paths=(-1,))):
        try:
            check(contract)
        except ValueError:
            continue
        raise AssertionError(f"invalid contract accepted: {contract}")


def _refresh() -> None:
    contracts = scenarios()
    arrival = check(contracts["refresh-arrival"])
    ensure(not arrival.zero_wait and arrival.trace == (((0, 1),),),
           "refresh must reserve the issue cycle")
    overlap = check(contracts["refresh-write-overlap"])
    ensure(not overlap.zero_wait and overlap.reason == "refresh-overlap"
           and overlap.failure == (0, (1,), ()) and overlap.trace == ((), ((0, 2),)),
           "refresh cannot preempt a write across frame wrap, even without arrivals")
    wrap = check(contracts["refresh-wrap"])
    ensure(not wrap.zero_wait and wrap.reason == "arrival-blocked"
           and len(wrap.trace) == 3 and wrap.failure == (0, (1,), ()),
           "refresh residue must survive frame wrap")
    ensure(check(contracts["refresh-quiet-window"]).zero_wait,
           "arrival at refresh completion must issue")
    ensure(check(contracts["refresh-other-bank"]).zero_wait,
           "refresh must not block unrelated banks or consume injection grants")
    repeated = check(Contract((0,), (((),),), refresh=(((0, 2),),)))
    ensure(not repeated.zero_wait and repeated.reason == "refresh-overlap",
           "refresh cannot overlap an earlier refresh")


def _paths() -> None:
    contracts = scenarios()
    order = check(contracts["path-order"])
    ensure(not order.zero_wait and order.reason == "order-inverted"
           and order.trace == (((0, 1),), ((1, 1),))
           and order.failure == (1, (0, 0), ((0, 2, 1, 0),)),
           "a shorter path to a later bank inverts one hart's acceptance order")
    equal = check(contracts["path-equal"])
    ensure(equal.zero_wait and equal.drain == 1,
           "equal paths keep order and leave one cycle in flight at every boundary")
    other = check(contracts["path-other-hart"])
    ensure(other.zero_wait and other.drain == 2,
           "another hart's earlier request carries no ordering obligation")
    busy = check(contracts["path-bank-busy"])
    ensure(not busy.zero_wait and busy.reason == "path-blocked"
           and busy.trace == (((0, 2),), ((0, 1),))
           and busy.failure == (0, (1,), ((0, 1, 1, 0),)),
           "a request that leaves the core and finds its bank taken is a fabric queue")
    # Within one batch, tuple order is issue order: a path-zero request after a
    # longer-path request of the same hart is accepted first.
    inverted = check(Contract((2,), ((((0, 1), (1, 1)),),), banks=2, paths=(1, 0)))
    ensure(not inverted.zero_wait and inverted.reason == "order-inverted"
           and len(inverted.trace) == 1, "batch order is issue order")
    ordered = check(Contract((2,), ((((1, 1), (0, 1)),),), banks=2, paths=(1, 0)))
    ensure(ordered.zero_wait and ordered.drain == 1, "the near bank first is in order")
    # Two harts' requests reaching one bank in the same cycle cannot both be
    # accepted there, whatever the injection grant allowed at issue.
    same = check(Contract((2,), ((((0, 1, 0), (0, 1, 1)),),), paths=(1,)))
    ensure(not same.zero_wait and same.reason == "path-blocked" and len(same.trace) == 1,
           "one acceptance port per bank holds for arrivals from the fabric")
    front = check(Contract((1, 1), ((((0, 1, 0),),), (((0, 1, 1),),)), paths=(0,)))
    ensure(front.zero_wait and front.drain == 0, "path zero is the former behaviour")


def _report() -> None:
    output = StringIO()
    with redirect_stdout(output):
        code = cli.main(["--json"])
    report = json.loads(output.getvalue())
    ensure(code == 0 and report["passed"], "synthetic regression verdict")
    ensure(report["target_comparison"] == "open" and "schedule" in report["open_because"],
           "no target qualification from fixtures, and no schedule artifact to read")
    flags = report["inputs"]
    ensure(all(isinstance(flags[name], bool) for name in
               ("first_class_qualified", "second_class_qualified", "timing_qualified",
                "core_class_c_frozen")),
           "the receipt reads the composition's own flags rather than stating them")
    ensure(report["cases"]["frame-wrap"]["failure"] == [0, [1], []], "trace evidence retained")
    ensure(report["cases"]["refresh-write-overlap"]["reason"] == "refresh-overlap"
           and report["cases"]["refresh-wrap"]["contract"]["refresh"] == [[], [[0, 2]]],
           "report binds refresh reservations and distinguishes schedule failures")
    ensure(report["cases"]["path-order"]["reason"] == "order-inverted"
           and report["cases"]["path-equal"]["drain"] == 1
           and report["cases"]["path-order"]["drain"] is None,
           "report carries the ordering verdict and the drain bound of a closed set")


def _contract_file() -> None:
    contract = {"grants": [1, 1], "arrivals": [[[[0, 1]]], [[[1, 1]]]],
                "banks": 2, "paths": [2, 0]}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "contract.json"
        path.write_text(json.dumps(contract), encoding="utf-8")
        output = StringIO()
        with redirect_stdout(output):
            code = cli.main(["--contract", str(path), "--json"])
        report = json.loads(output.getvalue())
        ensure(code == 1 and report["result"]["reason"] == "order-inverted"
               and report["result"]["contract"]["paths"] == [2, 0],
               "a supplied contract is checked and its refutation exits 1")
        path.write_text(json.dumps({**contract, "paths": [1, 1]}), encoding="utf-8")
        output = StringIO()
        with redirect_stdout(output):
            code = cli.main(["--contract", str(path)])
        ensure(code == 0 and "zero_wait=True" in output.getvalue()
               and "drain=1" in output.getvalue(), "a closed contract exits 0")
        path.write_text(json.dumps({**contract, "paths": [1]}), encoding="utf-8")
        output = StringIO()
        with redirect_stdout(output):
            code = cli.main(["--contract", str(path), "--json"])
        ensure(code == 2 and "error" in json.loads(output.getvalue()),
               "a malformed contract is refused with a reason")
        path.write_text('{"grants": [1], "arrivals": [[[]]], "banks": true}', encoding="utf-8")
        output = StringIO()
        with redirect_stdout(output):
            code = cli.main(["--contract", str(path)])
        ensure(code == 2 and "malformed" in output.getvalue(), "a boolean bank count is refused")


def cases() -> list[Case]:
    return [Case("counterexamples", _counterexamples), Case("long-residue", _long_residue),
            Case("invalid", _invalid), Case("refresh", _refresh), Case("paths", _paths),
            Case("report", _report), Case("contract-file", _contract_file)]
