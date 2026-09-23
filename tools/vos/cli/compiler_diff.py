#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""M1.2f's two acceptance loops over the contained purecap backend.

    tools/run.py compiler-diff program --ccomp PATH (SOURCE.c ... | --generate N [--perturb]
                                       [--pattern NAME]) [--interp] [--simulator PATH | --lane]
    tools/run.py compiler-diff component (--wasm MODULE | --host-record FILE)
                                         (--c SOURCE --ccomp PATH | --elf FILE
                                          | --purecap-record FILE) [--simulator PATH | --lane]
    tools/run.py compiler-diff generate --out DIR [--count N] [--seed S] [--perturb]

**The program level** feeds C through `ccomp -S` in a fresh directory, hands the emitted
stream to the in-tree assembler ([vos/asm.py](../asm.py)) and the image composer
([vos/image.py](../image.py)) under the harness stated below, and runs the image on the
golden emulator with the invocation `run.py model corpus` makes, asking the two questions
[differential-corpus.md](../../../docs/assurance/differential-corpus.md) §6 asks of a
member: the program's own, its HTIF verdict, and the rig's, the digest of its normalized
commit trace. The compiler is never in the tree: `--ccomp` names an executable outside every
checkout, which is M1.1a's containment, and the driver records the path and the digest of
what it found there rather than carrying either. `--ccomp-arg` passes the backend's own
flags, `-fverifiedos-typed` selecting its typed purecap route. `--interp` also runs the
source through the same compiler's reference interpreter, and an image whose `main`
returned something else is `source-disagrees`; a narrowing program has no such reading.

**The generated campaign** is deterministic in its seed and stays inside the selected
scalar source profile: pointers through stack memory, struct fields and whole-struct
copies, calls in both directions, arguments past the eight argument registers, a pointer
or null chosen on a branch, more live pointers across calls than registers, and a local
array narrowed through the plan-bound `csetbounds` primitive against an independent plan
the driver writes for that program. Every expected constant is computed by the generator;
`--pattern` selects a subset. `--perturb` is its negative control: each program moves
one check's constant off by one and must fail at exactly that check.

**The refusal verdict.** A stream the dialect does not spell is scanned before it is
assembled, and every mnemonic, directive and section the assembler refuses is reported by
name and by line of the emitted stream, never as an opaque failure. Stock `ccomp -S`
writes lp64d RV64, which R-18-002 forbids as a target; `--expect-refusal` makes that
verdict the green one. A refused *mnemonic* is the backend's to close, and a refused
*directive* is the seam between CompCert's printer and the assembler's vocabulary, which
the driver reports and does not translate.

**The harness.** A stream that assembles is wrapped before it is composed: `_start` moves
the store-side root out of `c1` into the reserved `c4` and derives the stack and the
`tohost` authority from it,
the way every corpus member derives an authority (R-15-001c), installs a trap handler
through MTCC, calls `main`, and folds the return into the exit code the corpus convention
reads back: `1` for success, `(code << 1) | 1` otherwise, where a code below `0x100` is
`main`'s return masked to a byte (a nonzero return with a zero low byte reads as `0xFF`)
and a code at or above it is `0x100 | mcause` for a trap that reached the handler. The
frame `main` itself expects is the backend's. The harness supplies a bounded local stack
with store-local permission under the selected scalar convention in `purecap-abi.md`.
It is a test composition; the firmware handoff remains a separate acceptance input.

**The third reading of the trace** is M1.7's own test that a capability went through
memory rather than only through the register file: one aligned eight-byte `W` whose tag
is set, read back by an `R` at the same address with the same value and tag before any
overlapping write. It is reported beside the digest; a frame's saved return capability
satisfies it as well as a program's own pointer store does.

**The component level** holds one Gallina component's host run on the CertiCoq-to-Wasm
oracle against its purecap run under one declared output encoding: the side's exit
verdict, which is the Wasm host's process status on one side and the image's HTIF exit
code on the other, plus the SHA-256 and the length of the bytes the component emitted,
the runner's standard output on one side and the emulator's terminal log, the HTIF console,
on the other. `--c` lowers the component's C through the backend and runs it under the
component harness, which reads `main`'s result as the one boolean `run_demo.mjs` reads
from the Wasm module: it prints `true` or `false` on the HTIF console and exits 0 or 1.
Either side is written as a record that the other side's run is later held against, the
report binds the module, source, compiler, stream, image, emulator and profile by digest,
and the comparator names the first field that disagrees, or the first byte where both
sides' bytes are in hand.

**What this does not decide, stated rather than implied.** A green run says this machine,
this compiler and these programs agree; it never says a lowering is correct, R-05-023a's
instrument being deferred hardening. A component's C is a hand-written refinement of its
Gallina, so agreement is differential evidence over its battery and not a refinement
proof. Every report carries `milestone_acceptance: open`, because a report is evidence for
one run and the milestone closes on a reviewed reading of recorded runs.
"""

import argparse
import functools
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from vos import asm, dialect, env, image, trace
from vos import corpus as corpus_mod
from vos.cli import Table, dispatch
from vos.dialect import AsmError
from vos.jsonc import Json

# The harness's stack: a region of the data section sized for the small programs the
# generator writes rather than for a component, derived to a capability off the store-side
# root the way every corpus member derives its authority (R-15-001c).
STACK_BYTES: Final = 16384

# Where a trap's cause lands in the HTIF exit code. `main`'s return occupies the byte below
# it, so the two readings of one code cannot collide.
TRAP_BASE: Final = 0x100

# The same bound `run.py model corpus` runs a member under.
INST_LIMIT: Final = 1_000_000
COMPILE_TIMEOUT: Final = 120
RUN_TIMEOUT: Final = 60

# The declared output encoding's name, carried by every record so that a comparator handed
# a file from some other tool refuses it by name rather than reading a field that is not
# there as a zero.
ENCODING: Final = "vos-component-output/1"

# How the Wasm oracle is run, relative to the repository root: the pinned Node through the
# script that verifies it, then the host that decodes one boolean (tools/wasm-oracle).
NODE_RUNNER: Final[tuple[str, ...]] = (
    "sh", "tools/wasm-oracle/node.sh", "--stack-size=10000000",
    "tools/wasm-oracle/run_demo.mjs")

# What a run's evidence is a function of, beside the compiler it was pointed at.
SOURCES: Final[tuple[str, ...]] = (
    "tools/vos/cli/compiler_diff.py", "tools/vos/asm.py", "tools/vos/image.py",
    "tools/generated/dialect-table.json", "docs/assurance/differential-corpus.md",
    "docs/implementation/contracts/purecap-abi.md", "model/model/core/cap_common.sail")

# The verdict a program can end in. Listed once, in the order the summary counts them.
VERDICTS: Final[tuple[str, ...]] = (
    "ccomp-refused", "dialect-refused", "assembled", "pass", "fail", "trap",
    "source-disagrees", "no-verdict")

MASK64: Final = (1 << 64) - 1


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# =====================================================================================
# The scan: what the in-tree assembler refuses in an emitted stream, by name and by line
# =====================================================================================


@dataclass(frozen=True)
class Refusal:
    """One line of an emitted stream the in-tree assembler will not take, and why.

    `kind` is `mnemonic` for a name the dialect table and the pseudo-instructions do not
    spell, `directive` for a directive the parser does not know, `section` for a `.section`
    naming one the image does not have, `label` for a numeric local label, which the
    assembler's label grammar has no form for, `relocation` for a `%pcrel_hi(...)`-style
    operator, which the assembler has none of by design (R-15-002b, R-15-036l: layout is
    absolute, so there is nothing to relocate), `operand` for a known mnemonic or directive
    whose operands the assembler refused, `symbol` for a stream that defines no `main`, and
    `layout` for an image the composer cannot place. `line` is 1-based in the emitted
    stream, and 0 where the refusal is not a line's.
    """

    kind: str
    name: str
    line: int
    detail: str = ""


_LABEL_RE = re.compile(r"([A-Za-z_.$][A-Za-z_.$0-9]*)\s*:")
_NUMERIC_LABEL_RE = re.compile(r"(\d+)\s*:")
_RELOCATION_RE = re.compile(r"%[A-Za-z_]+\(")
_ASM_ERROR_RE = re.compile(r"^(.*?):(\d+): (.*)$", re.DOTALL)


def normalize(stream: str) -> str:
    """The emitted stream with every tab a space, which is the one rewrite the driver makes.

    CompCert's printer separates a mnemonic from its operands with a tab and the assembler's
    line parse splits the two on a space alone, so an unnormalized stream is refused whole,
    every instruction reading as a mnemonic with its first operand glued on. A tab inside a
    string literal would move with the rest, which the generator never writes and a reader
    of the refusal list would see as a changed `.ascii`.
    """
    return stream.replace("\t", " ")


def _split(raw: str) -> tuple[list[str], str]:
    """One line as the assembler reads it: the labels it declares, and what follows them
    once the comment is gone.

    A numeric local label is taken off the front too, spelled with its colon so a reader
    tells `1:` from a symbol: the assembler does not read one, and leaving it in place
    would make the mnemonic behind it read as the refusal.
    """
    text = raw.split("#", 1)[0].split("//", 1)[0].strip()
    labels: list[str] = []
    while text:
        label = _LABEL_RE.match(text) or _NUMERIC_LABEL_RE.match(text)
        if not label:
            break
        labels.append(label.group(1) + (":" if label.re is _NUMERIC_LABEL_RE else ""))
        text = text[label.end():].strip()
    return labels, text


def _head(raw: str) -> tuple[str, str] | None:
    """A line's mnemonic or directive and its operand text, or `None` for a line carrying
    neither."""
    _, text = _split(raw)
    if not text:
        return None
    head, _, rest = text.partition(" ")
    return head.lower(), rest.strip()


def _directive_refusal(head: str, rest: str, number: int) -> Refusal | None:
    """Whether the assembler takes this directive line on its own, and how it refuses it.

    The parser is asked rather than a list of its directives restated here: the line is
    parsed alone, which is enough to decide a directive's name and a section's, and an
    operand the parser refuses is reported as the parser words it.
    """
    try:
        asm.Assembler(f"{head} {rest}".strip(), "stream")
    except AsmError as exc:
        said = str(exc).partition(": ")[2] or str(exc)
        if said.startswith("no directive"):
            return Refusal("directive", head, number)
        if said.startswith("no section"):
            return Refusal("section", rest.partition(",")[0].strip(), number)
        return Refusal("operand", head, number, said)
    return None


def refusals(stream: str) -> list[Refusal]:
    """Every line of `stream` the assembler refuses by name, before anything is laid out.

    A mnemonic is decided against the dialect table and the pseudo-instructions, a
    directive by parsing its line alone. Operand-level refusals of an instruction are not
    found here, because deciding one needs the layout; `assemble` reports those.
    """
    found: list[Refusal] = []
    for number, raw in enumerate(normalize(stream).splitlines(), 1):
        labels, text = _split(raw)
        found += [Refusal("label", label, number) for label in labels if label[0].isdigit()]
        found += [Refusal("relocation", found_at.group()[:-1], number)
                  for found_at in _RELOCATION_RE.finditer(text)]
        parsed = _head(raw)
        if parsed is None:
            continue
        head, rest = parsed
        if head.startswith("."):
            refused = _directive_refusal(head, rest, number)
            if refused is not None:
                found.append(refused)
        elif head not in asm.PSEUDOS and head not in dialect.TABLE:
            found.append(Refusal("mnemonic", head, number))
    return found


def _defines_main(stream: str) -> bool:
    return any("main" in _split(raw)[0] for raw in stream.splitlines())


# =====================================================================================
# The harness, and assembling a stream under it
# =====================================================================================

_SETUP: Final = f"""\
        .text
        .globl _start
