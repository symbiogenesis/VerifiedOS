#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""M1.2f's two acceptance loops, prepared ahead of the backend they accept.

    tools/run.py compiler-diff program --ccomp PATH (SOURCE.c ... | --generate N) [--simulator PATH]
    tools/run.py compiler-diff component (--wasm MODULE | --host-record FILE)
                                         (--elf FILE --simulator PATH | --purecap-record FILE)
    tools/run.py compiler-diff generate --out DIR [--count N] [--seed S]

**The program level** feeds C through `ccomp -S` in a fresh directory, hands the emitted
stream to the in-tree assembler ([vos/asm.py](../asm.py)) and the image composer
([vos/image.py](../image.py)) under the harness stated below, and runs the image on the
golden emulator with the invocation `run.py model corpus` makes, asking the two questions
[differential-corpus.md](../../../docs/assurance/differential-corpus.md) §6 asks of a
member: the program's own, its HTIF verdict, and the rig's, the digest of its normalized
commit trace. The compiler is never in the tree: `--ccomp` names an executable outside every
checkout, which is M1.1a's containment, and the driver records the path and the digest of
what it found there rather than carrying either.

**What the pre-backend verdict is.** Stock `ccomp -S` writes lp64d RV64 carrying no
capability mnemonic (M1.2's measurement), which R-18-002 forbids as a compilation target
and which the dialect table does not spell. So the stream is scanned before it is
assembled, and every mnemonic, directive and section the assembler refuses is reported by
name and by line of the emitted stream, as the expected verdict ahead of the backend and
never as an opaque failure. `--expect-refusal` makes that verdict the green one, so the run
that records the pre-backend state exits 0 and the day a stream assembles is the day the
expectation moves. Two classes are kept apart because two owners close them: a refused
*mnemonic* is the backend's to close, and a refused *directive* is the seam between
CompCert's printer and the assembler's vocabulary, which the driver reports and does not
translate.

**The harness.** A stream that assembles is wrapped before it is composed: `_start` moves
the store-side root out of `c1` and derives the stack and the `tohost` authority from it,
the way every corpus member derives an authority (R-15-001c), installs a trap handler
through MTCC, calls `main`, and folds the return into the exit code the corpus convention
reads back: `1` for success, `(code << 1) | 1` otherwise, where a code below `0x100` is
`main`'s return masked to a byte (a nonzero return with a zero low byte reads as `0xFF`)
and a code at or above it is `0x100 | mcause` for a trap that reached the handler. The
frame `main` itself expects is the backend's, so the convention this harness assumes at
the call is a placeholder M1.2d replaces, and the run says so.

**The third reading of the trace** is M1.7's own test that a capability went through
memory rather than only through the register file: one `W` record whose tag is set, read
back by an `R` at the same address with the tag set. It is reported beside the digest and
gates nothing, because only a purecap backend can make it true.

**The component level** holds one Gallina component's host run on the CertiCoq-to-Wasm
oracle against its purecap run under one declared output encoding: the side's exit
verdict, which is the Wasm host's process status on one side and the image's HTIF exit
code on the other, plus the SHA-256 and the length of the bytes the component emitted,
the runner's standard output on one side and the emulator's terminal log, the HTIF console,
on the other. Either side is written as a record that the other side's run is later held
against, and the comparator names the first field that disagrees, or the first byte where
both sides' bytes are in hand.

**What this does not decide, stated rather than implied.** No purecap component exists to
run before M1.2's backend is integrated, so the component loop's purecap side is a record
whose producer is still owed; the program loop's harness assumes a calling convention
M1.2d has not fixed; a green run says this machine and this program agree and never that a
lowering is correct, R-05-023a's instrument being deferred hardening; and every report
carries `milestone_acceptance: open` because the cell closes on the integrated backend and
not on this driver.
"""

import argparse
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
    "tools/generated/dialect-table.json", "docs/assurance/differential-corpus.md")

# The verdict a program can end in. Listed once, in the order the summary counts them.
VERDICTS: Final[tuple[str, ...]] = (
    "ccomp-refused", "dialect-refused", "assembled", "pass", "fail", "trap", "no-verdict")

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
    naming one the image does not have, `operand` for a known mnemonic or directive whose
    operands the assembler refused, `symbol` for a stream that defines no `main`, and
    `layout` for an image the composer cannot place. `line` is 1-based in the emitted
    stream, and 0 where the refusal is not a line's.
    """

    kind: str
    name: str
    line: int
    detail: str = ""


_LABEL_RE = re.compile(r"([A-Za-z_.$][A-Za-z_.$0-9]*)\s*:")
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
    once the comment is gone."""
    text = raw.split("#", 1)[0].split("//", 1)[0].strip()
    labels: list[str] = []
    while text:
        label = _LABEL_RE.match(text)
        if not label:
            break
        labels.append(label.group(1))
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

PROLOGUE: Final = """\
# The M1.2f driver's harness around an emitted stream. Every authority is derived off the
# store-side root the way a corpus member derives one (R-15-001c); the calling convention
# assumed at `call main` is a placeholder until M1.2d fixes the frame and the sentry pair.
        .text
        .globl _start
_start:
        cmove   c8, c1
        la      c9, __vos_handler
        cspecialrw cnull, mtcc, c9
        li      t0, __vos_stack_top
        csetaddr csp, c8, t0
        call    main
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
        csetaddr c31, c8, t1
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

EPILOGUE: Final = f"""\
# --- the emitted stream ends ---
        .data
        .align  3
tohost:
        .dword  0
        .align  4
__vos_stack:
        .space  {STACK_BYTES}
__vos_stack_top:
"""

# Where the stream's first line sits in the composite, so a layout-time refusal can be
# named by the stream's own line.
STREAM_OFFSET: Final = PROLOGUE.count("\n")


def compose(stream: str) -> str:
    """The composite the assembler is handed: the harness around the normalized stream."""
    body = normalize(stream)
    if body and not body.endswith("\n"):
        body += "\n"
    return PROLOGUE + body + EPILOGUE


def assemble(stream: str, name: str, elf: Path) -> tuple[list[Refusal], int]:
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
    assembler = asm.Assembler(compose(stream), name)
    try:
        sections, symbols, entry = assembler.assemble()
    except AsmError as exc:
        return [_layout_refusal(exc, stream)], 0
    text = sum(len(s.data) for s in sections if s.name == ".text")
    if text > asm.DATA_BASE - asm.TEXT_BASE:
        return [Refusal("layout", ".text", 0,
                        f"{text} bytes of text reach the data section at "
                        f"{asm.DATA_BASE:#x}")], 0
    image.write_elf(elf, sections, symbols, entry)
    return [], sum(len(s.data) for s in sections)


def _layout_refusal(exc: AsmError, stream: str) -> Refusal:
    """An assembler diagnostic over the composite, named by the stream's own line."""
    said = str(exc)
    matched = _ASM_ERROR_RE.match(said)
    if matched is None:
        return Refusal("operand", "?", 0, said)
    number = int(matched.group(2)) - STREAM_OFFSET
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

    The source is copied in and the compiler is run there, so the only files it can read
    or write are its own and the argv recorded is stable across runs: the compiler's
    path as the caller spelled it and two names relative to the fresh directory.
    """
    fresh.mkdir(parents=True, exist_ok=True)
    copied = fresh / source.name
    shutil.copyfile(source, copied)
    out = fresh / f"{source.stem}.s"
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
    if "SUCCESS" in said:
        return "pass", 0, "HTIF 0"
    failed = _FAILURE_RE.search(said)
    if failed:
        code = int(failed.group(1))
        if code >= TRAP_BASE:
            return "trap", code, f"HTIF {code}: cause {code - TRAP_BASE} reached the handler"
        return "fail", code, f"HTIF {code}: main returned {code}"
    if "trap loop" in said:
        return "no-verdict", None, "the emulator detected a trap loop"
    return "no-verdict", None, f"rc={returncode}, no HTIF verdict"


def cap_roundtrip(records: list[str]) -> bool:
    """Whether a tagged write was read back tagged at the same address (M1.7's test that a
    capability went through memory rather than only through the register file)."""
    written: set[str] = set()
    for record in records:
        parts = record.split()
        if len(parts) != 5 or parts[3] != "1":
            continue
        if parts[0] == "W":
            written.add(parts[1])
        elif parts[0] == "R" and parts[1] in written:
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
    return Ran(verdict, code, len(records), trace.digest(records), cap_roundtrip(records),
               emitted, detail)


# =====================================================================================
# The generator: small FP-free C programs over the capability-through-memory patterns
# =====================================================================================


@dataclass(frozen=True)
class Program:
    """One generated input: its name, the pattern it exercises, its text, and how many
    checks it carries, each returning its own number from `main` on the corpus's
    convention that a failure names the check."""

    name: str
    pattern: str
    source: str
    checks: int


class _Draw:
    """A deterministic draw, so that a seed names one campaign on every machine and every
    interpreter: Knuth's MMIX multiplier and increment over 64 bits, the top bits taken."""

    def __init__(self, seed: int) -> None:
        self.state = (seed * 6364136223846793005 + 1442695040888963407) & MASK64

    def between(self, low: int, high: int) -> int:
        self.state = (self.state * 6364136223846793005 + 1442695040888963407) & MASK64
        return low + (self.state >> 33) % (high - low + 1)


def _pointer(name: str, draw: _Draw) -> Program:
    """A pointer stored to memory and reloaded through a slot a volatile index selects, so
    the compiler cannot keep it in a register across the store."""
    cells = draw.between(3, 6)
    i = draw.between(0, cells - 1)
    j = (i + draw.between(1, cells - 1)) % cells
    a, b, d = draw.between(11, 90), draw.between(1, 9), draw.between(1, 7)
    source = f"""\
/* {name}: a pointer stored to memory and reloaded before it is used. */
static int cells[{cells}];
static int *slots[2];
static volatile int pick = 1;

int main(void)
{{
    int *p;
    cells[{i}] = {a};
    cells[{j}] = {b};
    slots[0] = &cells[{j}];
    slots[1] = &cells[{i}];
    p = slots[pick];
    if (*p != {a})
        return 1;
    *p = *p + {d};
    if (cells[{i}] != {a + d})
        return 2;
    if (slots[1 - pick] != &cells[{j}])
        return 3;
    if (*slots[0] != {b})
        return 4;
    return 0;
}}
"""
    return Program(name, "pointer", source, 4)


def _struct(name: str, draw: _Draw) -> Program:
    """A pointer held in a struct field and reached through the struct in memory."""
    t, g, v, d = (draw.between(1, 40), draw.between(1, 9), draw.between(100, 900),
                  draw.between(1, 9))
    source = f"""\
/* {name}: a pointer held in a struct field, reached through the struct in memory. */
struct node {{
    int tag;
    int *ref;
    long value;
}};

static int target = {t};
static struct node box;
static volatile int which = 0;

int main(void)
{{
    struct node *n = &box;
    int *r;
    box.tag = {g};
    box.ref = &target;
    box.value = {v};
    r = n->ref;
    if (which != 0)
        return 1;
    if (*r != {t})
        return 2;
    *r += {d};
    if (target != {t + d})
        return 3;
    if (n->value + n->tag != {v + g})
        return 4;
    return 0;
}}
"""
    return Program(name, "struct", source, 4)


def _call(name: str, draw: _Draw) -> Program:
    """A pointer crossing a call in both directions: passed in, and returned."""
    n, k, s, d, d2 = (draw.between(4, 8), draw.between(2, 5), draw.between(10, 50),
                      draw.between(1, 9), draw.between(1, 9))
    ix = draw.between(1, n - 1)
    source = f"""\
/* {name}: a pointer crossing a call in both directions. */
static int store;

static int *pick_slot(int *base, int index)
{{
    return base + index;
}}

static int bump(int *p, int by)
{{
    *p += by;
    return *p;
}}

int main(void)
{{
    int arena[{n}];
    int *q;
    int i;
    for (i = 0; i < {n}; i++)
        arena[i] = i * {k};
    store = {s};
    if (bump(&store, {d}) != {s + d})
        return 1;
    if (store != {s + d})
        return 2;
    q = pick_slot(arena, {ix});
    if (*q != {ix * k})
        return 3;
    if (bump(q, {d2}) != {ix * k + d2})
        return 4;
    if (arena[{ix}] != {ix * k + d2})
        return 5;
    return 0;
}}
"""
    return Program(name, "call", source, 5)


PATTERNS: Final = (_pointer, _struct, _call)


def programs(seed: int, count: int) -> list[Program]:
    """`count` programs cycling over the three patterns, every constant drawn from `seed`.

    Deterministic by construction: the same seed and count name the same texts, so a
    campaign a completion note quotes can be regenerated and a digest held against it.
    """
    draw = _Draw(seed)
    out: list[Program] = []
    for k in range(count):
        make = PATTERNS[k % len(PATTERNS)]
        out.append(make(f"g{seed}-{k:02d}-{make.__name__.lstrip('_')}", draw))
    return out


# =====================================================================================
# The program-level loop over one input
# =====================================================================================


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


def run_program(program: Program, ccomp: list[str], workdir: Path,
                simulator: list[str] | None, profile: Path, waits: str, *,
                compile_timeout: int = COMPILE_TIMEOUT, run_timeout: int = RUN_TIMEOUT,
                inst_limit: int = INST_LIMIT) -> Report:
    """Compile, scan, assemble, and run one program, stopping at the first thing that
    does not go through and saying which it was."""
    source = workdir / f"{program.name}.c"
    source.write_text(program.source, encoding="utf-8", newline="\n")
    digest = _sha256(source.read_bytes())
    compiled = compile_c(ccomp, source, workdir / program.name, compile_timeout)
    if compiled.stream is None:
        return Report(program.name, program.pattern, digest, program.checks, compiled, (),
                      0, None, "ccomp-refused",
                      f"ccomp exited {compiled.exit_code}: {compiled.said}")
    elf = workdir / f"{program.name}.elf"
    found, size = assemble(compiled.stream, program.name, elf)
    if found:
        mnemonics = sum(1 for r in found if r.kind == "mnemonic")
        return Report(program.name, program.pattern, digest, program.checks, compiled,
                      tuple(found), 0, None, "dialect-refused",
                      f"{len(found)} line(s) the dialect does not assemble, "
                      f"{mnemonics} of them mnemonics")
    if simulator is None:
        return Report(program.name, program.pattern, digest, program.checks, compiled, (),
                      size, None, "assembled", f"{size} bytes of image; {waits}")
    ran = run_image(simulator, profile, elf, workdir, run_timeout, inst_limit)
    return Report(program.name, program.pattern, digest, program.checks, compiled, (),
                  size, ran, ran.verdict, ran.detail)


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
    }


