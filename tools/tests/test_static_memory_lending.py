# SPDX-License-Identifier: Apache-2.0
"""Independent two-run enumeration, telling lending mutations and refusal typing."""

from itertools import combinations, product
from pathlib import Path
from typing import Any

from tests.harness import Case, ensure
from vos import static_memory_lending as lend


def reference_observation(calendar: lend.Calendar, capacity: tuple[int, ...],
                          padded: bool) -> tuple[tuple[str, ...], ...]:
    """Recompute the borrower's observation from held intervals and slot identities.

    No incremental load array and no shared helper: own-pool service is decided by
    colouring the held intervals onto the borrower's actual slots, borrowed service
    by rescanning every held interval against the per-tick capacity, and padding by
    scanning the declared instants forward from the completion tick.
    """
    own: list[list[tuple[int, int]]] = [[] for _ in range(calendar.borrower_slots)]
    loans: list[tuple[int, int]] = []
    result: list[tuple[str, ...]] = []
    for request in calendar.requests:
        served: tuple[str, str, int] | None = None
        usable = False
        for tick in request.attempts:
            start, end = tick, tick + request.duration
            if end > calendar.horizon:
                continue
            usable = True
            slot = next((index for index, held in enumerate(own)
                         if all(start >= stop or begin >= end for begin, stop in held)), None)
            if slot is not None:
                own[slot].append((start, end))
                served = (request.id, "own-pool", end)
                break
            if all(sum(1 for begin, stop in loans if begin <= unit < stop) < capacity[unit]
                   for unit in range(start, end)):
                loans.append((start, end))
                served = (request.id, "borrowed", end)
                break
        if served is None:
            result.append((request.id, "refused",
                           "capacity-exhausted" if usable else "outside-horizon", "none"))
            continue
        finish = served[2]
        while padded and finish not in calendar.release_points and finish < calendar.horizon:
            finish += 1
        result.append((served[0], served[1], "none", str(finish)))
    return tuple(result)


def _shape(observation: lend.Observation) -> tuple[tuple[str, ...], ...]:
    return tuple((request, verdict, reason or "none",
                  "none" if completion is None else str(completion))
                 for request, verdict, reason, completion in observation)


def _pairwise(calendar: lend.Calendar, policy: lend.Policy,
              declassified: tuple[int, ...]) -> tuple[str, int | None]:
    """Decide safety by comparing every label-equal pair, with no grouping step."""
    traces = lend.admitted_traces(calendar)
    seen = [reference_observation(calendar, lend.borrow_capacity(calendar, policy, trace),
                                  policy.pad_to_release_points)
            for trace in traces]
    distances = [
        sum(1 for one, other in zip(traces[left], traces[right], strict=True) if one != other)
        for left, right in combinations(range(len(traces)), 2)
        if all(traces[left][tick] == traces[right][tick] for tick in declassified)
        and seen[left] != seen[right]]
    return ("noninterferent", None) if not distances else ("distinguishing", min(distances))


def _small_calendars() -> list[lend.Calendar]:
    requests = (lend.Request("own", (0,), 2), lend.Request("loan", (0,), 3),
                lend.Request("retry", (0, 1, 2), 2))
    return [lend.Calendar(horizon=5, lender_slots=2, borrower_slots=1,
                          declared_cap=caps, release_points=(0, 2), requests=requests)
            for caps in ((1, 1, 1, 1, 0), (1, 0, 1, 1, 1), (2, 1, 1, 0, 0))]


def _policies(calendar: lend.Calendar) -> list[lend.Policy]:
    families = [lend.Policy(f"headroom-observed-{h}", "headroom-observed", h)
                for h in range(calendar.lender_slots + 1)]
    families += [lend.Policy(f"headroom-committed-{h}", "headroom-committed", h)
                 for h in range(calendar.lender_slots + 1)]
    return [lend.Policy("none", "none"), lend.Policy("any-idle", "any-idle"),
            lend.Policy("any-idle-padded", "any-idle", pad_to_release_points=True),
            lend.Policy("release-declared", "release-declared"),
            lend.Policy("release-declassified", "release-declassified"),
            lend.Policy("leaking", "headroom-committed", 1, (0, 1)),
            lend.Policy("leaking-padded", "headroom-committed", 1, (0, 1), True), *families]