_start:
        cmove   c4, c1
        la      c9, __vos_handler
        cspecialrw cnull, mtcc, c9
        li      t0, __vos_stack
        csetaddr csp, c4, t0
        li      t1, {STACK_BYTES}
__vos_stack_bounds:
        csetbounds csp, csp, t1
        li      t1, 0xFFE
        candperm csp, csp, t1
        li      t0, __vos_stack_top
        csetaddr csp, csp, t0
        call    main
"""

PROLOGUE: Final = f"""\
# The M1.2f driver's harness around an emitted stream. Every authority is derived off the
# store-side root (R-15-001c). c4 is reserved by the selected scalar ABI; c8, like every
# allocatable register, can be overwritten by main. Clearing expanded permission bit 0
# removes globality while retaining root_data_cap's store-local stack shape.
{_SETUP}\
        beqz    a0, __vos_pass
        andi    gp, a0, 0xFF
        bnez    gp, __vos_fail
        li      gp, 0xFF
__vos_fail:
        slli    t0, gp, 1
        ori     t0, t0, 1
        j       __vos_exit
__vos_pass:
        li      t0, 1
__vos_exit:
        li      t1, tohost
        csetaddr c31, c4, t1
        sd      t0, 0(c31)
__vos_halt:
        j       __vos_halt
__vos_handler:
        csrr    t0, mcause
        andi    t0, t0, 0xFF
        ori     gp, t0, 0x100
        j       __vos_fail
# --- the emitted stream follows ---
"""

# HTIF's terminal device: device 1, command 1, the byte in the payload (the `htif_store`
# clause of model/model/sys/platform.sail), which the emulator writes to its terminal log.
HTIF_PUTCHAR: Final = (1 << 56) | (1 << 48)


def _put(text: str) -> str:
    return "".join(f"        li      t0, {HTIF_PUTCHAR | ord(ch):#x}\n"
                   f"        sd      t0, 0(c31)\n" for ch in text)


COMPONENT_PROLOGUE: Final = f"""\
# The M1.2f driver's component harness: the same setup, then main's result read as one
# boolean the way tools/wasm-oracle/run_demo.mjs reads the Wasm module's. main returns 0
# for true; the harness prints true or false on the HTIF console and exits 0 or 1, the
# host runner's process status for the same answer. A trap exits with 0x100 | mcause
# and prints nothing.
{_SETUP}\
        li      t1, tohost
        csetaddr c31, c4, t1
        beqz    a0, __vos_true
{_put("false" + chr(10))}\
        li      t0, 3
        j       __vos_exit
__vos_true:
{_put("true" + chr(10))}\
        li      t0, 1
__vos_exit:
        sd      t0, 0(c31)
__vos_halt:
        j       __vos_halt
__vos_handler:
        csrr    t0, mcause
        andi    t0, t0, 0xFF
        ori     t0, t0, 0x100
        slli    t0, t0, 1
        ori     t0, t0, 1
        li      t1, tohost
        csetaddr c31, c4, t1
        j       __vos_exit
# --- the emitted stream follows ---
"""

EPILOGUE: Final = f"""\
# --- the emitted stream ends ---
        .data
        .align  3
tohost:
        .dword  0
        .align  8
__vos_stack:
        .space  {STACK_BYTES}
__vos_stack_top:
"""

# Where the stream's first line sits in the program harness's composite, so a layout-time
# refusal can be named by the stream's own line.
STREAM_OFFSET: Final = PROLOGUE.count("\n")


def compose(stream: str, prologue: str = PROLOGUE) -> str:
    """The composite the assembler is handed: the harness around the normalized stream."""
    body = normalize(stream)
    if body and not body.endswith("\n"):
        body += "\n"
    return prologue + body + EPILOGUE


def assemble(stream: str, name: str, elf: Path,
             prologue: str = PROLOGUE) -> tuple[list[Refusal], int]:
    """Assemble `stream` under the harness into `elf`.

    Returns the refusals found and the image's byte count; the image is written only where
    the list is empty. The scan runs first so that a stream the dialect refuses is reported
    whole rather than at its first refused line, and the layout runs second so that an
    operand the parser could not decide alone is still named by its line.
    """
    found = refusals(stream)
    if found:
        return found, 0
    if not _defines_main(stream):
        return [Refusal("symbol", "main", 0, "the stream defines no `main`")], 0
    assembler = asm.Assembler(compose(stream, prologue), name)
    try:
        sections, symbols, entry = assembler.assemble()
    except AsmError as exc:
        return [_layout_refusal(exc, stream, prologue.count("\n"))], 0
    text = sum(len(s.data) for s in sections if s.name == ".text")
    if text > asm.DATA_BASE - asm.TEXT_BASE:
        return [Refusal("layout", ".text", 0,
                        f"{text} bytes of text reach the data section at "
                        f"{asm.DATA_BASE:#x}")], 0
    image.write_elf(elf, sections, symbols, entry)
    return [], sum(len(s.data) for s in sections)


def _layout_refusal(exc: AsmError, stream: str, offset: int) -> Refusal:
    """An assembler diagnostic over the composite, named by the stream's own line;
    `offset` is the line count of the harness prologue ahead of the stream."""
    said = str(exc)
    matched = _ASM_ERROR_RE.match(said)
    if matched is None:
        return Refusal("operand", "?", 0, said)
    number = int(matched.group(2)) - offset
    message = matched.group(3)
    lines = normalize(stream).splitlines()
    if 1 <= number <= len(lines):
        parsed = _head(lines[number - 1])
        return Refusal("operand", parsed[0] if parsed else "?", number, message)
    # Outside the stream is the harness, and a harness that does not assemble is this
    # driver's defect rather than the stream's; it is still reported and never raised,
    # because a run's report is the artifact and a traceback is not one.
    return Refusal("operand", "harness", 0, f"line {matched.group(2)} of the composite: "
                                            f"{message}")


# =====================================================================================
# The compiler, and the emulator
# =====================================================================================


@dataclass(frozen=True)
class Compiled:
    """One `ccomp -S`: how it was asked, what it said, and the stream it wrote."""

    argv: tuple[str, ...]
    exit_code: int
    said: str
    stream: str | None
    stream_sha256: str
    lines: int


def compile_c(ccomp: list[str], source: Path, fresh: Path,
              timeout: int = COMPILE_TIMEOUT) -> Compiled:
    """Run `ccomp -S` over one source in `fresh`, a directory holding nothing else.

    The source is copied in and the compiler is run there. This working directory is
    not an OS sandbox. Remove any previous assembly first, so a reused --keep directory
    cannot supply a successful invocation that wrote nothing with stale output. The
    argv records the compiler's path and two names relative to this directory.
    """
    fresh.mkdir(parents=True, exist_ok=True)
    copied = fresh / source.name
    shutil.copyfile(source, copied)
    out = fresh / f"{source.stem}.s"
    out.unlink(missing_ok=True)
    argv = [*ccomp, "-S", copied.name, "-o", out.name]
    said = ""
    exit_code = -1
    try:
        done = subprocess.run(argv, cwd=fresh, capture_output=True, encoding="utf-8",
                              errors="replace", timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        said = f"no exit within {timeout}s"
    except OSError as err:
        said = f"could not run: {err}"
    else:
        exit_code = done.returncode
        said = (done.stderr + done.stdout).strip()[:600]
    if exit_code != 0 or not out.is_file():
        return Compiled(tuple(argv), exit_code, said or "(wrote nothing)", None, "", 0)
    raw = out.read_bytes()
    stream = raw.decode("utf-8", errors="replace")
    return Compiled(tuple(argv), 0, said, stream, _sha256(raw), len(stream.splitlines()))


@dataclass(frozen=True)
class Ran:
    """One emulator run under the corpus's two questions, and the third reading."""

    verdict: str
    code: int | None
    records: int
    digest: str
    cap_roundtrip: bool
    emitted: bytes
    detail: str


