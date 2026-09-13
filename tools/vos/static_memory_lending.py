# SPDX-License-Identifier: Apache-2.0
"""Two-run lending witnesses: borrower observations against a secret lender trace.

Borrowing is excluded today by R-08-012c and R-08-047, so nothing here proposes a
lending mechanism: this is a finite measurement of what the excluded branch would
cost. The borrower's verdict and completion tick are the observations, the lender's
occupancy trace is the secret, and one scheduler tick is the finest instant the
model has. Two verdicts are reported separately and neither implies the other: a
two-run noninterference result over the enumerated space, and a return-capacity
result about whether a granted loan can outlive the lender's own admitted demand.
A result here belongs to the calendar that produced it, so the receipt also carries
the counterexample calendars that bound what the fixture's own results may be read
to say.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import product
from pathlib import Path
from typing import Any, TypedDict

VERDICTS = ("own-pool", "borrowed", "refused")
REFUSAL_REASONS = ("capacity-exhausted", "outside-horizon")
KINDS = ("none", "any-idle", "headroom-observed", "headroom-committed",
         "release-declared", "release-declassified")
CHANNELS = ("refusal", "verdict", "timing")
MAX_TRACES = 1024

type Trace = tuple[int, ...]
type Sighting = tuple[str, str, str | None, int | None]
type Observation = tuple[Sighting, ...]
type Label = tuple[int, ...]


class SightingRow(TypedDict):
    """One borrower observation. Which attempt served it is not observed, only when."""

    request: str
    verdict: str
    refusal_reason: str | None
    completion_tick: int | None


class PairWitness(TypedDict):
    """A minimal distinguishing pair of admitted lender traces with equal labels."""

    channel: str
    differing_ticks: list[int]
    lender_trace_a: list[int]
    lender_trace_b: list[int]
    observation_a: list[SightingRow]
    observation_b: list[SightingRow]


class SlackRow(TypedDict):
    """What the borrower actually gets, as a range over the admitted lender traces."""

    own_pool_min: int
    own_pool_max: int
    borrowed_min: int
    borrowed_max: int
    refused_min: int
    refused_max: int
    borrowed_slot_ticks_min: int
    borrowed_slot_ticks_max: int
    constant_across_traces: bool


class ReturnRow(TypedDict):
    """Whether a loan can outlive the lender's own admitted demand for that slot."""

    status: str
    violating_traces: int
    witness_trace: list[int] | None
    witness_ticks: list[int] | None


class GrantRow(TypedDict):
    """Whether what the rule grants is fixed by the public label, probed black-box."""

    status: str
    label: list[int] | None
    capacity_a: list[int] | None
    capacity_b: list[int] | None


@dataclass(frozen=True)
class Request:
    """One public borrower request: declared retry instants and a fixed hold length."""

    id: str
    attempts: tuple[int, ...]
    duration: int


@dataclass(frozen=True)
class Calendar:
    """The public half of the model: pool shapes, the request calendar, the commitment.

    `declared_cap` is the lender's publicly committed per-tick occupancy ceiling and
    is also the envelope of the admitted secret set, so the enumeration and the
    commitment cannot disagree. `release_points` are the instants at which the
    lender declares a new segment of that commitment.
    """

    horizon: int
    lender_slots: int
    borrower_slots: int
    declared_cap: tuple[int, ...]
    release_points: tuple[int, ...]
    requests: tuple[Request, ...]


@dataclass(frozen=True)
class Policy:
    """A lending rule. `leaking_ticks` is a deliberate defect, never a design option.

    At a leaking tick the rule reads the lender's actual occupancy instead of its
    public commitment. The field exists so the enumeration can be shown to notice
    a mutation that turns a safe policy unsafe. `pad_to_release_points` is the
    separate timing countermeasure: every completion is delayed to the next declared
    release instant, which buys latency for the borrower and reveals nothing about
    when service actually happened.
    """

    name: str
    kind: str
    headroom: int = 0
    leaking_ticks: tuple[int, ...] = ()
    pad_to_release_points: bool = False


