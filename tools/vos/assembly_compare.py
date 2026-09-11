# SPDX-License-Identifier: Apache-2.0
"""Compare stock compiler assembly under the M1.2b annotation-only contract.

The transformation operates on bytes. The small lexer only protects that
transformation and finds a nonempty instruction witness; it is no assembler.
"""

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

_ANNOTATION = re.compile(rb"([ \t]*# Compartment )[0-9]+([ \t]*(?:\r?\n)?)")
_REGISTER = r"x(?:[0-9]|[12][0-9]|3[01])"
_WITNESSES = (
    re.compile(r"ret"),
    re.compile(rf"mv[ \t]+{_REGISTER}[ \t]*,[ \t]*{_REGISTER}"),
    re.compile(rf"add[ \t]+{_REGISTER}[ \t]*,[ \t]*{_REGISTER}"
               rf"[ \t]*,[ \t]*{_REGISTER}"),
)
_ADDI = re.compile(rf"addi[ \t]+{_REGISTER}[ \t]*,[ \t]*{_REGISTER}"
                   r"[ \t]*,[ \t]*([+-]?[0-9]+)")
_LABEL = re.compile(r"(?:[A-Za-z_.$][A-Za-z_.$0-9]*|[0-9]+):[ \t]*")
_UNSUPPORTED = frozenset({
    ".macro", ".endm", ".purgem", ".altmacro", ".noaltmacro", ".exitm",
    ".rept", ".irp", ".irpc", ".endr", ".else", ".elseif", ".endif",
    ".pushsection", ".popsection", ".previous", ".include", ".incbin",
})


class UnsupportedInputError(ValueError):
    """The input falls outside the contract's lexical or witness envelope."""


@dataclass(frozen=True)
class InputIdentity:
    """Original bytes and computed counts; null counts mean inspection refused."""

    sha256: str
    byte_count: int
    annotations: int | None = None
    instruction_witnesses: int | None = None


@dataclass(frozen=True)
class Comparison:
    """One pair's verdict, with offsets in the normalized byte streams."""

    verdict: Literal["equal", "different", "unsupported"]
    reason: str
    left: InputIdentity
    right: InputIdentity
    first_difference: int | None = None
    left_line: int | None = None
    right_line: int | None = None

    @property
    def exit_code(self) -> int:
        """Successful equality, observed difference, and ineligible input differ."""
        return {"equal": 0, "different": 1, "unsupported": 2}[self.verdict]


def _statements(line: str, lineno: int) -> list[str]:
    """Find assembly statements without reading inside strings or comments."""
    statements: list[str] = []
    start = 0
    pos = 0
    quoted = False
    while pos < len(line):
        char = line[pos]
        if quoted:
            if char == "\\":
                pos += 2
                continue
            if char == '"':
                quoted = False
        elif char == "#":
            line = line[:pos]
            break
        elif char == '"':
            quoted = True
        elif line[pos:pos + 2] in ("/*", "*/"):
            raise UnsupportedInputError(f"line {lineno}: block comments are unsupported")
        elif char == ";":
            statements.append(line[start:pos].strip())
            start = pos + 1
        pos += 1
    if quoted:
        raise UnsupportedInputError(f"line {lineno}: multiline or unterminated quoted string")
    tail = line[start:].strip()
    if tail.endswith("\\"):
        raise UnsupportedInputError(f"line {lineno}: line continuation is unsupported")
    statements.append(tail)
    return statements


def _witness(statement: str) -> bool:
    if any(pattern.fullmatch(statement) for pattern in _WITNESSES):
        return True
    match = _ADDI.fullmatch(statement)
    if not match:
        return False
    # Trim redundant zeros before converting, including all-zero long inputs.
    digits = match[1].lstrip("+-").lstrip("0") or "0"
    sign = -1 if match[1].startswith("-") else 1
    return len(digits) <= 4 and -2048 <= sign * int(digits) <= 2047


def _prepare(data: bytes) -> tuple[bytes, InputIdentity]:
    """Normalize only eligible comment digits, retaining every other byte."""
    if any(byte > 126 or (byte < 32 and byte not in (9, 10, 13)) for byte in data):
        raise UnsupportedInputError("non-ASCII or unsupported control byte")
    if re.search(rb"\r(?!\n)", data):
        raise UnsupportedInputError("bare CR is not an admitted line ending")
    normalized: list[bytes] = []
    annotations = 0
    witnesses = 0
    in_text = False
    for lineno, raw in enumerate(data.splitlines(keepends=True), 1):
        statements = _statements(raw.rstrip(b"\r\n").decode("ascii"), lineno)
        for raw_statement in statements:
            statement = raw_statement
            while label := _LABEL.match(statement):
                statement = statement[label.end():]
            if not statement:
                continue
            directive = statement.split(maxsplit=1)[0]
            if directive in _UNSUPPORTED or directive.startswith(".if"):
                raise UnsupportedInputError(f"line {lineno}: {directive} is unsupported")
            if directive == ".text":
                in_text = statement == ".text"
            elif directive in (".data", ".bss", ".rodata"):
                in_text = False
            elif directive == ".section":
                section = statement[len(directive):].strip().split(",", 1)[0].strip()
                in_text = section == ".text"
            elif in_text and _witness(statement):
                witnesses += 1
        if annotation := _ANNOTATION.fullmatch(raw):
            normalized.append(annotation[1] + b"<compartment>" + annotation[2])
            annotations += 1
        else:
            normalized.append(raw)
    if not witnesses:
        raise UnsupportedInputError("no admitted instruction witness in an explicit .text section")
    return b"".join(normalized), InputIdentity(
        hashlib.sha256(data).hexdigest(), len(data), annotations, witnesses)


def compare(left: bytes, right: bytes) -> Comparison:
    """Compare one pair, refusing unsupported input even when bytes are identical."""
    identities = [InputIdentity(hashlib.sha256(data).hexdigest(), len(data))
                  for data in (left, right)]
    normalized: list[bytes] = []
    errors: list[str] = []
    for index, (side, data) in enumerate((("left", left), ("right", right))):
        try:
            stream, identities[index] = _prepare(data)
        except UnsupportedInputError as err:
            errors.append(f"{side}: {err}")
        else:
            normalized.append(stream)
    if errors:
        return Comparison("unsupported", "; ".join(errors), identities[0], identities[1])
    a, b = normalized
    if a == b:
        return Comparison("equal", "all bytes agree under the annotation-only contract",
                          identities[0], identities[1])
    offset = next((index for index, (x, y) in enumerate(zip(a, b, strict=False))
                   if x != y), min(len(a), len(b)))
    return Comparison("different", "bytes differ outside the permitted annotation digits",
                      identities[0], identities[1], offset, a[:offset].count(b"\n") + 1,
                      b[:offset].count(b"\n") + 1)
