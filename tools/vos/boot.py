# SPDX-License-Identifier: Apache-2.0
"""M7.1's boot harness: the roster, the recipe that composes it, the boot and its digests.

[The roster and boot-recipe contract](../../docs/implementation/contracts/boot-roster.md)
owns every rule this module applies, and its roster table is the one statement of the
M8a roster's membership: `load_roster` reads that table rather than a second copy of it,
so a member added, re-ranked or re-owned there is what this harness composes against.

The harness has three acts, and each refuses rather than guesses.

* **Compose.** A recipe names each image member's source, its placement and the names
  it imports from its neighbours. Every image member the roster declares must appear,
  none may lack an executable product, the extents must lie in the composition's own
  memory regions without overlapping, and a member's entry is the first byte of its
  text. The members are assembled at their placements by [asm.py](asm.py) and written as
  one position-fixed ELF by [image.py](image.py). The boot record binds the recipe, the
  roster, the configuration, every source and the image by SHA-256, and is written last.
* **Boot.** The record is re-read first: an input whose bytes no longer match is a stale
  component and nothing runs. The golden emulator then runs the image with the commit
  trace on its standard output and the HTIF console in a file of its own.
* **Digest.** The console digest is the SHA-256 of the console bytes. The event log is a
  projection of the commit trace onto fields the RVFI packet also carries: `ENTER` at a
  member's entry, `TRAP` at every trap, `HTIF` at every write to the tohost doubleword,
  and one closing `EXIT`. Its digest is the SHA-256 of that log. The contract states the
  condition under which an RTL run computes the same log. A run is held against the
  recipe's expected digests and against the roster's boot order.

What none of this establishes is stated with it: a fixture member is not the real
producer, the image composer here is not M6.3a's package composer, an absent admission
record keeps a composition unaccepted, and the RoT's release of the main die is M3.5's
harness and not this one's.
"""

import hashlib
import json
import re
import subprocess
import threading
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, TextIO, cast

from . import admission, asm, composer, image, jsonc, trace

CONTRACT: Final[str] = "docs/implementation/contracts/boot-roster.md"
SCHEMA_VERSION: Final[int] = 1

# The roster table's heading and its exact header row. Read by position once the header
# is matched, so a column added or moved in the contract is a refusal here rather than
# a cell read into the wrong field.
ROSTER_HEADING: Final[str] = "## 2. The roster"
ROSTER_HEADER: Final[tuple[str, ...]] = (
    "Member", "Kind", "Rank", "Status", "Executable owner", "Reference", "Entry and handoff")

# The contract's closed vocabularies. `image` members are composed into the main-die
# image and entered; `rot` runs on the RoT's own instance; `offline` runs at composition
# and emits a record rather than code. There is no kind for code linked into its callers:
# a service its consumers call is a compartment of its own (R-13-010b).
KINDS: Final[tuple[str, ...]] = ("rot", "image", "offline")
STATUSES: Final[tuple[str, ...]] = ("executable", "partial", "statement-only", "fixture")
# The statuses that leave a member without a product this harness can compose or run.
NOT_EXECUTABLE: Final[frozenset[str]] = frozenset({"partial", "statement-only"})
PRODUCERS: Final[tuple[str, ...]] = ("asm",)

# The HTIF command word's fields (model/model/sys/platform.sail, `htif_cmd`): device in
# bits 63..56, command in 55..48, payload in 47..0. Device 0 with payload bit 0 set is the
# exit; device 1 command 1 prints the payload's low byte.
PAYLOAD_MASK: Final[int] = (1 << 48) - 1
HTIF_BYTES: Final[int] = 8


class RecipeError(ValueError):
    """A malformed roster, recipe or record: exit 2, nothing composed or run."""


class RefusalError(ValueError):
    """A well-formed input the contract refuses: exit 1, with the named cause."""


# --- the roster -------------------------------------------------------------------


@dataclass(frozen=True)
class RosterMember:
    id: str
    kind: str
    rank: int | None
    status: str
    owner: str


@dataclass(frozen=True)
class Roster:
    source: str
    members: tuple[RosterMember, ...]

    def by_id(self) -> dict[str, RosterMember]:
        return {m.id: m for m in self.members}

    def image_members(self) -> list[RosterMember]:
        return sorted((m for m in self.members if m.kind == "image"),
                      key=lambda m: cast("int", m.rank))

    def blocking(self) -> list[RosterMember]:
        """The members whose absent executable product blocks accepting the roster."""
        return [m for m in self.members if m.status in NOT_EXECUTABLE]


_CODE_RE = re.compile(r"`([^`]+)`")


def _code(cell: str, where: str) -> str:
    match = _CODE_RE.fullmatch(cell.strip())
    if not match:
        raise RecipeError(f"{where}: expected one code span, found {cell.strip()!r}")
    return str(match.group(1))


def _member(member_id: str, kind: str, rank: int | None, status: str, owner: str,
            where: str) -> RosterMember:
    if not re.fullmatch(r"[a-z][a-z0-9-]*", member_id):
        raise RecipeError(f"{where}: member id {member_id!r} is not a lowercase slug")
    if kind not in KINDS:
        raise RecipeError(f"{where}: kind {kind!r} is none of {', '.join(KINDS)}")
    if status not in STATUSES:
        raise RecipeError(f"{where}: status {status!r} is none of {', '.join(STATUSES)}")
    if (rank is None) != (kind != "image"):
        raise RecipeError(f"{where}: an image member carries a rank and no other kind does")
    if rank is not None and rank < 1:
        raise RecipeError(f"{where}: rank {rank} is not positive")
    if not owner.strip():
        raise RecipeError(f"{where}: every member names an executable owner")
    return RosterMember(member_id, kind, rank, status, owner.strip())


def _checked(members: list[RosterMember], source: str) -> Roster:
    if not members:
        raise RecipeError(f"{source}: the roster names no member")
    seen: set[str] = set()
    ranks: set[int] = set()
    for m in members:
        if m.id in seen:
            raise RecipeError(f"{source}: member {m.id} is declared twice")
        seen.add(m.id)
        if m.rank is not None:
            if m.rank in ranks:
                raise RecipeError(f"{source}: rank {m.rank} is declared twice")
            ranks.add(m.rank)
    return Roster(source, tuple(members))


