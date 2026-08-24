#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The RTL lane: the authored sources, and the elaboration the absence contract wants.

Three loops, and the first two answer on the host:

    provenance  instant  the synthesis-configuration record, parsed and printed
    lint        ~1 s     Verilator over the authored sources in rtl/, alone
    elaborate   ~2 min   the imported core at the curated configuration and at the
                         stock CHERI one, and the difference between the two

`elaborate` is the one that matters and it is the imported-core half of the absence
contract's day-one procedure: elaborate the core at its intended synthesis
configuration, enumerate what the elaborator instantiated, and hold that against the
stock configuration so that every structure the disabling parameters remove is named
rather than asserted. What it prints is what the elaborator reports; what removes each
structure is [rtl/synthesis-provenance.md](../rtl/synthesis-provenance.md)'s to say, and
rule K-76 holds the record against the configuration package so the two cannot drift.

**Nothing here is copied out of an imported tree.** `rtl/` holds files this repository
authored and the imported sources are reached through the gitlinks under `upstream/`,
so this tool composes a file list across the two rather than a vendored tree.

The last two run inside WSL, where Verilator lives:

    python tools/rtl.py provenance
    wsl -u root -e python3 tools/rtl.py lint
    wsl -u root -e python3 tools/rtl.py elaborate --background
    wsl -u root -e python3 tools/rtl.py wait

`elaborate` writes its whole run to a log and prints only where the log is, and the last
line it writes is `ALL_DONE`, so a caller waits on a marker instead of guessing at a
sleep. Its lane is the one `vos/env.py` derives from the checkout, so two worktrees
elaborating at once write two logs and share no working directory.
"""

import argparse
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

# The tools import `vos` without being installed, so each puts its own directory on
# the path first. Every import below this line is deliberately not at the top.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vos import env, provenance
from vos.corpus import find_root

# What every subcommand handler is. `main` attaches one to each subparser and argparse
# hands it back as an untyped attribute, so the shape is stated once here.
type Command = Callable[[argparse.Namespace], int]

# The pinned simulator, and the ground the pin stands on. Ubuntu 26.04 packages this
# version, which is what keeps a lane reproducible without a source build: a simulator
# built from source is a second toolchain to keep, and the guest already carries one
# interpreter floor for exactly this reason. The bring-up SoC this lane's imported
# sources come from pins 5.040 through nix; that difference is recorded rather than
# chased, because nothing here runs the reference's own flow and an elaborator's
# version is evidence about which tool reported, not about what it reported.
VERILATOR_PIN = "5.032"
VERILATOR_HOW = "apt-get install verilator on Ubuntu 26.04"

# The authored sources, in the order a compiler must see them: the format package
# declares the types the rest use.
AUTHORED: tuple[str, ...] = (
    "rtl/vos_cheri_pkg.sv",
)

# The imported core, reached through its gitlink and never copied.
CORE = "upstream/cva6-cheri"
CORE_FLIST = "core/Flist.cva6"
PRIM = "upstream/opentitan/hw/ip"

# Three OpenTitan primitives the imported core instantiates that its own manifest does
# not list, because the bring-up SoC supplies them from a vendored tree. Named here
# rather than globbed, so that a primitive arriving under a new name is a failed
# elaboration with a message rather than a silent change of what was elaborated.
PRIM_PACKAGES: tuple[str, ...] = (
    "prim_generic/rtl/prim_ram_1p_pkg.sv",
    "prim/rtl/prim_cipher_pkg.sv",
    "prim/rtl/prim_util_pkg.sv",
)

# The imported manifest names two trees this configuration does not reach: the
# floating-point unit, which A-15 deletes, and the high-performance data cache, which
# this configuration does not select. Both are submodules of the imported core that
# nothing here initializes, so their lines are dropped from the file list rather than
# fetched. A line dropped here is a file no configuration below instantiates.
UNREACHED = re.compile(r"cvfpu|opene906|openc910|fpu_wrap|HPDCACHE_DIR|hpdcache")

# The stock CHERI configuration, elaborated as the baseline the curated one is a
# difference from. It is the imported tree's own, reached through the gitlink.
STOCK_CONFIG = "core/include/cv64a6_imafdczcheri_sv39_config_pkg.sv"

# The one edit made to that baseline before it is elaborated, and the reason it is made
# rather than avoided. The stock configuration turns the floating-point extension on,
# which instantiates a unit living in a submodule of the imported core that nothing here
# initializes: the FPU is what A-15 deletes, so pinning an upstream in order to elaborate
# what this profile removes would be a commitment taken to produce a baseline. The
# consequence is stated wherever the difference is: **A-15 is evidenced by the parameter
# and by the unit not being instantiated, and never by this diff**, because the baseline
# does not instantiate it either. Every other row of the difference is a real one.
BASELINE_EDITS: tuple[tuple[str, str], ...] = (
    ("CVA6ConfigRVF = 1", "CVA6ConfigRVF = 0"),
    ("CVA6ConfigRVD = 1", "CVA6ConfigRVD = 0"),
)

# A `<module ... name="foo__Cz1_Tz37">` in Verilator's XML: the parameter hash after the
# double underscore distinguishes two elaborations of one module, which is noise for a
# question about which modules exist at all.
MODULE_RE = re.compile(r'<module [^>]*name="([^"]*)"')
CELL_RE = re.compile(r"<cell ")
VAR_RE = re.compile(r"<var ")

MARKER = "ALL_DONE"


def _verilator() -> str | None:
    """The simulator's own path, or None where it is not installed."""
    return shutil.which("verilator")