def enumeration_matches_a_direct_pairwise_checker() -> None:
    for calendar in _small_calendars():
        for policy in _policies(calendar):
            for declassified in ((), calendar.release_points):
                result = lend.analyze(calendar, policy, declassified)
                status, least = _pairwise(calendar, policy, declassified)
                ensure(result["status"] == status,
                       f"grouping and pairwise disagree: {policy.name}/{declassified}")
                witness = result["minimal_distinguishing_pair"]
                if least is None:
                    ensure(witness is None, "a safe policy reported a distinguishing pair")
                    continue
                ensure(witness is not None and len(witness["differing_ticks"]) == least,
                       f"reported witness is not minimal: {policy.name}")
                left = tuple(witness["lender_trace_a"])
                right = tuple(witness["lender_trace_b"])
                ensure(all(left[tick] == right[tick] for tick in declassified),
                       "a distinguishing pair must have equal public labels")
                ensure(lend.run(calendar, policy, left).observation
                       != lend.run(calendar, policy, right).observation,
                       "the reported pair does not actually distinguish")


def the_simulator_agrees_with_independent_interval_colouring() -> None:
    for calendar in _small_calendars():
        for policy in _policies(calendar):
            for trace in lend.admitted_traces(calendar):
                capacity = lend.borrow_capacity(calendar, policy, trace)
                ensure(_shape(lend.run(calendar, policy, trace).observation)
                       == reference_observation(calendar, capacity,
                                                policy.pad_to_release_points),
                       f"counter model differs from slot colouring: {policy.name}")


def refusal_typing_and_declared_attempts_are_preserved() -> None:
    calendar = lend.FIXTURE
    by_id = {request.id: request for request in calendar.requests}
    for policy in (*lend.POLICIES, lend.NEIGHBOUR):
        for trace in lend.admitted_traces(calendar):
            result = lend.run(calendar, policy, trace)
            for (request, verdict, reason, completion), attempt in zip(
                    result.observation, result.served, strict=True):
                ensure(verdict in lend.VERDICTS, f"unknown verdict: {verdict}")
                if verdict == "refused":
                    ensure(reason in lend.REFUSAL_REASONS, f"untyped refusal: {reason}")
                    ensure(completion is None and attempt is None,
                           "a refusal carries neither a completion tick nor a service instant")
                    continue
                ensure(reason is None, "a served request carries no refusal reason")
                if attempt is None or completion is None:
                    raise AssertionError("service carries both a serving instant and a completion")
                finish = by_id[request].attempts[attempt] + by_id[request].duration
                if policy.pad_to_release_points:
                    ensure(completion >= finish and (completion in calendar.release_points
                                                     or completion == calendar.horizon),
                           "padding must delay to a declared instant and never report early")
                else:
                    ensure(completion == finish,
                           "service happened away from a declared public attempt instant")
    late = lend.Calendar(horizon=4, lender_slots=2, borrower_slots=1,
                         declared_cap=(1, 1, 1, 1), release_points=(0,),
                         requests=(lend.Request("too-long", (2,), 3),))
    outside = lend.run(late, lend.Policy("any-idle", "any-idle"), (1, 1, 1, 1)).observation
    ensure(outside[0][2] == "outside-horizon", "an unusable attempt is not a capacity refusal")
    ensure(lend.pad(late, outside) == outside, "padding must not invent a completion tick")
    closed = lend.Calendar(horizon=4, lender_slots=2, borrower_slots=1,
                           declared_cap=(0, 0, 0, 0), release_points=(0,),
                           requests=(lend.Request("a", (0,), 4), lend.Request("b", (0, 1), 2)))
    baseline = lend.run(closed, lend.Policy("none", "none"), (0, 0, 0, 0)).observation
    ensure([row[1] for row in baseline] == ["own-pool", "refused"],
           "a full own pool was answered by borrowing under the no-lending baseline")
    ensure(baseline[1][2] == "capacity-exhausted", "an exhausted pool needs its typed verdict")


