# SPDX-License-Identifier: Apache-2.0
"""Independent credit oracle, physical-budget checks and delayed-reuse mutations."""

import copy
from collections.abc import Callable
from itertools import product
from typing import Any

from tests.harness import Case, ensure
from vos import memory_planner_contracts as contracts
from vos import memory_planner_resources as resources


def _reject(fn: Callable[[], object], text: str) -> None:
    try:
        fn()
    except ValueError as exc:
        ensure(text in str(exc), f"expected {text!r}, got {exc}")
    else:
        raise AssertionError(f"expected refusal: {text}")


def _finite_credit_oracle() -> None:
    alphabet = [(kind, amount) for kind in ("take", "return") for amount in (1, 2, 3)]
    for length in range(5):
        for trace in product(alphabet, repeat=length):
            used = peak = issued = refunded = 0
            for kind, amount in trace:
                used += amount if kind == "take" else -amount
                peak = max(peak, used)
                issued += amount if kind == "take" else 0
                refunded += amount if kind == "return" else 0
            events = list(trace)
            ensure(resources.required_credit(events) == peak,
                   "backward potential must equal independently measured maximum prefix demand")
            for initial in range(13):
                final = resources.run_credit(events, initial)
                ensure((final is not None) == (initial >= peak), "success must be exact at the credit boundary")
                if final is not None:
                    ensure(final + issued == initial + refunded, "credit cannot disappear or duplicate")


def _backed_slots_and_release_bounds() -> None:
    raw = resources.demo_resources()
    report = resources.analyze_resources(raw)
    ensure(not report["errors"], "the backed demo should satisfy its declared resource contract")
    pool = report["pools"][0]
    ensure(pool["occupancy_bound"] == 16 * 1024 * 1024 + 64,
           "independent slots and always-live overhead are all charged")
    ensure(report["maximum_release_bound"] == 11,
           "release operation, device wait, sweep and scrub all belong to reuse latency")
    for path in report["paths"]:
        for release in path["releases"]:
            ensure(sum(release["step_bounds"]) == release["elapsed_bound"], "deadline vector must replay")
            ensure(release["clock_origin"] == "release request/start of release operation"
                   and release["clock_end"] == "reuse barrier completion",
                   "release evidence must state the complete request-to-reuse clock interval")
        for meter in path["meters"]:
            events = [(e["kind"], e["bytes"]) for e in meter["events"]]
            ensure(resources.run_credit(events, meter["required_credit"]) == meter["required_credit"],
                   "terminal slot state must restore every prepaid byte")


def _underfunding_and_overhead() -> None:
    raw = resources.demo_resources()
    raw["reserved_bytes"]["scratch"] -= 1
    report = resources.analyze_resources(raw)
    ensure(report["errors"] and report["status"] == "refused resource contract",
           "a single missing overhead byte must lose guaranteed success")
    _reject(lambda: resources.emit_resource_certificate(raw), "refused resource contract")
    raw = resources.demo_resources()
    raw["placement"][2]["offset"] = 0
    _reject(lambda: resources.analyze_resources(raw), "fixed placement rejected")


def _delayed_device_and_exceptional_cleanup() -> None:
    raw = resources.demo_resources()
    raw["step_bounds"]["complete"] += 1
    report = resources.analyze_resources(raw)
    ensure(len(report["errors"]) == 4, "every normal and exceptional device cleanup must meet its bound")
    raw = resources.demo_resources()
    raw["contract"] = contracts.demo_contract(late_completion=True)
    _reject(lambda: resources.analyze_resources(raw), "fixed placement rejected")
    raw = resources.demo_resources()
    terminal = raw["contract"]["body"][-1]["branches"][-1]["body"]
    terminal[:] = [e for e in terminal if e["op"] != "barrier"]
    _reject(lambda: resources.analyze_resources(raw), "terminal outcome retains")


