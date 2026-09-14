# SPDX-License-Identifier: Apache-2.0
"""Producer adapters from the composed model's own sources into a record body.

[replay_record.py](replay_record.py) fixes the body, the bindings and the bounded
callback interface. Nothing there knows where a source is: a fixture hands it
bytes. This module is the other half, and its whole subject is *which access is a
draw*, answered from the model and the composition rather than from a list kept
here.

**Nothing below decides a placement, an offset or a draw site.** A window's base
and extent are the composition's
([model/config/verifiedos.json](../../model/config/verifiedos.json)); a door's
offset is the `let ROT_*` the model declares; which handler a window routes to is
`mmio_read`/`mmio_write`'s own dispatch; and whether a door reaches the entropy
root is computed over the model's call graph. So a door this repository adds, an
offset it moves and a third caller of `rot_draw` all arrive here without an edit,
and `tools/tests/test_replay_adapter.py` states what the model carries today and
fails when it changes.

**The watchdog's draw is the case this module refuses rather than intercepts.**
`rot_draw` has exactly two non-test callers: the `ROT_TRNG_DRAW` door read, whose
drawn word crosses the bus, and `watchdog_issue_nonce`, which no bus transaction
accompanies. The pet that reaches it draws only on its accepted arm and the arm
door only when the bite has not latched, and neither outcome is a record the
commit-trace dialect carries, the store retiring `Ok` either way. A host reading a
trace can therefore see that the site was *reached* and can never see whether it
drew or what it drew. The classification below says so: such a door is `internal`,
and touching one without an independently supplied account refuses the whole
capture. What would discharge it is a draw hook at `rot_draw` reaching an external
recorder, which no plan item authors today; this module is where the absence is
made to fail closed instead of being papered over.

The seal is injected and never implemented here. A `TraceProducer` with no sealing
primitive produces nothing at all, because the alternative is a host-computed hash
that would satisfy every structural check and be worth nothing.
"""

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NoReturn

from vos import jsonc
from vos.jsonc import Json
from vos.replay_record import (
    SOURCES,
    Binding,
    FixtureRecorder,
    Point,
    RecordError,
    instruction_point,
)
from vos.trace import COMMIT_RE

# The artifacts read, named once because the diagnostics below cite them.
COMPOSITION = "model/config/verifiedos.json"
PLATFORM_CONFIG = "model/model/core/platform_config.sail"
PLATFORM = "model/model/sys/platform.sail"
ROT = "model/model/sys/rot.sail"
MODEL = "model/model"
CONTRACT = "docs/implementation/replay-record-contract.md"

# The entropy root's one function. Every draw in the model passes through it, which
# is what makes a call-graph answer about it an answer about draws.
DRAW = "rot_draw"

# The three sources R-16-015 closes over that no interface in this tree produces.
# What is missing for each is the contract's source table's to say, not this file's.
ABSENT_SOURCES = ("link_address", "time_read", "physical_event")

type DoorAccess = Literal["read", "write"]
type DrawClass = Literal["none", "observed", "internal"]

# A sealing primitive: the drawn bytes in, an opaque sealed commitment out. That the
# result is sealed is the primitive's to establish and is unobservable from here.
type Seal = Callable[[bytes], bytes]

# An account of one internal draw site, from the device that can see it: the site's
# name and the local retire count in, the sealed commitment out, or None where the
# site was reached and did not draw. The host verifies neither answer.
type InternalAccount = Callable[[str, int], bytes | None]


class AdapterError(RecordError):
    """A capture is refused, or the model does not carry what this reads.

    A subclass of the record fixtures' own refusal, so a caller that already
    catches a capture refusal catches an adapter's too; the two latch the same way.
    """


# --- reading the model -----------------------------------------------------

_HEADER = re.compile(r"^(?:private\s+)?function\s+(?:clause\s+)?([A-Za-z_][A-Za-z0-9_']*)")
_TOP = re.compile(r"^(?:private\s+)?(?:function|val|let|enum|mapping|register|overload"
                  r"|type|union|struct|bitfield|scattered|default|infix|instantiation)\b")
