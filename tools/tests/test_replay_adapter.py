# SPDX-License-Identifier: Apache-2.0
"""Producer adapters over the composed model, and the draws they refuse.

The trace text below is written here rather than emitted by a run: these cases
exercise the adapter's own decisions against the model's real windows, doors and
call graph, and none of them is evidence that a machine was recorded. Real
recording against a running model is named as owed in the record contract.
"""

from collections.abc import Callable, Iterator
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import cast

from tests.harness import Case, ensure
from vos.corpus import find_root
from vos.replay_adapter import (
    AdapterError,
    InternalAccount,
    RootProducer,
    Seal,
    TraceProducer,
    Window,
    draw_sites,
    require_producer,
    rot_windows,
)
from vos.replay_record import Binding, FixtureRecorder, Interface, Limits, Point, RecordError

# The model's two non-test callers of the entropy root, and the class each puts its
# draw in. The MMIO caller's drawn word is the value the access returns; the
# watchdog's is a nonce no transaction carries, which is why the second column is
# not a property a host can measure.
_SITES = {
    "trng_load": "model/model/sys/platform.sail",
    "watchdog_issue_nonce": "model/model/sys/rot.sail",
}

# What the composed die's RoT windows carry today, stated so that a door added, an
# offset moved or a third draw site introduced fails here rather than silently
# changing what a record accounts for.
_WINDOWS = ("otp", "trng", "monotonic_counters", "watchdog")
_OBSERVED = {("trng", "ROT_TRNG_DRAW")}
_INTERNAL = {("watchdog", "ROT_WDT_PET"), ("watchdog", "ROT_WDT_ARM")}

_ENTROPY = "e" * 64
_BINDING = Binding("00ff", "a" * 64, "b" * 64)
_LIMITS = Limits(4096, 8)
_INTERFACES = {_ENTROPY: Interface("entropy", 32)}
_DRAWN = "DEADBEEFCAFEF00D"


def _root() -> Path:
    return find_root()


def _windows() -> tuple[Window, ...]:
    return rot_windows(_root())


def _door(windows: tuple[Window, ...], key: str, name: str) -> int:
    """One door's absolute address, as the composition and the model place it."""
    for window in windows:
        for door in window.doors:
            if (window.key, door.name) == (key, name):
                return window.base + door.offset
    raise AssertionError(f"the model carries no {key}.{name} door")


def _seal(drawn: bytes, *, seen: list[bytes]) -> bytes:
    # A stand-in for the injection point and never for the primitive: it records
    # what it was handed and returns bytes that are not the draw. Nothing here
    # seals, and no case below reads this result as evidence that anything did.
    seen.append(drawn)
    return b"\x5a" + bytes(len(drawn).to_bytes(1, "big"))


def _recorder() -> FixtureRecorder:
    return FixtureRecorder(_BINDING, limits=_LIMITS, interfaces=_INTERFACES, validators={})


def _producer(recorder: FixtureRecorder, *, seal: Seal | None = None,
              account: InternalAccount | None = None) -> TraceProducer:
    return TraceProducer(recorder, windows=_windows(), entropy_interface=_ENTROPY,
                         slot=7, core=0,
                         seal=seal if seal is not None else partial(_seal, seen=[]),
                         internal_account=account)


def _producer_on(recorder: FixtureRecorder, interface: str) -> TraceProducer:
    """A sealed producer aimed at one endpoint identity, whose class it may not pick."""
    return TraceProducer(recorder, windows=_windows(), entropy_interface=interface,
                         slot=0, core=0, seal=partial(_seal, seen=[]))


def _refused(fn: Callable[[], object]) -> None:
    """A refusal the adapter itself decided."""
    try:
        fn()
    except AdapterError:
        return
    raise AssertionError("adapter refusal was not raised")


def _latched(fn: Callable[[], object]) -> None:
    """A refusal either layer may decide: the recorder owns payload and capacity."""
    try:
        fn()
    except RecordError:
        return
    raise AssertionError("capture refusal was not raised")


def _retire(order: int, pc: int = 0x80000000) -> str:
    return f"I {order} {pc:016X} 00000013"


def _access(kind: str, address: int, value: str = _DRAWN) -> str:
    return f"{kind} {address:016X} 8 0 {value}"


