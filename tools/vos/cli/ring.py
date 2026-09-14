#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Emit the ring contract's generated interface artifact from its two owners.

    tools/run.py ring emit    # writes proofs/RingContract.v
    tools/run.py ring check   # re-emits and compares, byte for byte

The typed IDL profile's section 4.3 says the common ring schema and lifecycle are
content of the wire-format mapping, and that a ring-bearing declaration is compiled
to a generated interface artifact carrying three parts: the Coq interface skeleton,
the composition-time constants, and the conformance campaign. This is the compiler
for the one part of that pipeline a Gallina front can emit today.

**Two owners, and neither is this file.** The declaration
[interfaces/ring-reference.json](../../../interfaces/ring-reference.json) owns
everything a composition fixes. The register owns the two closed enumerations the
artifact carries, R-12-093's status set and R-12-094's lifecycle states, plus
R-12-095's full-ring result and R-12-097's cancellation answers; those are read out
of the register's own entry lines rather than transcribed here, so a member added at
either entry moves the artifact's bytes and a generator carrying its own copy of a
list the register states is the defect this arrangement exists to prevent.

**The declaration carries worlds and the artifact carries one block apiece.** A
Gallina file has one top-level scope, and two worlds each declaring an `op` cannot
both hold it, so the first world the declaration lists is emitted at the file's own
scope and every further world inside a module named from its own world name. That
order is the declaration's: moving a world moves the artifact, and the artifact's
consumers, [CopyRingService.v](../../../proofs/CopyRingService.v) and
[DescriptorCheck.v](../../bedrock2-lowering/DescriptorCheck.v), name the file-scope
world's constants unqualified. Every block is emitted by this one function of the
declaration, so a world states its own campaign at its own constants and no bound is
authored twice.

**The DMA clauses are a world's declaration and not a second campaign.** A world
declaring `dma` gets part 4, which is R-12-100 read at the artifact: the permission
each declared direction requires of the session-table capability, the complete extent
validated before the transfer starts and never reinterpreted after, one validation
charged per declared segment, and R-12-099's *old capabilities dead* as a hold that
ends at terminal completion, held beside a hold that ends at reclamation and fails.
A world declaring no `dma` carries none of it, which is what makes part 4 the
difference between the two worlds rather than a restatement of the first.

**What the artifact is not.** It is not a proof of the ring contract: the campaign is
a set of obligations decided by computation over the declared constants, which is the
fail-closed reading of R-18-037's *no interface world declaring rings is admitted
before its campaign runs*. A declaration whose constants break an obligation fails to
compile the artifact. The canonical SPSC and typestate proofs that entry also names are
not here and are not claimed, and neither is its lost-wakeup exclusion over the ring's
memory: the artifact carries R-12-096's decision rule over two reads of the producer
index, held to the exclusion beside a consumer that skips the recheck and fails it, so
the exclusion is a property one rule satisfies and another does not rather than one
rule's body unfolded. Nothing here reaches the machine: whether an engine presents its
capability to the fabric is a run's answer over a second bus initiator, and this model
has one hart.
"""

import argparse
import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict, cast

from vos import corpus as corpus_mod
from vos.cli import Table, dispatch
from vos.jsonc import Json
from vos.register import Register, read_register

if TYPE_CHECKING:
    from jsonschema.protocols import Validator

DECLARATION = "interfaces/ring-reference.json"
ARTIFACT = "proofs/RingContract.v"

STATUS_ENTRY = "R-12-093"
LIFECYCLE_ENTRY = "R-12-094"
FULL_RING_ENTRY = "R-12-095"
CANCEL_ENTRY = "R-12-097"

# The register entries this artifact is generated from, named once so the rule that
# holds the artifact can say how many owners it read rather than counting them again.
OWNED_ENTRIES: tuple[str, ...] = (STATUS_ENTRY, LIFECYCLE_ENTRY, FULL_RING_ENTRY,
                                  CANCEL_ENTRY)

# The two entries part 4 states in its own comments. They are cited rather than read:
# every figure part 4 carries is the declaration's, so neither is an owner this file
# parses and neither belongs in OWNED_ENTRIES.
DMA_ENTRY = "R-12-100"
RESTART_ENTRY = "R-12-099"

# Required keys at the JSON boundary. Shape and scalar types are checked before
# constructing the typed records consumed by the emitter.
DECL_KEYS: tuple[str, ...] = ("worlds",)
WORLD_KEYS: tuple[str, ...] = ("world", "ring", "encoding", "label_levels",
                               "operation_record_fields", "operations",
                               "deadline_classes", "flags", "directions",
                               "content_types", "dma")
ENCODING_KEYS: tuple[str, ...] = ("request_id_bytes", "session_index_bytes",
                                  "offset_bytes", "length_bytes", "direction_bytes",
                                  "content_type_bytes", "generation_bytes",
                                  "metadata_bytes", "byte_count_bytes",
                                  "flag_set_bytes", "flag_spare_bits")
OP_KEYS: tuple[str, ...] = ("scalars", "buffer_refs", "deadline",
                            "empty_validation_claim", "labels", "record",
                            "cancellation", "refinement", "fill", "activation_slack",
                            "payload_slack", "cancellation_slack", "dma")
CANCEL_KEYS: tuple[str, ...] = ("points", "commit_index", "quiescence_bound",
                                "max_to_terminal")
RING_KEYS: tuple[str, ...] = (
    "capacity", "index_width_bytes", "index_span", "descriptor_size_bytes",
    "descriptor_alignment_bytes", "completion_size_bytes", "completion_fill",
    "max_batch_size", "session_generation", "completion_capacity", "max_accepted",
    "max_segments", "segment_max_bytes", "slot_budget")
DMA_KEYS: tuple[str, ...] = ("permissions", "direction_permission")
# Left for the literal tuple type rather than widened to `tuple[str, ...]` like its
# neighbours: the emitter reads an operation's DMA record at each of these keys, and it
# is the literal that makes each one a key of that typed record rather than a string.
# The slack members `OP_KEYS` carries are read the same way, from their own literal.
OP_DMA_KEYS = ("extent_validated_bytes", "extent_validations_before_start",
               "extent_reads_after_start", "descriptor_validation_cost",
               "segment_validation_cost", "held_capabilities")

# A declared name this file spells into Gallina. Anything else is refused rather than
# interpolated, a world name also being the module name every further world sits in.
_NAME_RE = re.compile(r"\A[a-z][a-z0-9_]*\Z")


class Scalar(TypedDict):
    width_bytes: int
    validated_at_use: bool


class Labels(TypedDict):
    confidentiality: int
    integrity: int


class Cancellation(TypedDict):
    points: int
    commit_index: int
    quiescence_bound: int
    max_to_terminal: int


class OpDma(TypedDict):
    extent_validated_bytes: int
    extent_validations_before_start: int
    extent_reads_after_start: int
    descriptor_validation_cost: int
    segment_validation_cost: int
    held_capabilities: int


class Dma(TypedDict):
    permissions: list[str]
    direction_permission: list[str]


class Operation(TypedDict):
    name: str
    scalars: list[Scalar]
    buffer_refs: int
    deadline: bool
    empty_validation_claim: bool
    labels: Labels
    record: list[int]
    cancellation: Cancellation | None
    refinement: list[str]
    fill: int
    activation_slack: int
    payload_slack: int
    cancellation_slack: int
    dma: OpDma | None


class World(TypedDict):
    world: str
    ring: dict[str, int]
    encoding: dict[str, int]
    label_levels: int
    operation_record_fields: list[str]
    operations: list[Operation]
    deadline_classes: list[str]
    flags: list[str]
    directions: list[str]
    content_types: list[str]
    dma: Dma | None


class Declaration(TypedDict):
    worlds: list[World]

# The register's own spellings, found where each entry states them. A backticked
# lower-case identifier is how that document writes a wire token, the arrow chain is
# how it writes an ordered lifecycle, and each of the two steps the artifact carries
# past that chain is named in the sentence of the entry that fixes it; no pattern here
# is this file's invention and every one of them fails closed below rather than
# yielding an empty enumeration or a state this file chose.
_TOKEN_RE = re.compile(r"`([a-z][a-z_]*)`")
_CLOSED_SET_RE = re.compile(r"closed common set \(([^)]*)\)")
_CHAIN_RE = re.compile(r"([A-Z][a-z]+(?: → [A-Z][a-z]+)+)")
_MALFORMED_RE = re.compile(r"moves from ([A-Z][a-z]+) directly to ([A-Z][a-z]+)")
_UNSTARTED_RE = re.compile(r"a target still ([A-Z][a-z]+)")


class RingError(Exception):
    """An owner did not carry what the emitter reads out of it."""


def _ordered(names: list[str]) -> list[str]:
    """The names in first-appearance order, each once. An entry writes one token
    twice where its sentence needs it twice, and the enumeration is still one."""
    return list(dict.fromkeys(names))


@dataclass(frozen=True)
class Owned:
    """The four enumerations the register owns, read from its own entry lines, and the
    three states its own sentences name inside two of them."""

    statuses: list[str]
    states: list[str]
    full_ring: str
    cancels: list[str]
    malformed_from: str
    malformed_to: str
    unstarted: str


def owned(register: Register) -> Owned:
    """Read the register's four enumerations, failing closed on each."""
    body = register.body

    for ident in OWNED_ENTRIES:
        if ident not in body:
            raise RingError(f"the register carries no {ident}, whose enumeration "
                            f"{ARTIFACT} is generated from")

    closed_set = _CLOSED_SET_RE.search(body[STATUS_ENTRY])
    if closed_set is None:
        raise RingError(f"{STATUS_ENTRY} no longer states a closed common set in "
                        f"parentheses, so the status enumeration cannot be read")
    statuses = _TOKEN_RE.findall(closed_set.group(1))

    chain = _CHAIN_RE.search(body[LIFECYCLE_ENTRY])
    if chain is None:
        raise RingError(f"{LIFECYCLE_ENTRY} no longer states its lifecycle as an "
                        f"arrow chain, so the state enumeration cannot be read")
    states = chain.group(1).split(" → ")

    full = _ordered(_TOKEN_RE.findall(body[FULL_RING_ENTRY]))
    if len(full) != 1:
        raise RingError(f"{FULL_RING_ENTRY} states {len(full)} wire tokens where the "
                        f"full-ring result is one")

    cancels = _ordered(_TOKEN_RE.findall(body[CANCEL_ENTRY]))
    if not statuses or not cancels:
        raise RingError("an enumeration the register owns came back empty")
    if len(cancels) < 3:
        raise RingError(f"{CANCEL_ENTRY} states {len(cancels)} cancellation answers "
                        f"where the artifact reads three, one per situation that entry "
                        f"decides")

    step = _MALFORMED_RE.search(body[LIFECYCLE_ENTRY])
    if step is None:
        raise RingError(f"{LIFECYCLE_ENTRY} no longer states its malformed step as a "
                        f"move from one named state directly to another, so the step "
                        f"the artifact carries cannot be read")
    unstarted_match = _UNSTARTED_RE.search(body[CANCEL_ENTRY])
    if unstarted_match is None:
        raise RingError(f"{CANCEL_ENTRY} no longer names the state a target is still "
                        f"in when it is cancellable unstarted, so the situation the "
                        f"artifact decides cannot be read")
    malformed_from, malformed_to = step.group(1), step.group(2)
    unstarted = unstarted_match.group(1)
    for name in (malformed_from, malformed_to, unstarted):
        if name not in states:
            raise RingError(f"the register names `{name}` as a lifecycle state where "
                            f"{LIFECYCLE_ENTRY}'s own chain does not carry it")
    if states.index(malformed_to) - states.index(malformed_from) < 2:
        raise RingError(f"{LIFECYCLE_ENTRY}'s malformed step from `{malformed_from}` to "
                        f"`{malformed_to}` skips no state, where the step it states is "
                        f"the one admitted past a successor")
    if states.index(unstarted) + 1 >= len(states):
        raise RingError(f"{CANCEL_ENTRY} names `{unstarted}` as cancellable unstarted "
                        f"where {LIFECYCLE_ENTRY}'s chain gives it no successor for a "
                        f"started target to stand in")
    return Owned(statuses=statuses, states=states, full_ring=full[0], cancels=cancels,
                 malformed_from=malformed_from, malformed_to=malformed_to,
                 unstarted=unstarted)