def _verilator_version(binary: str) -> str:
    """What the installed simulator calls itself, as its bare version."""
    done = subprocess.run([binary, "--version"], capture_output=True, encoding="utf-8",
                          errors="replace", check=False)
    found = re.search(r"Verilator\s+(\d+\.\d+)", done.stdout)
    return str(found.group(1)) if found else done.stdout.strip()


def _require_verilator(out: list[str]) -> str | None:
    """The simulator at its pinned version, or None with the refusal already printed.

    A version other than the pinned one is a finding rather than a warning, which is
    the disposition the two type checkers and the prover already take: an elaboration
    is evidence, and evidence carries which tool produced it.
    """
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


def _settings(row: provenance.Row) -> str:
    """One row's settings, as a reader of the record would write them."""
    return ", ".join(f"{name} = {value}" for name, value in row.settings)


def cmd_provenance(args: argparse.Namespace) -> int:
    """The record, parsed and printed: what binds each absence, and what does not.

    The record is prose a person reads and a table two tools parse, and this prints the
    parse rather than the prose so that what the checker sees is what a reader can see.
    """
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
    """Verilator over one file set, with its output handed back rather than streamed."""
    argv = [binary, "--lint-only", "--timescale", "1ns/1ps", *extra,
            *[str(root / s) for s in sources]]
    done = subprocess.run(argv, capture_output=True, encoding="utf-8", errors="replace",
                          check=False, cwd=root)
    return done.returncode, done.stdout + done.stderr


def cmd_lint(args: argparse.Namespace) -> int:
    """The authored sources alone, under every warning a package can answer.

    Two warnings are switched off and both are properties of linting a *package* rather
    than of the code in it: a package instantiates nothing, so every parameter it
    declares for a consumer reads as unused, and every field of a struct a function does
    not touch reads as an unused bit. Switching them off here rather than in the source
    keeps the file free of suppressions that would go stale the day something
    instantiates it.
    """
    del args
    out: list[str] = []
    binary = _require_verilator(out)
    if binary is None:
        print("\n".join(out))
        return 1
    root = find_root()
    code, text = _lint(binary, root, list(AUTHORED),
                       ["-Wall", "-Wno-UNUSEDPARAM", "-Wno-UNUSEDSIGNAL"])
    if code != 0:
        print(text)
        print(f"FAIL {len(AUTHORED)} authored source(s) did not lint clean")
        return 1
    print(f"ok verilator {VERILATOR_PIN}: all {len(AUTHORED)} authored source(s) lint "
          "clean, with no warning a package can answer")
    return 0


