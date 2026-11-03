# SPDX-License-Identifier: Apache-2.0
"""Replay bounded Vela mathematical elaboration through Menhir and the Rocq kernel.

This qualifies generated CIC terms, never checked parsing, source correspondence,
the production frontend or machine-code admission. Each attempt retains its own
native sources, syntax, generated libraries, process logs and exact identities.
"""

import copy
import hashlib
import json
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from filelock import FileLock

from vos import env, proofenv, vela_elaborate, vela_parser
from vos.atomic import atomic_path
from vos.vela import VelaError

TIMEOUT = 120
EXAMPLE = "tools/vela/examples/dependent.vela"


@dataclass(frozen=True)
class Fixture:
    name: str
    source: bytes
    expected: str = "accepted"


def fixtures(example: bytes) -> tuple[Fixture, ...]:
    """Independent source examples and well-formed semantic negative neighbors."""
    positives = (
        ("fresh-polymorphic-calls", """module GenericReplay;
definition T Identity<T>(T value) = value;
definition Nat Number() = Identity(3);
definition bool Flag() = Identity(true);
definition Nat Explicit() = Identity::<Nat>(4);
"""),
        ("dependent-vector-lookup", """module VectorReplay;
definition Vec<T,n> Copy<T, ghost Nat n>(Vec<T,n> xs) = xs;
definition Vec<Nat,2> Two() = VCons(7, VCons(8, VNil::<Nat>()));
definition Vec<Nat,0> Empty() = Copy(VNil::<Nat>());
definition Nat Lookup() = At(Copy(Two()), FSucc(FZero::<0>()));
lemma Selected(): At(Two(), FSucc(FZero::<0>())) == 8 proof { return Refl(8); }
"""),
        ("product-projection-conversion", """module ProductReplay;
definition Nat Left() = Fst((7, true));
definition bool Right() = Snd((7, true));
lemma LeftValue(): Fst((7, true)) == 7 proof { return Refl(7); }
lemma RightValue(): Snd((7, true)) == true proof { return Refl(true); }
"""),
        ("higher-order-inference", """module InferenceReplay;
definition U Apply<T,U>(Fn(T value) -> U f, T x) = f(x);
definition Nat Increment() = Apply(x => x + 1, 2,);
Nat Arrow(Nat value,) => Apply((x) => x + 1, value,);
"""),
        ("dependent-type-family", """module FamilyReplay;
definition type[family(n)] Keep(Fn(Nat index) -> Type family, Nat n,
    type[family(n)] value) = value;
definition Nat Use() = Keep((Nat index) => type Nat, 0, 7);
"""),
        ("proof-composition", """module ProofReplay;
lemma Same<T>(T x): x == x proof {
    let p = Refl(x);
    return Trans(p, Symm(p));
}
definition Eq<T,(x),(y)> KeepProof<T, ghost T x, ghost T y>(Eq<T,(x),(y)> p) = p;
"""),
        ("definitional-conversion", """module ConversionReplay;
definition Nat Twice(Nat value) = value + value;
lemma Computed(): Twice(2) == 4 proof { return Refl(4); }
"""),
        ("canonical-unit-and-labeled-generics", """module NamedReplay;
definition T Identity<T>(T value) = value;
definition Unit Empty() = Identity::<Unit>(value: ());
definition Nat Value() = Identity(value: 7,);
lemma Same(): Identity(value: 7) == 7 proof { return Refl(7); }
"""),
        ("declared-dependent-callable-labels", """module CallableReplay;
alias Reader<T> = Fn(Nat count, Vec<T,count> values) -> Vec<T,count>;
definition Reader<Nat> Preserve() = (length, storage) => storage;
definition Vec<Nat,1> Singleton() = VCons(7, VNil::<Nat>());
definition Vec<Nat,1> Use() = Preserve()(count: 1, values: Singleton());
definition Vec<Nat,count> Keep(Nat count, Vec<Nat,count> values) = values;
definition Vec<Nat,1> Partial() = Keep(count: 1)(values: Singleton());
definition U Apply<T,U>(Fn(T input) -> U function, T value) = function(input: value);
definition Nat Higher() = Apply(implementation => implementation + 1, value: 41);
"""),
    )
    negatives = (
        ("wrong-call-domain", "definition Nat Identity(Nat x) = x; "
         "definition Nat Wrong() = Identity(true);", "type"),
        ("unequal-vector-index", "definition Vec<Nat,0> Wrong() = VCons(1, VNil::<Nat>());", "type"),
        ("out-of-bounds-index", "definition Nat Wrong() = At(VNil::<Nat>(), FZero::<0>());", "type"),
        ("false-equality-proof", "lemma Wrong(): 1 == 2 proof { return Refl(1); }", "type"),
        ("non-proposition", "lemma Wrong(): 3 proof { return 3; }", "type"),
        ("universe-self-typing", "definition Type Wrong() = type Type;", "type"),
        ("unresolved-inference", "definition _ Unknown() = VNil();", "inference"),
        ("unfinished-proof", "lemma Missing(): 1 == 1;", "unsupported"),
        ("proof-hole", "definition Nat Hole() = ?proof;", "inference"),
        ("unsupported-contract", "definition Nat Contract() requires true = 0;", "unsupported"),
        ("unbound-value", "definition Nat Wrong() = missing;", "name"),
        ("unknown-call-label", "definition Nat Id(Nat value) = value; "
         "definition Nat Wrong() = Id(missing: 1);", "name"),
        ("out-of-order-call-label", "definition Nat Pick(Nat first,Nat second) = first; "
         "definition Nat Wrong() = Pick(second: 1,first: 2);", "name"),
        ("duplicate-call-label", "definition Nat Pick(Nat first,Nat second) = first; "
         "definition Nat Wrong() = Pick(first: 1,first: 2);", "name"),
        ("positional-after-label", "definition Nat Pick(Nat first,Nat second) = first; "
         "definition Nat Wrong() = Pick(first: 1,2);", "name"),
        ("unnamed-callable-label", "definition Nat Use(Fn(Nat) -> Nat function) = function(value: 1);", "name"),
        ("unnamed-builtin-label", "definition Nat Wrong() = Succ(value: 1);", "name"),
        ("implementation-name-not-interface", "definition Fn(Nat published) -> Nat Build() = implementation => implementation; "
         "definition Nat Wrong() = Build()(implementation: 1);", "name"),
        ("labeled-dependent-index-mismatch", "definition Vec<Nat,n> Keep(Nat n,Vec<Nat,n> values) = values; "
         "definition Vec<Nat,0> Wrong() = Keep(n: 1,values: VNil::<Nat>());", "type"),
        ("labeled-false-equality", "definition Nat Id(Nat value) = value; "
         "lemma Wrong(): Id(value: 1) == 2 proof { return Refl(1); }", "type"),
        ("unsupported-use-grade", "definition Nat Graded(Nat value @ 1) = value;", "unsupported"),
        ("unsupported-source-loan", "definition Nat Loan(ref Nat value) = value;", "unsupported"),
    )
    return (Fixture("authored-example", example),
            *(Fixture(name, source.encode()) for name, source in positives),
            *(Fixture(name, ("module NegativeReplay; " + source).encode(), expected)
              for name, source, expected in negatives))


