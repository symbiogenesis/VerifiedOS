#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""RTL lane: authored/generated SystemVerilog lint, model cross-check, and absence-contract elaboration.

Subcommands:
- `provenance`: parse and print [rtl/synthesis-provenance.md](../../../rtl/synthesis-provenance.md).
- `filelist`: compose the curated elaboration file list and validate `SUBSTITUTIONS`.
- `lint`: run Verilator `--lint-only` over standalone authored and generated sources in `rtl/`.
- `widthcheck` / `device-regs` / `devicescheck`: verify scalar transport widths and standalone device wrappers.
- `vectors` / `crosscheck`: emit capability-format vectors from Sail and replay them through
  `rtl/vos_cheri_pkg.sv`.
- `elaborate` / `wait`: elaborate the imported CVA6 core at the curated and stock configurations
  and partition module differences into parameter-removed, displaced, and introduced structures.
"""

import argparse
import json
import re
import shutil
import subprocess
import tarfile
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from vos import (
    cli,
    device_registers,
    device_regs,
    env,
    provenance,
    receipts,
    rtl_vectors,
    rtl_width,
    sailrig,
    socmap,
)
from vos.corpus import find_root

# Pinned Verilator release built into a versioned project prefix.
VERILATOR_PIN = "5.054"
VERILATOR_URL = ("https://github.com/verilator/verilator/archive/refs/tags/"
                 f"v{VERILATOR_PIN}.tar.gz")
VERILATOR_SHA256 = "18658731b46922ef660bcb650be0aa503d751e5c17eb9d4644fdfabb11835198"
# Annotated tag object and tagged commit SHA-1 per Verilator release.
VERILATOR_TAGS: dict[str, tuple[str, str]] = {
    "5.054": ("76d93f464fe9e24e4e407dcb565d95c7f71a82a9",
              "bbb60a403932a9f695cb6ff001ceb73de6ad9234"),
}
VERILATOR_HOW = "python tools/run.py rtl install"
VERILATOR_PREREQUISITES = ("autoconf", "bison", "flex", "g++", "make", "help2man")
VERILATOR_PACKAGES = (*VERILATOR_PREREQUISITES, "libfl-dev")

FORMAT_PACKAGE = "rtl/vos_cheri_pkg.sv"
ADAPTER_PACKAGE = "rtl/vos_cva6_cheri_pkg.sv"
WIDTH_PACKAGE = "rtl/vos_scalar_width_pkg.sv"

# Standalone-lintable authored sources in dependency order.
AUTHORED: tuple[str, ...] = (
    FORMAT_PACKAGE,
    WIDTH_PACKAGE,
    ADAPTER_PACKAGE,
    "rtl/vos_soc_decode.sv",
    "rtl/vos_uart.sv",
    "rtl/vos_block_device.sv",
    "rtl/vos_device_route.sv",
)

# Generated sources under `rtl/`, linted ahead of `AUTHORED`.
GENERATED: tuple[str, ...] = (
    socmap.ARTIFACT,
    device_regs.ARTIFACT,
    device_registers.RTL_ARTIFACT,
)

SOURCES: tuple[str, ...] = (*GENERATED, *AUTHORED)


@dataclass(frozen=True)
class Substitution:
    """An authored RTL source replacing one or more imported manifest entries in the curated arm."""

    imported: tuple[str, ...]
    authored: str
    requires: tuple[str, ...] = ()

    @property
    def placed(self) -> tuple[str, ...]:
        """All authored paths placed into the file list, in compile order."""
        return (*self.requires, self.authored)


IMPORTED_FORMAT_PACKAGE = "core/include/cva6_cheri_pkg.sv"

SUBSTITUTIONS: tuple[Substitution, ...] = (
    Substitution(imported=(IMPORTED_FORMAT_PACKAGE,), authored=ADAPTER_PACKAGE,
                 requires=(FORMAT_PACKAGE, WIDTH_PACKAGE)),
)

HARNESS = "tools/cheri-equiv/vos_cheri_vectors_tb.sv"
HARNESS_TOP = "vos_cheri_vectors_tb"
MODEL_SOURCES = rtl_vectors.SOURCES
VECTORS = "vectors.txt"
REPLAY = "replay.txt"
SHOWN = 8
UNHANDLED_RE = re.compile(r"(\d+) of an unknown kind")

CORE = "upstream/cva6-cheri"
CORE_FLIST = "core/Flist.cva6"
CORE_VAR = "${CVA6_REPO_DIR}"
PRIM_UPSTREAM = "upstream/mocha"
PRIM = f"{PRIM_UPSTREAM}/hw/vendor/lowrisc_ip/ip"
PRIM_ASSERTIONS = "prim/rtl/prim_assert.sv"

PRIM_PACKAGES: tuple[str, ...] = (
    "prim_generic/rtl/prim_ram_1p_pkg.sv",
    "prim/rtl/prim_cipher_pkg.sv",
    "prim/rtl/prim_util_pkg.sv",
)
PRIM_LIBRARIES: tuple[str, ...] = ("prim/rtl", "prim_generic/rtl")

# Uninitialized upstream submodule trees not reached by the curated or baseline configuration.
UNREACHED = re.compile(r"cvfpu|opene906|openc910|fpu_wrap|HPDCACHE_DIR|hpdcache")

STOCK_CONFIG = "core/include/cv64a6_imafdczcheri_sv39_config_pkg.sv"

# Disable RVF/RVD in the baseline so elaboration does not require the uninitialized `cvfpu` submodule (A-15).
BASELINE_EDITS: tuple[tuple[str, str], ...] = (
    ("CVA6ConfigRVF = 1", "CVA6ConfigRVF = 0"),
    ("CVA6ConfigRVD = 1", "CVA6ConfigRVD = 0"),
)

LINE_COMMENT_RE = re.compile(r"//[^\n]*")
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
MODULE_DECL_RE = re.compile(r"^[ \t]*module[ \t]+([A-Za-z_]\w*)", re.MULTILINE)

MARKER = "ALL_DONE"


def verilator_prefix() -> Path:
    """Return the versioned Verilator installation prefix under the guest build root."""
    return env.build_root() / "toolchains" / f"verilator-{VERILATOR_PIN}"


def _installed_verilator() -> str | None:
    """Return the project-local Verilator binary path if its install receipt matches `VERILATOR_SHA256`."""
    local = verilator_prefix() / "bin" / "verilator"
    receipt = verilator_prefix() / "source.sha256"
    if (local.is_file() and receipt.is_file()
            and receipt.read_text(encoding="utf-8").strip() == VERILATOR_SHA256):
        return str(local)
    return None


def _verilator() -> str | None:
    """Return the project-installed Verilator binary or fall back to `PATH`."""
    return _installed_verilator() or shutil.which("verilator")


def _verilator_version(binary: str) -> str:
    """Return the bare version string reported by `binary --version`."""
    done = subprocess.run([binary, "--version"], capture_output=True, encoding="utf-8",
                          errors="replace", check=False)
    found = re.search(r"Verilator\s+(\d+\.\d+)", done.stdout)
    return str(found.group(1)) if found else done.stdout.strip()


def _require_verilator(out: list[str]) -> str | None:
    """Return the Verilator binary if installed at `VERILATOR_PIN`, else append an error to `out`."""
    binary = _verilator()
    if binary is None:
        out.append(f"FAIL verilator is not installed; {VERILATOR_HOW}")
        return None
    version = _verilator_version(binary)
    if version != VERILATOR_PIN:
        out.append(f"FAIL verilator is {version} where this lane pins "
                   f"{VERILATOR_PIN}; a version other than the pin is a finding")
        return None
    return binary


def _extract_verilator(archive: Path, work: Path) -> Path:
    """Download, verify, and extract the Verilator source archive into `work`."""
    receipts.download(VERILATOR_URL, archive, VERILATOR_SHA256)
    source_dir = work / f"verilator-{VERILATOR_PIN}"
    if source_dir.is_symlink() or source_dir.resolve().parent != work.resolve():
        raise ValueError(f"{source_dir}: source directory escapes its build workspace")
    if source_dir.exists():
        shutil.rmtree(source_dir)
    with tarfile.open(archive) as source:
        source.extractall(work, filter="data")
    return source_dir


def cmd_install(args: argparse.Namespace) -> int:
    """Build and install the pinned Verilator release into `verilator_prefix()`."""
    prefix = verilator_prefix()
    with env.hold_lock(prefix, "Verilator installation"):
        binary = prefix / "bin" / "verilator"
        if bool(_installed_verilator()) and _verilator_version(str(binary)) == VERILATOR_PIN:
            print(f"ok verilator {VERILATOR_PIN} at {binary}")
            return 0
        missing = [name for name in VERILATOR_PREREQUISITES if not bool(shutil.which(name))]
        if not missing:
            header = subprocess.run(("g++", "-x", "c++", "-E", "-include", "FlexLexer.h", "-"),
                                    input="", text=True, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE, check=False)
            if header.returncode:
                missing.append("FlexLexer.h (libfl-dev)")
        if missing:
            print(f"FAIL missing build prerequisites: {', '.join(missing)}; "
                  "apt-get install -y --no-upgrade --no-install-recommends "
                  + " ".join(VERILATOR_PACKAGES))
            return 1
        (prefix / "source.sha256").unlink(missing_ok=True)
        lane_root = env.lane_root(env.lane_of(find_root()))
        work = lane_root / f"verilator-{VERILATOR_PIN}-source"
        work.mkdir(parents=True, exist_ok=True)
        archive = work / f"verilator-{VERILATOR_PIN}.tar.gz"
        log_path = work / "build.log"
        print(f"== verilator {VERILATOR_PIN}: source and log {work}; install {prefix}",
              flush=True)
        try:
            jobs = args.jobs if args.jobs is not None else env.worker_jobs(2048, label="toolchain")
            source = _extract_verilator(archive, work)
            steps = (("autoconf",), ("./configure", f"--prefix={prefix}"),
                     ("make", f"-j{jobs}"), ("make", "install"))
            with log_path.open("w", encoding="utf-8") as log:
                for argv in steps:
                    print(f"== {' '.join(argv)}; log {log_path}", flush=True)
                    log.write(f"== {' '.join(argv)}\n")
                    log.flush()
                    code = subprocess.run(argv, cwd=source, stdout=log, stderr=log,
                                          check=False).returncode
                    if code:
                        print(f"FAIL {argv[0]} exited {code}; see {log_path}")
                        return 1
        except (OSError, ValueError, tarfile.TarError) as error:
            print(f"FAIL Verilator installation: {error}")
            return 1
        if _verilator_version(str(binary)) != VERILATOR_PIN:
            print(f"FAIL {binary} did not report Verilator {VERILATOR_PIN}")
            return 1
        (prefix / "source.sha256").write_text(VERILATOR_SHA256 + "\n", encoding="utf-8")
        print(f"ok verilator {VERILATOR_PIN} at {binary}")
        return 0


def _settings(row: provenance.Row) -> str:
    """Format a provenance row's parameter settings."""
    return ", ".join(f"{name} = {value}" for name, value in row.settings)


