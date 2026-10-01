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
QuickChick, which no release builds at Rocq 9.3, so it compiles in a switch of its own
built from pinned commits at the gate's release, beside the walk harness that decides
the property sets small enough to enumerate. The Wasm oracle loads CertiRocq, which no
release admits a Rocq newer than 9.1, so it keeps a switch at Rocq 9.1.1. K-117 holds
what each instrument older than Rocq 9.3.0 compiles, the Wasm oracle and the Rupicola
lowering, free of the syntax only Rocq 9.3 reads. Every switch is **read** here and
never written.
"""

import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from contextvars import ContextVar
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


# The switch QuickChick's commit-pinned recipe builds, tools/vos/cli/quickchick.py's
# RECIPE, at Rocq 9.3.0, beside which no QuickChick, coq-simple-io or coq-ext-lib
# release installs. QUICKCHICK_SWITCH below names this same switch, since the tracked
# lock is this recipe's export, so a recipe moved ahead of that lock is built and
# checked in a root that does not already hold that switch. A literal rather than
# `env.ROCQ_VERSION`, because a move of the proof switch's lock does not move this one.
QUICKCHICK_RECIPE_ROCQ_VERSION = "9.3.0"
QUICKCHICK_RECIPE_SWITCH = (f"verifiedos-quickchick-{QUICKCHICK_RECIPE_ROCQ_VERSION}"
                            f"-ocaml-{env.OCAML_VERSION}")

# QuickChick's switch, the one provisioning imports tools/opam/quickchick.lock into:
# that lock is the export of a hosted run that built the recipe's switch and passed the
# randomized half's checks on it, so the two are one switch at one release, and neither
# is the CertiRocq switch's.
QUICKCHICK_ROCQ_VERSION = QUICKCHICK_RECIPE_ROCQ_VERSION
QUICKCHICK_SWITCH = QUICKCHICK_RECIPE_SWITCH

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

# The wall-clock seconds one prover run is given before it is stopped, unless its caller
# names another limit. Read when a compile starts rather than bound as a default, so a
# test can lower it for the run it makes.
COMPILE_TIMEOUT = 900

# The one sentence that fixes QuickChick's random state in the randomized harness.
# QuickChick extracts `newRandomSeed` as `Random.State.make_self_init ()`, read from
# system-dependent data, so a verdict it reaches need not replay; the harness states the
# seed instead, read here so a run can report it and refuse a harness that states none.
_SEED = re.compile(r"\bExtract\s+Constant\s+(?:[\w']+\.)*newRandomSeed\s*=>\s*"
                   r'"\(\s*Random\.State\.make\s*\[\|\s*(\d+)\s*\|\]\s*\)"\s*\.')

# A sentence that Requires QuickChick's library: `From QuickChick Require ...`, or a
# `Require` naming QuickChick before its sentence ends. Loading the library replays
# QuickChick's own `Extract Constant newRandomSeed`, so a seed stated ahead of the last
# such sentence fixes nothing; a qualified name's dot is followed by a letter, which is
# what keeps the scan inside one sentence.
_REQUIRES_QUICKCHICK = re.compile(r"\bFrom\s+QuickChick\s+Require\b"
                                  r"|\bRequire\b(?:(?!\.(?:\s|$)).)*?\bQuickChick\b",
                                  re.DOTALL)


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
class Compiled:
    """One prover run: the source as staged, relative to the tree it compiled in, its
    wall seconds, its exit, None where it reached its limit and was stopped, and the
    limit it was given."""

    source: str
    seconds: float
    exit: int | None
    limit: float


class CompileTimeout(subprocess.TimeoutExpired):
    """A prover run that reached its limit and was stopped: the source as staged and the
    limit, `timeout`. A `TimeoutExpired`, so a caller catching that still catches it."""

    def __init__(self, source: str, timeout: float, cmd: list[str]) -> None:
        super().__init__(cmd, timeout)
        self.source = source


def signal_named(number: int) -> str:
    """A signal as a reason names it: its number, and its name where this platform's
    `signal` module knows one."""
    try:
        return f"signal {number} ({signal.Signals(number).name})"
    except ValueError:
        return f"signal {number}"


class CompileSignalled(subprocess.SubprocessError):
    """A prover run a signal ended rather than an exit, a kill for want of memory among
    them: the source as staged and the signal's number, `signal`. Raised where a compile
    is read for an answer, by `_compile_waves` and `vectors`, so a run nothing decided is
    never read as a source the prover refused or a harness that did not build."""

    def __init__(self, source: str, number: int) -> None:
        super().__init__(f"the compile of {source} was ended by {signal_named(number)}")
        self.source = source
        self.signal = number


def _exited(work: Path, source: Path,
            done: subprocess.CompletedProcess[str]) -> subprocess.CompletedProcess[str]:
    """A prover run handed back where it ended on an exit, and `CompileSignalled` raised
    where a signal ended it, which POSIX reports as a negative return code."""
    if done.returncode < 0:
        raise CompileSignalled(source.relative_to(work).as_posix(), -done.returncode)
    return done


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


# One count of a walk line: ASCII digits and nothing else, as Walks.v's `ns` prints one.
# `str.isdigit` admits a superscript digit that `int` then refuses.
_COUNT = re.compile(r"[0-9]+")

# The line on which QuickChick's plugin reports a drawn set's extracted program that
# built and did not finish: its command, `time` and the program, then `Exited with status
# N`, `Killed (N)` or `Stopped (N)`, on the prover's `Error:` line or the one after it,
# and then, after a blank line, what the program and `time` wrote to standard error.
# QuickChick 2.2.0's plugin builds the message so in plugin/quickChick.mlg.cppo, the
# status read from the shell that runs `time` and the program.
_UNFINISHED = re.compile(r"^(?:Error:[ \t]*)?(?P<said>\S.*?: (?:Exited with status "
                         r"(?P<status>-?\d+)|(?P<signalled>Killed|Stopped) \(-?\d+\)))"
                         r"[ \t]*$", re.MULTILINE)

# What OCaml's runtime writes to standard error for an exception nothing caught, before
# it exits with status 2: the exception's name, qualified or not, and its arguments.
_EXCEPTION = re.compile(r"^Fatal error: exception (?P<name>[A-Za-z_][\w'.]*)(?P<args>.*?)"
                        r"[ \t\r]*$", re.MULTILINE)

# The exceptions that are the program's memory or stack running out rather than a value
# the subject made it compute, so a set ending on one decides nothing about the subject.
_EXHAUSTION = frozenset({"Out_of_memory", "Stack_overflow"})

# GNU time's line for a program a signal ended, after which it exits 128 + the signal, as
# the shell's own `time` does without the line.
_TERMINATED = re.compile(r"\bCommand terminated by signal (?P<signal>\d+)")

# The notice QuickChick prints as it starts a set, naming the set as the harness states
# it, and the prover's header naming the line of the sentence it stopped at.
_QUICKCHECKING = re.compile(r"^QuickChecking (?P<set>.*?)[ \t\r]*$", re.MULTILINE)
_LOCATED = re.compile(r'^File "[^"]*", line (?P<line>\d+)', re.MULTILINE)

# How one compile of the randomized harness ended, as `drawn_sets` reads it. Decided: a
# draw refuted a set, or the compile finished with every set it reached passed. Crashed:
# no draw refuted a set, and a set's extracted program built and then ended on an
# exception nothing caught other than memory or stack running out, which the program
# never does over the unmutated tree, whose baseline finished every set. Unanswered: a
# set's program ended on what decides nothing about the subject: memory or stack running
# out, a signal, a program or `time` that could not run, or a status this reader cannot
# classify; or a signal ended the prover. Nothing: the harness did not build, its Rocq or
# its extracted OCaml, or it printed no verdict.
DRAWN_DECIDED = "decided"
DRAWN_CRASHED = "crashed"
DRAWN_UNANSWERED = "unanswered"
DRAWN_NOTHING = "nothing"


@dataclass(frozen=True)
class Drawn:
    """What one compile of the randomized harness decided: how many property sets passed
    and how many a draw refuted, the first counterexample or the reason no set was
    decided, and which of the `DRAWN_` readings says how the compile ended."""

    passed: int
    failed: int
    why: str
    ended: str


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


# Who is told of each prover run in this context: one callback, set by `observed` around
# the compiles a caller wants accounted, and none elsewhere. A context variable rather
# than an argument threaded through every reader that compiles, and per thread, so the
# shards of one run each report into their own account.
_OBSERVER: ContextVar[Callable[[Compiled], None] | None] = ContextVar("gallina_observer",
                                                                     default=None)


@contextmanager
def observed(callback: Callable[[Compiled], None]) -> Iterator[None]:
    """Tell `callback` of each prover run this thread makes inside the block, as it ends,
    the one that reaches its limit among them."""
    token = _OBSERVER.set(callback)
    try:
        yield
    finally:
        _OBSERVER.reset(token)


def _stop(running: subprocess.Popen[str]) -> None:
    """End a prover run and every process it started, and reap it.

    On POSIX the run leads a session of its own, so its group is everything it started:
    QuickChick runs each drawn set's extracted program as a grandchild of the prover,
    and a kill of the prover alone leaves that program running under every later
    compile, whose seconds a comparison between dispatches reads. Windows has no process
    group to end, and the prover alone is killed, as `subprocess.run` kills it."""
    if sys.platform != "win32":
        with suppress(ProcessLookupError):
            os.killpg(running.pid, signal.SIGKILL)
        running.wait()
        return
    running.kill()
    running.communicate()


def compile_one(found: Prover, work: Path, source: Path,
                timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    """One source, with the proofs directory rooted at the empty logical path.

    `-Q proofs ""` is the proof gate's own spelling, so a companion's `Require Import`
    resolves to the `.vo` built here and never to an installed one.

    Stopped at `timeout` seconds, `COMPILE_TIMEOUT` where none is named, and then raises
    `CompileTimeout` naming the source and the limit. A stop, or an interrupt of the
    wait, ends the prover's whole process group, as `_stop` states. The prover run alone
    is timed, the switch environment being read ahead of it, and an observer `observed`
    set is told of it either way.
    """
    rel = source.relative_to(work).as_posix()
    limit = COMPILE_TIMEOUT if timeout is None else timeout
    argv = [*found.argv, "-q", "-Q", PROOFS, "", "-Q", "harness", "", rel]
    environment = {**os.environ, **switch_env(found.switch)}
    observer = _OBSERVER.get()
    began = time.monotonic()
    with subprocess.Popen(argv, cwd=work, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, encoding="utf-8",
                          errors="replace", env=environment,
                          start_new_session=sys.platform != "win32") as running:
        try:
            stdout, stderr = running.communicate(timeout=limit)
        except subprocess.TimeoutExpired as expired:
            _stop(running)
            if observer is not None:
                observer(Compiled(rel, time.monotonic() - began, None, limit))
            raise CompileTimeout(rel, limit, argv) from expired
        except BaseException:
            _stop(running)
            raise
    done = subprocess.CompletedProcess(argv, running.returncode, stdout, stderr)
    if observer is not None:
        observer(Compiled(rel, time.monotonic() - began, done.returncode, limit))
    return done


def _compile_waves(found: Prover, work: Path,
                   ordered: list[list[Path]]) -> list[Failure]:
    """Sources already put in dependency order, every failure kept.

    Failures accumulate rather than stopping the run, because a mutation inside a
    definition several proofs read is refused by each of them and the reader wants to
    know which. A failure is a nonzero exit; a run a signal ended raises
    `CompileSignalled` instead and stops the waves, as a run stopped at its limit does,
    since a prover killed for want of memory has said nothing about the source.
    """
    out: list[Failure] = []
    for wave in ordered:
        for source in wave:
            done = _exited(work, source, compile_one(found, work, source))
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
    A compile a signal ended raises `CompileSignalled`, as `_compile_waves` does.
    """
    done = _exited(work, harness, compile_one(found, work, harness))
    if done.returncode != 0:
        return [], (done.stderr or done.stdout).strip()
    lines = _quoted(done.stdout)
    if not lines:
        return [], ("the harness compiled and printed no quoted vector; it must end "
                    "in a `Compute` over a `list string`")
    return lines, ""


