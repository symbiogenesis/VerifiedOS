# SPDX-License-Identifier: Apache-2.0
"""The Gallina front's rig: a scratch copy of the proofs, a prover, and a vector file.

Three loops need the same three things, so they are here rather than in any one of
them. [run.py seed](cli/seed.py) mutates a definition and asks whether the prover still
closes the artifact. [run.py quickchick](cli/quickchick.py) compiles a harness that
enumerates inputs and prints what the definitions answer. And a mutant that survives
the prover is handed straight to the second, which is the whole point of running them
together: what a seeded weakening survives is what the theorems do not constrain, and
generated inputs are what decides whether anything else does.

**Everything happens in a copy.** Nothing here writes into `proofs/`, and not merely
out of caution: a `.vo` compiled by one switch and read by another is a stale artifact
a later run believes, the tree is shared with whatever else is running, and a mutation
is by definition a file this repository must not carry. A run stages the proofs and
the harness into the lane's own directory and compiles there.

**A harness compiles in the switch its libraries decide.** The vector harnesses load
Stdlib and nothing else, and the proof gate's switch carries Stdlib, so
`quickchick vectors`, `quickchick freeze`, `kernel vectors` and `seed coq`'s enumerative
mode compile in that switch, at the gate's release and under their own flags: a proof
source that compiles under the gate compiles under them. The randomized harness loads
QuickChick and the Wasm oracle loads CertiRocq, and no release of either admits a Rocq
newer than 9.1, so each keeps a switch of its own at Rocq 9.1.1; the walk harness that
decides the property sets small enough to enumerate compiles beside the randomized one.
QuickChick's commit-pinned recipe builds a second QuickChick switch, at the gate's
release, which a run asks for by name while that recipe's lock awaits its hosted
checks. K-117 holds what each instrument older than Rocq 9.3.0 compiles, these two and the
Rupicola lowering among them, free of the syntax only Rocq 9.3 reads. Every switch is
**read** here and never written.
"""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from vos import env, proofs

# The switch the Stdlib-only harnesses compile in: the proof gate's own, at its release.
# Named here rather than spelled `env.ROCQ_SWITCH` at each instrument, so that the
# switch every vector instrument compiles in is one constant rather than a choice each
# instrument restates.
VECTOR_SWITCH = env.ROCQ_SWITCH
VECTOR_ROCQ_VERSION = env.ROCQ_VERSION

# The CertiRocq oracle's switch, where the Wasm oracle compiles: CertiRocq and its Wasm
# library cap Rocq below 9.2. tools/opam/certirocq.lock is its snapshot.
ORACLE_ROCQ_VERSION = "9.1.1"
CERTIROCQ_VERSION = "0.9.1+9.1"
# The first candidate below, declared: CertiRocq's native certirocqc bootstrap includes
# its runtime's Hd_val macro beside OCaml's runtime header, which at 4.14.4 defines the
# same macro token for token, where OCaml 5.2 made it an inline function the macro
# collides with. The release builds, bootstraps and passes the Wasm oracle's checks there,
# in the switch it built and again in the switch imported from the snapshot.
ORACLE_OCAML_VERSION = "4.14.4"
ORACLE_SWITCH = f"verifiedos-certirocq-0.9.1-ocaml-{ORACLE_OCAML_VERSION}"

# The candidates for that switch, in the order they are tried: the released CertiRocq,
# unpatched, at each OCaml release, beside every dependency opam resolves for it from
# rocq-released and the default repository. OCaml 4.14.4 comes first because its
# runtime header defines Hd_val as the same macro, token for token, that the native
# certirocqc bootstrap's C wrapper includes beside it; 5.1.1 defines another macro. A
# candidate is declared only once it builds and the Wasm oracle's positive and seeded
# negative checks pass in it: its export becomes tools/opam/certirocq.lock and
# ORACLE_OCAML_VERSION names it. The 4.14.4 candidate passed and is declared, so the
# 5.1.1 candidate's recipe has not been run. Each is built in an opam root that does not
# already hold its switch, such as a lane's private root.
ORACLE_CANDIDATE_OCAML_VERSIONS: tuple[str, ...] = ("4.14.4", "5.1.1")


def oracle_candidate_switch(ocaml: str) -> str:
    """The switch one candidate builds, named as ORACLE_SWITCH would name it."""
    return f"verifiedos-certirocq-0.9.1-ocaml-{ocaml}"