def cmd_provenance(args: argparse.Namespace) -> int:
    """Parse and print the synthesis-provenance record."""
    del args
    root = find_root()
    record = provenance.read(root)
    out: list[str] = []
    if not record.present:
        print(f"FAIL {provenance.RECORD} is not in the repository")
        return 1

    bound = [row for row in record.absences if row.settings]
    unbound = [row for row in record.absences if row.is_na]
    broken = [row for row in record.rows if not row.is_bound]

    out.append(f"== {provenance.RECORD}")
    out.append(f"   {len(record.absences)} absence rows, {len(record.removals)} "
               f"ISA-visible removal rows")
    out.append(f"   {len(bound)} absences taken by a parameter, {len(unbound)} "
               "standing on a stated ground")
    out.append("")
    out.extend(f"   {row.subject:<10} {_settings(row) or 'n/a'}" for row in record.rows)
    if broken:
        out.append("")
        out.extend(f"FAIL {row.subject} binds nothing and states no ground"
                   for row in broken)
    print("\n".join(out))
    return 1 if broken else 0


def _lint(binary: str, root: Path, sources: list[str], extra: list[str]) -> tuple[int, str]:
    """Run `verilator --lint-only` over `sources` and return `(returncode, output)`."""
    argv = [binary, "--lint-only", "--timescale", "1ns/1ps", *extra,
            *[str(root / s) for s in sources]]
    done = subprocess.run(argv, capture_output=True, encoding="utf-8", errors="replace",
                          check=False, cwd=root)
    return done.returncode, done.stdout + done.stderr


