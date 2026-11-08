# SPDX-License-Identifier: Apache-2.0
"""Stage and compile Gallina proofs and QuickChick/vector harnesses in a scratch directory.

Used by [run.py seed](cli/seed.py) and [run.py quickchick](cli/quickchick.py). All staging
and compilation happen under the lane's build root (`work_dir`), never in `proofs/`.

Switch selection by harness:
- Stdlib-only harnesses (`Vectors.v`, `FreezeModel.v`, `KernelVectors.v`, `Walks.v`) compile
  in `VECTOR_SWITCH` (`env.ROCQ_SWITCH`).
- Randomized QuickChick harnesses (`Properties.v`) compile in `QUICKCHICK_SWITCH`.
- The CertiRocq Wasm oracle compiles in `ORACLE_SWITCH` (Rocq 9.1.1 / OCaml 4.14.4).
"""

import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from vos import env, proofs

VECTOR_SWITCH = env.ROCQ_SWITCH
VECTOR_ROCQ_VERSION = env.ROCQ_VERSION

# CertiRocq Wasm oracle switch (`tools/opam/certirocq.lock`).
ORACLE_ROCQ_VERSION = "9.1.1"
CERTIROCQ_VERSION = "0.9.1+9.1"
ORACLE_OCAML_VERSION = "4.14.4"
ORACLE_SWITCH = f"verifiedos-certirocq-0.9.1-ocaml-{ORACLE_OCAML_VERSION}"
ORACLE_CANDIDATE_OCAML_VERSIONS: tuple[str, ...] = ("4.14.4", "5.1.1")


def oracle_candidate_switch(ocaml: str) -> str:
    """Return the CertiRocq candidate switch name for `ocaml`."""
    return f"verifiedos-certirocq-0.9.1-ocaml-{ocaml}"


def oracle_candidate_build(ocaml: str) -> tuple[tuple[str, ...], ...]:
    """Return the `opam` commands to build a CertiRocq candidate switch for `ocaml`."""
    switch = oracle_candidate_switch(ocaml)
    return (
        ("opam", "switch", "create", switch, "--repos=rocq-released,default",
         f"--packages=ocaml-base-compiler.{ocaml}", "--no-switch", "-y"),
        ("opam", "install", f"--switch={switch}", "-y",
         f"ocamlfind.{env.OCAMLFIND_VERSION}", f"rocq-certirocq.{CERTIROCQ_VERSION}"),
    )


# QuickChick switch (`tools/opam/quickchick.lock` and `tools/vos/cli/quickchick.py#RECIPE`).
QUICKCHICK_RECIPE_ROCQ_VERSION = "9.3.0"
QUICKCHICK_RECIPE_SWITCH = (f"verifiedos-quickchick-{QUICKCHICK_RECIPE_ROCQ_VERSION}"
                            f"-ocaml-{env.OCAML_VERSION}")
QUICKCHICK_ROCQ_VERSION = QUICKCHICK_RECIPE_ROCQ_VERSION
QUICKCHICK_SWITCH = QUICKCHICK_RECIPE_SWITCH

PROOFS = "proofs"
HARNESS_DIR = "tools/quickchick"

ENUMERATIVE = "Vectors.v"
RANDOMIZED = "Properties.v"
EXHAUSTIVE = "Walks.v"
FREEZE = "FreezeModel.v"
KERNEL = "KernelVectors.v"
WORK = "gallina"
VECTORS = "vectors.txt"
FREEZE_VECTORS = "freeze-vectors.txt"
FREEZE_MODEL = "freeze-model.txt"

# Entry-point harnesses excluded from `compile_support`.
ENTRY_POINTS: frozenset[str] = frozenset({ENUMERATIVE, RANDOMIZED, EXHAUSTIVE, FREEZE,
                                          KERNEL})

# Support files required only by the randomized/walk entry points (`Properties.v`, `Walks.v`).
RANDOMIZED_SUPPORT: frozenset[str] = frozenset({"IPCProperties.v"})

QUOTED = '"'
COMPILE_TIMEOUT = 900

# Match `Extract Constant newRandomSeed => "(Random.State.make [| <seed> |])".`
_SEED = re.compile(r"\bExtract\s+Constant\s+(?:[\w']+\.)*newRandomSeed\s*=>\s*"
                   r'"\(\s*Random\.State\.make\s*\[\|\s*(\d+)\s*\|\]\s*\)"\s*\.')

