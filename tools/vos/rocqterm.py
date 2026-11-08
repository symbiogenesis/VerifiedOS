# SPDX-License-Identifier: Apache-2.0
"""Receipt and provenance helpers for the Sail-emitted canonical Rocq machine term.

See [docs/assurance/canonical-machine-term.md](../../docs/assurance/canonical-machine-term.md)
(R-05-019b). `run.py model rocq` builds `generated_rocq_rv64d` (`rv64d.v` and
`rv64d_types.v`) and writes `receipt.json` binding the Sail binary, Rocq plugin, Z3
solver, Sail library `.sail` files, project-selected model sources, profile
configuration, emitted files, and `Axiom` declarations.
"""

import hashlib
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import NotRequired, TypedDict

from vos import receipts

TARGET = "generated_rocq_rv64d"
STEM = "rv64d"
OUTPUTS = (f"{STEM}.v", f"{STEM}_types.v")
OUTPUT_DIR = "rocq"
RECEIPT = "receipt.json"
FORMAT = "verifiedos-rocq-term-1"

# Rocq backend plugin relative to `sail --dir` (`share/sail`).
PLUGIN = Path("..") / "libsail" / "plugins" / "sail_plugin_coq.cmxs"

MODEL_SOURCES = "model/model"

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
    """Raised when canonical-term generation inputs or toolchain state are invalid."""


class FileIdentity(TypedDict):
    """Digest, byte size, and line count of an emitted file."""

    sha256: str
    bytes: int
    lines: int


class Manifest(TypedDict):
    """File digest map with file count and aggregate SHA-256."""

    files: int
    aggregate: str
    sha256: dict[str, str]


class Named(TypedDict):
    """Single file path and SHA-256 digest."""

    path: str
    sha256: str


class Inputs(TypedDict):
    """Checkout inputs read during canonical-term emission."""

    sources: Manifest
    configuration: Named
    project_file: Named
    target_cmake: Named


class Tool(TypedDict):
    """Executable or plugin path, SHA-256 digest, and version line."""

    path: str
    sha256: str
    version: str


class Toolchain(TypedDict):
    """Selected Sail binary, Rocq plugin, Z3 solver, and Sail library manifest."""

    sail: Tool
    rocq_plugin: Tool
    z3: Tool
    library: Manifest
    loaded_plugins: NotRequired[list[Tool]]
    plugin_directories: NotRequired[list[str]]


class GeneratorIdentity(TypedDict):
    """Installed library contents and the native loader's ordered plugin selection."""

    library_root: str
    library: Manifest
    loaded_plugins: list[Tool]
    plugin_directories: list[str]


def output_dir(tree: Path) -> Path:
    """Return the `rocq/` output directory inside build `tree`."""
    return tree / OUTPUT_DIR


def clear(tree: Path) -> list[str]:
    """Delete any existing term outputs and receipt from `tree` and return their filenames."""
    removed: list[str] = []
    for name in (*OUTPUTS, RECEIPT):
        path = output_dir(tree) / name
        if path.is_file() or path.is_symlink():
            path.unlink()
            removed.append(name)
    return removed


def target_command(listing: str) -> list[str]:
    """Extract the unique Sail argv containing `--rocq-output-dir` from `ninja -t commands` output."""
    found: list[list[str]] = []
    for line in listing.splitlines():
        if "--rocq-output-dir" not in line:
            continue
        segments: list[list[str]] = [[]]
        for word in shlex.split(line):
            if word == "&&":
                segments.append([])
            elif word in {";", "||", "|", "&", ">", ">>"}:
                raise TermError("unsupported shell operator in the Rocq generation command")
            else:
                segments[-1].append(word)
        found.extend(segment for segment in segments if "--rocq-output-dir" in segment)
    if len(found) != 1:
        raise TermError(f"the configured tree has {len(found)} command(s) writing the "
                        f"Rocq output directory for {TARGET}, and one is what it emits")
    return found[0]


def option(argv: list[str], flag: str) -> str:
    """Return the argument following `flag` in `argv`, requiring `flag` to appear exactly once."""
    at = [i for i, arg in enumerate(argv) if arg == flag]
    if len(at) != 1 or at[0] + 1 >= len(argv):
        raise TermError(f"the target's command carries {flag} {len(at)} time(s), "
                        "and once with a value is what it is read from")
    return argv[at[0] + 1]


def require_profile(argv: list[str], profile: Path) -> None:
    """Verify that `argv` is a `--rocq` emission configured against `profile`."""
    configured = option(argv, "--config")
    if Path(configured).resolve() != profile.resolve():
        raise TermError(f"stale configuration: the configured target emits at "
                        f"{configured}, not the frozen profile {profile}; reconfigure "
                        "from a model whose target binds it")
    if "--rocq" not in argv:
        raise TermError("the configured target's command is not a Rocq emission")


def axioms(text: str) -> list[str]:
    """Return all top-level `Axiom` names declared in `text` in source order."""
    return [found.group(1) for found in AXIOM.finditer(text)]


def file_identity(path: Path) -> FileIdentity:
    """Compute `FileIdentity` (`sha256`, `bytes`, `lines`) for `path`."""
    data = path.read_bytes()
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "lines": data.count(b"\n")}


