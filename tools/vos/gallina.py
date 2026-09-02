# SPDX-License-Identifier: Apache-2.0
"""The Gallina front's rig: a scratch copy of the proofs, a prover, and a vector file.

Three loops need the same three things, so they are here rather than in any one of
them. [seed.py](../seed.py) mutates a definition and asks whether the prover still
closes the artifact. [quickchick.py](../quickchick.py) compiles a harness that
enumerates inputs and prints what the definitions answer. And a mutant that survives
the prover is handed straight to the second, which is the whole point of running them
together: what a seeded weakening survives is what the theorems do not constrain, and
generated inputs are what decides whether anything else does.

**Everything happens in a copy.** Nothing here writes into `proofs/`, and not merely
out of caution: a `.vo` compiled by one switch and read by another is a stale artifact
a later run believes, the tree is shared with whatever else is running, and a mutation
is by definition a file this repository must not carry. A run stages the proofs and
the harness into the lane's own directory and compiles there.

**Two switches, and the difference is the stdlib.** The proof gate's `rocq-9.1.1`
carries `rocq-core` and nothing else, which is why the shipped proofs use the prelude
alone and name no library: an assumption reachable through an import is an assumption
inside R-05-163's gate. A vector harness has to render a number as text, so it wants
`Stdlib.Strings`, and the switch that already carries it is the CertiRocq oracle's own
`certirocq-0.9.1`. That is the right switch on its own terms as well, being the one the
Wasm oracle runs in and so the one the Gallina front is exercised in. It is **read**
here and never written.
"""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from vos import env, proofs

# The switch the Gallina front is compiled in: the CertiRocq oracle's own, which
# carries the standard library the shipped proofs deliberately do not need.
ORACLE_SWITCH = "certirocq-0.9.1"

# And the one QuickChick would be installed into, which is a decision this repository
# has not taken: see `quickchick.py` for what the install costs and why it is priced
# rather than made. Named here so the probe that reports its absence and the harness
# that would use it spell it once.
QUICKCHICK_SWITCH = "quickchick-9.1.1"

# Where the shipped proofs are, and where this repository's own Gallina harnesses are.
# The second is not under `proofs/` on purpose: the proof gate compiles everything it
# finds there and holds each constant's assumption set against the declared one, so a
# generator harness living there would put a test fixture inside the gate's subject.
PROOFS = "proofs"
HARNESS_DIR = "tools/quickchick"

# The two harnesses by the names they carry in the checkout, this lane's working
# directory under the lane root, and the file the vectors land in. Named here rather
# than in either tool, two tools driving this rig and neither being allowed its own
# name for where the other one's output went.
ENUMERATIVE = "Vectors.v"
RANDOMIZED = "Properties.v"
WORK = "gallina"
VECTORS = "vectors.txt"

# The one line a harness's output is read back through. `Compute` on a `list string`
# prints `= ["a"; "b"] : list string`, and the entries carry no quote and no backslash
# by construction, so the quoted segments are the vectors.
QUOTED = '"'


@dataclass(frozen=True)
class Failure:
    """One source the prover refused, and what it said."""

    source: str
    said: str


@dataclass(frozen=True)
class Prover:
    """A resolved prover: which switch, and the argument vector that compiles."""

    switch: str
    argv: tuple[str, ...]


# One `NAME='value'; export NAME;` line of `opam env --shell=sh`.
_EXPORT = re.compile(r"^(\w+)='(.*)';\s*export", re.MULTILINE)


def switch_env(switch: str) -> dict[str, str]:
    """One switch's own opam environment, for the child that runs in it.

    **This is load-bearing rather than tidy.** `vos.env.load` exports the *Sail*
    switch's environment into this process, because every model loop needs it; a prover
    child inherits it, and where that child shells out to `ocamlfind`, as QuickChick's
    extraction does, findlib then sees two definitions of `zarith` and picks the wrong
    one. The failure is `Unbound module Big_int_Z` inside a generated OCaml file in
    /tmp, which names neither switch and reads as a defect in QuickChick.

    So a prover child is given its own switch's variables, laid over the inherited ones
    rather than replacing them: PATH, OCAMLPATH and the rest come from the switch that
    is about to be compiled in, and everything the parent set for other reasons stays.
    """
    done = subprocess.run(["opam", "env", f"--switch={switch}", "--shell=sh"],
                          capture_output=True, text=True, check=False)
    if done.returncode != 0:
        return {}
    return {name: value.replace("'\\''", "'")
            for name, value in _EXPORT.findall(done.stdout)}


