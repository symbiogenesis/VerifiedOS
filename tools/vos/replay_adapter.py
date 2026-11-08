# SPDX-License-Identifier: Apache-2.0
"""Producer adapters from the composed model's RoT sources into a replay record body.

Derives RoT MMIO window placements, door offsets, access widths, and `rot_draw`
reachability directly from [verifiedos.json](../../model/config/verifiedos.json) and the
Sail model sources (`platform_config.sail`, `platform.sail`, `rot.sail`), and feeds
entropy draw events into [replay_record.py](replay_record.py)'s `FixtureRecorder` via
`RootProducer` (synchronous root callback) or `TraceProducer` (commit-trace bus draws
plus an optional `InternalAccount` for internal watchdog draws).
"""

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Never

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

COMPOSITION = "model/config/verifiedos.json"
PLATFORM_CONFIG = "model/model/core/platform_config.sail"
PLATFORM = "model/model/sys/platform.sail"
ROT = "model/model/sys/rot.sail"
MODEL = "model/model"
CONTRACT = "docs/implementation/contracts/replay-record.md"

# The model's single entropy-root draw function.
DRAW = "rot_draw"

# R-16-015 sources that have no production adapter in this tree.
ABSENT_SOURCES = ("link_address", "time_read", "physical_event")

type DoorAccess = Literal["read", "write"]
type DrawClass = Literal["none", "observed", "internal"]

# Sealing primitive mapping drawn bytes to an opaque sealed commitment.
type Seal = Callable[[bytes], bytes]

# Callback returning a sealed commitment (or `None` if no draw occurred) for `(site, retire_order)`.
type InternalAccount = Callable[[str, int], bytes | None]


class AdapterError(RecordError):
    """Raised when a capture is refused or the model lacks expected RoT dispatch structure."""


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
_WIDTH = re.compile(r"'n\s*==\s*(\d+)")


def _group(match: re.Match[str], index: int = 1) -> str:
    """Return matched group `index` as a `str`."""
    found = match.group(index)
    return found if isinstance(found, str) else ""


def _strip_comments(text: str) -> str:
    """Blank Sail `//` and `/* ... */` comments outside string literals while preserving line numbers."""
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
    """A Sail function definition and its body lines."""

    name: str
    path: str
    line: int
    body: tuple[str, ...]

    @property
    def calls(self) -> frozenset[str]:
        return frozenset(_group(match) for line in self.body for match in _CALL.finditer(line))


@dataclass(frozen=True)
class DrawSite:
    """A call site of `rot_draw` in the Sail model."""

    path: str
    line: int
    function: str


@dataclass(frozen=True)
class Door:
    """An MMIO offset arm inside a RoT window and its entropy-draw classification (`none`, `observed`, `internal`)."""

    window: str
    name: str
    offset: int
    access: DoorAccess
    draw: DrawClass
    width: int | None


@dataclass(frozen=True)
class Window:
    """A composed RoT MMIO window, its read/write handlers, and its classified doors."""

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
    """Extract `SailFunction` definitions from comment-stripped Sail `text`."""
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
    """Return sorted relative paths of non-test `.sail` files under `model/model`."""
    base = root / MODEL
    if not base.is_dir():
        raise AdapterError(f"{MODEL} is not in this checkout")
    return sorted(path.relative_to(root).as_posix() for path in base.rglob("*.sail")
                  if "unit_tests" not in path.parts)


def _index(root: Path) -> dict[str, SailFunction]:
    """Index all non-test Sail functions by name, merging scattered clauses."""
    merged: dict[str, SailFunction] = {}
    for rel in _sail_files(root):
        for fn in _functions(rel, _text(root, rel)):
            seen = merged.get(fn.name)
            merged[fn.name] = (fn if seen is None
                               else SailFunction(fn.name, seen.path, seen.line,
                                                 seen.body + fn.body))
    return merged


def _reaching(index: Mapping[str, SailFunction], target: str) -> frozenset[str]:
    """Return `target` and all functions in `index` that transitively call `target`."""
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
    """Return all non-test call sites of `rot_draw` in the Sail model."""
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
    """Parse `within_<guard>(...) ... then <handler>(...)` routes from `fn`."""
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
    """Extract and classify `offset == ROT_*` arms from MMIO handler `fn`."""
    if fn is None:
        return []
    order: list[str] = []
    draws: dict[str, DrawClass] = {}
    widths: dict[str, int | None] = {}
    current: str | None = None
    for line in fn.body:
        guard = _WIDTH.search(line)
        for match in _OFFSET.finditer(line):
            current = _group(match)
            if current not in draws:
                draws[current] = "none"
                widths[current] = int(_group(guard)) if guard is not None else None
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
    return [Door(window, name, constants[name], access, draws[name], widths[name])
            for name in order]


