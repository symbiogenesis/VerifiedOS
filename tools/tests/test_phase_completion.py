# SPDX-License-Identifier: Apache-2.0
"""Completion order, continuing maintenance and boundary-to-quiescence bounds."""

import hashlib
import json
import tempfile
from contextlib import redirect_stdout
from dataclasses import asdict
from io import StringIO
from itertools import product
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos.cli import phase_service as cli
from vos.phase_completion import check
from vos.phase_service import Contract, scenarios
from vos.phase_service import check as acceptance


def _inversion() -> None:
    contract = Contract((1, 1, 0), ((((0, 3),),), (((1, 1),),), ((),)), banks=2)
    result = check(contract)
    ensure(acceptance(contract).zero_wait and acceptance(contract).drain == 0,
           "the witness must close under the original acceptance predicate")
    ensure(result.ordered is False and result.reason == "completion-order-inverted"
           and result.trace == (((0, 3),), ((1, 1),)) and result.failure is not None
           and result.failure.phase == 1 and result.quiescent_drain is None,
           "later short operation completed before the earlier long operation")
    simultaneous = Contract((2, 0), ((((0, 2), (1, 1)),), ((),)), banks=2)
    ensure(acceptance(simultaneous).zero_wait and check(simultaneous).ordered is False,
           "batch order is per-hart issue order, even within the same cycle")


def _ties_and_harts() -> None:
    equal = Contract((1, 1), ((((0, 2),),), (((1, 1),),)), banks=2)
    result = check(equal)
    ensure(result.ordered is True and result.quiescent_drain == 1,
           "two operations finishing in the same cycle preserve order")
    simultaneous = Contract((2, 0), ((((0, 2), (1, 2)),), ((),)), banks=2)
    ensure(check(simultaneous).ordered is True, "equal batch completion is ordered")
    independent = Contract((1, 1, 0), ((((0, 3, 0),),), (((1, 1, 1),),), ((),)), banks=2)
    other = check(independent)
    ensure(other.ordered is True and other.quiescent_drain == 2,
           "completion order does not couple independent harts")


def _occupancy_drain() -> None:
    contract = Contract((1, 0, 0), ((((0, 3),),), ((),), ((),)))
    result = check(contract)
    ensure(acceptance(contract).drain == 0 and result.quiescent_drain == 2
           and result.drain_status == "finite" and result.ordered is True,
           "an occupied bank with no flight still has two residual cycles")
    instant = Contract((1,), ((((0, 1),),),))
    ensure(check(instant).quiescent_drain == 0,
           "one occupied acceptance cycle completes before the next boundary")


def _fabric_drain() -> None:
    contract = Contract((1, 0, 0, 0, 0), ((((0, 3),),), ((),), ((),), ((),), ((),)),
                        paths=(2,))
    result = check(contract)
    ensure(acceptance(contract).drain == 2 and result.quiescent_drain == 4
           and result.ordered is True,
           "two remaining fabric cycles plus three occupancy cycles share acceptance")
    one = Contract((1,), ((((0, 1),),),), paths=(1,))
    ensure(check(one).quiescent_drain == 1, "one-cycle path drains in one cycle")


def _refresh() -> None:
    empty = Contract((0,), (((),),), refresh=(((0, 1),),))
    ensure(check(empty).quiescent_drain == 0,
           "perpetual refresh is not issued workload that prevents drain")
    # A request issued in phase zero accepts in phase one, completes at the end
    # of phase two, and leaves room for the two-cycle refresh in phases 3 and 4.
    quiet = Contract((1, 0, 0, 0, 0), ((((0, 2),),), ((),), ((),), ((),), ((),)),
                     paths=(1,), refresh=((), (), (), ((0, 2),), ()))
    result = check(quiet)
    ensure(result.ordered is True and result.quiescent_drain == 2,
           "refresh remains scheduled while the workload drains")
    other_bank = Contract((1, 0, 0), ((((0, 3),),), ((),), ((),)), banks=2,
                          refresh=(((1, 1),), ((1, 1),), ((1, 1),)))
    ensure(check(other_bank).quiescent_drain == 2,
           "continuing refresh on another bank must neither extend nor erase drain")
    blocked = Contract((1, 0, 0), ((((0, 1),),), ((),), ((),)), paths=(2,),
                       refresh=((), (), ((0, 1),)))
    result = check(blocked)
    ensure(result.ordered is None and result.drain_status == "blocked"
           and result.reason == "drain-path-blocked" and result.quiescent_drain is None
           and result.drain_cycles == 1 and result.drain_failure is not None
           and result.drain_failure.phase == 2,
           "drain must not invent a finite bound through a refresh collision")


