#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regenerate the descriptor check's C from its Gallina source, and hold its digest.

The loop Q2a stood up, run by hand rather than through `run.py`: the Gallina source
beside this file is compiled in its dedicated Rupicola switch, where `Derive` closes the
functional relation and `c_module` prints the bedrock2 function as C; the C is cut out
of the prover's `Redirect` output, never edited, and its SHA-256, size and line count
are printed beside the timings the derivation took. `--check` recomputes the digest and
compares it with the one [DIGESTS.md](DIGESTS.md) records, exiting non-zero on drift,
which is the whole of what makes the emitted C reproducible rather than merely present.
`--ccomp` adds the reaching exit: the contained purecap `ccomp` of the compiler
milestone's lane, run to `-S` and to `-S -dcapasm`, with the mnemonic census and the
stubbed-arm count that bound what this route can reach today. `--baseline` puts
Rupicola's own shipped `ip_checksum` through the same steps so that every figure has a
yardstick taken the same way.

    python tools/bedrock2-lowering/regenerate.py --stage /root/q2-stage
    python tools/bedrock2-lowering/regenerate.py --stage /root/q2-stage --check
    python tools/bedrock2-lowering/regenerate.py --stage /root/q2-stage \\
        --ccomp /root/build/secomp-m12/ccomp --baseline

Every path is absolute and the staging directory is outside every checkout: a
subagent's working directory is not the worktree, and a relative write from the guest
lands in the primary checkout. From the host the script re-launches itself in WSL, the
switch living there; nothing is written under the repository on either lane.
"""

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
SWITCH = "verifiedos-rupicola-9.2.0-ocaml-5.4.1"
SOURCE = HERE / "DescriptorCheck.v"
BASELINE = HERE / "IpChecksumBaseline.v"
OWNER = HERE.parent.parent / "proofs" / "RingContract.v"
DIGESTS = HERE / "DIGESTS.md"
FUNCTION = "descriptor_check"
BASELINE_FUNCTION = "ip_checksum"
PACKAGES = ("coq-rupicola", "coq-bedrock2", "coq-bedrock2-compiler", "coq-coqutil",
            "coq-riscv", "rocq-core", "coq")

# The shipped derivation whose re-run times the yardstick: copied out of the switch's
# own library into the stage under another name, so that its `Derive` runs here and
# the installed `.vo` is left alone.
SHIPPED = Path("Rupicola/Examples/Net/IPChecksum/IPChecksum.v")
REDERIVE = "IpcRederive.v"

FINISHED = re.compile(r"Finished transaction in (\d+(?:\.\d+)?) secs")
MNEMONIC = re.compile(r"^\s+([a-z][a-z0-9.]*)", re.MULTILINE)
CAPABILITY = re.compile(r"^\s+(c[a-z]+)\s", re.MULTILINE)
TODO_ARM = re.compile(r"TODO: __[A-Za-z0-9_]+__")
DIGEST_ROW = re.compile(r"^\| `([^`]+\.c)` \| `([0-9a-f]{64})` \| (\d+) \| (\d+) \|", re.MULTILINE)
WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]")


@dataclass(frozen=True)
class Emitted:
    """One emitted C file and the three figures the digest record carries."""

    path: Path
    sha256: str
    nbytes: int
    nlines: int


@dataclass(frozen=True)
class Derivation:
    """What one `coqc` run of a derivation reports."""

    code: int
    wall: float
    maxrss_kb: int | None
    compile_s: float | None
    qed_s: float | None
    assumptions: str


def _run(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)


def _in_switch(argv: list[str]) -> list[str]:
    return ["opam", "exec", f"--switch={SWITCH}", "--", *argv]


def _timed(argv: list[str]) -> list[str]:
    """Wrap a child in GNU time where it exists, for its maximum resident set."""
    gnu_time = Path("/usr/bin/time")
    return [str(gnu_time), "-f", "maxrss_kb=%M", *argv] if gnu_time.exists() else argv


def stage_sources(stage: Path, sources: list[Path]) -> None:
    """Copy the sources into the stage and drop what an earlier run compiled of them."""
    stage.mkdir(parents=True, exist_ok=True)
    for source in sources:
        shutil.copyfile(source, stage / source.name)
        stem = source.stem
        for stale in (f"{stem}.vo", f"{stem}.vos", f"{stem}.vok", f"{stem}.glob", f".{stem}.aux"):
            (stage / stale).unlink(missing_ok=True)


def coqc(stage: Path, name: str) -> Derivation:
    """Compile one file in the switch and read the derivation's figures off its log."""
    started = time.monotonic()
    done = _run(_timed(_in_switch(["coqc", name])), cwd=stage)
    wall = time.monotonic() - started
    log = done.stdout + done.stderr
    (stage / f"{Path(name).stem}.log").write_text(log)
    times = [float(t) for t in FINISHED.findall(log)]
    rss = re.search(r"maxrss_kb=(\d+)", log)
    return Derivation(
        code=done.returncode,
        wall=wall,
        maxrss_kb=int(rss.group(1)) if rss else None,
        compile_s=times[0] if times else None,
        qed_s=times[1] if len(times) > 1 else None,
        assumptions=_assumptions(log),
    )