def _model_carries_exactly_two_draw_sites() -> None:
    sites = draw_sites(_root())
    ensure({site.function: site.path for site in sites} == _SITES,
           "the entropy root's non-test callers must be exactly the inventoried pair")
    ensure(len(sites) == len(_SITES), "a repeated call site is a draw the inventory owes")
    handlers = {window.load for window in _windows()} | {window.store for window in _windows()}
    ensure("watchdog_issue_nonce" not in handlers,
           "the watchdog's draw must stay off every MMIO handler, which is why it is "
           "unobservable from a trace and refused rather than intercepted")


def _composed_doors_classify_every_draw() -> None:
    windows = _windows()
    ensure(tuple(window.key for window in sorted(windows, key=lambda w: w.base)) == _WINDOWS,
           "the RoT's composed windows must be followed from the dispatch, not listed")
    observed = {(window.key, door.name) for window in windows for door in window.doors
                if door.draw == "observed"}
    internal = {(window.key, door.name) for window in windows for door in window.doors
                if door.draw == "internal"}
    ensure(observed == _OBSERVED, "exactly one door's draw crosses the bus")
    ensure(internal == _INTERNAL, "exactly the watchdog's two writes reach the root blind")
    ensure(all(door.access == "read" for window in windows for door in window.doors
               if door.draw == "observed"), "an observed draw is a read that returns it")
    ensure(all(door.access == "write" for window in windows for door in window.doors
               if door.draw == "internal"), "an internal draw is reached by a write")


def _observed_draw_is_sealed_and_never_carried() -> None:
    seen: list[bytes] = []
    recorder = _recorder()
    producer = _producer(recorder, seal=partial(_seal, seen=seen))
    draw = _door(_windows(), "trng", "ROT_TRNG_DRAW")
    producer.feed([_retire(3), _access("R", draw), _retire(4), _access("R", draw)])
    blob = producer.finish(expected=_BINDING, expected_events=2)
    ensure(seen == [bytes.fromhex(_DRAWN)] * 2, "the seal must receive the actual drawn bytes")
    ensure(_DRAWN.lower().encode() not in blob and _DRAWN.encode() not in blob,
           "the drawn word must not reach the body in either case")
    ensure(blob.count(b'"sealed_commitment"') == 2 and b'"value"' not in blob,
           "each observed draw is one opaque commitment and no public payload")
    ensure(b'"retire":3' in blob and b'"retire":4' in blob and b'"slot":7' in blob,
           "the trace supplies the retire anchor and the caller supplies the slot")


def _root_callbacks_seal_without_a_bus_transaction() -> None:
    seen: list[bytes] = []
    producer = RootProducer(_recorder(), entropy_interface=_ENTROPY,
                            seal=partial(_seal, seen=seen))
    producer.observe(point=Point(7, 0, 0, 0), available=True, value=bytes.fromhex(_DRAWN))
    producer.observe(point=Point(7, 0, 0, 1), available=False, value=bytes(8))
    producer.observe(point=Point(7, 0, 0, 1), available=True, value=bytes(8))
    blob = producer.finish(expected=_BINDING, expected_events=2)
    ensure(seen == [bytes.fromhex(_DRAWN), bytes(8)],
           "only actual draws reach sealing, including a successful all-zero word")
    ensure(blob.count(b'"sealed_commitment"') == 2 and _DRAWN.lower().encode() not in blob,
           "an internal draw reaches the bounded body without exposing the word")
    ensure(b'"retire":0' in blob and b'"ordinal":1' in blob,
           "pre-retirement draws have independent invocation order")


def _root_refusals_poison_the_whole_capture() -> None:
    for available, value in ((False, b"\x01" * 8), (True, b"short")):
        recorder = _recorder()
        producer = RootProducer(recorder, entropy_interface=_ENTROPY, seal=partial(_seal, seen=[]))
        _latched(partial(producer.observe, point=Point(0, 0, 0, 0),
                         available=available, value=value))
        _latched(partial(recorder.finish, expected=_BINDING, expected_events=0))
        _refused(partial(producer.finish, expected=_BINDING, expected_events=0))


def _root_capture_respects_capacity_and_order() -> None:
    recorder = FixtureRecorder(_BINDING, limits=Limits(4096, 1),
                               interfaces=_INTERFACES, validators={})
    seen: list[bytes] = []
    producer = RootProducer(recorder, entropy_interface=_ENTROPY, seal=partial(_seal, seen=seen))
    producer.observe(point=Point(0, 0, 0, 0), available=True, value=bytes(8))
    _latched(partial(producer.observe, point=Point(0, 0, 0, 1), available=True, value=bytes(8)))
    ensure(len(seen) == 1, "capacity refuses before a further secret is sealed")
    _latched(partial(producer.finish, expected=_BINDING, expected_events=1))
    producer = RootProducer(_recorder(), entropy_interface=_ENTROPY, seal=partial(_seal, seen=[]))
    producer.observe(point=Point(0, 0, 2, 0), available=True, value=bytes(8))
    _latched(partial(producer.observe, point=Point(0, 0, 1, 0), available=True, value=bytes(8)))


