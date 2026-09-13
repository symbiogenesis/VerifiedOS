# SPDX-License-Identifier: Apache-2.0
"""Worst-case retirement envelopes under a declared finite reclamation adversary.

The public service envelope, the byte units, the containment padding and the pass
calendar are imported from `static_memory_reclaim`; this module adds only the
adversary's admitted moves and the bounds that survive them. Q22a's predicates in
`revocation` decide every authority question. Bounded search over small horizons
is a lower-bound instrument on the adversary and never a theorem, and no hardware
sweep rate, real holder set or target service is qualified here.
"""

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import combinations, product
from math import lcm
from pathlib import Path
from typing import Any, NamedTuple

from vos import revocation as authority
from vos import static_memory_reclaim as reclaim


@dataclass(frozen=True)
class Limits:
    """The adversary's declared budget inside one public period.

    Every field is an admitted limit of the composition, not an observed rate. A
    schedule that spends more than one of them is outside the service envelope and
    is reported as such rather than credited as the same service.
    """

    restarts: int = 1
    stall_ticks: int = 1
    loans: int = 1
    saved_contexts: int = 1
    behind_cursor: int = 1
    loan_bytes: int = 16
    saved_bytes: int = 16
    windows: int = 1


@dataclass(frozen=True)
class Move:
    """One admitted retirement event and the adversary's choices on it.

    `restart` marks an extra retirement beyond the base calendar, `stall` the
    endpoint acknowledgement delay, `loans` the grant loans outstanding at
    retirement, `saved` a context retained across it, `behind` a holder revoked
    after the sweep cursor passed its location. `loan_persists` is the violated
    premise: a loan containment never cancels, so containment never completes.
    """

    window: int
    slot: int
    restart: bool = False
    stall: int = 0
    loans: int = 0
    saved: bool = False
    behind: bool = False
    loan_persists: bool = False


class Assignment(NamedTuple):
    """One event's derived calendar positions; every reader uses this derivation."""

    move: Move
    release: int
    barrier: int | None
    pass_start: int | None
    zero_position: int | None
    reuse: int | None


class Measurement(NamedTuple):
    """What one adversary schedule costs, in the imported synthetic byte units."""

    peak_retirement_bytes: int
    max_release_to_reuse: int
    unserved: int
    control_slack_bytes: int
    arrivals: tuple[tuple[int, int], ...]


def validate(env: reclaim.Envelope, policy: reclaim.Policy, limits: Limits) -> None:
    """Accept only a fixed calendar and a budget stated in whole admitted units."""
    reclaim.validate(env, policy)
    values = asdict(limits)
    if any(type(value) is not int or value < 0 for value in values.values()):
        raise ValueError("every adversary budget is a nonnegative whole number")
    if limits.windows < 1 or limits.loan_bytes < 1 or limits.saved_bytes < 1:
        raise ValueError("a finite horizon and positive pinned extents are required")
    events = env.requests + limits.restarts
    if (limits.stall_ticks >= env.period or limits.saved_contexts > events
            or limits.behind_cursor > events):
        raise ValueError("a stall, retention or behind-cursor budget exceeds one period")


def arrival_charge(limits: Limits, env: reclaim.Envelope, move: Move) -> int:
    """Charged extents entering release-to-reuse at one retirement event."""
    return (env.extent_bytes + move.loans * limits.loan_bytes
            + (limits.saved_bytes if move.saved else 0))


def assign(env: reclaim.Envelope, policy: reclaim.Policy,
           moves: tuple[Move, ...]) -> list[Assignment]:
    """Place every move on the imported calendar: containment, pass and zero slot.

    A stalled endpoint extends containment to exactly `C + stall`. A holder revoked
    behind the cursor invalidates the pass in progress, so the event waits for the
    next eligible pass. Zeroization is FIFO by immutable request identity and a
    whole extent consumes one whole slot, as the reclamation calendar states.
    """
    if any(not 0 <= move.slot < env.requests or move.stall < 0 for move in moves):
        raise ValueError("a move names an identity outside the fixed request calendar")
    order = sorted(moves, key=lambda move: (move.window, move.slot, move.restart))
    derived: list[tuple[Move, int, int | None, int | None]] = []
    cohorts: dict[int, list[int]] = {}
    for index, move in enumerate(order):
        release = move.window * env.period + policy.release_phases[move.slot]
        barrier = (None if move.loan_persists
                   else release + env.containment_ticks + move.stall)
        begin = None if barrier is None else reclaim.next_pass(policy, barrier)
        if begin is not None and move.behind:
            begin += policy.pass_period
        derived.append((move, release, barrier, begin))
        if begin is not None:
            cohorts.setdefault(begin, []).append(index)
    placed: dict[int, tuple[int, int]] = {}
    for begin, members in cohorts.items():
        for position, index in enumerate(members):
            if position < policy.zero_ticks:
                placed[index] = (position, begin + policy.sweep_ticks + position + 1)
    rows: list[Assignment] = []
    for index, (move, release, barrier, begin) in enumerate(derived):
        slot = placed.get(index)
        rows.append(Assignment(move, release, barrier, begin,
                               None if slot is None else slot[0],
                               None if slot is None else slot[1]))
    return rows