@dataclass(frozen=True)
class Run:
    """One run's borrower observation and the model-level facts it cannot see.

    `served` is the attempt index each request was served at. It is a fact about
    the run and deliberately not part of the observation, since a borrower that
    read it would see straight through a padded completion tick.
    """

    observation: Observation
    borrowed: tuple[int, ...]
    overcommitted_ticks: tuple[int, ...]
    served: tuple[int | None, ...]


def _positive(value: object) -> bool:
    return type(value) is int and value > 0


def _nonnegative(value: object) -> bool:
    return type(value) is int and value >= 0


def validate(calendar: Calendar, policy: Policy) -> None:
    """Refuse a model whose public half is not well formed before enumerating it."""
    if not (_positive(calendar.horizon) and _positive(calendar.lender_slots)
            and _positive(calendar.borrower_slots)):
        raise ValueError("horizon and both pool sizes must be positive integers")
    if len(calendar.declared_cap) != calendar.horizon:
        raise ValueError("the declared occupancy commitment must cover every tick")
    if any(not _nonnegative(cap) or cap > calendar.lender_slots
           for cap in calendar.declared_cap):
        raise ValueError("each committed ceiling must fit the lender pool")
    points = calendar.release_points
    if not points or points[0] != 0 or any(
            not _nonnegative(point) or point >= calendar.horizon for point in points):
        raise ValueError("release instants start at tick zero and lie inside the horizon")
    if list(points) != sorted(set(points)):
        raise ValueError("release instants must be strictly increasing")
    if not calendar.requests:
        raise ValueError("the borrower calendar needs at least one request")
    if len({request.id for request in calendar.requests}) != len(calendar.requests):
        raise ValueError("request identities must be distinct")
    for request in calendar.requests:
        if not _positive(request.duration) or not request.attempts:
            raise ValueError("every request has a positive duration and one declared attempt")
        if list(request.attempts) != sorted(set(request.attempts)) or any(
                not _nonnegative(tick) or tick >= calendar.horizon
                for tick in request.attempts):
            raise ValueError("attempt instants must increase strictly inside the horizon")
    if policy.kind not in KINDS:
        raise ValueError(f"unknown lending policy kind: {policy.kind}")
    if not _nonnegative(policy.headroom) or policy.headroom > calendar.lender_slots:
        raise ValueError("reserved headroom must be a slot count inside the lender pool")
    if any(not _nonnegative(tick) or tick >= calendar.horizon
           for tick in policy.leaking_ticks):
        raise ValueError("a deliberate leaking tick must lie inside the horizon")
    if type(policy.pad_to_release_points) is not bool:
        raise ValueError("completion padding is on or off, not a quantity")


def check_trace(calendar: Calendar, trace: Trace) -> None:
    """A secret trace is admitted only inside the lender's own public commitment."""
    if len(trace) != calendar.horizon:
        raise ValueError("a lender occupancy trace covers every modeled tick")
    if any(not _nonnegative(occupancy) or occupancy > cap
           for occupancy, cap in zip(trace, calendar.declared_cap, strict=True)):
        raise ValueError("lender occupancy leaves its declared commitment")


def admitted_traces(calendar: Calendar) -> tuple[Trace, ...]:
    """Every secret trace the public commitment admits, in lexicographic order."""
    total = 1
    for cap in calendar.declared_cap:
        total *= cap + 1
    if total > MAX_TRACES:
        raise ValueError(f"admitted set of {total} traces exceeds the enumeration budget")
    return tuple(product(*(range(cap + 1) for cap in calendar.declared_cap)))


def anchors(calendar: Calendar) -> tuple[int, ...]:
    """The latest declared release instant at or before each tick."""
    return tuple(max(point for point in calendar.release_points if point <= tick)
                 for tick in range(calendar.horizon))