def oracle_candidate_build(ocaml: str) -> tuple[tuple[str, ...], ...]:
    """The argv that builds one candidate from released packages, into a root carrying
    rocq-released and the default repository; it pins nothing and reads no checkout."""
    switch = oracle_candidate_switch(ocaml)
    return (
        ("opam", "switch", "create", switch, "--repos=rocq-released,default",
         f"--packages=ocaml-base-compiler.{ocaml}", "--no-switch", "-y"),
        ("opam", "install", f"--switch={switch}", "-y",
         f"ocamlfind.{env.OCAMLFIND_VERSION}", f"rocq-certirocq.{CERTIROCQ_VERSION}"),
    )

# QuickChick's coq-simple-io dependency caps Coq below 9.2~ independently of CertiRocq.
# Its dune < 3.22 constraint warrants a separate resolution from the Wasm oracle.
QUICKCHICK_ROCQ_VERSION = ORACLE_ROCQ_VERSION
QUICKCHICK_SWITCH = (f"verifiedos-quickchick-{QUICKCHICK_ROCQ_VERSION}"
                     f"-ocaml-{env.OCAML_VERSION}")

# The switch QuickChick's commit-pinned recipe builds, tools/vos/cli/quickchick.py's
# RECIPE, at Rocq 9.3.0, beside which no QuickChick, coq-simple-io or coq-ext-lib
# release installs. Named apart from QUICKCHICK_SWITCH while the recipe's lock is
# pending its hosted checks, so a run can ask for either. A literal rather than
# `env.ROCQ_VERSION`, because a move of the proof switch's lock does not move this one.
QUICKCHICK_RECIPE_ROCQ_VERSION = "9.3.0"
QUICKCHICK_RECIPE_SWITCH = (f"verifiedos-quickchick-{QUICKCHICK_RECIPE_ROCQ_VERSION}"
                            f"-ocaml-{env.OCAML_VERSION}")

# Where the shipped proofs are, and where this repository's own Gallina harnesses are.
# The second is not under `proofs/` on purpose: the proof gate compiles everything it
# finds there and holds each constant's assumption set against the declared one, so a
# generator harness living there would put a test fixture inside the gate's subject.
PROOFS = "proofs"
HARNESS_DIR = "tools/quickchick"

# The harnesses by the names they carry in the checkout, this lane's working directory
# under the lane root, and the files the vectors land in. Named here rather than in
# either tool, three tools driving this rig and none being allowed its own name for
# where another one's output went.
ENUMERATIVE = "Vectors.v"
RANDOMIZED = "Properties.v"
EXHAUSTIVE = "Walks.v"
FREEZE = "FreezeModel.v"
KERNEL = "KernelVectors.v"
WORK = "gallina"
VECTORS = "vectors.txt"
FREEZE_VECTORS = "freeze-vectors.txt"
FREEZE_MODEL = "freeze-model.txt"

# Every harness that is an *entry point*: a file `compile_support` must leave alone,
# because a run compiles exactly one of them and the others are either priced on a
# library this switch may not hold or are a second subject entirely. A set rather than
# a tuple spelled at the one site that reads it, so that adding a harness is one edit
# here and the exclusion cannot be the half somebody forgets.
ENTRY_POINTS: frozenset[str] = frozenset({ENUMERATIVE, RANDOMIZED, EXHAUSTIVE, FREEZE,
                                          KERNEL})

# The support harnesses only the randomized half's two entry points Require:
# IPCProperties.v states the property sets Properties.v draws and Walks.v walks.
# `compile_support` leaves them alone unless it is asked for that half, by name for the
# reason the entry points are: a vector run that compiled them would pay for statements
# none of its harnesses reads, and would stop on one that did not compile.
RANDOMIZED_SUPPORT: frozenset[str] = frozenset({"IPCProperties.v"})

# The one line a harness's output is read back through. `Compute` on a `list string`
# prints `= ["a"; "b"] : list string`, and the entries carry no quote and no backslash
# by construction, so the quoted segments are the vectors.
QUOTED = '"'

# How many draws QuickChick spends on one property set, its `stdArgs`' `maxSuccess`. A
# set whose domain holds no more points than this is walked whole by the exhaustive
# harness rather than drawn, a draw of that many covering no such domain.
DRAWS = 10_000

# The one sentence that fixes QuickChick's random state in the randomized harness.
# QuickChick extracts `newRandomSeed` as `Random.State.make_self_init ()`, read from
# system-dependent data, so a verdict it reaches need not replay; the harness states the
# seed instead, read here so a run can report it and refuse a harness that states none.
_SEED = re.compile(r"\bExtract\s+Constant\s+(?:[\w']+\.)*newRandomSeed\s*=>\s*"
                   r'"\(\s*Random\.State\.make\s*\[\|\s*(\d+)\s*\|\]\s*\)"\s*\.')


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


