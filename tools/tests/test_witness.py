# SPDX-License-Identifier: Apache-2.0
"""Q22b examples distinguish safe policy, durable history and trust replacement."""

import json
from collections.abc import Callable
from contextlib import redirect_stdout
from dataclasses import replace
from functools import partial
from io import StringIO
from itertools import product
from math import comb

from tests.harness import Case, ensure
from vos import witness as w
from vos.cli import witness as cli

BASE = ("base-root",)
LEFT = (*BASE, "package-left")
RIGHT = (*BASE, "package-right")


def refuses(operation: Callable[[], object]) -> None:
    try:
        operation()
    except w.WitnessError:
        return
    raise AssertionError("operation requiring refusal succeeded")


def _exhaustive_quorums() -> None:
    result = w.quorum_sweep()
    ensure(result.policies == sum(n * n for n in range(1, 7)), "incomplete policy grid")
    expected = sum(comb(n, k) ** 2 * sum(comb(n, size) for size in range(f + 1))
                   for n in range(1, 7) for k in range(1, n + 1) for f in range(n))
    ensure(result.assignments == expected, "quorum/fault assignment grid is incomplete")
    ensure(not result.disagreements, f"intersection formula disagrees: {result}")


def _policy_identity_and_availability() -> None:
    p = w.flat(4, 3, 1)
    ensure(p.safe and p.available(frozenset(p.witnesses[:3])), "3-of-4 must tolerate one outage")
    ensure(not p.available(frozenset(p.witnesses[:2])), "two responders cannot sign a quorum")
    ensure(not p.available(frozenset(w.flat(4, 3, 1, prefix="other").witnesses)),
           "outsiders contribute no availability")
    ensure(w.flat(3, 3, 1).safe, "unanimity can be safe despite poor availability")
    ensure(not w.flat(3, 3, 1).available(frozenset(w.flat(3, 3, 1).witnesses[:2])),
           "safety must not imply availability")
    refuses(lambda: w.flat(0, 0, 0))
    refuses(lambda: w.flat(2, 1, 2))
    refuses(lambda: replace(p, witnesses=(p.witnesses[0],) * 4))
    refuses(lambda: replace(p, witnesses=tuple(w.Key(str(i), "one-key") for i in range(4))))


def _fresh_split_view() -> None:
    p = w.flat(2, 1, 0)
    left = w.Witness(p, p.witnesses[0]).sign(LEFT)
    right = w.Witness(p, p.witnesses[1]).sign(RIGHT)
    ensure(left.authenticated and right.authenticated, "counterexample requires honest signatures")
    ensure(not w.extends(LEFT, RIGHT) and not w.extends(RIGHT, LEFT), "fixtures must conflict")
    for checkpoint, signature in ((LEFT, left), (RIGHT, right)):
        client = w.Client(p)
        ensure(not client.admit(checkpoint, (signature,), "base-root", (), "candidate"),
               "1-of-2 must be rejected even by a fresh client")
        ensure(client.installed == "running-generation" and client.pinned == (),
               "refusal changed running generation or pin")


def _crash_at_each_boundary() -> None:
    p = w.flat(4, 3, 1)
    for boundary in range(4):
        witness = w.Witness(p, p.witnesses[0], BASE)
        if boundary >= 1:
            witness.prepare(LEFT)
        if boundary >= 2:
            witness.commit()
        if boundary >= 3:
            witness.release()
        witness.crash()
        refuses(witness.release)
        if boundary < 2:
            ensure(witness.sign(RIGHT).checkpoint == RIGHT, "uncommitted proposal pinned history")
        else:
            refuses(partial(witness.sign, RIGHT))
            ensure(witness.sign(LEFT).checkpoint == LEFT, "durable retry cannot recover liveness")


def _bounded_action_schedules() -> None:
    p = w.flat(1, 1, 0)
    # Each sequence is independent; rejected operations preserve the model's
    # ability to decide the remaining actions. No scheduler fairness is assumed.
    for schedule in product(("left", "right", "commit", "release", "crash"), repeat=7):
        witness = w.Witness(p, p.witnesses[0], BASE)
        signed: list[w.Checkpoint] = []
        for action in schedule:
            try:
                if action in ("left", "right"):
                    witness.prepare(LEFT if action == "left" else RIGHT)
                elif action == "commit":
                    witness.commit()
                elif action == "crash":
                    witness.crash()
                else:
                    signature = witness.release()
                    ensure(witness.stored == witness.trusted, "released against damaged storage")
                    ensure(signature.checkpoint == witness.trusted.checkpoint,
                           "signature preceded durable successor")
                    ensure(all(w.extends(signature.checkpoint, old) for old in signed),
                           f"honest witness signed a fork under {schedule}")
                    signed.append(signature.checkpoint)
            except w.WitnessError:
                pass