def a_mutated_safe_policy_is_caught_on_both_verdicts() -> None:
    calendar = lend.FIXTURE
    safe = lend.Policy("headroom-committed-2", "headroom-committed", 2)
    clean = lend.analyze(calendar, safe)
    ensure(clean["status"] == "noninterferent"
           and clean["return_capacity"]["status"] == "return-safe",
           "the reference committed reserve is no longer safe on both verdicts")
    for ticks in ((0, 1, 2), (0, 1), (1, 2)):
        mutant = lend.analyze(calendar, lend.Policy("mutant", "headroom-committed", 2, ticks))
        ensure(mutant["status"] == "distinguishing",
               f"reading the secret at {ticks} was not caught")
        ensure(_pairwise(calendar, lend.Policy("mutant", "headroom-committed", 2, ticks), ())[0]
               == "distinguishing", "the independent checker missed the mutation")
    short = lend.analyze(calendar, lend.Policy("short", "headroom-committed", 1))
    ensure(short["status"] == "noninterferent"
           and short["return_capacity"]["status"] == "overcommits",
           "a reserve below the committed peak must keep the loan but lose the return")
    ensure(short["return_capacity"]["witness_ticks"], "an overcommit needs the ticks it happens at")


def the_two_headroom_families_separate_and_meet_their_limits() -> None:
    calendar = lend.FIXTURE
    observed = lend.headroom_sweep(calendar, "headroom-observed")
    committed = lend.headroom_sweep(calendar, "headroom-committed")
    ensure(observed["least_noninterferent_headroom"] == calendar.lender_slots,
           "an observed-idle reserve became safe while still lending")
    ensure(observed["sweep"][-1]["useful_slack"]["borrowed_max"] == 0,
           "the only safe observed-idle reserve must lend nothing")
    ensure(all(row["status"] == "noninterferent" for row in committed["sweep"]),
           "a reserve against the public commitment cannot depend on the secret")
    least = committed["least_headroom_meeting_both"]
    ensure(least == max(calendar.declared_cap),
           "the least usable committed reserve is the lender's committed peak")
    ensure(committed["useful_slack_at_least_headroom_meeting_both"]["borrowed_min"] > 0,
           "the least committed reserve leaves no useful slack")
    zero = lend.analyze(calendar, lend.Policy("headroom-observed-0", "headroom-observed", 0))
    idle = lend.analyze(calendar, lend.Policy("lend-any-idle", "any-idle"))
    ensure(zero["useful_slack"] == idle["useful_slack"] and zero["status"] == idle["status"],
           "lend-any-idle is the zero member of the observed-idle family")
    full = lend.analyze(calendar, lend.Policy("full", "headroom-committed", calendar.lender_slots))
    none = lend.analyze(calendar, lend.Policy("none", "none"))
    ensure(full["useful_slack"] == none["useful_slack"],
           "reserving the whole pool is the no-lending baseline")


def declassification_is_what_the_release_rule_needs() -> None:
    calendar = lend.FIXTURE
    policy = lend.Policy("release-declassified", "release-declassified")
    hidden = lend.analyze(calendar, policy)
    shown = lend.analyze(calendar, policy, calendar.release_points)
    ensure(hidden["status"] == "distinguishing" and shown["status"] == "noninterferent",
           "the rule must be unsafe without its labels and safe with them")
    ensure(shown["observations_from_public_inputs"]["status"] == "public-function",
           "with its labels the rule must recompute from public inputs alone")
    ensure(hidden["observations_from_public_inputs"]["status"] == "not-a-public-function",
           "without its labels the rule cannot be a public function")
    ensure(shown["return_capacity"]["status"] == "overcommits"
           and shown["return_capacity"]["violating_traces"] > 0,
           "a declassified label about the past does not reserve return capacity")
    declared = lend.analyze(calendar, lend.Policy("release-declared", "release-declared"))
    ensure(declared["status"] == "noninterferent"
           and declared["observations_from_public_inputs"]["status"] == "public-function"
           and declared["return_capacity"]["status"] == "return-safe",
           "the declared-commitment rule must pass both verdicts with no declassification")
    flat = lend.analyze(calendar, lend.Policy("flat", "headroom-committed",
                                              max(calendar.declared_cap)))
    ensure(declared["useful_slack"]["borrowed_min"] > flat["useful_slack"]["borrowed_max"],
           "a time-varying commitment must beat the flat reserve to be worth declaring")