@dataclass(frozen=True)
class Walk:
    """One property set the exhaustive harness decided over its whole domain: how many
    points the domain holds, how many meet the property's premise, how many refute the
    property, and the position of the first that does, None where none does."""

    name: str
    points: int
    premise: int
    refuted: int
    first: int | None


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
    # Captured, so it reads no standard input and is passed no answer: over a root whose
    # format upgrade cannot be made in memory, opam declines and the child runs without
    # the switch's variables, as `env._apply_opam_env` does for the Sail switch.
    done = subprocess.run(["opam", "env", f"--switch={switch}", "--shell=sh"],
                          capture_output=True, text=True, check=False,
                          stdin=subprocess.DEVNULL, env=env.declining_environment())
    if done.returncode != 0:
        return {}
    return {name: value.replace("'\\''", "'")
            for name, value in _EXPORT.findall(done.stdout)}


def prover(switch: str) -> Prover | None:
    """The prover in one named switch, or None where that switch is not installed.

    Rocq's core package provides `rocq`; the legacy `coqc` command requires the Coq
    compatibility package, so compilation is consistently spelled `rocq c`.
    Resolved by switch and never off
    PATH: a bare `rocq` is whichever switch the shell was last told about, and a run
    that compiled in one switch and reported the other's version is evidence about
    nothing.
    """
    binary = env.opam_root() / switch / "bin" / "rocq"
    if not binary.is_file():
        return None
    return Prover(switch=switch, argv=(str(binary), "c"))


def vector_prover() -> Prover | None:
    """The prover `emit` compiles with, asked here once, so a run's report names the
    switch its vectors came from rather than restating the choice."""
    return prover(VECTOR_SWITCH)


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


def compile_dependents(found: Prover, work: Path, rel: str,
                       moved: list[list[Path]] | None = None) -> list[Failure]:
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

    `moved`, where given, is what `closure_dependents` says the mutant moves inside the
    harnesses' `Require` closure, and only the proofs among it are compiled: a proof
    outside that closure is never handed to the prover, however many of them Require
    the subject.
    """
    if moved is not None:
        return _compile_waves(found, work, [[s for s in wave if s.parent == work / PROOFS]
                                            for wave in moved])
    sources = sorted((work / PROOFS).glob("*.v"))
    stem = Path(rel).stem
    if stem not in {source.stem for source in sources}:
        return _compile_all(found, work, sources)
    return _compile_waves(found, work, proofs.dependents(sources, stem))


def closure(work: Path, *harnesses: Path) -> list[list[Path]]:
    """The harnesses' `Require` closure over a tree holding the proofs and the
    harnesses' own directory, in dependency order, each harness in a wave after
    everything it Requires, one harness so in the last wave. The tree is the staged one,
    or the checkout, whose harnesses the stage copies unchanged.

    The proofs and the harnesses are read as one namespace because `compile_one` roots
    both directories at the empty logical path, so a harness's `Require` resolves
    against either and its closure runs through both. Several harnesses, all in one
    directory, are read as one closure, so a source two of them Require is in it once,
    in the order the union gives it.
    """
    sources = (sorted((work / PROOFS).glob("*.v"))
               + sorted(harnesses[0].parent.glob("*.v")))
    index = proofs.SourceIndex.read(sources)
    wanted = {s for harness in harnesses for s in index.imports[harness]} | set(harnesses)
    return [[s for s in wave if s in wanted] for wave in index.ordered
            if any(s in wanted for s in wave)]


def closure_dependents(work: Path, rel: str, *harnesses: Path) -> list[list[Path]]:
    """What a mutation of `rel` moves inside the harnesses' `Require` closure: `rel` and
    each member that Requires it, directly or through another member, proofs and
    support harnesses alike, in Require order, the harnesses themselves left for their
    caller to run. `compile_dependents` takes the proofs of it and `compile_support` the
    rest.

    A subject the closure does not hold moves the closure whole, for the reason
    `compile_dependents` falls back to the whole directory.
    """
    whole = [kept for wave in closure(work, *harnesses)
             if (kept := [s for s in wave if s not in harnesses])]
    return proofs.dependents([s for wave in whole for s in wave], Path(rel).stem) or whole


def compile_closure(found: Prover, work: Path, *harnesses: Path) -> list[Failure]:
    """What the harnesses Require and nothing else, in Require order, every failure
    kept; the harnesses themselves are left for their caller to run.

    Several harnesses are read as one closure, as `closure` reads them, so a source two
    of them Require is compiled once."""
    return _compile_waves(found, work, [[s for s in wave if s not in harnesses]
                                        for wave in closure(work, *harnesses)])


def is_support(name: str, randomized: bool = False) -> bool:
    """Whether `compile_support` compiles the harness of this name: never an entry
    point, and the randomized half's own support only with `randomized`. One predicate
    rather than a set difference spelled at each reader, K-117 reading it as well."""
    return name not in ENTRY_POINTS and (randomized or name not in RANDOMIZED_SUPPORT)


def compile_support(found: Prover, work: Path, moved: list[list[Path]] | None = None,
                    randomized: bool = False) -> list[Failure]:
    """The harness directory's shared sources: everything there that is not an entry
    point, which is what an entry point's `Require` resolves against, and is not the
    randomized half's own support unless `randomized` asks for that half.

    The entry points are excluded by name rather than by their contents, and the reason
    is one per harness. The randomized half needs a library this repository installs in
    a switch of its own, and compiling it to satisfy another harness's imports would
    make the enumerative half wait on the randomized half's price. The walk harness
    decides its sets over whole domains as it compiles, a price only the randomized
    half's runs owe. The freeze model is a second subject with no reader here at all:
    compiling it as shared support would put a `Compute` over a hundred vectors inside
    every `quickchick vectors` run and inside every seeded mutant's baseline, which is a
    price paid by loops that decide nothing about it. The randomized half's support is
    that half's price too, and a mutant over which it alone does not compile is one the
    vectors still decide rather than one their harness could not be built over.

    `moved`, where given, is what `closure_dependents` says a mutant moves inside the
    harnesses' closure, and only the shared sources among it are compiled, in its order,
    `randomized` admitting the randomized half's own support as it does for the rest.
    """
    if moved is not None:
        return _compile_waves(found, work, [[s for s in wave if s.parent == work / "harness"
                                             and is_support(s.name, randomized)]
                                            for wave in moved])
    shared = [p for p in sorted((work / "harness").glob("*.v"))
              if is_support(p.name, randomized)]
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
    own stdout is the result: `+++ Passed` per set, `*** Failed` with the drawn
    counterexample under it, unshrunk, `forAll` shrinking nothing. A compile that did
    not run at all is reported as a failure of every set rather than as none, an empty
    run being the vacuous pass every floor in this repository exists to catch.
    """
    done = compile_one(found, work, harness)
    said = done.stdout + done.stderr
    passed = said.count("+++ Passed")
    failed = said.count("*** Failed")
    if done.returncode != 0 and not failed:
        return 0, max(1, passed + failed), _first(said, "the harness did not compile")
    return passed, failed, _first(said, "") if failed else ""