def parse_contract_roster(text: str, source: str = CONTRACT) -> Roster:
    """The roster table under `ROSTER_HEADING`, refusing any row it cannot read whole."""
    lines = text.splitlines()
    try:
        start = lines.index(ROSTER_HEADING)
    except ValueError:
        raise RecipeError(f"{source}: no heading {ROSTER_HEADING!r}") from None
    rows: list[list[str]] = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if line.startswith("|"):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
        elif rows:
            break
    if len(rows) < 3 or tuple(rows[0]) != ROSTER_HEADER:
        raise RecipeError(f"{source}: the roster table's header is not "
                          f"{' | '.join(ROSTER_HEADER)}")
    members: list[RosterMember] = []
    for index, row in enumerate(rows[2:], start=1):
        where = f"{source}: roster row {index}"
        if len(row) != len(ROSTER_HEADER):
            raise RecipeError(f"{where}: {len(row)} cells where the header has "
                              f"{len(ROSTER_HEADER)}")
        rank_text = row[2].strip()
        if rank_text == "n/a":
            rank = None
        elif rank_text.isdigit():
            rank = int(rank_text)
        else:
            raise RecipeError(f"{where}: rank {rank_text!r} is neither a number nor n/a")
        members.append(_member(_code(row[0], where), _code(row[1], where), rank,
                               _code(row[3], where), row[4], where))
    return _checked(members, source)


_ROSTER_KEYS: Final[frozenset[str]] = frozenset({"schema_version", "name", "members"})
_ROSTER_MEMBER_KEYS: Final[frozenset[str]] = frozenset(
    {"id", "kind", "rank", "status", "owner"})


def _exact(obj: object, keys: frozenset[str], where: str) -> dict[str, object]:
    if not isinstance(obj, dict):
        raise RecipeError(f"{where}: expected an object")
    raw = cast("dict[str, object]", obj)
    missing = keys - raw.keys()
    unknown = raw.keys() - keys
    if missing:
        raise RecipeError(f"{where}: missing {', '.join(sorted(missing))}")
    if unknown:
        raise RecipeError(f"{where}: unknown {', '.join(sorted(unknown))}")
    return raw


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise RecipeError(f"{where}: expected a nonempty string")
    return value


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in pairs:
        if key in out:
            raise RecipeError(f"duplicate JSON key {key!r}")
        out[key] = value
    return out


def _json(data: bytes, where: str) -> object:
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecipeError(f"{where}: {exc}") from None
    except RecipeError as exc:
        raise RecipeError(f"{where}: {exc}") from None


def parse_json_roster(data: bytes, source: str) -> Roster:
    """A fixture roster: the contract's columns as JSON, every member a fixture."""
    raw = _exact(_json(data, source), _ROSTER_KEYS, source)
    if raw["schema_version"] != SCHEMA_VERSION:
        raise RecipeError(f"{source}: schema_version must be {SCHEMA_VERSION}")
    _text(raw["name"], f"{source}/name")
    listed = raw["members"]
    if not isinstance(listed, list):
        raise RecipeError(f"{source}/members: expected a list")
    members: list[RosterMember] = []
    for index, item in enumerate(cast("list[object]", listed)):
        where = f"{source}/members[{index}]"
        row = _exact(item, _ROSTER_MEMBER_KEYS, where)
        rank = row["rank"]
        if rank is not None and (not isinstance(rank, int) or isinstance(rank, bool)):
            raise RecipeError(f"{where}/rank: expected an integer or null")
        member = _member(_text(row["id"], f"{where}/id"), _text(row["kind"], f"{where}/kind"),
                         cast("int | None", rank), _text(row["status"], f"{where}/status"),
                         _text(row["owner"], f"{where}/owner"), where)
        if member.status != "fixture":
            raise RecipeError(f"{where}: a JSON roster is a fixture roster and every member "
                              f"is `fixture`; the real roster is the contract's table")
        members.append(member)
    return _checked(members, source)


def load_roster(root: Path, relative: str) -> Roster:
    path = root / relative
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise RecipeError(f"{relative}: {exc}") from None
    if relative.endswith(".md"):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RecipeError(f"{relative}: {exc}") from None
        return parse_contract_roster(text, relative)
    return parse_json_roster(data, relative)


# --- the recipe -------------------------------------------------------------------


@dataclass(frozen=True)
class RecipeMember:
    id: str
    producer: str
    source: str
    text_base: int
    data_base: int
    imports: dict[str, str]


@dataclass(frozen=True)
class Expected:
    """What the reference run measured, and on which image it measured it."""

    image_sha256: str
    console_sha256: str
    event_sha256: str
    events: int
    trace_digest: str
    retired: int


@dataclass(frozen=True)
class ComposerAttachment:
    source: str
    address: int


@dataclass(frozen=True)
class Recipe:
    path: str
    name: str
    roster: str
    configuration: str
    inst_limit: int
    tohost: int
    members: tuple[RecipeMember, ...]
    expected: Expected | None
    composer: ComposerAttachment | None = None
    admission: str | None = None

    @property
    def schema_version(self) -> int:
        return 2 if self.composer is not None else 1


_RECIPE_KEYS: Final[frozenset[str]] = frozenset({
    "schema_version", "name", "roster", "configuration", "inst_limit", "tohost",
    "members", "admission", "expected"})
_RECIPE_MEMBER_KEYS: Final[frozenset[str]] = frozenset({
    "id", "producer", "source", "text_base", "data_base", "imports"})
_EXPECTED_KEYS: Final[frozenset[str]] = frozenset({
    "image_sha256", "console_sha256", "event_sha256", "events", "trace_digest", "retired"})
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_DIGEST16_RE = re.compile(r"[0-9a-f]{16}")


def _address(value: object, where: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-fA-F]+", value):
        raise RecipeError(f"{where}: expected a hexadecimal address string")
    return int(value, 16)


def _count(value: object, where: str, *, positive: bool) -> int:
    if (not isinstance(value, int) or isinstance(value, bool)
            or value < (1 if positive else 0)):
        raise RecipeError(f"{where}: expected a {'positive' if positive else 'nonnegative'} "
                          f"integer")
    return value