def cmd_lint(args: argparse.Namespace) -> int:
    """Lint standalone authored and generated SystemVerilog sources under `rtl/`."""
    del args
    out: list[str] = []
    binary = _require_verilator(out)
    if binary is None:
        print("\n".join(out))
        return 1
    root = find_root()
    code, text = _lint(binary, root, list(SOURCES),
                       ["-Wall", "-Wno-UNUSEDPARAM", "-Wno-UNUSEDSIGNAL", "-Wno-MULTITOP"])
    if code != 0:
        print(text)
        print(f"FAIL {len(SOURCES)} source(s) under rtl/ did not lint clean")
        return 1
    unlinted = sorted(f"rtl/{path.name}" for path in (root / "rtl").glob("*.sv")
                      if f"rtl/{path.name}" not in SOURCES)
    aside = (f"; not among them: {', '.join(unlinted)}, compiled against the imported "
             f"packages and unable to lint alone") if unlinted else ""
    print(f"ok verilator {VERILATOR_PIN}: all {len(SOURCES)} source(s) under rtl/ that "
          f"lint standalone are clean, {len(AUTHORED)} authored and {len(GENERATED)} "
          f"generated, with no warning a package can answer{aside}")
    return 0


def _equiv_dir(e: env.Environment) -> Path:
    """Return the lane-private working directory for `cheri-equiv` builds and vectors."""
    work = e.lane_root / "cheri-equiv"
    work.mkdir(parents=True, exist_ok=True)
    return work


def cmd_vectors(args: argparse.Namespace) -> int:
    """Compile the Sail capability-format sources and emit test vectors to `vectors.txt`."""
    del args
    e = env.load()
    root = find_root()
    work = _equiv_dir(e)
    out: list[str] = []

    generator = work / "gen_vectors.sail"
    try:
        generator.write_text(rtl_vectors.harness(root), encoding="utf-8", newline="\n")
    except (OSError, ValueError) as error:
        print(f"FAIL capability vector generation: {error}")
        return 1
    sources = [root / s for s in MODEL_SOURCES] + [generator]
    binary = sailrig.build(sources, work, out)
    if binary is None:
        print("\n".join(out))
        return 1

    vectors = work / VECTORS
    if not sailrig.emit(binary, vectors, out):
        print("\n".join(out))
        return 1

    kinds, total, other = sailrig.census(vectors)
    out.append(f"== {vectors}")
    out.append(f"   {total} vector(s) over {len(kinds)} kind(s), and {other} "
               "commentary line(s)")
    out.extend(f"     {kind:<4} {count}" for kind, count in sorted(kinds.items()))
    out.append(f"ok the model emitted {total} vectors from {len(MODEL_SOURCES)} of "
               "its own sources")
    print("\n".join(out))
    return 0


def _compare(want: Path, got: Path) -> tuple[list[str], int, int, int]:
    """Compare `want` (model) and `got` (RTL) vector files via [sailrig.compare](../sailrig.py#compare)."""
    shown, bad, n_want, n_got = sailrig.compare(want, got, shown=SHOWN)
    named = [line.replace(" a: ", " model: ").replace(" b: ", " rtl:   ")
             for line in shown]
    return named, bad, n_want, n_got


def _unhandled(said: str) -> int:
    """Parse the count of unhandled vector kinds from harness output (`-1` if missing)."""
    found = UNHANDLED_RE.search(said)
    return int(found.group(1)) if found else -1


def cmd_device_regs(_args: argparse.Namespace) -> int:
    """Emit register constants from the populated selected owners."""
    print(device_regs.emit(find_root()), end="")
    return 0


def cmd_devicescheck(_args: argparse.Namespace) -> int:
    """Check owner byte identity, then execute the standalone device harness."""
    root = find_root()
    try:
        if (root / device_regs.ARTIFACT).read_text(encoding="utf-8") != device_regs.emit(root):
            print(f"FAIL {device_regs.ARTIFACT}: differs from its owners; regenerate with rtl device-regs")
            return 1
    except (OSError, ValueError) as error:
        print(f"FAIL device register generation: {error}")
        return 1
    work = _equiv_dir(env.load()) / "devices"
    work.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    binary = _require_verilator(out)
    if binary is None:
        print("\n".join(out))
        return 1
    sources = (*SOURCES, "tools/cheri-equiv/vos_devices_tb.sv")
    argv = [binary, "--binary", "--timescale", "1ns/1ps", "-Wall",
            "-Wno-UNUSEDPARAM", "-Wno-UNUSEDSIGNAL", "--Mdir", str(work / "obj_dir"),
            "-o", "devicescheck", "--top-module", "vos_devices_tb",
            *(str(root / source) for source in sources)]
    built = subprocess.run(argv, capture_output=True, text=True, check=False, cwd=work)
    (work / "build.log").write_text(built.stdout + built.stderr, encoding="utf-8")
    if built.returncode:
        print(built.stdout + built.stderr)
        return 1
    checked = subprocess.run([str(work / "obj_dir/devicescheck")], capture_output=True,
                             text=True, check=False, cwd=work)
    (work / "check.log").write_text(checked.stdout + checked.stderr, encoding="utf-8")
    print(checked.stdout + checked.stderr)
    return checked.returncode


