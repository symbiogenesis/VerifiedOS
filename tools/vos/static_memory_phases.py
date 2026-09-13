# SPDX-License-Identifier: Apache-2.0
"""Compositional reuse under public phases: finite model, candidate rules, witnesses.

The compositional checker consumes per-component certificates and the global reuse
rule alone; the exhaustive search enumerates every admitted completion timing and
can refute a rule. Agreement over this finite fixture is bounded executable
evidence for a conjecture, never a theorem, a barrier implementation or a change
to any requirement. Ticks are synthetic model quantities, not measured times.

Two things a reader would otherwise have to take on trust are computed instead. The
outstanding-completion bound a certificate declares is recomputed from the
composition, so `validate` refuses a certificate its own transfers falsify; and how
small a counterexample can be is settled by a reduction search over a declared
operator set, which reports irreducibility under those operators rather than
minimality among all compositions.
"""

from dataclasses import dataclass, replace
from itertools import pairwise, product
from typing import Any, TypedDict

RULES: tuple[str, ...] = ("R0", "R1", "R2")
MUTANTS: tuple[str, ...] = ("R2-skip-device", "R2-skip-pass")
SUMMARIES: tuple[str, ...] = ("honest", "drop-retained", "drop-completion-bound",
                              "chain-local-window")
OUT_OF_WINDOW_DELTAS: tuple[int, ...] = (1, 2, 3, 4)
REDUCTIONS: tuple[str, ...] = ("merge-components", "drop-transfer", "shrink-window",
                               "drop-retention", "drop-representation")


@dataclass(frozen=True)
class Transfer:
    """One accepted asynchronous device transfer and its declared completion window.

    `depends_on` names the transfer whose completion is this one's acceptance event.
    A chained acceptance is what makes a per-component window bound unsound as a
    global bound: the acceptance is no longer a public phase boundary.
    """

    name: str
    object_id: str
    accept_phase: int
    window: int
    depends_on: str | None = None


@dataclass(frozen=True)
class Obj:
    """One object bound to one global extent for a contiguous run of phases.

    `retained_through` is the retained-state half of the certificate's retained set:
    occupancy runs to the end of that phase, past the last public live phase.
    `stale_holder` is its representation half: a capability-bearing holder that can
    write the extent until a full post-barrier pass removes it.
    """

    id: str
    extent: str
    live_phases: tuple[int, ...]
    retained_through: int | None = None
    stale_holder: bool = False


@dataclass(frozen=True)
class Component:
    """A fixed public phase schedule with its objects, transfers and declared bounds.

    `declared_window` is the maximum per-transfer completion window R1 reads.
    `declared_outstanding` is the certificate's outstanding-completion bound: the
    latest tick past an object's occupancy end at which an accepted transfer under
    its authority can still complete. The two differ exactly when acceptance is not
    at a public boundary.
    """

    name: str
    phase_bounds: tuple[int, ...]
    labels: tuple[str, ...]
    objects: tuple[Obj, ...]
    transfers: tuple[Transfer, ...] = ()
    declared_window: int = 0
    declared_outstanding: int = 0


@dataclass(frozen=True)
class Composition:
    """Components, the per-extent reuse chains, and the barrier's service constants."""

    name: str
    components: tuple[Component, ...]
    chains: tuple[tuple[str, ...], ...]
    horizon: int
    root_clear: int = 1
    sweep: int = 2


class Certificate(TypedDict):
    """Exactly the four declared fields, plus the extent binding the plan reads.

    `phase_bounds`/`labels` are the public phase schedule, `live` the per-phase live
    set, `retained_occupancy`/`retained_holders` the retained set, and
    `declared_window`/`declared_outstanding` the outstanding-completion bound. No
    acceptance time, completion time or other component's state appears here.
    """

    component: str
    phase_bounds: tuple[int, ...]
    labels: tuple[str, ...]
    live: tuple[tuple[str, ...], ...]
    retained_occupancy: tuple[tuple[str, int], ...]
    retained_holders: tuple[str, ...]
    extents: tuple[tuple[str, str], ...]
    declared_window: int
    declared_outstanding: int


class Hazard(TypedDict):
    """One old-authority event landing on an extent bound to a later object."""

    kind: str
    extent: str
    old: str
    new: str
    tick: int


def validate(comp: Composition) -> None:
    """Refuse a malformed composition rather than reporting a verdict about it."""
    if not comp.components or not comp.chains:
        raise ValueError("a composition needs at least one component and one chain")
    if any(type(value) is not int or value < 1
           for value in (comp.horizon, comp.root_clear, comp.sweep)):
        raise ValueError("horizon and barrier service constants must be positive")
    seen: set[str] = set()
    extents: dict[str, str] = {}
    transfers: dict[str, Transfer] = {}
    if len({component.name for component in comp.components}) != len(comp.components):
        raise ValueError("component names are the certificate keys and must be distinct")
    for component in comp.components:
        bounds = component.phase_bounds
        if len(bounds) < 2 or bounds[0] != 0 or any(
                later <= earlier for earlier, later in pairwise(bounds)):
            raise ValueError(f"{component.name}: phase bounds start at 0 and increase")
        if len(component.labels) != len(bounds) - 1:
            raise ValueError(f"{component.name}: one public label per phase")
        if bounds[-1] > comp.horizon:
            raise ValueError(f"{component.name}: phase schedule exceeds the horizon")
        if any(type(value) is not int or value < 0
               for value in (component.declared_window, component.declared_outstanding)):
            raise ValueError(f"{component.name}: declared bounds are nonnegative integers")
        for obj in component.objects:
            if obj.id in seen:
                raise ValueError(f"duplicate object identity: {obj.id}")
            seen.add(obj.id)
            extents[obj.id] = obj.extent
            _validate_object(component, obj)
        for transfer in component.transfers:
            if transfer.name in transfers:
                raise ValueError(f"duplicate transfer identity: {transfer.name}")
            transfers[transfer.name] = transfer
            _validate_transfer(component, transfer)
    _validate_plan(comp, seen, extents, transfers)


