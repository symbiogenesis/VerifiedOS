# SPDX-License-Identifier: Apache-2.0
"""Compile a set of Sail sources together with a harness, and run what comes out.

This is the rig M2.1 built and R1a rebuilt: hand Sail a list of model files and one
more file that calls into them, take the C it emits, link it against Sail's own
runtime, and run the executable. Nothing about it is specific to the capability
format, and it was written inside [the RTL lane](cli/rtl.py) because at the time there
was one caller. There are now three, so it lives here and the callers name their own
sources.

**The two steps are named separately because they fail differently.** Sail typechecks
the sources and emits C, so a model file that has moved fails the first with a Sail
error naming it; the C compiler links that against Sail's runtime, so an absent GMP
fails the second. A caller that reported one failure for both would send a reader to
the wrong half.
"""

import re
import shutil
import subprocess
from itertools import zip_longest
from pathlib import Path

# Sail's own C runtime, named rather than globbed: a runtime file arriving under a new
# name should be a failed build with a message and not a silent change of what was
# linked.
RUNTIME: tuple[str, ...] = (
    "sail.c", "rts.c", "elf.c", "sail_failure.c", "cJSON.c", "sail_config.c",
)

SAIL_HOW = ("the Sail toolchain lives in the opam `default` switch, which `vos/env.py` "
            "puts on PATH")

# `<kind> <inputs> -> <outputs>`, and the kind is the first token. Read out of the file
# rather than from a list a caller would have to keep in step with the harness.
KIND_RE = re.compile(r"^([a-z]+) ")


def require(name: str, how: str, out: list[str]) -> str | None:
    """One prerequisite, refused by name rather than by the error its absence produces
    three commands later."""
    found = shutil.which(name)
    if found is None:
        out.append(f"FAIL {name} is not on PATH; {how}")
        return None
    return found


def sail_lib(sail: str) -> Path:
    """Sail's own library directory, asked of Sail rather than derived from a switch
    name, so that a re-installed toolchain moves this without an edit."""
    done = subprocess.run([sail, "--dir"], capture_output=True, encoding="utf-8",
                          errors="replace", check=False)
    return Path(done.stdout.strip()) / "lib"


def build(sources: list[Path], work: Path, out: list[str],
          stem: str = "gen") -> Path | None:
    """Compile `sources` into an executable under `work`, or say why not.

    The last source is the harness by convention rather than by declaration: Sail takes
    one file list and the order that matters is dependency order, which is the caller's
    to know.

    Deliberately without `--c-no-mangle`. Readable names would be pleasant and are not
    worth the collision: the model's own `bit_to_bool` is the name Sail's C runtime
    already gives a static inline, so an unmangled emission that reaches it fails to
    compile on a redefinition several hundred lines from anything a caller wrote.
    """
    sail = require("sail", SAIL_HOW, out)
    if sail is None:
        return None
    compiler = shutil.which("cc") or shutil.which("gcc")
    if compiler is None:
        out.append("FAIL neither cc nor gcc is on PATH, so the emitted C cannot be "
                   "compiled")
        return None

    missing = [str(s) for s in sources if not s.is_file()]
    if missing:
        out.extend(f"FAIL {s} is not a file" for s in missing)
        return None

    work.mkdir(parents=True, exist_ok=True)
    emitted = work / f"{stem}.c"
    emitted.unlink(missing_ok=True)
    done = subprocess.run([sail, "-c", "-o", stem, *[str(s) for s in sources]],
                          capture_output=True, encoding="utf-8", errors="replace",
                          check=False, cwd=work)
    if done.returncode != 0 or not emitted.is_file():
        out.append(done.stdout + done.stderr)
        out.append("FAIL sail did not emit C for the harness")
        return None

    lib = sail_lib(sail)
    runtime = [lib / name for name in RUNTIME]
    absent = [str(p) for p in runtime if not p.is_file()]
    if absent:
        out.extend(f"FAIL {p} is not in Sail's library directory" for p in absent)
        return None

    binary = work / stem
    binary.unlink(missing_ok=True)
    done = subprocess.run([compiler, "-O2", "-o", str(binary), str(emitted),
                           *[str(p) for p in runtime], "-I", str(lib), "-lgmp", "-lm"],
                          capture_output=True, encoding="utf-8", errors="replace",
                          check=False, cwd=work)
    if done.returncode != 0:
        out.append(done.stdout + done.stderr)
        out.append("FAIL the emitted C did not compile against Sail's runtime")
        return None
    return binary


def emit(binary: Path, target: Path, out: list[str], timeout: int = 1800) -> bool:
    """Run the harness with its whole output going to `target`.

    Straight to a file rather than through a pipe: a sweep's output is tens of
    megabytes and a caller that read it into memory to write it out again would hold
    the whole of both.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as handle:
        try:
            done = subprocess.run([str(binary)], stdout=handle,
                                  stderr=subprocess.PIPE, check=False,
                                  cwd=binary.parent, timeout=timeout)
        except subprocess.TimeoutExpired:
            out.append(f"FAIL the harness overran {timeout} s and was killed")
            return False
    if done.returncode != 0:
        out.append((done.stderr or b"").decode("utf-8", "replace"))
        out.append(f"FAIL the harness exited {done.returncode}")
        return False
    return True


def census(path: Path) -> tuple[dict[str, int], int, int]:
    """What one vector file holds: how many of each kind, how many vectors, and how
    many lines are commentary rather than vectors.

    The kinds are read out of the file rather than declared by the caller, so a kind a
    harness adds is counted the day it is added.
    """
    kinds: dict[str, int] = {}
    vectors = 0
    other = 0
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        for line in handle:
            found = KIND_RE.match(line)
            if found is None:
                other += 1
                continue
            kinds[found.group(1)] = kinds.get(found.group(1), 0) + 1
            vectors += 1
    return kinds, vectors, other


def compare(want: Path, got: Path, shown: int = 8) -> tuple[list[str], int, int, int]:
    """Two vector files, line against line: what disagrees, how much, and how long each
    file is.

    Streamed rather than read whole, a pair being over a hundred megabytes together,
    and compared on the raw line so a trailing-whitespace difference is a disagreement
    rather than something a strip would hide. `zip_longest` rather than `zip`, so a
    file that stops early is a run of disagreements at the line it stopped on rather
    than a comparison that quietly ends there and reports the prefix green.
    """
    examples: list[str] = []
    bad = 0
    n_want = 0
    n_got = 0
    with (want.open(encoding="utf-8", errors="replace", newline="") as a,
          got.open(encoding="utf-8", errors="replace", newline="") as b):
        for n, (left, right) in enumerate(zip_longest(a, b), start=1):
            if left is not None:
                n_want = n
            if right is not None:
                n_got = n
            if left == right:
                continue
            bad += 1
            if len(examples) < shown * 2:
                gone = "<no line>"
                examples.append(f"line {n} a: "
                                f"{gone if left is None else left.rstrip()}")
                examples.append(f"line {n} b: "
                                f"{gone if right is None else right.rstrip()}")
    if n_want != n_got:
        examples.append(f"one side wrote {n_want} line(s) and the other {n_got}, so "
                        "one of them stopped before the other")
    return examples, bad, n_want, n_got
