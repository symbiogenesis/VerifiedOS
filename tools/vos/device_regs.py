# SPDX-License-Identifier: Apache-2.0
"""Generate the simulation wrappers' register constants from their owners.

The UART owners live behind the `upstream/mocha` gitlink, so the header records the
commit the populated owner checkout stood at when the constants were emitted. `rtl
devicescheck` regenerates the header and so holds that stamp against the checkout it
reads, and K-88's row for the header holds the committed stamp against the index's
gitlink, which is what makes a gitlink moved without a regeneration a host finding
rather than a guest-only one. The block owners are in every checkout, so the same row
renders the whole package on the host from them, the recorded stamp and the package's
own UART lines, read against their fixed names and order with only their values open.
Every byte but those values is therefore decided there; the values are the command's.
"""

import re
import subprocess
from pathlib import Path

UPSTREAM = "upstream/mocha"
UART = f"{UPSTREAM}/hw/vendor/lowrisc_ip/ip/uart/rtl/uart_reg_pkg.sv"
UART_SPEC = f"{UPSTREAM}/hw/vendor/lowrisc_ip/ip/uart/data/uart.hjson"
BLOCK = "interfaces/block-device-contract.md"
BLOCK_MODEL = "model/model/sys/block_device.sail"
ARTIFACT = "rtl/vos_device_regs_pkg.sv"

# The header line recording which owner commit the UART constants were read at.
STAMP = f"// UART owner revision: {UPSTREAM} at "
STAMP_RE = re.compile(rf"(?m)^{re.escape(STAMP)}([0-9a-f]{{40}})$")
_OID_RE = re.compile(r"[0-9a-f]{40}")

# The UART constants in the order the package declares them: the register offsets, then
# the status bit positions.
UART_OFFSETS = ("STATUS", "RDATA", "WDATA")
UART_BITS = ("TXFULL", "RXFULL", "TXEMPTY", "TXIDLE", "RXIDLE", "RXEMPTY")
# A value in the one spelling each declaration form writes it in.
_HEX = "0|[1-9a-f][0-9a-f]*"
_DEC = "0|[1-9][0-9]*"


def _address(name: str, value: str) -> str:
    return f"  localparam logic [63:0] {name} = 64'h{value};"


def _count(name: str, value: str) -> str:
    return f"  localparam int unsigned {name} = {value};"


def _uart_forms() -> tuple[tuple[str, re.Pattern[str]], ...]:
    """Each UART declaration's name and its whole line with the value left open.

    Built from the same line writers the generator uses, so the host reading cannot
    accept a spelling the generator would not write.
    """
    forms: list[tuple[str, re.Pattern[str]]] = []
    for name, line, value in (*((f"UART_{n}", _address, _HEX) for n in UART_OFFSETS),
                              *((f"UART_{n}_BIT", _count, _DEC) for n in UART_BITS)):
        before, _, after = line(name, "@").partition("@")
        forms.append((name, re.compile(f"{re.escape(before)}(?:{value}){re.escape(after)}")))
    return tuple(forms)


_UART_FORMS = _uart_forms()


def _one(pattern: str, text: str, label: str) -> str:
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise ValueError(f"{label}: expected one owner declaration, found {len(matches)}")
    value = matches[0].group(1)
    if not isinstance(value, str):
        raise TypeError(f"{label}: owner declaration has no string value")
    return value


def selected_revision(root: Path) -> str:
    """The commit the populated owner checkout stands at.

    Refused unless `upstream/mocha` is the top of its own repository: an empty
    submodule directory inside the superproject would otherwise answer with the
    superproject's HEAD, and the header would record a commit no owner was read at.
    """
    done = subprocess.run(["git", "-C", str(root / UPSTREAM), "rev-parse",
                           "--show-prefix", "HEAD"],
                          capture_output=True, text=True, check=False)
    lines = done.stdout.splitlines()
    if done.returncode or len(lines) != 2 or lines[0] or not _OID_RE.fullmatch(lines[1]):
        raise ValueError(f"{UPSTREAM}: not a populated checkout whose commit can be "
                         f"recorded ({done.stderr.strip() or done.stdout.strip()})")
    return lines[1]


