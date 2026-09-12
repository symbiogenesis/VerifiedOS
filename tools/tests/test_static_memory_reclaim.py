# SPDX-License-Identifier: Apache-2.0
"""Independent bounded calendar replay and telling reclamation refusal witnesses."""

from dataclasses import replace
from itertools import product
from pathlib import Path
from typing import Any

from tests.harness import Case, ensure
from vos import static_memory_reclaim as r


def reference(env: r.Envelope, policy: r.Policy, cycles: int,
              selected: frozenset[int] | None = None) -> dict[int, int]:
    """Tick machine: discover barriers and passes, enqueue zero work, consume grants.

    No next-pass formula, cohort modulo arithmetic or production record reader.
    The small checked schedules have nonoverlapping full-pass and zero windows.
    """
    released: dict[int, int] = {}
    contained: dict[int, int] = {}
    sweeping: dict[int, list[int]] = {}
    zeroing: dict[int, list[int]] = {}
    done: dict[int, int] = {}
    for tick in range(cycles * env.period + 3 * policy.pass_period + 30):
        for cycle in range(cycles):
            for position, phase in enumerate(policy.release_phases):
                ident = cycle * env.requests + position
                if (selected is None or ident in selected) and tick == cycle * env.period + phase:
                    released[ident] = tick
        for ident, release in released.items():
            if tick == release + env.containment_ticks:
                contained[ident] = tick
        if tick % policy.pass_period == 0:
            assigned = {ident for ids in sweeping.values() for ident in ids}
            cohort = sorted(ident for ident, barrier in contained.items()
                            if barrier < tick and ident not in assigned)
            sweeping[tick] = cohort
        for begin, cohort in sweeping.items():
            if tick == begin + policy.sweep_ticks:
                zeroing[begin] = list(cohort)
        for begin, queue in zeroing.items():
            if begin + policy.sweep_ticks <= tick < begin + policy.sweep_ticks + policy.zero_ticks:
                if queue:
                    done[queue.pop(0)] = tick + 1
    return done


def periodic_envelope_matches_sliding_window_enumeration() -> None:
    for phases in product(range(1, 5), repeat=2):
        env = replace(r.Envelope(), period=12, requests=2)
        policy = r.Policy("tiny", phases, 12)
        arrivals = [cycle * env.period + phase
                    for cycle in range(-8, 9) for phase in phases]
        for duration in range(0, 40):
            expected = max(sum(start < event <= start + duration for event in arrivals)
                           for start in range(-12, 13)) * env.extent_bytes
            ensure(r.retirement_envelope(env, policy, duration) == expected,
                   f"wrong burst envelope: {phases}/{duration}")


def all_small_optional_calendars_obey_independent_replay_bound() -> None:
    for phases in product(range(1, 5), repeat=2):
        env = replace(r.Envelope(), period=12, requests=2)
        for period in (8, 12, 24):
            policy = r.Policy("tiny", phases, period)
            bound = r.bounds(env, policy)
            ensure(bound["status"] == "conditional", "tiny service unexpectedly refused")
            full = r.scheduled_records(env, policy, 3)
            expected = reference(env, policy, 3)
            ensure({row["id"]: row["reuse"] for row in full} == expected,
                   f"calendar differs from independent tick machine: {phases}/{period}")
            for choices in product((False, True), repeat=4):
                selected = frozenset(index for index, on in enumerate(choices) if on)
                done = reference(env, policy, 2, selected)
                ensure(set(done) == selected, "optional request lost zero service")
                releases = {ident: ident // 2 * env.period + phases[ident % 2]
                            for ident in selected}
                ensure(all(done[ident] - release <= bound["release_to_reuse"]
                           for ident, release in releases.items()), "optional subset breaks delay")
                for tick in range(2 * env.period + 2 * period):
                    charge = sum(env.extent_bytes for ident, release in releases.items()
                                 if release <= tick < done[ident])
                    ensure(charge <= bound["retirement_reserve_bytes"], "subset breaks reserve")