def aggregate(digests: dict[str, str]) -> str:
    """Compute the SHA-256 over sorted `<sha256>  <path>\\n` lines."""
    text = "".join(f"{digests[path]}  {path}\n" for path in sorted(digests))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def manifest(digests: dict[str, str]) -> Manifest:
    """Build a `Manifest` from `digests`."""
    ordered = dict(sorted(digests.items()))
    return {"files": len(ordered), "aggregate": aggregate(ordered), "sha256": ordered}


def listed_sources(sail: str, model_dir: Path) -> list[str]:
    """Return the `.sail` files selected by `riscv.sail_project` in compiler order."""
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
    """Build the `Inputs` manifest for `listed` sources and `profile`."""
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


def plugin_directories(share: Path) -> list[Path]:
    """Return the native plugin search directories loaded by Sail 0.20.3."""
    if "SAIL_NO_PLUGINS" in os.environ:
        raise TermError("SAIL_NO_PLUGINS disables the canonical Rocq plugin")
    override = os.environ.get("SAIL_PLUGIN_DIR")
    if override is None:
        if "SAIL_DIR" in os.environ or "DUNE_DIR_LOCATIONS" in os.environ:
            raise TermError("SAIL_DIR or DUNE_DIR_LOCATIONS can move the library or plugin "
                            "sites; an explicit absolute SAIL_PLUGIN_DIR is required")
        directories = [(share / PLUGIN).parent.resolve()]
    else:
        directories = [Path(value) for value in override.split(":")]
        if any(not value or not path.is_absolute()
               for value, path in zip(override.split(":"), directories, strict=True)):
            raise TermError("SAIL_PLUGIN_DIR requires nonempty absolute native directories")
    for directory in directories:
        if not directory.is_dir():
            raise TermError(f"Sail plugin directory does not exist: {directory}")
    return directories


def loaded_plugins(share: Path) -> list[Path]:
    """Return every `.cmxs` plugin loaded by Sail in `os.scandir` order."""
    loaded = []
    for directory in plugin_directories(share):
        with os.scandir(directory) as entries:
            loaded.extend(directory / entry.name for entry in entries
                          if entry.name.endswith(".cmxs") and entry.name[:-5].strip("."))
    return loaded


def selected_plugin(share: Path) -> Path:
    """Return the unique `sail_plugin_coq.cmxs` path among `loaded_plugins(share)`."""
    candidates = [path for path in loaded_plugins(share) if path.name == PLUGIN.name]
    if len(candidates) != 1 or not candidates[0].is_file():
        raise TermError(f"Sail's selected directories contain {len(candidates)} Rocq "
                        "plugin candidates; exactly one existing native plugin is required")
    return candidates[0].resolve()


def generator_identity(sail: str) -> GeneratorIdentity:
    """Bind installed generator inputs when reusing ordinary model evidence."""
    share = Path(_output([sail, "--dir"]).strip())
    if not share.is_absolute():
        raise TermError("sail --dir must name an absolute library directory")
    library = share / "lib"
    files: dict[str, str] = {}
    for path in library.rglob("*"):
        if path.is_dir():
            if path.is_symlink():
                raise TermError(f"unsupported linked Sail library directory: {path}")
            continue
        if not path.is_file():
            raise TermError(f"Sail library input is not a regular file: {path}")
        files[path.relative_to(library).as_posix()] = receipts.digest(path)
    if not any(name.endswith(".sail") for name in files):
        raise TermError(f"no Sail library files under {library}")
    return {"library_root": str(library.resolve()), "library": manifest(files),
            "loaded_plugins": [_tool(str(path), "") for path in loaded_plugins(share)],
            "plugin_directories": [str(path.resolve()) for path in plugin_directories(share)]}


def toolchain(sail: str, z3: str) -> Toolchain:
    """Record the `Toolchain` manifest for `sail`, its plugins/library, and `z3`."""
    share = Path(_output([sail, "--dir"]).strip())
    if not share.is_absolute():
        raise TermError("sail --dir must name an absolute library directory")
    plugin = selected_plugin(share)
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
        "loaded_plugins": [_tool(str(path), "") for path in loaded_plugins(share)],
        "plugin_directories": [str(path.resolve()) for path in plugin_directories(share)],
    }


def revision(root: Path, git_env: dict[str, str]) -> dict[str, object]:
    """Return `root`'s `HEAD` commit hash and whether `model/` has uncommitted changes."""
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
    """Build the receipt payload for the canonical Rocq term emitted in `tree`."""
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
    """Replace `tree` and `root` paths in `argv` with `<tree>` and `<checkout>` placeholders."""
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
    with tempfile.TemporaryDirectory(prefix="vos-rocq-term-query-") as temporary:
        done = subprocess.run(argv, cwd=Path(temporary).resolve(), capture_output=True,
                              encoding="utf-8", errors="replace", check=False, timeout=120)
    if done.returncode != 0:
        raise TermError(f"{argv[0]} {' '.join(argv[1:])} exited {done.returncode}")
    return done.stdout


def _tool(path: str, version: str) -> Tool:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise TermError(f"{resolved} is not a file, and the term's identity names it")
    return {"path": str(resolved), "sha256": receipts.digest(resolved),
            "version": version.strip().splitlines()[0] if version.strip() else ""}