def _sha256(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _write(path: Path, value: object) -> None:
    with atomic_path(path) as pending:
        pending.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8", newline="")


def _opam(arguments: list[str]) -> list[str]:
    return ["opam", "exec", "--switch", proofenv.ROCQ_SWITCH, "--", *arguments]


def _run(arguments: list[str], directory: Path, log: Path,
         steps: list[dict[str, object]], *, source: bytes | None = None) -> str:
    if log.exists():
        log = log.with_name(f"{log.stem}-{len(steps)}{log.suffix}")
    started = time.monotonic()
    row: dict[str, object] = {"command": arguments, "directory": str(directory)}
    try:
        done = subprocess.run(arguments, cwd=directory, input=source, capture_output=True,
                              timeout=TIMEOUT, check=False)
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or b"") + (error.stderr or b"")
        log.write_bytes(output)
        row.update({"status": "timeout", "seconds": round(time.monotonic() - started, 6),
                    "log": str(log), "log_sha256": _sha256(output)})
        steps.append(row)
        raise RuntimeError(f"Vela replay command exceeded {TIMEOUT} seconds") from error
    except OSError as error:
        output = str(error).encode("utf-8")
        log.write_bytes(output)
        row.update({"status": "unavailable", "log": str(log), "log_sha256": _sha256(output)})
        steps.append(row)
        raise
    output = done.stdout + done.stderr
    log.write_bytes(output)
    row.update({"status": "passed" if done.returncode == 0 else "failed", "exit": done.returncode,
                "seconds": round(time.monotonic() - started, 6),
                "log": str(log), "log_sha256": _sha256(output)})
    steps.append(row)
    if done.returncode:
        raise RuntimeError(f"Vela replay command exited {done.returncode}: "
                           + output.decode("utf-8", errors="replace")[-3000:])
    return done.stdout.decode("utf-8")