def cmd_widthcheck(_args: argparse.Namespace) -> int:
    """Execute the frozen transport-width and exhaustive store-lane bit checks."""
    root = find_root()
    work = _equiv_dir(env.load()) / "scalar-width"
    work.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    binary = _require_verilator(out)
    if binary is None:
        print("\n".join(out))
        return 1
    sources = (FORMAT_PACKAGE, WIDTH_PACKAGE, ADAPTER_PACKAGE,
               "tools/cheri-equiv/vos_scalar_width_tb.sv")
    argv = [binary, "--binary", "--timescale", "1ns/1ps", "-Wall",
            "-Wno-UNUSEDPARAM", "-Wno-UNUSEDSIGNAL", "--Mdir", str(work / "obj_dir"),
            "-o", "widthcheck", "--top-module", "vos_scalar_width_tb",
            *(str(root / source) for source in sources)]
    built = subprocess.run(argv, capture_output=True, text=True, check=False, cwd=work)
    (work / "build.log").write_text(built.stdout + built.stderr, encoding="utf-8")
    if built.returncode:
        print(built.stdout + built.stderr)
        return 1
    checked = subprocess.run([str(work / "obj_dir/widthcheck")], capture_output=True,
                             text=True, check=False, cwd=work)
    (work / "check.log").write_text(checked.stdout + checked.stderr, encoding="utf-8")
    print(checked.stdout + checked.stderr)
    return checked.returncode


def cmd_crosscheck(args: argparse.Namespace) -> int:
    """Replay capability-format vectors through `rtl/vos_cheri_pkg.sv` and compare line by line."""
    e = env.load()
    root = find_root()
    work = _equiv_dir(e)
    out: list[str] = []

    binary = _require_verilator(out)
    if binary is None:
        print("\n".join(out))
        return 1

    vectors = work / VECTORS
    if args.reuse:
        if not vectors.is_file():
            print(f"FAIL --reuse was given and there is no {vectors} to reuse")
            return 1
    else:
        code = cmd_vectors(args)
        if code != 0:
            return code

    sources = [root / s for s in (FORMAT_PACKAGE, HARNESS)]
    missing = [str(s) for s in sources if not s.is_file()]
    if missing:
        print("\n".join(f"FAIL {s} is not in the repository" for s in missing))
        return 1

    argv = [binary, "--binary", "--timescale", "1ns/1ps", "-Wall",
            "-Wno-UNUSEDPARAM", "-Wno-UNUSEDSIGNAL", "-O2",
            "--Mdir", str(work / "obj_dir"), "-o", "replay",
            "--top-module", HARNESS_TOP, *[str(s) for s in sources]]
    done = subprocess.run(argv, capture_output=True, encoding="utf-8",
                          errors="replace", check=False, cwd=work)
    if done.returncode != 0:
        print(done.stdout + done.stderr)
        print("FAIL the harness did not build")
        return 1

    replay = work / REPLAY
    replay.unlink(missing_ok=True)
    done = subprocess.run([str(work / "obj_dir" / "replay")], capture_output=True,
                          encoding="utf-8", errors="replace", check=False, cwd=work)
    if done.returncode != 0 or not replay.is_file():
        print(done.stdout + done.stderr)
        print("FAIL the harness did not replay the vectors")
        return 1
    said = [line for line in (done.stdout + done.stderr).splitlines()
            if line.startswith(("replayed", "FAIL"))]

    unhandled = _unhandled(done.stdout + done.stderr)

    shown, bad, n_want, n_got = _compare(vectors, replay)
    kinds, total, _ = sailrig.census(vectors)

    out.append(f"== crosscheck under verilator {VERILATOR_PIN}, lane "
               f"{e.lane or 'primary'}")
    out.extend(f"   {line}" for line in said)
    out.append(f"   {total} vector(s) over {len(kinds)} kind(s): "
               + ", ".join(f"{kind} {count}" for kind, count in sorted(kinds.items())))
    if shown:
        out.append("")
        out.extend(f"   {line}" for line in shown)
    out.append("")
    if unhandled != 0:
        out.append(f"FAIL {unhandled if unhandled > 0 else 'an unreadable number of'} "
                   "vector(s) name a kind the harness does not carry, so the model "
                   "computed an answer nothing was held to")
    if bad or n_want != n_got:
        out.append(f"FAIL {bad} of {total} vector(s) disagree with the model")
    elif unhandled == 0:
        out.append(f"ok all {total} vector(s) reproduce the model's own answers, "
                   f"line for line over {n_want} lines")
    print("\n".join(out))
    return 1 if (bad or n_want != n_got or unhandled != 0) else 0


@dataclass(frozen=True)
class FileList:
    """Composed elaboration file list for one arm and the status of its declared `Substitution`s."""

    lines: tuple[str, ...]
    taken: tuple[Substitution, ...]
    unmatched: tuple[tuple[str, str], ...]
    missing: tuple[str, ...]
    absent: tuple[tuple[str, str], ...]

    @property
    def refusals(self) -> list[str]:
        """Diagnostic lines for any unmatched, missing, or absent substitution sources."""
        return ([f"FAIL {authored} is declared to stand at {CORE}/{imported} and the "
                 "imported manifest names no such line" for authored, imported in
                 self.unmatched]
                + [f"FAIL {authored} is declared to stand in the imported build and is "
                   "not in this checkout" for authored in self.missing]
                + [f"FAIL {authored} is declared to stand at {CORE}/{imported}, which "
                   "the imported manifest names and this checkout does not carry, so "
                   "nothing can read the module kinds it declared" for authored,
                   imported in self.absent])