def _hex_digest(value: object, where: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise RecipeError(f"{where}: expected lowercase hexadecimal of the digest's width")
    return value


def parse_recipe(data: bytes, path: str) -> Recipe:
    parsed = _json(data, path)
    if not isinstance(parsed, dict):
        raise RecipeError(f"{path}: expected an object")
    version = parsed.get("schema_version")
    if type(version) is not int or version not in (1, 2):
        raise RecipeError(f"{path}: schema_version must be 1 or 2")
    raw = _exact(parsed, _RECIPE_KEYS | ({"composer"} if version == 2 else set()), path)
    members: list[RecipeMember] = []
    listed = raw["members"]
    if not isinstance(listed, list) or not listed:
        raise RecipeError(f"{path}/members: expected a nonempty list")
    for index, item in enumerate(cast("list[object]", listed)):
        where = f"{path}/members[{index}]"
        row = _exact(item, _RECIPE_MEMBER_KEYS, where)
        producer = _text(row["producer"], f"{where}/producer")
        if producer not in PRODUCERS:
            raise RecipeError(f"{where}/producer: {producer!r} is not a producer this harness "
                              f"drives; schema {SCHEMA_VERSION} composes assembly only")
        imports = row["imports"]
        if not isinstance(imports, dict):
            raise RecipeError(f"{where}/imports: expected an object")
        named = {_text(k, f"{where}/imports"): _text(v, f"{where}/imports/{k}")
                 for k, v in cast("dict[str, object]", imports).items()}
        members.append(RecipeMember(
            _text(row["id"], f"{where}/id"), producer, _text(row["source"], f"{where}/source"),
            _address(row["text_base"], f"{where}/text_base"),
            _address(row["data_base"], f"{where}/data_base"), named))
    attached_composer = None
    attached_admission = None
    if version == 1 and raw["admission"] is not None:
        raise RecipeError(f"{path}/admission: schema {SCHEMA_VERSION} defines no admission "
                          f"record, so the field must be null; the executable admission "
                          f"package defines the record it binds")
    if version == 2:
        block = _exact(raw["composer"], frozenset({"source", "address"}), f"{path}/composer")
        attached_composer = ComposerAttachment(
            _text(block["source"], f"{path}/composer/source"),
            _address(block["address"], f"{path}/composer/address"))
        attached_admission = _text(raw["admission"], f"{path}/admission")
    expected_raw = raw["expected"]
    expected = None
    if expected_raw is not None:
        where = f"{path}/expected"
        block = _exact(expected_raw, _EXPECTED_KEYS, where)
        expected = Expected(
            _hex_digest(block["image_sha256"], f"{where}/image_sha256", _SHA256_RE),
            _hex_digest(block["console_sha256"], f"{where}/console_sha256", _SHA256_RE),
            _hex_digest(block["event_sha256"], f"{where}/event_sha256", _SHA256_RE),
            _count(block["events"], f"{where}/events", positive=True),
            _hex_digest(block["trace_digest"], f"{where}/trace_digest", _DIGEST16_RE),
            _count(block["retired"], f"{where}/retired", positive=True))
    return Recipe(path, _text(raw["name"], f"{path}/name"), _text(raw["roster"], f"{path}/roster"),
                  _text(raw["configuration"], f"{path}/configuration"),
                  _count(raw["inst_limit"], f"{path}/inst_limit", positive=True),
                  _address(raw["tohost"], f"{path}/tohost"), tuple(members), expected,
                  attached_composer, attached_admission)


def load_recipe(root: Path, relative: str) -> Recipe:
    try:
        return parse_recipe((root / relative).read_bytes(), relative)
    except OSError as exc:
        raise RecipeError(f"{relative}: {exc}") from None


def declaration_sha256(path: Path) -> str:
    """The digest of a recipe's declaration: every field but the measured `expected` block.

    The record binds this rather than the file's bytes, because a refresh rewrites the
    measured block and nothing a composition reads; binding the bytes would make every
    refreshed recipe a stale input to the image it was just measured on.
    """
    raw = _json(path.read_bytes(), str(path))
    if not isinstance(raw, dict):
        raise RecipeError(f"{path}: expected an object")
    declared = {k: v for k, v in cast("dict[str, object]", raw).items() if k != "expected"}
    return digest_bytes(_canonical(declared))


# --- composition ------------------------------------------------------------------


@dataclass(frozen=True)
class Region:
    base: int
    size: int
    executable: bool
    writable: bool

    def holds(self, start: int, length: int) -> bool:
        return self.base <= start and start + length <= self.base + self.size


def _field(value: jsonc.Json, key: str, where: str) -> jsonc.Json:
    if not isinstance(value, dict) or key not in value:
        raise RecipeError(f"{where}: no field {key}")
    return value[key]


def _hex_value(value: jsonc.Json, where: str) -> int:
    """A configuration integer, which the model's files spell `{"len": .., "value": "0x.."}`."""
    spelled = _field(value, "value", where)
    if not isinstance(spelled, str) or not re.fullmatch(r"0x[0-9a-fA-F]+", spelled):
        raise RecipeError(f"{where}: expected a hexadecimal value")
    return int(spelled, 16)


def regions(configuration: Path) -> list[Region]:
    """The composition's main-memory regions, read from the file the emulator reads."""
    try:
        raw = jsonc.load(configuration)
    except (OSError, ValueError) as exc:
        raise RecipeError(f"{configuration}: {exc}") from None
    where = f"{configuration}: memory.regions"
    listed = _field(_field(raw, "memory", where), "regions", where)
    if not isinstance(listed, list):
        raise RecipeError(f"{where}: expected a list")
    out: list[Region] = []
    for index, region in enumerate(listed):
        here = f"{where}[{index}]"
        attributes = _field(region, "attributes", here)
        if _field(attributes, "mem_type", here) != "MainMemory":
            continue
        out.append(Region(_hex_value(_field(region, "base", here), f"{here}.base"),
                          _hex_value(_field(region, "size", here), f"{here}.size"),
                          _field(attributes, "executable", here) is True,
                          _field(attributes, "writable", here) is True))
    if not out:
        raise RecipeError(f"{configuration}: declares no MainMemory region")
    return out


@dataclass
class Placed:
    member: RecipeMember
    roster: RosterMember
    source_sha256: str
    entry: int
    text: tuple[int, int]
    data: tuple[int, int]
    resolved: dict[str, int]
    sections: list[image.Section] = field(default_factory=list)
    symbols: dict[str, tuple[str, int]] = field(default_factory=dict)


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def check_membership(recipe: Recipe, roster: Roster) -> None:
    """Duplicated, unknown, misplaced, non-executable and missing members, and the order."""
    known = roster.by_id()
    ids = [m.id for m in recipe.members]
    duplicate = sorted({i for i in ids if ids.count(i) > 1})
    if duplicate:
        raise RefusalError(f"member {', '.join(duplicate)} is composed twice")
    unknown = [i for i in ids if i not in known]
    if unknown:
        raise RefusalError(f"{', '.join(unknown)} is not a member of the roster {roster.source}")
    for member_id in ids:
        declared = known[member_id]
        if declared.kind != "image":
            raise RefusalError(f"{member_id} is a `{declared.kind}` member and has no place in the "
                          f"main-die image")
        if declared.status in NOT_EXECUTABLE:
            raise RefusalError(f"{member_id} is {declared.status}: no executable product exists "
                          f"to compose (executable owner {declared.owner})")
    missing = [m for m in roster.image_members() if m.id not in ids]
    if missing:
        raise RefusalError("missing member " + "; missing member ".join(
            f"{m.id} ({m.status}, executable owner {m.owner})" for m in missing))
    ranks = [cast("int", known[i].rank) for i in ids]
    if ranks != sorted(ranks):
        raise RefusalError(f"the recipe's member order {', '.join(ids)} contradicts the roster's "
                      f"boot ranks {ranks}")


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[1] > 0 and b[1] > 0 and a[0] < b[0] + b[1] and b[0] < a[0] + a[1]


def _place(root: Path, recipe: Recipe, roster: Roster) -> list[Placed]:
    known = roster.by_id()
    entries = {m.id: m.text_base for m in recipe.members}
    placed: list[Placed] = []
    for member in recipe.members:
        resolved: dict[str, int] = {"tohost": recipe.tohost}
        for name, target in member.imports.items():
            if name == "tohost":
                raise RefusalError(f"{member.id} imports tohost by name; the recipe owns it")
            if target not in entries:
                raise RefusalError(f"{member.id} imports {name} from {target}, which the recipe "
                              f"does not compose")
            if target == member.id:
                raise RefusalError(f"{member.id} imports {name} from itself")
            resolved[name] = entries[target]
        # An unreadable or undecodable source is an input the harness cannot read (exit 2),
        # not a refusal of a well-formed member.
        source = root / member.source
        try:
            data = source.read_bytes()
            text = data.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise RecipeError(f"{member.id}: its source {member.source} is unreadable "
                              f"({exc})") from None
        unit = asm.Assembler(text, member.source, text_base=member.text_base,
                             data_base=member.data_base, externals=resolved)
        try:
            sections, symbols, entry = unit.assemble()
        except asm.AsmError as exc:
            raise RefusalError(f"{member.id}: {exc}") from None
        if "_start" not in symbols or entry != member.text_base:
            raise RefusalError(f"{member.id}: its entry must be `_start` at the first byte of its "
                          f"text, {member.text_base:#x}")
        text_section, data_section = sections
        for section in (text_section, data_section):
            section.name = f"{section.name}.{member.id}"
        qualified = {f"{member.id}.{name}": (f"{section}.{member.id}", value)
                     for name, (section, value) in symbols.items()}
        placed.append(Placed(member, known[member.id], digest_bytes(data), entry,
                             (text_section.addr, len(text_section.data)),
                             (data_section.addr, len(data_section.data)), resolved,
                             [text_section, data_section], qualified))
    return placed


def _check_extents(placed: list[Placed], memory: list[Region], tohost: int) -> None:
    if tohost % HTIF_BYTES:
        raise RefusalError(f"tohost {tohost:#x} is not doubleword aligned")
    extents: list[tuple[str, tuple[int, int], bool]] = []
    for p in placed:
        extents.append((f"{p.member.id} text", p.text, True))
        extents.append((f"{p.member.id} data", p.data, False))
    extents.append(("tohost", (tohost, HTIF_BYTES), False))
    for name, (start, length), executable in extents:
        if length == 0:
            continue
        home = [r for r in memory if r.holds(start, length)]
        if not home:
            raise RefusalError(f"{name} [{start:#x}, {start + length:#x}) lies in no MainMemory "
                          f"region of the composition")
        if executable and not home[0].executable:
            raise RefusalError(f"{name} lies in a region the composition does not make executable")
        if not executable and not home[0].writable:
            raise RefusalError(f"{name} lies in a region the composition does not make writable")
    for i, (a_name, a, _) in enumerate(extents):
        for b_name, b, _ in extents[i + 1:]:
            if _overlaps(a, b):
                raise RefusalError(f"{a_name} and {b_name} overlap")


def _canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _git(root: Path, *args: str) -> tuple[int, str]:
    try:
        done = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                              text=True, encoding="utf-8", check=False)
    except OSError:
        return 1, ""
    return done.returncode, done.stdout.strip()