def _inputs(root: Path) -> dict[str, str]:
    paths = (EXAMPLE, "tools/opam/rocq.lock", "tools/vos/proofenv.py", "tools/vos/env.py",
             "tools/vos/vela_elaborate.py", "tools/vos/vela_ast.py", "tools/vos/vela.py",
             "tools/vos/vela_elaboration_check.py", "tools/vos/atomic.py")
    return {**vela_parser._inputs(root),
            **{name: _sha256((root / name).read_bytes()) for name in paths}}


def _toolchain(root: Path, directory: Path, steps: list[dict[str, object]]) -> dict[str, object]:
    lock = (root / "tools/opam/rocq.lock").read_text(encoding="utf-8")
    if set(re.findall(r'"rocq-core\.([^"\s]+)"', lock)) != {proofenv.ROCQ_VERSION}:
        raise ValueError("Vela replay prover differs from the proof snapshot")
    version = _run(_opam(["rocq", "c", "--version"]), directory,
                   directory / "toolchain.log", steps).strip()
    found = re.search(r"\bversion\s+([^\s]+)", version)
    if found is None or found[1] not in {proofenv.ROCQ_VERSION, proofenv.ROCQ_VERSION.removesuffix(".0")}:
        raise ValueError("Vela replay compiler differs from the locked prover")
    compiler = _run(_opam(["ocamlc", "-version"]), directory,
                    directory / "ocaml.log", steps).strip()
    if compiler != proofenv.OCAML_VERSION:
        raise ValueError("Vela replay OCaml differs from the proof snapshot")
    binary = _run(["opam", "var", "bin", "--switch", proofenv.ROCQ_SWITCH], directory,
                  directory / "tool-path.log", steps).strip()
    binary_dir = Path(binary)
    if not binary_dir.is_absolute():
        raise ValueError("Vela replay tool directory must be absolute")
    return {"switch": proofenv.ROCQ_SWITCH, "rocq": version, "ocamlc": compiler,
            "binary_sha256": {name: _sha256((binary_dir / name).read_bytes())
                              for name in ("rocq", "rocqchk", "ocamlc")}}


def _runtime(directory: Path, steps: list[dict[str, object]]) -> dict[str, object]:
    """Bind the actual runtime roots, including user-contrib and plugin inputs."""
    config = _run(_opam(["rocq", "c", "-config"]), directory,
                  directory / "runtime-config.log", steps)
    where = _run(_opam(["rocqchk", "-where"]), directory,
                 directory / "runtime-where.log", steps).strip()
    listing = _run(_opam(["rocq", "top", "-q", "-quiet"]), directory,
                   directory / "runtime-loadpath.log", steps, source=b"Print LoadPath.\n")
    settings = dict(line.split("=", 1) for line in config.splitlines() if "=" in line)
    if any(key not in settings or not Path(settings[key]).is_absolute()
           for key in ("COQLIB", "COQCORELIB")):
        raise ValueError("Vela replay prover library configuration is unsupported")
    if not where or not Path(where).is_absolute():
        raise ValueError("Vela replay kernel library path is unsupported")
    roots = {Path(settings[key]).resolve() for key in ("COQLIB", "COQCORELIB")}
    roots.add(Path(where).resolve())
    lines = re.sub(r"\n\s+(/)", r" \1", listing).splitlines()
    if not lines or lines[0] != "Installed / Logical Path / Physical path:":
        raise ValueError("Vela replay prover load-path listing is unsupported")
    for line in lines[1:]:
        found = re.fullmatch(r"\s*(?:i\s+)?(?:<>|[\w.]+)\s+(/.+)", line)
        if found is None:
            raise ValueError("Vela replay prover load-path row is unsupported")
        path = Path(found[1]).resolve()
        if path != directory.resolve():
            roots.add(path)
    minimal = sorted(path for path in roots
                     if not any(path != other and path.is_relative_to(other) for other in roots))
    files: dict[str, str] = {}
    for root in minimal:
        if not root.is_dir():
            raise ValueError("Vela replay library root is missing")
        for path in sorted(root.rglob("*")):
            if path.is_symlink() and path.is_dir():
                raise ValueError("Vela replay library has a directory alias")
            if path.is_file():
                files[str(path)] = _sha256(path.read_bytes())
    if not files:
        raise ValueError("Vela replay runtime inventory is empty")
    return {"config": config, "load_path": listing, "files_sha256": files}