def _file_list(root: Path, config: Path,
               subs: tuple[Substitution, ...] = ()) -> FileList:
    """Compose the elaboration file list from `CORE_FLIST`, `config`, and `subs`."""
    core = root / CORE
    text = (core / CORE_FLIST).read_text(encoding="utf-8")
    wanted = {f"{CORE_VAR}/{rel}": (sub, rel) for sub in subs for rel in sub.imported}
    hit: dict[Substitution, set[str]] = {}
    placed: set[str] = set()
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line or UNREACHED.search(line):
            continue
        if "${TARGET_CFG}_config_pkg.sv" in line:
            lines.append(str(config))
            continue
        found = wanted.get(line)
        if found is not None:
            sub, rel = found
            hit.setdefault(sub, set()).add(rel)
            for path in sub.placed:
                if path not in placed:
                    lines.append(str(root / path))
                    placed.add(path)
            continue
        lines.append(line.replace(CORE_VAR, str(core)))
    prim = root / PRIM
    gone = {sub: {rel for rel in hit.get(sub, set())
                  if not (root / CORE / rel).is_file()} for sub in subs}
    return FileList(
        lines=tuple([str(prim / PRIM_ASSERTIONS)]
                    + [str(prim / p) for p in PRIM_PACKAGES] + lines),
        taken=tuple(sub for sub in subs
                    if hit.get(sub, set()).issuperset(sub.imported) and not gone[sub]),
        unmatched=tuple((sub.authored, rel) for sub in subs for rel in sub.imported
                        if rel not in hit.get(sub, set())),
        missing=tuple(path for sub in subs for path in sub.placed
                      if not (root / path).is_file()),
        absent=tuple((sub.authored, rel) for sub in subs for rel in sub.imported
                     if rel in gone[sub]))


def _kind(name: str) -> str:
    """Strip Verilator's `__<param_hash>` suffix from an elaborated or declared module name."""
    return name.split("__", maxsplit=1)[0]


def _declared_modules(text: str) -> frozenset[str]:
    """Return module kinds declared in SystemVerilog `text` after stripping comments."""
    bare = LINE_COMMENT_RE.sub("", BLOCK_COMMENT_RE.sub("", text))
    return frozenset(_kind(str(name)) for name in MODULE_DECL_RE.findall(bare))


def _substitution_modules(root: Path, subs: tuple[Substitution, ...]
                          ) -> tuple[dict[str, str], dict[str, str]]:
    """Return `(introduced_by, displaced_by)` mapping module kinds to authored/imported paths."""
    introduced: dict[str, str] = {}
    displaced: dict[str, str] = {}
    for sub in subs:
        for path in sub.placed:
            authored = root / path
            if authored.is_file():
                for name in _declared_modules(authored.read_text(encoding="utf-8",
                                                                 errors="replace")):
                    introduced[name] = path
        for rel in sub.imported:
            imported = root / CORE / rel
            if imported.is_file():
                for name in _declared_modules(imported.read_text(encoding="utf-8",
                                                                 errors="replace")):
                    displaced[name] = rel
    return introduced, displaced


@dataclass(frozen=True)
class Diff:
    """Partitioned module-kind difference between curated and baseline elaborations.

    `removed` holds parameter-removed kinds tracked by
    [the provenance record](../../../rtl/synthesis-provenance.md); `displaced` and
    `introduced` hold kinds accounted for by `SUBSTITUTIONS`; `unexplained` and `inert`
    are findings.
    """

    removed: tuple[str, ...]
    displaced: tuple[str, ...]
    introduced: tuple[str, ...]
    unexplained: tuple[str, ...]
    inert: tuple[str, ...]

    @property
    def findings(self) -> int:
        return len(self.unexplained) + len(self.inert)


def _diff(curated: set[str], stock: set[str], introduced_by: dict[str, str],
          displaced_by: dict[str, str]) -> Diff:
    """Partition `curated` and `stock` module kinds using `introduced_by` and `displaced_by`."""
    gone = stock - curated
    new = curated - stock
    return Diff(
        removed=tuple(sorted(kind for kind in gone if kind not in displaced_by)),
        displaced=tuple(sorted(kind for kind in gone if kind in displaced_by)),
        introduced=tuple(sorted(kind for kind in new if kind in introduced_by)),
        unexplained=tuple(sorted(kind for kind in new if kind not in introduced_by)),
        inert=tuple(sorted(kind for kind in introduced_by if kind not in curated)))


def _baseline_config(root: Path, work: Path) -> Path:
    """Write the baseline configuration (`STOCK_CONFIG` with `BASELINE_EDITS`) into `work`."""
    text = (root / CORE / STOCK_CONFIG).read_text(encoding="utf-8")
    for old, new in BASELINE_EDITS:
        text = text.replace(old, new)
    path = work / "baseline_config_pkg.sv"
    path.write_text(text, encoding="utf-8", newline="")
    return path