def grouped(found: tuple[Refusal, ...] | list[Refusal]) -> list[tuple[str, str, list[int]]]:
    """The refusals as one row per name: kind, name, and the lines it occurs on."""
    rows: dict[tuple[str, str], list[int]] = {}
    for refusal in found:
        rows.setdefault((refusal.kind, refusal.name), []).append(refusal.line)
    order = {"mnemonic": 0, "directive": 1, "section": 2, "operand": 3, "symbol": 4,
             "layout": 5}
    return [(kind, name, lines) for (kind, name), lines
            in sorted(rows.items(), key=lambda item: (order.get(item[0][0], 9), item[0][1]))]


def disagreements(current: list[Report], against: dict[str, Json]) -> list[str]:
    """Where this run's answers to the two questions differ from a recorded run's.

    Compared by program name over the HTIF code and the trace digest, which are the two
    questions; a program one side did not run to a verdict is named as such rather than
    read as agreeing. The recorded run is a `--json` report of this command.
    """
    recorded = against.get("programs")
    if not isinstance(recorded, list):
        return ["the recorded run carries no `programs` list"]
    by_name: dict[str, dict[str, Json]] = {}
    for entry in recorded:
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            by_name[cast("str", entry["name"])] = entry
    out: list[str] = []
    for report in current:
        before = by_name.get(report.name)
        if before is None:
            out.append(f"{report.name}: not in the recorded run")
            continue
        was = before.get("run")
        if report.ran is None or not isinstance(was, dict):
            # one side or both stopped short of the emulator, so the verdicts are what
            # there is to compare: a stream refused here and assembled there is a finding
            if report.verdict != before.get("verdict"):
                out.append(f"{report.name}: verdict {report.verdict!r} against the "
                           f"recorded {before.get('verdict')!r}")
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