def _work_root(root: Path) -> Path:
    directory = env.lane_root(env.lane_of(root)) / "vela-elaboration"
    kind = env.filesystem(directory)
    if not kind or kind in env.CROSS_OS_FILESYSTEMS | env.VOLATILE_FILESYSTEMS:
        raise ValueError("Vela replay outputs require a persistent native filesystem")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _parser_outputs(compiled: vela_parser.Build) -> dict[str, str]:
    outputs = cast("dict[str, str]", compiled.receipt["generated_sha256"])
    current = {name: _sha256((compiled.directory / name).read_bytes())
               for name in (*vela_parser.GENERATED, "vela-parser")}
    if current != outputs:
        raise ValueError("Vela replay parser output changed after its build")
    return current


def _case(compiled: vela_parser.Build, case: Fixture, directory: Path, index: int,
          steps: list[dict[str, object]]) -> dict[str, object]:
    """A parsing failure can never satisfy a semantic negative fixture."""
    stem = f"Case{index:03d}"
    source_path = directory / f"{stem}.vela"
    source_path.write_bytes(case.source)
    parsed = vela_parser.parse_source(compiled, case.source, surface=True)
    syntax_path = directory / f"{stem}.syntax.json"
    _write(syntax_path, parsed)
    row: dict[str, object] = {"name": case.name, "source": str(source_path),
                              "source_sha256": _sha256(case.source), "expected": case.expected,
                              "syntax": str(syntax_path), "syntax_sha256": _sha256(syntax_path.read_bytes())}
    try:
        translated = vela_elaborate.elaborate(case.source, parsed)
    except VelaError as error:
        row.update({"category": error.kind, "line": error.line, "column": error.column,
                    "message": error.message})
        if error.kind != case.expected or case.expected == "accepted":
            raise ValueError(f"Vela replay {case.name}: expected {case.expected}, got {error.kind}") from error
        return row
    if case.expected != "accepted":
        raise ValueError(f"Vela replay {case.name}: expected {case.expected}, source was accepted")
    repeated = vela_elaborate.elaborate(case.source, parsed)
    if translated != repeated:
        raise ValueError(f"Vela replay {case.name}: elaboration is nondeterministic")
    target = directory / f"{stem}.v"
    target.write_text(translated.gallina, encoding="utf-8", newline="")
    _run(_opam(["rocq", "c", "-q", "-R", str(directory), "VelaElaboration", target.name]),
         directory, directory / f"{stem}.compile.log", steps)
    exports = re.findall(r"^Definition (vela_d[0-9]+_[A-Za-z_][A-Za-z0-9_]*)\s*:",
                         translated.gallina, flags=re.MULTILINE)
    if not exports:
        raise ValueError(f"Vela replay {case.name}: no generated exports to audit")
    module = "Vela_" + translated.module.replace(".", "_")
    query = directory / f"{stem}Assumptions.v"
    query.write_text(f"From VelaElaboration Require Import {stem}.\n"
                     + "".join(f"Print Assumptions {stem}.{module}.{name}.\n" for name in exports),
                     encoding="utf-8", newline="")
    assumptions = _run(_opam(["rocq", "c", "-q", "-R", str(directory), "VelaElaboration", query.name]),
                       directory, directory / f"{stem}.assumptions.log", steps)
    if [line.strip() for line in assumptions.splitlines() if line.strip()] != [
            "Closed under the global context"] * len(exports):
        raise ValueError(f"Vela replay {case.name}: generated exports have unqualified assumptions")
    artifact = directory / f"{stem}.vo"
    row.update({"category": "accepted", "module": translated.module,
                "gallina": str(target), "gallina_sha256": _sha256(target.read_bytes()),
                "assumptions": str(query), "assumptions_sha256": _sha256(query.read_bytes()),
                "assumption_exports": exports,
                "library": f"VelaElaboration.{stem}", "vo": str(artifact),
                "vo_sha256": _sha256(artifact.read_bytes())})
    return row