def producing_inputs(root: Path) -> list[str]:
    """The modules that turn a recipe's inputs into the image's bytes, as input paths.

    A locally modified assembler, image writer or placement composes a different image
    from the same recipe, so the revision names an image only where these are that
    revision's bytes too. A module outside `root` is named by its absolute path, which
    `_differs_from_revision` reads as an input the revision does not hold.
    """
    resolved = root.resolve()
    out: list[str] = []
    for module_file in (asm.__file__, image.__file__, __file__):
        path = Path(module_file).resolve()
        out.append(path.relative_to(resolved).as_posix() if path.is_relative_to(resolved)
                   else str(path))
    return out


def _graph_attachment(root: Path, recipe: Recipe, roster: Roster,
                      placed: list[Placed], memory: list[Region]) -> bytes | None:
    if recipe.composer is None:
        return None
    try:
        descriptors = composer.load_document(root, recipe.composer.source)
        graph = composer.graph_bytes(descriptors)
        composer.validate_graph(descriptors, graph, tuple(m.id for m in roster.members))
    except composer.ComposerError as exc:
        raise RecipeError(f"composer: {exc}") from exc
    extent = (recipe.composer.address, len(graph))
    if not any(region.holds(*extent) for region in memory):
        raise RefusalError("handler graph lies in no MainMemory region of the composition")
    occupied = [("tohost", (recipe.tohost, HTIF_BYTES))]
    for member in placed:
        occupied += [(f"{member.member.id} text", member.text),
                     (f"{member.member.id} data", member.data)]
    for name, other in occupied:
        if other[1] and _overlaps(extent, other):
            raise RefusalError(f"handler graph and {name} overlap")
    return graph