def _validate_object(component: Component, obj: Obj) -> None:
    phases = len(component.phase_bounds) - 1
    if not obj.live_phases or sorted(set(obj.live_phases)) != list(obj.live_phases):
        raise ValueError(f"{obj.id}: live phases are a nonempty sorted set")
    if any(index < 0 or index >= phases for index in obj.live_phases):
        raise ValueError(f"{obj.id}: a live phase is outside the schedule")
    if list(obj.live_phases) != list(range(obj.live_phases[0], obj.live_phases[-1] + 1)):
        raise ValueError(f"{obj.id}: this model binds one contiguous run of phases")
    if obj.retained_through is not None and not obj.live_phases[-1] <= obj.retained_through < phases:
        raise ValueError(f"{obj.id}: retention runs from the last live phase to a later one")


def _validate_transfer(component: Component, transfer: Transfer) -> None:
    owner = next((obj for obj in component.objects if obj.id == transfer.object_id), None)
    if owner is None:
        raise ValueError(f"{transfer.name}: names no object of {component.name}")
    if type(transfer.window) is not int or transfer.window < 1:
        raise ValueError(f"{transfer.name}: the completion window is a positive integer")
    if transfer.window > component.declared_window:
        raise ValueError(f"{transfer.name}: window exceeds the component's declared maximum")
    last = owner.retained_through if owner.retained_through is not None else owner.live_phases[-1]
    if not owner.live_phases[0] <= transfer.accept_phase <= last:
        raise ValueError(f"{transfer.name}: acceptance is outside its object's occupancy")


def _validate_plan(comp: Composition, seen: set[str], extents: dict[str, str],
                   transfers: dict[str, Transfer]) -> None:
    chained: set[str] = set()
    for chain in comp.chains:
        if not chain or len(set(chain)) != len(chain):
            raise ValueError("a reuse chain is a nonempty sequence of distinct objects")
        if any(name not in seen for name in chain):
            raise ValueError("a reuse chain names an object no component declares")
        if len({extents[name] for name in chain}) != 1:
            raise ValueError("a reuse chain binds exactly one extent")
        if chained & set(chain):
            raise ValueError("an object belongs to one reuse chain")
        chained.update(chain)
    if chained != seen:
        raise ValueError("every declared object belongs to a reuse chain")
    starts = {obj.id: component.phase_bounds[obj.live_phases[0]]
              for component in comp.components for obj in component.objects}
    for chain in comp.chains:
        ordered = [starts[name] for name in chain]
        if ordered != sorted(ordered):
            raise ValueError("a reuse chain is ordered by its objects' declared starts")
    for transfer in transfers.values():
        if transfer.depends_on is not None and transfer.depends_on not in transfers:
            raise ValueError(f"{transfer.name}: depends on no declared transfer")
    _transfer_order(comp)
    recomputed = true_outstanding(comp)
    for component in comp.components:
        if component.declared_outstanding < recomputed[component.name]:
            raise ValueError(
                f"{component.name}: the declared outstanding-completion bound is below "
                f"the latest completion its own accepted transfers admit")


def _transfer_order(comp: Composition) -> list[tuple[Component, Transfer]]:
    """Acceptance order, so a chained acceptance reads an already resolved event."""
    pending = [(component, transfer) for component in comp.components
               for transfer in component.transfers]
    resolved: set[str] = set()
    order: list[tuple[Component, Transfer]] = []
    while pending:
        ready = [row for row in pending if row[1].depends_on in (None, *resolved)]
        if not ready:
            raise ValueError("chained transfer acceptance is cyclic")
        order.extend(ready)
        resolved.update(transfer.name for _, transfer in ready)
        pending = [row for row in pending if row[1].name not in resolved]
    return order


def true_outstanding(comp: Composition) -> dict[str, int]:
    """Recompute what each component's outstanding-completion bound has to cover.

    This is the one certificate field R2's soundness rests on, so the model derives it
    from the composition rather than taking the declaration on trust: every transfer
    runs to the end of its window, chained acceptance resolved in order, and a
    component's bound is the furthest any completion under one of its objects'
    authority lands past that object's occupancy end. `validate` refuses a declaration
    below this value; a declaration above it is a conservative certificate, which costs
    reuse and cannot make an acceptance unsound.
    """
    facts = object_facts(comp)
    worst = completion_map(comp, {transfer.name: transfer.window
                                  for component in comp.components
                                  for transfer in component.transfers})
    result: dict[str, int] = {}
    for component in comp.components:
        past = [worst[transfer.name] - facts[transfer.object_id]["occupancy_end"]
                for transfer in component.transfers]
        result[component.name] = max([0, *past])
    return result


def certificate(component: Component) -> Certificate:
    """Project a component onto its certificate; acceptance and completion drop out."""
    phases = len(component.phase_bounds) - 1
    live = tuple(tuple(sorted(obj.id for obj in component.objects if index in obj.live_phases))
                 for index in range(phases))
    return {
        "component": component.name,
        "phase_bounds": component.phase_bounds,
        "labels": component.labels,
        "live": live,
        "retained_occupancy": tuple(sorted(
            (obj.id, obj.retained_through) for obj in component.objects
            if obj.retained_through is not None)),
        "retained_holders": tuple(sorted(obj.id for obj in component.objects if obj.stale_holder)),
        "extents": tuple(sorted((obj.id, obj.extent) for obj in component.objects)),
        "declared_window": component.declared_window,
        "declared_outstanding": component.declared_outstanding,
    }


def certificates(comp: Composition) -> dict[str, Certificate]:
    return {component.name: certificate(component) for component in comp.components}