def prover(switch: str) -> Prover | None:
    """The prover in one named switch, or None where that switch is not installed.

    Rocq 9 ships no `coqc` at any version, its switch holding `rocq`, `rocq.byte` and
    `rocqchk`, so compilation is spelled `rocq c`. Resolved by switch and never off
    PATH: a bare `rocq` is whichever switch the shell was last told about, and a run
    that compiled in one switch and reported the other's version is evidence about
    nothing.
    """
    binary = env.opam_root() / switch / "bin" / "rocq"
    if not binary.is_file():
        return None
    return Prover(switch=switch, argv=(str(binary), "c"))


def version(found: Prover) -> str:
    """What the resolved prover calls itself, for the run that has to record it."""
    done = subprocess.run([found.argv[0], "--version"], capture_output=True,
                          encoding="utf-8", errors="replace", check=False)
    return done.stdout.strip().splitlines()[0] if done.stdout.strip() else "unknown"


def stage(root: Path, work: Path) -> Path:
    """Copy the proofs and this repository's Gallina harnesses into a scratch tree.

    The whole directory rather than the files one loop names, because a `Require` is
    resolved against the load path and a partial copy fails at the first companion. The
    tree is rebuilt from scratch on every run: a `.vo` left over from a previous
    mutant is exactly the stale artifact this rig must not read.
    """
    if work.exists():
        shutil.rmtree(work)
    (work / PROOFS).parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root / PROOFS, work / PROOFS,
                    ignore=shutil.ignore_patterns("*.vo", "*.vok", "*.vos", "*.glob",
                                                  ".*.aux"))
    harness = root / HARNESS_DIR
    if harness.is_dir():
        shutil.copytree(harness, work / "harness",
                        ignore=shutil.ignore_patterns("*.vo", "*.vok", "*.vos",
                                                      "*.glob", ".*.aux"))
    return work


def compile_one(found: Prover, work: Path, source: Path,
                timeout: int = 900) -> subprocess.CompletedProcess[str]:
    """One source, with the proofs directory rooted at the empty logical path.

    `-Q proofs ""` is the proof gate's own spelling, so a companion's `Require Import`
    resolves to the `.vo` built here and never to an installed one.
    """
    return subprocess.run(
        [*found.argv, "-q", "-Q", PROOFS, "", "-Q", "harness", "",
         source.relative_to(work).as_posix()],
        cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, check=False,
        env={**os.environ, **switch_env(found.switch)})


def _compile_waves(found: Prover, work: Path,
                   ordered: list[list[Path]]) -> list[Failure]:
    """Sources already put in dependency order, every failure kept.

    Failures accumulate rather than stopping the run, because a mutation inside a
    definition several proofs read is refused by each of them and the reader wants to
    know which.
    """
    out: list[Failure] = []
    for wave in ordered:
        for source in wave:
            done = compile_one(found, work, source)
            if done.returncode != 0:
                out.append(Failure(source=source.name,
                                   said=(done.stderr or done.stdout).strip()))
    return out


def _compile_all(found: Prover, work: Path, sources: list[Path]) -> list[Failure]:
    """One directory's sources in Require order."""
    return _compile_waves(found, work, proofs.waves(sources))


def compile_proofs(found: Prover, work: Path) -> list[Failure]:
    """Every shipped proof in the staged tree, in Require order."""
    return _compile_all(found, work, sorted((work / PROOFS).glob("*.v")))


def compile_dependents(found: Prover, work: Path, rel: str) -> list[Failure]:
    """The one mutated proof and whatever Requires it, which is what a mutant moves.

    `compile_proofs` is the right shape for a baseline, where nothing on disk is
    trusted yet. Inside the population loop it recompiles the whole directory once per
    member, and all but the mutated file's closure is work whose answer cannot have
    changed: [proofs.dependents](proofs.py) states why the narrowing keeps the whole
    failure set. Most proofs here are Required by nothing, so for most subjects the
    closure is the subject alone and the directory was being rebuilt around it once per
    member of the population. That price is one a proof has already been written
    against: a source in this tree declines a `Require` it would otherwise carry, and
    says in its own prose that the reason is what the mutation loop would charge for it.

    A subject the proofs directory does not hold falls back to the whole directory,
    because the closure of a name that is not there is empty and an empty compile would
    report a green baseline for a tree nobody built.
    """
    sources = sorted((work / PROOFS).glob("*.v"))
    stem = Path(rel).stem
    if stem not in {source.stem for source in sources}:
        return _compile_all(found, work, sources)
    return _compile_waves(found, work, proofs.dependents(sources, stem))