def _elaborate(binary: str, root: Path, files: FileList, ast: Path,
               *, curated: bool = False) -> tuple[int, str]:
    """Elaborate `cva6` from `files` into JSON netlist `ast` inside `ast.parent`."""
    prim = root / PRIM
    listing = ast.with_suffix(".f")
    lines = files.lines
    try:
        if curated:
            lines = rtl_width.stage(root, lines, ast.parent)
    except (OSError, ValueError) as error:
        return 1, f"FAIL RTL source staging: {error}"
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    argv = [binary, "--json-only", "--timescale", "1ns/1ps", "-Wno-fatal",
            *(arg for rel in PRIM_LIBRARIES for arg in ("-y", str(prim / rel))),
            f"+incdir+{(prim / PRIM_ASSERTIONS).parent}",
            "+define+PRIM_DEFAULT_IMPL=prim_pkg::ImplGeneric",
            "--top-module", "cva6", "--json-only-output", str(ast),
            "--json-only-meta-output", str(ast.with_suffix(".meta.json")),
            "-f", str(listing)]
    done = subprocess.run(argv, capture_output=True, encoding="utf-8", errors="replace",
                          check=False, cwd=ast.parent)
    return done.returncode, done.stdout + done.stderr


def _json_nodes(value: object) -> Iterator[dict[str, object]]:
    """Walk owned AST children; cross-references are strings and are not followed."""
    if isinstance(value, dict):
        node = cast("dict[str, object]", value)
        yield node
        for child in node.values():
            yield from _json_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _json_nodes(child)


# Memory-array kinds and cache scopes cited by A-09 and A-10 in `rtl/synthesis-provenance.md`.
ARRAY_KINDS: tuple[str, ...] = ("prim_ram_1p", "sram_cache", "sram")
ARRAY_SCOPES: tuple[str, ...] = ("wt_dcache", "cva6_icache")
WHOLE_CORE = "whole core"
OUTSIDE = "outside every cache"


@dataclass(frozen=True)
class Inventory:
    """Instantiated module kinds, expanded cell count, variable count, and memory-array counts."""

    kinds: set[str]
    cells: int
    variables: int
    arrays: tuple[tuple[str, int, tuple[int, ...]], ...]


def _inventory(ast: Path) -> Inventory:
    """Extract the `Inventory` from a Verilator JSON netlist at `ast`."""
    tree = json.loads(ast.read_text(encoding="utf-8"))
    if not isinstance(tree, dict) or tree.get("type") != "NETLIST":
        raise ValueError(f"{ast}: expected a Verilator NETLIST")
    definitions = tree.get("modulesp")
    if not isinstance(definitions, list):
        raise TypeError(f"{ast}: NETLIST has no module definitions")
    modules: dict[str, dict[str, object]] = {}
    for definition in definitions:
        if not isinstance(definition, dict) or not isinstance(definition.get("type"), str):
            raise TypeError(f"{ast}: malformed module definition")
        if definition.get("type") not in {"MODULE", "IFACE"}:
            continue
        name = definition.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{ast}: module definition has no name")
        if name in modules:
            raise ValueError(f"{ast}: duplicate module definition {name!r}")
        modules[name] = definition
    roots = [name for name, node in modules.items()
             if node.get("type") == "MODULE" and node.get("level") == 1]
    if len(roots) != 1:
        raise ValueError(f"{ast}: expected one top module, found {len(roots)}")
    kinds = {_kind(name) for name, node in modules.items() if node.get("type") == "MODULE"}
    variables = sum(node.get("type") == "VAR" for node in _json_nodes(definitions))
    children: dict[str, list[str]] = {}
    for name, module in modules.items():
        children[name] = []
        for node in _json_nodes(module):
            if node.get("type") != "CELL":
                continue
            target = node.get("modName")
            if not isinstance(target, str) or target not in modules:
                raise ValueError(f"{ast}: unresolved module {target!r} in {name!r}")
            children[name].append(target)
    below: dict[str, Counter[str]] = {}

    def expand(name: str, ancestors: frozenset[str]) -> Counter[str]:
        """Each kind's instances in one template's expanded subtree, itself included."""
        if name in ancestors or name not in modules:
            raise ValueError(f"{ast}: recursive or unresolved module {name!r}")
        if name not in below:
            found = Counter({_kind(name): 1})
            for child in children[name]:
                found.update(expand(child, ancestors | {name}))
            below[name] = found
        return below[name]

    for name in modules:
        expand(name, frozenset())
    top = roots[0]

    def within(scope: str) -> Counter[str]:
        """Each kind's instances at or below an instance of `scope`, each once."""
        seen: dict[str, Counter[str]] = {}

        def walk(name: str) -> Counter[str]:
            if name not in seen:
                found: Counter[str] = Counter()
                if _kind(name) == scope:
                    found.update(below[name])
                else:
                    for child in children[name]:
                        found.update(walk(child))
                seen[name] = found
            return seen[name]

        return walk(top)

    def outside() -> Counter[str]:
        """Each kind's instances under the top at or below no instance of a cache."""
        seen: dict[str, Counter[str]] = {}

        def walk(name: str) -> Counter[str]:
            if name not in seen:
                found: Counter[str] = Counter()
                if _kind(name) not in ARRAY_SCOPES:
                    found[_kind(name)] += 1
                    for child in children[name]:
                        found.update(walk(child))
                seen[name] = found
            return seen[name]

        return walk(top)

    scopes = ((WHOLE_CORE, 1, below[top]),
              *((scope, below[top][scope], within(scope)) for scope in ARRAY_SCOPES),
              (OUTSIDE, 1, outside()))
    arrays = tuple((scope, reached, tuple(found[kind] for kind in ARRAY_KINDS))
                   for scope, reached, found in scopes)
    return Inventory(kinds, sum(below[top].values()), variables, arrays)