def _phases_of(cert: Certificate, name: str) -> tuple[int, int]:
    live = [index for index, members in enumerate(cert["live"]) if name in members]
    if not live:
        raise ValueError(f"{name}: the certificate declares no live phase for it")
    return live[0], live[-1]


def cert_start(cert: Certificate, name: str) -> int:
    return cert["phase_bounds"][_phases_of(cert, name)[0]]


def cert_live_end(cert: Certificate, name: str) -> int:
    return cert["phase_bounds"][_phases_of(cert, name)[1] + 1]


def cert_occupancy_end(cert: Certificate, name: str) -> int:
    retained = dict(cert["retained_occupancy"])
    if name in retained:
        return cert["phase_bounds"][retained[name] + 1]
    return cert_live_end(cert, name)


def reuse_bound(cert: Certificate, name: str, rule: str, root_clear: int, sweep: int) -> int:
    """The rule's earliest reuse tick, derived from one certificate and nothing else."""
    if rule == "R0":
        return cert_live_end(cert, name)
    occupancy = cert_occupancy_end(cert, name)
    if rule == "R1":
        return occupancy + cert["declared_window"]
    if rule == "R2":
        return occupancy + cert["declared_outstanding"] + root_clear + sweep
    if rule == "R2-skip-device":
        return occupancy + root_clear + sweep
    if rule == "R2-skip-pass":
        return occupancy + cert["declared_outstanding"] + root_clear
    raise ValueError(f"unknown reuse rule: {rule}")


def summarize(certs: dict[str, Certificate], mode: str) -> dict[str, Certificate]:
    """Weaken every certificate the same way, to price one naive summary."""
    if mode == "honest":
        return certs
    if mode not in SUMMARIES:
        raise ValueError(f"unknown certificate summary: {mode}")
    result: dict[str, Certificate] = {}
    for name, cert in certs.items():
        row: Certificate = {
            "component": cert["component"], "phase_bounds": cert["phase_bounds"],
            "labels": cert["labels"], "live": cert["live"],
            "retained_occupancy": () if mode == "drop-retained" else cert["retained_occupancy"],
            "retained_holders": cert["retained_holders"], "extents": cert["extents"],
            "declared_window": 0 if mode == "drop-completion-bound" else cert["declared_window"],
            "declared_outstanding": _summarized_outstanding(cert, mode),
        }
        result[name] = row
    return result


def _summarized_outstanding(cert: Certificate, mode: str) -> int:
    """A chained summary reads the component's own window as if it were absolute."""
    if mode == "drop-completion-bound":
        return 0
    if mode == "chain-local-window":
        return cert["declared_window"]
    return cert["declared_outstanding"]


def _certificate_index(certs: dict[str, Certificate]) -> dict[str, Certificate]:
    index: dict[str, Certificate] = {}
    for cert in certs.values():
        for name, _extent in cert["extents"]:
            index[name] = cert
    return index


def compositional_check(certs: dict[str, Certificate], chains: tuple[tuple[str, ...], ...],
                        rule: str, root_clear: int, sweep: int) -> dict[str, Any]:
    """Compare each adjacent chain pair, and count how much of the input that read.

    The certificates and the chains are the whole argument list, so no product of
    component states is reachable from here. What the receipt carries is therefore two
    counts, comparisons and certificates consulted, to be read beside the number of
    timings the exhaustive search enumerates for the same composition; a count moves
    when the implementation changes, where a declared property would not.
    """
    index = _certificate_index(certs)
    refusals: list[dict[str, Any]] = []
    consulted: set[str] = set()
    comparisons = 0
    for chain in chains:
        for old, new in pairwise(chain):
            comparisons += 1
            consulted.update((index[old]["component"], index[new]["component"]))
            required = reuse_bound(index[old], old, rule, root_clear, sweep)
            start = cert_start(index[new], new)
            if start < required:
                refusals.append({"old": old, "new": new, "declared_start": start,
                                 "required_reuse": required})
    return {"rule": rule, "accept": not refusals, "refusals": refusals,
            "comparisons": comparisons, "certificates_read": len(consulted)}


def object_facts(comp: Composition) -> dict[str, dict[str, Any]]:
    """True per-object timing, read from the composition rather than a certificate."""
    facts: dict[str, dict[str, Any]] = {}
    for component in comp.components:
        cert = certificate(component)
        for obj in component.objects:
            facts[obj.id] = {
                "component": component.name, "extent": obj.extent,
                "start": cert_start(cert, obj.id),
                "live_end": cert_live_end(cert, obj.id),
                "occupancy_end": cert_occupancy_end(cert, obj.id),
                "stale_holder": obj.stale_holder,
            }
    return facts


def completion_map(comp: Composition, offsets: dict[str, int]) -> dict[str, int]:
    """Resolve acceptance, chained acceptance included, then add each timing offset."""
    result: dict[str, int] = {}
    for component, transfer in _transfer_order(comp):
        accept = (component.phase_bounds[transfer.accept_phase]
                  if transfer.depends_on is None else result[transfer.depends_on])
        result[transfer.name] = accept + offsets[transfer.name]
    return result


def _transfers_by_object(comp: Composition) -> dict[str, tuple[str, ...]]:
    owners: dict[str, list[str]] = {}
    for component in comp.components:
        for transfer in component.transfers:
            owners.setdefault(transfer.object_id, []).append(transfer.name)
    return {name: tuple(sorted(names)) for name, names in owners.items()}


def _exposure(comp: Composition, rule: str, occupancy_end: int, live_end: int,
              completions: tuple[int, ...]) -> tuple[int, int]:
    """The interval in which a retained representation can still write the extent."""
    if rule == "R0":
        return live_end, comp.horizon
    if rule == "R1":
        return occupancy_end, comp.horizon
    latest = max((occupancy_end, *completions)) if rule != "R2-skip-device" else occupancy_end
    barrier = latest + comp.root_clear
    if rule == "R2-skip-pass":
        return barrier, comp.horizon
    return barrier, barrier + comp.sweep