def recorded_revision(text: str) -> str:
    """The owner commit a generated header records, or a refusal naming why none is."""
    found = STAMP_RE.findall(text)
    if len(found) != 1:
        raise ValueError(f"{ARTIFACT}: expected one recorded {UPSTREAM} revision, "
                         f"found {len(found)}")
    return str(found[0])


def uart_lines(root: Path) -> list[str]:
    """The UART constants, read from owners only a populated Mocha checkout carries."""
    uart = (root / UART).read_text(encoding="utf-8")
    spec = (root / UART_SPEC).read_text(encoding="utf-8")
    lines: list[str] = []
    for name in UART_OFFSETS:
        value = _one(r"\bUART_" + name + r"_OFFSET\s*=\s*\d+'h\s*([0-9a-fA-F]+)\s*;", uart, name)
        lines.append(_address(f"UART_{name}", f"{int(value, 16):x}"))
    for name in UART_BITS:
        value = _one(r'bits:\s*"(\d+)"\s+name:\s*"' + name + '"', spec, name)
        lines.append(_count(f"UART_{name}_BIT", str(int(value))))
    return lines


def emitted_uart_lines(text: str) -> list[str]:
    """A package's UART declarations in generator order, whatever their values.

    Each name is declared by exactly one whole line in the generator's own form, or the
    package is refused: a second declaration, a commented copy in that form, a line in
    another spelling or a missing one is not something the generator writes.
    """
    lines = text.split("\n")
    found: list[str] = []
    for name, form in _UART_FORMS:
        matches = [line for line in lines if form.fullmatch(line)]
        if len(matches) != 1:
            raise ValueError(f"{ARTIFACT}: expected one {name} declaration in the "
                             f"generator's form, found {len(matches)}")
        found.append(matches[0])
    return found


def block_lines(root: Path) -> list[str]:
    """The block constants, read from owners every checkout carries.

    K-88's host inspector renders the package around these, so the block half is
    decided without the Mocha checkout the UART half needs.
    """
    block = (root / BLOCK).read_text(encoding="utf-8")
    model = (root / BLOCK_MODEL).read_text(encoding="utf-8")
    lines: list[str] = []
    for name in ("VERSION", "BLOCK_BYTES", "BLOCK_COUNT", "STATUS", "RESULT", "BLOCK", "COMMAND", "ACK"):
        value = _one(r"(?m)^\| `0x([0-9a-fA-F]+)` \| `" + name + r"` \|", block, name)
        lines.append(_address(f"BLK_{name}", f"{int(value, 16):x}"))
    value = _one(r"(?m)^\| `0x([0-9a-fA-F]+) \+ 8\*i`,", block, "DATA")
    lines.append(_address("BLK_DATA", f"{int(value, 16):x}"))
    for name in ("max_bytes", "max_block_bytes"):
        value = _one(r"(?m)^let blkdev_" + name + r"\s*:\s*int\(\d+\)\s*=\s*(\d+)$", model, name)
        lines.append(_count(f"BLK_{name.upper()}", str(int(value))))
    return lines


def render(uart: list[str], block: list[str], stamp: str) -> str:
    """The package around its two halves' declarations, stamped at `stamp`.

    `emit` writes the package through this, and K-88's host inspector renders the
    tracked package through it from that package's own UART lines, so the two cannot
    disagree about any byte outside those lines' values.
    """
    if not _OID_RE.fullmatch(stamp):
        raise ValueError(f"{UPSTREAM}: {stamp!r} is not a full commit id")
    lines = ["// SPDX-License-Identifier: Apache-2.0",
             "// Generated by vos.device_regs from the owners below; rtl devicescheck checks it.",
             f"// UART: {UART}", f"// Status fields: {UART_SPEC}", f"{STAMP}{stamp}",
             f"// Block: {BLOCK}", f"// Model bounds: {BLOCK_MODEL}",
             "package vos_device_regs_pkg;", *uart, *block, "endpackage", ""]
    return "\n".join(lines)


def emit(root: Path, revision: str | None = None) -> str:
    """The generated package, stamped with `revision` or the checkout's own commit."""
    uart = uart_lines(root)
    block = block_lines(root)
    stamp = selected_revision(root) if revision is None else revision
    return render(uart, block, stamp)