def properties(found: Prover, work: Path, harness: Path) -> Drawn:
    """Run the randomized harness, and read what it decided as `drawn_sets` does."""
    return drawn_sets(compile_one(found, work, harness))


def drawn_sets(done: subprocess.CompletedProcess[str]) -> Drawn:
    """What one compile of the randomized harness decided: how many property sets
    passed, how many failed, and the first counterexample where one did; or, where it
    decided none, no set passed or failed, the reason why, and how the compile ended.

    QuickChick runs a property at compile time and prints its verdict, so the prover's
    own stdout is the result: `+++ Passed` per set, `*** Failed` with the drawn
    counterexample under it, unshrunk, `forAll` shrinking nothing. A set a draw refuted
    is read as refuted however the compile ended after it. Short of one, a compile that
    failed decided no set, even where sets ahead of the failure passed, the sets after it
    never having run, and neither did one that printed no verdict: neither is read as a
    set that passed, an empty run being the vacuous pass every floor in this repository
    exists to catch.

    How it failed is read off the report `_UNFINISHED` names. A set's program that built
    and ended on an exception nothing caught, `Exited with status N` for N from 1 to 125
    with OCaml's `Fatal error: exception E` after it, crashed, unless E is Out_of_memory
    or Stack_overflow. Memory or stack running out, a signal, read as `Killed (N)`,
    `Stopped (N)`, N of 128 and over or GNU time's `Command terminated by signal`, a
    program or `time` that could not run, N of 126 or 127, and any status this reader
    cannot classify each decide nothing about the subject, and read as unanswered, as
    does a prover run a signal ended, which `_compile_waves` and `vectors` raise as
    `CompileSignalled`. A harness that did not build, its Rocq or, reported as `Could
    not compile test program`, its extracted OCaml, decided nothing: a mutant no draw ran
    against and a baseline that is none, as the walk harness's is.
    """
    said = done.stdout + done.stderr
    passed = said.count("+++ Passed")
    failed = said.count("*** Failed")
    if failed:
        return Drawn(passed, failed, _first(said, ""), DRAWN_DECIDED)
    if done.returncode < 0:
        return Drawn(0, 0, f"the prover compiling it was ended by "
                           f"{signal_named(-done.returncode)}, which decides nothing about "
                           "the subject", DRAWN_UNANSWERED)
    if done.returncode != 0:
        unfinished = _UNFINISHED.search(said)
        if unfinished:
            ended, why = _unfinished(said, unfinished)
            return Drawn(0, 0, why, ended)
        error = _first(said, "")
        return Drawn(0, 0, f"it did not build: {error}" if error else "it did not build",
                     DRAWN_NOTHING)
    if not passed:
        return Drawn(0, 0, "it compiled and printed no verdict line", DRAWN_NOTHING)
    return Drawn(passed, 0, "", DRAWN_DECIDED)