def _array_lines(inventories: dict[str, Inventory]) -> list[str]:
    """Format expanded memory-array instance counts per arm and cache scope."""
    column = 13
    absent = f"{'absent: the top reaches none':>{column * len(ARRAY_KINDS)}}"
    rows: list[tuple[str, str, str]] = []
    for arm in sorted(inventories):
        for scope, reached, found in inventories[arm].arrays:
            if scope in {WHOLE_CORE, OUTSIDE}:
                label = scope
            else:
                label = f"under {scope} ({reached})" if reached else f"under {scope}"
            counts = "".join(f"{n:>{column}}" for n in found) if reached else absent
            rows.append((arm, label, counts))
    width = max([len("scope"), *(len(label) for _, label, _ in rows)])
    lines = ["   memory-array instances, expanded, per arm and scope; a cache's label carries",
             "   in parentheses how many instances of it the top reaches:",
             f"     {'arm':<9} {'scope':<{width}}"
             + "".join(f"{kind:>{column}}" for kind in ARRAY_KINDS)]
    lines.extend(f"     {arm:<9} {label:<{width}}{counts}" for arm, label, counts in rows)
    return lines


def prim_inputs() -> tuple[str, ...]:
    """Every primitive path an elaboration reads, relative to the checkout root."""
    return tuple(f"{PRIM}/{rel}" for rel in (PRIM_ASSERTIONS, *PRIM_PACKAGES,
                                             *PRIM_LIBRARIES))


def _absent_inputs(root: Path) -> tuple[list[str], list[str]]:
    """Return missing imported manifest or primitive paths under `root` and hints to populate them."""
    manifest = f"{CORE}/{CORE_FLIST}"
    absent = [rel for rel in (manifest, *prim_inputs()) if not (root / rel).exists()]
    init = [CORE] if manifest in absent else []
    hints: list[str] = []
    if any(rel.startswith(f"{PRIM}/") for rel in absent):
        if (root / PRIM_UPSTREAM / ".git").exists():
            cones = sorted({rel.split("/", 1)[0] for rel in (
                PRIM_ASSERTIONS, *PRIM_PACKAGES, *PRIM_LIBRARIES)})
            within = PRIM.removeprefix(f"{PRIM_UPSTREAM}/")
            hints.append(f"     {PRIM_UPSTREAM} is populated without these primitives, as a "
                         "cone-sparse checkout for devicescheck is: `git -C "
                         f"{PRIM_UPSTREAM} sparse-checkout add "
                         f"{' '.join(f'{within}/{cone}' for cone in cones)}`, or check "
                         "it out in full")
        else:
            init.append(PRIM_UPSTREAM)
    if init:
        hints.insert(0, "     the imported cores are gitlinks and this elaboration reads "
                        f"them: `git submodule update --init {' '.join(init)}`")
    return absent, hints


def cmd_filelist(args: argparse.Namespace) -> int:
    """Compose the curated arm's file list and report the status of each `Substitution`."""
    root = find_root()
    out: list[str] = []
    manifest = f"{CORE}/{CORE_FLIST}"
    if not (root / manifest).exists():
        out.append(f"FAIL {manifest} is not in this checkout")
        out.append("     the imported core is a gitlink and this reads its manifest: "
                   "`git submodule update --init upstream/cva6-cheri`")
        print("\n".join(out))
        return 1
    config = root / provenance.CONFIG
    if not config.is_file():
        out.append(f"FAIL the curated configuration is not at {config}")
        print("\n".join(out))
        return 1

    files = _file_list(root, config, SUBSTITUTIONS)
    introduced_by, displaced_by = _substitution_modules(root, files.taken)
    out.append(f"== the curated arm's file list, {len(files.lines)} entries")
    out.append(f"   {len(SUBSTITUTIONS)} declared substitution(s), {len(files.taken)} "
               "of them standing in the imported manifest's place")
    out.extend(f"   {'ok  ' if sub in files.taken else 'FAIL'} {sub.authored} "
               f"<- {', '.join(sub.imported)}" for sub in SUBSTITUTIONS)
    if files.taken:
        out.append(f"   {len(introduced_by)} module kind(s) the authored sources "
                   f"declare, against {len(displaced_by)} the imported ones did")
    absent, hints = _absent_inputs(root)
    absent = [rel for rel in absent if rel.startswith(f"{PRIM}/")]
    if absent:
        out.append(f"   {len(absent)} primitive input(s) an elaboration reads are not in "
                   "this checkout, so it would refuse them by name:")
        out.extend(f"     {rel}" for rel in absent)
        out.extend(hints)
    if args.show:
        out.append("")
        out.extend(f"   {line}" for line in files.lines)
    out.extend(files.refusals)
    print("\n".join(out))
    return 1 if files.refusals else 0


