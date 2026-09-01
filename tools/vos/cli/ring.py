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

**What the artifact is not.** It is not a proof of the ring contract: the campaign is
a set of obligations decided by computation over the declared constants, which is the
fail-closed reading of R-18-037's *no interface world declaring rings is admitted
before its campaign runs*. A declaration whose constants break an obligation fails to
compile the artifact. The canonical SPSC, lost-wakeup and typestate proofs that entry
also names are not here and are not claimed.
"""

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vos import corpus as corpus_mod
from vos.cli import Table, dispatch
from vos.register import Register, read_register

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

# The register's own spellings, found where each entry states them. A backticked
# lower-case identifier is how that document writes a wire token, and the arrow chain
# is how it writes an ordered lifecycle; neither pattern is this file's invention and
# both fail closed below rather than yielding an empty enumeration.
_TOKEN_RE = re.compile(r"`([a-z][a-z_]*)`")
_CLOSED_SET_RE = re.compile(r"closed common set \(([^)]*)\)")
_CHAIN_RE = re.compile(r"([A-Z][a-z]+(?: → [A-Z][a-z]+)+)")


class RingError(Exception):
    """An owner did not carry what the emitter reads out of it."""


def _ordered(names: list[str]) -> list[str]:
    """The names in first-appearance order, each once. An entry writes one token
    twice where its sentence needs it twice, and the enumeration is still one."""
    seen: dict[str, None] = {}
    for name in names:
        seen.setdefault(name, None)
    return list(seen)


@dataclass(frozen=True)
class Owned:
    """The four enumerations the register owns, read from its own entry lines."""

    statuses: list[str]
    states: list[str]
    full_ring: str
    cancels: list[str]


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
    if not statuses or len(states) < 2 or not cancels:
        raise RingError("an enumeration the register owns came back empty")
    return Owned(statuses=statuses, states=states, full_ring=full[0], cancels=cancels)


def declaration(root: Path) -> dict[str, Any]:
    """The one authored declaration, with the shape checks the emitter depends on."""
    path = root / DECLARATION
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RingError(f"{DECLARATION} is not readable: {exc}") from exc
    try:
        decl: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RingError(f"{DECLARATION} is not JSON: {exc}") from exc

    for key in ("ring", "encoding", "operation_record_fields", "operations",
                "deadline_classes", "flags", "directions", "content_types"):
        if key not in decl:
            raise RingError(f"{DECLARATION} declares no `{key}`")
    if not decl["operations"]:
        raise RingError(f"{DECLARATION} declares no operation, so the artifact would "
                        f"carry an empty tag set and every obligation over it would "
                        f"hold vacuously")
    width = len(decl["operation_record_fields"])
    for op in decl["operations"]:
        if len(op["record"]) != width:
            raise RingError(f"operation `{op['name']}` supplies {len(op['record'])} "
                            f"record values where the declared field set has {width}")
    return decl


def _inductive(name: str, prefix: str, members: list[str], note: str) -> list[str]:
    out = [f"(* {note} *)", f"Inductive {name} : Set :="]
    out += [f"  | {prefix}{member}" for member in members]
    out[-1] += "."
    return [*out, ""]


def _match(fn: str, arg_type: str, prefix: str, members: list[str],
           result: str, arms: list[str]) -> list[str]:
    out = [f"Definition {fn} (o : {arg_type}) : {result} :=", "  match o with"]
    out += [f"  | {prefix}{member} => {arm}"
            for member, arm in zip(members, arms, strict=True)]
    return [*out, "  end.", ""]


def _theorem(name: str, statement: str, proof: str) -> list[str]:
    return [f"Theorem {name} :", f"  {statement}", f"Proof. {proof} Qed.", ""]


def _skip(states: list[str]) -> int:
    """How many ranks the malformed step covers, from the register's own order: the
    submitted state to the terminal one, which is a figure of that order rather than
    one this file chooses."""
    return states.index(states[4]) - states.index(states[2])


def _attains(ops: list[dict[str, Any]], names: list[str], field: int) -> str:
    """The operation whose declared record is largest at `field`.

    A ring constant declared above every operation's use of it is a constant nothing
    constrains, so the artifact states that each declared maximum is *attained*: the
    witness is this operation, and naming it is what turns a bound into a figure a
    weakening moves.
    """
    best = max(range(len(ops)), key=lambda i: int(ops[i]["record"][field]))
    return names[best]


def emit(root: Path, register: Register | None = None) -> str:
    """The artifact's whole text, as a function of the declaration and the register.

    `register` is handed in by the checker, which has already parsed it; a caller with
    nothing parsed passes none and this reads the corpus itself. Either way the parse
    is the one `vos/register.py` owns rather than a second one written here.
    """
    own = owned(register if register is not None
                else read_register(corpus_mod.load(root)))
    decl = declaration(root)
    ring, enc = decl["ring"], decl["encoding"]
    ops = decl["operations"]
    names = [op["name"] for op in ops]
    fields = decl["operation_record_fields"]

    lines: list[str] = [
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
        "         everything a composition fixes: the ring constants, the encoding",
        "         widths, the operation set, and each operation's declared record.",
        "     docs/requirements-register.md",
        f"         {STATUS_ENTRY}'s closed status set, {LIFECYCLE_ENTRY}'s lifecycle"
        " states,",
        f"         {FULL_RING_ENTRY}'s full-ring result, and {CANCEL_ENTRY}'s"
        " cancellation answers.",
        "",
        "   What this is, per the profile's section 4.3.6: the generated interface",
        "   artifact, carrying the interface skeleton, the composition-time",
        "   constants, and the conformance campaign R-18-037 requires. The campaign",
        "   is decided by computation over the declared constants, so a declaration",
        "   whose constants break an obligation fails to compile this file. The",
        "   canonical SPSC, lost-wakeup and typestate proofs that entry also names",
        "   are not here and are not claimed.",
        "",
        "   Nothing here is a proof about an implementation: the profile's own rule",
        "   is that its types document the contract and never are it.",
        "   ========================================================================= *)",
        "",
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
    lines += _inductive("deadline_class", "deadline_", decl["deadline_classes"],
                        "the interface's finite deadline classes")
    lines += _inductive("ring_flag", "flag_", decl["flags"], "the closed flag set")
    lines += _inductive("direction", "direction_", decl["directions"],
                        "a buffer reference's declared direction")
    lines += _inductive("content_type", "content_", decl["content_types"],
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
    ring_keys = ["capacity", "index_width_bytes", "index_span",
                 "descriptor_size_bytes", "descriptor_alignment_bytes",
                 "completion_size_bytes", "completion_fill", "max_batch_size",
                 "session_generation", "completion_capacity", "max_accepted",
                 "max_segments", "segment_max_bytes", "slot_budget"]
    for key in ring_keys:
        if key not in ring:
            raise RingError(f"{DECLARATION} declares no ring constant `{key}`")
        lines.append(f"Definition ring_{key} : nat := {ring[key]}.")
    lines.append("")
    for key in sorted(enc):
        lines.append(f"Definition enc_{key} : nat := {enc[key]}.")
    lines += [
        "",
        f"Definition label_levels : nat := {decl['label_levels']}.",
        "",
        "Definition buffer_ref_bytes : nat :=",
        "  enc_session_index_bytes + enc_offset_bytes + enc_length_bytes",
        "  + enc_direction_bytes + enc_content_type_bytes.",
        "",
        f"Definition op_count : nat := {len(ops)}.",
        f"Definition deadline_class_count : nat := {len(decl['deadline_classes'])}.",
        f"Definition flag_count : nat := {len(decl['flags'])}.",
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
        for op in ops:
            if slack not in op:
                raise RingError(f"operation `{op['name']}` declares no `{slack}`")
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
    # request: submitted straight to terminal, acquiring no device authority.
    submitted, terminal = own.states[2], own.states[4]
    lines += _match(
        "lifecycle_malformed", "slot_state", "state_", own.states,
        "option slot_state",
        [f"Some state_{terminal}" if state == submitted else "None"
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
        f"  | Some t => Nat.eqb (lifecycle_rank t) ({_skip(own.states)} + "
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
        "(* The notification discipline: work is pending when the consumer index",
        "   trails the producer's, and the consumer sleeps only on a recheck that",
        "   shows none. *)",
        "Definition work_pending (produced consumed : nat) : bool :=",
        "  Nat.ltb consumed produced.",
        "",
        "Definition sleeps (produced consumed : nat) (armed : bool) : bool :=",
        "  andb armed (negb (work_pending produced consumed)).",
        "",
        "Definition no_lost_wakeup (produced consumed : nat) (armed : bool) : bool :=",
        "  implb (sleeps produced consumed armed) (negb (work_pending produced consumed)).",
        "",
        "(* Cancellation's deterministic race, as the answers depend on where the",
        "   target stands: live and unstarted, live and past a declared point, past",
        "   the commit point, or not live at all. *)",
        "Definition cancel (o : op) (s : slot_state) (position : nat) : cancel_answer :=",
        "  if op_cancellable o then",
        "    match s with",
        f"    | state_{submitted} => cancel_{own.cancels[0]}",
        f"    | state_{own.states[3]} =>",
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
        f"lifecycle_malformed state_{own.states[3]} = None.",
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
        "forall produced consumed : nat, forall armed : bool,"
        " no_lost_wakeup produced consumed armed = true.",
        "intros produced consumed armed; unfold no_lost_wakeup, sleeps;"
        " destruct armed; destruct (work_pending produced consumed); reflexivity.")
    lines += _theorem(
        "a_target_past_its_commit_point_is_too_late",
        "forall (o : op) (position : nat), op_cancellable o = true ->"
        " Nat.ltb position (op_commit_index o) = false ->"
        f" cancel o state_{own.states[3]} position = cancel_{own.cancels[1]}.",
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
        "a_target_past_its_commit_point_is_too_late",
        "a_non_cancellable_operation_is_never_live_to_cancel",
    ]
    lines += [
        "(* -------------------------------------------------------------------------",
        "   The R-05-163 gate: every constant closed under the global context.",
        "   ------------------------------------------------------------------------- *)",
        "",
    ]
    lines += [f"Print Assumptions {name}." for name in printed]
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