def _object_schema(properties: dict[str, Json], *, required: tuple[str, ...] | None = None,
                   additional: Json = True) -> dict[str, Json]:
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else list(required),
            "additionalProperties": additional}


@cache
def _declaration_validator() -> Validator:
    # Loading the existing runtime dependency is deferred until this command is used.
    # The validator and schema are built once per process, including test campaigns.
    from jsonschema import Draft202012Validator, validators  # noqa: PLC0415

    integer: Json = {"type": "integer"}
    boolean: Json = {"type": "boolean"}
    strings: Json = {"type": "array", "items": {"type": "string"}}
    scalar = _object_schema({"width_bytes": integer, "validated_at_use": boolean})
    cancellation = _object_schema(dict.fromkeys(CANCEL_KEYS, integer))
    op_dma = _object_schema(dict.fromkeys(OP_DMA_KEYS, integer))
    operation = _object_schema({
        "name": {"type": "string"},
        "scalars": {"type": "array", "items": scalar},
        "buffer_refs": integer, "deadline": boolean, "empty_validation_claim": boolean,
        "labels": _object_schema(dict.fromkeys(("confidentiality", "integrity"), integer)),
        "record": {"type": "array", "items": integer},
        "cancellation": {"anyOf": [{"type": "null"}, cancellation]},
        "dma": {"anyOf": [{"type": "null"}, op_dma]},
        "refinement": strings,
        **dict.fromkeys(("fill", "activation_slack", "payload_slack", "cancellation_slack"),
                        integer),
    }, required=("name", *OP_KEYS))
    dma = _object_schema(dict.fromkeys(DMA_KEYS, strings))
    world = _object_schema({
        "world": {"type": "string"},
        "ring": _object_schema(dict.fromkeys(RING_KEYS, integer), additional=integer),
        "encoding": _object_schema(dict.fromkeys(ENCODING_KEYS, integer), additional=integer),
        "label_levels": integer,
        "operation_record_fields": strings,
        "operations": {"type": "array", "minItems": 1, "items": operation},
        "dma": {"anyOf": [{"type": "null"}, dma]},
        **dict.fromkeys(("deadline_classes", "flags", "directions", "content_types"), strings),
    }, required=WORLD_KEYS)
    schema = _object_schema({
        "worlds": {"type": "array", "minItems": 1, "items": world},
    }, required=DECL_KEYS)
    # JSON Schema also calls 1.0 an integer. Gallina numerals and the typed records
    # need Python integers, so reject floats and bools without coercing input data.
    checker = Draft202012Validator.TYPE_CHECKER.redefine("integer", _is_integer)
    validator = validators.extend(Draft202012Validator, type_checker=checker)
    validator.check_schema(schema)
    return validator(schema)


