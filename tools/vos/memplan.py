# SPDX-License-Identifier: Apache-2.0
"""The memory plan's placement problem, read out of MemoryPlan.v, and an exact check over it.

[proofs/MemoryPlan.v](../../proofs/MemoryPlan.v) is M1.9's statement artifact: the
`Plan` record every composition magnitude is a field of, the boolean checks the
register's memory-plan obligations decide by, and one demo plan instantiating them
with witness values. Q5 wants that problem as structured data a search can read and an
exact check every proposed placement is re-admitted by, and this module is both halves,
on two rules the plan states.

**One owner.** Every figure here is read out of the `.v` and none is typed in: the
`Definition demo_* : list ...` lists, the literal fields of `build_plan`, the
`Definition <name> : Plan := build_plan ...` applications, `placed_by_name`'s arms and
the `RegionKind` constructors. A list this reader cannot find or cannot read is
`PlanError` and never an empty roster, on the fail-closed ground the generated group
states (K-67, K-75): a regex that stops matching would otherwise yield zero regions and
a green report about nothing. `emit` writes the export K-88 holds byte-identical to what
this reader writes, so a hand edit of the artifact is a finding at the next gate and an
edit of the `.v` that this reader no longer follows is a raise at the same gate.

**The check is a port and it admits nothing.** Each predicate below is one Gallina
definition of the `.v`, named in its docstring, re-implemented over Python integers so
that a placement the enumerator proposes is decided by arithmetic the search's own
objective never touches. The plan's item says what that port is: development hygiene,
with the proof status staying with the `.v`. Nothing here is evidence about the
machine, and the `.v`'s own refutation variants are what the tests hold this port to,
so a port that drifted from the file would disagree with a plan the file refutes.

**What the search may move, and what it may not.** A candidate placement moves slot
bases alone. The roster, the kinds, the cycle-criticality judgment, the class
assignment, the lengths, the live ranges, the island map, the fetch counts and the
charged slots are the plan's own fields and stay where the `.v` declares them, because
the item's own text makes a cross-owner borrowing or a new shared-lifetime assumption
an architecture change taken elsewhere, and because the class is the register's
placement rather than a degree of freedom (R-15-247s, `register_place`).

**What the port takes of R-08-014.** The `.v` reads that entry's side condition as slot
disjointness over *overlapping* live ranges (its reading 7) and reports the entry's own
word *disjoint* as an inversion it owes to the register; the literal reading refuses the
mechanism the plan exists to use. `colouring_ok` below is the file's reading, so the
enumerator shares a slot exactly where `live_overlap` is false, and `literal_colouring_ok`
is carried beside it only so that a test can show the two answer opposite ways on the
same two plans the file shows it on.
"""

import dataclasses
import hashlib
import json
import math
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# The one owner, the artifact it is exported to, and the command that rewrites it.
SOURCE = "proofs/MemoryPlan.v"
ARTIFACT = "tools/generated/memory-plan.json"
REPAIR = "python tools/run.py placement export"

# The plan the `.v` names as the specification's own instance, and the one this export
# carries whole. Every other `: Plan :=` definition is a variant moving one declared
# quantity and is carried by name and by the lists it is built from.
STANDING = "demo_plan"

# The two class constructors, spelled as the `.v` spells them. They are the register's
# two static latency classes (R-15-247) and the file's own comment says there is no
# third constructor, so a third one arriving here is a reader that has stopped reading.
FIRST = "FirstClass"
SECOND = "SecondClass"

# The record fields `build_plan` fixes as literals rather than as arguments or lists. A
# `Plan` field outside this set and outside the list-backed set is a shape the reader
# refuses, so a field added to the record arrives as a raise here and not as a silent
# omission from the export.
LITERAL_FIELDS = ("region_count", "first_fetch", "fixed_first_class", "first_budget")

# The fields the demo plan does *not* carry and the item's export list names. Each is
# declared absent by name rather than invented, and which artifact owes it is stated
# beside it so that a reader knows where the field would come from.
ABSENT: dict[str, str] = {
    "owner": "no Plan field names the compartment or line item a region belongs to; "
             "R-08-045's charge is read over `placed` as a list of region indices",
    "bank": "no Plan field names a bank; R-15-228a makes the bank/macro/tier-to-island "
            "map an input to the plan, and the plan reads it only as `island_of`, "
            "`island_base` and `island_span`",
    "reserved_size": "no Plan field states a reservation apart from `length_of`; a "
                     "region's slot is exactly its length",
    "slot_bound": "the timing limit of the frame slot a region's code runs in is "
                  "CyclicExecutive.v's `Frame`, read by `slot_indices_held` against a "
                  "frame's slot count and carried by the plan only as `slot_of`",
}

# Which Gallina definition each check ports, and the register entry each decides for.
# Names, so that the export cites and restates nothing; the sites are the `.v`'s own.
CONSTRAINTS: tuple[tuple[str, str], ...] = (
    ("containment_ok", "R-08-012c"),
    ("colouring_ok", "R-08-014"),
    ("slot_bases_quantized", "R-15-007k"),
    ("slot_lengths_quantized", "R-15-007k"),
    ("plan_ok", "R-08-045"),
    ("places_ok", "R-15-247s"),
    ("slot_indices_held", "R-15-247j"),
    ("pool_fits", "R-14-010"),
)