def _root_seal_failure_never_returns_a_prefix() -> None:
    def fail(_drawn: bytes) -> bytes:
        raise RuntimeError("sealing unavailable")

    recorder = _recorder()
    producer = RootProducer(recorder, entropy_interface=_ENTROPY, seal=fail)
    try:
        producer.observe(point=Point(0, 0, 0, 0), available=True, value=bytes(8))
    except RuntimeError:
        pass
    else:
        raise AssertionError("the synchronous seal exception must reach the harness")
    _latched(partial(recorder.finish, expected=_BINDING, expected_events=0))
    _refused(partial(RootProducer, _recorder(), entropy_interface=_ENTROPY))


def _no_sealing_primitive_produces_nothing() -> None:
    _refused(partial(TraceProducer, _recorder(), windows=_windows(),
                     entropy_interface=_ENTROPY, slot=0, core=0))


def _a_caller_cannot_choose_the_class_of_a_draw() -> None:
    # The recorder takes an event's class from its endpoint, so naming a public one
    # would put sealed bytes in a `value` payload with the public validator's
    # blessing. The class is the source's; the producer refuses to be handed it.
    public = "f" * 64
    recorder = FixtureRecorder(_BINDING, limits=_LIMITS,
                               interfaces={public: Interface("link_address", 32)},
                               validators={public: lambda _payload: True})
    _refused(partial(_producer_on, recorder, public))
    _refused(partial(_producer_on, _recorder(), "0" * 64))


def _a_width_the_arm_refuses_is_not_that_doors_access() -> None:
    windows = _windows()
    ensure(all(door.width == 8 for window in windows for door in window.doors),
           "every composed RoT door carries the doubleword guard its own arm states")
    draw = _door(windows, "trng", "ROT_TRNG_DRAW")
    producer = _producer(_recorder())
    producer.feed([_retire(1), f"R {draw:016X} 4 0 DEADBEEF"])
    blob = producer.finish(expected=_BINDING, expected_events=0)
    ensure(b'"events":[]' in blob,
           "an access the door's arm does not admit reached the fault arm and drew nothing")


def _watchdog_write_refuses_the_whole_capture() -> None:
    windows = _windows()
    draw = _door(windows, "trng", "ROT_TRNG_DRAW")
    for name in ("ROT_WDT_PET", "ROT_WDT_ARM"):
        recorder = _recorder()
        producer = _producer(recorder)
        producer.feed([_retire(1), _access("R", draw)])
        _refused(partial(producer.feed,
                         [_retire(2), _access("W", _door(windows, "watchdog", name), "01")]))
        _refused(partial(producer.finish, expected=_BINDING, expected_events=1))
        _latched(partial(recorder.finish, expected=_BINDING, expected_events=1))


def _internal_account_is_the_devices_statement() -> None:
    windows = _windows()
    pet = _door(windows, "watchdog", "ROT_WDT_PET")
    asked: list[tuple[str, int]] = []

    def account(site: str, order: int) -> bytes | None:
        # Supplied independently, exactly as the binding and the count are, and
        # unverifiable here for the same reason. Declining is the recorder's own
        # no-value promise: a pet outside the window issues no challenge.
        asked.append((site, order))
        return b"\x01\x02" if order == 5 else None

    producer = _producer(_recorder(), account=account)
    producer.feed([_retire(5), _access("W", pet, "01"), _retire(6), _access("W", pet, "01")])
    blob = producer.finish(expected=_BINDING, expected_events=1)
    ensure(asked == [("watchdog.ROT_WDT_PET", 5), ("watchdog.ROT_WDT_PET", 6)],
           "every reached internal site must be put to the account")
    ensure(blob.count(b'"sealed_commitment"') == 1 and b'"retire":5' in blob,
           "an accounted draw is recorded and a declined one owes no event")


def _deterministic_rot_traffic_adds_no_event() -> None:
    windows = _windows()
    lines = [_retire(1)]
    for window in windows:
        for door in window.doors:
            if door.draw == "none":
                kind = "R" if door.access == "read" else "W"
                lines.append(_access(kind, window.base + door.offset, "00"))
    ensure(len(lines) > 10, "the deterministic doors must actually be exercised")
    producer = _producer(_recorder())
    producer.feed([*lines, _access("R", windows[0].base + 4096), "entry 0x80000000", "W x"])
    blob = producer.finish(expected=_BINDING, expected_events=0)
    ensure(b'"events":[]' in blob,
           "RoT traffic that does not draw, an unclaimed address and non-records add none")