def cmd_elaborate(args: argparse.Namespace) -> int:
    """Elaborate curated and baseline CVA6 configurations and report structural differences."""
    e = env.load()
    log = e.log("rtl-elaborate")
    if args.background:
        return _detach(log)

    out: list[str] = []
    binary = _require_verilator(out)
    if binary is None:
        print("\n".join(out))
        return 1

    root = find_root()
    absent, hints = _absent_inputs(root)
    if absent:
        out.extend(f"FAIL {rel} is not in this checkout" for rel in absent)
        out.extend(hints)
        print("\n".join(out))
        return 1

    work = e.lane_root / "rtl-elaborate"
    work.mkdir(parents=True, exist_ok=True)

    curated_config = root / provenance.CONFIG
    if not curated_config.is_file():
        out.append(f"FAIL the curated configuration is not at {curated_config}")
        print("\n".join(out))
        return 1

    arms = {"curated": _file_list(root, curated_config, SUBSTITUTIONS),
            "baseline": _file_list(root, _baseline_config(root, work))}
    refusals = arms["curated"].refusals
    if refusals:
        out.extend(refusals)
        out.append("     a declaration that reaches no line leaves the imported source "
                   "in the build and the authored one out of it, which elaborates")
        print("\n".join(out))
        return 1

    inventories: dict[str, Inventory] = {}
    for name, files in arms.items():
        ast = work / f"{name}.json"
        code, text = _elaborate(binary, root, files, ast, curated=name == "curated")
        if code != 0:
            print(text)
            out.append(f"FAIL the {name} configuration did not elaborate")
            print("\n".join(out))
            return 1
        try:
            inventories[name] = _inventory(ast)
        except (OSError, TypeError, ValueError) as error:
            print(f"FAIL the {name} elaboration inventory could not be read: {error}")
            return 1

    curated, stock = inventories["curated"], inventories["baseline"]
    introduced_by, displaced_by = _substitution_modules(root, arms["curated"].taken)
    diff = _diff(curated.kinds, stock.kinds, introduced_by, displaced_by)

    out.append(f"== elaborated under verilator {VERILATOR_PIN}, lane "
               f"{e.lane or 'primary'}")
    out.append("   the baseline is the imported tree's stock CHERI configuration with "
               "the floating-point")
    out.append("   extension off, so A-15 is evidenced by its parameter and not by "
               "this difference")
    if arms["curated"].taken:
        out.append(f"   the curated arm stands {len(arms['curated'].taken)} authored "
                   "source(s) in the imported manifest's place and the baseline "
                   "stands none")
    out.append(f"   baseline: {len(stock.kinds)} module kinds, {stock.cells} cells, "
               f"{stock.variables} declared variables")
    out.append(f"   curated: {len(curated.kinds)} module kinds, {curated.cells} cells, "
               f"{curated.variables} declared variables")
    out.append("")
    out.extend(_array_lines(inventories))
    out.append("")
    out.append(f"   {len(diff.removed)} structure(s) the disabling parameters remove:")
    out.extend(f"     {kind}" for kind in diff.removed)
    if diff.displaced:
        out.append("")
        out.append(f"   {len(diff.displaced)} structure(s) an authored source replaces "
                   "rather than a parameter removes:")
        out.extend(f"     {kind:<28} {displaced_by[kind]}" for kind in diff.displaced)
    if diff.introduced:
        out.append("")
        out.append(f"   {len(diff.introduced)} structure(s) an authored source "
                   "introduces:")
        out.extend(f"     {kind:<28} {introduced_by[kind]}" for kind in diff.introduced)
    if diff.unexplained:
        out.append("")
        out.append(f"FAIL {len(diff.unexplained)} structure(s) the curated configuration "
                   "instantiates that no authored source in its file list declares:")
        out.extend(f"     {kind}" for kind in diff.unexplained)
    if diff.inert:
        out.append("")
        out.append(f"FAIL {len(diff.inert)} authored module(s) reached the file list and "
                   "not the netlist:")
        out.extend(f"     {kind:<28} {introduced_by[kind]}" for kind in diff.inert)
    print("\n".join(out))
    return 1 if diff.findings else 0


def _detach(log: Path) -> int:
    """Launch `run.py rtl elaborate` in a detached session writing output to `log`."""
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as handle:
        child = subprocess.Popen(cli.entry("rtl", "elaborate"), stdout=handle,
                                 stderr=subprocess.STDOUT, start_new_session=True)
    print(f"== log: {log} (pid {child.pid}); wait on it with `run.py rtl wait`")
    return 0


def cmd_wait(args: argparse.Namespace) -> int:
    """Check whether a backgrounded `rtl elaborate` run has written `MARKER` to its log."""
    e = env.load()
    log = e.log("rtl-elaborate")
    if not log.is_file():
        print(f"FAIL no elaboration log at {log}")
        return 1
    text = log.read_text(encoding="utf-8", errors="replace")
    if not text.rstrip().endswith(MARKER):
        if args.block:
            print(f"== {log} is still being written; re-run when it ends in {MARKER}")
        else:
            print(f"== {log} carries no {MARKER}, so its run is unfinished or died")
        return 1
    print(text)
    return 0 if "FAIL" not in text else 1


COMMANDS: cli.Table = {
    "install": (cmd_install, "build the verified Verilator release in a project prefix"),
    "provenance": (cmd_provenance, "parse and print the synthesis-provenance record"),
    "filelist": (cmd_filelist,
                 "the curated arm's file list, and every substitution's verdict"),
    "lint": (cmd_lint, "Verilator over this repository's own sources in rtl/"),
    "widthcheck": (cmd_widthcheck, "frozen transport widths and every store rotation bit/lane"),
    "device-regs": (cmd_device_regs, "emit wrapper register constants from their owners"),
    "devicescheck": (cmd_devicescheck, "check register constants and execute standalone devices"),
    "vectors": (cmd_vectors,
                "the model's own answers about the capability format, as text"),
    "crosscheck": (cmd_crosscheck,
                   "and the authored package required to reproduce every line"),
    "elaborate": (cmd_elaborate,
                  "elaborate the imported core at both configurations and diff them"),
    "wait": (cmd_wait, "the verdict of a backgrounded elaboration"),
}


def _flags(name: str, sub: argparse.ArgumentParser) -> None:
    if name == "install":
        sub.add_argument("--jobs", type=cli.positive_int, metavar="N",
                         help="worker override (default: available CPUs limited by memory)")
    if name == "filelist":
        sub.add_argument("--show", action="store_true",
                         help="print the composed list itself, entry by entry")
    if name == "elaborate":
        sub.add_argument("--background", action="store_true",
                         help="detach, writing the whole run to this lane's log")
    if name == "crosscheck":
        sub.add_argument("--reuse", action="store_true",
                         help="replay the vectors this lane already emitted "
                              "instead of emitting them again")
    if name == "wait":
        sub.add_argument("--block", action="store_true",
                         help="say so rather than failing where the run is live")


def main(argv: list[str] | None = None) -> int:
    """Dispatch `run.py rtl` subcommands and append `MARKER` after foreground `elaborate`."""
    args = list(argv or [])
    code = cli.dispatch(__doc__, COMMANDS, args, _flags, prog="run.py rtl")
    if args[:1] == ["elaborate"] and "--background" not in args:
        print(MARKER, flush=True)
    return code