class PlanError(ValueError):
    """The `.v` does not carry what this reader reads out of it, in the shape it reads.

    A `ValueError` so that the generated group's host reading catches it as that rule's
    finding rather than as that rule's crash.
    """


# ---------------------------------------------------------------------------------
# the reader
# ---------------------------------------------------------------------------------

_LIST_RE = re.compile(
    r"^Definition (?P<name>\w+) : list (?P<kind>nat|bool|RegionKind) :=\s*"
    r"(?P<body>[^.]*)\.", re.MULTILINE)
_INDUCTIVE_RE = re.compile(
    r"^Inductive RegionKind : Type :=\s*(?P<body>.*?)\.\s*$", re.MULTILINE | re.DOTALL)
_ARM_RE = re.compile(r"^\| (\w+)", re.MULTILINE)
_PLACED_RE = re.compile(
    r"^Definition placed_by_name \(k : RegionKind\) : option MemClass :=\s*"
    r"match k with\s*(?P<body>.*?)\s*end\.", re.MULTILINE | re.DOTALL)
_PLACED_ARM_RE = re.compile(r"\| (\w+) => (Some (\w+)|None)")
_CRITERION_RE = re.compile(
    r"^Definition criterion_class \(critical : bool\) : MemClass :=\s*"
    r"if critical then (\w+) else (\w+)\.", re.MULTILINE)
_BUILD_RE = re.compile(
    r"^Definition build_plan \((?P<params>[\w ]+) : list nat\)\s*"
    r"\((?P<second>\w+) : nat\) : Plan := \{\|(?P<body>.*?)\|\}\.",
    re.MULTILINE | re.DOTALL)
_FIELD_RE = re.compile(r"(\w+) := ([^;]+?)\s*(?:;|$)", re.DOTALL)
_AT_LIST_RE = re.compile(r"^fun (\w+) => at_list (\w+) \1 (\w+)$")
_OF_RE = re.compile(
    r"^Definition (?P<name>\w+) \(r : nat\) : (?P<kind>\w+) := "
    r"at_list (?P<list>\w+) r (?P<default>\w+)\.", re.MULTILINE)
_CLASS_OF_RE = re.compile(
    r"^Definition (?P<name>\w+) \(r : nat\) : MemClass :=\s*"
    r"match placed_by_name \((?P<kind>\w+) r\) with\s*\| Some c => c\s*"
    r"\| None => criterion_class \((?P<critical>\w+) r\)\s*end\.", re.MULTILINE)
_PLAN_RE = re.compile(
    r"^Definition (?P<name>\w+) : Plan :=\s*build_plan (?P<args>[\w\s]+?)\.",
    re.MULTILINE)


def _cons(body: str, name: str) -> list[str] | None:
    """The members of one `cons x (cons y ... nil)` chain, as the tokens spelling them.

    Read by walking the chain rather than by collecting every token, so a body that
    opens as a chain and is not one is refused instead of being read as whichever
    tokens it happens to carry: the count of `cons` is the count of members and the
    chain ends in `nil`. A body that is no chain at all, `app` of two lists being the
    `.v`'s one such shape, answers `None` and is left unread; whether an unread list
    mattered is decided where `build_plan` is resolved against the lists found.
    """
    tokens = re.findall(r"[A-Za-z_]\w*|\d+", body)
    if not tokens or tokens[0] not in ("cons", "nil"):
        return None
    members: list[str] = []
    while tokens and tokens[0] == "cons":
        if len(tokens) < 2:
            raise PlanError(f"{SOURCE}'s {name} ends inside a `cons`")
        members.append(tokens[1])
        tokens = tokens[2:]
    if tokens != ["nil"]:
        raise PlanError(f"{SOURCE}'s {name} is not a `cons` chain ending in `nil`")
    return members


def _nat(word: str, where: str) -> int:
    if not word.isdigit():
        raise PlanError(f"{SOURCE}'s {where} carries `{word}` where a numeral is read")
    return int(word)


def _bool(word: str, where: str) -> bool:
    if word not in ("true", "false"):
        raise PlanError(f"{SOURCE}'s {where} carries `{word}` where a boolean is read")
    return word == "true"


@dataclass(frozen=True)
class Source:
    """What the `.v` states, as this reader found it: every typed list, the region
    kinds, the register's placement of each, the criterion, `build_plan`'s shape and
    every plan built from it."""

    md5: str
    kinds: tuple[str, ...]
    placed_by_name: dict[str, str | None]
    criterion: tuple[str, str]
    nat_lists: dict[str, tuple[int, ...]]
    bool_lists: dict[str, tuple[bool, ...]]
    kind_lists: dict[str, tuple[str, ...]]
    # the typed lists whose body is no `cons` chain, left unread and named
    unread: tuple[str, ...]
    literals: dict[str, int]
    # `Plan` field -> the list-backed reading: (kind, list or parameter name, default)
    fields: dict[str, tuple[str, str, str]]
    params: tuple[str, ...]
    second: str
    class_field: str
    plans: dict[str, tuple[tuple[str, ...], int]]


def read(root: Path) -> Source:
    """The `.v` as a `Source`, failing closed at every shape this reader depends on."""
    path = root / SOURCE
    if not path.is_file():
        raise PlanError(f"{SOURCE} is not in this checkout")
    raw = path.read_bytes()
    return parse(raw.decode("utf-8"), hashlib.md5(raw, usedforsecurity=False).hexdigest())


