# SPDX-License-Identifier: Apache-2.0
"""Session substitution, custody and freshness counterexamples for Q22c."""

import json
from contextlib import redirect_stdout
from dataclasses import replace
from functools import partial
from io import StringIO
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
    ensure(outputs[0] == outputs[1], "evidence is deterministic")
    broken = replace(sb.experiment(), relation_failures=("counterexample",))
    with patch.object(cli, "experiment", return_value=broken), redirect_stdout(StringIO()):
        ensure(cli.main([]) == 1, "a violated relation must fail the command")


def cases() -> list[Case]:
    return [Case("finite-deliveries", _finite_deliveries),
            Case("credential-custody", _credential_custody),
            Case("tls-lifecycle", _tls_lifecycle),
            Case("freshness-and-failure-consumption", _freshness_and_failure_consumption),
            Case("identity-scope", _identity_scope),
            Case("oracle-detects-binding-collision", _oracle_detects_binding_collision),
            Case("cli-evidence", _cli_evidence)]