def release_tick(comp: Composition, rule: str, occupancy_end: int, live_end: int,
                 window: int, completions: tuple[int, ...]) -> int:
    """When the rule's own service actually finishes for one object and one timing."""
    if rule == "R0":
        return live_end
    if rule == "R1":
        return occupancy_end + window
    if rule == "R2-skip-device":
        return occupancy_end + comp.root_clear + comp.sweep
    barrier = max((occupancy_end, *completions)) + comp.root_clear
    return barrier if rule == "R2-skip-pass" else barrier + comp.sweep


def simulate(comp: Composition, completions: dict[str, int], rule: str) -> dict[str, Any]:
    """Bind every successor at its declared public start and look for old authority."""
    facts = object_facts(comp)
    owned = _transfers_by_object(comp)
    windows = {component.name: component.declared_window for component in comp.components}
    hazards: list[Hazard] = []
    shortfall = 0
    for chain in comp.chains:
        holds = [(name, facts[name]["start"],
                  facts[chain[position + 1]]["start"] if position + 1 < len(chain)
                  else comp.horizon)
                 for position, name in enumerate(chain)]
        for position, name in enumerate(chain):
            if position + 1 >= len(chain):
                continue
            fact = facts[name]
            successor = chain[position + 1]
            rebound = facts[successor]["start"]
            times = tuple(completions[transfer] for transfer in owned.get(name, ()))
            release = release_tick(comp, rule, fact["occupancy_end"], fact["live_end"],
                                   windows[fact["component"]], times)
            shortfall = max(shortfall, release - rebound)
            if fact["occupancy_end"] > rebound:
                hazards.append({"kind": "occupancy-overlap", "extent": fact["extent"],
                                "old": name, "new": successor, "tick": rebound})
            for transfer in owned.get(name, ()):
                landing = completions[transfer]
                holder = _holder(holds, landing)
                if holder is not None and holder != name:
                    hazards.append({"kind": "device-completion", "extent": fact["extent"],
                                    "old": name, "new": holder, "tick": landing})
            if fact["stale_holder"]:
                first, last = _exposure(comp, rule, fact["occupancy_end"],
                                        fact["live_end"], times)
                tick = max(first, rebound)
                holder = _holder(holds, tick) if tick < min(last, comp.horizon) else None
                if holder is not None and holder != name:
                    hazards.append({"kind": "stale-representation", "extent": fact["extent"],
                                    "old": name, "new": holder, "tick": tick})
    return {"rule": rule, "safe": not hazards, "hazards": hazards,
            "gated_start_shortfall": shortfall}


def _holder(holds: list[tuple[str, int, int]], tick: int) -> str | None:
    for name, first, last in holds:
        if first <= tick < last:
            return name
    return None


def timing_space(comp: Composition, delta: int = 0) -> list[dict[str, int]]:
    """Every offset inside the declared windows, or one adversarial offset outside.

    A positive `delta` holds the other transfers at their declared worst case and
    overruns one window by exactly that much. The model assumes a certificate rather
    than proving it, so this family is what shows the cost of one that is false.
    """
    if type(delta) is not int or delta < 0:
        raise ValueError("an out-of-window delta is a nonnegative integer")
    names = [transfer.name for component in comp.components
             for transfer in component.transfers]
    windows = {transfer.name: transfer.window for component in comp.components
               for transfer in component.transfers}
    if not names:
        return [{}]
    if delta == 0:
        return [dict(zip(names, offsets, strict=True))
                for offsets in product(*(range(1, windows[name] + 1) for name in names))]
    return [{name: windows[name] + (delta if name == violated else 0) for name in names}
            for violated in names]


def exhaustive_check(comp: Composition, rule: str, delta: int = 0) -> dict[str, Any]:
    """Enumerate the product of admitted completion timings and report a witness."""
    validate(comp)
    unsafe = 0
    witness: dict[str, Any] | None = None
    shortfall = 0
    space = timing_space(comp, delta)
    for offsets in space:
        completions = completion_map(comp, offsets)
        outcome = simulate(comp, completions, rule)
        shortfall = max(shortfall, outcome["gated_start_shortfall"])
        if not outcome["safe"]:
            unsafe += 1
            if witness is None:
                witness = {"offsets": offsets, "completions": completions,
                           "hazards": outcome["hazards"]}
    return {"rule": rule, "timings": len(space), "unsafe_timings": unsafe,
            "verdict": "unsafe" if unsafe else "safe", "witness": witness,
            "max_gated_start_shortfall": shortfall,
            "out_of_window_delta": delta}


def agreement(comp: Composition, rule: str, summary: str = "honest") -> dict[str, Any]:
    """The bounded soundness comparison: an acceptance must survive every timing."""
    certs = summarize(certificates(comp), summary)
    decided = compositional_check(certs, comp.chains, rule, comp.root_clear, comp.sweep)
    observed = exhaustive_check(comp, rule)
    classification = {
        (True, "safe"): "sound-acceptance", (True, "unsafe"): "unsound-acceptance",
        (False, "unsafe"): "necessary-refusal", (False, "safe"): "conservative-refusal",
    }[(decided["accept"], observed["verdict"])]
    return {"composition": comp.name, "rule": rule, "summary": summary,
            "classification": classification, "compositional": decided,
            "exhaustive": observed}


def _component(name: str, bounds: tuple[int, ...], labels: tuple[str, ...],
               objects: tuple[Obj, ...], transfers: tuple[Transfer, ...] = (),
               window: int = 0, outstanding: int = 0) -> Component:
    return Component(name, bounds, labels, objects, transfers, window, outstanding)


