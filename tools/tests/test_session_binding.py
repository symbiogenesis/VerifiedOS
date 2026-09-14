# SPDX-License-Identifier: Apache-2.0
"""Session substitution, custody and freshness counterexamples for Q22c and Q23c."""

import json
from contextlib import redirect_stdout
from dataclasses import replace
from functools import partial
from io import StringIO
from itertools import product
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import session_binding as sb
from vos.cli import session_binding as cli


def _finite_deliveries() -> None:
    result = sb.experiment()
    ensure(result.passed, f"finite relation failed: {result}")
    ensure(result.accepted > 0 and result.refused > result.accepted,
           "the finite universe must exercise acceptance and refusal")
    ensure(result.replay_refusals == result.substitutions,
           "every completed appraisal must consume its challenge")
    ensure(result.reopen_refusals == result.substitutions,
           "reconstructing an appraiser cannot reopen the TLS context")
    cases = {case.name: case.observed for case in result.scenarios}
    ensure(cases["public-exporter-injection"] == "accepted",
           "the intentionally broken issuer must expose the relay counterexample")
    ensure(cases["traffic-key-compromise"] == "attacker-record-accepted",
           "key exposure must defeat the exclusive application-holder inference")


def _credential_custody() -> None:
    broker, channels = sb.fixture()
    channel = channels[0]
    challenge = sb.Challenge("fresh", channel.origin, "software")
    changes = ({"unit": "B"}, {"principal": "other"}, {"origin": "wrong.example"},
               {"scope": "unit"}, {"role": "tls-server"}, {"operation": "sign-any"},
               {"domain": "other-protocol"}, {"remaining": 0}, {"expires": 0})
    for change in changes:
        handle = replace(sb.credential(channel), **change)
        try:
            broker.issue(handle, channel, challenge)
        except sb.SessionBindingError:
            continue
        raise AssertionError(f"credential widened or escaped its context: {change}")
    handle = sb.credential(channel)
    broker.issue(handle, channel, challenge)
    try:
        broker.issue(handle, channel, challenge)
    except sb.SessionBindingError:
        return
    raise AssertionError("credential use bound is not consumed")


def _tls_lifecycle() -> None:
    broker, channels = sb.fixture()
    ch = channels[0]
    for change in ({"complete": False}, {"server_authenticated": False},
                   {"early_data": True}, {"resumed": True}):
        bad = replace(ch, **change)
        for operation in (partial(sb.Appraisal, bad, sb.policy(broker, bad, "software"), "n"),
                          partial(broker.issue, sb.credential(bad), bad,
                                  sb.Challenge("n", bad.origin, "software"))):
            try:
                operation()
            except sb.SessionBindingError:
                continue
            raise AssertionError(f"ineligible handshake accepted: {change}")
    pending = sb.Appraisal(ch, sb.policy(broker, ch, "software"), "n")
    quote = broker.issue(sb.credential(ch), ch, pending.challenge)
    keys = sb.TrafficKeys(ch)
    ensure(not keys.record_accepted(pending, ch.unit), "service opens only after appraisal")
    ensure(pending.decide(quote, broker) == "accepted", "positive session")
    ensure(not keys.record_accepted(pending, "X"), "public exporter does not grant keys")
    ensure(keys.record_accepted(pending, ch.unit), "actual holder can send records")
    pending.close()
    ensure(not keys.record_accepted(pending, ch.unit), "teardown removes service authority")


def _freshness_and_failure_consumption() -> None:
    broker, channels = sb.fixture()
    ch = channels[0]
    for now, expected in ((4, "accepted"), (5, "freshness-expired")):
        ch = replace(ch, lifecycle=sb.Lifecycle())
        pending = sb.Appraisal(ch, sb.policy(broker, ch, "software"), "n", deadline=5)
        quote = broker.issue(sb.credential(ch), ch, pending.challenge)
        ensure(pending.decide(quote, broker, now) == expected, "deadline boundary")
        ensure(pending.decide(quote, broker, now) == "already-decided", "single attempt")
    ch = replace(ch, lifecycle=sb.Lifecycle())
    pending = sb.Appraisal(ch, sb.policy(broker, ch, "software"), "fresh")
    good = broker.issue(sb.credential(ch), ch, pending.challenge)
    ensure(pending.decide(None, broker) == "evidence-invalid", "missing evidence closes")
    ensure(pending.decide(good, broker) == "already-decided", "no retry on failed channel")