def _assumptions(log: str) -> str:
    """The `Print Assumptions` answer: the closed line, or every axiom it names."""
    if "Closed under the global context" in log:
        return "Closed under the global context"
    match = re.search(r"Axioms:\n((?:.+\n)+?)(?:\n|File |$)", log)
    if match is None:
        return "not printed"
    names = [line.split(":")[0].strip() for line in match.group(1).splitlines() if ":" in line]
    return "Axioms: " + ", ".join(names)


def extract_c(stage: Path, function: str) -> Emitted:
    """Cut the C out of the prover's `Redirect` output, byte for byte.

    The `.out` file is one Rocq string: `     = "` before the C, and `"` then
    `     : string` after it. Everything between the first and the last quote is the
    C, the printer never emitting a quote of its own, and nothing is reformatted.
    """
    out = stage / f"{function}.out"
    text = out.read_text()
    c_text = text[text.index('"') + 1:text.rindex('"')]
    path = stage / f"{function}.c"
    path.write_text(c_text)
    data = path.read_bytes()
    return Emitted(path=path, sha256=hashlib.sha256(data).hexdigest(),
                   nbytes=len(data), nlines=data.count(b"\n"))


def reaching_exit(ccomp: Path, emitted: Emitted) -> list[str]:
    """The contained `ccomp` on the emitted C: `-S`, then `-S -dcapasm`."""
    stem = emitted.path.with_suffix("")
    stage = emitted.path.parent
    lines: list[str] = []
    asm = stem.with_suffix(".s")
    done = _run([str(ccomp), "-S", "-o", str(asm), str(emitted.path)], cwd=stage)
    lines.append(f"ccomp -S: exit {done.returncode}")
    if done.returncode != 0:
        lines.append("  " + (done.stderr or done.stdout).strip()[-400:])
    if done.returncode == 0:
        text = asm.read_text()
        names = MNEMONIC.findall(text)
        capability = [m for m in CAPABILITY.findall(text) if m != "call"]
        lines.append(f"  {asm.name}: {text.count(chr(10))} lines, {len(names)} instructions, "
                     f"{len(set(names))} distinct mnemonics, {len(capability)} capability "
                     f"mnemonics (predicate ^\\s+c[a-z]+\\s, call excluded)")
    # `-dcapasm` names its file after the source and writes it into the working
    # directory, whatever `-o` says, so the child runs in the stage and a file an
    # earlier run left there is removed before it, never read as this run's.
    asm2 = Path(f"{stem}2.s")
    cap_asm = stem.with_suffix(".cap_asm")
    cap_asm.unlink(missing_ok=True)
    done = _run([str(ccomp), "-S", "-dcapasm", "-o", str(asm2), str(emitted.path)], cwd=stage)
    lines.append(f"ccomp -S -dcapasm: exit {done.returncode}")
    if done.returncode == 0 and cap_asm.exists():
        text = cap_asm.read_text()
        arms = set(TODO_ARM.findall(text))
        lines.append(f"  {cap_asm.name}: {len(text.encode())} bytes, {text.count(chr(10))} lines, "
                     f"{text.count('TODO')} TODO tokens over {len(arms)} distinct arms")
    return lines