def _release_cost_alone_misses_deadline() -> None:
    raw = resources.demo_resources()
    ensure(not resources.analyze_resources(raw)["errors"], "the original deadline must be sufficient")
    raw["step_bounds"]["release"] += 1
    report = resources.analyze_resources(raw)
    ensure(report["maximum_release_bound"] == 12 and len(report["errors"]) == 4,
           "release cost alone must invalidate every outcome's request-to-reuse bound")
    for path in report["paths"]:
        exceeded = [release for release in path["releases"]
                    if release["elapsed_bound"] > report["reuse_deadline"]]
        ensure(len(exceeded) == 1, "only the device-bearing lease should miss this deadline")
        ensure(sum(exceeded[0]["step_bounds"][1:]) <= report["reuse_deadline"],
               "omitting release's own cost would incorrectly accept this path")
    _reject(lambda: resources.emit_resource_certificate(raw), "refused resource contract")


def _input_guards_and_replay() -> None:
    raw = resources.demo_resources()
    before = copy.deepcopy(raw)
    report = resources.analyze_resources(raw)
    ensure(raw == before and not resources.replay_resources(raw, report), "input isolation and replay")
    for replacement in (False, 0.0):
        mistyped = copy.deepcopy(report)
        mistyped["paths"][0]["meters"][0]["slot"] = replacement
        ensure(bool(resources.replay_resources(raw, mistyped)),
               "equal-valued booleans and floats must not replace integer receipt fields")
    report["paths"][0]["meters"][0]["events"][1]["kind"] = "take"
    ensure(bool(resources.replay_resources(raw, report)), "altered credit evidence must fail replay")
    del raw["step_bounds"]["complete"]
    _reject(lambda: resources.analyze_resources(raw), "every used operation")
    raw = resources.demo_resources()
    raw["step_bounds"]["complete"] = True
    _reject(lambda: resources.analyze_resources(raw), "expected an integer")
    _reject(lambda: resources.analyze_resources(resources.demo_resources(), max_work=10), "budget")
    _reject(lambda: resources.emit_resource_certificate(resources.demo_resources(), max_work=10), "budget")
    _reject(lambda: resources.required_credit([("invent", 1)]), "invalid credit")


def _certificate_is_fresh_and_numeric() -> None:
    raw: dict[str, Any] = resources.demo_resources()
    # Keep the replay fixture small in natural-number kernel computation.
    for obj in raw["contract"]["objects"]:
        obj["size"] //= 1024 * 1024
        obj["alignment"] = 1
    for row in raw["placement"]:
        row["offset"] //= 1024 * 1024
    raw["contract"]["pools"][0]["capacity"] = 28
    raw["reserved_bytes"]["scratch"] = 16
    raw["overhead_bytes"]["scratch"] = 0
    emitted = resources.emit_resource_certificate(raw)
    ensure("Require Import MemoryPlannerResources." in emitted and "Take 4" in emitted,
           "certificate must replay the actual normalized credit actions")
    ensure("list_sum [1; 1; 4; 2; 2; 1] <= 11" in emitted,
           "certificate must recompute request-to-reuse addition including release inside Rocq")
    ensure("Input SHA256:" in emitted and "report SHA256:" in emitted, "both endpoints need identities")


def cases() -> list[Case]:
    return [
        Case("resources finite exhaustive credit oracle and conservation", _finite_credit_oracle),
        Case("resources prepaid slot success and complete release bounds", _backed_slots_and_release_bounds),
        Case("resources scalar credits require physical layout and overhead", _underfunding_and_overhead),
        Case("resources delayed devices and exceptional cleanup", _delayed_device_and_exceptional_cleanup),
        Case("resources release cost alone can exceed request-to-reuse deadline", _release_cost_alone_misses_deadline),
        Case("resources malformed inputs and content-bound replay", _input_guards_and_replay),
        Case("resources fresh finite Rocq certificate emission", _certificate_is_fresh_and_numeric),
    ]