def parse(text: str, md5: str = "") -> Source:
    """`read` over text already in hand, so a test can hand it a shape and watch it
    refuse."""
    inductive = _INDUCTIVE_RE.search(text)
    if inductive is None:
        raise PlanError(f"{SOURCE} no longer states `RegionKind` as an inductive this "
                        f"reader can read")
    kinds = tuple(_ARM_RE.findall(inductive.group("body")))
    if not kinds:
        raise PlanError(f"{SOURCE}'s `RegionKind` carries no constructor")

    placed = _PLACED_RE.search(text)
    if placed is None:
        raise PlanError(f"{SOURCE} no longer states `placed_by_name` as a match over "
                        f"`RegionKind`")
    placement: dict[str, str | None] = {}
    for kind, _, cls in _PLACED_ARM_RE.findall(placed.group("body")):
        if kind not in kinds:
            raise PlanError(f"{SOURCE}'s `placed_by_name` names `{kind}`, which is no "
                            f"`RegionKind` constructor")
        if cls and cls not in (FIRST, SECOND):
            raise PlanError(f"{SOURCE}'s `placed_by_name` places `{kind}` on `{cls}`, "
                            f"which is neither class")
        placement[kind] = cls or None
    if set(placement) != set(kinds):
        raise PlanError(f"{SOURCE}'s `placed_by_name` decides "
                        f"{len(placement)} of {len(kinds)} region kinds")

    criterion = _CRITERION_RE.search(text)
    if criterion is None:
        raise PlanError(f"{SOURCE} no longer states `criterion_class` as one `if`")
    if {criterion.group(1), criterion.group(2)} != {FIRST, SECOND}:
        raise PlanError(f"{SOURCE}'s `criterion_class` answers with something other "
                        f"than the two classes")

    nat_lists: dict[str, tuple[int, ...]] = {}
    bool_lists: dict[str, tuple[bool, ...]] = {}
    kind_lists: dict[str, tuple[str, ...]] = {}
    unread: list[str] = []
    for m in _LIST_RE.finditer(text):
        name, kind = m.group("name"), m.group("kind")
        members = _cons(m.group("body"), name)
        if members is None:
            unread.append(name)
            continue
        if kind == "nat":
            nat_lists[name] = tuple(_nat(t, name) for t in members)
        elif kind == "bool":
            bool_lists[name] = tuple(_bool(t, name) for t in members)
        else:
            for t in members:
                if t not in kinds:
                    raise PlanError(f"{SOURCE}'s {name} carries `{t}`, which is no "
                                    f"`RegionKind` constructor")
            kind_lists[name] = tuple(members)

    build = _BUILD_RE.search(text)
    if build is None:
        raise PlanError(f"{SOURCE} no longer states `build_plan` as a record literal "
                        f"over list parameters and one constant")
    params = tuple(build.group("params").split())
    second = build.group("second")
    ofs = {m.group("name"): (m.group("kind"), m.group("list"), m.group("default"))
           for m in _OF_RE.finditer(text)}
    class_ofs = {m.group("name"): (m.group("kind"), m.group("critical"))
                 for m in _CLASS_OF_RE.finditer(text)}

    literals: dict[str, int] = {}
    fields: dict[str, tuple[str, str, str]] = {}
    class_field = ""
    for name, raw_rhs in _FIELD_RE.findall(build.group("body")):
        rhs = " ".join(raw_rhs.split())
        if name in LITERAL_FIELDS:
            literals[name] = _nat(rhs, f"build_plan's {name}")
            continue
        if name == "second_fetch":
            if rhs != second:
                raise PlanError(f"{SOURCE}'s build_plan fixes second_fetch to `{rhs}` "
                                f"rather than to its `{second}` parameter")
            continue
        if name == "class_of":
            if rhs not in class_ofs:
                raise PlanError(f"{SOURCE}'s build_plan fixes class_of to `{rhs}`, "
                                f"which is not the register's placement over a kind "
                                f"list and a criticality list")
            class_field = rhs
            continue
        at = _AT_LIST_RE.match(rhs)
        if at is not None:
            fields[name] = ("nat", at.group(2), at.group(3))
        elif rhs in ofs:
            fields[name] = ofs[rhs]
        elif rhs in nat_lists:
            fields[name] = ("list", rhs, "")
        else:
            raise PlanError(f"{SOURCE}'s build_plan fixes `{name}` to `{rhs}`, a shape "
                            f"this reader does not read")
    for name in LITERAL_FIELDS:
        if name not in literals:
            raise PlanError(f"{SOURCE}'s build_plan states no literal `{name}`")
    if not class_field:
        raise PlanError(f"{SOURCE}'s build_plan states no `class_of`")
    for name, (_, source, _) in fields.items():
        if source not in params and source not in nat_lists \
                and source not in bool_lists and source not in kind_lists:
            raise PlanError(f"{SOURCE}'s build_plan reads `{name}` from `{source}`, "
                            f"which is neither a parameter nor a list this reader found")

    plans: dict[str, tuple[tuple[str, ...], int]] = {}
    for m in _PLAN_RE.finditer(text):
        args = m.group("args").split()
        if len(args) != len(params) + 1:
            raise PlanError(f"{SOURCE}'s {m.group('name')} applies build_plan to "
                            f"{len(args)} arguments where it takes {len(params) + 1}")
        for arg in args[:-1]:
            if arg not in nat_lists:
                raise PlanError(f"{SOURCE}'s {m.group('name')} names `{arg}`, which is "
                                f"no `list nat` this reader found")
        plans[m.group("name")] = (tuple(args[:-1]), _nat(args[-1], m.group("name")))
    if STANDING not in plans:
        raise PlanError(f"{SOURCE} no longer builds `{STANDING}` from build_plan")

    return Source(md5=md5, kinds=kinds, placed_by_name=placement,
                  criterion=(criterion.group(1), criterion.group(2)),
                  nat_lists=nat_lists, bool_lists=bool_lists, kind_lists=kind_lists,
                  unread=tuple(unread), literals=literals, fields=fields,
                  params=params, second=second, class_field=class_field, plans=plans)