def _unfinished(said: str, report: re.Match[str]) -> tuple[str, str]:
    """How a drawn set whose program built did not finish, read from QuickChick's report
    of it and what follows: `DRAWN_CRASHED` or `DRAWN_UNANSWERED`, and the reason, naming
    the set, as the last notice ahead of the report and the line the prover stopped at
    name it, and QuickChick's own report line."""
    ahead, after = said[:report.start()], said[report.end():]
    named = [m.group("set") for m in _QUICKCHECKING.finditer(ahead)]
    lines = [m.group("line") for m in _LOCATED.finditer(ahead)]
    which = " ".join([*([f"`{named[-1][:120]}`"] if named else []),
                      *([f"at line {lines[-1]}"] if lines else [])])
    program = f"the program of the drawn set {which}" if which else "a drawn set's program"
    line = report.group("said")[:200]
    nothing = "which decides nothing about the subject"
    if report.group("signalled"):
        how = report.group("signalled").lower()
        return DRAWN_UNANSWERED, f"{program} was {how} by a signal, {nothing}: {line}"
    code = int(report.group("status"))
    terminated = _TERMINATED.search(after)
    if terminated or code >= 128:
        signal_number = terminated.group("signal") if terminated else str(code - 128)
        return DRAWN_UNANSWERED, (f"{program} was ended by signal {signal_number}, "
                                  f"{nothing}: {line}")
    if code in (126, 127):
        return DRAWN_UNANSWERED, (f"{program} or the `time` running it could not run, "
                                  f"{nothing}: {line}")
    thrown = _EXCEPTION.search(after)
    if thrown is None or not 1 <= code <= 125:
        return DRAWN_UNANSWERED, (f"{program} exited with status {code}, which this "
                                  "reader cannot classify, so it decides nothing about "
                                  f"the subject: {line}")
    exception = f"{thrown.group('name')}{thrown.group('args')}"[:120]
    if thrown.group("name").rsplit(".", 1)[-1] in _EXHAUSTION:
        return DRAWN_UNANSWERED, (f"{program} exited with status {code} on {exception}, "
                                  f"its memory or stack running out, {nothing}: {line}")
    return DRAWN_CRASHED, (f"{program} exited with status {code} on the uncaught "
                           f"exception {exception}, so the sets after it in the harness "
                           "did not run")