def fixtures() -> tuple[Composition, ...]:
    """Small compositions, each chosen for the implication it decides."""
    capture = _component(
        "capture", (0, 4, 14), ("fill", "idle"), (Obj("a-buf", "e0", (0,)),),
        (Transfer("a-dma", "a-buf", 0, 6),), window=6, outstanding=2)
    return (
        Composition("device-crosses-public-boundary",
                    (capture, _component("init", (0, 4, 14), ("wait", "use"),
                                         (Obj("b-buf", "e0", (1,)),))),
                    (("a-buf", "b-buf"),), 14),
        Composition("late-successor-safe",
                    (capture, _component("encode", (0, 10, 16), ("wait", "use"),
                                         (Obj("b-buf", "e0", (1,)),))),
                    (("a-buf", "b-buf"),), 16),
        Composition("retained-state-after-public-end",
                    (_component("logger", (0, 3, 12), ("record", "hold"),
                                (Obj("a-log", "e0", (0,), retained_through=1),),
                                (Transfer("a-flush", "a-log", 1, 4),), window=4, outstanding=0),
                     _component("report", (0, 6, 14), ("wait", "emit"),
                                (Obj("b-out", "e0", (1,)),))),
                    (("a-log", "b-out"),), 14),
        Composition("long-window-outstanding",
                    (_component("radio", (0, 4, 14), ("receive", "idle"),
                                (Obj("a-rx", "e0", (0,)),),
                                (Transfer("a-in", "a-rx", 0, 9),), window=9, outstanding=5),
                     _component("parse", (0, 8, 14), ("wait", "decode"),
                                (Obj("b-msg", "e0", (1,)),))),
                    (("a-rx", "b-msg"),), 14),
        Composition("chained-completion-windows",
                    (_component("sensor", (0, 2, 14), ("sample", "idle"),
                                (Obj("a-raw", "e1", (0,)),),
                                (Transfer("a-dma", "a-raw", 0, 5),), window=5, outstanding=3),
                     _component("codec", (0, 2, 14), ("stage", "idle"),
                                (Obj("b-stage", "e0", (0,)),),
                                (Transfer("b-dma", "b-stage", 0, 4, depends_on="a-dma"),),
                                window=4, outstanding=7),
                     _component("sink", (0, 9, 14), ("wait", "consume"),
                                (Obj("c-out", "e0", (1,)),))),
                    (("a-raw",), ("b-stage", "c-out")), 14),
        Composition("resident-authority-after-window",
                    (_component("session", (0, 4, 14), ("serve", "idle"),
                                (Obj("a-ctx", "e0", (0,), stale_holder=True),),
                                (Transfer("a-ack", "a-ctx", 0, 2),), window=2, outstanding=0),
                     _component("successor", (0, 7, 14), ("wait", "serve"),
                                (Obj("b-ctx", "e0", (1,)),))),
                    (("a-ctx", "b-ctx"),), 14),
    )


COUNTEREXAMPLES: tuple[tuple[str, str, str], ...] = (
    ("drop-retained", "retained-state-after-public-end",
     "the summary presumes the object dead at its public live boundary"),
    ("drop-completion-bound", "long-window-outstanding",
     "the summary presumes no transfer outstanding past the occupancy end"),
    ("chain-local-window", "chained-completion-windows",
     "the summary adds a component's own window to its own boundary while its "
     "acceptance waits on another component's completion"),
)


def is_counterexample(comp: Composition, summary: str) -> bool:
    """The honest certificate refuses, the summary accepts, and a timing refutes it."""
    try:
        validate(comp)
    except ValueError:
        return False
    certs = certificates(comp)
    honest = compositional_check(certs, comp.chains, "R2", comp.root_clear, comp.sweep)
    lossy = compositional_check(summarize(certs, summary), comp.chains, "R2",
                                comp.root_clear, comp.sweep)
    if honest["accept"] or not lossy["accept"]:
        return False
    return str(exhaustive_check(comp, "R2")["verdict"]) == "unsafe"


def _describe(comp: Composition) -> dict[str, int]:
    objects = [obj for component in comp.components for obj in component.objects]
    return {"components": len(comp.components), "objects": len(objects),
            "extents": len({obj.extent for obj in objects}),
            "transfers": sum(len(component.transfers) for component in comp.components)}


def _size(comp: Composition) -> tuple[int, ...]:
    """The well-founded order the search descends, coarsest structure first."""
    objects = [obj for component in comp.components for obj in component.objects]
    transfers = [transfer for component in comp.components
                 for transfer in component.transfers]
    shape = _describe(comp)
    return (shape["components"], shape["objects"], shape["extents"], shape["transfers"],
            sum(1 for obj in objects
                if obj.retained_through is not None or obj.stale_holder),
            sum(transfer.window for transfer in transfers))


def _tighten(comp: Composition) -> Composition:
    """Give every component the tightest certificate its own transfers justify."""
    draft = replace(comp, components=tuple(
        replace(component, declared_outstanding=0,
                declared_window=max([0, *(transfer.window
                                          for transfer in component.transfers)]))
        for component in comp.components))
    bounds = true_outstanding(draft)
    return replace(draft, components=tuple(
        replace(component, declared_outstanding=bounds[component.name])
        for component in draft.components))


def _move_object(source: Component, obj: Obj, bounds: tuple[int, ...]) -> Obj | None:
    """Re-index one object onto a finer schedule; every original boundary survives it."""
    start = source.phase_bounds[obj.live_phases[0]]
    live_end = source.phase_bounds[obj.live_phases[-1] + 1]
    live = tuple(index for index in range(len(bounds) - 1)
                 if start <= bounds[index] and bounds[index + 1] <= live_end)
    if not live:
        return None
    retained: int | None = None
    if obj.retained_through is not None:
        end = source.phase_bounds[obj.retained_through + 1]
        covered = [index for index in range(len(bounds) - 1) if bounds[index + 1] <= end]
        if not covered:
            return None
        retained = max(covered)
    return replace(obj, live_phases=live, retained_through=retained)