def _absent_production_interfaces_refuse() -> None:
    require_producer("entropy")
    for source in ("link_address", "time_read", "physical_event", "watchdog", ""):
        _refused(partial(require_producer, source))


def _ordinals_advance_and_a_reset_refuses() -> None:
    draw = _door(_windows(), "trng", "ROT_TRNG_DRAW")
    producer = _producer(_recorder())
    producer.feed([_retire(9), _access("R", draw), _access("R", draw)])
    blob = producer.finish(expected=_BINDING, expected_events=2)
    ensure(b'"ordinal":0' in blob and b'"ordinal":1' in blob,
           "two draws under one retire are ordered by the ordinal")
    recorder = _recorder()
    producer = _producer(recorder)
    producer.feed([_retire(9), _access("R", draw)])
    _refused(partial(producer.feed, [_retire(2), _access("R", draw)]))
    _refused(partial(producer.finish, expected=_BINDING, expected_events=1))
    _latched(partial(recorder.finish, expected=_BINDING, expected_events=1))


def _declined_observed_seal_poisoning_reaches_the_recorder() -> None:
    draw = _door(_windows(), "trng", "ROT_TRNG_DRAW")
    recorder = _recorder()
    # A bad injected primitive must not turn a delivered draw into the recorder's
    # no-value outcome, even when its caller bypasses the producer to finalize.
    producer = _producer(recorder, seal=cast(Seal, lambda _drawn: None))
    _refused(partial(producer.feed, [_retire(1), _access("R", draw)]))
    _latched(partial(recorder.finish, expected=_BINDING, expected_events=0))


def _interrupted_trace_never_finalizes_its_prefix() -> None:
    draw = _door(_windows(), "trng", "ROT_TRNG_DRAW")
    recorder = _recorder()
    producer = _producer(recorder)
    interrupted = KeyboardInterrupt("capture input interrupted")

    def lines() -> Iterator[str]:
        yield _retire(1)
        yield _access("R", draw)
        raise interrupted

    try:
        producer.feed(lines())
    except KeyboardInterrupt as exc:
        ensure(exc is interrupted, "adapter must preserve the original cancellation")
    else:
        raise AssertionError("trace interruption must propagate")
    _refused(partial(producer.feed, []))
    _refused(partial(producer.finish, expected=_BINDING, expected_events=1))
    _latched(partial(recorder.finish, expected=_BINDING, expected_events=1))


def _capacity_and_seal_failures_latch() -> None:
    draw = _door(_windows(), "trng", "ROT_TRNG_DRAW")
    producer = _producer(_recorder(), seal=lambda _drawn: b"")
    _latched(partial(producer.feed, [_retire(1), _access("R", draw)]))
    _refused(partial(producer.finish, expected=_BINDING, expected_events=0))
    recorder = FixtureRecorder(_BINDING, limits=replace(_LIMITS, max_events=1),
                               interfaces=_INTERFACES, validators={})
    producer = _producer(recorder)
    _latched(partial(producer.feed, [_retire(1), _access("R", draw), _access("R", draw)]))
    _refused(partial(producer.finish, expected=_BINDING, expected_events=1))


def cases() -> list[Case]:
    return [Case(fn.__name__.lstrip("_"), fn) for fn in (
        _model_carries_exactly_two_draw_sites,
        _composed_doors_classify_every_draw,
        _observed_draw_is_sealed_and_never_carried,
        _no_sealing_primitive_produces_nothing,
        _a_caller_cannot_choose_the_class_of_a_draw,
        _a_width_the_arm_refuses_is_not_that_doors_access,
        _watchdog_write_refuses_the_whole_capture,
        _root_callbacks_seal_without_a_bus_transaction,
        _root_refusals_poison_the_whole_capture,
        _root_capture_respects_capacity_and_order,
        _root_seal_failure_never_returns_a_prefix,
        _internal_account_is_the_devices_statement,
        _deterministic_rot_traffic_adds_no_event,
        _absent_production_interfaces_refuse,
        _ordinals_advance_and_a_reset_refuses,
        _declined_observed_seal_poisoning_reaches_the_recorder,
        _interrupted_trace_never_finalizes_its_prefix,
        _capacity_and_seal_failures_latch,
    )]