def _aperture(loaded: Json, key: str) -> tuple[int, int]:
    """Read `(base, size)` for supported aperture `platform.<key>` from `loaded`."""
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
    """Discover composed RoT MMIO windows, their doors, and each door's `rot_draw` classification."""
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
    """Reject unknown sources or R-16-015 sources lacking a production interface."""
    if source not in SOURCES:
        raise AdapterError(f"'{source}' is not one of R-16-015's four closed sources")
    if source in ABSENT_SOURCES:
        raise AdapterError(f"'{source}' has no production interface to adapt; "
                           f"{CONTRACT}'s source table names what is missing")


class RootProducer:
    """Record sealed entropy events from the synchronous `rot_draw` observer callback."""

    def __init__(self, recorder: FixtureRecorder, *, entropy_interface: str,
                 seal: Seal | None = None) -> None:
        if seal is None:
            raise AdapterError("root capture requires an injected sealing primitive")
        if recorder.source_of(entropy_interface) != "entropy":
            raise AdapterError("root capture requires an entropy-classed endpoint")
        self._recorder = recorder
        self._entropy = entropy_interface
        self._seal = seal
        self._closed = False

    def observe(self, *, point: Point, available: bool, value: bytes) -> None:
        """Record one completed root draw (`available=False` records no event)."""
        if self._closed:
            raise AdapterError("root capture is refused or already finished")

        def produce() -> bytes | None:
            if type(available) is not bool or len(value) != 8:
                raise AdapterError("root callback requires a boolean and one 64-bit word")
            if not available:
                if any(value):
                    raise AdapterError("a refused root callback must carry zero")
                return None
            sealed = self._seal(value)
            if sealed is None:
                raise AdapterError("a successful root draw cannot be declined by its seal")
            return sealed

        try:
            self._recorder.record(point=point, interface=self._entropy, produce=produce)
        except BaseException:
            self._recorder.abort()
            self._closed = True
            raise

    def finish(self, *, expected: Binding, expected_events: int) -> bytes:
        if self._closed:
            raise AdapterError("root capture is refused or already finished")
        self._closed = True
        return self._recorder.finish(expected=expected, expected_events=expected_events)


class TraceProducer:
    """Produce sealed entropy events into `recorder` from a commit trace's RoT MMIO accesses.

    Refusals latch and abort `recorder` so a failed capture never finalizes a partial prefix.
    """

    def __init__(self, recorder: FixtureRecorder, *, windows: Iterable[Window],
                 entropy_interface: str, slot: int, core: int,
                 seal: Seal | None = None,
                 internal_account: InternalAccount | None = None) -> None:
        if seal is None:
            raise AdapterError("a sealing primitive must be injected before any draw is "
                               "produced: M3.4 owes the real one, and a host-computed "
                               "hash would satisfy every check here and seal nothing")
        if recorder.source_of(entropy_interface) != "entropy":
            raise AdapterError("the endpoint named here is not an entropy-classed composed "
                               "endpoint, and the classification is the source's rather "
                               "than a caller's: the recorder takes an event's class from "
                               "the endpoint, so a public one would admit these sealed "
                               "bytes as a public value, which R-16-017 forbids")
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
        """Seal and record a bus-observed draw word."""
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
        """Record an internal draw site via `self._account` or refuse the capture."""
        site = f"{door.window}.{door.name}"
        account = self._account
        if account is None:
            self._refuse_internal(site)
        order = self._order
        if self._recorder.record(point=self._point(), interface=self._entropy,
                                 produce=lambda: account(site, order)) is not None:
            self._ordinal += 1

    def _refuse_internal(self, site: str) -> Never:
        message = (f"{site} reaches the model's internal entropy draw and no bus "
                   f"transaction carries it, so this capture is refused whole; "
                   f"use the synchronous {DRAW} observer with RootProducer, or "
                   f"supply an independently authenticated internal account")

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
        if door.width is not None and int(fields[2]) != door.width:
            # Access width mismatch reaches the handler's fault arm without drawing.
            return
        if door.draw == "observed":
            self._observed(door, fields[4])
        else:
            self._internal(door)

    def feed(self, lines: Iterable[str]) -> None:
        """Process commit-trace `lines` and record entropy draw events."""
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
            self._recorder.abort()
            self._failed = True
            raise

    def finish(self, *, expected: Binding, expected_events: int) -> bytes:
        """Finalize the capture against `expected` and `expected_events`."""
        self._ready()
        try:
            blob = self._recorder.finish(expected=expected, expected_events=expected_events)
        except BaseException:
            self._recorder.abort()
            self._failed = True
            raise
        self._finished = True
        return blob
