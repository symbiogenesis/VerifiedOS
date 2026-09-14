# SPDX-License-Identifier: Apache-2.0
"""Derived register literals move with their owners and reject ambiguous input."""

from tests.harness import Case, ensure, sandbox_tree
from vos import device_regs as regs

_UART = "\n".join(f"parameter logic [5:0] UART_{name}_OFFSET = 6'h {offset};"
                   for name, offset in (("STATUS", "14"), ("RDATA", "18"), ("WDATA", "1c")))
_SPEC = "\n".join(f'{{ bits: "{i}" name: "{name}" }}' for i, name in enumerate(
    ("TXFULL", "RXFULL", "TXEMPTY", "TXIDLE", "RXIDLE", "RXEMPTY")))
_BLOCK = "\n".join(f"| `0x{i*8:02x}` | `{name}` | RO | value |" for i, name in enumerate(
    ("VERSION", "BLOCK_BYTES", "BLOCK_COUNT", "STATUS", "RESULT", "BLOCK", "COMMAND", "ACK")))
_BLOCK += "\n| `0x100 + 8*i`, `0 <= i < B/8` | `DATA[i]` | RW | staging |\n"
_MODEL = "let blkdev_max_bytes : int(8192) = 8192\nlet blkdev_max_block_bytes : int(4096) = 4096\n"


def _tree() -> dict[str, str]:
    return {regs.UART: _UART, regs.UART_SPEC: _SPEC, regs.BLOCK: _BLOCK, regs.BLOCK_MODEL: _MODEL}


def _owners_drive_offsets_and_fields() -> None:
    with sandbox_tree(_tree()) as root:
        before = regs.emit(root)
        ensure("UART_WDATA = 64'h1c" in before and "BLK_DATA = 64'h100" in before,
               "both register owners supply their offsets")
        (root / regs.UART).write_text(_UART.replace("6'h 1c", "6'h 2c"), encoding="utf-8")
        after = regs.emit(root)
        ensure(after == before.replace("UART_WDATA = 64'h1c", "UART_WDATA = 64'h2c"),
               "a changed owner changes precisely its generated constant")
        (root / regs.UART_SPEC).write_text(_SPEC.replace('bits: "5"', 'bits: "7"'), encoding="utf-8")
        ensure("UART_RXEMPTY_BIT = 7" in regs.emit(root), "status bit positions are also derived")


def _missing_or_duplicate_owners_refuse() -> None:
    for replacement in ("", _UART + "\n" + _UART):
        tree = _tree()
        tree[regs.UART] = replacement
        with sandbox_tree(tree) as root:
            try:
                regs.emit(root)
            except ValueError:
                pass
            else:
                raise AssertionError("absent or ambiguous UART layout accepted")


def cases() -> list[Case]:
    return [Case("owners-drive-offsets-and-fields", _owners_drive_offsets_and_fields),
            Case("missing-or-duplicate-owners-refuse", _missing_or_duplicate_owners_refuse)]