def _observations(rows: list[dict[str, object]], steps: list[dict[str, object]]) -> dict[str, str]:
    files: dict[str, str] = {}
    for row in rows:
        for field in ("source", "syntax", "gallina", "assumptions", "vo"):
            if field in row:
                path = Path(str(row[field]))
                digest = _sha256(path.read_bytes())
                expected = str(row[f"{field}_sha256"])
                if digest != expected:
                    raise ValueError("Vela replay artifact changed during qualification")
                files[str(path)] = digest
    for step in steps:
        path = Path(str(step["log"]))
        digest = _sha256(path.read_bytes())
        if digest != step["log_sha256"]:
            raise ValueError("Vela replay process transcript changed during qualification")
        files[str(path)] = digest
    return files


def qualify(root: Path) -> dict[str, object]:
    """Fresh native syntax/term/kernel replay with no production-language verdict."""
    work = _work_root(root)
    with FileLock(work / "qualification.lock", timeout=1):
        latest = work / "qualification.json"
        latest.unlink(missing_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="replay-", dir=work))
        steps: list[dict[str, object]] = []
        rows: list[dict[str, object]] = []
        attempt: dict[str, object] = {"schema": 1, "scope": "vela-mathematical-elaboration-kernel-replay",
                                      "status": "running", "directory": str(directory),
                                      "steps": steps, "fixtures": rows, "checked_parser": False,
                                      "source_correspondence": False, "production_admission": False}
        _write(directory / "attempt.json", attempt)
        try:
            inputs = _inputs(root)
            tools = _toolchain(root, directory, steps)
            runtime = _runtime(directory, steps)
            compiled = vela_parser.build(root)
            parser_receipt = copy.deepcopy(compiled.receipt)
            outputs = _parser_outputs(compiled)
            attempt.update({"inputs": inputs, "toolchain": tools, "runtime": runtime,
                            "parser": parser_receipt, "parser_outputs": outputs})
            for index, case in enumerate(fixtures(vela_parser.read_source(root / EXAMPLE))):
                rows.append(_case(compiled, case, directory, index, steps))
                _write(directory / "attempt.json", attempt)
            libraries = [str(row["library"]) for row in rows if row["category"] == "accepted"]
            _require(bool(libraries), "Vela replay has no accepted library to kernel-check")
            _run(_opam(["rocqchk", "-R", str(directory), "VelaElaboration", *libraries]),
                 directory, directory / "kernel.log", steps)
            _require(_inputs(root) == inputs and _toolchain(root, directory, steps) == tools
                     and _runtime(directory, steps) == runtime,
                     "Vela replay inputs, toolchain or runtime changed during qualification")
            _require(compiled.receipt == parser_receipt and _parser_outputs(compiled) == outputs
                     and vela_parser._toolchain(root) == parser_receipt["toolchain"],
                     "Vela replay parser identity changed during qualification")
            attempt.update({"status": "passed", "kernel_checked": True,
                            "artifacts_sha256": _observations(rows, steps)})
            _write(directory / "attempt.json", attempt)
            _write(latest, attempt)
        except Exception as error:
            attempt.update({"status": "failed", "kernel_checked": False,
                            "error": f"{type(error).__name__}: {error}"})
            _write(directory / "attempt.json", attempt)
            raise
        else:
            return attempt