def environment() -> list[str]:
    """The switch, its prover and the packages the derivation stands on."""
    lines: list[str] = []
    version = _run(_in_switch(["coqc", "--version"]))
    lines.append(f"switch {SWITCH}: {version.stdout.strip().splitlines()[0] if version.stdout else version.stderr.strip()}")
    listing = _run(["opam", "list", f"--switch={SWITCH}", "--installed", "--short",
                    "--columns=name,installed-version"])
    for row in listing.stdout.splitlines():
        parts = row.split()
        if len(parts) == 2 and parts[0] in PACKAGES:
            lines.append(f"  {parts[0]} {parts[1]}")
    return lines


def record_rows(emitted: list[Emitted]) -> list[str]:
    """The rows DIGESTS.md carries for these files, in its own grammar."""
    return [f"| `{e.path.name}` | `{e.sha256}` | {e.nbytes} | {e.nlines} |" for e in emitted]


def check_digests(emitted: list[Emitted]) -> int:
    """Compare each emitted file with the recorded row; 0 agrees, 1 drifts or is unrecorded."""
    recorded = {name: (sha, int(nbytes), int(nlines))
                for name, sha, nbytes, nlines in DIGEST_ROW.findall(DIGESTS.read_text())}
    drift = 0
    for e in emitted:
        row = recorded.get(e.path.name)
        if row is None:
            print(f"check: {e.path.name} has no row in {DIGESTS.name}")
            drift = 1
        elif row != (e.sha256, e.nbytes, e.nlines):
            print(f"check: {e.path.name} drifted: recorded {row[0][:12]}.. {row[1]} B {row[2]} lines, "
                  f"regenerated {e.sha256[:12]}.. {e.nbytes} B {e.nlines} lines")
            drift = 1
        else:
            print(f"check: {e.path.name} agrees with {DIGESTS.name} ({e.sha256[:12]}..)")
    return drift


def derivation_lines(name: str, d: Derivation) -> list[str]:
    figures = [f"coqc exit {d.code} in {d.wall:.2f} s wall"]
    if d.maxrss_kb is not None:
        figures.append(f"maximum resident set {d.maxrss_kb} KB")
    if d.compile_s is not None:
        figures.append(f"compile {d.compile_s:.3f} s")
    if d.qed_s is not None:
        figures.append(f"Qed {d.qed_s:.3f} s")
    return [f"{name}: " + ", ".join(figures), f"  Print Assumptions: {d.assumptions}"]


def shipped_source() -> Path | None:
    """Where the switch installed the shipped derivation, or None where it did not."""
    lib = _run(["opam", "var", f"--switch={SWITCH}", "lib"])
    if lib.returncode != 0:
        return None
    path = Path(lib.stdout.strip()) / "coq" / "user-contrib" / SHIPPED
    return path if path.exists() else None