_CALL = re.compile(r"\b([a-z_][A-Za-z0-9_']*)\s*\(")
_WITHIN = re.compile(r"\bwithin_([A-Za-z_]\w*)\s*\(")
_THEN = re.compile(r"\bthen\s+([a-z_]\w*)\s*\(")
_ROT_GUARD = re.compile(r"\bwithin_rot_window\(\s*[A-Za-z_]\w*\s*,\s*(plat_\w+_base)\s*,")
_PLAT_BASE = re.compile(r"^let\s+(plat_\w+_base)\s*:\s*physaddrbits\s*=\s*to_bits_checked\("
                        r"config\s+platform\.([A-Za-z_]\w*)\.base\s*:\s*int\)")
_CONST = re.compile(r"^let\s+(ROT_\w+)\s*:\s*int\s*=\s*(\d+)\s*$")
_OFFSET = re.compile(r"\boffset\s*==\s*(ROT_\w+)")


def _group(match: re.Match[str], index: int = 1) -> str:
    """One matched group as a string, every pattern here having no optional group."""
    found = match.group(index)
    return found if isinstance(found, str) else ""


def _strip_comments(text: str) -> str:
    """Sail source with its comments blanked and every line's position kept.

    Written as a scanner rather than as two substitutions because a `//` inside a
    string literal is not a comment, and a sweep that treated it as one could hide
    a draw site from the inventory below: the one direction this must not fail in.
    """
    out: list[str] = []
    index = 0
    size = len(text)
    in_string = False
    while index < size:
        char = text[index]
        if in_string:
            out.append(char)
            if char == "\\" and index + 1 < size:
                out.append(text[index + 1])
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
        elif char == '"':
            in_string = True
            out.append(char)
            index += 1
        elif text.startswith("//", index):
            while index < size and text[index] != "\n":
                index += 1
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            stop = size if end < 0 else end + 2
            out.append("".join("\n" if c == "\n" else " " for c in text[index:stop]))
            index = stop
        else:
            out.append(char)
            index += 1
    return "".join(out)


@dataclass(frozen=True)
class SailFunction:
    """One function definition, as the lines between its header and the next one."""

    name: str
    path: str
    line: int
    body: tuple[str, ...]

    @property
    def calls(self) -> frozenset[str]:
        return frozenset(_group(match) for line in self.body for match in _CALL.finditer(line))


@dataclass(frozen=True)
class DrawSite:
    """One call of the entropy root, and the function it sits in."""

    path: str
    line: int
    function: str


@dataclass(frozen=True)
class Door:
    """One offset of one RoT window, and what reaching it does to the root.

    `draw` is `observed` where the root is called in the handler's own body, so the
    drawn word is the value the access returns and a trace carries it; `internal`
    where the root is reached through a call, so no transaction carries the draw and
    a host cannot tell whether it happened; `none` where the arm does not reach it.
    """

    window: str
    name: str
    offset: int
    access: DoorAccess
    draw: DrawClass


@dataclass(frozen=True)
class Window:
    """One composed RoT MMIO window, with the handlers the dispatch routes to."""

    key: str
    base: int
    size: int
    load: str | None
    store: str | None
    doors: tuple[Door, ...]


def _text(root: Path, rel: str) -> str:
    path = root / rel
    if not path.is_file():
        raise AdapterError(f"{rel} is not in this checkout, so no source can be adapted")
    return _strip_comments(path.read_text(encoding="utf-8"))


def _functions(path: str, text: str) -> list[SailFunction]:
    """Every function in one comment-stripped file, keyed by its header line."""
    found: list[SailFunction] = []
    name: str | None = None
    start = 0
    body: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        header = _HEADER.match(line)
        if name is not None and (header or _TOP.match(line)):
            found.append(SailFunction(name, path, start, tuple(body)))
            name = None
            body = []
        if header:
            name, start, body = _group(header), number, [line]
        elif name is not None:
            body.append(line)
    if name is not None:
        found.append(SailFunction(name, path, start, tuple(body)))
    return found


def _sail_files(root: Path) -> list[str]:
    """Every model source outside the unit tests, in a stable order.

    The unit tests are excluded because they call the root directly to check its
    refusals: they are not a consumer the record has to account for, and counting
    them would make the inventory disagree with the machine.
    """
    base = root / MODEL
    if not base.is_dir():
        raise AdapterError(f"{MODEL} is not in this checkout")
    return sorted(path.relative_to(root).as_posix() for path in base.rglob("*.sail")
                  if "unit_tests" not in path.parts)