def borrow_capacity(calendar: Calendar, policy: Policy, trace: Trace) -> tuple[int, ...]:
    """Per-tick lender slots the policy makes borrowable under one secret trace."""
    validate(calendar, policy)
    check_trace(calendar, trace)
    slots = calendar.lender_slots
    anchor = anchors(calendar)
    values: list[int] = []
    for tick in range(calendar.horizon):
        match policy.kind:
            case "none":
                value = 0
            case "any-idle":
                value = slots - trace[tick]
            case "headroom-observed":
                value = slots - trace[tick] - policy.headroom
            case "headroom-committed":
                value = slots - policy.headroom
            case "release-declared":
                value = slots - calendar.declared_cap[tick]
            case _:
                value = slots - trace[anchor[tick]]
        if tick in policy.leaking_ticks:
            value = slots - trace[tick]
        values.append(max(0, value))
    return tuple(values)


def public_capacity(calendar: Calendar, policy: Policy, label: Label,
                    declassified: tuple[int, ...]) -> tuple[int, ...] | None:
    """The capacity a reader holding only public inputs and the label can compute.

    `None` means the rule is not a function of the public inputs at all, which is
    the finding itself and not a failure of this routine. Where a rule is a public
    function this restates its capacity without the trace in scope, so the check it
    feeds is double entry rather than an independent derivation: it catches a rule
    that reaches for the secret or a transcription slip, and the black-box probe in
    `_granted` is what decides whether the grant moves with the secret at all.
    """
    validate(calendar, policy)
    if policy.leaking_ticks:
        return None
    slots = calendar.lender_slots
    known = dict(zip(declassified, label, strict=True))
    if policy.kind == "none":
        return (0,) * calendar.horizon
    if policy.kind == "headroom-committed":
        return (max(0, slots - policy.headroom),) * calendar.horizon
    if policy.kind == "release-declared":
        return tuple(max(0, slots - cap) for cap in calendar.declared_cap)
    if policy.kind == "release-declassified" and all(
            point in known for point in anchors(calendar)):
        return tuple(max(0, slots - known[point]) for point in anchors(calendar))
    return None


def simulate(calendar: Calendar,
             capacity: tuple[int, ...]) -> tuple[Observation, tuple[int, ...],
                                                 tuple[int | None, ...]]:
    """Serve the public calendar against a fixed borrowable capacity, in calendar order.

    A request takes its own pool where the whole hold window fits, then a loan
    where the whole window fits, and otherwise waits for its next publicly declared
    attempt instant. There is no implicit wait: a request that exhausts its declared
    attempts carries a typed refusal rather than blocking.
    """
    if len(capacity) != calendar.horizon:
        raise ValueError("a capacity vector covers every modeled tick")
    own = [0] * calendar.horizon
    borrowed = [0] * calendar.horizon
    sightings: list[Sighting] = []
    served: list[int | None] = []
    for request in calendar.requests:
        placed: Sighting | None = None
        attempt: int | None = None
        usable = False
        for index, tick in enumerate(request.attempts):
            if tick + request.duration > calendar.horizon:
                continue
            usable = True
            window = range(tick, tick + request.duration)
            if all(own[unit] < calendar.borrower_slots for unit in window):
                for unit in window:
                    own[unit] += 1
                placed, attempt = (request.id, "own-pool", None, tick + request.duration), index
                break
            if all(borrowed[unit] < capacity[unit] for unit in window):
                for unit in window:
                    borrowed[unit] += 1
                placed, attempt = (request.id, "borrowed", None, tick + request.duration), index
                break
        if placed is None:
            reason = "capacity-exhausted" if usable else "outside-horizon"
            placed = (request.id, "refused", reason, None)
        sightings.append(placed)
        served.append(attempt)
    return tuple(sightings), tuple(borrowed), tuple(served)