def _merged_pair(comp: Composition, first: int, second: int) -> Composition | None:
    """Fold two components onto the union of their schedules, preserving every tick.

    The merge changes no start, no occupancy end and no acceptance tick, so the
    exhaustive verdict cannot move; what it removes is the composition boundary the
    counterexample was claimed to need.
    """
    left, right = comp.components[first], comp.components[second]
    bounds = tuple(sorted({*left.phase_bounds, *right.phase_bounds, comp.horizon}))
    objects: list[Obj] = []
    transfers: list[Transfer] = []
    for source in (left, right):
        for obj in source.objects:
            moved = _move_object(source, obj, bounds)
            if moved is None:
                return None
            objects.append(moved)
        transfers.extend(
            replace(transfer,
                    accept_phase=bounds.index(source.phase_bounds[transfer.accept_phase]))
            for transfer in source.transfers)
    merged = Component(f"{left.name}+{right.name}", bounds,
                       tuple(f"p{index}" for index in range(len(bounds) - 1)),
                       tuple(objects), tuple(transfers))
    rest = tuple(component for index, component in enumerate(comp.components)
                 if index not in (first, second))
    return replace(comp, name=f"{comp.name}/merged", components=(merged, *rest))


def _without_transfer(comp: Composition, name: str) -> Composition:
    """Drop one transfer and every transfer whose acceptance waited on it."""
    doomed = {name}
    changed = True
    while changed:
        changed = False
        for component in comp.components:
            for transfer in component.transfers:
                if transfer.depends_on in doomed and transfer.name not in doomed:
                    doomed.add(transfer.name)
                    changed = True
    return replace(comp, components=tuple(
        replace(component, transfers=tuple(transfer for transfer in component.transfers
                                           if transfer.name not in doomed))
        for component in comp.components))


def _with_transfer_window(comp: Composition, name: str, window: int) -> Composition:
    return replace(comp, components=tuple(
        replace(component, transfers=tuple(
            replace(transfer, window=window) if transfer.name == name else transfer
            for transfer in component.transfers))
        for component in comp.components))


def _without_retention(comp: Composition, target: str) -> Composition:
    return replace(comp, components=tuple(
        replace(component, objects=tuple(
            replace(obj, retained_through=None) if obj.id == target else obj
            for obj in component.objects))
        for component in comp.components))


def _without_representation(comp: Composition, target: str) -> Composition:
    return replace(comp, components=tuple(
        replace(component, objects=tuple(
            replace(obj, stale_holder=False) if obj.id == target else obj
            for obj in component.objects))
        for component in comp.components))


def _candidate_reductions(comp: Composition) -> list[tuple[str, Composition]]:
    """Every single step the declared reduction set admits, in a fixed order."""
    out: list[tuple[str, Composition]] = []
    for first in range(len(comp.components)):
        for second in range(first + 1, len(comp.components)):
            merged = _merged_pair(comp, first, second)
            if merged is not None:
                out.append(("merge-components", merged))
    named = [transfer for component in comp.components for transfer in component.transfers]
    out.extend(("drop-transfer", _without_transfer(comp, transfer.name))
               for transfer in named)
    out.extend(("shrink-window", _with_transfer_window(comp, transfer.name,
                                                       transfer.window - 1))
               for transfer in named if transfer.window > 1)
    objects = [obj for component in comp.components for obj in component.objects]
    out.extend(("drop-retention", _without_retention(comp, obj.id))
               for obj in objects if obj.retained_through is not None)
    out.extend(("drop-representation", _without_representation(comp, obj.id))
               for obj in objects if obj.stale_holder)
    return [(operator, _tighten(candidate)) for operator, candidate in out]


def reduce_counterexample(comp: Composition,
                          summary: str) -> tuple[Composition, tuple[str, ...]]:
    """Shrink a counterexample until no declared reduction applies to it.

    Each step takes the smallest candidate that is still a counterexample and still
    smaller than what it replaces, so the search terminates in the order `_size`
    defines. What it establishes is irreducibility under this reduction set, which is
    weaker than minimality among all compositions: no reduction here removes an object
    or rewrites a schedule, and nothing outside the reduction order is searched.
    """
    if not is_counterexample(comp, summary):
        raise ValueError(f"{comp.name} is not a counterexample to {summary}")
    current = comp
    applied: list[str] = []
    shrinking = True
    while shrinking:
        shrinking = False
        standing = _size(current)
        smaller = [(_size(candidate), operator, candidate)
                   for operator, candidate in _candidate_reductions(current)
                   if _size(candidate) < standing
                   and is_counterexample(candidate, summary)]
        if smaller:
            chosen = min(smaller, key=lambda row: row[0])
            current, shrinking = chosen[2], True
            applied.append(chosen[1])
    return current, tuple(applied)


def reduction_report(comp: Composition, summary: str) -> dict[str, Any]:
    """What the search reached, beside what it started from and what it may not claim."""
    reduced, applied = reduce_counterexample(comp, summary)
    return {
        "summary": summary, "source": comp.name, "declared_reductions": REDUCTIONS,
        "applied": applied, "source_size": _describe(comp),
        "reduced_size": _describe(reduced),
        "reduced_certificates": certificates(reduced),
        "reduced_exhaustive": exhaustive_check(reduced, "R2"),
        "minimality": "irreducible under the declared reductions; not proved minimal "
                      "among all compositions",
    }


