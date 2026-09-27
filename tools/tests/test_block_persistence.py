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
        initial = {"event": "open", "sha256": "0" * 64}
        write = {"event": "persist", "durable": True, "kind": "write"}
        close = {"event": "close", "sha256": "1" * 64, "healthy": True}
        cases = [([initial, write, close], True), ([initial, write], False),
                 ([initial, {**write, "durable": False}, close], False),
                 ([initial, write, {**close, "healthy": False}], False),
                 ([{**initial, "sha256": "?" * 64}, close], False)]
        for rows, accepted in cases:
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            try:
                block_persistence.read_receipt(path)
            except ValueError:
                ensure(not accepted, "valid receipt refused")
            else:
                ensure(accepted, "incomplete or failed receipt accepted")


def cases() -> list[Case]:
    return [Case("purecap programs assemble and preserve unobserved completion", _programs),
            Case("incomplete and failed image receipts refuse", _receipts)]