def read_output(path: Path) -> Output:
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
    if not (isinstance(side, str) and isinstance(digest, str) and isinstance(length, int)
            and isinstance(head, str) and isinstance(produced, str)
            and (verdict is None or isinstance(verdict, int))):
        raise ValueError(f"{path}: a field of the record is missing or of the wrong type")
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


def _inputs(args: argparse.Namespace) -> list[Program]:
    """The programs to run: the sources named, then the generated campaign."""
    out: list[Program] = []
    for spelled in args.source:
        path = Path(spelled)
        text = path.read_text(encoding="utf-8")
        out.append(Program(path.stem, "given", text, 0))
    if args.generate:
        out += programs(args.seed, args.generate)
    return out


def _print_report(report: Report) -> None:
    label = report.verdict.upper()
    print(f"{label:<15} {report.name}: {report.detail}")
    if report.compiled is not None and report.verdict != "ccomp-refused":
        print(f"{'':<15}   ccomp exited 0 with {report.compiled.lines} line(s), "
              f"sha256 {report.compiled.stream_sha256[:16]}")
    for kind, name, lines in grouped(report.refusals):
        where = ", ".join(str(n) for n in lines if n) or "(the stream)"
        note = next((r.detail for r in report.refusals
                     if r.kind == kind and r.name == name and r.detail), "")
        print(f"{'':<15}   {kind:<9} {name:<16} line(s) {where}"
              + (f": {note}" if note else ""))
    if report.ran is not None:
        print(f"{'':<15}   {report.ran.records} records, digest {report.ran.digest}, "
              f"capability round trip: {'yes' if report.ran.cap_roundtrip else 'no'}")