def pad(calendar: Calendar, observation: Observation) -> Observation:
    """Delay every completion to the first declared instant at or after it, or the horizon.

    A completion already sitting on a declared instant is not moved, so padding
    confuses two completions only where both fall strictly inside one declared
    segment: whether it closes a timing channel is a property of how the instants
    are spaced against the completions, not of the rule. This is the timing
    countermeasure on its own: it moves no verdict, so it cannot close the refusal
    channel, and the borrower pays for it in latency.
    """
    instants = (*calendar.release_points, calendar.horizon)
    return tuple((request, verdict, reason, None if completion is None
                  else min(point for point in instants if point >= completion))
                 for request, verdict, reason, completion in observation)


def observe(calendar: Calendar, policy: Policy,
            capacity: tuple[int, ...]) -> tuple[Observation, tuple[int, ...],
                                                tuple[int | None, ...]]:
    """Everything the borrower sees under one policy, padding included."""
    observation, borrowed, served = simulate(calendar, capacity)
    if policy.pad_to_release_points:
        observation = pad(calendar, observation)
    return observation, borrowed, served


def run(calendar: Calendar, policy: Policy, trace: Trace) -> Run:
    """One complete run, plus the overcommit the borrower's observation cannot show."""
    observation, borrowed, served = observe(
        calendar, policy, borrow_capacity(calendar, policy, trace))
    over = tuple(tick for tick in range(calendar.horizon)
                 if trace[tick] + borrowed[tick] > calendar.lender_slots)
    return Run(observation, borrowed, over, served)


def rows(observation: Observation) -> list[SightingRow]:
    """Render one observation as receipt rows without changing what it distinguishes."""
    return [SightingRow(request=request, verdict=verdict, refusal_reason=reason,
                        completion_tick=completion)
            for request, verdict, reason, completion in observation]


def channel(first: Observation, second: Observation) -> str | None:
    """Name the channel a difference travels on, or `None` where there is none.

    A verdict difference involving a refusal, or a difference in the refusal reason
    itself, is the refusal channel; a verdict difference between own-pool and
    borrowed service is the verdict channel; equal verdicts and equal reasons with
    an unequal completion tick is the timing channel. The reason is checked on its
    own because a secret-dependent reason is a refusal leak whatever the verdicts do.
    """
    left = tuple(sighting[1] for sighting in first)
    right = tuple(sighting[1] for sighting in second)
    if left != right:
        return "refusal" if any(
            one != other and "refused" in (one, other)
            for one, other in zip(left, right, strict=True)) else "verdict"
    if any(one[2] != other[2] for one, other in zip(first, second, strict=True)):
        return "refusal"
    return "timing" if first != second else None


def _witness(calendar: Calendar, traces: tuple[Trace, ...], runs: list[Run],
             members: list[int], wanted: str | None
             ) -> tuple[tuple[int, int, int], PairWitness] | None:
    """The least distinguishing pair inside one label class, with its ordering key."""
    best: tuple[tuple[int, int, int], PairWitness] | None = None
    for position, index in enumerate(members):
        for other in members[position + 1:]:
            found = channel(runs[index].observation, runs[other].observation)
            if found is None or (wanted is not None and found != wanted):
                continue
            differing = [tick for tick in range(calendar.horizon)
                         if traces[index][tick] != traces[other][tick]]
            key = (len(differing), index, other)
            if best is not None and key >= best[0]:
                continue
            best = (key, PairWitness(
                channel=found, differing_ticks=differing,
                lender_trace_a=list(traces[index]), lender_trace_b=list(traces[other]),
                observation_a=rows(runs[index].observation),
                observation_b=rows(runs[other].observation)))
    return best