def _admission_attachment(root: Path, recipe: Recipe, roster: Roster,
                          image_bytes: bytes, graph: bytes) -> dict[str, object]:
    if recipe.admission is None:
        raise RecipeError("a composed graph requires a reference admission request")
    try:
        record = admission.make_record(root, recipe.admission, image_bytes, graph, roster)
    except (admission.AdmissionError, OSError) as exc:
        raise RecipeError(f"admission: {exc}") from exc
    if record["decision"] != "accepted":
        raise RefusalError("admission refused a member; the whole generation is refused")
    _admitted_sources(root, recipe, record)
    return record


def _admitted_sources(root: Path, recipe: Recipe, record: dict[str, object]) -> None:
    """Join each image member's reference evidence to the source actually assembled."""
    records = {cast("str", member["member"]): member
               for member in cast("list[dict[str, object]]", record["members"])}
    for member in recipe.members:
        certified = records.get(member.id)
        source = (root / member.source).resolve()
        if (certified is None
                or (root / cast("str", certified["artifact"])).resolve() != source
                or certified["artifact_sha256"] != digest_file(source)):
            raise RefusalError(f"admission artifact for {member.id} differs from its recipe source")


def _differs_from_revision(root: Path, inputs: list[str]) -> bool:
    """Whether any input is not the revision's own bytes: changed, untracked or outside."""
    resolved = root.resolve()
    for relative in inputs:
        path = (root / relative).resolve()
        if not path.is_relative_to(resolved):
            return True
        code, _ = _git(root, "ls-files", "--error-unmatch", "--", relative)
        if code != 0:
            return True
    code, status = _git(root, "status", "--porcelain", "--", *inputs)
    return code != 0 or bool(status)


def compose(root: Path, recipe: Recipe, out: Path) -> dict[str, object]:
    """Compose a recipe into `out`: the image, its link map, and the boot record.

    Returns the record it wrote. Raises `RefusalError` for a recipe the contract refuses and
    `RecipeError` for one it cannot read. A previous record in `out` is removed before
    anything else, and the new one is written last, so a refused composition leaves no
    record claiming that the image beside it was composed from these inputs.
    """
    record_path = out / "record.json"
    record_path.unlink(missing_ok=True)
    roster = load_roster(root, recipe.roster)
    check_membership(recipe, roster)
    configuration = root / recipe.configuration
    memory = regions(configuration)
    placed = _place(root, recipe, roster)
    _check_extents(placed, memory, recipe.tohost)
    graph = _graph_attachment(root, recipe, roster, placed, memory)

    sections: list[image.Section] = []
    symbols: dict[str, tuple[str, int]] = {}
    for p in placed:
        sections += p.sections
        symbols.update(p.symbols)
    sections.append(image.Section(".htif", recipe.tohost, bytearray(HTIF_BYTES), writable=True))
    symbols["tohost"] = (".htif", recipe.tohost)
    if graph is not None and recipe.composer is not None:
        sections.append(image.Section(".handler_graph", recipe.composer.address, bytearray(graph)))
        symbols["handler_graph"] = (".handler_graph", recipe.composer.address)

    out.mkdir(parents=True, exist_ok=True)
    elf = out / "image.elf"
    image.write_elf(elf, sections, symbols, placed[0].entry)
    admission_record = (_admission_attachment(root, recipe, roster, elf.read_bytes(), graph)
                        if graph is not None else None)

    members = [{
        "id": p.member.id, "kind": p.roster.kind, "rank": p.roster.rank,
        "status": p.roster.status, "owner": p.roster.owner, "producer": p.member.producer,
        "source": {"path": p.member.source, "sha256": p.source_sha256},
        "entry": f"{p.entry:#x}",
        "text": [f"{p.text[0]:#x}", p.text[1]], "data": [f"{p.data[0]:#x}", p.data[1]],
        "imports": {name: f"{value:#x}" for name, value in sorted(p.resolved.items())},
    } for p in placed]
    configuration_sha = digest_file(configuration)
    composition: dict[str, object] = {
        "configuration": configuration_sha, "tohost": f"{recipe.tohost:#x}", "members": members}
    graph_record = None
    if graph is not None and recipe.composer is not None:
        (out / "handler-graph.json").write_bytes(graph)
        graph_record = {
            "source": {"path": recipe.composer.source,
                       "sha256": digest_file(root / recipe.composer.source)},
            "path": "handler-graph.json", "sha256": digest_bytes(graph),
            "producer_sha256": digest_file(root / "tools/vos/composer.py"),
            "address": f"{recipe.composer.address:#x}", "bytes": len(graph)}
        composition["composer"] = graph_record
    admission_binding = None
    if admission_record is not None:
        (out / "admission.json").write_bytes(_canonical(admission_record) + b"\n")
        admission_binding = {"path": "admission.json", "sha256": digest_file(out / "admission.json")}
    link_map = "".join(f"{p.member.id}\t{p.entry:#x}\t{p.text[0]:#x}\t{p.text[1]}\t"
                       f"{p.data[0]:#x}\t{p.data[1]}\n" for p in placed)
    (out / "link-map.tsv").write_text("id\tentry\ttext\ttext_bytes\tdata\tdata_bytes\n"
                                      + link_map, encoding="utf-8", newline="\n")

    fixture = [p.member.id for p in placed if p.roster.status == "fixture"]
    open_joins = [f"{m.id} ({m.kind}, {m.status}): executable owner {m.owner}"
                  for m in roster.blocking()]
    open_joins.append("reference discharge metadata is not production admission evidence"
                      if admission_record is not None else
                      "no composition-time admission record binds this image")
    if fixture:
        open_joins.append(f"fixture members stand in for real producers: {', '.join(fixture)}")
    open_joins.append("the RoT's release of the main die is driven by M3.5's harness, "
                      "not by this one")
    inputs = ([recipe.path, recipe.roster, recipe.configuration]
              + [m.source for m in recipe.members] + producing_inputs(root))
    if recipe.composer is not None and recipe.admission is not None:
        inputs += [recipe.composer.source, recipe.admission, "tools/vos/composer.py",
                   "tools/vos/admission.py", "proofs/AdmissionPath.v"]
        if admission_record is not None:
            inputs += [cast("str", member["artifact"])
                       for member in cast("list[dict[str, object]]", admission_record["members"])]
    _, revision = _git(root, "rev-parse", "HEAD")
    record: dict[str, object] = {
        "schema_version": recipe.schema_version,
        "recipe": {"path": recipe.path,
                   "declaration_sha256": declaration_sha256(root / recipe.path),
                   "name": recipe.name},
        "roster": {"path": recipe.roster, "sha256": digest_file(root / recipe.roster)},
        "configuration": {"path": recipe.configuration, "sha256": configuration_sha},
        "revision": revision,
        "inputs_differ_from_revision": _differs_from_revision(root, inputs),
        "inst_limit": recipe.inst_limit,
        "tohost": f"{recipe.tohost:#x}",
        "members": members,
        "image": {"path": "image.elf", "sha256": digest_file(elf),
                  "bytes": elf.stat().st_size},
        "composition_sha256": digest_bytes(_canonical(composition)),
        "accepted": False,
        "open": open_joins,
    }
    if graph_record is not None:
        record["composer"] = graph_record
        record["admission"] = admission_binding
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return record