def _peak(spans: list[tuple[int, int, int]]) -> int:
    """Largest simultaneous charge of a set of half-open byte reservations."""
    deltas: dict[int, int] = {}
    for start, stop, amount in spans:
        if stop > start:
            deltas[start] = deltas.get(start, 0) + amount
            deltas[stop] = deltas.get(stop, 0) - amount
    running = best = 0
    for tick in sorted(deltas):
        running += deltas[tick]
        best = max(best, running)
    return best


def measure(env: reclaim.Envelope, policy: reclaim.Policy, limits: Limits,
            rows: list[Assignment], horizon: int) -> Measurement:
    """Charge each event's extent, pinned loans and retained context separately.

    An unserved event keeps its extent to the declared horizon: the model never
    invents a zero slot the reservation does not carry.
    """
    spans: list[tuple[int, int, int]] = []
    pipelines: list[tuple[int, int, int]] = []
    arrivals: list[tuple[int, int]] = []
    latest = unserved = 0
    for row in rows:
        closed = horizon if row.barrier is None else row.barrier
        spans.append((row.release, horizon if row.reuse is None else row.reuse,
                      env.extent_bytes))
        if row.move.loans:
            spans.append((row.release, closed, row.move.loans * limits.loan_bytes))
        if row.move.saved:
            spans.append((row.release,
                          horizon if row.pass_start is None
                          else row.pass_start + policy.sweep_ticks, limits.saved_bytes))
        pipelines.append((row.release, closed, env.control_work_bytes_per_request_tick))
        arrivals.append((row.release, arrival_charge(limits, env, row.move)))
        if row.reuse is None:
            unserved += 1
        else:
            latest = max(latest, row.reuse - row.release)
    return Measurement(_peak(spans), latest, unserved,
                       env.control_bytes_per_tick - _peak(pipelines), tuple(arrivals))


def alpha_profile(arrivals: tuple[tuple[int, int], ...],
                  durations: tuple[int, ...]) -> tuple[int, ...]:
    """Largest charge entering retirement in any window `(s, s + T]`, per `T`.

    A supremum over window starts is attained at a window whose right end is an
    arrival, so one sorted sweep per duration decides it. Completion precedes
    acquisition at an equal timestamp, which is what the half-open window states.
    """
    if any(type(duration) is not int or duration < 0 for duration in durations):
        raise ValueError("every window duration is a nonnegative whole number")
    order = sorted(arrivals)
    profile: list[int] = []
    for duration in durations:
        best = running = left = 0
        for right, (time, amount) in enumerate(order):
            running += amount
            while left <= right and order[left][0] <= time - duration:
                running -= order[left][1]
                left += 1
            best = max(best, running)
        profile.append(best)
    return tuple(profile)


def alpha_observed(arrivals: tuple[tuple[int, int], ...], duration: int) -> int:
    """The single-duration reading of `alpha_profile`, for one window length."""
    return alpha_profile(arrivals, (duration,))[0]