def _least_witness(calendar: Calendar, traces: tuple[Trace, ...], runs: list[Run],
                   distinguishing: list[list[int]], wanted: str | None) -> PairWitness | None:
    """The least witness over every label class, not the first class to hold one.

    Taking the first class would report a witness minimal only inside that class, so
    a later class with a smaller difference in the secret would never be consulted.
    The key orders by differing ticks and then by enumeration order, and trace
    indices are global, so the minimum is total and independent of class order.
    """
    found = [candidate for members in distinguishing
             if (candidate := _witness(calendar, traces, runs, members, wanted)) is not None]
    return min(found, key=lambda item: item[0])[1] if found else None


def _slack(runs: list[Run]) -> SlackRow:
    counts = [(*(sum(1 for sighting in item.observation if sighting[1] == verdict)
                 for verdict in VERDICTS), sum(item.borrowed))
              for item in runs]
    columns = list(zip(*counts, strict=True))
    return SlackRow(
        own_pool_min=min(columns[0]), own_pool_max=max(columns[0]),
        borrowed_min=min(columns[1]), borrowed_max=max(columns[1]),
        refused_min=min(columns[2]), refused_max=max(columns[2]),
        borrowed_slot_ticks_min=min(columns[3]), borrowed_slot_ticks_max=max(columns[3]),
        constant_across_traces=len(set(counts)) == 1)


def _granted(calendar: Calendar, policy: Policy, traces: tuple[Trace, ...],
             classes: dict[Label, list[int]]) -> GrantRow:
    """Probe the rule itself: does the amount it grants move with the secret?

    This evaluates `borrow_capacity` over the admitted set and compares the vectors
    inside each label class, so it restates no formula and would notice a rule that
    reads the secret however it is written. It is a fact about the grant and not
    about the borrower: a grant that moves with the secret is observable only where
    a request reaches the ticks at which it moves, which is why the receipt reports
    this beside the noninterference verdict rather than in place of it.
    """
    for label, members in classes.items():
        vectors = sorted({borrow_capacity(calendar, policy, traces[index])
                          for index in members})
        if len(vectors) > 1:
            return GrantRow(status="reads-the-secret", label=list(label),
                            capacity_a=list(vectors[0]), capacity_b=list(vectors[1]))
    return GrantRow(status="label-determined", label=None,
                    capacity_a=None, capacity_b=None)


def _return_capacity(traces: tuple[Trace, ...], runs: list[Run]) -> ReturnRow:
    offenders = [index for index, item in enumerate(runs) if item.overcommitted_ticks]
    if not offenders:
        return ReturnRow(status="return-safe", violating_traces=0,
                         witness_trace=None, witness_ticks=None)
    first = offenders[0]
    return ReturnRow(status="overcommits", violating_traces=len(offenders),
                     witness_trace=list(traces[first]),
                     witness_ticks=list(runs[first].overcommitted_ticks))


def analyze(calendar: Calendar, policy: Policy,
            declassified: tuple[int, ...] = ()) -> dict[str, Any]:
    """Enumerate the admitted secret set and decide both verdicts over it.

    Low-equivalence is equality of the declassified label, so an empty label makes
    every admitted trace low-equivalent and states the strong model. The scope is
    this finite calendar and this admitted set: a policy with no distinguishing
    pair here is not thereby proved noninterferent in general.
    """
    validate(calendar, policy)
    if any(not _nonnegative(tick) or tick >= calendar.horizon for tick in declassified):
        raise ValueError("a declassified instant must lie inside the horizon")
    if list(declassified) != sorted(set(declassified)):
        raise ValueError("declassified instants must be strictly increasing")
    traces = admitted_traces(calendar)
    runs = [run(calendar, policy, trace) for trace in traces]
    classes: dict[Label, list[int]] = {}
    for index, trace in enumerate(traces):
        classes.setdefault(tuple(trace[tick] for tick in declassified), []).append(index)
    distinguishing = [members for members in classes.values()
                      if len({runs[index].observation for index in members}) > 1]
    witnesses: dict[str, PairWitness | None] = {
        name: _least_witness(calendar, traces, runs, distinguishing, name)
        for name in CHANNELS}
    minimal = _least_witness(calendar, traces, runs, distinguishing, None)
    public: dict[str, Any] = {"status": "not-a-public-function", "mismatches": None}
    vectors = [public_capacity(calendar, policy,
                               tuple(trace[tick] for tick in declassified), declassified)
               for trace in traces]
    if all(vector is not None for vector in vectors):
        mismatches = sum(1 for vector, item in zip(vectors, runs, strict=True)
                         if vector is not None
                         and observe(calendar, policy, vector)[0] != item.observation)
        public = {"status": "public-function" if not mismatches else "recomputation-differs",
                  "mismatches": mismatches}
    return {
        "policy": asdict(policy),
        "declassified_points": list(declassified),
        "admitted_traces": len(traces),
        "label_classes": len(classes),
        "status": "distinguishing" if distinguishing else "noninterferent",
        "minimal_distinguishing_pair": minimal,
        "channels": witnesses,
        "granted_capacity": _granted(calendar, policy, traces, classes),
        "observations_from_public_inputs": public,
        "return_capacity": _return_capacity(traces, runs),
        "useful_slack": _slack(runs),
        "scope": ("one finite calendar and one admitted secret set, at scheduler-tick "
                  "granularity; no general theorem and no admission of lending"),
    }


