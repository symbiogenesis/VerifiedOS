# SPDX-License-Identifier: Apache-2.0
"""Derived register literals move with their owners and reject ambiguous input.

The header records the owner checkout's commit, read back by the host rule that holds
it against the gitlink, so the stamp is written once, read once and refused when it is
absent, doubled, or taken from a directory that is not its own checkout.
"""

from collections.abc import Callable
from subprocess import CompletedProcess
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from vos import device_regs as regs

_REV = "4b9bec92" + "0" * 32

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
        before = regs.emit(root, _REV)
        ensure("UART_WDATA = 64'h1c" in before and "BLK_DATA = 64'h100" in before,
               "both register owners supply their offsets")
        (root / regs.UART).write_text(_UART.replace("6'h 1c", "6'h 2c"), encoding="utf-8")
        after = regs.emit(root, _REV)
        ensure(after == before.replace("UART_WDATA = 64'h1c", "UART_WDATA = 64'h2c"),
               "a changed owner changes precisely its generated constant")
        (root / regs.UART_SPEC).write_text(_SPEC.replace('bits: "5"', 'bits: "7"'), encoding="utf-8")
        ensure("UART_RXEMPTY_BIT = 7" in regs.emit(root, _REV),
               "status bit positions are also derived")


def _missing_or_duplicate_owners_refuse() -> None:
    for replacement in ("", _UART + "\n" + _UART):
        tree = _tree()
        tree[regs.UART] = replacement
        with sandbox_tree(tree) as root:
            try:
                regs.emit(root, _REV)
            except ValueError:
                pass
            else:
                raise AssertionError("absent or ambiguous UART layout accepted")


def _block_half_needs_no_mocha_owner() -> None:
    with sandbox_tree(_tree()) as root:
        text = regs.emit(root, _REV)
        lines = text.splitlines()
        uart, block = regs.uart_lines(root), regs.block_lines(root)
        ensure(lines[8:8 + len(uart) + len(block)] == uart + block,
               "the package is the UART half followed by the block half")
    tree = _tree()
    del tree[regs.UART], tree[regs.UART_SPEC]
    with sandbox_tree(tree) as root:
        ensure(regs.block_lines(root) == block,
               "the block half is derived without the Mocha checkout")
        try:
            regs.uart_lines(root)
        except OSError:
            pass
        else:
            raise AssertionError("the UART half was derived with no Mocha owner")


def _package_renders_from_its_own_uart_lines() -> None:
    # The host renders the package without the Mocha owners: the UART lines it reads
    # back are the emitted ones, and rendering around them reproduces every byte.
    with sandbox_tree(_tree()) as root:
        text = regs.emit(root, _REV)
        uart, block = regs.uart_lines(root), regs.block_lines(root)
    ensure(regs.emitted_uart_lines(text) == uart,
           "the package's UART lines read back in generator order")
    ensure(regs.render(uart, block, _REV) == text,
           "emit is render over the owners' lines and the stamp")
    moved = text.replace("UART_WDATA = 64'h1c", "UART_WDATA = 64'h2c")
    ensure(regs.render(regs.emitted_uart_lines(moved), block, _REV) == moved,
           "a UART value is left open to the guest command")
    _refused(regs.render, uart, block, "4b9bec92")


def _uart_lines_outside_the_generators_form_refuse() -> None:
    with sandbox_tree(_tree()) as root:
        text = regs.emit(root, _REV)
    status = "  localparam logic [63:0] UART_STATUS = 64'h14;"
    for changed in (
            text.replace(status + "\n", ""),                         # missing
            text.replace(status, f"{status}\n{status}"),              # declared twice
            text.replace(status, f"{status}\n/*\n{status}\n*/"),      # commented copy
            text.replace("64'h14;", "64'h014;"),                      # another spelling
            text.replace("64'h14;", "64'h14;  // status")):           # trailing text
        _refused(regs.emitted_uart_lines, changed)


def _tracked_package_renders_from_this_checkout() -> None:
    root = TOOLS.parent
    text = (root / regs.ARTIFACT).read_text(encoding="utf-8")
    ensure(regs.render(regs.emitted_uart_lines(text), regs.block_lines(root),
                       regs.recorded_revision(text)) == text,
           f"{regs.ARTIFACT} is what the generator renders around its own UART values")


def _refused(read: Callable[..., object], *args: object) -> None:
    try:
        read(*args)
    except ValueError:
        return
    raise AssertionError(f"{args!r} was accepted")


def _stamp_records_the_owner_revision() -> None:
    with sandbox_tree(_tree()) as root:
        text = regs.emit(root, _REV)
        ensure(regs.recorded_revision(text) == _REV,
               "the header's stamp reads back as the revision it was emitted at")
        ensure(text.splitlines()[4] == f"{regs.STAMP}{_REV}",
               "the stamp sits in the header beside the UART owners it describes")
        _refused(regs.emit, root, "4b9bec92")
    _refused(regs.recorded_revision, text.replace(regs.STAMP, "// UART: "))
    _refused(regs.recorded_revision, text + f"{regs.STAMP}{_REV}\n")


def _stamp_is_taken_from_the_owner_checkout_itself() -> None:
    def git(stdout: str, code: int = 0) -> CompletedProcess[str]:
        return CompletedProcess([], code, stdout, "")

    with sandbox_tree(_tree()) as root:
        with patch.object(regs.subprocess, "run", return_value=git(f"\n{_REV}\n")):
            ensure(regs.selected_revision(root) == _REV and _REV in regs.emit(root),
                   "a populated owner checkout's own commit is the one recorded")
        # An empty submodule directory resolves to the superproject, whose prefix
        # names the directory: its HEAD is not a commit any owner was read at.
        for refused in (git(f"{regs.UPSTREAM}/\n{_REV}\n"), git("", 128), git("\nHEAD\n")):
            with patch.object(regs.subprocess, "run", return_value=refused):
                _refused(regs.selected_revision, root)


def cases() -> list[Case]:
    return [Case("owners-drive-offsets-and-fields", _owners_drive_offsets_and_fields),
            Case("missing-or-duplicate-owners-refuse", _missing_or_duplicate_owners_refuse),
            Case("block-half-needs-no-mocha-owner", _block_half_needs_no_mocha_owner),
            Case("package-renders-from-its-own-uart-lines",
                 _package_renders_from_its_own_uart_lines),
            Case("uart-lines-outside-the-generators-form-refuse",
                 _uart_lines_outside_the_generators_form_refuse),
            Case("tracked-package-renders-from-this-checkout",
                 _tracked_package_renders_from_this_checkout),
            Case("stamp-records-the-owner-revision", _stamp_records_the_owner_revision),
            Case("stamp-is-taken-from-the-owner-checkout-itself",
                 _stamp_is_taken_from_the_owner_checkout_itself)]