def _index(root: Path) -> dict[str, SailFunction]:
    """Every non-test model function, one entry per name.

    A name defined more than once (a scattered clause set) merges its bodies, which
    is what the reachability question below wants: a clause that calls the root is
    a call site of the root whichever clause it is.
    """
    merged: dict[str, SailFunction] = {}
    for rel in _sail_files(root):
        for fn in _functions(rel, _text(root, rel)):
            seen = merged.get(fn.name)
            merged[fn.name] = (fn if seen is None
                               else SailFunction(fn.name, seen.path, seen.line,
                                                 seen.body + fn.body))
    return merged


def _reaching(index: Mapping[str, SailFunction], target: str) -> frozenset[str]:
    """Every function whose calls reach `target`, transitively, plus `target`."""
    callers: dict[str, set[str]] = {}
    for name, fn in index.items():
        for called in fn.calls:
            callers.setdefault(called, set()).add(name)
    seen = {target}
    queue = [target]
    while queue:
        for caller in callers.get(queue.pop(), ()):
            if caller not in seen:
                seen.add(caller)
                queue.append(caller)
    return frozenset(seen)


def draw_sites(root: Path) -> tuple[DrawSite, ...]:
    """Every non-test call of the entropy root in the model, with its caller.

    This is the inventory the S6 cell's *the model's internal watchdog draw must be
    intercepted beside MMIO draws* is answered against. A site whose caller is not
    an MMIO handler is a draw no bus transaction accompanies.
    """
    found: list[DrawSite] = []
    call = re.compile(rf"\b{DRAW}\s*\(")
    for rel in _sail_files(root):
        text = _text(root, rel)
        functions = _functions(rel, text)
        for number, line in enumerate(text.splitlines(), start=1):
            if call.search(line) is None:
                continue
            enclosing = [fn for fn in functions
                         if fn.line <= number < fn.line + len(fn.body)]
            name = enclosing[-1].name if enclosing else "(top level)"
            if name != DRAW:
                found.append(DrawSite(rel, number, name))
    return tuple(found)


def _dispatch(fn: SailFunction) -> dict[str, str]:
    """One MMIO dispatch body as guard name to handler name."""
    routes: dict[str, str] = {}
    pending: str | None = None
    for line in fn.body:
        guard = _WITHIN.search(line)
        if guard:
            pending = _group(guard)
        handler = _THEN.search(line)
        if handler and pending is not None:
            routes[pending] = _group(handler)
            pending = None
    return routes


def _doors(window: str, access: DoorAccess, fn: SailFunction | None,
           reaching: frozenset[str], constants: Mapping[str, int]) -> list[Door]:
    """One handler's offset arms, each classified against the entropy root."""
    if fn is None:
        return []
    order: list[str] = []
    draws: dict[str, DrawClass] = {}
    current: str | None = None
    for line in fn.body:
        for match in _OFFSET.finditer(line):
            current = _group(match)
            if current not in draws:
                draws[current] = "none"
                order.append(current)
        if current is None:
            continue
        for match in _CALL.finditer(line):
            name = _group(match)
            if name == DRAW:
                draws[current] = "observed" if access == "read" else "internal"
            elif name in reaching and name != fn.name and draws[current] == "none":
                draws[current] = "internal"
    missing = sorted(name for name in order if name not in constants)
    if missing:
        raise AdapterError(f"{ROT} declares no literal offset for {', '.join(missing)}, "
                           f"so {window}'s door addresses cannot be derived")
    return [Door(window, name, constants[name], access, draws[name]) for name in order]


def _aperture(loaded: Json, key: str) -> tuple[int, int]:
    """One supported window's base and extent, from the composition alone."""
    platform = loaded.get("platform") if isinstance(loaded, dict) else None
    node = platform.get(key) if isinstance(platform, dict) else None
    if not isinstance(node, dict) or node.get("supported") is not True:
        raise AdapterError(f"{COMPOSITION} declares no supported platform.{key}")
    base, size = node.get("base"), node.get("size")
    if isinstance(base, bool) or not isinstance(base, int):
        raise AdapterError(f"{COMPOSITION}'s platform.{key}.base is not an address")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise AdapterError(f"{COMPOSITION}'s platform.{key}.size is not an extent")
    return base, size