def malformed_models_and_oversized_spaces_are_refused() -> None:
    calendar = lend.FIXTURE
    not_a_flag: Any = 1
    bad: list[tuple[lend.Calendar, lend.Policy]] = [
        (lend.Calendar(4, 2, 1, (1, 1, 1), (0,), calendar.requests[:1]),
         lend.Policy("p", "none")),
        (lend.Calendar(4, 2, 1, (1, 1, 1, 3), (0,), calendar.requests[:1]),
         lend.Policy("p", "none")),
        (lend.Calendar(4, 2, 1, (1, 1, 1, 1), (1,), calendar.requests[:1]),
         lend.Policy("p", "none")),
        (lend.Calendar(4, 2, 1, (1, 1, 1, 1), (0,), ()), lend.Policy("p", "none")),
        (lend.Calendar(4, 2, 1, (1, 1, 1, 1), (0,),
                       (lend.Request("a", (1, 1), 2),)), lend.Policy("p", "none")),
        (lend.Calendar(4, 2, 1, (1, 1, 1, 1), (0,),
                       (lend.Request("a", (0,), 0),)), lend.Policy("p", "none")),
        (lend.Calendar(4, 2, 1, (1, 1, 1, 1), (0,), calendar.requests[:1]),
         lend.Policy("p", "invented")),
        (lend.Calendar(4, 2, 1, (1, 1, 1, 1), (0,), calendar.requests[:1]),
         lend.Policy("p", "headroom-committed", 3)),
        (lend.Calendar(4, 2, 1, (1, 1, 1, 1), (0,), calendar.requests[:1]),
         lend.Policy("p", "none", 0, (9,))),
        (lend.Calendar(4, 2, 1, (1, 1, 1, 1), (0,), calendar.requests[:1]),
         lend.Policy("p", "none", 0, (), not_a_flag)),
        (lend.Calendar(4, 2, True, (1, 1, 1, 1), (0,), calendar.requests[:1]),
         lend.Policy("p", "none")),
    ]
    for model, policy in bad:
        try:
            lend.validate(model, policy)
        except ValueError:
            continue
        raise AssertionError(f"an invalid model was admitted: {policy.kind}")
    wide = lend.Calendar(12, 3, 1, (2,) * 12, (0,), calendar.requests[:1])
    try:
        lend.admitted_traces(wide)
    except ValueError:
        pass
    else:
        raise AssertionError("an unbounded secret space was enumerated anyway")
    for trace in ((0, 0), (0, 3, 0, 0, 0, 0, 0, 0)):
        try:
            lend.check_trace(calendar, trace)
        except ValueError:
            continue
        raise AssertionError("a trace outside the declared commitment was admitted")
    try:
        lend.analyze(calendar, lend.Policy("p", "none"), (2, 1))
    except ValueError:
        pass
    else:
        raise AssertionError("unordered declassified instants were accepted")