def publish_covering(left: Certificate, right: Certificate) -> Certificate:
    """Join two branches' certificates into the one a service publishes for both.

    The shared public schedule is a precondition and not a result: the join refuses
    two runs whose bounds, labels or public live sets differ, because those are what
    an observer of the schedule already reads. What the join computes is the rest,
    every field taken at its upper bound, so a branch that retains more or waits
    longer is covered by the certificate the other branch also publishes.
    """
    if left["phase_bounds"] != right["phase_bounds"] or left["labels"] != right["labels"]:
        raise ValueError("a covering certificate needs one shared public schedule")
    if left["extents"] != right["extents"] or left["live"] != right["live"]:
        raise ValueError("a covering certificate needs one shared public live set")
    retained = dict(left["retained_occupancy"])
    for name, end in right["retained_occupancy"]:
        retained[name] = max(retained.get(name, end), end)
    return {
        "component": f"{left['component']}|{right['component']}",
        "phase_bounds": left["phase_bounds"], "labels": left["labels"],
        "live": left["live"],
        "retained_occupancy": tuple(sorted(retained.items())),
        "retained_holders": tuple(sorted({*left["retained_holders"],
                                          *right["retained_holders"]})),
        "extents": left["extents"],
        "declared_window": max(left["declared_window"], right["declared_window"]),
        "declared_outstanding": max(left["declared_outstanding"],
                                    right["declared_outstanding"]),
    }


def secret_phase_witness() -> dict[str, Any]:
    """Equal public labels, different selected phases, different reuse timing.

    Two of the reported booleans are guarantees of how the runs are built rather than
    outcomes: both runs carry one schedule, and padding both to one published
    certificate equalizes that bound because it is the same expression twice. The
    payload names them, so a reader is not invited to count a construction as an
    observation. What is computed and could be false is that the published
    certificate covers each branch's own bound, that the event-gated ticks differ,
    and that both padded runs survive the enumeration.
    """
    def run(name: str, obj: Obj, transfers: tuple[Transfer, ...],
            window: int, outstanding: int) -> Composition:
        return Composition(
            name, (_component("service", (0, 4, 14), ("serve", "idle"), (obj,),
                              transfers, window, outstanding),
                   _component("successor", (0, 17, 20), ("wait", "serve"),
                              (Obj("b-ctx", "e0", (1,)),))),
            (("a-ctx", "b-ctx"),), 20)

    low = run("secret-low", Obj("a-ctx", "e0", (0,)), (), 3, 0)
    high = run("secret-high", Obj("a-ctx", "e0", (0,), retained_through=1),
               (Transfer("a-dma", "a-ctx", 1, 3),), 3, 0)
    published = publish_covering(certificate(low.components[0]),
                                 certificate(high.components[0]))
    rows: list[dict[str, Any]] = []
    for comp in (low, high):
        facts = object_facts(comp)["a-ctx"]
        own = certificate(comp.components[0])
        offsets = timing_space(comp)[-1]
        times = tuple(completion_map(comp, offsets).values())
        gated = release_tick(comp, "R2", facts["occupancy_end"], facts["live_end"],
                             comp.components[0].declared_window, times)
        rows.append({
            "run": comp.name, "labels": comp.components[0].labels,
            "phase_bounds": comp.components[0].phase_bounds,
            "selected_occupancy_end": facts["occupancy_end"],
            "accepted_transfers": tuple(t.name for t in comp.components[0].transfers),
            "event_gated_reuse": gated,
            "own_reuse_bound": reuse_bound(own, "a-ctx", "R2", comp.root_clear, comp.sweep),
            "padded_reuse": reuse_bound(published, "a-ctx", "R2",
                                        comp.root_clear, comp.sweep),
            "successor_start": object_facts(comp)["b-ctx"]["start"],
            "padded_run": exhaustive_check(comp, "R2")["verdict"],
        })
    equal_labels = rows[0]["labels"] == rows[1]["labels"]
    equal_bounds = rows[0]["phase_bounds"] == rows[1]["phase_bounds"]
    return {
        "runs": rows,
        "published_certificate": published,
        "public_labels_equal": equal_labels and equal_bounds,
        "successor_binding_equal": rows[0]["successor_start"] == rows[1]["successor_start"],
        "event_gated_reuse_differs": rows[0]["event_gated_reuse"] != rows[1]["event_gated_reuse"],
        "published_covers_both_runs": all(
            row["padded_reuse"] >= max(row["own_reuse_bound"], row["event_gated_reuse"])
            for row in rows),
        "padded_reuse_equal": rows[0]["padded_reuse"] == rows[1]["padded_reuse"],
        "padded_runs_safe": all(row["padded_run"] == "safe" for row in rows),
        "construction_guards": ("public_labels_equal", "padded_reuse_equal",
                                "successor_binding_equal"),
        "computed_observations": ("event_gated_reuse_differs",
                                  "published_covers_both_runs", "padded_runs_safe"),
        "observation": "the tick at which the old authority's own reuse service finishes",
        "separation_quantity": "release_tick, which this model reports but does not "
                               "simulate as a binding: the successor binds at its "
                               "declared public start in both runs",
        "padding_cost": "the low run holds the extent to the declared bound it does not need",
        "scope": "one observation and two runs; no non-interference theorem and no "
                 "declared leakage model for any other observation",
    }


def invariants(rows: list[dict[str, Any]], adversarial: list[dict[str, Any]],
               secret: dict[str, Any]) -> list[str]:
    """Fail the experiment when its own witnesses stop deciding what they claim."""
    errors: list[str] = []
    honest = [row for row in rows if row["summary"] == "honest"]
    if any(row["classification"] == "unsound-acceptance"
           for row in honest if row["rule"] == "R2"):
        errors.append("R2 accepted a composition the enumeration refutes")
    if not any(row["classification"] == "sound-acceptance"
               for row in honest if row["rule"] == "R2"):
        errors.append("R2 refused every composition; the comparison decides nothing")
    errors.extend(f"{rule} was not refuted by any enumerated composition"
                  for rule in ("R0", "R1")
                  if not any(row["classification"] == "unsound-acceptance"
                             for row in honest if row["rule"] == rule))
    errors.extend(f"the {summary} counterexample no longer refutes R2"
                  for summary, name, _reason in COUNTEREXAMPLES
                  if not any(row["classification"] == "unsound-acceptance" for row in rows
                             if row["summary"] == summary and row["composition"] == name
                             and row["rule"] == "R2"))
    errors.extend(f"barrier mutant {mutant} was not caught" for mutant in MUTANTS
                  if not any(row["classification"] == "unsound-acceptance" for row in rows
                             if row["summary"] == "honest" and row["rule"] == mutant))
    if not any(row["verdict"] == "unsafe" for row in adversarial):
        errors.append("a violated certificate produced no hazard in any witness")
    if not (secret["public_labels_equal"] and secret["event_gated_reuse_differs"]
            and secret["padded_reuse_equal"] and secret["padded_runs_safe"]
            and secret["published_covers_both_runs"]
            and secret["successor_binding_equal"]):
        errors.append("the secret-phase witness no longer separates labels from timing")
    return errors


