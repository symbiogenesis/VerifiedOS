# SPDX-License-Identifier: Apache-2.0
"""Independent checks of the adversary model, its bounds and its refusal witnesses."""

from dataclasses import replace
from itertools import product
from pathlib import Path
from typing import Any

from tests.harness import Case, ensure
from vos import revocation as authority
from vos import static_memory_envelope as envelope
from vos import static_memory_reclaim as reclaim


def _seeded_instances() -> list[tuple[reclaim.Envelope, reclaim.Policy, envelope.Limits]]:
    """Small instances derived from an index, so a red run replays exactly."""
    base = replace(reclaim.Envelope(), period=12, requests=2)
    found: list[tuple[reclaim.Envelope, reclaim.Policy, envelope.Limits]] = []
    for seed in range(30):
        phases = (1 + seed % 4, 5 + seed // 4 % 4)
        limits = envelope.Limits(restarts=seed % 2, stall_ticks=seed // 3 % 2,
                                 loans=seed // 5 % 2, saved_contexts=seed // 7 % 2,
                                 behind_cursor=seed // 2 % 2,
                                 windows=1 + seed // 11 % 2)
        try:
            policy = envelope.sized(base, limits, f"seed-{seed}", phases,
                                    (6, 12, 24)[seed % 3], 1 + seed % 2)
        except ValueError:
            continue
        found.append((base, policy, limits))
    return found


def _tick_machine(env: reclaim.Envelope, policy: reclaim.Policy,
                  moves: tuple[envelope.Move, ...],
                  horizon: int) -> list[tuple[int, int | None, int | None, int | None]]:
    """Discover passes tick by tick and consume zero grants; no next-pass formula.

    A holder revoked behind the cursor spoils the pass that is running, so this
    machine skips the first pass the event is eligible for and takes the next one.
    """
    order = sorted(range(len(moves)),
                   key=lambda index: (moves[index].window, moves[index].slot,
                                      moves[index].restart))
    release = {index: moves[index].window * env.period
               + policy.release_phases[moves[index].slot] for index in order}
    barrier = {index: (None if moves[index].loan_persists else release[index]
                       + env.containment_ticks + moves[index].stall) for index in order}
    begun: dict[int, int] = {}
    skipped: set[int] = set()
    for tick in range(horizon + 1):
        if tick % policy.pass_period:
            continue
        for index in order:
            stamp = barrier[index]
            if index in begun or stamp is None or stamp >= tick:
                continue
            if moves[index].behind and index not in skipped:
                skipped.add(index)
                continue
            begun[index] = tick
    reuse: dict[int, int] = {}
    taken: dict[int, int] = {}
    for index in order:
        if index not in begun:
            continue
        position = taken.get(begun[index], 0)
        taken[begun[index]] = position + 1
        if position < policy.zero_ticks:
            reuse[index] = begun[index] + policy.sweep_ticks + position + 1
    return sorted((release[index], barrier[index], begun.get(index), reuse.get(index))
                  for index in order)


def search_maxima_stay_within_every_closed_form_bound() -> None:
    admitted = 0
    for env, policy, limits in _seeded_instances():
        contract = envelope.bounds(env, policy, limits)
        if contract["status"] == "refused":
            ensure(contract["release_to_reuse"] is None, "a refused service kept a bound")
            continue
        admitted += 1
        durations = (1, env.containment_ticks, env.period,
                     contract["phased_release_to_reuse"])
        found = envelope.search(env, policy, limits, durations, max_schedules=4000)
        checked = envelope.compare(env, policy, limits, contract, found)
        ensure(not checked["errors"], f"{policy.name}: {checked['errors']}")
        ensure(all(row["within_bound"] for row in checked["checks"]),
               f"{policy.name}: a search maximum left its bound")
        ensure(found["overrun_schedules"] == 0,
               f"{policy.name}: an admitted schedule found no zero slot")
    ensure(admitted >= 8, "the seeded corpus must admit several services")


def the_closed_form_reduces_to_the_reclamation_envelope() -> None:
    """Every budget spent to zero leaves the fixed calendar's own envelope."""
    quiet = envelope.Limits(restarts=0, stall_ticks=0, loans=0, saved_contexts=0,
                            behind_cursor=0)
    env = replace(reclaim.Envelope(), period=12, requests=2)
    for phases in product(range(1, 5), repeat=2):
        for period in (6, 12, 24):
            policy = reclaim.Policy("tiny", phases, period, 1, env.extent_bytes, 1,
                                    env.extent_bytes)
            for duration in range(32):
                ensure(envelope.alpha_bound(env, policy, quiet, duration)
                       == reclaim.retirement_envelope(env, policy, duration),
                       f"adversarial envelope differs from the calendar: {phases}/{duration}")


def observed_envelope_matches_direct_window_enumeration() -> None:
    env = reclaim.Envelope()
    limits = envelope.Limits()
    policy = envelope.sized(env, limits, "spread", (1, 2, 7, 8), 24, 4)
    horizon = envelope.horizon_of(env, policy, limits)
    for moves in envelope.window_configurations(env, limits, 0)[::1009]:
        if not moves:
            continue
        rows = envelope.assign(env, policy, moves)
        arrivals = envelope.measure(env, policy, limits, rows, horizon).arrivals
        times = [time for time, _ in arrivals]
        for duration in range(env.period + 1):
            expected = max(sum(amount for time, amount in arrivals
                               if start < time <= start + duration)
                           for start in range(min(times) - duration - 1, max(times) + 2))
            ensure(envelope.alpha_observed(arrivals, duration) == expected,
                   f"sliding envelope differs from direct enumeration: {duration}")


def calendar_placement_matches_an_independent_tick_machine() -> None:
    env = replace(reclaim.Envelope(), period=12, requests=2)
    limits = envelope.Limits(windows=2)
    for name, phases, period, sweep in envelope.REDUCED_SCHEDULES:
        policy = envelope.sized(env, limits, name, phases, period, sweep)
        horizon = envelope.horizon_of(env, policy, limits)
        spaces = [envelope.window_configurations(env, limits, window)
                  for window in range(limits.windows)]
        for combination in list(product(*spaces))[::503]:
            moves = tuple(move for window in combination for move in window)
            if not moves:
                continue
            rows = envelope.assign(env, policy, moves)
            ensure(sorted((row.release, row.barrier, row.pass_start, row.reuse)
                          for row in rows)
                   == _tick_machine(env, policy, moves, horizon),
                   f"{name}: the calendar differs from the independent tick machine")


def barrier_mutants_reach_the_stale_capability() -> None:
    comp, initial = authority.fixture()
    safe = authority.reclaimed(comp, initial)
    ensure(not authority.reuse_errors(comp, safe), "the positive Q22a path refused reuse")
    old = next(holder for holder in initial.holders if holder.name == "saved")
    behind = authority.replace_holder(safe, old.name, old)
    ensure("reuse-resurrection" in authority.reuse_errors(comp, behind),
           "a write behind the cursor was accepted for reuse")
    second = authority.start_sweep(comp, behind)
    for name in sorted(comp.swept):
        second = authority.sweep(comp, second, name)
    ensure(not authority.reuse_errors(comp, second),
           "a complete second pass did not clear the stale representation")
    no_pass = authority.replace_holder(
        authority.complete(comp, authority.ready(comp, initial)), old.name, old)
    ensure({"post-barrier-full-pass", "reuse-resurrection"}
           <= set(authority.reuse_errors(comp, no_pass)),
           "skipping the post-barrier pass admitted the stale capability")
    ensure("saved" in authority.exposed(replace(behind, bits=behind.bits - comp.targets)),
           "the stale saved root has no observable authority to lose")
    early = authority.finish_device(authority.cancel_loan(
        authority.clear_core(authority.publish(comp, initial), 0), "call"))
    ensure("remote-acknowledgement" in authority.completion_errors(comp, early),
           "a skipped completion wait reported containment")
    ensure(bool(authority.exposed(early, 1)), "the unacknowledged peer holds no authority")
    try:
        authority.complete(comp, early)
    except authority.RevocationError:
        pass
    else:
        raise AssertionError("completion accepted a pending proxy")
    witnesses = envelope.barrier_witnesses()
    ensure(witnesses["behind_cursor_refused"] == ["reuse-resurrection"]
           and not witnesses["behind_cursor_accepted_after_second_pass"]
           and witnesses["skip_completion_wait_exposes"] == ("remote-register",)
           and witnesses["premature_reuse_exposes"] == ("saved",)
           and witnesses["uncancelled_loan_refuses_containment"] == ["outstanding-loan"],
           f"the receipt's barrier witnesses drifted: {witnesses}")


def an_undercounted_bound_is_reported_as_a_finding() -> None:
    env = replace(reclaim.Envelope(), period=12, requests=2)
    limits = envelope.Limits(windows=1)
    policy = envelope.sized(env, limits, "mutant", (2, 8), 12, 2)
    contract = envelope.bounds(env, policy, limits)
    durations = (env.period,)
    found = envelope.search(env, policy, limits, durations, max_schedules=20000)
    ensure(not envelope.compare(env, policy, limits, contract, found)["errors"],
           "the honest bound already reports a finding")
    for key in ("phased_release_to_reuse", "control_demand_bytes",
                "retirement_reserve_bytes"):
        shrunk: dict[str, Any] = dict(contract)
        shrunk[key] = 0
        ensure(envelope.compare(env, policy, limits, shrunk, found)["errors"],
               f"an undercounted {key} passed the comparison")
    starved = replace(policy, zero_ticks=1)
    hungry = envelope.search(env, starved, limits, durations, max_schedules=20000)
    ensure(hungry["overrun_schedules"] > 0, "a one-slot reservation served every cohort")
    ensure(envelope.compare(env, starved, limits, contract, hungry)["errors"],
           "an overrun zero reservation was not reported")


def restart_storm_and_uncancelled_loan_leave_the_admitted_bound() -> None:
    env = reclaim.Envelope()
    limits = envelope.Limits()
    searched = 0
    for name, phases, period, sweep in envelope.PUBLIC_SCHEDULES:
        policy = envelope.sized(env, limits, name, phases, period, sweep)
        contract = envelope.bounds(env, policy, limits)
        if contract["status"] == "refused":
            ensure(contract["control_demand_bytes"] > contract["control_grant_bytes"],
                   f"{name}: refused for no stated service reason")
            continue
        searched += 1
        storm = envelope.storm_witness(env, policy, limits, contract)
        ensure(storm["limit_is_load_bearing"],
               f"{name}: one restart beyond the budget changed nothing")
        loan = envelope.loan_witness(env, policy, limits)
        ensure(loan["outstanding"]["reuse"] is None
               and loan["outstanding"]["barrier"] is None,
               f"{name}: an uncancelled loan reached containment")
        ensure(loan["outstanding"]["pinned_bytes"] > env.extent_bytes,
               f"{name}: the lender's extent was never pinned")
        ensure(loan["cancelled_at_containment"]["release_to_reuse"]
               <= contract["phased_release_to_reuse"],
               f"{name}: a cancelled loan left the bound")
    ensure(searched >= 2, "the declared public schedules admitted no service")


def report_is_deterministic_and_keeps_its_scope_limits() -> None:
    root = Path(__file__).resolve().parents[2]
    first: dict[str, Any] = envelope.report(root)
    ensure(first == envelope.report(root), "receipt includes nondeterministic content")
    ensure(not first["errors"], "receipt carries internal findings")
    ensure(set(first["sources_sha256"]) == set(envelope.SOURCES), "source closure missing")
    ensure(first["open_obligations"], "the receipt claims no remaining work")
    rows = [row for item in first["instances"] for row in item["schedules"]]
    ensure(any(row["status"] == "service-refused" for row in rows),
           "every declared schedule was admitted, so no negative result stands")
    searched = [row for row in rows if row["status"] == "searched"]
    ensure(all(row["search"]["status"] == "exhaustive" for row in searched),
           "a declared search was not exhaustive")
    ensure(all(row["storm"]["limit_is_load_bearing"] for row in searched),
           "an admitted restart budget decides nothing")
    ensure(any(row["comparison"]["attained"] for row in searched),
           "no bound carries a tightness witness")
    ensure(any(row["comparison"]["open_tightness"] for row in searched),
           "an open tightness gap was reported as closed")


def cases() -> list[Case]:
    return [Case(fn.__name__, fn) for fn in (
        search_maxima_stay_within_every_closed_form_bound,
        the_closed_form_reduces_to_the_reclamation_envelope,
        observed_envelope_matches_direct_window_enumeration,
        calendar_placement_matches_an_independent_tick_machine,
        barrier_mutants_reach_the_stale_capability,
        an_undercounted_bound_is_reported_as_a_finding,
        restart_storm_and_uncancelled_loan_leave_the_admitted_bound,
        report_is_deterministic_and_keeps_its_scope_limits,
    )]
