# SPDX-License-Identifier: Apache-2.0
"""Compile Sail sources with a harness and run or compare the emitted executable.

Compilation is split into Sail-to-C emission and C compilation against Sail's runtime so
that Sail typechecking failures and C compiler/library failures are reported separately.
"""

import re
import shutil
import subprocess
from itertools import zip_longest
from pathlib import Path

from vos import env

# Explicit Sail C runtime sources so an upstream runtime change fails compilation loudly.
RUNTIME: tuple[str, ...] = (
    "sail.c", "rts.c", "elf.c", "sail_failure.c", "cJSON.c", "sail_config.c",
)

SAIL_HOW = env.install_line(env.SAIL_INSTALL)

# Vector line kind prefix (`<kind> <inputs> -> <outputs>`).
KIND_RE = re.compile(r"^([a-z]+) ")


def require(name: str, how: str, out: list[str]) -> str | None:
    """Resolve `name` on `PATH` or record an installation failure in `out`."""
    found = shutil.which(name)
    if found is None:
        out.append(f"FAIL {name} is not on PATH; {how}")
        return None
    return found


def sail_lib(sail: str) -> Path:
    """Return Sail's C library directory via `sail --dir`."""
    done = subprocess.run([sail, "--dir"], capture_output=True, encoding="utf-8",
                          errors="replace", check=False)
    return Path(done.stdout.strip()) / "lib"


def build(sources: list[Path], work: Path, out: list[str],
          stem: str = "gen") -> Path | None:
    """Compile `sources` (in dependency order, harness last) into an executable under `work`.

    Omits `--c-no-mangle` so model identifiers such as `bit_to_bool` do not collide with
    Sail's C runtime declarations.
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
    """Run `binary` and stream its stdout directly to `target`."""
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
    """Return `(counts_by_kind, vector_lines, non_vector_lines)` for vector file `path`."""
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
    """Stream-compare vector files `want` and `got` line by line with `zip_longest`."""
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
