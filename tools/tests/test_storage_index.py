# SPDX-License-Identifier: Apache-2.0
"""Independent map, accounting, corruption and CLI checks for the Q22f fixture."""

import json
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import storage_index as si
from vos.cli import storage_index as cli


def _direct_accounting() -> None:
    keys = (0,) * si.UPDATES
    plain = si.measure("hot", keys, 1, "cow-bplus")
    buffered = si.measure("hot", keys, 1, "buffered")
    ensure(plain.block_writes == 6 * si.UPDATES, "single-key plain CoW must charge all L0 writes")
    ensure(not plain.accepted(5) and plain.accepted(6), "endurance predicate must decide")
    ensure(buffered.block_writes < plain.block_writes and buffered.drain_writes > 0,
           "buffering must charge its final drain and reveal a batching advantage")
    ensure(buffered.byte_amplification == buffered.block_writes * 64 / si.UPDATES,
           "report byte amplification, not just block programs per small overwrite")
    ensure(not replace(buffered, max_transaction_writes=37).accepted(6),
           "amortized endurance cannot hide an excessive worst transaction")
    ensure(not replace(buffered, max_query_message_checks=49).accepted(6),
           "query scan must stay bounded")


def _duplicate_and_drain() -> None:
    pending = tuple((child * si.KEYS_PER_LEAF, round_number)
                    for round_number in (1, 2, 3) for child in range(si.LEAVES))
    state = si.State(messages=pending)
    overflow = si.advance(state, ((0, 99),), "buffered")
    ensure(overflow.pending_peak == 49 and overflow.state.lookup(0) == 99,
           "full-buffer overflow must preserve the last duplicate")
    ensure(all(state.lookup(child * si.KEYS_PER_LEAF) == 3 for child in range(si.LEAVES)),
           "an immutable retained root still sees its own messages")
    drained = si.advance(state, (), "buffered", drain=True)
    ensure(drained.writes == 36 and len(drained.changed) == 17,
           "all-child drain is the maximum transaction, not an amortized single flush")
    expected = [0] * si.KEYS
    for child in range(si.LEAVES):
        expected[child * si.KEYS_PER_LEAF] = 3
    ensure(drained.state.values == tuple(expected) and not drained.state.messages,
           "drain must match independently replayed last-write values")
    ensure(si.crash_checks(state, drained, tuple(expected)) > 0,
           "interrupted full drain needs crash evidence")


def _recovery_refuses_corruption() -> None:
    before = si.State()
    update = si.advance(before, ((0, 10), (si.KEYS_PER_LEAF, 20)), "cow-bplus")
    records = si.redo(before, update)
    old = before.medium()
    for prefix in range(len(records)):
        ensure(si.recover(old, old, records[:prefix], None) == old,
               "uncommitted prefixes cannot publish updates")
        try:
            si.recover(old, old, records[:prefix], records)
        except ValueError:
            pass
        else:
            raise AssertionError("a committed missing payload cannot roll back")
    try:
        si.recover(old, old, tuple(reversed(records)), records)
    except ValueError:
        pass
    else:
        raise AssertionError("commit must bind record order and target identity")
    recovered = si.recover(old, old, records, records)
    ensure(recovered[1][0] == 10 and recovered[2][0] == 20,
           "independent expected committed leaf values")
    ensure(si.recover(old, recovered, records, records) == recovered,
           "retained redo must be idempotent after any recovery prefix")


def _oracle_detects_lost_messages() -> None:
    real = si.advance

    def broken(state: si.State, messages: tuple[si.Message, ...], arm: si.Arm,
               *, drain: bool = False) -> si.Transition:
        result = real(state, messages, arm, drain=drain)
        return replace(result, state=replace(result.state, messages=()))

    with patch.object(si, "advance", side_effect=broken):
        try:
            si.measure("lost-message", (0,), 1, "buffered")
        except AssertionError:
            pass
        else:
            raise AssertionError("flat-map oracle misses dropped acknowledged message")


def _cli_evidence() -> None:
    with redirect_stdout(StringIO()) as output:
        ensure(cli.main(["--json"]) == 0, "bounded experiment must pass")
    result = json.loads(output.getvalue())
    ensure(result["passed"] and result["production_adoption"] == "open",
           "finite success is not product admission")
    ensure(result["exhaustive_streams"] == sum(3 ** length for length in range(1, 7)),
           "declared stream domain must be exhausted")
    ensure(all(len(value) == 64 for value in result["sources_sha256"].values()),
           "evidence must identify source bytes")
    ensure(any(row["cases"].get("buffered-only", 0) for row in result["budget_dispositions"]),
           "the fixture must exercise an endurance tradeoff")
    with (patch.object(cli, "experiment", side_effect=AssertionError("seeded violation")),
          redirect_stdout(StringIO())):
        ensure(cli.main([]) == 1, "an experiment violation must fail its CLI")


def cases() -> list[Case]:
    return [Case("direct-accounting", _direct_accounting),
            Case("duplicate-and-drain", _duplicate_and_drain),
            Case("recovery-refuses-corruption", _recovery_refuses_corruption),
            Case("oracle-detects-lost-messages", _oracle_detects_lost_messages),
            Case("cli-evidence", _cli_evidence)]