def _is_integer(checker: object, value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _dma_agrees(world: World) -> None:
    """A world's DMA declaration against the world it is declared in.

    The permission map is one member per declared direction and each member is one of
    the permissions the same block declares, the distinction between two directions
    being what part 4's own refusal case turns on. A world declaring DMA declares it of
    every operation, and a world declaring none carries none, so the absence is a
    property of the world rather than a default this file supplies. The retained-hold
    refutation needs an operation that holds something, and a world where nothing does
    is refused rather than given a refutation over zero.
    """
    dma = world["dma"]
    name = world["world"]
    carried = [op["name"] for op in world["operations"] if op["dma"] is not None]
    if dma is None:
        if carried:
            raise RingError(f"world `{name}` declares no DMA where its operation(s) "
                            + ", ".join(f"`{op}`" for op in carried) + " declare one")
        return
    if len(carried) != len(world["operations"]):
        missing = [op["name"] for op in world["operations"] if op["dma"] is None]
        raise RingError(f"world `{name}` declares DMA where its operation(s) "
                        + ", ".join(f"`{op}`" for op in missing) + " declare none")
    for permission in dma["permissions"]:
        if not _NAME_RE.match(permission):
            raise RingError(f"world `{name}` declares the permission `{permission}`, "
                            f"which is not a name this emitter spells into Gallina")
    if len(set(dma["permissions"])) != len(dma["permissions"]) or not dma["permissions"]:
        raise RingError(f"world `{name}` declares {len(dma['permissions'])} permissions "
                        f"where the set it checks against is non-empty and each member "
                        f"is declared once")
    if len(world["directions"]) < 2:
        raise RingError(f"world `{name}` declares DMA over {len(world['directions'])} "
                        f"direction(s), where the permission check it states is a "
                        f"distinction between two")
    if not world["content_types"]:
        raise RingError(f"world `{name}` declares DMA without a content type, so its "
                        "segment campaign has no inhabited reference")
    if len(dma["direction_permission"]) != len(world["directions"]):
        raise RingError(f"world `{name}` maps {len(dma['direction_permission'])} "
                        f"permissions onto {len(world['directions'])} declared "
                        f"directions, where the map is one per direction")
    outside = [p for p in dma["direction_permission"] if p not in dma["permissions"]]
    if outside:
        raise RingError(f"world `{name}` requires the permission(s) "
                        + ", ".join(f"`{p}`" for p in outside)
                        + " of a direction, which its own declared set does not carry")
    if not any(_op_dma(op)["held_capabilities"] > 0 for op in world["operations"]):
        raise RingError(f"world `{name}` declares DMA and no operation of it holds a "
                        f"capability, so {RESTART_ENTRY}'s hold has nothing to end")


def _op_dma(op: Operation) -> OpDma:
    """An operation's DMA declaration, where `_dma_agrees` has established there is one."""
    dma = op["dma"]
    if dma is None:
        raise RingError(f"operation `{op['name']}` carries no DMA declaration")
    return dma


def declaration(root: Path) -> Declaration:
    """Validate JSON shapes once, preserving additional declaration metadata.

    Numeric relationships remain the generated conformance campaign's obligations.
    This boundary decides representation types, the record's declared width, the world
    names the artifact's scopes are spelled from, and whether a world's DMA declaration
    agrees with the world it sits in.
    """
    path = root / DECLARATION
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RingError(f"{DECLARATION} is not readable: {exc}") from exc
    try:
        loaded: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RingError(f"{DECLARATION} is not JSON: {exc}") from exc

    error = next(iter(_declaration_validator().iter_errors(loaded)), None)
    if error is not None:
        where = "/".join(str(part) for part in error.absolute_path) or "<root>"
        raise RingError(f"{DECLARATION} at {where}: {error.message}")
    # The schema checks every field the emitter reads; this cast marks that boundary.
    decl = cast("Declaration", loaded)
    seen: set[str] = set()
    scopes: set[str] = set()
    for index, world in enumerate(decl["worlds"]):
        name = world["world"]
        if not _NAME_RE.match(name):
            raise RingError(f"`{name}` is not a world name this emitter spells into a "
                            f"Gallina scope")
        if name in seen:
            raise RingError(f"world `{name}` is declared twice, where one world is one "
                            f"scope of {ARTIFACT}")
        seen.add(name)
        if index:
            scope = _module(name)
            if scope in scopes:
                raise RingError(f"world `{name}` repeats the emitted Gallina scope "
                                f"`{scope}`")
            scopes.add(scope)
        width = len(world["operation_record_fields"])
        for op in world["operations"]:
            if len(op["record"]) != width:
                raise RingError(f"operation `{op['name']}` of world `{name}` supplies "
                                f"{len(op['record'])} record values where the declared "
                                f"field set has {width}")
        _dma_agrees(world)
    return decl


def _inductive(name: str, prefix: str, members: list[str], note: str) -> list[str]:
    out = [f"(* {note} *)", f"Inductive {name} : Set :="]
    out += [f"  | {prefix}{member}" for member in members]
    out[-1] += "."
    return [*out, ""]


def _match(fn: str, arg_type: str, prefix: str, members: list[str],
           result: str, arms: list[str], binder: str = "o") -> list[str]:
    out = [f"Definition {fn} ({binder} : {arg_type}) : {result} :=",
           f"  match {binder} with"]
    out += [f"  | {prefix}{member} => {arm}"
            for member, arm in zip(members, arms, strict=True)]
    return [*out, "  end.", ""]


def _theorem(name: str, statement: str, proof: str) -> list[str]:
    return [f"Theorem {name} :", f"  {statement}", f"Proof. {proof} Qed.", ""]


def _conj(terms: list[str]) -> str:
    """A right-nested `andb` over the terms, in the declaration's own order."""
    out = terms[-1]
    for term in reversed(terms[:-1]):
        out = f"andb ({term}) ({out})"
    return out


def _skip(own: Owned) -> int:
    """How many ranks the malformed step covers: the distance, in R-12-094's own chain,
    between the two states that entry's own malformed-step sentence names. A state
    inserted between them moves this figure, which is what makes it a reading of that
    order rather than a constant read off two positions."""
    return own.states.index(own.malformed_to) - own.states.index(own.malformed_from)


def _live(own: Owned) -> str:
    """The state a cancellation answer treats as live and started: the successor, in
    R-12-094's own chain, of the state R-12-097 names a target as still in when it is
    cancellable unstarted. Which states are live to cancel is joined to that entry by
    nothing (F-217b), so the successor is this profile's reading of the join rather
    than a sentence read out of either entry; what the register does fix is the two
    ends, and both are read here."""
    return own.states[own.states.index(own.unstarted) + 1]


def _attains(ops: list[Operation], names: list[str], field: int) -> str:
    """The operation whose declared record is largest at `field`.

    A ring constant declared above every operation's use of it is a constant nothing
    constrains, so the artifact states that each declared maximum is *attained*: the
    witness is this operation, and naming it is what turns a bound into a figure a
    weakening moves.
    """
    best = max(range(len(ops)), key=lambda i: ops[i]["record"][field])
    return names[best]


def _holds_most(ops: list[Operation], names: list[str]) -> str:
    """The operation holding the most capabilities, which is the retained-hold
    refutation's witness. `_dma_agrees` has established that it holds one."""
    best = max(range(len(ops)), key=lambda i: _op_dma(ops[i])["held_capabilities"])
    return names[best]


def _module(name: str) -> str:
    """The Gallina module a world past the first is emitted into, from its own name."""
    return "".join(part.capitalize() for part in name.split("_"))


def _preamble(worlds: list[World]) -> list[str]:
    """The file header: what this artifact is, who owns it, and where each world sits."""
    first = worlds[0]["world"]
    further = [f"`{world['world']}` in module `{_module(world['world'])}`"
               for world in worlds[1:]]
    placed = (f"     `{first}` at the file's own scope"
              if not further else
              f"     `{first}` at the file's own scope, then "
              + ", then ".join(further))
    return [
        "(* SPDX-License-Identifier: Apache-2.0 *)",
        "(* =========================================================================",
        "   RingContract.v",
        "",
        "   GENERATED. No hand edit survives: `python tools/run.py ring emit` writes",
        "   this file and rule K-89 holds it byte-identical to what that command",
        "   emits from its owners. Change an owner and regenerate.",
        "",
        "   Owners:",
        f"     {DECLARATION}",
        "         everything a composition fixes: the worlds, and for each of them the",
        "         ring constants, the encoding widths, the operation set, and each",
        "         operation's declared record.",
        "     docs/requirements-register.md",
        f"         {STATUS_ENTRY}'s closed status set, {LIFECYCLE_ENTRY}'s lifecycle"
        " states,",
        f"         {FULL_RING_ENTRY}'s full-ring result, and {CANCEL_ENTRY}'s"
        " cancellation answers.",
        "",
        f"   Worlds, in the declaration's own order ({len(worlds)}):",
        placed,
        "   A Gallina file has one top-level scope and two worlds each declaring an",
        "   `op` cannot both hold it, so the first world listed takes that scope and",
        "   every further world takes a module of its own name. Each block is emitted",
        "   by one function of the declaration, so every world states the whole",
        "   campaign at its own constants and no bound is authored twice.",
        "",
        "   What this is, per the profile's section 4.3.6: the generated interface",
        "   artifact, carrying the interface skeleton, the composition-time",
        "   constants, and the conformance campaign R-18-037 requires. The campaign",
        "   is decided by computation over the declared constants, so a declaration",
        "   whose constants break an obligation fails to compile this file. The",
        "   canonical SPSC and typestate proofs that entry also names are not here",
        "   and are not claimed, and neither is its lost-wakeup exclusion over the",
        "   ring's memory: what part 3 carries of R-12-096 is its decision rule",
        "   over two reads of the producer index, held to the exclusion beside a",
        "   consumer that skips the recheck and fails it.",
        "",
        "   Nothing here is a proof about an implementation: the profile's own rule",
        "   is that its types document the contract and never are it.",
        "   ========================================================================= *)",
        "",
    ]


def _dma_part(own: Owned, world: World, names: list[str]) -> tuple[list[str], list[str]]:
    """Part 4: the DMA clauses, over this world's own declared constants.

    Returns the lines and the constants the R-05-163 gate below prints, both empty for
    a world declaring no DMA.

    Every clause here is one of R-12-100's, minus what part 2 and part 3 already carry
    of them. The bounded segment list at its fixed maximum and the payload charged
    there are above; the cleanup bound, the quiescence rule and the maximum time to
    terminal completion are above; the stale half of R-12-099's restart test is above.
    What is added is the permission the declared direction requires, the extent
    validated whole before the transfer and never again after it, the check charged per
    segment rather than per operation, and the hold that ends at terminal completion.
    """
    dma = world["dma"]
    if dma is None:
        return [], []
    ops = world["operations"]
    directions = world["directions"]
    required = dma["direction_permission"]
    live, terminal, reclaimed = _live(own), own.malformed_to, own.states[-1]

    lines: list[str] = [
        "(* -------------------------------------------------------------------------",
        f"   Part 4: the DMA clauses {DMA_ENTRY} states, at this world's own constants.",
        "   ------------------------------------------------------------------------- *)",
        "",
    ]
    lines += _inductive("permission", "perm_", dma["permissions"],
                        "the permissions a session-table capability carries on this "
                        "world's data plane")
    lines += _match("permission_rank", "permission", "perm_", dma["permissions"], "nat",
                    [str(i) for i in range(len(dma["permissions"]))], binder="p")
    lines += [
        "Definition permission_eqb (a b : permission) : bool :=",
        "  Nat.eqb (permission_rank a) (permission_rank b).",
        "",
        "Lemma permission_eqb_reflexive : forall p : permission,"
        " permission_eqb p p = true.",
        "Proof. intro p; destruct p; reflexivity. Qed.",
        "",
        f"(* The permission {DMA_ENTRY} makes the session-table capability carry, per",
        "   direction the descriptor declares. *)",
    ]
    lines += _match("direction_permission", "direction", "direction_", directions,
                    "permission", [f"perm_{name}" for name in required], binder="d")
    lines += [
        "(* The check that runs before the transfer: the granted permission against the",
        "   direction the descriptor declares, and nothing else about the descriptor. *)",
        "Definition direction_authorized (granted : permission) (d : direction) : bool :=",
        "  permission_eqb granted (direction_permission d).",
        "",
        "Definition ref_authorized (granted : permission) (b : buffer_ref) : bool :=",
        "  direction_authorized granted (ref_direction b).",
        "",
    ]

    admits: list[str] = []
    for direction, want in zip(directions, required, strict=True):
        admits.append(f"direction_authorized perm_{want} direction_{direction}")
        admits += [f"negb (direction_authorized perm_{other} direction_{direction})"
                   for other in dma["permissions"] if other != want]
    lines += _theorem(
        "the_permission_check_admits_exactly_the_declared_map",
        f"{_conj(admits)} = true.",
        "vm_compute; reflexivity.")
    distinct = [f"negb (permission_eqb (direction_permission direction_{a})"
                f" (direction_permission direction_{b}))"
                for i, a in enumerate(directions) for b in directions[i + 1:]]
    lines += _theorem(
        "every_declared_direction_requires_its_own_permission",
        f"{_conj(distinct)} = true.",
        "vm_compute; reflexivity.")
    lines += _theorem(
        "a_reference_is_authorized_by_the_direction_it_declares",
        "forall (index offset : nat) (c : content_type) (d : direction),"
        " ref_authorized (direction_permission d)"
        " (mk_buffer_ref index offset ring_segment_max_bytes d c) = true.",
        "intros index offset c d; destruct d; vm_compute; reflexivity.")

    lines += [
        "(* One checked session-table entry per segment. Bounds are relative to the",
        "   delegated capability; no raw address is carried in the descriptor. *)",
        "Record dma_segment : Set := mk_dma_segment {",
        "  segment_permission : permission;",
        "  segment_capability_bytes : nat;",
        "  segment_reference : buffer_ref",
        "}.",
        "",
        "Definition segment_valid (segment : dma_segment) : bool :=",
        "  let b := segment_reference segment in",
        "  andb (ref_authorized (segment_permission segment) b)",
        "       (Nat.leb (ref_offset b + ref_length b)",
        "                (segment_capability_bytes segment)).",
        "",
        "Fixpoint all_segments_valid (segments : list dma_segment) : bool :=",
        "  match segments with",
        "  | nil => true",
        "  | cons segment rest => andb (segment_valid segment) (all_segments_valid rest)",
        "  end.",
        "",
        "Fixpoint segment_count (segments : list dma_segment) : nat :=",
        "  match segments with nil => 0 | cons _ rest => S (segment_count rest) end.",
        "",
        "Fixpoint repeat_segment (segment : dma_segment) (count : nat)",
        "                        : list dma_segment :=",
        "  match count with",
        "  | 0 => nil",
        "  | S rest => cons segment (repeat_segment segment rest)",
        "  end.",
        "",
        "Fixpoint append_segments (prefix suffix : list dma_segment) : list dma_segment :=",
        "  match prefix with",
        "  | nil => suffix",
        "  | cons segment rest => cons segment (append_segments rest suffix)",
        "  end.",
        "",
        "Definition dma_segments_admitted (segments : list dma_segment) : bool :=",
        "  andb (Nat.leb (segment_count segments) ring_max_segments)",
        "       (all_segments_valid segments).",
        "",
        "Definition maximum_segment (d : direction) (c : content_type) : dma_segment :=",
        "  mk_dma_segment (direction_permission d) ring_segment_max_bytes",
        "    (mk_buffer_ref 0 0 ring_segment_max_bytes d c).",
        "",
        "Definition witness_dma_segment : dma_segment :=",
        f"  maximum_segment direction_{directions[0]}"
        f" content_{world['content_types'][0]}.",
        "",
    ]
    lines += _theorem(
        "the_maximum_segment_list_is_admitted",
        "forall (d : direction) (c : content_type),"
        " dma_segments_admitted (repeat_segment (maximum_segment d c) ring_max_segments)"
        " = true.",
        "intros d c; destruct d; destruct c; vm_compute; reflexivity.")
    lines += _theorem(
        "one_segment_past_the_maximum_is_refused",
        "forall (d : direction) (c : content_type),"
        " dma_segments_admitted (repeat_segment (maximum_segment d c) (S ring_max_segments))"
        " = false.",
        "intros d c; destruct d; destruct c; vm_compute; reflexivity.")
    lines += _theorem(
        "a_segment_extending_past_its_capability_is_refused",
        "forall (d : direction) (c : content_type),"
        " segment_valid (mk_dma_segment (direction_permission d) ring_segment_max_bytes"
        " (mk_buffer_ref 0 1 ring_segment_max_bytes d c)) = false.",
        "intros d c; destruct d; destruct c; vm_compute; reflexivity.")
    lines += _theorem(
        "a_bad_segment_at_any_position_refuses_the_list",
        "forall (prefix suffix : list dma_segment) (bad : dma_segment),"
        " segment_valid bad = false ->"
        " all_segments_valid (append_segments prefix (cons bad suffix)) = false.",
        "intros prefix suffix bad H; induction prefix as [|segment rest IH];"
        " simpl; [ rewrite H; reflexivity | rewrite IH;"
        " destruct (segment_valid segment); reflexivity ].")

    for field in OP_DMA_KEYS:
        lines += _match(f"op_{field}", "op", "op_", names, "nat",
                        [str(_op_dma(op)[field]) for op in ops])

    lines += [
        "(* The extent is validated whole when the bytes validated are the operation's",
        "   declared payload and not a prefix of it. *)",
        "Definition validates_the_whole_extent (validated : nat) (o : op) : bool :=",
        "  Nat.eqb validated (rec_max_payload_bytes (op_declared_record o)).",
        "",
    ]
    lines += _theorem(
        "the_complete_extent_is_validated_before_the_transfer_starts",
        "forall o : op,"
        " andb (validates_the_whole_extent (op_extent_validated_bytes o) o)"
        " (andb (implb (Nat.ltb 0 (rec_max_payload_bytes (op_declared_record o)))"
        " (Nat.ltb 0 (op_extent_validations_before_start o)))"
        " (Nat.eqb (op_extent_reads_after_start o) 0)) = true.",
        "intro o; destruct o; vm_compute; reflexivity.")
    # The refusal that makes the clause a property rather than a restatement: a
    # validation one byte short of the declared payload is not the complete extent, so
    # a declaration validating a prefix fails this rather than passing it by name.
    lines += _theorem(
        "a_validation_short_of_the_declared_payload_is_not_the_extent",
        "forall o : op,"
        " implb (Nat.ltb 0 (rec_max_payload_bytes (op_declared_record o)))"
        " (negb (validates_the_whole_extent"
        " (Nat.pred (rec_max_payload_bytes (op_declared_record o))) o)) = true.",
        "intro o; destruct o; vm_compute; reflexivity.")
    lines += _theorem(
        "the_validation_cost_is_one_check_per_declared_segment",
        "forall o : op,"
        " Nat.eqb (rec_validation_cost (op_declared_record o))"
        " (op_descriptor_validation_cost o + op_segment_validation_cost o"
        " * rec_max_segment_count (op_declared_record o)) = true.",
        "intro o; destruct o; vm_compute; reflexivity.")
    lines += _theorem(
        "an_operation_with_segments_charges_each_of_them",
        "forall o : op,"
        " implb (Nat.ltb 0 (rec_max_segment_count (op_declared_record o)))"
        " (Nat.ltb 0 (op_segment_validation_cost o)) = true.",
        "intro o; destruct o; vm_compute; reflexivity.")

    lines += [
        f"(* {RESTART_ENTRY}'s *old capabilities dead*, read at the artifact: what a",
        f"   transfer holds while it is live, and where the hold ends. `state_{terminal}`",
        f"   is the state {LIFECYCLE_ENTRY}'s own malformed-step sentence names as the",
        f"   destination, which is terminal completion; `state_{reclaimed}` is the last",
        "   state of that entry's own chain. *)",
        "Definition holds_until_terminal (o : op) (s : slot_state) : nat :=",
        f"  if andb (Nat.leb (lifecycle_rank state_{live}) (lifecycle_rank s))",
        f"          (Nat.ltb (lifecycle_rank s) (lifecycle_rank state_{terminal}))",
        "  then op_held_capabilities o else 0.",
        "",
        "(* The hold this world excludes: one released only when the slot is reclaimed,",
        "   which outlives terminal completion by every state between the two. *)",
        "Definition holds_until_reclaimed (o : op) (s : slot_state) : nat :=",
        f"  if andb (Nat.leb (lifecycle_rank state_{live}) (lifecycle_rank s))",
        f"          (Nat.ltb (lifecycle_rank s) (lifecycle_rank state_{reclaimed}))",
        "  then op_held_capabilities o else 0.",
        "",
        "(* Stated of a hold and not of one hold's body, on the same ground as the",
        "   lost-wakeup exclusion above: nothing is held at or past terminal",
        "   completion. Both holds are held to it, and one of them fails. *)",
        "Definition dead_past_terminal_completion"
        " (hold : op -> slot_state -> nat) : Prop :=",
        "  forall (o : op) (s : slot_state),",
        f"    Nat.leb (lifecycle_rank state_{terminal}) (lifecycle_rank s) = true ->",
        "    hold o s = 0.",
        "",
    ]
    lines += _theorem(
        "no_capability_is_acquired_before_acceptance",
        "forall (o : op) (s : slot_state),"
        f" Nat.ltb (lifecycle_rank s) (lifecycle_rank state_{live}) = true ->"
        " holds_until_terminal o s = 0.",
        "intros o s H; destruct o; destruct s; vm_compute in H |- *;"
        " try reflexivity; discriminate H.")
    lines += _theorem(
        "no_capability_is_retained_past_terminal_completion",
        "dead_past_terminal_completion holds_until_terminal.",
        "intros o s H; destruct o; destruct s; vm_compute in H |- *;"
        " try reflexivity; discriminate H.")
    lines += _theorem(
        "a_hold_released_only_at_reclamation_outlives_terminal_completion",
        "~ dead_past_terminal_completion holds_until_reclaimed.",
        "intro H; unfold dead_past_terminal_completion in H;"
        f" specialize (H op_{_holds_most(ops, names)} state_{terminal});"
        " vm_compute in H; discriminate (H eq_refl).")
    # The refuter's keeps-theorem, so the refutation isolates the release point and
    # nothing else: before terminal completion the two holds are the same function.
    lines += _theorem(
        "the_two_holds_agree_before_terminal_completion",
        "forall (o : op) (s : slot_state),"
        f" Nat.ltb (lifecycle_rank s) (lifecycle_rank state_{terminal}) = true ->"
        " holds_until_terminal o s = holds_until_reclaimed o s.",
        "intros o s H; destruct o; destruct s; vm_compute in H |- *;"
        " try reflexivity; discriminate H.")

    return lines, [
        "permission_eqb_reflexive",
        "the_permission_check_admits_exactly_the_declared_map",
        "every_declared_direction_requires_its_own_permission",
        "a_reference_is_authorized_by_the_direction_it_declares",
        "the_maximum_segment_list_is_admitted",
        "one_segment_past_the_maximum_is_refused",
        "a_segment_extending_past_its_capability_is_refused",
        "a_bad_segment_at_any_position_refuses_the_list",
        "the_complete_extent_is_validated_before_the_transfer_starts",
        "a_validation_short_of_the_declared_payload_is_not_the_extent",
        "the_validation_cost_is_one_check_per_declared_segment",
        "an_operation_with_segments_charges_each_of_them",
        "no_capability_is_acquired_before_acceptance",
        "no_capability_is_retained_past_terminal_completion",
        "a_hold_released_only_at_reclamation_outlives_terminal_completion",
        "the_two_holds_agree_before_terminal_completion",
    ]


def _world_block(own: Owned, world: World) -> list[str]:
    """One world's whole block: the skeleton, the constants, the campaign, the gate."""
    ring, enc = world["ring"], world["encoding"]
    ops = world["operations"]
    names = [op["name"] for op in ops]
    fields = world["operation_record_fields"]

    lines: list[str] = [
        "(* -------------------------------------------------------------------------",
        "   Part 1: the interface skeleton.",
        "   ------------------------------------------------------------------------- *)",
        "",
    ]

    lines += _inductive("status", "status_", own.statuses,
                        f"the closed common set {STATUS_ENTRY} states")
    lines += _inductive("slot_state", "state_", own.states,
                        f"the monotone lifecycle {LIFECYCLE_ENTRY} states, in its order")
    lines += _inductive("cancel_answer", "cancel_", own.cancels,
                        f"the cancellation answers {CANCEL_ENTRY} states")
    lines += _inductive("submit_result", "submit_", ["enqueued", own.full_ring],
                        f"submission, whose full-ring arm {FULL_RING_ENTRY} names")
    lines += _inductive("deadline_class", "deadline_", world["deadline_classes"],
                        "the interface's finite deadline classes")
    lines += _inductive("ring_flag", "flag_", world["flags"], "the closed flag set")
    lines += _inductive("direction", "direction_", world["directions"],
                        "a buffer reference's declared direction")
    lines += _inductive("content_type", "content_", world["content_types"],
                        "a buffer reference's declared content type")
    lines += _inductive("op", "op_", names, "the interface's closed operation variant")

    refinements = [f"{op['name']}__{ref}" for op in ops for ref in op["refinement"]]
    if refinements:
        lines += _inductive("refinement", "refine_", refinements,
                            "each operation's closed result refinement, which "
                            f"{STATUS_ENTRY} admits beside the common set")

    lines += [
        "(* The width IDL-023 fixes, and the only ladder this profile has: the",
        "   smallest of one, two or four bytes that holds a declared case count. A",
        "   flag set's width is not this rule's and no rung here is a flag set's:",
        "   WF-10 makes it a declared width, and the declaration states it below as",
        "   `enc_flag_set_bytes`. *)",
        "Definition disc_width (cases : nat) : nat :=",
        "  if Nat.leb cases 256 then 1 else if Nat.leb cases 65536 then 2 else 4.",
        "",
        "Record labels : Set := mk_labels {",
        "  confidentiality : nat;",
        "  integrity : nat",
        "}.",
        "",
        "Record buffer_ref : Set := mk_buffer_ref {",
        "  session_index : nat;",
        "  ref_offset : nat;",
        "  ref_length : nat;",
        "  ref_direction : direction;",
        "  ref_content : content_type",
        "}.",
        "",
        "Record descriptor : Set := mk_descriptor {",
        "  descriptor_op : op;",
        "  request_id : nat;",
        "  descriptor_generation : nat;",
        "  scalars : list nat;",
        "  buffers : list buffer_ref;",
        "  deadline : option deadline_class;",
        "  flags : list ring_flag",
        "}.",
        "",
        "Record completion : Set := mk_completion {",
        "  completion_request_id : nat;",
        "  completion_status : status;",
        "  completion_refinement : option nat;",
        "  metadata : nat;",
        "  consumed_bytes : nat;",
        "  produced_bytes : nat;",
        "  server_generation : nat",
        "}.",
        "",
        "Record op_record : Set := mk_op_record {",
    ]
    lines += [f"  rec_{field} : nat;" for field in fields]
    lines[-1] = lines[-1].rstrip(";")
    lines += ["}.", ""]

    lines += [
        "(* -------------------------------------------------------------------------",
        "   Part 2: the composition-time constants, from the declaration.",
        "   ------------------------------------------------------------------------- *)",
        "",
    ]
    for key in RING_KEYS:
        lines.append(f"Definition ring_{key} : nat := {ring[key]}.")
    lines.append("")
    for key in sorted(enc):
        lines.append(f"Definition enc_{key} : nat := {enc[key]}.")
    lines += [
        "",
        f"Definition label_levels : nat := {world['label_levels']}.",
        "",
        "Definition buffer_ref_bytes : nat :=",
        "  enc_session_index_bytes + enc_offset_bytes + enc_length_bytes",
        "  + enc_direction_bytes + enc_content_type_bytes.",
        "",
        f"Definition op_count : nat := {len(ops)}.",
        f"Definition deadline_class_count : nat := {len(world['deadline_classes'])}.",
        f"Definition flag_count : nat := {len(world['flags'])}.",
        f"Definition status_count : nat := {len(own.statuses)}.",
        f"Definition refinement_count : nat := {len(refinements)}.",
        "",
        "Definition tag_width : nat := disc_width op_count.",
        "Definition deadline_width : nat := disc_width deadline_class_count.",
        "Definition status_width : nat := disc_width status_count.",
        "Definition refinement_width : nat := disc_width refinement_count.",
        "",
    ]

    lines += _match("op_scalar_bytes", "op", "op_", names, "nat",
                    [str(sum(s["width_bytes"] for s in op["scalars"])) for op in ops])
    lines += _match("op_buffer_refs", "op", "op_", names, "nat",
                    [str(op["buffer_refs"]) for op in ops])
    lines += _match("op_has_deadline", "op", "op_", names, "bool",
                    ["true" if op["deadline"] else "false" for op in ops])
    lines += _match("op_marked_scalars", "op", "op_", names, "nat",
                    [str(sum(1 for s in op["scalars"] if s["validated_at_use"]))
                     for op in ops])
    lines += _match("op_empty_validation_claim", "op", "op_", names, "bool",
                    ["true" if op["empty_validation_claim"] else "false" for op in ops])
    lines += _match("op_labels", "op", "op_", names, "labels",
                    [f"mk_labels {op['labels']['confidentiality']} "
                     f"{op['labels']['integrity']}" for op in ops])
    lines += _match("op_cancellable", "op", "op_", names, "bool",
                    ["true" if op["cancellation"] else "false" for op in ops])
    lines += _match("op_cancel_points", "op", "op_", names, "nat",
                    [str(op["cancellation"]["points"] if op["cancellation"] else 0)
                     for op in ops])
    lines += _match("op_commit_index", "op", "op_", names, "nat",
                    [str(op["cancellation"]["commit_index"] if op["cancellation"] else 0)
                     for op in ops])
    lines += _match("op_quiescence_bound", "op", "op_", names, "nat",
                    [str(op["cancellation"]["quiescence_bound"] if op["cancellation"]
                         else 0) for op in ops])
    lines += _match("op_max_to_terminal", "op", "op_", names, "nat",
                    [str(op["cancellation"]["max_to_terminal"] if op["cancellation"]
                         else 0) for op in ops])
    lines += _match(
        "op_declared_record", "op", "op_", names, "op_record",
        ["mk_op_record " + " ".join(str(value) for value in op["record"]) for op in ops])

    # The declared margins. A composition declares its headroom rather than leaving it
    # to be computed, so every quantity the register makes it prove a bound over sits
    # inside an equality here: a margin nobody wrote down is a margin no reader can
    # audit and no statement can constrain.
    for slack in ("fill", "activation_slack", "payload_slack", "cancellation_slack"):
        lines += _match(f"op_{slack}", "op", "op_", names, "nat",
                        [str(op[slack]) for op in ops])

    lines += [
        "(* The encoded size of a descriptor, by section 4.2's rows: the tag, the",
        "   request identifier, the operation's scalars, its buffer references, its",
        "   optional deadline, and the closed flag set, packed with no interior",
        "   padding. *)",
        "Definition descriptor_bytes (o : op) : nat :=",
        "  tag_width + enc_request_id_bytes + op_scalar_bytes o",
        "  + op_buffer_refs o * buffer_ref_bytes",
        "  + (if op_has_deadline o then 1 + deadline_width else 0)",
        "  + enc_flag_set_bytes.",
        "",
        "(* The encoded size of a terminal completion: its status, the request",
        "   identifier it carries back, the optional operation-specific refinement,",
        "   the bounded result metadata, the consumed and produced byte counts, and",
        "   the server generation. *)",
        "Definition completion_bytes : nat :=",
        "  status_width + enc_request_id_bytes + (1 + refinement_width)",
        "  + enc_metadata_bytes + 2 * enc_byte_count_bytes + enc_generation_bytes.",
        "",
        "(* An activation's declared cost: the requests one drain admits, each",
        "   validated, served, and published. *)",
        "Definition activation_cost (o : op) : nat :=",
        "  rec_max_requests_drained (op_declared_record o)",
        "  * (rec_validation_cost (op_declared_record o)",
        "     + rec_device_service_bound (op_declared_record o)",
        "     + rec_completion_publication_cost (op_declared_record o)).",
        "",
        "(* The interval admission accounts from expiry observation to terminal",
        "   completion: the device's own bound, the declared cleanup, the DMA",
        "   quiescence, and the publication. *)",
        "Definition cancellation_interval (o : op) : nat :=",
        "  rec_device_service_bound (op_declared_record o)",
        "  + rec_cancellation_cleanup_cost (op_declared_record o)",
        "  + op_quiescence_bound o",
        "  + rec_completion_publication_cost (op_declared_record o).",
        "",
        "(* -------------------------------------------------------------------------",
        "   Part 3: the lifecycle, the ring machine, and the conformance campaign.",
        "   ------------------------------------------------------------------------- *)",
        "",
    ]

    last = own.states[-1]
    lines += _match(
        "lifecycle_next", "slot_state", "state_", own.states, "option slot_state",
        [f"Some state_{nxt}" for nxt in own.states[1:]] + ["None"])
    lines += _match("lifecycle_rank", "slot_state", "state_", own.states, "nat",
                    [str(i) for i in range(len(own.states))])

    # The one admitted step past a successor, which R-12-094 states of a malformed
    # request: the two states that entry's own sentence names, acquiring no device
    # authority between them.
    live = _live(own)
    lines += _match(
        "lifecycle_malformed", "slot_state", "state_", own.states,
        "option slot_state",
        [f"Some state_{own.malformed_to}" if state == own.malformed_from else "None"
         for state in own.states])

    lines += [
        "(* The lifecycle is a sequence and not merely an order, so a successor's rank",
        "   is its predecessor's and one more: a step that only *increased* the rank",
        "   would admit a lifecycle that skipped a state, which is exactly what the",
        "   malformed step below is the one licensed instance of. *)",
        "Definition lifecycle_step_ok (s : slot_state) : bool :=",
        "  match lifecycle_next s with",
        "  | None => true",
        "  | Some t => Nat.eqb (lifecycle_rank t) (S (lifecycle_rank s))",
        "  end.",
        "",
        "(* The malformed step skips, and skips exactly the states the register's own",
        "   order puts between the two it names. *)",
        "Definition lifecycle_malformed_ok (s : slot_state) : bool :=",
        "  match lifecycle_malformed s with",
        "  | None => true",
        f"  | Some t => Nat.eqb (lifecycle_rank t) ({_skip(own)} + "
        "lifecycle_rank s)",
        "  end.",
        "",
        "Definition may_reserve (occupancy : nat) : bool :=",
        "  Nat.ltb occupancy ring_capacity.",
        "",
        "Definition submit (occupancy : nat) : submit_result :=",
        f"  if may_reserve occupancy then submit_enqueued else submit_{own.full_ring}.",
        "",
        "(* Acceptance reads the session table and never the descriptor's contents:",
        "   a stale generation and a duplicate live identifier are each refused. *)",
        "Definition accept (session_generation descriptor_generation : nat)",
        "                  (duplicate_live : bool) : bool :=",
        "  andb (Nat.eqb session_generation descriptor_generation) (negb duplicate_live).",
        "",
        f"(* {RESTART_ENTRY}'s artifact reset: the returned generation and empty indices",
        "   are publishable only after revocation or quiescence has been established.",
        "   None keeps the session closed. The boolean is supplied evidence, not a",
        "   claim that the absent DMA engine has actually quiesced. Every lifecycle",
        "   state takes the same reset; the machine must implement this ordering. *)",
        "Definition reset_session (s : slot_state) (generation : nat)",
        "                         (dma_quiesced : bool)",
        "                         : option (nat * nat * nat * bool) :=",
        "  if dma_quiesced then Some (S generation, 0, 0, false) else None.",
        "",
        "(* The notification discipline R-12-096 states, over the two indices at",
        "   the width the declaration gives them: the producer and consumer indices",
        "   are free-running counters below `ring_index_span`, so work is pending",
        "   when their modular difference is not zero, and it is",
        "   `the_capacity_divides_the_index_span` below, bounding the capacity by",
        "   half the span, that makes that difference the occupancy. *)",
        "Definition work_pending (produced consumed : nat) : bool :=",
        "  negb (Nat.eqb (Nat.modulo (produced + ring_index_span - consumed)",
        "                            ring_index_span) 0).",
        "",
        "(* A consumer's sleep decision sees two reads of the producer index:",
        "   `drained`, the one its drain ended on, and `recheck`, the one it takes",
        "   after arming its notification word. The discipline sleeps on an armed",
        "   word and an empty recheck; the drain's index decides nothing. *)",
        "Definition sleeps (drained recheck consumed : nat) (armed : bool) : bool :=",
        "  andb armed (negb (work_pending recheck consumed)).",
        "",
        "(* The consumer the discipline excludes: one that arms and then sleeps on",
        "   the index its drain ended on, never re-reading the producer's. *)",
        "Definition sleeps_without_recheck (drained recheck consumed : nat)",
        "                                  (armed : bool) : bool :=",
        "  andb armed (negb (work_pending drained consumed)).",
        "",
        "(* The lost-wakeup exclusion, stated of a decision rule and not of either",
        "   rule's body: whatever the drain saw, work pending at the recheck is never",
        "   slept over. Both consumers above are held to it, and one of them fails. *)",
        "Definition no_lost_wakeup (decide : nat -> nat -> nat -> bool -> bool) : Prop :=",
        "  forall drained recheck consumed : nat, forall armed : bool,",
        "    work_pending recheck consumed = true ->",
        "    decide drained recheck consumed armed = false.",
        "",
        "(* Cancellation's deterministic race, as the answers depend on where the",
        "   target stands: live and unstarted, live and past a declared point, past",
        "   the commit point, or not live at all. *)",
        "Definition cancel (o : op) (s : slot_state) (position : nat) : cancel_answer :=",
        "  if op_cancellable o then",
        "    match s with",
        f"    | state_{own.unstarted} => cancel_{own.cancels[0]}",
        f"    | state_{live} =>",
        f"        if Nat.ltb position (op_commit_index o) then cancel_{own.cancels[0]}",
        f"        else cancel_{own.cancels[1]}",
        f"    | _ => cancel_{own.cancels[2]}",
        "    end",
        f"  else cancel_{own.cancels[2]}.",
        "",
        "(* Every value a receiver uses as an index, length, offset, or selector: a",
        "   marked scalar, and every field of every buffer reference. *)",
        "Definition op_has_validated (o : op) : bool :=",
        "  orb (Nat.ltb 0 (op_marked_scalars o)) (Nat.ltb 0 (op_buffer_refs o)).",
        "",
        "(* Boolean agreement, written here because the prelude carries `xorb` and",
        "   the library that carries its complement is not on this file's path. *)",
        "Definition agree (a b : bool) : bool := negb (xorb a b).",
        "",
        "Lemma eqb_reflexive : forall n : nat, Nat.eqb n n = true.",
        "Proof. induction n as [| m IH]; simpl; [ reflexivity | exact IH ]. Qed.",
        "",
    ]

    lines += _theorem(
        "the_width_rule_admits_one_form",
        "andb (andb (Nat.eqb (disc_width 256) 1) (Nat.eqb (disc_width 257) 2))"
        " (andb (Nat.eqb (disc_width 65536) 2) (Nat.eqb (disc_width 65537) 4)) = true.",
        "vm_compute; reflexivity.")
    lines += _theorem(
        "the_flag_set_spends_its_declared_width",
        "Nat.eqb (flag_count + enc_flag_spare_bits) (8 * enc_flag_set_bytes) = true.",
        "vm_compute; reflexivity.")
    lines += _theorem(
        "descriptor_fills_its_slot_exactly",
        "forall o : op,"
        " Nat.eqb (descriptor_bytes o + op_fill o) ring_descriptor_size_bytes = true.",
        "intro o; destruct o; vm_compute; reflexivity.")
    lines += _theorem(
        "completion_fills_its_slot_exactly",
        "Nat.eqb (completion_bytes + ring_completion_fill)"
        " ring_completion_size_bytes = true.",
        "vm_compute; reflexivity.")
    lines += _theorem(
        "both_slots_are_aligned",
        "andb"
        " (Nat.eqb (Nat.modulo ring_descriptor_size_bytes"
        " ring_descriptor_alignment_bytes) 0)"
        " (Nat.eqb (Nat.modulo ring_completion_size_bytes"
        " ring_descriptor_alignment_bytes) 0) = true.",
        "vm_compute; reflexivity.")
    lines += _theorem(
        "the_index_span_is_the_declared_width",
        "Nat.eqb ring_index_span (Nat.pow 2 (8 * ring_index_width_bytes)) = true.",
        "vm_compute; reflexivity.")
    lines += _theorem(
        "the_capacity_divides_the_index_span",
        "andb (Nat.eqb (Nat.modulo ring_index_span ring_capacity) 0)"
        " (Nat.leb (2 * ring_capacity) ring_index_span) = true.",
        "vm_compute; reflexivity.")
    lines += _theorem(
        "ring_fills_to_capacity",
        "may_reserve (Nat.pred ring_capacity) = true.",
        "vm_compute; reflexivity.")
    lines += _theorem(
        "ring_refuses_one_past_capacity",
        f"submit ring_capacity = submit_{own.full_ring}.",
        "vm_compute; reflexivity.")
    lines += _theorem(
        "completion_capacity_covers_accepted",
        "andb (Nat.leb ring_max_accepted ring_completion_capacity)"
        " (Nat.leb ring_max_accepted ring_capacity) = true.",
        "vm_compute; reflexivity.")
    lines += _theorem(
        "batch_is_bounded_by_capacity",
        "andb (Nat.ltb 0 ring_max_batch_size)"
        " (Nat.leb ring_max_batch_size ring_capacity) = true.",
        "vm_compute; reflexivity.")
    lines += _theorem(
        "drain_is_bounded_by_the_batch",
        "forall o : op, Nat.leb (rec_max_requests_drained (op_declared_record o))"
        " ring_max_batch_size = true.",
        "intro o; destruct o; vm_compute; reflexivity.")
    lines += _theorem(
        "the_declared_batch_and_segment_maxima_are_attained",
        "andb (Nat.eqb (rec_max_requests_drained (op_declared_record op_"
        f"{_attains(ops, names, 7)})) ring_max_batch_size)"
        " (Nat.eqb (rec_max_segment_count (op_declared_record op_"
        f"{_attains(ops, names, 2)})) ring_max_segments) = true.",
        "vm_compute; reflexivity.")
    lines += _theorem(
        "notifications_are_coalesced_to_one",
        "forall o : op,"
        " Nat.leb (rec_max_notifications (op_declared_record o)) 1 = true.",
        "intro o; destruct o; vm_compute; reflexivity.")
    lines += _theorem(
        "the_payload_is_exactly_the_declared_segments",
        "forall o : op,"
        " andb (Nat.leb (rec_max_segment_count (op_declared_record o))"
        " ring_max_segments)"
        " (Nat.eqb (rec_max_payload_bytes (op_declared_record o)"
        " + op_payload_slack o)"
        " (rec_max_segment_count (op_declared_record o) * ring_segment_max_bytes))"
        " = true.",
        "intro o; destruct o; vm_compute; reflexivity.")
    lines += _theorem(
        "an_activation_spends_the_declared_slot_budget",
        "forall o : op,"
        " Nat.eqb (activation_cost o + op_activation_slack o) ring_slot_budget = true.",
        "intro o; destruct o; vm_compute; reflexivity.")
    lines += _theorem(
        "cancellation_spends_the_declared_interval",
        "forall o : op, implb (op_cancellable o)"
        " (Nat.eqb (cancellation_interval o + op_cancellation_slack o)"
        " (op_max_to_terminal o)) = true.",
        "intro o; destruct o; vm_compute; reflexivity.")
    lines += _theorem(
        "a_non_cancellable_operation_declares_no_cancellation",
        "forall o : op, implb (negb (op_cancellable o))"
        " (Nat.eqb (rec_cancellation_cleanup_cost (op_declared_record o)"
        " + op_quiescence_bound o + op_max_to_terminal o + op_cancel_points o"
        " + op_commit_index o + op_cancellation_slack o) 0) = true.",
        "intro o; destruct o; vm_compute; reflexivity.")
    lines += _theorem(
        "cancellability_is_the_declaration_and_nothing_else",
        "forall o : op,"
        " agree (op_cancellable o) (Nat.ltb 0 (op_cancel_points o)) = true.",
        "intro o; destruct o; vm_compute; reflexivity.")
    lines += _theorem(
        "commit_point_is_one_of_the_declared_points",
        "forall o : op, Nat.leb (op_commit_index o) (op_cancel_points o) = true.",
        "intro o; destruct o; vm_compute; reflexivity.")
    lines += _theorem(
        "labels_are_drawn_from_the_declared_lattice",
        "forall o : op,"
        " andb (Nat.ltb (confidentiality (op_labels o)) label_levels)"
        " (Nat.ltb (integrity (op_labels o)) label_levels) = true.",
        "intro o; destruct o; vm_compute; reflexivity.")
    lines += _theorem(
        "the_empty_validation_case_is_a_claim",
        "forall o : op,"
        " agree (op_empty_validation_claim o) (negb (op_has_validated o)) = true.",
        "intro o; destruct o; vm_compute; reflexivity.")
    lines += _theorem(
        "lifecycle_advances_monotonically",
        "forall s : slot_state, lifecycle_step_ok s = true.",
        "intro s; destruct s; vm_compute; reflexivity.")
    lines += _theorem(
        "lifecycle_has_one_terminal_state",
        f"lifecycle_next state_{last} = None.",
        "vm_compute; reflexivity.")
    lines += _theorem(
        "the_malformed_step_skips_forward",
        "forall s : slot_state, lifecycle_malformed_ok s = true.",
        "intro s; destruct s; vm_compute; reflexivity.")
    lines += _theorem(
        "the_malformed_step_acquires_no_authority",
        f"lifecycle_malformed state_{live} = None.",
        "vm_compute; reflexivity.")
    lines += _theorem(
        "a_stale_generation_is_refused",
        "forall g h : nat, Nat.eqb g h = false -> forall d : bool,"
        " accept g h d = false.",
        "intros g h H d; unfold accept; rewrite H; reflexivity.")
    lines += _theorem(
        "a_duplicate_live_identifier_is_refused",
        "forall g h : nat, accept g h true = false.",
        "intros g h; unfold accept; destruct (Nat.eqb g h); reflexivity.")
    lines += _theorem(
        "a_fresh_unique_request_is_accepted",
        "forall g : nat, accept g g false = true.",
        "intro g; unfold accept; rewrite eqb_reflexive; reflexivity.")
    lines += _theorem(
        "no_published_work_stays_behind_a_sleep",
        "no_lost_wakeup sleeps.",
        "intros drained recheck consumed armed H; unfold sleeps; rewrite H;"
        " destruct armed; reflexivity.")
    # The refutation that makes the exclusion a property rather than a restatement:
    # the drain saw an empty ring, one descriptor was published before the sleep, and
    # the consumer that never re-read the producer index sleeps over it.
    lines += _theorem(
        "a_consumer_that_skips_the_recheck_loses_a_wakeup",
        "~ no_lost_wakeup sleeps_without_recheck.",
        "intro H; unfold no_lost_wakeup in H; specialize (H 0 1 0 true);"
        " vm_compute in H; discriminate (H eq_refl).")
    # The refuter's keeps-theorem, so the refutation isolates the recheck and nothing
    # else: wherever the producer index did not move between the drain and the recheck
    # the two consumers decide alike, so the failure above turns on that one read.
    lines += _theorem(
        "the_two_consumers_differ_only_where_the_producer_moved",
        "forall drained consumed : nat, forall armed : bool,"
        " sleeps drained drained consumed armed"
        " = sleeps_without_recheck drained drained consumed armed.",
        "intros; reflexivity.")
    lines += _theorem(
        "a_sleep_needs_the_armed_word_and_an_empty_recheck",
        "(forall drained recheck consumed : nat,"
        " sleeps drained recheck consumed false = false)"
        " /\\ sleeps 0 0 0 true = true.",
        "split; [ intros; reflexivity | vm_compute; reflexivity ].")
    lines += _theorem(
        "an_unstarted_cancellable_target_is_cancelled",
        "forall (o : op) (position : nat), op_cancellable o = true ->"
        f" cancel o state_{own.unstarted} position = cancel_{own.cancels[0]}.",
        "intros o position H; unfold cancel; rewrite H; reflexivity.")
    lines += _theorem(
        "a_target_before_its_commit_point_is_cancelled",
        "forall (o : op) (position : nat), op_cancellable o = true ->"
        " Nat.ltb position (op_commit_index o) = true ->"
        f" cancel o state_{live} position = cancel_{own.cancels[0]}.",
        "intros o position Hc Hp; unfold cancel; rewrite Hc, Hp; reflexivity.")
    lines += _theorem(
        "cancellation_outside_live_states_is_not_live",
        "forall (o : op) (s : slot_state) (position : nat),"
        f" s <> state_{own.unstarted} -> s <> state_{live} ->"
        f" cancel o s position = cancel_{own.cancels[2]}.",
        "intros o s position Hu Hl; unfold cancel; destruct (op_cancellable o);"
        " [ destruct s; try reflexivity; contradiction | reflexivity ].")
    lines += _theorem(
        "reset_in_every_lifecycle_state_clears_the_indices_and_notification",
        "forall s : slot_state, reset_session s ring_session_generation true ="
        " Some (S ring_session_generation, 0, 0, false).",
        "intro s; destruct s; vm_compute; reflexivity.")
    lines += _theorem(
        "reset_without_quiescence_never_publishes_a_generation",
        "forall s : slot_state, reset_session s ring_session_generation false = None.",
        "intro s; destruct s; vm_compute; reflexivity.")
    lines += _theorem(
        "reset_in_every_lifecycle_state_refuses_the_old_generation",
        "forall (s : slot_state) (generation produced consumed : nat) (armed : bool),"
        " reset_session s ring_session_generation true ="
        " Some (generation, produced, consumed, armed) ->"
        " accept generation ring_session_generation false = false.",
        "intros s generation produced consumed armed H; destruct s;"
        " vm_compute in H; inversion H; vm_compute; reflexivity.")
    lines += _theorem(
        "a_target_past_its_commit_point_is_too_late",
        "forall (o : op) (position : nat), op_cancellable o = true ->"
        " Nat.ltb position (op_commit_index o) = false ->"
        f" cancel o state_{live} position = cancel_{own.cancels[1]}.",
        "intros o position Hc Hp; unfold cancel; rewrite Hc, Hp; reflexivity.")
    lines += _theorem(
        "a_non_cancellable_operation_is_never_live_to_cancel",
        "forall (o : op) (s : slot_state) (position : nat),"
        " op_cancellable o = false ->"
        f" cancel o s position = cancel_{own.cancels[2]}.",
        "intros o s position H; unfold cancel; rewrite H; reflexivity.")

    printed = [
        "eqb_reflexive",
        "the_width_rule_admits_one_form",
        "the_flag_set_spends_its_declared_width",
        "descriptor_fills_its_slot_exactly", "completion_fills_its_slot_exactly",
        "both_slots_are_aligned", "the_index_span_is_the_declared_width",
        "the_capacity_divides_the_index_span", "ring_fills_to_capacity",
        "ring_refuses_one_past_capacity", "completion_capacity_covers_accepted",
        "batch_is_bounded_by_capacity", "drain_is_bounded_by_the_batch",
        "the_declared_batch_and_segment_maxima_are_attained",
        "notifications_are_coalesced_to_one",
        "the_payload_is_exactly_the_declared_segments",
        "an_activation_spends_the_declared_slot_budget",
        "cancellation_spends_the_declared_interval",
        "a_non_cancellable_operation_declares_no_cancellation",
        "cancellability_is_the_declaration_and_nothing_else",
        "commit_point_is_one_of_the_declared_points",
        "labels_are_drawn_from_the_declared_lattice",
        "the_empty_validation_case_is_a_claim",
        "lifecycle_advances_monotonically", "lifecycle_has_one_terminal_state",
        "the_malformed_step_skips_forward",
        "the_malformed_step_acquires_no_authority",
        "a_stale_generation_is_refused", "a_duplicate_live_identifier_is_refused",
        "a_fresh_unique_request_is_accepted",
        "no_published_work_stays_behind_a_sleep",
        "a_consumer_that_skips_the_recheck_loses_a_wakeup",
        "the_two_consumers_differ_only_where_the_producer_moved",
        "a_sleep_needs_the_armed_word_and_an_empty_recheck",
        "an_unstarted_cancellable_target_is_cancelled",
        "a_target_before_its_commit_point_is_cancelled",
        "cancellation_outside_live_states_is_not_live",
        "reset_in_every_lifecycle_state_clears_the_indices_and_notification",
        "reset_without_quiescence_never_publishes_a_generation",
        "reset_in_every_lifecycle_state_refuses_the_old_generation",
        "a_target_past_its_commit_point_is_too_late",
        "a_non_cancellable_operation_is_never_live_to_cancel",
    ]
    dma_lines, dma_printed = _dma_part(own, world, names)
    lines += dma_lines
    printed += dma_printed
    lines += [
        "(* -------------------------------------------------------------------------",
        "   The R-05-163 gate: every constant closed under the global context.",
        "   ------------------------------------------------------------------------- *)",
        "",
    ]
    lines += [f"Print Assumptions {name}." for name in printed]
    return lines


def emit(root: Path, register: Register | None = None) -> str:
    """The artifact's whole text, as a function of the declaration and the register.

    `register` is handed in by the checker, which has already parsed it; a caller with
    nothing parsed passes none and this reads the corpus itself. Either way the parse
    is the one `vos/register.py` owns rather than a second one written here.
    """
    own = owned(register if register is not None
                else read_register(corpus_mod.load(root)))
    worlds = declaration(root)["worlds"]

    lines = _preamble(worlds)
    for index, world in enumerate(worlds):
        if index == 0:
            lines += _world_block(own, world)
            continue
        module = _module(world["world"])
        lines += [
            "",
            "(* -------------------------------------------------------------------------",
            f"   World `{world['world']}`, in a scope of its own: the declaration lists it",
            "   past the first, and the campaign below is the same one the file scope",
            "   carries, decided over this world's own declared constants.",
            "   ------------------------------------------------------------------------- *)",
            "",
            f"Module {module}.",
            "",
        ]
        lines += _world_block(own, world)
        lines += ["", f"End {module}.", ""]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def _emit(args: argparse.Namespace) -> int:
    root = corpus_mod.find_root()
    try:
        text = emit(root)
    except RingError as exc:
        print(f"FAIL: {exc}")
        return 1
    path = root / ARTIFACT
    path.write_text(text, encoding="utf-8", newline="")
    print(f"emitted {ARTIFACT} from {DECLARATION} and the register "
          f"({len(text.splitlines())} lines)")
    return 0


def _check(args: argparse.Namespace) -> int:
    root = corpus_mod.find_root()
    try:
        text = emit(root)
    except RingError as exc:
        print(f"FAIL: {exc}")
        return 1
    path = root / ARTIFACT
    if not path.is_file():
        print(f"FAIL: {ARTIFACT} is not in the working tree; `run.py ring emit` "
              f"writes it")
        return 1
    on_disk = path.read_text(encoding="utf-8")
    if on_disk != text:
        want, got = text.splitlines(), on_disk.splitlines()
        where = next((i for i, (a, b) in enumerate(zip(want, got, strict=False))
                      if a != b), min(len(want), len(got)))
        print(f"FAIL: {ARTIFACT} is not what `run.py ring emit` writes; the first "
              f"difference is at line {where + 1}")
        return 1
    print(f"ok: {ARTIFACT} is byte-identical to what `run.py ring emit` writes from "
          f"{DECLARATION} and the register")
    return 0


TABLE: Table = {
    "emit": (_emit, "write the generated interface artifact from its owners"),
    "check": (_check, "re-emit and compare, byte for byte"),
}


def main(argv: list[str] | None = None) -> int:
    return dispatch(__doc__, TABLE, argv, prog="run.py ring")