def regenerate(args: argparse.Namespace) -> int:
    stage = Path(args.stage)
    source = Path(args.source)
    owner = Path(args.owner)
    print(f"=== bedrock2-lowering: regenerate {FUNCTION} in {stage} ===")
    for line in environment():
        print(line)

    stage_sources(stage, [owner, source])
    (stage / f"{FUNCTION}.out").unlink(missing_ok=True)
    owner_run = coqc(stage, owner.name)
    print(f"{owner.name}: coqc exit {owner_run.code} in {owner_run.wall:.2f} s wall")
    if owner_run.code != 0:
        print((stage / f"{owner.stem}.log").read_text()[-2000:])
        return 1
    derived = coqc(stage, source.name)
    for line in derivation_lines(source.name, derived):
        print(line)
    if derived.code != 0:
        print((stage / f"{source.stem}.log").read_text()[-3000:])
        return 1
    emitted = [extract_c(stage, FUNCTION)]
    print(f"{FUNCTION}.c: {emitted[0].nbytes} bytes, {emitted[0].nlines} lines, "
          f"sha256 {emitted[0].sha256}")
    if args.ccomp:
        for line in reaching_exit(Path(args.ccomp), emitted[0]):
            print(line)

    if args.baseline:
        print(f"--- baseline: {BASELINE_FUNCTION} ---")
        shipped = shipped_source()
        if shipped is not None:
            shutil.copyfile(shipped, stage / REDERIVE)
            for stale in (REDERIVE.replace(".v", ".vo"), REDERIVE.replace(".v", ".glob")):
                (stage / stale).unlink(missing_ok=True)
            for line in derivation_lines(f"{REDERIVE} (the shipped Derive, re-run here)",
                                         coqc(stage, REDERIVE)):
                print(line)
        stage_sources(stage, [BASELINE])
        (stage / f"{BASELINE_FUNCTION}.out").unlink(missing_ok=True)
        baseline_run = coqc(stage, BASELINE.name)
        for line in derivation_lines(BASELINE.name, baseline_run):
            print(line)
        if baseline_run.code == 0:
            emitted.append(extract_c(stage, BASELINE_FUNCTION))
            print(f"{BASELINE_FUNCTION}.c: {emitted[1].nbytes} bytes, {emitted[1].nlines} lines, "
                  f"sha256 {emitted[1].sha256}")
            if args.ccomp:
                for line in reaching_exit(Path(args.ccomp), emitted[1]):
                    print(line)

    print("--- DIGESTS.md rows ---")
    for row in record_rows(emitted):
        print(row)
    if args.check:
        return check_digests(emitted)
    return 0


def _guest_path(path: str) -> str:
    done = _run(["wsl", "-e", "wslpath", "-a", path])
    return done.stdout.strip() or path


def _relaunch_in_guest(argv: list[str]) -> int:
    """From the host, run this same file in WSL with every Windows path translated."""
    print("== regenerate runs in WSL; re-launching there", flush=True)
    translated = [_guest_path(arg) if WINDOWS_PATH.match(arg) else arg for arg in argv]
    script = _guest_path(str(Path(__file__).resolve()))
    try:
        return subprocess.run(["wsl", "-u", "root", "-e", "python3", script, *translated],
                              check=False).returncode
    except OSError as err:
        print(f"the guest lane could not be reached: {err}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    args_in = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description="Regenerate the descriptor check's C in the rupicola switch and hold its digest.")
    parser.add_argument("--stage", required=True,
                        help="absolute staging directory in the guest, outside every checkout")
    parser.add_argument("--source", default=str(SOURCE),
                        help="the Gallina source to derive (default: DescriptorCheck.v beside this file)")
    parser.add_argument("--owner", default=str(OWNER),
                        help="the generated interface artifact the source imports (default: proofs/RingContract.v)")
    parser.add_argument("--ccomp", default=None,
                        help="the contained ccomp to run the reaching exit through (default: not run)")
    parser.add_argument("--baseline", action="store_true",
                        help="also put the shipped ip_checksum through the same steps")
    parser.add_argument("--check", action="store_true",
                        help="compare the regenerated digests with DIGESTS.md and exit 1 on drift")
    args = parser.parse_args(args_in)
    if sys.platform == "win32":
        return _relaunch_in_guest(args_in)
    return regenerate(args)


if __name__ == "__main__":
    sys.exit(main())