def rot_windows(root: Path) -> tuple[Window, ...]:
    """The RoT's composed windows, their doors, and each door's relation to the root.

    Followed rather than asserted: the dispatch names a guard, the guard names the
    configuration symbol, the symbol names the composition key, and the key carries
    the base. A window whose handler reaches the root with no offset arm to attribute
    the draw to is refused here rather than adapted, because a door that draws and is
    not in this table is exactly the unaccounted draw the record exists to prevent.

    The table names the arms an `offset ==` comparison guards, so a handler that
    indexes a bank instead (the fuse words, the counter file) contributes no row and
    an access to one produces no event. That is right rather than tolerated: the
    refusal above is what establishes no such arm draws.
    """
    index = _index(root)
    reaching = _reaching(index, DRAW)
    symbols = {_group(match): _group(match, 2)
               for line in _text(root, PLATFORM_CONFIG).splitlines()
               if (match := _PLAT_BASE.match(line))}
    guards = {name[len("within_"):]: _group(match)
              for name, fn in index.items() if name.startswith("within_")
              and (match := _ROT_GUARD.search("\n".join(fn.body)))}
    constants = {_group(match): int(_group(match, 2))
                 for line in _text(root, ROT).splitlines()
                 if (match := _CONST.match(line))}
    reads = _dispatch(index["mmio_read"]) if "mmio_read" in index else {}
    writes = _dispatch(index["mmio_write"]) if "mmio_write" in index else {}
    if not guards or not reads or not writes:
        raise AdapterError(f"{PLATFORM} carries no RoT window dispatch to read")

    found: list[Window] = []
    loaded = jsonc.load(root / COMPOSITION)
    for guard, symbol in sorted(guards.items()):
        key = symbols.get(symbol)
        if key is None:
            raise AdapterError(f"{PLATFORM_CONFIG} binds no composition key to {symbol}")
        base, size = _aperture(loaded, key)
        load, store = reads.get(guard), writes.get(guard)
        doors = (_doors(key, "read", index.get(load or ""), reaching, constants)
                 + _doors(key, "write", index.get(store or ""), reaching, constants))
        for handler, arms in ((load, "read"), (store, "write")):
            if handler in reaching and not any(door.access == arms and door.draw != "none"
                                               for door in doors):
                raise AdapterError(f"{handler} reaches {DRAW} and no offset arm accounts "
                                   f"for it, so {key}'s draws cannot be attributed")
        found.append(Window(key, base, size, load, store, tuple(doors)))
    return tuple(sorted(found, key=lambda window: window.base))


# --- producing into a record -----------------------------------------------


def require_producer(source: str) -> None:
    """Refuse a source this tree has no interface to produce from.

    The point is that an absent production ABI cannot be papered over by a fixture:
    a synthesized address, time reply or sentinel event would satisfy every
    structural check in the reader and mean nothing.
    """
    if source not in SOURCES:
        raise AdapterError(f"'{source}' is not one of R-16-015's four closed sources")
    if source in ABSENT_SOURCES:
        raise AdapterError(f"'{source}' has no production interface to adapt; "
                           f"{CONTRACT}'s source table names what is missing")