# Match `From QuickChick Require ...` or `Require ... QuickChick ...`.
_REQUIRES_QUICKCHICK = re.compile(r"\bFrom\s+QuickChick\s+Require\b"
                                  r"|\bRequire\b(?:(?!\.(?:\s|$)).)*?\bQuickChick\b",
                                  re.DOTALL)


@dataclass(frozen=True)
class Failure:
    """A Gallina source that failed to compile and its compiler diagnostic."""

    source: str
    said: str


@dataclass(frozen=True)
class Prover:
    """Resolved opam switch and `rocq c` argument vector."""

    switch: str
    argv: tuple[str, ...]


@dataclass(frozen=True)
class Compiled:
    """Result record for a single prover invocation."""

    source: str
    seconds: float
    exit: int | None
    limit: float


class CompileTimeout(subprocess.TimeoutExpired):
    """Raised when a prover invocation exceeds its wall-clock timeout."""

    def __init__(self, source: str, timeout: float, cmd: list[str]) -> None:
        super().__init__(cmd, timeout)
        self.source = source


def signal_named(number: int) -> str:
    """Format signal `number` with its symbolic `signal.Signals` name when known."""
    try:
        return f"signal {number} ({signal.Signals(number).name})"
    except ValueError:
        return f"signal {number}"


class CompileSignalled(subprocess.SubprocessError):
    """Raised when a prover invocation is terminated by a signal (such as `SIGKILL` on OOM)."""

    def __init__(self, source: str, number: int) -> None:
        super().__init__(f"the compile of {source} was ended by {signal_named(number)}")
        self.source = source
        self.signal = number


def _exited(work: Path, source: Path,
            done: subprocess.CompletedProcess[str]) -> subprocess.CompletedProcess[str]:
    """Return `done` if the process exited normally, or raise `CompileSignalled` if killed by a signal."""
    if done.returncode < 0:
        raise CompileSignalled(source.relative_to(work).as_posix(), -done.returncode)
    return done


@dataclass(frozen=True)
class Walk:
    """Exhaustive domain-walk result for one property set (`Walks.v`)."""

    name: str
    points: int
    premise: int
    refuted: int
    first: int | None


_COUNT = re.compile(r"[0-9]+")

# Match QuickChick plugin failure lines when an extracted test binary exits nonzero or is signalled.
_UNFINISHED = re.compile(r"^(?:Error:[ \t]*)?(?P<said>\S.*?: (?:Exited with status "
                         r"(?P<status>-?\d+)|(?P<signalled>Killed|Stopped) \(-?\d+\)))"
                         r"[ \t]*$", re.MULTILINE)

# Match uncaught OCaml runtime exceptions on stderr before exit status 2.
_EXCEPTION = re.compile(r"^Fatal error: exception (?P<name>[A-Za-z_][\w'.]*)(?P<args>.*?)"
                        r"[ \t\r]*$", re.MULTILINE)

_EXHAUSTION = frozenset({"Out_of_memory", "Stack_overflow"})
_TERMINATED = re.compile(r"\bCommand terminated by signal (?P<signal>\d+)")
_QUICKCHECKING = re.compile(r"^QuickChecking (?P<set>.*?)[ \t\r]*$", re.MULTILINE)
_LOCATED = re.compile(r'^File "[^"]*", line (?P<line>\d+)', re.MULTILINE)

DRAWN_DECIDED = "decided"
DRAWN_CRASHED = "crashed"
DRAWN_UNANSWERED = "unanswered"
DRAWN_NOTHING = "nothing"


@dataclass(frozen=True)
class Drawn:
    """Result of compiling and running the randomized QuickChick harness (`Properties.v`)."""

    passed: int
    failed: int
    why: str
    ended: str


_EXPORT = re.compile(r"^(\w+)='(.*)';\s*export", re.MULTILINE)


def switch_env(switch: str) -> dict[str, str]:
    """Return the environment variables exported by `opam env --switch=<switch>`.

    Overlaying the target switch's `PATH` and `OCAMLPATH` prevents `ocamlfind` in
    extracted QuickChick programs from seeing the Sail switch's packages exported by
    `vos.env.load`.
    """
    done = subprocess.run(["opam", "env", f"--switch={switch}", "--shell=sh"],
                          capture_output=True, text=True, check=False,
                          stdin=subprocess.DEVNULL, env=env.declining_environment())
    if done.returncode != 0:
        return {}
    return {name: value.replace("'\\''", "'")
            for name, value in _EXPORT.findall(done.stdout)}