def _identity_scope() -> None:
    broker, channels = sb.fixture()
    a = channels[0]
    other_origin = next(c for c in channels if c.unit == "A" and c.origin != a.origin)
    aliases = []
    for ch in (a, other_origin):
        quote = broker.issue(sb.credential(ch), ch, sb.Challenge("n", ch.origin, "software"))
        ensure(quote.claims.unit_alias is None, "software evidence omits unit alias")
        quote = broker.issue(sb.credential(ch, "unit"), ch,
                             sb.Challenge("n", ch.origin, "unit"))
        aliases.append(quote.claims.unit_alias)
    ensure(aliases[0] != aliases[1], "unit enrollment is local to an origin")
    for policy in (sb.Policy("unit", frozenset({"approved"})),
                   sb.Policy("software", frozenset({"approved"}), expected_alias="alias"),
                   sb.Policy("software", frozenset())):
        try:
            sb.Appraisal(a, policy, "n")
        except sb.SessionBindingError:
            continue
        raise AssertionError("inconsistent identity or empty generation policy accepted")


def _oracle_detects_binding_collision() -> None:
    broker, channels = sb.fixture()
    collided = [replace(ch, binding="same-exporter") for ch in channels]
    def collision_fixture() -> tuple[sb.Broker, list[sb.Channel]]:
        return sb.Broker(broker.generations, broker.aliases), [
            replace(ch, lifecycle=sb.Lifecycle()) for ch in collided]
    with patch.object(sb, "fixture", side_effect=collision_fixture):
        result = sb.experiment()
    ensure(bool(result.relation_failures), "event agreement must detect lost TLS uniqueness")


def _ensemble_deliveries() -> None:
    result = sb.ensemble_experiment()
    ensure(result.passed, f"finite ensemble relation failed: {result.relation_failures}")
    ensure(result.accepted > 0 and result.refused > result.accepted,
           "the finite ensemble universe must exercise acceptance and refusal")
    ensure(result.repeat_refusals == result.deliveries,
           "every completed establishment attempt must consume its challenge")
    _, _, members, ends = sb.ensemble_fixture()
    # Each issuer-end pair carries 2 nonces x 2 challengers x 2 suites, delivered at 2 nonces.
    per_pair = 16
    pairs = list(product(members.values(), ends.values()))
    substituted = sum(1 for member, end in pairs
                      if member.device_register.unit != end.expected_peer_unit)
    foreign = sum(1 for member, end in pairs
                  if member.generation_register.ensemble_identity
                  != end.expected_ensemble_identity)
    # The substituting act adds one further die-C issuer, which mismatches both ends.
    ensure(result.substituted_unit_refusals == per_pair * (substituted + 2),
           f"every substituted unit must be refused, not {result.substituted_unit_refusals}")
    ensure(result.foreign_identity_refusals == per_pair * foreign,
           f"every foreign ensemble identity must be refused, not "
           f"{result.foreign_identity_refusals}")


def _ensemble_device_identity_binding() -> None:
    broker, registry, members, ends = sb.ensemble_fixture()
    near = sb.EnsembleAppraisal(ends["a"], "fresh", registry)
    forged = broker.issue(members["c"], near.challenge,
                          claimed_device=sb.DeviceRegister("die-B"), alias=True)
    ensure(near.decide(forged, broker) == "device-identity-binding",
           "a signing identity rooted in no device secret must be refused by name")
    credulous = sb.EnsembleAppraisal(ends["a"], "fresh", registry, bind_identity=False)
    ensure(credulous.decide(forged, broker) == "accepted",
           "taking the binding on faith must admit the substituted unit")
    try:
        broker.issue(members["c"], near.challenge, claimed_device=sb.DeviceRegister("die-B"))
    except sb.SessionBindingError:
        pass
    else:
        raise AssertionError("a member signed another unit's register under a rooted identity")
    ensure(registry.speaks_for("die-B", sb.rooted_identity(sb.device_secret("die-B"))),
           "the premise names one signing identity per device-identity secret")
    ensure(not registry.speaks_for("die-B", sb.alias_identity("die-C")),
           "an alias speaks for no unit")


def _ensemble_mutuality_and_configuration() -> None:
    broker, registry, members, ends = sb.ensemble_fixture()
    honest = sb.PeerAct(members["b"])
    good = sb.establish(ends["a"], ends["b"], broker, registry, honest,
                        sb.PeerAct(members["a"]))
    ensure(good.outcome == "established", "both appraisals accept the composition's peers")
    ensure(good.session() is not None, "an established link opens a session")
    for near, far, expected in ((honest, sb.PeerAct(members["c"]), "refused-unit-identity"),
                                (sb.PeerAct(members["c"]), sb.PeerAct(members["a"]),
                                 "refused-unit-identity"),
                                (sb.PeerAct(members["d"]), sb.PeerAct(members["a"]),
                                 "refused-ensemble-identity")):
        fresh_broker, fresh_registry, _, fresh_ends = sb.ensemble_fixture()
        result = sb.establish(fresh_ends["a"], fresh_ends["b"], fresh_broker, fresh_registry,
                              near, far)
        ensure(result.outcome == expected, f"one-sided acceptance is not a link: {result}")
        ensure(result.session() is None, "a refused establishment opens no session")
    offered = sb.establish(ends["a"], ends["b"], broker, registry, honest,
                           sb.PeerAct(members["a"]),
                           offered=(sb.ADMISSIBLE_SUITE, sb.SECOND_SUITE))
    ensure(offered.outcome == "refused-configuration-negotiated",
           "an offered second configuration terminates rather than selecting a path")


