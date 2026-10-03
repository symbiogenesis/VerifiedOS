# SPDX-License-Identifier: Apache-2.0
"""The canonical machine term: what the model's Rocq target emits, and what names it.

R-05-019b makes the Rocq definitions Sail's own backend emits from the frozen model the
one term the Iris-over-Sail logic and the RTL refinement quantify over, and
[the canonical-term record](../../docs/assurance/canonical-machine-term.md) states how
it is emitted and what identifies it. `run.py model rocq` runs the model's own
`generated_rocq_rv64d` target in the lane's tree and writes this module's receipt
beside the two files the target emits. This module holds the parses and the identity;
the command holds the lock, the configure and the build.

**Stale outputs are deleted before anything else, and that is most of why the command
exists rather than a bare cmake call.** The target's DEPENDS name the Sail sources, the
project file and the configuration, but not the Sail binary, its library or its Rocq
plugin, so outputs older than a toolchain change satisfy the target without an
emission, and a receipt read beside them would name a term nothing emitted. A refused
run deletes what it emitted as well, so no output stands without its receipt.

**The target must read the frozen profile.** The emission fixes every configuration
leaf into the term, hart identity included, so a tree configured from a target that
names another file emits another machine's term (F-478 in the findings register). The
command reads the configured Sail command back out of the tree's own ninja file and
refuses one whose `--config` is not this checkout's primary composition, and it
refuses a run whose configuration or sources changed while Sail read them.

**What the receipt binds, and what it does not.** The Sail binary, its Rocq plugin and
the solver by SHA-256; every `.sail` file under the Sail library directory, which is
more than the term includes and binds the implicit inclusions with the rest; the
source list the project file yields, each file by SHA-256 and the list by the
aggregate the record states; the configuration, the project file and the target's
CMake file; the command; both outputs; and the names of the term's `Axiom`
declarations. It is a record of one run, not a compile: whether the term compiles at
the locked prover, and which assumptions the kernel checker reads in its closure, are
the record's owed readings and nothing here decides them.
"""

import hashlib
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import TypedDict

from vos import receipts

# The target, the stem it passes to `-o`, and the two files it writes under the tree's
# `rocq/` directory, as model/model/CMakeLists.txt states them.
TARGET = "generated_rocq_rv64d"
STEM = "rv64d"
OUTPUTS = (f"{STEM}.v", f"{STEM}_types.v")
OUTPUT_DIR = "rocq"
RECEIPT = "receipt.json"
FORMAT = "verifiedos-rocq-term-1"

# The Rocq backend's plugin, relative to the directory `sail --dir` names, which is the
# switch's `share/sail`.
PLUGIN = Path("..") / "libsail" / "plugins" / "sail_plugin_coq.cmxs"

# Where the sources Sail lists sit, relative to the checkout: the project file's paths
# are relative to the directory it is in.
MODEL_SOURCES = "model/model"

# An `Axiom` declaration opening a line, which is the form the backend writes for a
# function the model declares and does not define for the target.
AXIOM = re.compile(r"^Axiom\s+([A-Za-z_][A-Za-z0-9_']*)", re.MULTILINE)

PREDICATES = {
    "digest": "SHA-256 of the file's bytes; a line is a newline character",
    "sources": "the files `sail riscv.sail_project --all-modules --list-files-separated "
               "';'` lists from model/model, keyed by repository path; the aggregate is "
               "the SHA-256 of the lines `<sha256>  <path>` sorted by path, each ending "
               "in a newline",
    "library": "every file ending .sail under `sail --dir`/lib, keyed relative to it, "
               "aggregated as the sources are",
    "axioms": "the names of the lines of the main output that open with `Axiom`",
}


class TermError(ValueError):
    """A run this module refuses, named at what it read rather than at the build."""


class FileIdentity(TypedDict):
    """One emitted file: its digest, its size and its line count."""

    sha256: str
    bytes: int
    lines: int


class Manifest(TypedDict):
    """A set of files by digest, with their count and aggregate."""

    files: int
    aggregate: str
    sha256: dict[str, str]