def seed(harness: Path) -> str | None:
    """The seed the randomized harness fixes QuickChick's random state at, or None where
    it fixes none, fixes it other than once, or fixes it ahead of a sentence that
    Requires QuickChick, whose loading states QuickChick's own seed over it.

    Read with the comments blanked by the shared lexer, so a commented-out sentence
    fixes nothing."""
    try:
        text = proofs.strip_comments(harness.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None
    found = list(_SEED.finditer(text))
    loads = [m.end() for m in _REQUIRES_QUICKCHICK.finditer(text)]
    if len(found) != 1 or (loads and found[0].start() < loads[-1]):
        return None
    return str(found[0].group(1))


def walks(found: Prover, work: Path, harness: Path) -> tuple[list[Walk], str]:
    """Run the exhaustive harness: each property set it walked, or why there are none.

    The harness loads Stdlib alone and ends in a `Compute` over a `list string`, one
    entry per set, `name points premise refuted first`, the last the walk-order position,
    from 0, of the first point that refutes, `-` where none does. A harness that did not
    compile, printed no entry, printed one this cannot read, or printed counts that
    disagree with each other is an error rather than a set that held, so a walk that
    never ran, or ran and was misread, reads as no verdict.
    """
    lines, said = vectors(found, work, harness)
    if said:
        return [], said
    out: list[Walk] = []
    for line in lines:
        parts = line.rsplit(" ", 4)
        numbers = parts[1:]
        if (len(parts) != 5 or not all(_COUNT.fullmatch(n) for n in numbers[:3])
                or not (_COUNT.fullmatch(numbers[3]) or numbers[3] == "-")):
            return [], (f"the walk harness printed {line!r}, which is not "
                        "`name points premise refuted first`")
        walk = Walk(name=parts[0], points=int(numbers[0]), premise=int(numbers[1]),
                    refuted=int(numbers[2]),
                    first=None if numbers[3] == "-" else int(numbers[3]))
        if not (walk.premise <= walk.points and walk.refuted <= walk.points
                and (walk.first is None) == (walk.refuted == 0)
                and (walk.first is None or walk.first < walk.points)):
            return [], (f"the walk harness printed {line!r}, whose counts disagree: the "
                        "premise and refuted counts are at most the points, and a first "
                        "position inside the domain is printed exactly where a point "
                        "refutes")
        out.append(walk)
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
    """The first line that says something a reader wants, for a one-line verdict: a
    bare `Error:`, which the prover prints over a message of several lines, with the
    message's first line after it."""
    lines = [line.strip() for line in text.splitlines()]
    for n, line in enumerate(lines):
        if line.startswith(("*** Failed", "Error", "Failed")):
            message = [after for after in lines[n + 1:] if after][:1] if line == "Error:" else []
            return " ".join([line, *message])[:200]
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