_FAILURE_RE = re.compile(r"FAILURE: (\d+)")


def htif_verdict(said: str, returncode: int) -> tuple[str, int | None, str]:
    """Read the emulator's output back as the program's own verdict.

    The exit code is what the program left in the harness's `gp`, on the corpus's own
    convention; the harness puts `main`'s return below `TRAP_BASE` and a trap's cause at or
    above it. An emulator that printed neither line gave no verdict, and a trap loop is
    that case named, because it is what a fault inside the handler itself looks like.
    """
    failed = _FAILURE_RE.search(said)
    if failed:
        code = int(failed.group(1))
        if code >= TRAP_BASE:
            return "trap", code, f"HTIF {code}: cause {code - TRAP_BASE} reached the handler"
        return "fail", code, f"HTIF {code}: main returned {code}"
    if returncode == 0 and re.search(r"^SUCCESS\s*$", said, re.MULTILINE):
        return "pass", 0, "HTIF 0"
    if "trap loop" in said:
        return "no-verdict", None, "the emulator detected a trap loop"
    return "no-verdict", None, f"rc={returncode}, no HTIF verdict"


def cap_roundtrip(records: list[str]) -> bool:
    """Find a stored capability read back intact in normalized commit records.

    R-15-203's capability granule is eight bytes. Every write touching a candidate's
    granule invalidates it, including an ordinary byte store or a block zeroing. A new
    aligned tagged capability write can then supply a fresh candidate. Malformed memory
    records cannot be skipped because a skipped write could hide an intervening change.
    """
    written: dict[int, str] = {}
    for record in records:
        parts = record.split()
        if not parts or parts[0] not in ("W", "R"):
            continue
        if trace.COMMIT_RE.fullmatch(record) is None:
            return False
        address, width = int(parts[1], 16), int(parts[2])
        if width <= 0 or len(parts[4]) != width * 2:
            return False
        capability = width == 8 and address % 8 == 0 and parts[3] == "1"
        if parts[0] == "W":
            for granule in range(address // 8, (address + width - 1) // 8 + 1):
                written.pop(granule * 8, None)
            if capability:
                written[address] = parts[4]
        elif capability and written.get(address) == parts[4]:
            return True
    return False


def run_image(simulator: list[str], profile: Path, elf: Path, workdir: Path,
              timeout: int = RUN_TIMEOUT, inst_limit: int = INST_LIMIT) -> Ran:
    """Run one image the way `run.py model corpus` runs a member, plus the terminal log.

    The commit trace is read off the merged streams by shape, as the corpus runner reads
    it; the terminal log is the HTIF console, which is where a component's emitted bytes
    land, and it is a file rather than the console so that the emulator's own lines and
    the trace never mix with them.
    """
    term = workdir / f"{elf.stem}.term"
    term.unlink(missing_ok=True)
    argv = [*simulator, "--config", str(profile), "--trace-commit",
            "--inst-limit", str(inst_limit), "--terminal-log", str(term), str(elf)]
    try:
        done = subprocess.run(argv, capture_output=True, encoding="utf-8",
                              errors="replace", timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return Ran("no-verdict", None, 0, "", False, b"",
                   f"no HTIF write within {timeout}s")
    except OSError as err:
        return Ran("no-verdict", None, 0, "", False, b"", f"the emulator could not run: {err}")
    said = done.stdout + done.stderr
    records = trace.normalize_commit(said.splitlines())
    emitted = term.read_bytes() if term.is_file() else b""
    verdict, code, detail = htif_verdict(said, done.returncode)
    if verdict == "pass" and not records:
        verdict, code, detail = "no-verdict", None, "HTIF 0 without a commit trace"
    return Ran(verdict, code, len(records), trace.digest(records), cap_roundtrip(records),
               emitted, detail)


# =====================================================================================
# The generator: small FP-free C programs in the selected scalar source profile
# =====================================================================================


@dataclass(frozen=True)
class Program:
    """One input: its name, the pattern it exercises, its text, how many checks it
    carries, and what `main` is expected to return.

    Each check returns its own number from `main` on the corpus's convention that a
    failure names the check. `expect` is 0 for an ordinary program and, for a perturbed
    one, the number of the check whose expected constant was moved off by one, so the
    campaign's negative control names the check it must fail at. `narrowing` is the byte
    length of the one local the program narrows through the plan-bound `csetbounds`
    primitive, or 0 where it narrows nothing."""

    name: str
    pattern: str
    source: str
    checks: int
    expect: int = 0
    narrowing: int = 0


class _Draw:
    """A deterministic draw, so that a seed names one campaign on every machine and every
    interpreter: Knuth's MMIX multiplier and increment over 64 bits, the top bits taken."""

    def __init__(self, seed: int) -> None:
        self.state = (seed * 6364136223846793005 + 1442695040888963407) & MASK64

    def between(self, low: int, high: int) -> int:
        self.state = (self.state * 6364136223846793005 + 1442695040888963407) & MASK64
        return low + (self.state >> 33) % (high - low + 1)


class _Expect:
    """The expected constant of each numbered check, one of them moved off by one when
    the program is the perturbed twin. The draws never depend on the perturbation, so a
    perturbed campaign differs from its seed's ordinary one in exactly one constant per
    program."""

    def __init__(self, perturb: int) -> None:
        self.perturb = perturb

    def __call__(self, check: int, value: int) -> int:
        return value + (1 if check == self.perturb else 0)


# The generated programs stay inside the selected scalar source profile
# (docs/implementation/contracts/compiler-source-values.md): no global object, whose
# authority the profile binds only through a composition; no pointer/integer cast; no
# pointer equality or ordering beyond comparison with null; no recursion; no switch.
# Every constant a check compares against is computed here, independently of the
# compiler and of the emulator.


def _memory(name: str, draw: _Draw, e: _Expect) -> tuple[str, int, int]:
    """Pointers stored to a stack array of pointers, reloaded through an index the
    program computes, written through, and copied pointer by pointer."""
    n = draw.between(4, 7)
    m, c = draw.between(3, 19), draw.between(1, 50)
    r = draw.between(1, n - 1)
    t = draw.between(0, n - 1)
    d = draw.between(1, 9)
    cells = [i * m + c for i in range(n)]
    hit = (t + r) % n
    after = list(cells)
    after[hit] += d
    via_copy = after[((t + 1) % n + r) % n]
    return f"""\
/* {name}: pointers stored to a stack array, reloaded through a computed index. */
int main(void)
{{
    long cells[{n}];
    long *slots[{n}];
    long *copies[{n}];
    long *p;
    long i, k, sum;
    for (i = 0; i < {n}; i++) {{
        cells[i] = i * {m} + {c};
        slots[i] = &cells[(i + {r}) % {n}];
    }}
    k = 0;
    for (i = 0; i < {n}; i++)
        if (cells[i] == {cells[t]})
            k = i;
    p = slots[k];
    if (*p != {e(1, cells[hit])})
        return 1;
    *p = *p + {d};
    if (cells[{hit}] != {e(2, after[hit])})
        return 2;
    for (i = 0; i < {n}; i++)
        copies[i] = slots[i];
    if (*copies[(k + 1) % {n}] != {e(3, via_copy)})
        return 3;
    sum = 0;
    for (i = 0; i < {n}; i++)
        sum = sum + *copies[i];
    if (sum != {e(4, sum(after))})
        return 4;
    return 0;
}}
""", 4, 0


def _struct(name: str, draw: _Draw, e: _Expect) -> tuple[str, int, int]:
    """Two pointers held in struct fields beside mixed-width scalars, the struct copied
    whole and reached through a pointer to the copy."""
    a, b = draw.between(2, 90), draw.between(1, 60)
    g, s = draw.between(1, 40), draw.between(1, 300)
    v, k, d = draw.between(100, 900), draw.between(2, 9), draw.between(1, 9)
    return f"""\
/* {name}: pointers in struct fields, the struct copied and reached through memory. */
struct rec {{
    int tag;
    long *first;
    short small;
    long value;
    long *second;
}};

static long reach(struct rec *q, long k)
{{
    return *q->first * k + *q->second + q->value + q->small;
}}

int main(void)
{{
    long a = {a};
    long b = {b};
    struct rec src;
    struct rec dst;
    src.tag = {g};
    src.first = &a;
    src.small = {s};
    src.value = {v};
    src.second = &b;
    dst = src;
    if (reach(&dst, {k}) != {e(1, a * k + b + v + s)})
        return 1;
    *dst.second = *dst.second + {d};
    if (b != {e(2, b + d)})
        return 2;
    src.first = &b;
    if (*dst.first + *src.first != {e(3, a + b + d)})
        return 3;
    if (dst.tag + dst.small != {e(4, g + s)})
        return 4;
    return 0;
}}
""", 4, 0


def _call(name: str, draw: _Draw, e: _Expect) -> tuple[str, int, int]:
    """A pointer crossing calls in both directions, and live across a nested call."""
    n = draw.between(5, 9)
    k, c = draw.between(2, 11), draw.between(0, 40)
    ix = draw.between(1, n - 2)
    j = draw.between(1, n - 1 - ix)
    d = draw.between(1, 9)
    arena = [i * k + c for i in range(n)]
    v = arena[ix]
    return f"""\
/* {name}: a pointer passed in, returned, and live across a nested call. */
static long *at(long *base, long index)
{{
    return base + index;
}}

static long bump(long *p, long by)
{{
    *p = *p + by;
    return *p;
}}

static long twice(long *p, long by)
{{
    long first = bump(p, by);
    return first + bump(p, by);
}}

int main(void)
{{
    long arena[{n}];
    long *q;
    long i;
    for (i = 0; i < {n}; i++)
        arena[i] = i * {k} + {c};
    q = at(arena, {ix});
    if (*q != {e(1, v)})
        return 1;
    if (twice(q, {d}) != {e(2, 2 * v + 3 * d)})
        return 2;
    if (arena[{ix}] != {e(3, v + 2 * d)})
        return 3;
    if (*at(q, {j}) != {e(4, arena[ix + j])})
        return 4;
    return 0;
}}
""", 4, 0


def _stack(name: str, draw: _Draw, e: _Expect) -> tuple[str, int, int]:
    """Pointer arguments past the eight argument registers, in the caller's outgoing
    area, beside one in a register."""
    total = draw.between(10, 12)
    in_reg = draw.between(0, 7)
    first_stack = draw.between(8, total - 2)
    second_stack = draw.between(first_stack + 1, total - 1)
    x, y = draw.between(1, 70), draw.between(1, 70)
    words = {i: draw.between(1, 99) for i in range(total)
             if i not in (in_reg, first_stack, second_stack)}
    low, high = min(words), max(words)
    minus = sorted(words)[1]
    params, args = [], []
    for i in range(total):
        if i in (in_reg, first_stack, second_stack):
            params.append(f"long *p{i}")
            args.append({in_reg: "&x", first_stack: "&y", second_stack: "&z"}[i])
        else:
            params.append(f"long a{i}")
            args.append(str(words[i]))
    z = y + x + words[low] + words[high]
    return f"""\
/* {name}: pointer arguments beyond the argument registers. */
static long gather({", ".join(params)})
{{
    *p{second_stack} = *p{first_stack} + *p{in_reg} + a{low} + a{high};
    return *p{second_stack} - a{minus};
}}

int main(void)
{{
    long x = {x};
    long y = {y};
    long z = 0;
    if (gather({", ".join(args)}) != {e(1, z - words[minus])})
        return 1;
    if (z != {e(2, z)})
        return 2;
    if (x + y != {e(3, x + y)})
        return 3;
    return 0;
}}
""", 3, 0


def _nullable(name: str, draw: _Draw, e: _Expect) -> tuple[str, int, int]:
    """A pointer or null chosen on a branch and returned, stored, tested against null
    and dereferenced where it is not null."""
    x, d = draw.between(1, 90), draw.between(1, 9)
    p = draw.between(2, 3)
    m = draw.between(1, p - 1)
    o = draw.between(0, p - 1)
    n = draw.between(p + 1, 8)
    flags = [(i * m + o) % p for i in range(n)]
    live = sum(1 for f in flags if f)
    first_live = next(i for i, f in enumerate(flags) if f)
    choose = ("""\
static long *choose(long *p, long flag)
{
    if (flag)
        return p;
    return 0;
}
""" if draw.between(0, 1) else """\
static long *choose(long *p, long flag)
{
    long *r = 0;
    if (flag)
        r = p;
    return r;
}
""")
    return f"""\
/* {name}: a pointer or null by branch, stored, and tested against null. */
{choose}
int main(void)
{{
    long x = {x};
    long *hold[{n}];
    long i, live, sum;
    for (i = 0; i < {n}; i++)
        hold[i] = choose(&x, (i * {m} + {o}) % {p});
    live = 0;
    sum = 0;
    for (i = 0; i < {n}; i++)
        if (hold[i] != 0) {{
            live = live + 1;
            sum = sum + *hold[i];
        }}
    if (live != {e(1, live)})
        return 1;
    if (sum != {e(2, live * x)})
        return 2;
    x = x + {d};
    if (*hold[{first_live}] != {e(3, x + d)})
        return 3;
    return 0;
}}
""", 3, 0


def _spill(name: str, draw: _Draw, e: _Expect) -> tuple[str, int, int]:
    """More pointers live across calls than there are registers to keep them in."""
    k = draw.between(10, 14)
    m, c = draw.between(1, 13), draw.between(0, 30)
    r = draw.between(1, k - 1)
    u = draw.between(0, k - 1)
    w = (u + draw.between(1, k - 1)) % k
    v, x = draw.between(1, 50), draw.between(1, 50)
    a = [i * m + c for i in range(k)]
    target = [(i + r) % k for i in range(k)]
    after = list(a)
    after[target[u]] += v
    first = after[target[u]]
    after[target[w]] += x
    second = after[target[w]]
    names = [f"p{i}" for i in range(k)]
    pointers = ", ".join("*" + p for p in names)
    loads = " + ".join("*" + p for p in names)
    bind = "".join(f"    {p} = &a[{target[i]}];\n" for i, p in enumerate(names))
    return f"""\
/* {name}: pointers live across calls beyond the register file's reach. */
static long touch(long *p, long v)
{{
    *p = *p + v;
    return *p;
}}

int main(void)
{{
    long a[{k}];
    long {pointers};
    long i, s;
    for (i = 0; i < {k}; i++)
        a[i] = i * {m} + {c};
{bind}    s = touch(p{u}, {v});
    s = s + touch(p{w}, {x});
    s = s + {loads};
    if (s != {e(1, first + second + sum(after))})
        return 1;
    if (a[{target[u]}] + a[{target[w]}] != {e(2, after[target[u]] + after[target[w]])})
        return 2;
    return 0;
}}
""", 2, 0


def _narrow(name: str, draw: _Draw, e: _Expect) -> tuple[str, int, int]:
    """A local array narrowed to exactly its own bytes by the plan-bound `csetbounds`
    primitive, written through the narrowed capability and read back through both.

    The length is a multiple of 256 bytes, the stack region's granule under the plan's
    representability decision, and the array is the frame's only object, so it sits at
    the top of the harness stack where the independent plan request places it."""
    n = 32 * draw.between(1, 3)
    m, c = draw.between(1, 17), draw.between(0, 60)
    j, k = draw.between(0, n - 1), draw.between(0, n - 1)
    d = draw.between(1, 9)
    values = [i * m + c for i in range(n)]
    after = list(values)
    after[k] += d
    return f"""\
/* {name}: a local array narrowed to its own bytes by a plan-bound csetbounds. */
extern long *csetbounds(long *, unsigned long);

int main(void)
{{
    long values[{n}];
    long *p = csetbounds(values, {8 * n}UL);
    long i, sum;
    for (i = 0; i < {n}; i++)
        p[i] = i * {m} + {c};
    if (p[{j}] != {e(1, values[j])})
        return 1;
    p[{k}] = p[{k}] + {d};
    sum = 0;
    for (i = 0; i < {n}; i++)
        sum = sum + values[i];
    if (sum != {e(2, sum(after))})
        return 2;
    if (values[{k}] != {e(3, after[k])})
        return 3;
    return 0;
}}
""", 3, 8 * n


PATTERNS: Final = (_memory, _struct, _call, _stack, _nullable, _spill, _narrow)

# Each pattern's check count, fixed so that a perturbed twin can name its check before
# the pattern draws anything.
CHECKS: Final[dict[str, int]] = {"memory": 4, "struct": 4, "call": 4, "stack": 3,
                                 "nullable": 3, "spill": 2, "narrow": 3}


def pattern_names() -> list[str]:
    return [make.__name__.lstrip("_") for make in PATTERNS]


def programs(seed: int, count: int, perturb: bool = False,
             patterns: list[str] | None = None) -> list[Program]:
    """`count` programs cycling over the patterns, every constant drawn from `seed`.

    Deterministic by construction: the same seed, count and pattern selection name the
    same texts, so a campaign a completion note quotes can be regenerated and a digest
    held against it. `patterns` selects a subset in the table's order, every pattern by
    default. With `perturb`, program `k` moves check `k // len(selected) % checks + 1`
    off by one and expects `main` to return that number; the draws are the ordinary
    campaign's.
    """
    unknown = sorted(set(patterns or []) - set(pattern_names()))
    if unknown:
        raise ValueError(f"no generator pattern named {', '.join(unknown)}")
    selected = [make for make in PATTERNS
                if patterns is None or make.__name__.lstrip("_") in patterns]
    draw = _Draw(seed)
    out: list[Program] = []
    for k in range(count):
        make = selected[k % len(selected)]
        pattern = make.__name__.lstrip("_")
        chosen = k // len(selected) % CHECKS[pattern] + 1 if perturb else 0
        name = f"g{seed}-{k:02d}-{pattern}" + (f"-p{chosen}" if chosen else "")
        source, checks, narrowed = make(name, draw, _Expect(chosen))
        if checks != CHECKS[pattern]:
            raise AssertionError(f"{pattern} carries {checks} checks, not {CHECKS[pattern]}")
        out.append(Program(name, pattern, source, checks, chosen, narrowed))
    return out


# =====================================================================================
# The program-level loop over one input
# =====================================================================================


@functools.cache
def harness_stack() -> tuple[int, int]:
    """The program harness's stack, `[base, top)`, as the assembler lays it out."""
    _, symbols, _ = asm.Assembler(compose("main:\n        ret\n"), "layout").assemble()
    return symbols["__vos_stack"][1], symbols["__vos_stack_top"][1]


def narrowing_inputs(fresh: Path, source: bytes, profile: Path, length: int) -> list[str]:
    """Write the independent plan inputs one narrowing program compiles against, and
    return the compiler arguments that name them.

    The composition places the harness stack and the one requested local at its top;
    the plan's single region is that stack and its single request that local, bound to
    `main`'s first narrowing. The context binds the exact source bytes the compiler
    reads, the executed profile and the composition, so a changed input is refused.
    """
    fresh.mkdir(parents=True, exist_ok=True)
    (fresh / "profile.json").write_bytes(profile.read_bytes())
    base, top = harness_stack()
    composition = {"target_hart": 0, "stack_base": base, "stack_size": top - base,
                   "initial_csp": top, "requested_local_base": top - length,
                   "requested_local_size": length}
    (fresh / "composition.json").write_text(json.dumps(composition), encoding="utf-8")
    plan = {
        "schema": "verifiedos-typed-narrowing-input-v1",
        "context": {"source_sha256": _sha256(source),
                    "profile_sha256": _sha256(profile.read_bytes()),
                    "composition_sha256": _sha256((fresh / "composition.json").read_bytes())},
        "regions": [{"region_id": 1, "authority_id": 1, "base": base, "size": top - base}],
        "requests": [{"request_id": 1, "parent_base": base, "parent_size": top - base,
                      "offset": top - length - base, "stride": 0, "last": 0,
                      "length": length}],
        "bindings": [{"function_name": "main", "operation_ordinal": 0, "function_id": 1,
                      "operation_id": 1, "region_id": 1, "authority_id": 1,
                      "request_id": 1}],
    }
    (fresh / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    return ["-fverifiedos-narrowing-plan", "plan.json", "-fverifiedos-profile", "profile.json",
            "-fverifiedos-composition", "composition.json",
            "-fverifiedos-narrowing-output", "narrowing"]


@dataclass(frozen=True)
class Interpreted:
    """One `ccomp -interp` run: CompCert's reference interpreter for the source, which is
    the program-level loop's source-side reading of what `main` returns."""

    argv: tuple[str, ...]
    exit_code: int
    code: int | None
    said: str


_TERMINATED_RE = re.compile(
    r"^Time \d+: program terminated \(exit code = (-?\d+)\)\s*$", re.MULTILINE)


def interpret_c(ccomp: list[str], source: Path, fresh: Path,
                timeout: int = COMPILE_TIMEOUT) -> Interpreted:
    """Run the same compiler's `-interp` over one source in `fresh`.

    The reading is the exit code the interpreter reports for `main`, and only where it
    reports exactly one termination; a stuck state, an undefined behaviour the
    interpreter detects, a timeout or a second termination line leave it `None`.
    """
    fresh.mkdir(parents=True, exist_ok=True)
    copied = fresh / source.name
    shutil.copyfile(source, copied)
    argv = [*ccomp, "-interp", copied.name]
    try:
        done = subprocess.run(argv, cwd=fresh, capture_output=True, encoding="utf-8",
                              errors="replace", timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return Interpreted(tuple(argv), -1, None, f"no exit within {timeout}s")
    except OSError as err:
        return Interpreted(tuple(argv), -1, None, f"could not run: {err}")
    said = done.stdout + done.stderr
    ended = _TERMINATED_RE.findall(done.stdout)
    code = int(ended[0]) if len(ended) == 1 else None
    return Interpreted(tuple(argv), done.returncode, code, said.strip()[-600:])


@dataclass(frozen=True)
class Report:
    """One program through the loop, as far as it got."""

    name: str
    pattern: str
    source_sha256: str
    checks: int
    compiled: Compiled | None
    refusals: tuple[Refusal, ...]
    image_bytes: int
    ran: Ran | None
    verdict: str
    detail: str
    expect: int = 0
    interpreted: Interpreted | None = None
    narrowing: int = 0


def target_code(ran: Ran | None) -> int | None:
    """What the image says `main` returned: 0 on success, the code below `TRAP_BASE`
    on a failed check, and nothing for a trap or a run with no verdict."""
    if ran is None:
        return None
    if ran.verdict == "pass":
        return 0
    if ran.verdict == "fail" and ran.code is not None and ran.code < TRAP_BASE:
        return ran.code
    return None


def as_expected(report: Report) -> bool:
    """Whether the program ended where its source says it ends: every check held for an
    ordinary program, and the one moved check failed for a perturbed twin."""
    if report.expect == 0:
        return report.verdict == "pass"
    return report.verdict == "fail" and target_code(report.ran) == report.expect


def run_program(program: Program, ccomp: list[str], workdir: Path,
                simulator: list[str] | None, profile: Path, waits: str, *,
                compile_timeout: int = COMPILE_TIMEOUT, run_timeout: int = RUN_TIMEOUT,
                inst_limit: int = INST_LIMIT, interp: bool = False) -> Report:
    """Compile, scan, assemble, and run one program, stopping at the first thing that
    does not go through and saying which it was.

    With `interp`, the same compiler's reference interpreter also runs the source, and
    an image whose `main` returned something other than what the interpreter reports is
    `source-disagrees` rather than a pass or a failure.
    """
    # A narrowing program is handed over as `.i`, so the bytes the plan binds are the
    # bytes the compiler reads rather than a preprocessor's rewriting of them.
    source = workdir / f"{program.name}{'.i' if program.narrowing else '.c'}"
    source.write_text(program.source, encoding="utf-8", newline="\n")
    digest = _sha256(source.read_bytes())
    # The primitive has target semantics and no C interpreter meaning, so a narrowing
    # program has no source-side reading.
    interpreted = (interpret_c(ccomp, source, workdir / f"{program.name}.interp",
                               compile_timeout) if interp and not program.narrowing else None)
    extra = (narrowing_inputs(workdir / program.name, source.read_bytes(), profile,
                              program.narrowing) if program.narrowing else [])

    def report(compiled: Compiled | None, found: tuple[Refusal, ...], size: int,
               ran: Ran | None, verdict: str, detail: str) -> Report:
        return Report(program.name, program.pattern, digest, program.checks, compiled,
                      found, size, ran, verdict, detail, program.expect, interpreted,
                      program.narrowing)

    compiled = compile_c([*ccomp, *extra], source, workdir / program.name, compile_timeout)
    if compiled.stream is None:
        return report(compiled, (), 0, None, "ccomp-refused",
                      f"ccomp exited {compiled.exit_code}: {compiled.said}")
    elf = workdir / f"{program.name}.elf"
    found, size = assemble(compiled.stream, program.name, elf)
    if found:
        mnemonics = sum(1 for r in found if r.kind == "mnemonic")
        return report(compiled, tuple(found), 0, None, "dialect-refused",
                      f"{len(found)} refusal(s) the dialect does not assemble, "
                      f"{mnemonics} of them mnemonics")
    if simulator is None:
        return report(compiled, (), size, None, "assembled",
                      f"{size} bytes of image; {waits}")
    ran = run_image(simulator, profile, elf, workdir, run_timeout, inst_limit)
    target = target_code(ran)
    if interpreted is not None and target is not None and interpreted.code != target:
        return report(compiled, (), size, ran, "source-disagrees",
                      f"the image's main returned {target}; the interpreter reports "
                      f"{interpreted.code}")
    return report(compiled, (), size, ran, ran.verdict, ran.detail)


def _refusal_json(refusal: Refusal) -> Json:
    return {"kind": refusal.kind, "name": refusal.name, "line": refusal.line,
            "detail": refusal.detail}


def _compiled_json(compiled: Compiled) -> Json:
    return {"argv": list(compiled.argv), "exit": compiled.exit_code, "said": compiled.said,
            "stream_sha256": compiled.stream_sha256, "lines": compiled.lines}


def _ran_json(ran: Ran) -> Json:
    return {"verdict": ran.verdict, "code": ran.code, "records": ran.records,
            "digest": ran.digest, "capability_roundtrip": ran.cap_roundtrip,
            "output_sha256": _sha256(ran.emitted), "output_length": len(ran.emitted),
            "detail": ran.detail}


def report_json(report: Report) -> Json:
    return {
        "name": report.name, "pattern": report.pattern,
        "source_sha256": report.source_sha256, "checks": report.checks,
        "verdict": report.verdict, "detail": report.detail,
        "ccomp": None if report.compiled is None else _compiled_json(report.compiled),
        "refusals": [_refusal_json(r) for r in report.refusals],
        "image_bytes": report.image_bytes,
        "run": None if report.ran is None else _ran_json(report.ran),
        "expect": report.expect, "narrowing": report.narrowing,
        "interp": None if report.interpreted is None else {
            "argv": list(report.interpreted.argv), "exit": report.interpreted.exit_code,
            "code": report.interpreted.code},
    }


def grouped(found: tuple[Refusal, ...] | list[Refusal]) -> list[tuple[str, str, list[int]]]:
    """The refusals as one row per name: kind, name, and the lines it occurs on."""
    rows: dict[tuple[str, str], list[int]] = {}
    for refusal in found:
        rows.setdefault((refusal.kind, refusal.name), []).append(refusal.line)
    order = {"mnemonic": 0, "relocation": 1, "label": 2, "directive": 3, "section": 4,
             "operand": 5, "symbol": 6, "layout": 7}
    return [(kind, name, lines) for (kind, name), lines
            in sorted(rows.items(), key=lambda item: (order.get(item[0][0], 9), item[0][1]))]


def disagreements(current: list[Report], against: dict[str, Json]) -> list[str]:
    """Where this run's answers to the two questions differ from a recorded run's.

    The program names and source digests must match before the HTIF code and trace
    digest are compared. Duplicate names and missing campaign members are findings.
    The recorded run is a `--json` report of this command.
    """
    recorded = against.get("programs")
    if not isinstance(recorded, list):
        return ["the recorded run carries no `programs` list"]
    by_name: dict[str, dict[str, Json]] = {}
    for entry in recorded:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            return ["the recorded run carries an invalid program entry"]
        name = cast("str", entry["name"])
        if name in by_name:
            return [f"{name}: duplicate name in the recorded run"]
        by_name[name] = entry
    out: list[str] = []
    names = {report.name for report in current}
    if len(names) != len(current):
        return ["the current run carries duplicate program names"]
    out += [f"{name}: not in the current run" for name in by_name if name not in names]
    for report in current:
        before = by_name.get(report.name)
        if before is None:
            out.append(f"{report.name}: not in the recorded run")
            continue
        if report.source_sha256 != before.get("source_sha256"):
            out.append(f"{report.name}: source digest differs from the recorded run")
            continue
        was = before.get("run")
        if report.ran is None or not isinstance(was, dict):
            # one side or both stopped short of the emulator, so the verdicts are what
            # there is to compare: a stream refused here and assembled there is a finding
            if report.verdict != before.get("verdict"):
                out.append(f"{report.name}: verdict {report.verdict!r} against the "
                           f"recorded {before.get('verdict')!r}")
            elif report.ran is not None or was is not None:
                out.append(f"{report.name}: only one run carries emulator evidence")
            continue
        if report.ran.code != was.get("code"):
            out.append(f"{report.name}: HTIF {report.ran.code} against the recorded "
                       f"{was.get('code')}")
        elif report.ran.digest != was.get("digest"):
            out.append(f"{report.name}: trace digest {report.ran.digest} over "
                       f"{report.ran.records} records against the recorded "
                       f"{was.get('digest')} over {was.get('records')}")
    return out


# =====================================================================================
# The component level: the declared output encoding and its comparator
# =====================================================================================


@dataclass(frozen=True)
class Output:
    """One side's result under the declared encoding.

    `verdict` is the side's exit verdict: the Wasm host's process status, which
    `run_demo.mjs` makes 0 for `true` and 1 otherwise, or the purecap image's HTIF exit
    code, `None` where the emulator gave none. The bytes are the runner's standard output
    on the host side and the emulator's terminal log on the purecap side, carried as
    their SHA-256 and length with a short head for a reader; `produced_by` says how.
    """

    side: str
    verdict: int | None
    output_sha256: str
    output_length: int
    output_head: str
    produced_by: str

    def to_json(self) -> dict[str, Json]:
        return {"encoding": ENCODING, "side": self.side, "verdict": self.verdict,
                "output_sha256": self.output_sha256, "output_length": self.output_length,
                "output_head": self.output_head, "produced_by": self.produced_by}


def output_of(side: str, verdict: int | None, emitted: bytes, produced_by: str) -> Output:
    head = emitted[:64].decode("utf-8", errors="replace")
    return Output(side, verdict, _sha256(emitted), len(emitted), head, produced_by)


def read_output(path: Path, expected_side: str | None = None) -> Output:
    """A record written by `to_json`, refused by name where it is not one."""
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"{path}: not a record object")
    record = cast("dict[str, object]", raw)
    if record.get("encoding") != ENCODING:
        raise ValueError(f"{path}: encoding {record.get('encoding')!r} is not {ENCODING}")
    side, digest = record.get("side"), record.get("output_sha256")
    length, head = record.get("output_length"), record.get("output_head")
    verdict, produced = record.get("verdict"), record.get("produced_by")
    if not (isinstance(side, str) and isinstance(digest, str) and type(length) is int
            and isinstance(head, str) and isinstance(produced, str)
            and (verdict is None or type(verdict) is int)):
        raise ValueError(f"{path}: a field of the record is missing or of the wrong type")
    if side not in ("wasm-host", "purecap") or (expected_side and side != expected_side):
        raise ValueError(f"{path}: side {side!r} is not {expected_side or 'a component side'}")
    if length < 0 or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError(f"{path}: invalid output length or SHA-256 digest")
    return Output(side, verdict, digest, length, head, produced)


@dataclass(frozen=True)
class Disagreement:
    """The first field on which the two sides differ, and both readings of it."""

    field: str
    host: str
    purecap: str

    def line(self) -> str:
        return f"{self.field}: host {self.host}, purecap {self.purecap}"


def compare_outputs(host: Output, purecap: Output, host_bytes: bytes | None = None,
                    purecap_bytes: bytes | None = None) -> Disagreement | None:
    """The first disagreement between the two sides, or `None` where they agree.

    The verdict is compared first, because a component whose verdicts differ has already
    decided the question; then the length, then the digest, and where both sides' bytes
    are in hand the first differing byte is named rather than the digests.
    """
    if host.side != "wasm-host" or purecap.side != "purecap":
        return Disagreement("side", host.side, purecap.side)
    if host.verdict is None or purecap.verdict is None:
        return Disagreement("verdict", str(host.verdict), str(purecap.verdict))
    if host.verdict != purecap.verdict:
        return Disagreement("verdict", str(host.verdict), str(purecap.verdict))
    if host.output_length != purecap.output_length:
        return Disagreement("output_length", str(host.output_length),
                            str(purecap.output_length))
    if host.output_sha256 == purecap.output_sha256:
        return None
    if host_bytes is not None and purecap_bytes is not None:
        for offset, (a, b) in enumerate(zip(host_bytes, purecap_bytes, strict=False)):
            if a != b:
                return Disagreement(f"output byte {offset}", f"{a:#04x}", f"{b:#04x}")
    return Disagreement("output_sha256", host.output_sha256, purecap.output_sha256)


def wasm_output(module: Path, runner: list[str], cwd: Path,
                timeout: int = RUN_TIMEOUT) -> tuple[Output, bytes]:
    """Run one compiled module on the Wasm oracle's host and read its side."""
    argv = [*runner, str(module)]
    produced = " ".join(argv)
    try:
        done = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=timeout,
                              check=False)
    except subprocess.TimeoutExpired:
        return output_of("wasm-host", None, b"", f"{produced} (no exit within {timeout}s)"), b""
    except OSError as err:
        return output_of("wasm-host", None, b"", f"{produced} (could not run: {err})"), b""
    return output_of("wasm-host", done.returncode, done.stdout, produced), done.stdout


def purecap_output(elf: Path, simulator: list[str], profile: Path, workdir: Path,
                   timeout: int = RUN_TIMEOUT,
                   inst_limit: int = INST_LIMIT) -> tuple[Output, bytes]:
    """Run one lowered image on the golden emulator and read its side."""
    ran = run_image(simulator, profile, elf, workdir, timeout, inst_limit)
    produced = (f"{' '.join(simulator)} --config {profile} --trace-commit "
                f"--terminal-log <log> {elf.name}: {ran.detail}")
    return output_of("purecap", ran.code, ran.emitted, produced), ran.emitted


@dataclass(frozen=True)
class Lowered:
    """A component's C through the backend and the assembler, stage by stage."""

    compiled: Compiled
    refusals: tuple[Refusal, ...]
    elf_sha256: str | None


def lower_component(source: Path, ccomp: list[str], workdir: Path,
                    timeout: int = COMPILE_TIMEOUT) -> tuple[Lowered, Path | None]:
    """Compile one component with `ccomp -S` in a fresh directory and assemble it under
    the component harness; the image is returned only where every stage went through."""
    compiled = compile_c(ccomp, source, workdir / source.stem, timeout)
    if compiled.stream is None:
        return Lowered(compiled, (), None), None
    elf = workdir / f"{source.stem}.elf"
    elf.unlink(missing_ok=True)
    found, _ = assemble(compiled.stream, source.stem, elf, COMPONENT_PROLOGUE)
    if found:
        return Lowered(compiled, tuple(found), None), None
    return Lowered(compiled, (), _sha256(elf.read_bytes())), elf


# =====================================================================================
# The command
# =====================================================================================


def _sources(root: Path) -> dict[str, Json]:
    return {name: _sha256((root / name).read_bytes()) for name in SOURCES
            if (root / name).is_file()}


def _executable_identity(spelled: str) -> dict[str, Json]:
    """The compiler or emulator as the caller named it, with the digest of the file where
    the spelling is one; the digest is what a completion note quotes."""
    path = Path(spelled)
    return {"path": spelled,
            "sha256": _sha256(path.read_bytes()) if path.is_file() else None}


def _profile(args: argparse.Namespace, root: Path) -> Path:
    return Path(args.profile) if args.profile else root / "model" / env.PROFILE_CONFIG


def _simulator(args: argparse.Namespace) -> tuple[list[str] | None, str]:
    """The emulator to run images on, or `None` and the sentence saying what waits."""
    if args.simulator:
        return [str(args.simulator)], ""
    if args.lane:
        lane = env.load(toolchain=False).simulator
        if lane.is_file():
            return [str(lane)], ""
        return None, (f"the emulator half waits: no simulator at {lane} (this lane has "
                      f"not built; `run.py model build`)")
    return None, "the emulator half waits: pass --simulator PATH or --lane"


def _file_identity(path: Path) -> dict[str, Json]:
    return {"path": str(path),
            "sha256": _sha256(path.read_bytes()) if path.is_file() else None}


def _inputs(args: argparse.Namespace) -> list[Program]:
    """The programs to run: the sources named, then the generated campaign."""
    out: list[Program] = []
    for spelled in args.source:
        path = Path(spelled)
        text = path.read_text(encoding="utf-8")
        out.append(Program(path.stem, "given", text, 0))
    if args.generate:
        out += programs(args.seed, args.generate, args.perturb, args.pattern or None)
    if len({program.name for program in out}) != len(out):
        raise ValueError("program names must be unique, including generated programs")
    return out


def _print_report(report: Report) -> None:
    label = report.verdict.upper()
    print(f"{label:<16} {report.name}: {report.detail}")
    if report.compiled is not None and report.verdict != "ccomp-refused":
        print(f"{'':<16}   ccomp exited 0 with {report.compiled.lines} line(s), "
              f"sha256 {report.compiled.stream_sha256[:16]}")
    for kind, name, lines in grouped(report.refusals):
        where = ", ".join(str(n) for n in lines if n) or "(the stream)"
        note = next((r.detail for r in report.refusals
                     if r.kind == kind and r.name == name and r.detail), "")
        print(f"{'':<16}   {kind:<9} {name:<16} line(s) {where}"
              + (f": {note}" if note else ""))
    if report.ran is not None:
        print(f"{'':<16}   {report.ran.records} records, digest {report.ran.digest}, "
              f"capability round trip: {'yes' if report.ran.cap_roundtrip else 'no'}")
    if report.interpreted is not None:
        print(f"{'':<16}   interpreter: main returned {report.interpreted.code}"
              + (f", expected {report.expect}" if report.expect else ""))


def _program(args: argparse.Namespace) -> int:
    root = corpus_mod.find_root()
    try:
        inputs = _inputs(args)
    except (OSError, ValueError) as err:
        print(f"FAIL compiler-diff: unreadable input: {err}", file=sys.stderr)
        return 2
    if not inputs:
        print("nothing to compile: name a C source, or --generate N", file=sys.stderr)
        return 2
    simulator, waits = _simulator(args)
    profile = _profile(args, root)
    against: dict[str, Json] | None = None
    if args.against:
        try:
            loaded: object = json.loads(Path(args.against).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as err:
            print(f"FAIL compiler-diff: the recorded run is unreadable: {err}",
                  file=sys.stderr)
            return 2
        against = cast("dict[str, Json]", loaded) if isinstance(loaded, dict) else {}

    ccomp = [str(args.ccomp), *args.ccomp_arg]
    keep = Path(args.keep) if args.keep else None
    with tempfile.TemporaryDirectory(prefix="vos-compiler-diff-") as scratch:
        workdir = keep or Path(scratch)
        workdir.mkdir(parents=True, exist_ok=True)
        reports = [run_program(program, ccomp, workdir, simulator, profile, waits,
                               compile_timeout=args.timeout, run_timeout=args.run_timeout,
                               inst_limit=args.inst_limit, interp=args.interp)
                   for program in inputs]

    differs = disagreements(reports, against) if against is not None else []
    tally = {verdict: sum(1 for r in reports if r.verdict == verdict) for verdict in VERDICTS}
    closed = all(as_expected(r) for r in reports) and not differs
    expected = (all(r.verdict == "dialect-refused" for r in reports) and not differs
                if args.expect_refusal else closed)

    if args.json:
        summary: dict[str, Json] = {}
        for verdict in VERDICTS:
            summary[verdict] = tally[verdict]
        recorded: Json = None if against is None else {"disagreements": list(differs)}
        payload: dict[str, Json] = {
            "scope": "program-level", "milestone_acceptance": "open",
            "sources_sha256": _sources(root),
            "ccomp": _executable_identity(args.ccomp),
            "simulator": None if simulator is None else _executable_identity(simulator[0]),
            "profile": _file_identity(profile),
            "campaign": {"seed": args.seed, "generated": args.generate,
                         "perturb": args.perturb,
                         "patterns": cast("list[Json]", args.pattern or pattern_names()),
                         "given": [p.name for p in inputs if p.pattern == "given"]},
            "interp": args.interp,
            "expect": ("refusal" if args.expect_refusal
                       else "perturbed" if args.perturb else "pass"),
            "programs": [report_json(r) for r in reports],
            "summary": summary,
            "against": recorded,
            "green": expected,
        }
        print(json.dumps(payload, indent=2))
        return 0 if expected else 1

    for report in reports:
        _print_report(report)
    for line in differs:
        print(f"{'DISAGREE':<16} {line}")
    counts = " ".join(f"{verdict}={tally[verdict]}" for verdict in VERDICTS)
    print(f"TOTAL {counts} of {len(reports)}"
          + (f"; {len(differs)} disagreement(s) with the recorded run" if against else "")
          + (f"; {waits}" if simulator is None else ""))
    if closed:
        print(("every perturbed program failed at its moved check"
               if args.perturb else "every program answered both questions")
              + ("; the source interpreter agreed with every image" if args.interp else "")
              + "; a run is evidence for this campaign and decides no milestone alone")
    elif args.expect_refusal:
        print("the refusal is the expected verdict ahead of the backend (R-18-002): "
              + ("every stream was refused" if expected
                 else "the refusals or the recorded comparison did not meet the expectation"))
    else:
        print("the acceptance loop is open: not every program ended where its source says")
    return 0 if expected else 1


def _component(args: argparse.Namespace) -> int:
    root = corpus_mod.find_root()
    host: Output | None = None
    purecap: Output | None = None
    host_bytes: bytes | None = None
    purecap_bytes: bytes | None = None
    bindings: dict[str, Json] = {}
    interpreted: Interpreted | None = None
    simulator: list[str] | None = None
    if args.c and not args.purecap_record:
        simulator, waits = _simulator(args)
        refused = ("--c needs --ccomp, the contained compiler" if not args.ccomp
                   else waits if simulator is None else "")
        if refused:
            print(f"FAIL compiler-diff component: {refused}", file=sys.stderr)
            return 2
    try:
        if args.host_record:
            host = read_output(Path(args.host_record), "wasm-host")
        elif args.wasm:
            runner = list(args.runner) if args.runner else list(NODE_RUNNER)
            bindings["wasm_module"] = _file_identity(Path(args.wasm))
            host, host_bytes = wasm_output(Path(args.wasm), runner, root, args.timeout)
        if args.purecap_record:
            purecap = read_output(Path(args.purecap_record), "purecap")
        elif args.c and simulator is not None:
            source, profile = Path(args.c), _profile(args, root)
            ccomp = [str(args.ccomp), *args.ccomp_arg]
            with tempfile.TemporaryDirectory(prefix="vos-compiler-diff-") as scratch:
                workdir = Path(args.keep) if args.keep else Path(scratch)
                workdir.mkdir(parents=True, exist_ok=True)
                lowered, elf = lower_component(source, ccomp, workdir, args.compile_timeout)
                if elf is None:
                    stage = (f"ccomp exited {lowered.compiled.exit_code}: "
                             f"{lowered.compiled.said}" if lowered.compiled.stream is None
                             else "the assembler refused " + "; ".join(
                                 f"{r.kind} {r.name} line {r.line}" for r in lowered.refusals))
                    purecap = output_of("purecap", None, b"", f"lowering stopped: {stage}")
                else:
                    purecap, purecap_bytes = purecap_output(
                        elf, simulator, profile, workdir, args.timeout, args.inst_limit)
                if args.interp:
                    interpreted = interpret_c(ccomp, source,
                                              workdir / f"{source.stem}.interp",
                                              args.compile_timeout)
            bindings.update({
                "c_source": _file_identity(source),
                "ccomp": _executable_identity(args.ccomp),
                "ccomp_args": list(args.ccomp_arg),
                "stream_sha256": lowered.compiled.stream_sha256 or None,
                "refusals": [_refusal_json(r) for r in lowered.refusals],
                "elf_sha256": lowered.elf_sha256,
                "simulator": _executable_identity(simulator[0]),
                "profile": _file_identity(profile),
            })
        elif args.elf and args.simulator:
            with tempfile.TemporaryDirectory(prefix="vos-compiler-diff-") as scratch:
                purecap, purecap_bytes = purecap_output(
                    Path(args.elf), [str(args.simulator)], _profile(args, root),
                    Path(scratch), args.timeout, args.inst_limit)
    except (OSError, ValueError, TypeError) as err:
        # `json.JSONDecodeError` is a `ValueError`, so a record that is not JSON at all
        # is refused by the same arm as one whose fields are wrong
        print(f"FAIL compiler-diff component: {err}", file=sys.stderr)
        return 2
    if host is None and purecap is None:
        print("nothing to compare: name a Wasm module or a host record, and a C source or "
              "an image with a simulator, or a purecap record", file=sys.stderr)
        return 2

    for spelled, side in ((args.write_host, host), (args.write_purecap, purecap)):
        if spelled and side is not None:
            Path(spelled).write_text(json.dumps(side.to_json(), indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    verdict = (compare_outputs(host, purecap, host_bytes, purecap_bytes)
               if host is not None and purecap is not None else None)
    incomplete = any(side is not None and side.verdict is None for side in (host, purecap))
    # The interpreter's reading of the same C, as the harness would print it: 0 is true.
    source_verdict = (None if interpreted is None or interpreted.code is None
                      else 0 if interpreted.code == 0 else 1)
    source_differs = interpreted is not None and (
        purecap is None or source_verdict is None or source_verdict != purecap.verdict)
    if interpreted is not None:
        bindings["interp"] = {"argv": list(interpreted.argv), "exit": interpreted.exit_code,
                              "code": interpreted.code, "verdict": source_verdict}
    failed = verdict is not None or incomplete or source_differs

    if args.json:
        payload: dict[str, Json] = {
            "scope": "component-level", "milestone_acceptance": "open",
            "encoding": ENCODING, "sources_sha256": _sources(root),
            "bindings": bindings,
            "host": None if host is None else host.to_json(),
            "purecap": None if purecap is None else purecap.to_json(),
            "compared": host is not None and purecap is not None,
            "disagreement": None if verdict is None else verdict.line(),
            "source_disagrees": source_differs,
        }
        print(json.dumps(payload, indent=2))
        return 1 if failed else 0

    for side in (host, purecap):
        if side is not None:
            print(f"{side.side.upper():<9} verdict {side.verdict}, {side.output_length} "
                  f"byte(s), sha256 {side.output_sha256[:16]}, head {side.output_head!r}")
            print(f"{'':<9} produced by: {side.produced_by}")
    for key in ("wasm_module", "c_source", "ccomp", "simulator", "profile"):
        if isinstance(bindings.get(key), dict):
            bound = cast("dict[str, Json]", bindings[key])
            print(f"{'BOUND':<9} {key} {bound.get('path')} sha256 {bound.get('sha256')}")
    for key in ("stream_sha256", "elf_sha256"):
        if key in bindings:
            print(f"{'BOUND':<9} {key} {bindings[key]}")
    if interpreted is not None:
        print(f"{'SOURCE':<9} the interpreter reports main returned {interpreted.code}"
              + (": it disagrees with the image" if source_differs else ""))
    if host is None or purecap is None:
        if incomplete:
            print("FAIL      the requested side did not produce an exit verdict")
            return 1
        missing = "purecap" if purecap is None else "host"
        print(f"WAITS     the {missing} side: no record and no run was named for it")
        return 1 if source_differs else 0
    if verdict is None and not source_differs:
        print(f"AGREE     both sides under {ENCODING}: verdict {host.verdict} and "
              f"{host.output_length} byte(s)")
        return 0
    if verdict is not None:
        print(f"DISAGREE  {verdict.line()}")
    return 1


def _generate(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows: list[Json] = []
    try:
        generated = programs(args.seed, args.count, args.perturb, args.pattern or None)
    except ValueError as err:
        print(f"FAIL compiler-diff generate: {err}", file=sys.stderr)
        return 2
    for program in generated:
        path = out / f"{program.name}.c"
        path.write_text(program.source, encoding="utf-8", newline="\n")
        rows.append({"name": program.name, "pattern": program.pattern,
                     "checks": program.checks, "expect": program.expect,
                     "sha256": _sha256(path.read_bytes())})
        print(f"WROTE   {path} ({program.pattern}, {program.checks} checks)")
    manifest: dict[str, Json] = {"seed": args.seed, "count": args.count,
                                 "perturb": args.perturb,
                                 "patterns": cast("list[Json]", args.pattern or pattern_names()),
                                 "programs": rows}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                       encoding="utf-8", newline="\n")
    print(f"TOTAL   {len(rows)} program(s) from seed {args.seed}, FP-free, over "
          f"{len(PATTERNS)} pattern(s); a failure names its check through main's return")
    return 0


def _flags(name: str, sub: argparse.ArgumentParser) -> None:
    if name == "program":
        sub.add_argument("source", nargs="*", help="C sources to feed through the loop")
        sub.add_argument("--ccomp", required=True, metavar="PATH",
                         help="the contained ccomp executable, outside every checkout")
        sub.add_argument("--generate", type=int, default=0, metavar="N",
                         help="also run N generated programs (see `generate`)")
        sub.add_argument("--seed", type=int, default=1, help="the generator's seed")
        sub.add_argument("--perturb", action="store_true",
                         help="the negative control: each generated program moves one "
                              "check's constant and must fail at that check")
        sub.add_argument("--pattern", action="append", default=[], metavar="NAME",
                         help="generate only this pattern (repeatable; default: all)")
        sub.add_argument("--against", metavar="FILE",
                         help="a --json report of an earlier run to hold this one against")
        sub.add_argument("--expect-refusal", action="store_true",
                         help="green iff every stream is refused by the dialect")
        sub.add_argument("--timeout", type=int, default=COMPILE_TIMEOUT,
                         help="seconds the compiler gets per program")
        sub.add_argument("--run-timeout", type=int, default=RUN_TIMEOUT,
                         help="seconds the emulator gets per image")
    if name == "component":
        sub.add_argument("--wasm", metavar="MODULE", help="a module the oracle compiled")
        sub.add_argument("--runner", action="append", metavar="ARG",
                         help="the Wasm host's argv, one argument per flag (default: "
                              "the pinned Node through tools/wasm-oracle)")
        sub.add_argument("--host-record", metavar="FILE", help="the host side, recorded")
        sub.add_argument("--c", metavar="SOURCE",
                         help="the component's C, lowered through --ccomp and run under "
                              "the component harness")
        sub.add_argument("--ccomp", metavar="PATH",
                         help="the contained ccomp executable, outside every checkout")
        sub.add_argument("--elf", metavar="FILE", help="the component's lowered image")
        sub.add_argument("--purecap-record", metavar="FILE",
                         help="the purecap side, recorded")
        sub.add_argument("--write-host", metavar="FILE", help="record the host side here")
        sub.add_argument("--write-purecap", metavar="FILE",
                         help="record the purecap side here")
        sub.add_argument("--timeout", type=int, default=RUN_TIMEOUT,
                         help="seconds either side gets to run")
        sub.add_argument("--compile-timeout", type=int, default=COMPILE_TIMEOUT,
                         help="seconds the compiler and its interpreter get")
    if name in ("program", "component"):
        sub.add_argument("--ccomp-arg", action="append", default=[], metavar="ARG",
                         help="pass one compiler argument unchanged (repeatable; use "
                              "--ccomp-arg=-flag for an option)")
        sub.add_argument("--interp", action="store_true",
                         help="also run the source through the same compiler's -interp "
                              "and require the image to agree with it")
        sub.add_argument("--keep", metavar="DIR",
                         help="keep the streams and images here rather than in scratch")
        sub.add_argument("--simulator", metavar="PATH",
                         help="the golden emulator, a lane's c_emulator/sail_riscv_sim")
        sub.add_argument("--lane", action="store_true",
                         help="use this checkout's own lane's simulator (guest only)")
        sub.add_argument("--profile", metavar="FILE",
                         help=f"the configuration (default: model/{env.PROFILE_CONFIG})")
        sub.add_argument("--inst-limit", type=int, default=INST_LIMIT,
                         help="the emulator's instruction bound per run")
        sub.add_argument("--json", action="store_true",
                         help="emit the report as one JSON object")
    if name == "generate":
        sub.add_argument("--out", required=True, metavar="DIR", help="where to write them")
        sub.add_argument("--count", type=int, default=6, help="how many programs")
        sub.add_argument("--seed", type=int, default=1, help="the generator's seed")
        sub.add_argument("--perturb", action="store_true",
                         help="write the negative-control twins instead")
        sub.add_argument("--pattern", action="append", default=[], metavar="NAME",
                         help="generate only this pattern (repeatable; default: all)")


TABLE: Table = {
    "program": (_program, "C through ccomp, the assembler, the composer and the emulator"),
    "component": (_component, "one Gallina component's Wasm-host run against its "
                              "purecap run, under the declared output encoding"),
    "generate": (_generate, "write the deterministic FP-free C campaign"),
}


def main(argv: list[str] | None = None) -> int:
    return dispatch(__doc__, TABLE, argv, _flags, prog="run.py compiler-diff")