class TraceProducer:
    """One commit trace's RoT accesses, produced into a bounded record.

    The trace is the input dialect S6's cell asks to be reused and is not a replay
    artifact: it supplies the local retired-instruction anchor and the addresses, and
    nothing else about it enters the body. `slot` is the caller's declared schedule
    slot, an assertion this tree cannot derive because R-11-017's composed operating
    point, TDM schedule and watchdog windows are one artifact that does not exist yet.

    Refusals latch. A refused capture returns no body, not even the prefix that had
    already been admitted, and the underlying recorder is poisoned through its own
    callback path rather than by a second latch kept here.
    """

    def __init__(self, recorder: FixtureRecorder, *, windows: Iterable[Window],
                 entropy_interface: str, slot: int, core: int,
                 seal: Seal | None = None,
                 internal_account: InternalAccount | None = None) -> None:
        if seal is None:
            raise AdapterError("a sealing primitive must be injected before any draw is "
                               "produced: M3.4 owes the real one, and a host-computed "
                               "hash would satisfy every check here and seal nothing")
        self._recorder = recorder
        self._entropy = entropy_interface
        self._slot = slot
        self._core = core
        self._seal = seal
        self._account = internal_account
        self._doors: dict[tuple[int, DoorAccess], Door] = {}
        for window in windows:
            for door in window.doors:
                where = (window.base + door.offset, door.access)
                if where in self._doors:
                    raise AdapterError(f"{window.key}.{door.name} shares an address and "
                                       "access with another door, so a trace record "
                                       "would name two of them")
                self._doors[where] = door
        self._line: str | None = None
        self._order = 0
        self._ordinal = 0
        self._failed = False
        self._finished = False

    def _ready(self) -> None:
        if self._failed or self._finished:
            raise AdapterError("capture is refused or already finished")

    def _point(self) -> Point:
        if self._line is None:
            return Point(self._slot, self._core, 0, self._ordinal)
        return instruction_point(self._line, slot=self._slot, core=self._core,
                                 ordinal=self._ordinal)

    def _retired(self, line: str) -> None:
        order = int(line.split()[1])
        if order < self._order:
            raise AdapterError("the trace's local retire count regresses, which needs a "
                               "new capture origin rather than a continued record")
        self._line = line
        self._order = order
        self._ordinal = 0

    def _observed(self, door: Door, value: str) -> None:
        """A draw whose word crossed the bus: sealed here, never carried."""
        if len(value) % 2:
            raise AdapterError(f"{door.window}.{door.name} returned an odd-width value")
        drawn = bytes.fromhex(value)
        seal = self._seal
        event = self._recorder.record(point=self._point(), interface=self._entropy,
                                      produce=lambda: seal(drawn))
        if event is None:
            raise AdapterError(f"{door.window}.{door.name} delivered a word, so declining "
                               "it would leave a consumed draw unaccounted for")
        self._ordinal += 1

    def _internal(self, door: Door) -> None:
        """A draw site reached with no transaction carrying it.

        Whether the site drew is the device's statement: `watchdog_pet` draws only on
        its accepted arm and `watchdog_arm` only where the bite has not latched, and
        the store retires `Ok` either way. So an account may decline, which is the
        recorder's own no-value promise, and its absence refuses the whole capture.
        """
        site = f"{door.window}.{door.name}"
        account = self._account
        if account is None:
            self._refuse_internal(site)
        order = self._order
        if self._recorder.record(point=self._point(), interface=self._entropy,
                                 produce=lambda: account(site, order)) is not None:
            self._ordinal += 1

    def _refuse_internal(self, site: str) -> NoReturn:
        message = (f"{site} reaches the model's internal entropy draw and no bus "
                   f"transaction carries it, so this capture is refused whole; "
                   f"an account of it is owed by a draw hook at {DRAW} reaching an "
                   f"external recorder, which nothing in this tree implements")

        def refuse() -> bytes:
            raise AdapterError(message)

        try:
            self._recorder.record(point=self._point(), interface=self._entropy,
                                  produce=refuse)
        except RecordError as exc:
            raise AdapterError(message) from exc
        raise AdapterError(message)

    def _access(self, kind: str, line: str) -> None:
        fields = line.split()
        access: DoorAccess = "read" if kind == "R" else "write"
        door = self._doors.get((int(fields[1], 16), access))
        if door is None or door.draw == "none":
            return
        if door.draw == "observed":
            self._observed(door, fields[4])
        else:
            self._internal(door)

    def feed(self, lines: Iterable[str]) -> None:
        """Walk one trace, producing an event at each draw the model would make.

        Anything that is not a record is dropped for the reason `normalize_commit`
        drops it: the emulator prints its own diagnostics on the same stream. Neither
        that normalizer nor the corpus digest is used, both deliberately discarding
        what this needs.
        """
        self._ready()
        try:
            for raw in lines:
                line = raw.rstrip("\n").rstrip()
                if COMMIT_RE.match(line) is None:
                    continue
                if line[0] == "I":
                    self._retired(line)
                elif line[0] in ("R", "W"):
                    self._access(line[0], line)
        except BaseException:
            self._failed = True
            raise

    def finish(self, *, expected: Binding, expected_events: int) -> bytes:
        """Close the capture against the independently supplied binding and count."""
        self._ready()
        try:
            blob = self._recorder.finish(expected=expected, expected_events=expected_events)
        except BaseException:
            self._failed = True
            raise
        self._finished = True
        return blob
