# SPDX-License-Identifier: Apache-2.0
"""Generate [vos_device_regs_pkg.sv](../../rtl/vos_device_regs_pkg.sv) register constants from their owners.

UART constants come from `upstream/mocha` and carry a recorded submodule commit stamp;
block-device constants come from [block-device-contract.md](../../interfaces/block-device-contract.md)
and [block_device.sail](../../model/model/sys/block_device.sail). `rtl devicescheck`
checks the full regeneration against a populated `upstream/mocha` checkout, while
[K-88](checks/generated.py) checks the recorded submodule revision, UART line shapes,
and block-device lines on the host.
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

STAMP = f"// UART owner revision: {UPSTREAM} at "
STAMP_RE = re.compile(rf"(?m)^{re.escape(STAMP)}([0-9a-f]{{40}})$")
_OID_RE = re.compile(r"[0-9a-f]{40}")

UART_OFFSETS = ("STATUS", "RDATA", "WDATA")
UART_BITS = ("TXFULL", "RXFULL", "TXEMPTY", "TXIDLE", "RXIDLE", "RXEMPTY")
_HEX = "0|[1-9a-f][0-9a-f]*"
_DEC = "0|[1-9][0-9]*"


def _address(name: str, value: str) -> str:
    return f"  localparam logic [63:0] {name} = 64'h{value};"


def _count(name: str, value: str) -> str:
    return f"  localparam int unsigned {name} = {value};"


def _uart_forms() -> tuple[tuple[str, re.Pattern[str]], ...]:
    """Build exact-line regexes for each UART constant using the generator's line writers."""
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
    """Return the `HEAD` commit of the populated `upstream/mocha` checkout."""
    done = subprocess.run(["git", "-C", str(root / UPSTREAM), "rev-parse",
                           "--show-prefix", "HEAD"],
                          capture_output=True, text=True, check=False)
    lines = done.stdout.splitlines()
    if done.returncode or len(lines) != 2 or lines[0] or not _OID_RE.fullmatch(lines[1]):
        raise ValueError(f"{UPSTREAM}: not a populated checkout whose commit can be "
                         f"recorded ({done.stderr.strip() or done.stdout.strip()})")
    return lines[1]


def recorded_revision(text: str) -> str:
    """Extract the recorded `upstream/mocha` commit from a generated header."""
    found = STAMP_RE.findall(text)
    if len(found) != 1:
        raise ValueError(f"{ARTIFACT}: expected one recorded {UPSTREAM} revision, "
                         f"found {len(found)}")
    return str(found[0])


def uart_lines(root: Path) -> list[str]:
    """Read UART offset and status-bit declarations from a populated Mocha checkout."""
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
    """Extract and validate a package's UART declaration lines in generator order."""
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
    """Read block-device register and bound declarations from tracked owners."""
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
    """Render `vos_device_regs_pkg` from `uart` and `block` lines stamped at `stamp`."""
    if not _OID_RE.fullmatch(stamp):
        raise ValueError(f"{UPSTREAM}: {stamp!r} is not a full commit id")
    lines = ["// SPDX-License-Identifier: Apache-2.0",
             "// Generated by vos.device_regs from the owners below; rtl devicescheck checks it.",
             f"// UART: {UART}", f"// Status fields: {UART_SPEC}", f"{STAMP}{stamp}",
             f"// Block: {BLOCK}", f"// Model bounds: {BLOCK_MODEL}",
             "package vos_device_regs_pkg;", *uart, *block, "endpackage", ""]
    return "\n".join(lines)


def emit(root: Path, revision: str | None = None) -> str:
    """Generate `vos_device_regs_pkg.sv` stamped with `revision` or the checkout's commit."""
    uart = uart_lines(root)
    block = block_lines(root)
    stamp = selected_revision(root) if revision is None else revision
    return render(uart, block, stamp)