def channels_separate_refusal_from_timing() -> None:
    calendar = lend.FIXTURE
    idle = lend.analyze(calendar, lend.Policy("lend-any-idle", "any-idle"))
    for name in ("refusal", "timing"):
        witness = idle["channels"][name]
        ensure(witness is not None and witness["channel"] == name,
               f"lend-any-idle no longer exhibits the {name} channel")
        verdicts = [tuple(row["verdict"] for row in witness[side])
                    for side in ("observation_a", "observation_b")]
        completions = [tuple(row["completion_tick"] for row in witness[side])
                       for side in ("observation_a", "observation_b")]
        if name == "refusal":
            ensure(verdicts[0] != verdicts[1] and "refused" in verdicts[0] + verdicts[1],
                   "the refusal channel must show a refusal")
        else:
            ensure(verdicts[0] == verdicts[1] and completions[0] != completions[1],
                   "the timing channel must keep every verdict and move a completion tick")
    ensure(all(len(idle["channels"][name]["differing_ticks"]) == 1
               for name in ("refusal", "timing")),
           "both leaks are visible from a one-tick difference in the secret")
    for one, other in product(lend.VERDICTS, repeat=2):
        first: lend.Observation = (("r", one, None, 1),)
        second: lend.Observation = (("r", other, None, 1),)
        found = lend.channel(first, second)
        ensure((found is None) == (one == other), "channel naming must follow the verdicts")
        if one != other:
            ensure(found == ("refusal" if "refused" in (one, other) else "verdict"),
                   "a refusal difference is not an own-pool-versus-loan difference")
    ensure(lend.channel((("r", "borrowed", None, 2),), (("r", "borrowed", None, 3),)) == "timing",
           "equal verdicts with unequal completion ticks travel on the timing channel")


def padding_closes_the_timing_channel_and_not_the_refusal_channel() -> None:
    calendar = lend.FIXTURE
    bare = lend.Policy("lend-any-idle", "any-idle")
    padded = lend.Policy("lend-any-idle-padded", "any-idle", pad_to_release_points=True)
    open_leak = lend.analyze(calendar, bare)
    closed = lend.analyze(calendar, padded)
    ensure(open_leak["channels"]["timing"] is not None
           and closed["channels"]["timing"] is None,
           "padding every completion to a declared instant must close the timing channel")
    ensure(closed["channels"]["refusal"] is not None and closed["status"] == "distinguishing",
           "padding cannot reach a refusal, so the policy stays refuted")
    ensure(_pairwise(calendar, padded, ())[0] == "distinguishing",
           "the independent checker must still refute the padded policy")
    ensure(closed["useful_slack"] == open_leak["useful_slack"],
           "padding moves no verdict, so it changes no slack")
    completions = [row[3] for trace in lend.admitted_traces(calendar)
                   for row in lend.run(calendar, padded, trace).observation if row[3] is not None]
    ensure(all(tick in calendar.release_points or tick == calendar.horizon
               for tick in completions), "a padded completion sits on a declared instant")
    late = [lend.run(calendar, policy, (0,) * calendar.horizon).observation
            for policy in (bare, padded)]
    ensure(any(one[3] != other[3] for one, other in zip(*late, strict=True)),
           "padding must actually delay a completion on the reference trace")


def the_receipt_is_deterministic_and_keeps_its_scope() -> None:
    root = Path(__file__).resolve().parents[2]
    first: dict[str, Any] = lend.report(root)
    ensure(first == lend.report(root), "the receipt is not reproducible")
    ensure(not first["errors"], f"the receipt carries findings: {first['errors']}")
    ensure(set(first["sources_sha256"]) == set(lend.SOURCES), "source closure missing")
    ensure(first["excluded_by"] == ["R-08-012c", "R-08-047"],
           "the receipt must name the entries that exclude this branch")
    ensure("no general theorem" in first["analyses"][0]["scope"],
           "every analysis states the scope its enumeration has")
    ensure(first["observation_model"]["unmodeled"], "the unmodeled list must not be empty")


def cases() -> list[Case]:
    return [Case(fn.__name__, fn) for fn in (
        enumeration_matches_a_direct_pairwise_checker,
        the_simulator_agrees_with_independent_interval_colouring,
        refusal_typing_and_declared_attempts_are_preserved,
        a_mutated_safe_policy_is_caught_on_both_verdicts,
        the_two_headroom_families_separate_and_meet_their_limits,
        declassification_is_what_the_release_rule_needs,
        malformed_models_and_oversized_spaces_are_refused,
        channels_separate_refusal_from_timing,
        padding_closes_the_timing_channel_and_not_the_refusal_channel,
        the_receipt_is_deterministic_and_keeps_its_scope,
    )]