# ---------------------------------------------------------------------------------
# the plan, as the `.v`'s `Plan` record with its `at_list` fallbacks
# ---------------------------------------------------------------------------------

def at_list[T](members: tuple[T, ...], index: int, default: T) -> T:
    """`at_list` (MemoryPlan.v): the nth member, or the declared fallback past the end."""
    return members[index] if 0 <= index < len(members) else default


@dataclass(frozen=True)
class Plan:
    """One `Plan` of the `.v`, every field a tuple read from a list or a literal.

    A field is read through the accessor of its name below, which carries the `.v`'s
    own `at_list` fallback, so that a region outside a list declares the fallback rather
    than raising, exactly as the record does.
    """

    name: str
    region_count: int
    kinds: tuple[str, ...]
    critical: tuple[bool, ...]
    lengths: tuple[int, ...]
    bases: tuple[int, ...]
    live_starts: tuple[int, ...]
    live_ends: tuple[int, ...]
    base_granules: tuple[int, ...]
    length_granules: tuple[int, ...]
    islands: tuple[int, ...]
    island_bases: tuple[int, ...]
    island_spans: tuple[int, ...]
    first_fetch: int
    second_fetch: int
    fetch_counts: tuple[int, ...]
    slots: tuple[int, ...]
    placed: tuple[int, ...]
    origin_regions: tuple[int, ...]
    fixed_first_class: int
    first_budget: int
    placed_by_name: dict[str, str | None] = field(default_factory=dict, compare=False)
    criterion: tuple[str, str] = (FIRST, SECOND)
    kind_default: str = "ModelWeights"

    def kind_of(self, r: int) -> str:
        return at_list(self.kinds, r, self.kind_default)

    def cycle_critical(self, r: int) -> bool:
        return at_list(self.critical, r, False)

    def class_of(self, r: int) -> str:
        """`demo_class_of`: the register's placement by name, else by criterion."""
        return register_place(self, r)

    def base_of(self, r: int) -> int:
        return at_list(self.bases, r, 0)

    def length_of(self, r: int) -> int:
        return at_list(self.lengths, r, 0)

    def live_from(self, r: int) -> int:
        return at_list(self.live_starts, r, 0)

    def live_to(self, r: int) -> int:
        return at_list(self.live_ends, r, 0)

    def base_granules_of(self, r: int) -> int:
        return at_list(self.base_granules, r, 0)

    def length_granules_of(self, r: int) -> int:
        return at_list(self.length_granules, r, 0)

    def island_of(self, r: int) -> int:
        return at_list(self.islands, r, 0)

    def island_base(self, i: int) -> int:
        return at_list(self.island_bases, i, 0)

    def island_span(self, i: int) -> int:
        return at_list(self.island_spans, i, 0)

    def fetch_count(self, r: int) -> int:
        return at_list(self.fetch_counts, r, 0)

    def slot_of(self, r: int) -> int:
        return at_list(self.slots, r, 0)

    def regions(self) -> range:
        """`upto region_count`: the roster's index set."""
        return range(self.region_count)

    def island_ids(self) -> tuple[int, ...]:
        """Every island a region of the roster is placed into, in first-use order."""
        seen: dict[int, None] = {}
        for r in self.regions():
            seen.setdefault(self.island_of(r), None)
        return tuple(seen)


def _field(src: Source, name: str, args: dict[str, tuple[int, ...]],
           expect: str) -> tuple[Any, ...]:
    kind, source, _ = src.fields[name]
    if source in args:
        return args[source]
    if source in src.nat_lists:
        return src.nat_lists[source]
    if kind == "bool" and source in src.bool_lists:
        return src.bool_lists[source]
    if kind == "RegionKind" and source in src.kind_lists:
        return src.kind_lists[source]
    raise PlanError(f"{SOURCE}'s build_plan reads `{name}` from `{source}`, which is no "
                    f"{expect} list")