def load_record(out: Path) -> dict[str, object]:
    path = out / "record.json"
    try:
        raw = _json(path.read_bytes(), str(path))
    except OSError:
        raise RecipeError(f"no boot record at {path}; compose the recipe first") from None
    if not isinstance(raw, dict):
        raise RecipeError(f"{path}: expected an object")
    record = cast("dict[str, object]", raw)
    if type(record.get("schema_version")) is not int or record.get("schema_version") not in (1, 2):
        raise RecipeError(f"{path}: schema_version must be 1 or 2")
    _record_shape(record, str(path))
    return record


def _bound_file(value: object, where: str, digest_key: str = "sha256") -> None:
    if not isinstance(value, dict):
        raise RecipeError(f"{where}: expected an object")
    block = cast("dict[str, object]", value)
    _text(block.get("path"), f"{where}/path")
    _hex_digest(block.get(digest_key), f"{where}/{digest_key}", _SHA256_RE)


def _record_shape(record: dict[str, object], where: str) -> None:
    """Every field `stale`, `boot run` and the roster identity read, before any is read.

    A record is written by `compose` and read back here; a record some other hand wrote
    or truncated is an input the harness cannot read, and is refused whole rather than
    failing on the first field a later step happens to reach.
    """
    try:
        _record_fields(record, where)
    except RecipeError as exc:
        raise RecipeError(f"unreadable boot record: {exc}") from None


def _record_fields(record: dict[str, object], where: str) -> None:
    _bound_file(record.get("recipe"), f"{where}: recipe", "declaration_sha256")
    for key in ("roster", "configuration", "image"):
        _bound_file(record.get(key), f"{where}: {key}")
    if record.get("schema_version") == 2:
        if record.get("accepted") is not False:
            raise RecipeError(f"{where}: reference attachments cannot authorize production acceptance")
        _bound_file(record.get("composer"), f"{where}: composer")
        attached = cast("dict[str, object]", record["composer"])
        _bound_file(attached.get("source"), f"{where}: composer source")
        _address(attached.get("address"), f"{where}: composer address")
        _hex_digest(attached.get("producer_sha256"), f"{where}: composer producer", _SHA256_RE)
        _count(attached.get("bytes"), f"{where}: composer bytes", positive=True)
        _bound_file(record.get("admission"), f"{where}: admission")
    if not isinstance(record.get("revision"), str):
        raise RecipeError(f"{where}: revision: expected a string")
    if not isinstance(record.get("inputs_differ_from_revision"), bool):
        raise RecipeError(f"{where}: inputs_differ_from_revision: expected a boolean")
    _address(record.get("tohost"), f"{where}: tohost")
    _hex_digest(record.get("composition_sha256"), f"{where}: composition_sha256", _SHA256_RE)
    members = record.get("members")
    if not isinstance(members, list) or not members:
        raise RecipeError(f"{where}: members: expected a nonempty list")
    for index, member in enumerate(cast("list[object]", members)):
        here = f"{where}: members[{index}]"
        if not isinstance(member, dict):
            raise RecipeError(f"{here}: expected an object")
        row = cast("dict[str, object]", member)
        _text(row.get("id"), f"{here}/id")
        _address(row.get("entry"), f"{here}/entry")
        _bound_file(row.get("source"), f"{here}/source")


# --- staleness --------------------------------------------------------------------


def _attachment_findings(root: Path, record: dict[str, object], out: Path,
                         recipe: Recipe) -> list[str]:
    if record.get("schema_version") != recipe.schema_version:
        return ["boot record schema differs from the recipe"]
    if record.get("accepted") is not False:
        return ["reference attachments cannot authorize production acceptance"]
    if recipe.composer is None:
        return []
    try:
        roster = load_roster(root, recipe.roster)
        descriptors = composer.load_document(root, recipe.composer.source)
        graph = (out / "handler-graph.json").read_bytes()
        composer.validate_graph(descriptors, graph, tuple(m.id for m in roster.members))
        expected_graph = {
            "source": {"path": recipe.composer.source,
                       "sha256": digest_file(root / recipe.composer.source)},
            "path": "handler-graph.json", "sha256": digest_bytes(graph),
            "producer_sha256": digest_file(root / "tools/vos/composer.py"),
            "address": f"{recipe.composer.address:#x}", "bytes": len(graph)}
        if record.get("composer") != expected_graph:
            return ["composer binding differs from the recipe or graph inputs"]
        admission_bytes = (out / "admission.json").read_bytes()
        if record.get("admission") != {
                "path": "admission.json", "sha256": digest_bytes(admission_bytes)}:
            return ["admission attachment differs from the boot record"]
        attached = _json(admission_bytes, "admission.json")
        if not isinstance(attached, dict):
            return ["admission attachment is not an object"]
        request = attached.get("request")
        if not isinstance(request, dict) or request.get("path") != recipe.admission:
            return ["admission request differs from the recipe"]
        findings = admission.validate_record(root, attached, (out / "image.elf").read_bytes(),
                                              graph, roster)
        if not findings:
            _admitted_sources(root, recipe, cast("dict[str, object]", attached))
    except (RecipeError, RefusalError, composer.ComposerError, admission.AdmissionError, OSError) as exc:
        return [f"composition attachments: {exc}"]
    else:
        return findings