def seed(harness: Path) -> str | None:
    """The seed the randomized harness fixes QuickChick's random state at, or None where
    it fixes none or fixes it other than once.

    Read with the comments blanked by the shared lexer, so a commented-out sentence
    fixes nothing."""
    try:
        text = proofs.strip_comments(harness.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None
    found = [str(m.group(1)) for m in _SEED.finditer(text)]
    return found[0] if len(found) == 1 else None


def walks(found: Prover, work: Path, harness: Path) -> tuple[list[Walk], str]:
    """Run the exhaustive harness: each property set it walked, or why there are none.

    The harness loads Stdlib alone and ends in a `Compute` over a `list string`, one
    entry per set, `name points premise refuted first`, the last `-` where no point
    refutes. A harness that did not compile, printed no entry or printed one this cannot
    read is an error rather than a set that held, so a walk that never ran reads as no
    verdict.
    """
    lines, said = vectors(found, work, harness)
    if said:
        return [], said
    out: list[Walk] = []
    for line in lines:
        parts = line.rsplit(" ", 4)
        numbers = parts[1:]
        if (len(parts) != 5 or not all(n.isdigit() for n in numbers[:3])
                or not (numbers[3].isdigit() or numbers[3] == "-")):
            return [], (f"the walk harness printed {line!r}, which is not "
                        "`name points premise refuted first`")
        out.append(Walk(name=parts[0], points=int(numbers[0]), premise=int(numbers[1]),
                        refuted=int(numbers[2]),
                        first=None if numbers[3] == "-" else int(numbers[3])))
    return out, ""


def walk_failures(found_walks: list[Walk]) -> list[str]:
    """Each walked set that does not hold, as one line naming it: one a point refutes,
    one whose domain is empty and so decides nothing, and one whose premise no point
    meets, which holds vacuously."""
    out: list[str] = []
    for w in found_walks:
        if w.refuted:
            out.append(f"{w.name}: {w.refuted} of {w.points} point(s) refute it, the "
                       f"first at position {w.first}")
        elif not w.points:
            out.append(f"{w.name}: its domain holds no point, so it decides nothing")
        elif not w.premise:
            out.append(f"{w.name}: no one of its {w.points} point(s) meets its premise, "
                       "so it holds vacuously")
    return out


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
    found = vector_prover()
    if found is None:
        out.append(f"FAIL no prover in the {VECTOR_SWITCH} switch, the proof gate's; "
                   "`run.py provision --apply` imports it")
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
