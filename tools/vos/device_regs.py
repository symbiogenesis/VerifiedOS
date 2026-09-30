# SPDX-License-Identifier: Apache-2.0
"""Generate the simulation wrappers' register constants from their owners.

The UART owners live behind the `upstream/mocha` gitlink, so the header records the
commit the populated owner checkout stood at when the constants were emitted. `rtl
devicescheck` regenerates the header and so holds that stamp against the checkout it
reads, and K-88's row for the header holds the committed stamp against the index's
gitlink, which is what makes a gitlink moved without a regeneration a host finding
rather than a guest-only one. The block owners are in every checkout, so the same row
re-derives the block constants on the host and compares them line for line.
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
# A package line declaring one of the block constants, whatever its value.
BLOCK_LINE_RE = re.compile(r"\s*localparam\b[^=]*\bBLK_\w+\s*=")


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
    for name in ("STATUS", "RDATA", "WDATA"):
        value = _one(r"\bUART_" + name + r"_OFFSET\s*=\s*\d+'h\s*([0-9a-fA-F]+)\s*;", uart, name)
        lines.append(f"  localparam logic [63:0] UART_{name} = 64'h{int(value, 16):x};")
    for name in ("TXFULL", "RXFULL", "TXEMPTY", "TXIDLE", "RXIDLE", "RXEMPTY"):
        value = _one(r'bits:\s*"(\d+)"\s+name:\s*"' + name + '"', spec, name)
        lines.append(f"  localparam int unsigned UART_{name}_BIT = {int(value)};")
    return lines


def block_lines(root: Path) -> list[str]:
    """The block constants, read from owners every checkout carries.

    K-88's host inspector compares these with the tracked package's `BLK_` lines, so
    the block half is decided without the Mocha checkout the UART half needs.
    """
    block = (root / BLOCK).read_text(encoding="utf-8")
    model = (root / BLOCK_MODEL).read_text(encoding="utf-8")
    lines: list[str] = []
    for name in ("VERSION", "BLOCK_BYTES", "BLOCK_COUNT", "STATUS", "RESULT", "BLOCK", "COMMAND", "ACK"):
        value = _one(r"(?m)^\| `0x([0-9a-fA-F]+)` \| `" + name + r"` \|", block, name)
        lines.append(f"  localparam logic [63:0] BLK_{name} = 64'h{int(value, 16):x};")
    value = _one(r"(?m)^\| `0x([0-9a-fA-F]+) \+ 8\*i`,", block, "DATA")
    lines.append(f"  localparam logic [63:0] BLK_DATA = 64'h{int(value, 16):x};")
    for name in ("max_bytes", "max_block_bytes"):
        value = _one(r"(?m)^let blkdev_" + name + r"\s*:\s*int\(\d+\)\s*=\s*(\d+)$", model, name)
        lines.append(f"  localparam int unsigned BLK_{name.upper()} = {int(value)};")
    return lines


def emitted_block_lines(text: str) -> list[str]:
    """The `BLK_` constant lines a generated package carries, in their order."""
    return [line for line in text.splitlines() if BLOCK_LINE_RE.match(line)]


def emit(root: Path, revision: str | None = None) -> str:
    """The generated package, stamped with `revision` or the checkout's own commit."""
    uart = uart_lines(root)
    block = block_lines(root)
    stamp = selected_revision(root) if revision is None else revision
    if not _OID_RE.fullmatch(stamp):
        raise ValueError(f"{UPSTREAM}: {stamp!r} is not a full commit id")
    lines = ["// SPDX-License-Identifier: Apache-2.0",
             "// Generated by vos.device_regs from the owners below; rtl devicescheck checks it.",
             f"// UART: {UART}", f"// Status fields: {UART_SPEC}", f"{STAMP}{stamp}",
             f"// Block: {BLOCK}", f"// Model bounds: {BLOCK_MODEL}",
             "package vos_device_regs_pkg;", *uart, *block, "endpackage", ""]
    return "\n".join(lines)