def joint_change_saves_backing_but_not_peak_quarantine() -> None:
    env = r.Envelope()
    late, early = (8,) * 4, (1, 2, 3, 4)
    runs = [r.experiment(env, r.Policy(name, phases, period))
            for name, phases, period in (("base", late, 24), ("phase-only", early, 24),
                                         ("sweep-only", late, 12), ("joint", early, 12))]
    ensure(all(not run["errors"] for run in runs), "research invariant failed")
    ensure([run["peak_occupied_backing_bytes"] for run in runs] == [128, 128, 128, 64],
           "ablation no longer distinguishes useful joint schedule")
    ensure([run["peak_quarantined_bytes"] for run in runs] == [64] * 4,
           "backing saving mislabeled as peak quarantine reduction")
    ensure([run["fixed_capacity_binding"]["same_service_admitted"] for run in runs]
           == [False, False, False, True], "fixed capacity hides rejected requests")
    for run in runs:
        for row in run["timeline"]:
            # Independently enumerate each occupied byte from reservation lifetimes.
            expected = sum(1 for obj in run["records"] for _ in range(env.extent_bytes)
                           if obj["start"] <= row["tick"] < obj["reuse"])
            ensure(row["occupied_backing"] == expected, "physical bytes double charged")
            ensure(row["total_charge"] == expected + env.permanent_bytes,
                   "permanent metadata or result outbox uncharged")


def excess_sweep_and_restart_bursts_refuse_service() -> None:
    env = r.Envelope()
    over = r.experiment(env, r.Policy("too-fast", (1, 2, 3, 4), 6))
    ensure(over["status"] == "service-refused", "overreserved workload grant admitted")
    ensure(over["bound"]["release_to_reuse"] is None, "invalid service gets reuse bound")
    ensure(any(row["total_reserved"] > env.fabric_bytes_per_tick
               for row in over["reservation"]), "refusal has no real traffic violation")
    storm_env = replace(env, requests=8)
    storm = r.experiment(storm_env, r.Policy("storm", (8,) * 8, 24))
    ensure(storm["status"] == "service-refused", "restart storm exceeds zero reservation")
    rows = r.scheduled_records(storm_env, r.Policy("storm", (8,) * 8, 24), 1)
    ensure(sum(row["reuse"] is None for row in rows) == 4, "overflow invents zeroization service")
    weak_control = replace(env, control_bytes_per_tick=4)
    control = r.bounds(weak_control, r.Policy("weak-control", (8,) * 4, 24))
    ensure(control["status"] == "refused", "concurrent containment jobs share an underfunded grant")


def failed_containment_never_becomes_available_at_deadline() -> None:
    env = r.Envelope()
    policy = r.Policy("failed", (8,) * 4, 24)
    rows = r.scheduled_records(env, policy, 2, frozenset(range(4)))
    ensure(all(row["reuse"] is None and row["barrier"] is None for row in rows[:4]),
           "deadline converted failed containment into successful reuse")
    ledger = r.timeline(env, rows, 100)
    ensure(ledger[-1]["failed_retention"] == 64, "failure bytes disappear with elapsed time")
    binding = r.fixed_bindings(rows, 4)
    ensure(binding["refused_ids"] == [4, 5, 6, 7], "failed slots were rebound")
    checks = r.semantic_checks()
    ensure(not checks["positive_reuse_errors"], "safe Q22 witness failed")
    ensure(all(case["refusals"] for case in checks["cases"]), "Q22 defect admitted")
    ensure("reuse-resurrection" in checks["behind_cursor_reuse_errors"],
           "cursor completion lost raw-tag requirement")
    ensure("saved" in checks["premature_bit_clear_exposes"],
           "stale saved-root counterexample has no observable authority")


def exact_barrier_timestamp_waits_for_a_new_pass() -> None:
    policy = r.Policy("strict", (2,) * 4, 8)
    rows = r.scheduled_records(r.Envelope(), policy, 1)
    ensure(all(row["barrier"] == 8 and row["pass_start"] == 16 for row in rows),
           "a pass at the barrier timestamp was used as post-barrier evidence")


def report_is_deterministic_and_keeps_the_scope_limits() -> None:
    root = Path(__file__).resolve().parents[2]
    first: dict[str, Any] = r.report(root)
    ensure(first == r.report(root), "receipt includes nondeterministic timing")
    ensure(not first["errors"], "receipt carries internal findings")
    ensure(first["failed_containment"]["successful_reuse_bound"] is None,
           "failure has a finite successful bound")
    ensure(first["comparisons"]["finite_trace_backing_saved_bytes"] == 64,
           "comparison does not derive witness backing result")
    ensure(set(first["sources_sha256"]) == set(r.SOURCES), "source closure missing")


def cases() -> list[Case]:
    return [Case(fn.__name__, fn) for fn in (
        periodic_envelope_matches_sliding_window_enumeration,
        all_small_optional_calendars_obey_independent_replay_bound,
        joint_change_saves_backing_but_not_peak_quarantine,
        excess_sweep_and_restart_bursts_refuse_service,
        failed_containment_never_becomes_available_at_deadline,
        exact_barrier_timestamp_waits_for_a_new_pass,
        report_is_deterministic_and_keeps_the_scope_limits,
    )]