def plan_of(src: Source, name: str) -> Plan:
    """The named plan, built as the `.v`'s `build_plan` builds it."""
    if name not in src.plans:
        raise PlanError(f"{SOURCE} builds no plan named `{name}`")
    arg_names, second = src.plans[name]
    args = {p: src.nat_lists[a] for p, a in zip(src.params, arg_names, strict=True)}
    wanted = ("kind_of", "cycle_critical", "base_of", "length_of", "live_from",
              "live_to", "base_granules", "length_granules_of", "island_of",
              "island_base", "island_span", "fetch_count", "slot_of", "placed",
              "origin_regions")
    for want in wanted:
        if want not in src.fields:
            raise PlanError(f"{SOURCE}'s build_plan states no `{want}`")
    kinds = _field(src, "kind_of", args, "kind")
    kind_default = src.fields["kind_of"][2]
    if kind_default not in src.kinds:
        raise PlanError(f"{SOURCE}'s kind_of falls back to `{kind_default}`, which is "
                        f"no `RegionKind` constructor")
    return Plan(
        name=name,
        region_count=src.literals["region_count"],
        kinds=tuple(kinds),
        critical=tuple(_field(src, "cycle_critical", args, "bool")),
        lengths=tuple(_field(src, "length_of", args, "nat")),
        bases=tuple(_field(src, "base_of", args, "nat")),
        live_starts=tuple(_field(src, "live_from", args, "nat")),
        live_ends=tuple(_field(src, "live_to", args, "nat")),
        base_granules=tuple(_field(src, "base_granules", args, "nat")),
        length_granules=tuple(_field(src, "length_granules_of", args, "nat")),
        islands=tuple(_field(src, "island_of", args, "nat")),
        island_bases=tuple(_field(src, "island_base", args, "nat")),
        island_spans=tuple(_field(src, "island_span", args, "nat")),
        first_fetch=src.literals["first_fetch"],
        second_fetch=second,
        fetch_counts=tuple(_field(src, "fetch_count", args, "nat")),
        slots=tuple(_field(src, "slot_of", args, "nat")),
        placed=tuple(_field(src, "placed", args, "nat")),
        origin_regions=tuple(_field(src, "origin_regions", args, "nat")),
        fixed_first_class=src.literals["fixed_first_class"],
        first_budget=src.literals["first_budget"],
        placed_by_name=dict(src.placed_by_name),
        criterion=src.criterion,
        kind_default=kind_default,
    )


def with_bases(plan: Plan, bases: dict[int, int]) -> Plan:
    """The same plan with some regions' slot bases moved and nothing else.

    The declared granule count moves with each base, as the `.v`'s own variant plans
    move `shared_base_granules` beside `shared_bases`: a base is stated as the count of
    its region's granules, and `base_is_quantized` multiplies that count back rather
    than dividing, so a base that is no whole number of granules is refused there and
    not rounded here (reading 8 of the `.v`).
    """
    new_bases = list(plan.bases)
    new_granules = list(plan.base_granules)
    for r, base in bases.items():
        while len(new_bases) <= r:
            new_bases.append(0)
        while len(new_granules) <= r:
            new_granules.append(0)
        new_bases[r] = base
        new_granules[r] = base // granule_of(plan, r)
    return dataclasses.replace(plan, bases=tuple(new_bases),
                               base_granules=tuple(new_granules))


# ---------------------------------------------------------------------------------
# the exact check: one Gallina definition per function, over Python integers
# ---------------------------------------------------------------------------------

def register_place(plan: Plan, r: int) -> str:
    """`register_place`: the class the register puts a region's kind on by name, and
    where it names none, `criterion_class` over the plan's own cycle-criticality
    judgment (reading 4 of the `.v`)."""
    kind = plan.kind_of(r)
    if kind not in plan.placed_by_name:
        raise PlanError(f"region {r}'s kind `{kind}` is one `placed_by_name` decides "
                        f"nothing about")
    named = plan.placed_by_name[kind]
    if named is not None:
        return named
    return plan.criterion[0] if plan.cycle_critical(r) else plan.criterion[1]


def places_ok(plan: Plan) -> bool:
    """`places_ok` over the plan's own `class_of`, which for a plan built by
    `build_plan` is the register's placement and so holds by construction."""
    return all(plan.class_of(r) == register_place(plan, r) for r in plan.regions())


def granule_exponent(length: int) -> int:
    """`granule_exponent` with the length as its own fuel: step while 2^6 times the
    next power of two still fits inside the length, and stop where it does not.

    The `.v` recurses `length` times and the exponent stops moving the first time the
    step refuses, since a refused step leaves it where it was and the test is the same
    at the next step; the loop below leaves at that point, which is the same value
    the fuel would have reached.
    """
    e = 0
    for _ in range(length):
        if 64 * (2 * (1 << e)) <= length:
            e += 1
        else:
            break
    return e


def representable_granule(length: int) -> int:
    """`representable_granule`: byte-exact to 128 bytes, above it the coarsest power of
    two whose 2^6 multiple still fits inside the length (R-15-007c)."""
    return 1 if length <= 128 else 1 << granule_exponent(length)


def granule_of(plan: Plan, r: int) -> int:
    """`granule_of`: the region's own representable granule."""
    return representable_granule(plan.length_of(r))


def base_is_quantized(plan: Plan, r: int) -> bool:
    """`base_is_quantized`: the declared granule count multiplied back is the base."""
    return granule_of(plan, r) * plan.base_granules_of(r) == plan.base_of(r)


def length_is_quantized(plan: Plan, r: int) -> bool:
    """`length_is_quantized`: the declared granule count multiplied back is the length."""
    return granule_of(plan, r) * plan.length_granules_of(r) == plan.length_of(r)


def slot_bases_quantized(plan: Plan) -> bool:
    """`slot_bases_quantized` (R-15-007k)."""
    return all(base_is_quantized(plan, r) for r in plan.regions())


def slot_lengths_quantized(plan: Plan) -> bool:
    """`slot_lengths_quantized` (R-15-007k)."""
    return all(length_is_quantized(plan, r) for r in plan.regions())