def _file_list(root: Path, config: Path) -> list[str]:
    """The imported core's own manifest, with one configuration substituted into it.

    The manifest is read rather than transcribed, so a source the imported tree adds
    arrives here without an edit. Three substitutions are made and each is named: the
    repository variable it is written against, the configuration package it leaves to
    the caller, and the two trees this configuration does not reach.
    """
    core = root / CORE
    text = (core / CORE_FLIST).read_text(encoding="utf-8")
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line or UNREACHED.search(line):
            continue
        if "${TARGET_CFG}_config_pkg.sv" in line:
            lines.append(str(config))
            continue
        lines.append(line.replace("${CVA6_REPO_DIR}", str(core)))
    prim = root / PRIM
    return [str(prim / p) for p in PRIM_PACKAGES] + lines


def _baseline_config(root: Path, work: Path) -> Path:
    """The baseline configuration, derived from the imported tree's stock one.

    Written into the lane's own working directory and never into `rtl/`, because it is
    not a file this repository authored: it is the imported tree's, with the one edit
    `BASELINE_EDITS` names, made so that the baseline elaborates without initializing a
    submodule for a unit this profile deletes. A derived file with no home in the tree
    is the right shape for it, the tree holding only what we wrote.
    """
    text = (root / CORE / STOCK_CONFIG).read_text(encoding="utf-8")
    for old, new in BASELINE_EDITS:
        text = text.replace(old, new)
    path = work / "baseline_config_pkg.sv"
    path.write_text(text, encoding="utf-8", newline="")
    return path


def _elaborate(binary: str, root: Path, config: Path, xml: Path) -> tuple[int, str]:
    """One elaboration of the imported core, its AST written where the caller says.

    Run from the lane's own working directory rather than from the checkout, for two
    reasons that point the same way. Nothing an elaborator writes belongs in a tree the
    checker reads out of the git index. And the imported core's manifest carries relative
    include directories that resolve against the working directory, so elaborating from
    the checkout root silently searches the wrong tree for them: the failure it produces
    is a missing package, several files away from the cause.
    """
    prim = root / PRIM
    listing = xml.with_suffix(".f")
    listing.write_text("\n".join(_file_list(root, config)) + "\n", encoding="utf-8")
    argv = [binary, "--xml-only", "--timescale", "1ns/1ps", "-Wno-fatal",
            "-y", str(prim / "prim/rtl"), "-y", str(prim / "prim_generic/rtl"),
            f"+incdir+{prim / 'prim/rtl'}",
            "+define+PRIM_DEFAULT_IMPL=prim_pkg::ImplGeneric",
            "--top-module", "cva6", "--xml-output", str(xml), "-f", str(listing)]
    done = subprocess.run(argv, capture_output=True, encoding="utf-8", errors="replace",
                          check=False, cwd=xml.parent)
    return done.returncode, done.stdout + done.stderr


def _inventory(xml: Path) -> tuple[set[str], int, int]:
    """What one elaboration instantiated: its module kinds, its cells, and its
    declared variables.

    The module *kind* is the name with its parameter hash removed, because two
    elaborations of one module at different parameters are one structure and the
    question this answers is which structures exist.
    """
    text = xml.read_text(encoding="utf-8", errors="replace")
    kinds: set[str] = {str(name).split("__")[0] for name in MODULE_RE.findall(text)}
    return kinds, len(CELL_RE.findall(text)), len(VAR_RE.findall(text))