def compile_support(found: Prover, work: Path) -> list[Failure]:
    """The harness directory's shared sources: everything there that is not an entry
    point, which is what an entry point's `Require` resolves against.

    The two entry points are excluded by name rather than by their contents, because
    one of them needs a library this repository has not installed and compiling it to
    satisfy the other one's imports would make the enumerative half wait on the
    randomized half's price.
    """
    shared = [p for p in sorted((work / "harness").glob("*.v"))
              if p.name not in (ENUMERATIVE, RANDOMIZED)]
    return _compile_all(found, work, shared)


def vectors(found: Prover, work: Path, harness: Path) -> tuple[list[str], str]:
    """Compile one harness and read the vectors it printed, or say why there are none.

    The harness ends in a `Compute` over a `list string`, so the prover's own stdout is
    the artifact: every quoted segment is one vector, in the order the list holds them.
    A harness that printed nothing is an error rather than an empty run, an empty
    comparison being the failure mode every rule in this repository is written against.
    """
    done = compile_one(found, work, harness)
    if done.returncode != 0:
        return [], (done.stderr or done.stdout).strip()
    lines = _quoted(done.stdout)
    if not lines:
        return [], ("the harness compiled and printed no quoted vector; it must end "
                    "in a `Compute` over a `list string`")
    return lines, ""


def properties(found: Prover, work: Path, harness: Path) -> tuple[int, int, str]:
    """Run the randomized harness: how many property sets passed, how many failed, and
    the first counterexample where one did.

    QuickChick runs a property at compile time and prints its verdict, so the prover's
    own stdout is the result: `+++ Passed` per set, `*** Failed` with the shrunk
    counterexample under it. A compile that did not run at all is reported as a failure
    of every set rather than as none, an empty run being the vacuous pass every floor in
    this repository exists to catch.
    """
    done = compile_one(found, work, harness)
    said = done.stdout + done.stderr
    passed = said.count("+++ Passed")
    failed = said.count("*** Failed")
    if done.returncode != 0 and not failed:
        return 0, max(1, passed + failed), _first(said, "the harness did not compile")
    return passed, failed, _first(said, "") if failed else ""


def _first(text: str, fallback: str) -> str:
    """The first line that says something a reader wants, for a one-line verdict."""
    for line in text.splitlines():
        if line.strip().startswith(("*** Failed", "Error", "Failed")):
            return line.strip()[:200]
    return fallback


def _quoted(text: str) -> list[str]:
    """Every double-quoted segment of the prover's output, in order.

    A scan rather than a regular expression over the whole text, the printed list being
    one logical line of some hundreds of kilobytes: the entries carry no quote and no
    escape by construction, which is what makes the scan exact rather than a heuristic.
    """
    out: list[str] = []
    rest = text
    while True:
        start = rest.find(QUOTED)
        if start < 0:
            return out
        end = rest.find(QUOTED, start + 1)
        if end < 0:
            return out
        out.append(rest[start + 1:end])
        rest = rest[end + 1:]


def write(lines: list[str], target: Path) -> Path:
    """The vectors as a file, one per line, so the comparison is the same text
    comparison the Sail lane makes and the same one R1a made."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return target


def work_dir(lane_root: Path) -> Path:
    """Where the Gallina front stages and compiles in this lane."""
    path = lane_root / WORK
    path.mkdir(parents=True, exist_ok=True)
    return path


def emit(root: Path, work: Path, out: list[str],
         harness: str = ENUMERATIVE) -> list[str] | None:
    """Stage, compile the proofs, compile one harness, and hand back its vectors.

    The proofs are compiled first and whole rather than left to the harness's own
    `Require`, so a proof the staged tree cannot build is reported as what it is
    instead of as a load-path failure several files away inside the harness.
    """
    found = prover(ORACLE_SWITCH)
    if found is None:
        out.append(f"FAIL no prover in the {ORACLE_SWITCH} switch; "
                   "tools/wasm-oracle/README.md states how it is created")
        return None
    stage(root, work)
    failures = compile_proofs(found, work) + compile_support(found, work)
    if failures:
        out.extend(f"FAIL {f.source} did not compile:\n{f.said}" for f in failures)
        return None
    source = work / "harness" / harness
    if not source.is_file():
        out.append(f"FAIL there is no harness at {HARNESS_DIR}/{harness}")
        return None
    lines, said = vectors(found, work, source)
    if said:
        out.append(f"FAIL {harness} did not run:\n{said}")
        return None
    return lines