def island_lo(plan: Plan, r: int) -> int:
    """`island_lo`."""
    return plan.island_base(plan.island_of(r))


def island_hi(plan: Plan, r: int) -> int:
    """`island_hi`."""
    i = plan.island_of(r)
    return plan.island_base(i) + plan.island_span(i)


def inside_island(plan: Plan, r: int) -> bool:
    """`inside_island` over the plan's own bases (`spec_placement`)."""
    base = plan.base_of(r)
    return island_lo(plan, r) <= base and base + plan.length_of(r) <= island_hi(plan, r)


def containment_ok(plan: Plan) -> bool:
    """`containment_ok` (R-08-012c): every region inside its island at both edges."""
    return all(inside_island(plan, r) for r in plan.regions())


def live_overlap(plan: Plan, r: int, s: int) -> bool:
    """`live_overlap`: two half-open live ranges that meet."""
    return plan.live_from(r) < plan.live_to(s) and plan.live_from(s) < plan.live_to(r)


def slots_disjoint(plan: Plan, r: int, s: int) -> bool:
    """`slots_disjoint`: one slot ends at or before the other begins."""
    return (plan.base_of(r) + plan.length_of(r) <= plan.base_of(s)
            or plan.base_of(s) + plan.length_of(s) <= plan.base_of(r))


def colouring_ok(plan: Plan) -> bool:
    """`colouring_ok` (R-08-014, the `.v`'s reading 7): distinct regions whose live
    ranges overlap have disjoint slots, and nothing is asked of the rest."""
    return all(slots_disjoint(plan, r, s)
               for r in plan.regions() for s in plan.regions()
               if r != s and live_overlap(plan, r, s))


def strict_colouring_ok(plan: Plan) -> bool:
    """`strict_colouring_ok`: the reading R-08-012 excludes, disjointness outright."""
    return all(slots_disjoint(plan, r, s)
               for r in plan.regions() for s in plan.regions() if r != s)


def literal_colouring_ok(plan: Plan) -> bool:
    """`literal_colouring_ok`: R-08-014's own words, disjointness over *disjoint* live
    ranges, carried so that the inversion the `.v` reports can be shown and never
    used."""
    return all(slots_disjoint(plan, r, s)
               for r in plan.regions() for s in plan.regions()
               if r != s and not live_overlap(plan, r, s))


def each_region_once(plan: Plan, placed: tuple[int, ...]) -> bool:
    """`each_region_once` (R-08-045's arity of one)."""
    return all(placed.count(r) == 1 for r in plan.regions())


def no_stranger(plan: Plan, placed: tuple[int, ...]) -> bool:
    """`no_stranger`: nothing claimed the roster does not carry."""
    return all(r < plan.region_count for r in placed)


def plan_ok(plan: Plan, placed: tuple[int, ...] | None = None) -> bool:
    """`plan_ok` (R-08-045) over the plan's own placement list unless one is handed in."""
    listed = plan.placed if placed is None else placed
    return each_region_once(plan, listed) and no_stranger(plan, listed)


def slot_indices_held(plan: Plan, slot_count: int) -> bool:
    """`slot_indices_held` (reading 11): every charged slot is one the frame carries.
    The frame is CyclicExecutive.v's and the plan does not carry it, so its slot count
    is an argument here and the export declares the bound absent."""
    return all(plan.slot_of(r) < slot_count for r in plan.regions())


def fetch_constant(plan: Plan, cls: str) -> int:
    """`fetch_constant`: the class's own constant."""
    if cls == FIRST:
        return plan.first_fetch
    if cls == SECOND:
        return plan.second_fetch
    raise PlanError(f"`{cls}` is neither class")


def placement_delta(plan: Plan, r: int) -> int:
    """`placement_delta` (R-15-247j) over the plan's own assignment: the fetch count
    times the per-fetch difference, which truncates at zero as `nat` subtraction does
    (reading 3), so a faster second class carries no credit."""
    per_fetch = max(0, fetch_constant(plan, plan.class_of(r)) - plan.first_fetch)
    return plan.fetch_count(r) * per_fetch


def second_class_is_no_faster(plan: Plan) -> bool:
    """`SecondClassIsNoFaster`: the side condition under which the delta is faithful."""
    return plan.first_fetch <= plan.second_fetch


def bytes_on(plan: Plan, cls: str, members: tuple[int, ...]) -> int:
    """`bytes_on`: the lengths of the listed regions the assignment puts on a class."""
    return sum(plan.length_of(r) for r in members if plan.class_of(r) == cls)


def member_first_class_cost(plan: Plan) -> int:
    """`member_first_class_cost`: an origin-pool member's first-class bytes."""
    return bytes_on(plan, FIRST, plan.origin_regions)


def pool_fits(plan: Plan, population: int) -> bool:
    """`pool_fits` (R-14-010, R-18-004b): the fixed charge plus the population's
    member cost stays inside the first-class budget."""
    return (plan.fixed_first_class + population * member_first_class_cost(plan)
            <= plan.first_budget)


def refused_by(plan: Plan) -> list[str]:
    """Which of the plan's boolean checks refuse it, by the `.v`'s own names, and an
    empty list where every one admits it. The checks a placement can move come first
    and the two it cannot come after, so that a report can say which half moved."""
    checks = (
        ("containment_ok", containment_ok),
        ("colouring_ok", colouring_ok),
        ("slot_bases_quantized", slot_bases_quantized),
        ("slot_lengths_quantized", slot_lengths_quantized),
        ("plan_ok", plan_ok),
        ("places_ok", places_ok),
    )
    return [name for name, check in checks if not check(plan)]