def alpha_bound(env: reclaim.Envelope, policy: reclaim.Policy, limits: Limits,
                duration: int) -> int:
    """Adversarial arrival supremum, derived from the calendar and the budgets.

    Every arrival instant is a release phase of some public period, so a window
    meets each period in one contiguous piece and that period can spend its whole
    budget on the phases inside the piece. Enumerating window starts modulo the
    period is exact because the calendar and the budgets are both periodic.
    """
    validate(env, policy, limits)
    if type(duration) is not int or duration < 0:
        raise ValueError("window duration must be a nonnegative whole number")
    best = 0
    for start in range(env.period):
        total = 0
        for window in range((start + duration) // env.period + 1):
            count = sum(1 for phase in policy.release_phases
                        if start < window * env.period + phase <= start + duration)
            if count:
                total += ((count + limits.restarts) * env.extent_bytes
                          + limits.loans * limits.loan_bytes
                          + limits.saved_contexts * limits.saved_bytes)
        best = max(best, total)
    return best


def wait_bound(env: reclaim.Envelope, policy: reclaim.Policy, limits: Limits) -> int:
    """Largest containment-to-eligible-pass delay over the reachable barriers.

    `next_pass(b) - b` is `pass_period - (b mod pass_period)`, so the adversary
    maximizes the wait by stalling its endpoint into the smallest reachable
    residue. The unphased bound is one sweep period.
    """
    residues = {(window * env.period + phase + env.containment_ticks + stall)
                % policy.pass_period
                for window in range(policy.pass_period)
                for phase in policy.release_phases
                for stall in range(limits.stall_ticks + 1)}
    return policy.pass_period - min(residues)


def containment_wait_bound(env: reclaim.Envelope, policy: reclaim.Policy,
                           limits: Limits) -> int:
    """Largest release-to-eligible-pass delay, taken over phase and stall together.

    `C + D + W` charges the longest stall and the longest wait to one event, and
    the two trade off: a tick of stall that does not cross a pass boundary buys the
    adversary nothing, and one that crosses it spends the wait it just gained. This
    term is the same quantity read once, so it is never larger and usually smaller.
    """
    return max(reclaim.next_pass(policy, window * env.period + phase
                                 + env.containment_ticks + stall)
               - (window * env.period + phase)
               for window in range(policy.pass_period)
               for phase in policy.release_phases
               for stall in range(limits.stall_ticks + 1))


def _reaching(env: reclaim.Envelope, policy: reclaim.Policy, limits: Limits,
              window: int, begin: int) -> int:
    """Slots of one window whose admitted barrier can select the pass at `begin`."""
    return sum(1 for phase in policy.release_phases
               if any(reclaim.next_pass(policy, window * env.period + phase
                                        + env.containment_ticks + stall) == begin
                      for stall in range(limits.stall_ticks + 1)))


def _direct(env: reclaim.Envelope, policy: reclaim.Policy, limits: Limits,
            begin: int) -> int:
    """Events the admitted budgets can steer into one pass without a second pass."""
    reach = env.result_phase + env.containment_ticks + limits.stall_ticks
    low = (begin - policy.pass_period - reach) // env.period
    total = 0
    for window in range(low, begin // env.period + 1):
        count = _reaching(env, policy, limits, window, begin)
        total += count + (limits.restarts if count else 0)
    return total


def cohort_bound(env: reclaim.Envelope, policy: reclaim.Policy, limits: Limits) -> int:
    """Largest zero-slot demand one pass can be forced to serve.

    A pass serves the events whose containment selected it plus the events whose
    first pass was invalidated by a holder revoked behind its cursor. The second
    term is charged per window at the declared behind-cursor budget; the sum is an
    upper bound and the two terms are not claimed to be jointly attained.
    """
    validate(env, policy, limits)
    cycle = lcm(env.period, policy.pass_period)
    reach = env.result_phase + env.containment_ticks + limits.stall_ticks
    best = 0
    for begin in range(cycle, 2 * cycle + policy.pass_period, policy.pass_period):
        earlier = begin - policy.pass_period
        low = (earlier - policy.pass_period - reach) // env.period
        pushed = sum(min(limits.behind_cursor,
                         _reaching(env, policy, limits, window, earlier))
                     for window in range(low, earlier // env.period + 1))
        best = max(best, _direct(env, policy, limits, begin) + pushed)
    return best


def control_bound(env: reclaim.Envelope, policy: reclaim.Policy, limits: Limits) -> int:
    """Largest simultaneous containment control demand the adversary can force.

    Each retirement in its containment pipeline costs the fixed per-request-tick
    control charge, a restart opens another pipeline on the same phase, and a
    stalled endpoint holds one open for `C + stall` ticks.
    """
    validate(env, policy, limits)
    span = env.containment_ticks + limits.stall_ticks
    best = 0
    for tick in range(env.period):
        total = 0
        for window in (-2, -1, 0, 1):
            active = sum(1 for phase in policy.release_phases
                         if 0 <= tick - (window * env.period + phase) < span)
            total += active + (limits.restarts if active else 0)
        best = max(best, total)
    return best * env.control_work_bytes_per_request_tick


def bounds(env: reclaim.Envelope, policy: reclaim.Policy, limits: Limits) -> dict[str, Any]:
    """The closed-form release-to-reuse and retirement bounds under the adversary.

    `C` is the padded containment, `D` the declared endpoint stall, `W` the wait
    for an eligible pass, `S` the complete pass, `Z` the largest cohort's whole
    zero slots and `B` the second pass a stale capability behind the cursor forces.
    The reclamation calendar's `C + W + S + Z` is this shape with `D` and `B` zero.
    """
    validate(env, policy, limits)
    rows = reclaim.reservation(env, policy)
    control = control_bound(env, policy, limits)
    cohort = cohort_bound(env, policy, limits)
    errors: list[str] = []
    if control > env.control_bytes_per_tick:
        errors.append("admitted restarts and stalls exceed the fixed control grant")
    if cohort > policy.zero_ticks:
        errors.append("an admitted cohort exceeds the reserved zeroization slots")
    if any(row["workload_available"] < row["workload_required"] for row in rows):
        errors.append("fixed reclamation reservation removes required workload service")
    wait = wait_bound(env, policy, limits)
    behind = policy.pass_period if limits.behind_cursor else 0
    joint = containment_wait_bound(env, policy, limits)
    total = (env.containment_ticks + limits.stall_ticks + wait
             + policy.sweep_ticks + cohort + behind)
    phased = joint + policy.sweep_ticks + cohort + behind
    result: dict[str, Any] = {
        "status": "refused" if errors else "admitted", "errors": errors,
        "C": env.containment_ticks, "D": limits.stall_ticks, "W": wait,
        "S": policy.sweep_ticks, "Z": cohort, "B": behind, "CDW": joint,
        "unphased_wait_bound": policy.pass_period,
        "control_demand_bytes": control, "control_grant_bytes": env.control_bytes_per_tick,
        "zero_slots_reserved": policy.zero_ticks,
        "workload_slack_bytes": min(row["workload_available"] - row["workload_required"]
                                    for row in rows),
        "quantifier": "every schedule of admitted moves over the fixed periodic calendar",
        "initial_backlog": "zero; an arbitrary initial backlog is an additional charge",
    }
    if errors:
        result.update(release_to_reuse=None, phased_release_to_reuse=None,
                      retirement_reserve_bytes=None)
        return result
    result.update(release_to_reuse=total, phased_release_to_reuse=phased,
                  retirement_reserve_bytes=alpha_bound(env, policy, limits, phased),
                  unadversarial=reclaim.bounds(env, policy))
    return result


def _distributions(count: int, budget: int) -> list[tuple[int, ...]]:
    """Every way to spend at most `budget` whole units over `count` positions."""
    if count == 0:
        return [()]
    return [(head, *rest) for head in range(budget + 1)
            for rest in _distributions(count - 1, budget - head)]


def _selections(count: int, budget: int) -> list[tuple[int, ...]]:
    """Every choice of at most `budget` of `count` positions, as a 0/1 vector."""
    return [tuple(1 if index in chosen else 0 for index in range(count))
            for size in range(min(budget, count) + 1)
            for chosen in combinations(range(count), size)]


def window_configurations(env: reclaim.Envelope, limits: Limits,
                          window: int) -> list[tuple[Move, ...]]:
    """Every admitted configuration of one public period.

    A restart shares its slot's endpoint, so it carries that slot's declared stall;
    the loan, retention and behind-cursor budgets are spent over the window's whole
    event list, restarts included. This is the declared move space, and a search
    over it is evidence about this model rather than about a real workload.
    """
    result: list[tuple[Move, ...]] = []
    for size in range(env.requests + 1):
        for present in combinations(range(env.requests), size):
            for restarts in _distributions(size, limits.restarts):
                for stalls in product(range(limits.stall_ticks + 1), repeat=size):
                    seeds = [(slot, stall, copy)
                             for slot, stall, extra in zip(present, stalls, restarts,
                                                           strict=True)
                             for copy in range(extra + 1)]
                    events = len(seeds)
                    result.extend(
                        tuple(Move(window, slot, copy > 0, stall, loan,
                                   bool(keep), bool(stale))
                              for (slot, stall, copy), loan, keep, stale
                              in zip(seeds, loans, saved, behind, strict=True))
                        for loans in _distributions(events, limits.loans)
                        for saved in _selections(events, limits.saved_contexts)
                        for behind in _selections(events, limits.behind_cursor))
    return result


def label(moves: tuple[Move, ...]) -> str:
    """A deterministic name for one adversary schedule, readable in the receipt."""
    parts = []
    for move in moves:
        tags = "-".join(tag for flag, tag in (
            (move.restart, "restart"), (move.saved, "saved"),
            (move.behind, "behind"), (move.loan_persists, "uncancelled"))
            if flag)
        parts.append(f"w{move.window}s{move.slot}"
                     f"{'-' + tags if tags else ''}-d{move.stall}-l{move.loans}")
    return "+".join(parts) if parts else "idle-window"


def horizon_of(env: reclaim.Envelope, policy: reclaim.Policy, limits: Limits) -> int:
    """A finite observation window that closes every admitted event's lifetime."""
    return (limits.windows * env.period + env.containment_ticks + limits.stall_ticks
            + 3 * policy.pass_period + policy.sweep_ticks + policy.zero_ticks)


def search(env: reclaim.Envelope, policy: reclaim.Policy, limits: Limits,
           durations: tuple[int, ...], max_schedules: int = 2_000_000) -> dict[str, Any]:
    """Maximize retirement, latency and control demand over the whole move space.

    The enumeration is complete when the declared space fits the budget; otherwise
    it reports `incomplete` and a stride sample, and its maxima stay lower bounds
    on the adversary. Either way it is finite evidence about small horizons.
    """
    validate(env, policy, limits)
    spaces = [window_configurations(env, limits, window)
              for window in range(limits.windows)]
    total = 1
    for space in spaces:
        total *= len(space)
    stride = 1 if total <= max_schedules else total // max_schedules + 1
    horizon = horizon_of(env, policy, limits)
    peaks: dict[str, tuple[int, tuple[Move, ...]]] = {}
    idle: tuple[int, tuple[Move, ...]] = (0, ())
    alphas: dict[int, tuple[int, tuple[Move, ...]]] = dict.fromkeys(durations, idle)
    overrun = 0
    visited = 0
    for index, combination in enumerate(product(*spaces)):
        if index % stride:
            continue
        visited += 1
        moves = tuple(move for window in combination for move in window)
        result = measure(env, policy, limits, assign(env, policy, moves), horizon)
        overrun += 1 if result.unserved else 0
        for key, value in (("peak_retirement_bytes", result.peak_retirement_bytes),
                           ("max_release_to_reuse", result.max_release_to_reuse),
                           ("control_demand_bytes",
                            env.control_bytes_per_tick - result.control_slack_bytes)):
            if key not in peaks or value > peaks[key][0]:
                peaks[key] = (value, moves)
        for duration, observed in zip(durations, alpha_profile(result.arrivals, durations),
                                      strict=True):
            if observed > alphas[duration][0]:
                alphas[duration] = (observed, moves)
    return {
        "status": "exhaustive" if stride == 1 else "incomplete",
        "space": total, "schedules": visited, "stride": stride, "horizon": horizon,
        "overrun_schedules": overrun,
        "maxima": {key: {"value": value, "witness": label(moves),
                         "moves": [asdict(move) for move in moves]}
                   for key, (value, moves) in sorted(peaks.items())},
        "alpha": {str(duration): {"value": value, "witness": label(moves),
                                  "moves": [asdict(move) for move in moves]}
                  for duration, (value, moves) in sorted(alphas.items())},
    }


def compare(env: reclaim.Envelope, policy: reclaim.Policy, limits: Limits,
            contract: dict[str, Any], found: dict[str, Any]) -> dict[str, Any]:
    """Check every enumerated maximum against its closed-form bound.

    A search maximum above a bound is a defect of the bound, reported as an error
    rather than absorbed. A bound the search does not attain leaves tightness open
    and reports its gap; attainment names the instance that attains it.
    """
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    pairs = [("release-to-reuse", found["maxima"]["max_release_to_reuse"],
              contract["phased_release_to_reuse"]),
             ("control-demand", found["maxima"]["control_demand_bytes"],
              contract["control_demand_bytes"]),
             ("retirement-occupancy", found["maxima"]["peak_retirement_bytes"],
              contract["retirement_reserve_bytes"])]
    pairs.extend((f"alpha-{duration}", row, alpha_bound(env, policy, limits, int(duration)))
                 for duration, row in found["alpha"].items())
    for name, row, limit in pairs:
        observed = row["value"]
        checks.append({"quantity": name, "search": observed, "bound": limit,
                       "within_bound": observed <= limit, "gap": limit - observed,
                       "tightness": "attained" if observed == limit else "open",
                       "witness": row["witness"]})
        if observed > limit:
            errors.append(f"{policy.name}: {name} search maximum exceeds its bound")
    if found["overrun_schedules"]:
        errors.append(f"{policy.name}: an admitted schedule overran the zero reservation")
    if contract["phased_release_to_reuse"] > contract["release_to_reuse"]:
        errors.append(f"{policy.name}: the phased reading exceeds the C+D+W+S+Z+B shape")
    return {"checks": checks, "errors": errors,
            "attained": [row["quantity"] for row in checks if row["tightness"] == "attained"],
            "open_tightness": {row["quantity"]: row["gap"] for row in checks
                               if row["tightness"] == "open"}}


def barrier_witnesses() -> dict[str, Any]:
    """Q22a decides these; the timing model restates none of its predicates.

    The stale capability behind the cursor is refused by the complete protocol,
    accepted after a second full pass, refused when no post-barrier pass runs, and
    actually restored to usable authority when the bits are cleared without one.
    """
    comp, initial = authority.fixture()
    swept = authority.reclaimed(comp, initial)
    old = next(holder for holder in initial.holders if holder.name == "saved")
    behind = authority.replace_holder(swept, old.name, old)
    second = authority.start_sweep(comp, behind)
    for name in sorted(comp.swept):
        second = authority.sweep(comp, second, name)
    contained = authority.complete(comp, authority.ready(comp, initial))
    no_pass = authority.replace_holder(contained, old.name, old)
    partial = authority.finish_device(authority.cancel_loan(
        authority.clear_core(authority.publish(comp, initial), 0), "call"))
    try:
        authority.complete(comp, partial)
        refusal: list[str] = []
    except authority.RevocationError as error:
        refusal = str(error).split(", ")
    cleared = replace(behind, bits=behind.bits - comp.targets)
    loaned = replace(authority.ready(comp, initial), loans=frozenset({"call"}))
    return {
        "behind_cursor_refused": authority.reuse_errors(comp, behind),
        "behind_cursor_accepted_after_second_pass": authority.reuse_errors(comp, second),
        "skip_post_barrier_pass": authority.reuse_errors(comp, no_pass),
        "skip_completion_wait": authority.completion_errors(comp, partial),
        "skip_completion_wait_refusal": refusal,
        "skip_completion_wait_exposes": authority.exposed(partial, 1),
        "premature_reuse_exposes": authority.exposed(cleared),
        "uncancelled_loan_refuses_containment": authority.completion_errors(comp, loaned),
        "positive_reuse_errors": authority.reuse_errors(comp, swept),
        "scope": "Q22a finite authority fixtures, separate from the synthetic calendar",
    }


def loan_witness(env: reclaim.Envelope, policy: reclaim.Policy,
                 limits: Limits) -> dict[str, Any]:
    """A loan outstanding past containment blocks reuse until it is cancelled."""
    horizon = horizon_of(env, policy, limits)
    held = (Move(0, 0, loans=1, loan_persists=True),)
    cancelled = (Move(0, 0, loans=1),)
    stuck = assign(env, policy, held)
    freed = assign(env, policy, cancelled)
    return {
        "outstanding": {"witness": label(held),
                        "reuse": stuck[0].reuse, "barrier": stuck[0].barrier,
                        "pinned_bytes": measure(env, policy, limits, stuck,
                                                horizon).peak_retirement_bytes},
        "cancelled_at_containment": {
            "witness": label(cancelled), "reuse": freed[0].reuse,
            "barrier": freed[0].barrier,
            "release_to_reuse": None if freed[0].reuse is None
            else freed[0].reuse - freed[0].release},
        "rule": "containment cancels the loan and clears its borrowed footprint; "
                "an uncancelled loan has no containment event and no reuse",
    }


def storm_schedules(env: reclaim.Envelope, over: Limits) -> list[tuple[Move, ...]]:
    """Every over-limit restart concentration, with the other budgets fully spent.

    Restart placement and endpoint stall are the two dimensions a storm has, so
    this sub-space is enumerated whole rather than sampled. The remaining budgets
    take one declared allocation: the witness has to exceed a bound, not maximize.
    """
    per_window: list[tuple[Move, ...]] = []
    for restarts in _distributions(env.requests, over.restarts):
        for stalls in product(range(over.stall_ticks + 1), repeat=env.requests):
            seeds = [(slot, stall, copy)
                     for slot, (stall, extra) in enumerate(zip(stalls, restarts,
                                                               strict=True))
                     for copy in range(extra + 1)]
            per_window.append(tuple(
                Move(0, slot, copy > 0, stall, 1 if index < over.loans else 0,
                     index < over.saved_contexts, index < over.behind_cursor)
                for index, (slot, stall, copy) in enumerate(seeds)))
    return [tuple(replace(move, window=window)
                  for window, config in enumerate(combination) for move in config)
            for combination in product(per_window, repeat=over.windows)]


def storm_witness(env: reclaim.Envelope, policy: reclaim.Policy, limits: Limits,
                  contract: dict[str, Any]) -> dict[str, Any]:
    """One restart beyond the admitted per-window budget leaves the bound behind."""
    over = replace(limits, restarts=limits.restarts + 1)
    horizon = horizon_of(env, policy, limits)
    exceeds: dict[str, str] = {}
    worst = {"release-to-reuse": 0, "control-demand": 0, "retirement-occupancy": 0}
    overrun = 0
    for moves in storm_schedules(env, over):
        result = measure(env, policy, over, assign(env, policy, moves), horizon)
        overrun += 1 if result.unserved else 0
        for key, value, limit in (
                ("release-to-reuse", result.max_release_to_reuse,
                 contract["phased_release_to_reuse"]),
                ("control-demand",
                 env.control_bytes_per_tick - result.control_slack_bytes,
                 contract["control_demand_bytes"]),
                ("retirement-occupancy", result.peak_retirement_bytes,
                 contract["retirement_reserve_bytes"])):
            worst[key] = max(worst[key], value)
            if value > limit and key not in exceeds:
                exceeds[key] = label(moves)
        if result.unserved and "zero-reservation" not in exceeds:
            exceeds["zero-reservation"] = label(moves)
    return {"admitted_restarts": limits.restarts, "storm_restarts": over.restarts,
            "schedules": len(storm_schedules(env, over)), "status": "exhaustive",
            "storm_maxima": worst, "overrun_schedules": overrun,
            "exceeds": exceeds, "limit_is_load_bearing": bool(exceeds),
            "admitted_bound": {key: contract[key] for key in (
                "phased_release_to_reuse", "control_demand_bytes",
                "retirement_reserve_bytes")}}


def schedule_report(env: reclaim.Envelope, policy: reclaim.Policy, limits: Limits,
                    budget: int) -> dict[str, Any]:
    """One sweep schedule: its bounds, its search, and the comparison between them."""
    contract = bounds(env, policy, limits)
    result: dict[str, Any] = {"policy": asdict(policy), "bound": contract}
    if contract["status"] == "refused":
        result.update(status="service-refused", errors=[], search=None)
        return result
    durations = (env.containment_ticks, env.period, contract["phased_release_to_reuse"])
    found = search(env, policy, limits, durations, max_schedules=budget)
    checked = compare(env, policy, limits, contract, found)
    result.update(status="searched", search=found, comparison=checked,
                  errors=checked["errors"],
                  storm=storm_witness(env, policy, limits, contract),
                  loan=loan_witness(env, policy, limits))
    if not result["storm"]["limit_is_load_bearing"]:
        result["errors"] = [*checked["errors"],
                            f"{policy.name}: the admitted restart limit decides nothing"]
    if result["loan"]["outstanding"]["reuse"] is not None:
        result["errors"] = [*result["errors"],
                            f"{policy.name}: an uncancelled loan reached reuse"]
    return result


def sized(env: reclaim.Envelope, limits: Limits, name: str, phases: tuple[int, ...],
          pass_period: int, sweep_ticks: int) -> reclaim.Policy:
    """Size one schedule's zeroization reservation at the admitted cohort bound.

    Reserving exactly the admitted worst case is what makes the declared restart
    budget load-bearing rather than decorative: nothing is left over for a storm.
    A cohort bound wider than the pass has no admissible reservation at all, and
    raises here rather than being capped into a reservation nothing established.
    """
    draft = reclaim.Policy(name, phases, pass_period, sweep_ticks, env.extent_bytes,
                           1, env.extent_bytes)
    cohort = cohort_bound(env, draft, limits)
    if cohort > pass_period:
        raise ValueError("the admitted cohort does not fit one sweep pass")
    return replace(draft, zero_ticks=cohort)


def instance(name: str, env: reclaim.Envelope, limits: Limits,
             schedules: tuple[tuple[str, tuple[int, ...], int, int], ...],
             budget: int) -> dict[str, Any]:
    """Replay one public envelope against every declared sweep schedule."""
    policies = [sized(env, limits, *schedule) for schedule in schedules]
    rows = [schedule_report(env, policy, limits, budget) for policy in policies]
    return {"name": name, "envelope": asdict(env), "limits": asdict(limits),
            "base_retirement_envelope_bytes": {
                str(duration): reclaim.retirement_envelope(env, policies[0], duration)
                for duration in (env.containment_ticks, env.period)},
            "schedules": rows,
            "errors": [error for row in rows for error in row["errors"]]}


SOURCES = ("tools/vos/static_memory_envelope.py",
           "tools/tests/test_static_memory_envelope.py",
           "tools/vos/static_memory_reclaim.py", "tools/vos/revocation.py",
           "docs/assurance/revocation-qualification.md",
           "docs/implementation/static-memory-reclamation.md",
           "docs/implementation/static-memory-envelope.md")

PUBLIC_SCHEDULES = (("spread-slow", (1, 2, 7, 8), 24, 4),
                    ("spread-faster", (1, 2, 7, 8), 12, 4),
                    ("deferred-slow", (8, 8, 8, 8), 24, 4))

REDUCED_SCHEDULES = (("reduced-slow", (2, 8), 24, 2), ("reduced-faster", (2, 8), 12, 2))

SEARCH_BUDGET = 400_000


def report(root: Path) -> dict[str, Any]:
    """Return a deterministic replay receipt; the shared CLI adds Git identity.

    The one-window instance enumerates the document's whole public envelope; the
    two-window instance is a reduced calendar of the same shape, because the full
    envelope's two-window space does not fit this budget. The reduced instance
    spends no retention budget for the same reason, and says so: saved-context
    retention is enumerated only where the one-window instance enumerates it.
    """
    public = reclaim.Envelope()
    reduced = replace(public, period=12, requests=2)
    instances = [
        instance("public-envelope-one-window", public, Limits(),
                 PUBLIC_SCHEDULES, SEARCH_BUDGET),
        instance("reduced-calendar-two-windows", reduced,
                 Limits(windows=2, saved_contexts=0), REDUCED_SCHEDULES, SEARCH_BUDGET),
    ]
    checks = barrier_witnesses()
    errors = [error for item in instances for error in item["errors"]]
    if (checks["positive_reuse_errors"] or checks["behind_cursor_accepted_after_second_pass"]
            or "reuse-resurrection" not in checks["behind_cursor_refused"]
            or "post-barrier-full-pass" not in checks["skip_post_barrier_pass"]
            or "remote-acknowledgement" not in checks["skip_completion_wait"]
            or not checks["skip_completion_wait_exposes"]
            or not checks["premature_reuse_exposes"]
            or "outstanding-loan" not in checks["uncancelled_loan_refuses_containment"]):
        errors.append("Q22a barrier witness failed to reproduce")
    return {
        "schema": "static-memory-envelope-v1",
        "scope": "adversarial synthetic calendar bounds and bounded search; "
                 "no target rate, holder set or theorem",
        "adversary": {
            "restarts": "extra kernel-mediated retirements of an admitted identity, "
                        "bounded per public period",
            "stalled_endpoints": "proxy and device acknowledgement delayed to its "
                                 "declared deadline, extending containment to C + D",
            "grant_loans": "each loan outstanding at retirement pins the lender's "
                           "extent until containment cancels it",
            "saved_contexts": "a context retained across a retirement pins a copy "
                              "until the post-barrier pass sweeps it",
            "behind_cursor": "a holder revoked after the cursor passed its location "
                             "invalidates the pass in progress and forces a second",
            "excluded": "arrival jitter, a phase outside the fixed calendar, an "
                        "unbounded call, and any move above a declared budget",
        },
        "bound_shape": "release-to-reuse is C + D + W + S + Z + B, and the peak "
                       "retirement charge is alpha of that bound from zero backlog",
        "instances": instances,
        "barrier_witnesses": checks,
        "open_obligations": [
            "qualified sweep, zeroization and containment service rates on a target",
            "the real composed holder set and its admitted restart and stall deadlines",
            "tightness of the cohort and behind-cursor terms beyond these horizons",
            "a mechanized all-executions statement of either bound",
        ],
        "errors": errors,
        "sources_sha256": {name: sha256((root / name).read_bytes()).hexdigest()
                           for name in SOURCES},
    }