def headroom_sweep(calendar: Calendar, kind: str,
                   declassified: tuple[int, ...] = ()) -> dict[str, Any]:
    """Sweep every reserved headroom the lender pool admits and report both least values."""
    if kind not in ("headroom-observed", "headroom-committed"):
        raise ValueError("only a headroom family can be swept")
    sweep: list[dict[str, Any]] = []
    for reserve in range(calendar.lender_slots + 1):
        policy = Policy(f"{kind}-{reserve}", kind, reserve)
        result = analyze(calendar, policy, declassified)
        sweep.append({"headroom": reserve,
                      "status": result["status"],
                      "return_capacity": result["return_capacity"]["status"],
                      "useful_slack": result["useful_slack"],
                      "channels": [name for name, found in result["channels"].items()
                                   if found is not None]})
    safe = [row["headroom"] for row in sweep if row["status"] == "noninterferent"]
    returning = [row["headroom"] for row in sweep if row["return_capacity"] == "return-safe"]
    both = [row for row in sweep
            if row["headroom"] in safe and row["headroom"] in returning]
    return {
        "kind": kind,
        "sweep": sweep,
        "least_noninterferent_headroom": safe[0] if safe else None,
        "least_return_safe_headroom": returning[0] if returning else None,
        "least_headroom_meeting_both": both[0]["headroom"] if both else None,
        "useful_slack_at_least_headroom_meeting_both": both[0]["useful_slack"] if both else None,
        "scope": ("least over this enumerated calendar and admitted set; a smaller "
                  "reserve refuted here, a larger one not thereby proved in general"),
    }


FIXTURE = Calendar(
    horizon=8,
    lender_slots=3,
    borrower_slots=1,
    declared_cap=(2, 2, 2, 1, 1, 0, 0, 0),
    release_points=(0, 3, 5),
    requests=(
        Request("own-only", (0,), 2),
        Request("long-borrow", (0,), 5),
        Request("contended", (0, 1), 2),
        Request("own-filler", (2,), 3),
        Request("late-borrow", (3,), 2),
    ),
)

POLICIES = (
    Policy("none", "none"),
    Policy("lend-any-idle", "any-idle"),
    Policy("lend-any-idle-padded", "any-idle", pad_to_release_points=True),
    Policy("headroom-observed-1", "headroom-observed", 1),
    Policy("headroom-committed-2", "headroom-committed", 2),
    Policy("release-declared", "release-declared"),
    Policy("release-declassified", "release-declassified"),
)

NEIGHBOUR = Policy("headroom-committed-2-reading-the-secret", "headroom-committed", 2, (0, 1, 2))