def worst_case_timing(plan: Plan) -> int:
    """The sum of every region's placement delta: what the plan charges §11 admission
    over the whole roster. A base search leaves it where it is, the delta reading the
    class and the fetch count and never the base."""
    return sum(placement_delta(plan, r) for r in plan.regions())


# ---------------------------------------------------------------------------------
# the objectives: what a base search can and cannot move
# ---------------------------------------------------------------------------------

@dataclass(frozen=True)
class Score:
    """One island's placement, measured.

    `footprint` is the proven simultaneous peak R-08-012 collapses over-reservation
    onto: the most bytes live at once, over the live ranges and lengths, which no base
    moves. `span_used` is how far past the island's base the last slot ends,
    `unused_reservation` is that span less the footprint, and `padding` is the bytes
    under the span no slot covers at all. R-08-012a's first term is the footprint and
    it is fixed, so what a base search ranks is the span, then the padding, and the
    unused reservation moves with the span one for one.
    """

    footprint: int
    span_used: int
    unused_reservation: int
    padding: int

    def key(self) -> tuple[int, int]:
        return (self.span_used, self.padding)


def footprint(plan: Plan, regions: tuple[int, ...]) -> int:
    """The peak over time of the bytes live at once among `regions`."""
    starts = {plan.live_from(r) for r in regions}
    return max((sum(plan.length_of(r) for r in regions
                    if plan.live_from(r) <= t < plan.live_to(r)) for t in starts),
               default=0)


def score(plan: Plan, island: int) -> Score:
    """The island's `Score` under the plan's own bases."""
    regions = tuple(r for r in plan.regions() if plan.island_of(r) == island)
    base = plan.island_base(island)
    ends = [plan.base_of(r) + plan.length_of(r) for r in regions]
    span = max((end - base for end in ends), default=0)
    covered = 0
    edge = base
    for lo, hi in sorted((plan.base_of(r), plan.base_of(r) + plan.length_of(r))
                         for r in regions):
        start = max(lo, edge)
        if hi > start:
            covered += hi - start
            edge = hi
    peak = footprint(plan, regions)
    return Score(footprint=peak, span_used=span, unused_reservation=span - peak,
                 padding=span - covered)


# ---------------------------------------------------------------------------------
# the enumerator
# ---------------------------------------------------------------------------------

# The candidate-set predicate, as the report prints it. Stated once here so that the
# document describing the search and the report the tool prints cannot say two things.
PREDICATE = (
    "per island, every assignment of slot bases to that island's regions in which each "
    "base is a multiple of the region's step inside its island, the step being the "
    "least common multiple of the region's R-15-007c granule and the island's quantum, "
    "and the quantum being the greatest common divisor of the standing plan's bases in "
    "that island measured from the island's base; the other islands' regions stay at "
    "their standing bases, and islands, classes, kinds, lengths, live ranges, fetch "
    "counts and charged slots are fixed"
)


@dataclass(frozen=True)
class Candidate:
    """One placement the enumerator reached: the bases it proposes for one island's
    regions and what the exact check said of the whole plan carrying them."""

    bases: tuple[tuple[int, int], ...]
    refused: tuple[str, ...]
    score: Score | None


@dataclass(frozen=True)
class IslandSearch:
    """What one island's enumeration decided."""

    island: int
    regions: tuple[int, ...]
    quantum: int
    steps: tuple[int, ...]
    counts: tuple[int, ...]
    grid: int
    granule_grid: int
    leaves: int
    pruned: int
    feasible: int
    truncated: bool
    standing: Score
    standing_admitted: bool
    best: Candidate | None


def island_quantum(plan: Plan, regions: tuple[int, ...], island: int) -> int:
    """The coarsest grid the standing plan sits on: the gcd of its bases in the island,
    measured from the island's base. Zero, which is every base at the island's own
    base, reads as one so that the grid is every byte."""
    base = plan.island_base(island)
    q = 0
    for r in regions:
        q = math.gcd(q, plan.base_of(r) - base)
    return q or 1


def _positions(lo: int, hi: int, length: int, step: int) -> range:
    """Every base at a multiple of `step` from `lo` at which a slot of `length` still
    ends at or before `hi`."""
    if lo + length > hi:
        return range(0)
    return range(lo, hi - length + 1, step)