def cmd_elaborate(args: argparse.Namespace) -> int:
    """The curated configuration against the stock one, and the difference named.

    The absence contract's own procedure is elaborate, enumerate, search, record. This
    is the first two and the shape of the third: what it reports is which structures the
    curated configuration does not instantiate that the stock one does, which is the
    state-enumeration half. What it deliberately does not do is decide that the result
    is *right*: an absence is claimed by the contract and bound by the record, and this
    says what the elaborator built.

    Every row of the difference is a deletion. A module the curated configuration
    instantiates and the stock one does not would be a finding, because every row of the
    profile and the contract is less hardware than the stock core and never more.
    """
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
    work = e.lane_root / "rtl-elaborate"
    work.mkdir(parents=True, exist_ok=True)

    configs = {"curated": root / provenance.CONFIG,
               "baseline": _baseline_config(root, work)}
    inventories: dict[str, tuple[set[str], int, int]] = {}
    for name, config in configs.items():
        if not config.is_file():
            out.append(f"FAIL the {name} configuration is not at {config}")
            print("\n".join(out))
            return 1
        code, text = _elaborate(binary, root, config, work / f"{name}.xml")
        if code != 0:
            print(text)
            out.append(f"FAIL the {name} configuration did not elaborate")
            print("\n".join(out))
            return 1
        inventories[name] = _inventory(work / f"{name}.xml")

    curated_kinds, curated_cells, curated_vars = inventories["curated"]
    stock_kinds, stock_cells, stock_vars = inventories["baseline"]
    removed = sorted(stock_kinds - curated_kinds)
    added = sorted(curated_kinds - stock_kinds)

    out.append(f"== elaborated under verilator {VERILATOR_PIN}, lane "
               f"{e.lane or 'primary'}")
    out.append("   the baseline is the imported tree's stock CHERI configuration with "
               "the floating-point")
    out.append("   extension off, so A-15 is evidenced by its parameter and not by "
               "this difference")
    out.append(f"   baseline: {len(stock_kinds)} module kinds, {stock_cells} cells, "
               f"{stock_vars} declared variables")
    out.append(f"   curated: {len(curated_kinds)} module kinds, {curated_cells} cells, "
               f"{curated_vars} declared variables")
    out.append("")
    out.append(f"   {len(removed)} structure(s) the disabling parameters remove:")
    out.extend(f"     {kind}" for kind in removed)
    if added:
        out.append("")
        out.append(f"FAIL {len(added)} structure(s) the curated configuration "
                   "instantiates and the stock one does not:")
        out.extend(f"     {kind}" for kind in added)
    print("\n".join(out))
    return 1 if added else 0


def _detach(log: Path) -> int:
    """Start this run again in the background, writing its whole output to a log.

    The child is started in a session of its own. Without that it dies with the shell
    that launched it, which on this lane is a `wsl -e` invocation that returns as soon
    as the parent does: the log is created, nothing is ever written into it, and the
    marker never lands, which reads exactly like a run that is still going.

    The previous log is removed only once the child exists, so a failed start leaves the
    last run's verdict readable rather than deleting it in favour of nothing.
    """
    log.parent.mkdir(parents=True, exist_ok=True)
    argv = [sys.executable, str(Path(__file__).resolve()), "elaborate"]
    with log.open("w", encoding="utf-8") as handle:
        child = subprocess.Popen(argv, stdout=handle, stderr=subprocess.STDOUT,
                                 start_new_session=True)
    print(f"== log: {log} (pid {child.pid}); wait on it with `rtl.py wait`")
    return 0


def cmd_wait(args: argparse.Namespace) -> int:
    """The verdict of a backgrounded elaboration, once its marker has landed.

    The wait is on the marker rather than on a sleep, and on the marker rather than on
    the process, because a caller that started the run in another shell has no pid to
    wait on and the log is the thing both of them can read.
    """
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


COMMANDS: dict[str, tuple[Command, str]] = {
    "provenance": (cmd_provenance, "parse and print the synthesis-provenance record"),
    "lint": (cmd_lint, "Verilator over the authored sources in rtl/"),
    "elaborate": (cmd_elaborate,
                  "elaborate the imported core at both configurations and diff them"),
    "wait": (cmd_wait, "the verdict of a backgrounded elaboration"),
}


def main() -> int:
    """Dispatch, and write the marker every backgrounded run is waited on by."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subs = parser.add_subparsers(dest="command", required=True)
    for name, (_, help_text) in COMMANDS.items():
        sub = subs.add_parser(name, help=help_text)
        if name == "elaborate":
            sub.add_argument("--background", action="store_true",
                             help="detach, writing the whole run to this lane's log")
        if name == "wait":
            sub.add_argument("--block", action="store_true",
                             help="say so rather than failing where the run is live")
    args = parser.parse_args()
    handler, _ = COMMANDS[args.command]
    code = handler(args)
    if args.command == "elaborate" and not getattr(args, "background", False):
        print(MARKER, flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