def _wrap_and_alternatives() -> None:
    contract = Contract((1, 0, 1), (((), ((1, 1),)), ((),), ((), ((0, 3),))), banks=2)
    result = check(contract)
    ensure(acceptance(contract).zero_wait and result.ordered is False
           and len(result.trace) == 4 and result.failure is not None
           and result.failure.phase == 0,
           "all alternatives and completion residue must survive the first frame")
    for name in ("average-gap", "joint-bank-conflict", "frame-wrap"):
        ensure(not acceptance(scenarios()[name]).zero_wait
               and check(scenarios()[name]).ordered is not True,
               f"load-bearing acceptance counterexample was lost: {name}")


def _small_schedule_oracle() -> None:
    # Each six-cycle frame issues to bank zero in cycle zero and bank one in
    # cycle one, then leaves four silent cycles. Enumerate path and occupancy
    # combinations, comparing with absolute completion times independently of
    # the state representation. No operation can survive to the next frame.
    compared = 0
    for first_path, second_path, first_duration, second_duration in product(
            range(3), range(3), range(1, 4), range(1, 4)):
        contract = Contract((1, 1, 0, 0, 0, 0),
                            ((((0, first_duration),),), (((1, second_duration),),),
                             ((),), ((),), ((),), ((),)), banks=2,
                            paths=(first_path, second_path))
        if not acceptance(contract).zero_wait:
            continue
        compared += 1
        first_completion = first_path + first_duration - 1
        second_completion = 1 + second_path + second_duration - 1
        result = check(contract)
        ensure(result.ordered is (first_completion <= second_completion),
               f"completion differs from absolute cycle oracle: {contract}")
        if result.ordered:
            ensure(result.quiescent_drain
                   == max(first_completion, second_completion - 1),
                   f"boundary drain differs from absolute cycle oracle: {contract}")
    ensure(compared > 0, "the completion oracle compared no accepted schedules")


def _cli() -> None:
    contract = Contract((1, 1, 0), ((((0, 3),),), (((1, 1),),), ((),)), banks=2)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "contract.json"
        path.write_text(json.dumps(asdict(contract)), encoding="utf-8")
        output = StringIO()
        with redirect_stdout(output):
            old_code = cli.main(["--contract", str(path), "--json"])
        original = json.loads(output.getvalue())
        output = StringIO()
        with redirect_stdout(output):
            code = cli.main(["--contract", str(path), "--completion", "--json"])
        report = json.loads(output.getvalue())
        ensure(old_code == 0 and code == 1 and "completion" not in original
               and original["result"] == report["result"]
               and report["completion"]["ordered"] is False,
               "completion is opt-in and preserves the acceptance receipt")
        for name in ("tools/vos/phase_completion.py", "tools/tests/test_phase_completion.py"):
            ensure(report["sources_sha256"][name]
                   == hashlib.sha256((TOOLS.parent / name).read_bytes()).hexdigest(),
                   "completion evidence must bind its checker and tests")
        path.write_text(json.dumps(asdict(Contract((1, 0, 0), ((((0, 3),),), ((),), ((),))))),
                        encoding="utf-8")
        output = StringIO()
        with redirect_stdout(output):
            code = cli.main(["--contract", str(path), "--completion", "--json"])
        report = json.loads(output.getvalue())
        ensure(code == 0 and report["completion"]["quiescent_drain"] == 2
               and report["completion"]["drain_status"] == "finite"
               and report["target_comparison"] == "open",
               "finite model drain never supplies target qualification")


def cases() -> list[Case]:
    return [Case("inversion", _inversion), Case("ties-and-harts", _ties_and_harts),
            Case("occupancy-drain", _occupancy_drain), Case("fabric-drain", _fabric_drain),
            Case("refresh", _refresh), Case("wrap-and-alternatives", _wrap_and_alternatives),
            Case("small-schedule-oracle", _small_schedule_oracle), Case("cli", _cli)]