def _rollback_loss_and_recovery() -> None:
    p = w.flat(4, 3, 1)
    witness = w.Witness(p, p.witnesses[0], BASE)
    old = witness.trusted
    witness.sign(LEFT)
    latest = witness.trusted
    for damaged in (None, old, replace(latest, checkpoint=RIGHT)):
        witness.stored = damaged
        witness.crash()
        refuses(lambda: witness.sign(RIGHT))
        refuses(lambda: witness.recover(w.Recovery(p, witness.key, old, True)))
        refuses(lambda: witness.recover(w.Recovery(p, witness.key, latest, False)))
        refuses(lambda: witness.recover(w.Recovery(p, p.witnesses[1], latest, True)))
        refuses(lambda: witness.recover(w.Recovery(replace(p, epoch=1), witness.key, latest, True)))
        witness.recover(w.Recovery(p, witness.key, latest, True))
        refuses(lambda: witness.sign(RIGHT))
        ensure(witness.sign(LEFT).checkpoint == LEFT, "authenticated latest recovery refused")


def _certificate_binding() -> None:
    p = w.flat(4, 3, 1)
    valid = w.signatures(p, LEFT)
    ensure(w.certificate(p, LEFT, valid), "positive inhabited certificate refused")
    variants = (
        valid[:2],
        (valid[0], valid[0], valid[1]),
        (replace(valid[0], authenticated=False), *valid[1:]),
        (replace(valid[0], checkpoint=RIGHT), *valid[1:]),
        (replace(valid[0], policy=replace(p, epoch=1)), *valid[1:]),
        (replace(valid[0], signer=w.Key("outsider", "other-key")), *valid[1:]),
        (replace(valid[0], signer=w.Key(valid[0].signer.identity, "wrong-key")), *valid[1:]),
    )
    for signatures in variants:
        ensure(not w.certificate(p, LEFT, signatures), f"bad certificate accepted: {signatures}")


def _admission_inclusion_pin_and_outage() -> None:
    p = w.flat(4, 3, 1)
    valid = w.signatures(p, LEFT)
    client = w.Client(p)
    ensure(client.admit(LEFT, valid, "base-root", ("package-left",), "first"),
           "valid base/package inclusion refused")
    for checkpoint, sigs, base, packages in (
        (RIGHT, w.signatures(p, RIGHT), "base-root", ("package-right",)),
        (LEFT, valid, "unpublished-base", ("package-left",)),
        (LEFT, valid, "base-root", ("promised-package",)),
        (LEFT, valid[:2], "base-root", ("package-left",)),
        (BASE, w.signatures(p, BASE), "base-root", ()),
    ):
        ensure(not client.admit(checkpoint, sigs, base, packages, "bad"),
               "inconsistent, absent, promised or insufficient evidence accepted")
        ensure(client.installed == "first" and client.pinned == LEFT,
               "install refusal disturbed the running generation or durable pin")


def _prefix_only_disjoint_transition_is_insufficient() -> None:
    old = w.flat(4, 3, 1)
    new = w.flat(4, 3, 1, epoch=1, prefix="new")
    change = w.Transition(old, new, BASE)
    old_witnesses = [w.Witness(old, key) for key in old.witnesses[:3]]
    new_witnesses = [w.Witness(new, key) for key in new.witnesses[:3]]
    old_prefix = tuple(witness.sign(BASE) for witness in old_witnesses)
    new_prefix = tuple(witness.sign(BASE) for witness in new_witnesses)
    ensure(not w.Client(old).transition(change, old_prefix, new_prefix),
           "ordinary shared-prefix signatures wrongly close old signing authority")
    # The rejected construction has a concrete attack: both individually safe
    # populations keep signing, so shared-prefix evidence alone permits a fork.
    left = tuple(witness.sign(LEFT) for witness in old_witnesses)
    right = tuple(witness.sign(RIGHT) for witness in new_witnesses)
    ensure(w.certificate(old, LEFT, left) and w.certificate(new, RIGHT, right),
           "disjoint continuation counterexample lost its valid certificates")