class Named(TypedDict):
    """One file named by its path and digest."""

    path: str
    sha256: str


class Inputs(TypedDict):
    """What the emission reads from the checkout."""

    sources: Manifest
    configuration: Named
    project_file: Named
    target_cmake: Named


class Tool(TypedDict):
    """One executable or plugin: where it was, its digest and, for a binary, its
    version line."""

    path: str
    sha256: str
    version: str


class Toolchain(TypedDict):
    """The selected Sail, its Rocq plugin, the solver and the Sail library."""

    sail: Tool
    rocq_plugin: Tool
    z3: Tool
    library: Manifest


def output_dir(tree: Path) -> Path:
    """Where the target writes the term in a build tree."""
    return tree / OUTPUT_DIR


def clear(tree: Path) -> list[str]:
    """Delete the term's outputs and receipt from a tree, naming what was there."""
    removed: list[str] = []
    for name in (*OUTPUTS, RECEIPT):
        path = output_dir(tree) / name
        if path.is_file() or path.is_symlink():
            path.unlink()
            removed.append(name)
    return removed


def target_command(listing: str) -> list[str]:
    """The Sail argv of the target's emission, out of `ninja -t commands`.

    Exactly one command of the target's closure writes the Rocq output directory; none,
    or two, is a tree this module cannot read rather than a guess between them. CMake
    writes the step as `cd <dir> && <argv>`, so the argv is what follows the `&&`.
    """
    found: list[list[str]] = []
    for line in listing.splitlines():
        if "--rocq-output-dir" not in line:
            continue
        _, sep, tail = line.partition(" && ")
        found.append(shlex.split(tail if sep else line))
    if len(found) != 1:
        raise TermError(f"the configured tree has {len(found)} command(s) writing the "
                        f"Rocq output directory for {TARGET}, and one is what it emits")
    return found[0]


def option(argv: list[str], flag: str) -> str:
    """The value one flag carries, refusing a command that carries it other than once."""
    at = [i for i, arg in enumerate(argv) if arg == flag]
    if len(at) != 1 or at[0] + 1 >= len(argv):
        raise TermError(f"the target's command carries {flag} {len(at)} time(s), "
                        "and once with a value is what it is read from")
    return argv[at[0] + 1]


def require_profile(argv: list[str], profile: Path) -> None:
    """Refuse a configured target that does not emit at the frozen profile."""
    configured = option(argv, "--config")
    if Path(configured).resolve() != profile.resolve():
        raise TermError(f"stale configuration: the configured target emits at "
                        f"{configured}, not the frozen profile {profile}; reconfigure "
                        "from a model whose target binds it")
    if "--rocq" not in argv:
        raise TermError("the configured target's command is not a Rocq emission")


def axioms(text: str) -> list[str]:
    """The names the term declares as axioms, in the order it declares them."""
    return [found.group(1) for found in AXIOM.finditer(text)]


def file_identity(path: Path) -> FileIdentity:
    """One emitted file's identity."""
    data = path.read_bytes()
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "lines": data.count(b"\n")}


def aggregate(digests: dict[str, str]) -> str:
    """The record's aggregate over a set of files: the SHA-256 of `<sha256>  <path>`
    lines sorted by path, each ending in a newline."""
    text = "".join(f"{digests[path]}  {path}\n" for path in sorted(digests))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def manifest(digests: dict[str, str]) -> Manifest:
    """A set of files with its count and aggregate."""
    ordered = dict(sorted(digests.items()))
    return {"files": len(ordered), "aggregate": aggregate(ordered), "sha256": ordered}


def listed_sources(sail: str, model_dir: Path) -> list[str]:
    """The source files the project file selects, relative to its directory, in the
    order Sail lists them."""
    done = subprocess.run([sail, "riscv.sail_project", "--all-modules",
                           "--list-files-separated", ";"],
                          cwd=model_dir / "model", capture_output=True, encoding="utf-8",
                          errors="replace", check=False, timeout=300)
    if done.returncode != 0:
        raise TermError(f"sail could not list the project's sources: {done.stderr.strip()}")
    listed = [rel for rel in done.stdout.strip().split(";") if rel]
    if not listed:
        raise TermError("sail listed no sources for the project")
    return listed