def enumerate_island(plan: Plan, island: int,
                     max_leaves: int | None = None) -> IslandSearch:
    """Every candidate the predicate admits for one island, each decided exactly.

    Regions are placed in roster order. A prefix the pairwise check refuses is pruned,
    and the grid points under it are counted as decided, since no completion of a
    refused pair passes `colouring_ok`: the pair test is the `.v`'s own `live_overlap`
    and `slots_disjoint` applied to the two regions alone, read here off local arrays
    so that the walk over a large grid is not paid in method calls. Every leaf is a
    whole plan, the other islands held at their standing bases, and it is admitted or
    refused by `refused_by` alone: the objective ranks what that check admitted and
    never decides admission.
    """
    regions = tuple(r for r in plan.regions() if plan.island_of(r) == island)
    lo, hi = plan.island_base(island), plan.island_base(island) + plan.island_span(island)
    quantum = island_quantum(plan, regions, island)
    steps = tuple(math.lcm(quantum, granule_of(plan, r)) for r in regions)
    counts = tuple(len(_positions(lo, hi, plan.length_of(r), step))
                   for r, step in zip(regions, steps, strict=True))
    grid = math.prod(counts) if regions else 0
    granule_grid = math.prod(
        len(_positions(lo, hi, plan.length_of(r), granule_of(plan, r)))
        for r in regions) if regions else 0
    standing = score(plan, island)
    standing_admitted = not refused_by(plan)

    lengths = [plan.length_of(r) for r in regions]
    overlaps = [[live_overlap(plan, r, s) for s in regions] for r in regions]
    positions = [_positions(lo, hi, lengths[i], steps[i]) for i in range(len(regions))]
    depth_count = len(regions)

    leaves = pruned = feasible = 0
    truncated = False
    best: Candidate | None = None
    chosen: list[int] = [0] * depth_count

    def below(depth: int) -> int:
        return math.prod(counts[depth:]) if depth < depth_count else 1

    def walk(depth: int) -> None:
        nonlocal leaves, pruned, feasible, truncated, best
        if depth == depth_count:
            leaves += 1
            placed = dict(zip(regions, chosen, strict=True))
            candidate = with_bases(plan, placed)
            refused = tuple(refused_by(candidate))
            found = Candidate(bases=tuple(sorted(placed.items())), refused=refused,
                              score=None if refused else score(candidate, island))
            if not refused:
                feasible += 1
                if best is None or best.score is None or found.score is None \
                        or found.score.key() < best.score.key():
                    best = found
            if max_leaves is not None and leaves >= max_leaves:
                truncated = True
            return
        length = lengths[depth]
        overlap = overlaps[depth]
        for base in positions[depth]:
            end = base + length
            ok = True
            for j in range(depth):
                if overlap[j]:
                    other = chosen[j]
                    if not (end <= other or other + lengths[j] <= base):
                        ok = False
                        break
            if not ok:
                pruned += below(depth + 1)
                continue
            chosen[depth] = base
            walk(depth + 1)
            if truncated:
                return

    if regions:
        walk(0)
    return IslandSearch(island=island, regions=regions, quantum=quantum, steps=steps,
                        counts=counts, grid=grid, granule_grid=granule_grid,
                        leaves=leaves, pruned=pruned, feasible=feasible,
                        truncated=truncated, standing=standing,
                        standing_admitted=standing_admitted, best=best)


def search(plan: Plan, max_leaves: int | None = None) -> Iterator[IslandSearch]:
    """One `IslandSearch` per island the plan places into, in the plan's order."""
    for island in plan.island_ids():
        yield enumerate_island(plan, island, max_leaves)


# ---------------------------------------------------------------------------------
# the export
# ---------------------------------------------------------------------------------

def _region(plan: Plan, r: int) -> dict[str, Any]:
    return {
        "index": r,
        "kind": plan.kind_of(r),
        "cycle_critical": plan.cycle_critical(r),
        "class": plan.class_of(r),
        "base": plan.base_of(r),
        "length": plan.length_of(r),
        "live_from": plan.live_from(r),
        "live_to": plan.live_to(r),
        "granule": granule_of(plan, r),
        "base_granules": plan.base_granules_of(r),
        "length_granules": plan.length_granules_of(r),
        "island": plan.island_of(r),
        "fetch_count": plan.fetch_count(r),
        "slot": plan.slot_of(r),
        "placement_delta": placement_delta(plan, r),
    }


def export(src: Source) -> dict[str, Any]:
    """The placement problem as data: the standing plan whole, every variant by the
    lists it is built from, the fields the plan does not carry, and the checks by the
    entry each decides for."""
    plan = plan_of(src, STANDING)
    islands = [{"id": i, "base": plan.island_base(i), "span": plan.island_span(i)}
               for i in plan.island_ids()]
    variants = {
        name: {**dict(zip(src.params, args, strict=True)), src.second: second}
        for name, (args, second) in src.plans.items() if name != STANDING
    }
    return {
        "header": {
            "generator": "vos.memplan",
            "version": 1,
            "source": SOURCE,
            "source_md5": src.md5,
            "standing": STANDING,
            "lists_read": sorted([*src.nat_lists, *src.bool_lists, *src.kind_lists]),
            "lists_unread": sorted(src.unread),
            "literals_read": dict(src.literals),
            "plans_read": len(src.plans),
        },
        "plan": {
            "name": plan.name,
            "region_count": plan.region_count,
            "first_fetch": plan.first_fetch,
            "second_fetch": plan.second_fetch,
            "fixed_first_class": plan.fixed_first_class,
            "first_budget": plan.first_budget,
            "placed": list(plan.placed),
            "origin_regions": list(plan.origin_regions),
            "islands": islands,
            "regions": [_region(plan, r) for r in plan.regions()],
            "worst_case_timing": worst_case_timing(plan),
        },
        "variants": variants,
        "absent": dict(ABSENT),
        "constraints": [{"check": check, "entry": entry} for check, entry in CONSTRAINTS],
    }


def render(problem: dict[str, Any]) -> str:
    """The export as the bytes the artifact carries: one key per line at the top, the
    regions one per line, LF throughout."""
    return json.dumps(problem, indent=1) + "\n"


def emit(root: Path) -> str:
    """The whole artifact, from the `.v` alone."""
    return render(export(read(root)))