def _terminal_continuity_and_recovery() -> None:
    old = w.flat(4, 3, 1)
    new = w.flat(4, 3, 1, epoch=1, prefix="new")
    change = w.Transition(old, new, BASE)
    retired = [w.Witness(old, key) for key in old.witnesses[:3]]
    seals = tuple(witness.sign(BASE, change) for witness in retired)
    fresh = w.signatures(new, BASE)
    client = w.Client(old)
    ensure(client.transition(change, seals, fresh), "terminal quorum continuity refused")
    ensure(client.policy == new and client.continuity_preserved, "continuity status lost")
    ensure(client.installed == "running-generation", "policy transition installed an image")
    for witness in retired:
        terminal = witness.trusted
        witness.stored = None
        witness.crash()
        witness.recover(w.Recovery(old, witness.key, terminal, True))
        refuses(partial(witness.sign, LEFT))
        refuses(partial(witness.sign, BASE))
        alternate = replace(change, new=w.flat(4, 3, 1, epoch=1, prefix="alternate"))
        refuses(partial(witness.sign, BASE, alternate))
        ensure(witness.sign(BASE, change).terminal == change, "sealed retry refused")
    unsealed = w.Witness(old, old.witnesses[3]).sign(RIGHT)
    ensure(not w.certificate(old, RIGHT, (unsealed,)), "remaining old witness forms a quorum")
    ensure(not w.Client(old, LEFT).transition(change, seals, fresh),
           "transition rolled a client back below its pin")
    ensure(not w.Client(old).transition(replace(change, new=replace(new, threshold=4)),
                                       seals, fresh), "policy parameters were not signed")
    ensure(not w.Client(old).transition(replace(change, new=replace(new, epoch=2)),
                                       seals, fresh), "skipped epoch accepted")


def _authenticated_rebootstrap_has_new_scope() -> None:
    old = w.flat(4, 3, 1)
    new = w.flat(3, 3, 1, scope="replacement-population", prefix="replacement")
    change = w.Rebootstrap(old, new, RIGHT, "new identities and fresh durable anchors", True)
    sigs = w.signatures(new, RIGHT)
    for bad in (replace(change, authenticated=False), replace(change, replacement_assumptions=" "),
                replace(change, old=replace(old, epoch=9)), replace(change, anchor=LEFT),
                replace(change, new=replace(new, scope=old.scope))):
        client = w.Client(old, LEFT)
        ensure(not client.rebootstrap(bad, sigs), "unauthenticated or unscoped replacement accepted")
        ensure(client.policy == old and client.pinned == LEFT, "refused rebootstrap changed state")
    client = w.Client(old, LEFT)
    ensure(client.rebootstrap(change, sigs), "explicit authenticated replacement refused")
    ensure(not client.continuity_preserved and client.policy.scope != old.scope,
           "disjoint trust replacement claimed old population continuity")
    ensure(client.installed == "running-generation", "rebootstrap installed an image")
    reused = w.Rebootstrap(new, old, LEFT, "reuse the original scope", True)
    ensure(not client.rebootstrap(reused, w.signatures(old, LEFT)),
           "A-to-B-to-A rebootstrap reused an earlier trust scope")


def _selective_delivery_remains_valid() -> None:
    p = w.flat(4, 3, 1)
    both = (*LEFT, "package-right")
    sigs = w.signatures(p, both)
    ordinary, target = w.Client(p), w.Client(p)
    ensure(ordinary.admit(both, sigs, "base-root", ("package-left",), "ordinary"),
           "ordinary logged variant refused")
    ensure(target.admit(both, sigs, "base-root", ("package-right",), "targeted"),
           "valid selective-delivery residual was silently forbidden")
    ensure(ordinary.pinned == target.pinned and ordinary.installed != target.installed,
           "same public log must allow different valid selection")


def _cli_reports_bounded_scope() -> None:
    output = StringIO()
    with redirect_stdout(output):
        status = cli.main(["qualify", "--max-n", "2", "--json"])
    result = json.loads(output.getvalue())
    ensure(status == 0 and result["max_n"] == 2 and result["policies"] == 5,
           "CLI lost its enumerated bounds or verdict")
    output = StringIO()
    with redirect_stdout(output):
        status = cli.main(["qualify", "--max-n", "1"])
    ensure(status == 0 and "theorem and production validator remain open" in output.getvalue(),
           "CLI claimed more than its bounded model")


def cases() -> list[Case]:
    return [Case(fn.__name__.removeprefix("_"), fn) for fn in (
        _exhaustive_quorums, _policy_identity_and_availability, _fresh_split_view,
        _crash_at_each_boundary, _bounded_action_schedules, _rollback_loss_and_recovery,
        _certificate_binding, _admission_inclusion_pin_and_outage,
        _prefix_only_disjoint_transition_is_insufficient, _terminal_continuity_and_recovery,
        _authenticated_rebootstrap_has_new_scope, _selective_delivery_remains_valid,
        _cli_reports_bounded_scope,
    )]