def inputs(root: Path, listed: list[str], profile: Path) -> Inputs:
    """What one emission reads from the checkout, by digest."""
    model_dir = root / MODEL_SOURCES

    def named(path: Path) -> Named:
        return {"path": _relative(path, root), "sha256": receipts.digest(path)}

    return {
        "sources": manifest({f"{MODEL_SOURCES}/{rel}": receipts.digest(model_dir / rel)
                             for rel in listed}),
        "configuration": named(profile),
        "project_file": named(model_dir / "riscv.sail_project"),
        "target_cmake": named(model_dir / "CMakeLists.txt"),
    }


def toolchain(sail: str, z3: str) -> Toolchain:
    """The selected Sail with its plugin and library, and the solver, by digest."""
    share = Path(_output([sail, "--dir"]).strip())
    plugin = (share / PLUGIN).resolve()
    library = share / "lib"
    files = {path.relative_to(library).as_posix(): receipts.digest(path)
             for path in library.rglob("*.sail") if path.is_file()}
    if not files:
        raise TermError(f"no Sail library files under {library}")
    return {
        "sail": _tool(sail, _output([sail, "--version"])),
        "rocq_plugin": _tool(str(plugin), ""),
        "z3": _tool(z3, _output([z3, "--version"])),
        "library": manifest(files),
    }


def revision(root: Path, git_env: dict[str, str]) -> dict[str, object]:
    """The checkout's commit, and whether its model differs from that commit."""
    env = {**os.environ, **git_env}
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                          encoding="utf-8", check=False, timeout=60, env=env)
    status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all",
                             "--", "model"], cwd=root, capture_output=True,
                            encoding="utf-8", check=False, timeout=120, env=env)
    if head.returncode or status.returncode:
        raise TermError("git could not identify the checkout the term was emitted from")
    return {"revision": head.stdout.strip(), "model_dirty": bool(status.stdout.strip())}


def receipt(*, command: list[str], tools: Toolchain, read: Inputs,
            checkout: dict[str, object], tree: Path, started: str, finished: str,
            elapsed: float) -> dict[str, object]:
    """The generation identity of the term a run left in `tree`."""
    main = output_dir(tree) / OUTPUTS[0]
    names = axioms(main.read_text(encoding="utf-8", errors="replace"))
    return {
        "format": FORMAT,
        "target": TARGET,
        "started_at": started,
        "finished_at": finished,
        "elapsed_seconds": round(elapsed, 3),
        "checkout": checkout,
        "command": command,
        "toolchain": tools,
        "inputs": read,
        "outputs": {name: file_identity(output_dir(tree) / name) for name in OUTPUTS},
        "axioms": {"count": len(names), "names": names},
        "predicates": PREDICATES,
    }


def placeheld(argv: list[str], tree: Path, root: Path) -> list[str]:
    """The command with the lane's tree and the checkout written as placeholders, so
    two lanes' receipts state one command."""
    out: list[str] = []
    for arg in argv:
        held = arg
        for path, mark in ((tree, "<tree>"), (root, "<checkout>")):
            held = held.replace(str(path), mark).replace(path.as_posix(), mark)
        out.append(held)
    return out


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _output(argv: list[str]) -> str:
    done = subprocess.run(argv, capture_output=True, encoding="utf-8", errors="replace",
                          check=False, timeout=120)
    if done.returncode != 0:
        raise TermError(f"{argv[0]} {' '.join(argv[1:])} exited {done.returncode}")
    return done.stdout


def _tool(path: str, version: str) -> Tool:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise TermError(f"{resolved} is not a file, and the term's identity names it")
    return {"path": str(resolved), "sha256": receipts.digest(resolved),
            "version": version.strip().splitlines()[0] if version.strip() else ""}