PADDING_OPEN = Calendar(
    horizon=5,
    lender_slots=2,
    borrower_slots=1,
    declared_cap=(1, 1, 1, 1, 0),
    release_points=(0, 2),
    requests=(
        Request("own", (0,), 2),
        Request("loan", (0,), 3),
        Request("retry", (0, 1, 2), 2),
    ),
)

GRANT_UNOBSERVED = Calendar(
    horizon=4,
    lender_slots=3,
    borrower_slots=1,
    declared_cap=(0, 0, 1, 1),
    release_points=(0,),
    requests=(
        Request("early", (0,), 2),
        Request("contended", (0, 2), 2),
        Request("short", (1, 3), 1),
    ),
)

COUNTEREXAMPLES: dict[str, tuple[Calendar, Policy, str | None]] = {
    "padding-does-not-close-timing-in-general": (
        PADDING_OPEN, Policy("lend-any-idle-padded", "any-idle",
                             pad_to_release_points=True), None),
    "an-observed-idle-reserve-can-be-safe-and-still-lend": (
        GRANT_UNOBSERVED, Policy("headroom-observed-1", "headroom-observed", 1),
        "headroom-observed"),
}

SOURCES = ("tools/vos/static_memory_lending.py",
           "tools/tests/test_static_memory_lending.py",
           "docs/implementation/static-memory-lending.md")


def _counterexamples() -> dict[str, dict[str, Any]]:
    """Enumerate the calendars that bound the scope of the fixture's own results.

    Each entry refutes a statement the fixture alone would invite: that padding
    closes a timing channel, and that a reserve subtracted from observed idle
    capacity must choose between lending and hiding. They are part of the receipt so
    the bound is replayed rather than asserted in prose.
    """
    return {
        name: {
            "question": name,
            "calendar": asdict(model),
            "analysis": analyze(model, policy),
            "headroom_sweep": None if kind is None else headroom_sweep(model, kind),
        }
        for name, (model, policy, kind) in COUNTEREXAMPLES.items()
    }


def _findings(calendar: Calendar, analyses: list[dict[str, Any]],
              declassified: dict[str, Any], neighbour: dict[str, Any],
              sweeps: dict[str, dict[str, Any]],
              counterexamples: dict[str, dict[str, Any]]) -> list[str]:
    """Bind every claim the receipt makes to an input, so fixture drift is a finding."""
    by_name = {item["policy"]["name"]: item for item in analyses}
    errors: list[str] = []
    if by_name["none"]["status"] != "noninterferent":
        errors.append("the no-lending baseline is not trivially safe")
    if by_name["none"]["useful_slack"]["borrowed_max"]:
        errors.append("the no-lending baseline served a borrowed request")
    idle = by_name["lend-any-idle"]
    errors.extend(f"lend-any-idle no longer leaks through the {name} channel"
                  for name in ("refusal", "timing") if idle["channels"][name] is None)
    padded = by_name["lend-any-idle-padded"]
    if padded["channels"]["timing"] is not None:
        errors.append("padding no longer closes the timing channel on the fixture calendar")
    if padded["channels"]["refusal"] is None:
        errors.append("padding completions closed the refusal channel it cannot reach")
    if by_name["release-declared"]["observations_from_public_inputs"]["status"] != "public-function":
        errors.append("the declared-release rule stopped being a function of public inputs")
    if by_name["release-declassified"]["status"] != "distinguishing":
        errors.append("the declassifying rule no longer needs its declassification")
    if declassified["status"] != "noninterferent":
        errors.append("the declassifying rule leaks past its own declared labels")
    if declassified["return_capacity"]["status"] != "overcommits":
        errors.append("the declassifying rule no longer exhibits the return-capacity gap")
    if neighbour["status"] != "distinguishing":
        errors.append("the mutated safe policy was not caught by the enumeration")
    observed = sweeps["headroom-observed"]
    committed = sweeps["headroom-committed"]
    if observed["least_noninterferent_headroom"] != calendar.lender_slots:
        errors.append("an observed-idle headroom below the whole pool became safe")
    if observed["sweep"][-1]["useful_slack"]["borrowed_max"]:
        errors.append("the safe observed-idle headroom still lends")
    least = committed["least_headroom_meeting_both"]
    if least is None or not 0 < least < calendar.lender_slots:
        errors.append("the committed headroom no longer has a useful least reserve")
    elif not committed["useful_slack_at_least_headroom_meeting_both"]["borrowed_max"]:
        errors.append("the least committed headroom leaves no useful slack")
    if (by_name["release-declared"]["useful_slack"]["borrowed_max"]
            <= by_name["headroom-committed-2"]["useful_slack"]["borrowed_max"]):
        errors.append("the declared-release rule is no longer more useful than a flat reserve")
    if by_name["headroom-committed-2"]["granted_capacity"]["status"] != "label-determined":
        errors.append("a reserve against the public commitment started granting on the secret")
    if idle["granted_capacity"]["status"] != "reads-the-secret":
        errors.append("lend-any-idle stopped granting on the secret")
    timing = counterexamples[
        "padding-does-not-close-timing-in-general"]["analysis"]["channels"]["timing"]
    if timing is None:
        errors.append("the padding counterexample no longer bounds the fixture's padding result")
    unobserved = counterexamples["an-observed-idle-reserve-can-be-safe-and-still-lend"]
    if (unobserved["analysis"]["status"] != "noninterferent"
            or not unobserved["analysis"]["useful_slack"]["borrowed_max"]
            or unobserved["analysis"]["granted_capacity"]["status"] != "reads-the-secret"
            or unobserved["headroom_sweep"]["least_noninterferent_headroom"]):
        errors.append("the counterexample no longer shows an observed-idle reserve "
                      "that grants on the secret, stays safe and still lends")
    return errors


