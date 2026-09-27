# SPDX-License-Identifier: Apache-2.0
"""Device persistence campaign generation and evidence refusal controls."""

import json
import tempfile
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import asm, block_persistence

ROOT = TOOLS.parent


def _programs() -> None:
    sources = {name: block_persistence.program(ROOT, name)
               for name in ("durable", "flush", "reopen")}
    for name, source in sources.items():
        ensure(bool(asm.Assembler(source, name).assemble()), f"{name} failed assembly")
    after_submit = sources["durable"].split("sd t0, 48(c9)", 1)[1]
    ensure("24(c9)" not in after_submit and "56(c9)" not in after_submit,
           "C-durable observed or acknowledged the completed write")
    ensure(block_persistence.program(ROOT, "reopen", wrong_byte=True) != sources["reopen"],
           "wrong-byte control failed to change the reader")
    ensure(sources["reopen"] == block_persistence.program(ROOT, "reopen"),
           "program generation is nondeterministic")


def _receipts() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "receipt.jsonl"
        initial = {"event": "open", "sha256": "0" * 64, "block_bytes": 8,
                   "schema": "verifiedos-blkdev-receipt-2"}
        input_record = {"event": "input", "kind": "progress", "epoch": 1, "status": 1,
                        "command": 2, "remaining": 1, "input_epoch": 1, "misplaced": None,
                        "io_error": False, "mask": [0] * 8}
        write = {"event": "persist", "durable": True, "kind": "write", "offset": 0, "length": 8}
        close = {"event": "close", "sha256": "1" * 64, "healthy": True}
        cases = [([initial, input_record, write, close], True), ([initial, input_record, write], False),
                 ([initial, input_record, {**write, "durable": False}, close], False),
                 ([initial, input_record, write, {**close, "healthy": False}], False),
                 ([{**initial, "sha256": "?" * 64}, input_record, close], False),
                 ([initial, write, close], False),
                 ([initial, {**input_record, "mask": [0] * 7}, close], False),
                 ([initial, {**input_record, "input_epoch": -1}, close], False),
                 ([initial, {**input_record, "io_error": 1}, close], False)]
        for rows, accepted in cases:
            path.write_text("\n".join(json.dumps({"sequence": i, **row}) for i, row in enumerate(rows))
                            + "\n", encoding="utf-8")
            try:
                block_persistence.read_receipt(path)
            except ValueError:
                ensure(not accepted, "valid receipt refused")
            else:
                ensure(accepted, "incomplete or failed receipt accepted")
        rows = [{"sequence": i, **row} for i, row in enumerate([initial, input_record, write, close])]
        rows[2]["sequence"] = 3
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        try:
            block_persistence.read_receipt(path)
        except ValueError as exc:
            ensure("sequence" in str(exc), "wrong sequence refusal")
        else:
            raise AssertionError("missing or reordered input sequence was accepted")


def _verdicts() -> None:
    good = "SUCCESS\n"
    bad = "FAILURE: 3 (0x00000003)\n"
    ensure(block_persistence.htif_verdict(good, 0, None), "positive verdict refused")
    ensure(block_persistence.htif_verdict(bad, 1, 3), "exact expected negative verdict refused")
    for text, code, expected in ((good, -11, None), (bad, -11, 3), (bad, 0, 3),
                                  (bad, 1, 2), (bad + good, 1, 3), (good + bad, 0, None),
                                  ("FAILURE: unrelated trap\n", 1, 3)):
        ensure(not block_persistence.htif_verdict(text, code, expected),
               "crash, wrong check or conflicting verdict accepted as evidence")


def cases() -> list[Case]:
    return [Case("purecap programs assemble and preserve unobserved completion", _programs),
            Case("incomplete, malformed and failed image receipts refuse", _receipts),
            Case("HTIF negatives require exact check and normal exit", _verdicts)]