def _ensemble_slot_count_and_custody() -> None:
    broker, registry, members, ends = sb.ensemble_fixture()
    session = sb.establish(ends["a"], ends["b"], broker, registry, sb.PeerAct(members["b"]),
                           sb.PeerAct(members["a"])).session()
    if session is None:
        raise AssertionError("the honest establishment must open a session")
    core = session.core
    try:
        core.export()
    except sb.SessionBindingError:
        pass
    else:
        raise AssertionError("the crypto core exported a session key")
    frame = core.seal(session.link, session.epoch, 2, "payload")
    ensure(session.receive(frame, 2) == "delivered", "a frame verifies in its own slot")
    ensure(session.receive(core.seal(session.link, session.epoch, 2, "other"), 2)
           == "slot-consumed", "the window admits at most one frame per slot")
    replayed = core.seal(session.link, session.epoch, 3, "payload")
    ensure(session.receive(replayed, 9) == "tag-failed", "a replay into another slot fails")
    ensure(session.receive(replayed, 3) == "link-stopped", "a failed tag stops the link")
    credulous = sb.WireCountedSession(session.link, session.epoch, core)
    ensure(credulous.receive(replayed, 9) == "delivered",
           "counting from the wire accepts the replay: the counterexample")
    epochs = sb.EnsembleSession(session.link, session.epoch + 1, core)
    ensure(epochs.receive(frame, 2) == "tag-failed", "the epoch is associated data too")


def _ensemble_oracle_decides_both_directions() -> None:
    with patch.object(sb.IdentityRegistry, "speaks_for", return_value=True):
        credulous = sb.ensemble_experiment()
    ensure(any("substituted unit accepted" in failure
               for failure in credulous.relation_failures),
           "dropping the identity binding must be caught by the event-level oracle")
    with (patch.object(sb.EnsembleAppraisal, "decide", return_value="evidence-invalid"),
          patch.object(sb, "_ensemble_scenarios", return_value=())):
        deaf = sb.ensemble_experiment()
    ensure(bool(deaf.relation_failures), "refusing every establishment must also fail")


def _cli_evidence() -> None:
    outputs = []
    for _ in range(2):
        stream = StringIO()
        with redirect_stdout(stream):
            code = cli.main(["--json"])
        outputs.append(stream.getvalue())
        data = json.loads(stream.getvalue())
        ensure(code == 0 and data["passed"], "CLI must report experiment success")
        ensure(data["production_adoption"] == "open", "finite success is no adoption")
        ensure(all(len(value) == 64 for value in data["sources_sha256"].values()),
               "evidence binds actual source bytes")
        ensure(data["substitutions"] > 0 and data["ensemble"]["deliveries"] > 0,
               "both populations are reported")
        ensure(not data["ensemble"]["relation_failures"], "the ensemble relation holds")
        ensure(data["ensemble"]["substituted_unit_refusals"] > 0
               and data["ensemble"]["foreign_identity_refusals"] > 0,
               "the two named counters must be reported")
    ensure(outputs[0] == outputs[1], "evidence is deterministic")
    broken = replace(sb.experiment(), relation_failures=("counterexample",))
    with patch.object(cli, "experiment", return_value=broken), redirect_stdout(StringIO()):
        ensure(cli.main([]) == 1, "a violated relation must fail the command")
    broken_ensemble = replace(sb.ensemble_experiment(), relation_failures=("counterexample",))
    with (patch.object(cli, "ensemble_experiment", return_value=broken_ensemble),
          redirect_stdout(StringIO())):
        ensure(cli.main([]) == 1, "a violated ensemble relation must fail the command")


def cases() -> list[Case]:
    return [Case("finite-deliveries", _finite_deliveries),
            Case("credential-custody", _credential_custody),
            Case("tls-lifecycle", _tls_lifecycle),
            Case("freshness-and-failure-consumption", _freshness_and_failure_consumption),
            Case("identity-scope", _identity_scope),
            Case("oracle-detects-binding-collision", _oracle_detects_binding_collision),
            Case("ensemble-deliveries", _ensemble_deliveries),
            Case("ensemble-device-identity-binding", _ensemble_device_identity_binding),
            Case("ensemble-mutuality-and-configuration", _ensemble_mutuality_and_configuration),
            Case("ensemble-slot-count-and-custody", _ensemble_slot_count_and_custody),
            Case("ensemble-oracle-decides-both-directions",
                 _ensemble_oracle_decides_both_directions),
            Case("cli-evidence", _cli_evidence)]