def stale(root: Path, record: dict[str, object], out: Path) -> list[str]:
    """Every input whose bytes no longer match the record, named; empty when fresh."""
    findings: list[str] = []

    def against(path: Path, sha: object, what: str, *, declaration: bool = False) -> None:
        try:
            now = declaration_sha256(path) if declaration else digest_file(path)
        except OSError:
            findings.append(f"{what}: {path} is missing")
            return
        except RecipeError as exc:
            findings.append(f"{what}: {exc}")
            return
        if now != sha:
            findings.append(f"{what}: {path} changed since composition")

    try:
        for member in cast("list[dict[str, object]]", record["members"]):
            source = cast("dict[str, str]", member["source"])
            against(root / source["path"], source["sha256"],
                    f"stale component {cast('str', member['id'])}")
        recipe = cast("dict[str, str]", record["recipe"])
        against(root / recipe["path"], recipe["declaration_sha256"], "stale recipe",
                declaration=True)
        for key in ("roster", "configuration"):
            block = cast("dict[str, str]", record[key])
            against(root / block["path"], block["sha256"], f"stale {key}")
        picture = cast("dict[str, str]", record["image"])
        against(out / picture["path"], picture["sha256"], "stale image")
        current_recipe = load_recipe(root, recipe["path"])
        if current_recipe.schema_version == 2 or record.get("schema_version") == 2:
            findings += _attachment_findings(root, record, out, current_recipe)
    except (KeyError, TypeError) as exc:
        raise RecipeError(f"{out / 'record.json'}: unreadable boot record ({exc})") from None
    return findings


# --- the run and its digests ------------------------------------------------------


@dataclass
class Projection:
    """What one run's standard output said, reduced to the contract's observations."""

    events: list[str]
    records: int
    retired: int
    trace_digest: str
    verdict: str | None
    htif_exit: int | None
    console: bytes

    def event_log(self) -> bytes:
        return "".join(f"{event}\n" for event in self.events).encode("ascii")

    @property
    def event_sha256(self) -> str:
        return digest_bytes(self.event_log())


def project(lines: Iterable[str], entries: dict[int, str], tohost: int) -> Projection:
    """The event log, the commit-trace fingerprint and the HTIF reading of one run.

    `lines` is the emulator's standard output, read once as a stream because a composed
    boot's trace is far larger than a corpus member's. A line is a commit record exactly
    when [trace.py](trace.py)'s normalizer would keep it, and the fingerprint is that
    module's `digest` over the same records, so a boot and a corpus member are
    fingerprinted by one definition. Of the other lines only the emulator's own verdict
    is kept, as the second channel the HTIF reading is held against.

    `retired` counts `I` records, one per traced step, which includes a step that traps
    and the step that takes an interrupt. That step is traced as an `I` record with a zero
    word at the saved PC and a `T 1` record under it (the reading
    [test_trap_boundary.py](../tests/test_trap_boundary.py) already makes); nothing is
    issued at that PC, so it enters no member, and its `ENTER` is held until the step's
    own records say whether it was one.
    """
    events: list[str] = []
    running = hashlib.sha256()
    records = retired = 0
    verdict: str | None = None
    htif_exit: int | None = None
    console = bytearray()
    held: tuple[int, str] | None = None
    for raw in lines:
        line = raw.rstrip("\n").rstrip()
        if not trace.COMMIT_RE.match(line):
            if verdict is None and line.startswith(("SUCCESS", "FAILURE")):
                verdict = line
            continue
        record = trace.ORDER_RE.sub("I ", line)
        running.update((("\n" if records else "") + record).encode())
        records += 1
        kind = record[0]
        if kind == "I" and held is not None:
            # The previous step issued at its PC after all: its entry goes where it was
            # held, ahead of the events its own records added.
            events.insert(held[0], held[1])
            held = None
        if kind == "I":
            retired += 1
            pc = int(record[2:18], 16)
            if pc in entries:
                if record.endswith(" 00000000"):
                    held = (len(events), f"ENTER {entries[pc]}")
                else:
                    events.append(f"ENTER {entries[pc]}")
        elif kind == "T":
            if record.startswith("T 1 "):
                held = None
            events.append("TRAP")
        elif kind == "W":
            _, address_hex, width_text, _, value_hex = record.split()
            address, width = int(address_hex, 16), int(width_text)
            if tohost <= address < tohost + HTIF_BYTES:
                events.append(f"HTIF {address - tohost} {width} {value_hex}")
                if address == tohost and width == HTIF_BYTES:
                    value = int(value_hex, 16)
                    device, command, payload = value >> 56, (value >> 48) & 0xFF, value & PAYLOAD_MASK
                    if device == 1 and command == 1:
                        console.append(payload & 0xFF)
                    elif device == 0 and payload & 1:
                        htif_exit = payload >> 1
    if held is not None:
        events.insert(held[0], held[1])
    events.append(f"EXIT {'none' if htif_exit is None else htif_exit}")
    return Projection(events, records, retired, running.hexdigest()[:16], verdict, htif_exit,
                      bytes(console))


def verdict_code(verdict: str | None) -> int | None:
    """The exit code the emulator's verdict line states, or None where it states none."""
    if verdict is None:
        return None
    if verdict.startswith("SUCCESS"):
        return 0
    failure = re.match(r"FAILURE: (\d+)", verdict)
    return int(failure.group(1)) if failure else None


def entries_of(record: dict[str, object]) -> dict[int, str]:
    return {int(cast("str", m["entry"]), 16): cast("str", m["id"])
            for m in cast("list[dict[str, object]]", record["members"])}


def boot_order(events: list[str], record: dict[str, object]) -> list[str]:
    """Findings where the members' first entries do not follow the composed order."""
    wanted = [cast("str", m["id"]) for m in cast("list[dict[str, object]]", record["members"])]
    first: list[str] = []
    for event in events:
        if event.startswith("ENTER "):
            member = event.removeprefix("ENTER ")
            if member not in first:
                first.append(member)
    findings = [f"member {m} was never entered" for m in wanted if m not in first]
    if not findings and first != wanted:
        findings.append(f"first entries {', '.join(first)} do not follow the composed order "
                        f"{', '.join(wanted)}")
    return findings