def _program(args: argparse.Namespace) -> int:
    root = corpus_mod.find_root()
    try:
        inputs = _inputs(args)
    except OSError as err:
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

    ccomp = [str(args.ccomp)]
    keep = Path(args.keep) if args.keep else None
    with tempfile.TemporaryDirectory(prefix="vos-compiler-diff-") as scratch:
        workdir = keep or Path(scratch)
        workdir.mkdir(parents=True, exist_ok=True)
        reports = [run_program(program, ccomp, workdir, simulator, profile, waits,
                               compile_timeout=args.timeout, run_timeout=args.run_timeout,
                               inst_limit=args.inst_limit)
                   for program in inputs]

    differs = disagreements(reports, against) if against is not None else []
    tally = {verdict: sum(1 for r in reports if r.verdict == verdict) for verdict in VERDICTS}
    closed = all(r.verdict == "pass" for r in reports) and not differs
    expected = (all(r.verdict == "dialect-refused" for r in reports)
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
            "expect": "refusal" if args.expect_refusal else "pass",
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
        print(f"{'DISAGREE':<15} {line}")
    counts = " ".join(f"{verdict}={tally[verdict]}" for verdict in VERDICTS)
    print(f"TOTAL {counts} of {len(reports)}"
          + (f"; {len(differs)} disagreement(s) with the recorded run" if against else ""))
    if closed:
        print("every program answered both questions; compiler campaign acceptance stays "
              "open until the integrated backend runs this loop")
    elif args.expect_refusal:
        print("the refusal is the expected verdict ahead of the backend (R-18-002): "
              + ("every stream was refused" if expected
                 else "and at least one stream was not refused, which is the finding"))
    else:
        print("the acceptance loop is open: not every program answered both questions")
    return 0 if expected else 1


def _component(args: argparse.Namespace) -> int:
    root = corpus_mod.find_root()
    host: Output | None = None
    purecap: Output | None = None
    host_bytes: bytes | None = None
    purecap_bytes: bytes | None = None
    try:
        if args.host_record:
            host = read_output(Path(args.host_record))
        elif args.wasm:
            runner = list(args.runner) if args.runner else list(NODE_RUNNER)
            host, host_bytes = wasm_output(Path(args.wasm), runner, root, args.timeout)
        if args.purecap_record:
            purecap = read_output(Path(args.purecap_record))
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
        print("nothing to compare: name a Wasm module or a host record, and an image with "
              "a simulator or a purecap record", file=sys.stderr)
        return 2

    for spelled, side in ((args.write_host, host), (args.write_purecap, purecap)):
        if spelled and side is not None:
            Path(spelled).write_text(json.dumps(side.to_json(), indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    verdict = (compare_outputs(host, purecap, host_bytes, purecap_bytes)
               if host is not None and purecap is not None else None)

    if args.json:
        payload: dict[str, Json] = {
            "scope": "component-level", "milestone_acceptance": "open",
            "encoding": ENCODING, "sources_sha256": _sources(root),
            "host": None if host is None else host.to_json(),
            "purecap": None if purecap is None else purecap.to_json(),
            "compared": host is not None and purecap is not None,
            "disagreement": None if verdict is None else verdict.line(),
        }
        print(json.dumps(payload, indent=2))
        return 1 if verdict is not None else 0

    for side in (host, purecap):
        if side is not None:
            print(f"{side.side.upper():<9} verdict {side.verdict}, {side.output_length} "
                  f"byte(s), sha256 {side.output_sha256[:16]}, head {side.output_head!r}")
            print(f"{'':<9} produced by: {side.produced_by}")
    if host is None or purecap is None:
        missing = "purecap" if purecap is None else "host"
        print(f"WAITS     the {missing} side: no record and no run was named for it; the "
              f"purecap side's producer is M1.2's integrated backend")
        return 0
    if verdict is None:
        print(f"AGREE     both sides under {ENCODING}: verdict {host.verdict} and "
              f"{host.output_length} byte(s)")
        return 0
    print(f"DISAGREE  {verdict.line()}")
    return 1


def _generate(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows: list[Json] = []
    for program in programs(args.seed, args.count):
        path = out / f"{program.name}.c"
        path.write_text(program.source, encoding="utf-8", newline="\n")
        rows.append({"name": program.name, "pattern": program.pattern,
                     "checks": program.checks, "sha256": _sha256(path.read_bytes())})
        print(f"WROTE   {path} ({program.pattern}, {program.checks} checks)")
    manifest: dict[str, Json] = {"seed": args.seed, "count": args.count, "programs": rows}
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
        sub.add_argument("--against", metavar="FILE",
                         help="a --json report of an earlier run to hold this one against")
        sub.add_argument("--expect-refusal", action="store_true",
                         help="ahead of the backend: green iff every stream is refused")
        sub.add_argument("--keep", metavar="DIR",
                         help="keep the streams and images here rather than in scratch")
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
        sub.add_argument("--elf", metavar="FILE", help="the component's lowered image")
        sub.add_argument("--purecap-record", metavar="FILE",
                         help="the purecap side, recorded")
        sub.add_argument("--write-host", metavar="FILE", help="record the host side here")
        sub.add_argument("--write-purecap", metavar="FILE",
                         help="record the purecap side here")
        sub.add_argument("--timeout", type=int, default=RUN_TIMEOUT,
                         help="seconds either side gets to run")
    if name in ("program", "component"):
        sub.add_argument("--simulator", metavar="PATH",
                         help="the golden emulator, a lane's c_emulator/sail_riscv_sim")
        sub.add_argument("--profile", metavar="FILE",
                         help=f"the configuration (default: model/{env.PROFILE_CONFIG})")
        sub.add_argument("--inst-limit", type=int, default=INST_LIMIT,
                         help="the emulator's instruction bound per run")
        sub.add_argument("--json", action="store_true",
                         help="emit the report as one JSON object")
    if name == "program":
        sub.add_argument("--lane", action="store_true",
                         help="use this checkout's own lane's simulator (guest only)")
    if name == "generate":
        sub.add_argument("--out", required=True, metavar="DIR", help="where to write them")
        sub.add_argument("--count", type=int, default=6, help="how many programs")
        sub.add_argument("--seed", type=int, default=1, help="the generator's seed")


TABLE: Table = {
    "program": (_program, "C through ccomp, the assembler, the composer and the emulator"),
    "component": (_component, "one Gallina component's Wasm-host run against its "
                              "purecap run, under the declared output encoding"),
    "generate": (_generate, "write the deterministic FP-free C campaign"),
}


def main(argv: list[str] | None = None) -> int:
    return dispatch(__doc__, TABLE, argv, _flags, prog="run.py compiler-diff")