def _composition_row(comp: Composition) -> dict[str, Any]:
    """One composition's shape, the bounds the model rechecks, and its certificates."""
    recomputed = true_outstanding(comp)
    decided = compositional_check(certificates(comp), comp.chains, "R2",
                                  comp.root_clear, comp.sweep)
    return {
        "name": comp.name, **_describe(comp),
        "enumerated_timings": len(timing_space(comp)),
        "compositional_comparisons": decided["comparisons"],
        "certificates_read": decided["certificates_read"],
        "outstanding_bounds": {
            component.name: {"declared": component.declared_outstanding,
                             "recomputed": recomputed[component.name]}
            for component in comp.components},
        "certificates": certificates(comp),
    }


def report(source_revision: str = "unspecified") -> dict[str, Any]:
    """Replay the whole comparison deterministically; the CLI adds Git identity."""
    compositions = fixtures()
    rows: list[dict[str, Any]] = [agreement(comp, rule, summary) for comp in compositions
                                  for summary in SUMMARIES for rule in (*RULES, *MUTANTS)]
    adversarial = [dict(exhaustive_check(comp, rule, delta), composition=comp.name)
                   for comp in compositions for rule in ("R1", "R2")
                   for delta in OUT_OF_WINDOW_DELTAS]
    secret = secret_phase_witness()
    honest = [row for row in rows if row["summary"] == "honest"]
    return {
        "schema": "static-memory-phases-v1", "source_revision": source_revision,
        "scope": "finite compositions and bounded enumeration; no theorem, no barrier "
                 "implementation, no admission change",
        "model": {
            "certificate_fields": ("public phase schedule", "per-phase live set",
                                   "retained set (occupancy and representations)",
                                   "outstanding-completion bound"),
            "hazards": ("occupancy-overlap", "device-completion", "stale-representation"),
            "barrier_service": {"root_clear": compositions[0].root_clear,
                                "post_barrier_pass": compositions[0].sweep},
            "binding": "a successor binds its extent at its declared public start; this "
                       "model has no runtime gate that could delay that binding",
            "declared_bounds": "the outstanding-completion bound is recomputed from the "
                               "composition's own transfers and a declaration below the "
                               "recomputed value is refused, so an honest certificate is "
                               "checked rather than labelled",
        },
        "rules": {
            "R0": "reuse at the public phase boundary",
            "R1": "reuse after the boundary plus the component's declared maximum "
                  "completion window",
            "R2": "reuse only after the barrier: every accepted transfer completed under "
                  "the old authority, live roots cleared, and a full post-barrier pass",
            "R2-skip-device": "mutant of R2 whose barrier ignores outstanding completions",
            "R2-skip-pass": "mutant of R2 that reuses at the barrier without the pass",
        },
        "compositions": [_composition_row(comp) for comp in compositions],
        "agreements": rows,
        "honest_census": {
            cell: sum(1 for row in honest if row["classification"] == cell)
            for cell in ("sound-acceptance", "unsound-acceptance",
                         "necessary-refusal", "conservative-refusal")},
        "counterexamples": [
            {"summary": summary, "composition": name, "why": reason,
             "honest": next(row for row in honest
                            if row["composition"] == name and row["rule"] == "R2"),
             "summarized": next(row for row in rows
                                if row["summary"] == summary and row["composition"] == name
                                and row["rule"] == "R2"),
             "reduction": reduction_report(
                 next(comp for comp in compositions if comp.name == name), summary)}
            for summary, name, reason in COUNTEREXAMPLES],
        "adversarial_timings": adversarial,
        "secret_phase_selection": secret,
        "conjecture": {
            "statement": "under the premises below, per-component certificates and the "
                         "per-extent chain decide global non-overlap and bounded reuse "
                         "without enumerating component states",
            "premises": (
                "public phase schedules are composition constants shared by every component",
                "each certificate's retained set carries occupancy retention and every "
                "capability-bearing representation of the object",
                "each outstanding-completion bound is an absolute latest completion "
                "relative to the component's own public schedule and depends on no other "
                "component's events",
                "every extent carries one declared reuse chain whose successor start is a "
                "composition constant",
                "reuse follows R2, and the barrier and post-barrier pass are actually "
                "realized",
                "the modeled hazards are the only ones",
            ),
            "status": "conjecture with bounded executable evidence over this fixture only",
            "not_established": ("any statement about compositions outside this fixture",
                                "completeness: a refusal here is not proved necessary in "
                                "general", "a machine-checked proof"),
        },
        "errors": invariants(rows, adversarial, secret),
        "open_obligations": [
            "Q22a's barrier realization: an implementation of publication, root clearing, "
            "loan cancellation, proxy acknowledgement and the post-barrier pass",
            "R-15-208a's RTL-enforced device completion postcondition, which this model "
            "assumes as the meaning of a completion event",
            "a declared leakage model and observation set before any non-interference claim",
            "an admitted-language derivation of the per-phase live and retained sets",
            "a machine-checked compositional theorem, with the premises above as hypotheses",
        ],
    }