@dataclass
class Observation:
    """One run: its projection, its console bytes and how the process ended."""

    projection: Projection
    console: bytes
    returncode: int
    timed_out: bool
    wall_seconds: float

    @property
    def console_sha256(self) -> str:
        return digest_bytes(self.console)


def _tee(stream: Iterable[str], sink: TextIO) -> Iterator[str]:
    for line in stream:
        sink.write(line)
        yield line


def boot_image(argv: list[str], console_path: Path, entries: dict[int, str], tohost: int,
               timeout: float, trace_path: Path | None = None) -> Observation:
    """Run one image and project its output as it streams past.

    `argv` is the whole emulator command line, the console file among its arguments.
    The run is killed at `timeout` seconds, which is a finding and never a verdict.
    """
    console_path.unlink(missing_ok=True)
    started = time.monotonic()
    fired = threading.Event()
    with subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                          encoding="utf-8", errors="replace") as proc:
        def kill() -> None:
            fired.set()
            proc.kill()

        timer = threading.Timer(timeout, kill)
        timer.start()
        try:
            # Popen with PIPE always opens the stream; the test is the type's, not the run's.
            stream = proc.stdout
            if stream is None:
                raise RecipeError("the emulator's standard output was not captured")
            if trace_path is None:
                projection = project(stream, entries, tohost)
            else:
                with trace_path.open("w", encoding="utf-8", newline="\n") as sink:
                    projection = project(_tee(stream, sink), entries, tohost)
            returncode = proc.wait()
        finally:
            timer.cancel()
    console = console_path.read_bytes() if console_path.exists() else b""
    return Observation(projection, console, returncode, fired.is_set(),
                       time.monotonic() - started)


def run_findings(observation: Observation, record: dict[str, object]) -> list[str]:
    """Every way a run falls short of a clean boot, before any expected digest is read."""
    projection = observation.projection
    findings: list[str] = []
    if observation.timed_out:
        findings.append("the run was stopped at the timeout before it reported")
    elif observation.returncode != 0:
        # A clean boot ends with the emulator's own exit 0 (riscv_sim.cpp exits 0 only
        # after SUCCESS and without a model exception); a crash in teardown or a kill
        # after a SUCCESS line and an HTIF exit 0 is still not a clean boot.
        how = (f"was killed by signal {-observation.returncode}" if observation.returncode < 0
               else f"exited {observation.returncode}")
        findings.append(f"the emulator process {how}, whatever its output said")
    if projection.htif_exit is None:
        findings.append(f"no HTIF exit was written (emulator exit {observation.returncode})")
    elif projection.htif_exit != 0:
        findings.append(f"HTIF exit {projection.htif_exit}")
    stated = verdict_code(projection.verdict)
    if stated != projection.htif_exit:
        findings.append(f"the emulator's verdict {projection.verdict!r} disagrees with the HTIF "
                        f"exit the trace carries ({projection.htif_exit})")
    if observation.console != projection.console:
        findings.append(f"the console file holds {len(observation.console)} byte(s) and the "
                        f"trace's HTIF writes carry {len(projection.console)} different ones")
    findings += boot_order(projection.events, record)
    return findings


_REVISION_RE = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")


def roster_identity(record: dict[str, object]) -> tuple[dict[str, object] | None, str | None]:
    """The identity roster-measurement.md's capture boundary requires, or why not.

    That contract's revision is a full Git object ID, and it names the image only where
    every input and producing module is the revision's own bytes; otherwise the identity
    is withheld with its reason rather than carried with a revision that does not name
    this image. Withholding it refuses no boot: the digests are the bound bytes' either way.
    """
    revision = record["revision"]
    if not isinstance(revision, str) or not _REVISION_RE.fullmatch(revision):
        return None, f"the record's revision {revision!r} is not a full Git object ID"
    if record["inputs_differ_from_revision"] is not False:
        return None, (f"an input or producing module differs from revision {revision}'s "
                      f"bytes, so the revision does not name this image")
    return {"roster_revision": revision,
            "image_sha256": cast("dict[str, str]", record["image"])["sha256"],
            "composition_sha256": record["composition_sha256"]}, None


def against_expected(observation: Observation, image_sha256: str,
                     expected: Expected | None) -> list[str]:
    if expected is None:
        return ["the recipe records no expected digests"]
    projection = observation.projection
    if expected.image_sha256 != image_sha256:
        return [f"the recipe's expected digests were measured on image {expected.image_sha256} "
                f"and this image is {image_sha256}: refresh them from a reviewed run"]
    findings: list[str] = []
    if observation.console_sha256 != expected.console_sha256:
        findings.append(f"console digest {observation.console_sha256} against the recipe's "
                        f"{expected.console_sha256}")
    if (projection.event_sha256 != expected.event_sha256
            or len(projection.events) != expected.events):
        findings.append(f"event digest {projection.event_sha256} over {len(projection.events)} "
                        f"events against the recipe's {expected.event_sha256} over "
                        f"{expected.events}")
    if (projection.trace_digest != expected.trace_digest
            or projection.retired != expected.retired):
        findings.append(f"commit trace {projection.trace_digest} over {projection.retired} "
                        f"retired instructions against the recipe's {expected.trace_digest} "
                        f"over {expected.retired}")
    return findings


def expected_block(observation: Observation, image_sha256: str) -> dict[str, object]:
    projection = observation.projection
    return {"image_sha256": image_sha256,
            "console_sha256": observation.console_sha256,
            "event_sha256": projection.event_sha256,
            "events": len(projection.events),
            "trace_digest": projection.trace_digest,
            "retired": projection.retired}


def refresh_expected(root: Path, recipe: Recipe, block: dict[str, object]) -> bool:
    """Write a run's digests into the recipe's `expected` block; True where they moved.

    Every other field is left as it was, on `differential.rewrite`'s ground: a recipe
    declares, and only the measured block is the run's to rewrite.
    """
    path = root / recipe.path
    before = path.read_text(encoding="utf-8")
    raw = cast("dict[str, object]", json.loads(before))
    raw["expected"] = block
    text = json.dumps(raw, indent=2) + "\n"
    if text == before:
        return False
    path.write_text(text, encoding="utf-8", newline="\n")
    return True