def prover(switch: str) -> Prover | None:
    """Return the `rocq c` prover in `switch`, or `None` if not installed."""
    binary = env.opam_root() / switch / "bin" / "rocq"
    if not binary.is_file():
        return None
    return Prover(switch=switch, argv=(str(binary), "c"))


def vector_prover() -> Prover | None:
    """Return the `VECTOR_SWITCH` prover."""
    return prover(VECTOR_SWITCH)


def version(found: Prover) -> str:
    """Return the first line of `rocq --version` for `found`."""
    done = subprocess.run([found.argv[0], "--version"], capture_output=True,
                          encoding="utf-8", errors="replace", check=False)
    return done.stdout.strip().splitlines()[0] if done.stdout.strip() else "unknown"


def stage(root: Path, work: Path) -> Path:
    """Copy `proofs/` and `tools/quickchick/` (excluding compiled `.vo`/`.glob` files) into `work`."""
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


_OBSERVER: ContextVar[Callable[[Compiled], None] | None] = ContextVar("gallina_observer",
                                                                     default=None)


@contextmanager
def observed(callback: Callable[[Compiled], None]) -> Generator[None]:
    """Invoke `callback` after each `compile_one` run within this context."""
    token = _OBSERVER.set(callback)
    try:
        yield
    finally:
        _OBSERVER.reset(token)


def _stop(running: subprocess.Popen[str]) -> None:
    """Kill `running` (and its process group on POSIX) and reap it."""
    if sys.platform != "win32":
        with suppress(ProcessLookupError):
            os.killpg(running.pid, signal.SIGKILL)
        running.wait()
        return
    running.kill()
    running.communicate()