def report(root: Path) -> dict[str, Any]:
    """Return a deterministic replay receipt; the shared CLI adds Git identity."""
    calendar = FIXTURE
    analyses = [analyze(calendar, policy) for policy in POLICIES]
    declassified = analyze(calendar, Policy("release-declassified", "release-declassified"),
                           calendar.release_points)
    neighbour = analyze(calendar, NEIGHBOUR)
    sweeps = {kind: headroom_sweep(calendar, kind)
              for kind in ("headroom-observed", "headroom-committed")}
    counterexamples = _counterexamples()
    return {
        "schema": "static-memory-lending-v1",
        "scope": ("finite two-run relational witnesses for an excluded branch; no "
                  "target measurement, no admission of lending and no impossibility claim"),
        "excluded_by": ["R-08-012c", "R-08-047"],
        "observation_model": {
            "observations": ("per request the verdict and the completion tick; which "
                             "attempt served it is a fact of the run, not observed"),
            "verdicts": list(VERDICTS),
            "refusal_reasons": list(REFUSAL_REASONS),
            "secret": "the lender's per-tick occupancy, drawn from the admitted set",
            "public": ("pool shapes, the borrower request and retry calendar, the "
                       "lender's declared occupancy commitment and release instants"),
            "granularity": ("one scheduler tick; sub-tick timing, cache state and "
                            "fabric contention are outside the model"),
            "low_equivalence": "equality of the declassified label, empty unless stated",
            "unmodeled": ["sub-tick timing", "cache and predictor state",
                          "fabric and bank contention", "energy", "ownership transition proofs",
                          "authority revocation between owners"],
        },
        "calendar": asdict(calendar),
        "analyses": analyses,
        "declassified_release_points": declassified,
        "mutated_neighbour": neighbour,
        "headroom_sweeps": sweeps,
        "counterexamples": counterexamples,
        "errors": _findings(calendar, analyses, declassified, neighbour, sweeps,
                            counterexamples),
        "sources_sha256": {name: sha256((root / name).read_bytes()).hexdigest()
                           for name in SOURCES},
    }