def compile_one(found: Prover, work: Path, source: Path,
                timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    """Compile `source` in `work` with `-Q proofs "" -Q harness ""`, raising `CompileTimeout` on timeout."""
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
    """Compile dependency waves in order and return all `Failure` records."""
    out: list[Failure] = []
    for wave in ordered:
        for source in wave:
            done = _exited(work, source, compile_one(found, work, source))
            if done.returncode != 0:
                out.append(Failure(source=source.name,
                                   said=(done.stderr or done.stdout).strip()))
    return out


def _compile_all(found: Prover, work: Path, sources: list[Path]) -> list[Failure]:
    """Compile `sources` in `Require` dependency order."""
    return _compile_waves(found, work, proofs.waves(sources))


def compile_proofs(found: Prover, work: Path) -> list[Failure]:
    """Compile all `.v` files under `work / PROOFS` in `Require` order."""
    return _compile_all(found, work, sorted((work / PROOFS).glob("*.v")))


def compile_dependents(found: Prover, work: Path, rel: str,
                       moved: list[list[Path]] | None = None) -> list[Failure]:
    """Compile `rel` and its reverse `Require` dependents in `work / PROOFS`."""
    if moved is not None:
        return _compile_waves(found, work, [[s for s in wave if s.parent == work / PROOFS]
                                            for wave in moved])
    sources = sorted((work / PROOFS).glob("*.v"))
    stem = Path(rel).stem
    if stem not in {source.stem for source in sources}:
        return _compile_all(found, work, sources)
    return _compile_waves(found, work, proofs.dependents(sources, stem))


def closure(work: Path, *harnesses: Path) -> list[list[Path]]:
    """Return the `Require` dependency waves of `harnesses` across `work / PROOFS` and `harnesses`'s directory."""
    sources = (sorted((work / PROOFS).glob("*.v"))
               + sorted(harnesses[0].parent.glob("*.v")))
    index = proofs.SourceIndex.read(sources)
    wanted = {s for harness in harnesses for s in index.imports[harness]} | set(harnesses)
    return [[s for s in wave if s in wanted] for wave in index.ordered
            if any(s in wanted for s in wave)]


def closure_dependents(work: Path, rel: str, *harnesses: Path) -> list[list[Path]]:
    """Return the subset of `closure(work, *harnesses)` (excluding `harnesses`) that depends on `rel`."""
    whole = [kept for wave in closure(work, *harnesses)
             if (kept := [s for s in wave if s not in harnesses])]
    return proofs.dependents([s for wave in whole for s in wave], Path(rel).stem) or whole


def compile_closure(found: Prover, work: Path, *harnesses: Path) -> list[Failure]:
    """Compile the `Require` dependencies of `harnesses` (excluding `harnesses` themselves)."""
    return _compile_waves(found, work, [[s for s in wave if s not in harnesses]
                                        for wave in closure(work, *harnesses)])


def is_support(name: str, randomized: bool = False) -> bool:
    """Return whether harness file `name` is shared support (including `RANDOMIZED_SUPPORT` when `randomized` is true)."""
    return name not in ENTRY_POINTS and (randomized or name not in RANDOMIZED_SUPPORT)


def compile_support(found: Prover, work: Path, moved: list[list[Path]] | None = None,
                    randomized: bool = False) -> list[Failure]:
    """Compile shared support files in `work / "harness"`."""
    if moved is not None:
        return _compile_waves(found, work, [[s for s in wave if s.parent == work / "harness"
                                             and is_support(s.name, randomized)]
                                            for wave in moved])
    shared = [p for p in sorted((work / "harness").glob("*.v"))
              if is_support(p.name, randomized)]
    return _compile_all(found, work, shared)


def vectors(found: Prover, work: Path, harness: Path) -> tuple[list[str], str]:
    """Compile `harness` and extract double-quoted vector strings from its `Compute` stdout."""
    done = _exited(work, harness, compile_one(found, work, harness))
    if done.returncode != 0:
        return [], (done.stderr or done.stdout).strip()
    lines = _quoted(done.stdout)
    if not lines:
        return [], ("the harness compiled and printed no quoted vector; it must end "
                    "in a `Compute` over a `list string`")
    return lines, ""


def properties(found: Prover, work: Path, harness: Path) -> Drawn:
    """Compile the randomized QuickChick `harness` and classify its output."""
    return drawn_sets(compile_one(found, work, harness))


def drawn_sets(done: subprocess.CompletedProcess[str]) -> Drawn:
    """Classify QuickChick compile output into `DRAWN_DECIDED`, `DRAWN_CRASHED`, `DRAWN_UNANSWERED`, or `DRAWN_NOTHING`."""
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
    """Classify an unfinished QuickChick test binary execution (`DRAWN_CRASHED` vs `DRAWN_UNANSWERED`)."""
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
    """Return the fixed `newRandomSeed` value in `harness` if declared once after all `QuickChick` imports."""
    try:
        text = proofs.strip_comments(harness.read_text(encoding="utf-8"))
    except OSError, UnicodeDecodeError:
        return None
    found = list(_SEED.finditer(text))
    loads = [m.end() for m in _REQUIRES_QUICKCHICK.finditer(text)]
    if len(found) != 1 or (loads and found[0].start() < loads[-1]):
        return None
    return str(found[0].group(1))


def walks(found: Prover, work: Path, harness: Path) -> tuple[list[Walk], str]:
    """Compile and parse the exhaustive domain-walk `harness` (`name points premise refuted first`)."""
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
    """Return diagnostic lines for any `Walk` with refutations, an empty domain, or a vacuous premise."""
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
    """Return the first `*** Failed`, `Error`, or `Failed` line in `text` (joining a bare `Error:` with the next line)."""
    lines = [line.strip() for line in text.splitlines()]
    for n, line in enumerate(lines):
        if line.startswith(("*** Failed", "Error", "Failed")):
            message = [after for after in lines[n + 1:] if after][:1] if line == "Error:" else []
            return " ".join([line, *message])[:200]
    return fallback


def _quoted(text: str) -> list[str]:
    """Return all double-quoted substrings in `text` in order."""
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
    """Write `lines` to `target` with LF line endings."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return target


def work_dir(lane_root: Path) -> Path:
    """Return (and create) the Gallina staging directory under `lane_root`."""
    path = lane_root / WORK
    path.mkdir(parents=True, exist_ok=True)
    return path


def emit(root: Path, work: Path, out: list[str],
         harness: str = ENUMERATIVE) -> list[str] | None:
    """Stage proofs and harnesses into `work`, compile proofs and support files, and return `harness`'s vectors."""
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
