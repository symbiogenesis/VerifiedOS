# SPDX-License-Identifier: Apache-2.0
"""Private Q35j instrument: compile two unchanged Clight source closures."""

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import TypedDict, cast


class Closure(TypedDict):
    sources_sha256: dict[str, str]
    objects_sha256: dict[str, str]
    compile_seconds: float
    upstream_diagnostics: str


class Report(TypedDict, total=False):
    scope: str
    closures: dict[str, Closure]
    statement_sha256: str
    statement_log_sha256: str
    prover: str


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dependency_order(dependencies: dict[str, list[str]], root: Path) -> list[Path]:
    order: list[Path] = []
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(obj: str) -> None:
        if obj in done:
            return
        if obj in visiting:
            raise ValueError(f"dependency cycle: {obj}")
        if obj not in dependencies:
            raise ValueError(f"unresolved native dependency: {obj}")
        visiting.add(obj)
        for dependency in dependencies[obj]:
            visit(dependency)
        visiting.remove(obj)
        done.add(obj)
        order.append(Path(obj).with_suffix(".v"))

    visit(str(root))
    return order


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", type=Path, required=True)
    parser.add_argument("--contained", type=Path, required=True)
    parser.add_argument("--flocq", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--switch", required=True)
    parser.add_argument("--coq-bin", type=Path,
                        help="explicit compatible legacy compiler directory; never a shared-switch change")
    parser.add_argument("--statement-only", action="store_true",
                        help="resume only after validating the completed upstream source/object receipt")
    args = parser.parse_args()
    if not args.output.is_absolute():
        parser.error("output must be absolute")
    out = Path(str(args.output)).resolve()
    if len(out.parts) > 1 and out.parts[1] in {"mnt", "tmp"}:
        parser.error("output must be an absolute guest-native durable lane path")
    out.mkdir(parents=True, exist_ok=True)
    command = ["opam", "exec", f"--switch={args.switch}", "--"]
    compiler = [str(args.coq_bin / "coqc")] if args.coq_bin else ["rocq", "c"]
    dep_tool = [str(args.coq_bin / "coqdep")] if args.coq_bin else ["rocq", "dep"]
    upstream_receipt = out / "upstream-report.json"
    report: Report = (cast(Report, json.loads(upstream_receipt.read_text(encoding="utf-8")))
              if args.statement_only else
              {"scope": "Q35j statement and concrete witness/refusal only", "closures": {}})

    def run(argv: list[str], cwd: Path, log: Path) -> float:
        started = time.monotonic()
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run(command + argv, cwd=cwd, stdout=stream,
                                    stderr=subprocess.STDOUT, check=False)
        if result.returncode:
            raise RuntimeError(f"command exit {result.returncode}: {log}")
        return time.monotonic() - started

    run([*compiler, "--version"], out, out / "prover.log")
    version = (out / "prover.log").read_text(encoding="utf-8")
    if args.statement_only and report["prover"] != version:
        raise ValueError("changed prover")
    report["prover"] = version
    namespaces: list[str] = []
    # The original imports remain unchanged; only logical load paths distinguish
    # the two independent libraries. The proof switch is never selected.
    for name, source, arch, backend in (("Stock", args.stock, "x86_64", "x86"),
                                         ("Contained", args.contained, "riscV", "riscV")):
        stage = out / name
        stage.mkdir(exist_ok=True)
        dirs = ["lib", "common", "cfrontend", arch, "backend"]
        if (source / "security").is_dir():
            dirs.append("security")
        if backend not in dirs:
            dirs.append(backend)
        for directory in dirs:
            target = stage / directory
            target.mkdir(exist_ok=True)
            for path in (source / directory).glob("*.v"):
                shutil.copyfile(path, target / path.name)
        # The two exact Clight sources share the separately selected Flocq
        # dependency. Its identity is recorded along with the source closure.
        flocq = out / "flocq"
        if not flocq.exists():
            shutil.copytree(args.flocq, flocq,
                            ignore=shutil.ignore_patterns("*.vo", "*.vos", "*.vok", "*.glob"))
        loads = ["-R", str(flocq), "Flocq"]
        for directory in dirs:
            loads += ["-R", str(stage / directory), name + "." + directory]
        paths = sorted(stage.rglob("*.v")) + sorted(flocq.rglob("*.v"))
        dep = subprocess.run(command + dep_tool + loads + list(map(str, paths)),
                             cwd=out, capture_output=True, text=True, check=True)
        (out / (name + "-deps.log")).write_text(dep.stderr, encoding="utf-8")
        dependencies: dict[str, list[str]] = {}
        for line in dep.stdout.splitlines():
            if ": " not in line:
                continue
            left, right = line.split(": ", 1)
            targets = left.split()
            if targets and targets[0].endswith(".vo"):
                dependencies[targets[0]] = [p for p in right.split() if p.endswith(".vo")]
        order = dependency_order(dependencies, stage / "cfrontend" / "Clight.vo")
        elapsed = 0.0
        identities = {}
        objects = {}
        for path in order:
            identities[str(path.relative_to(out))] = digest(path)
            if args.statement_only:
                objects[str(path.with_suffix(".vo").relative_to(out))] = digest(path.with_suffix(".vo"))
                continue
            if name == "Contained" and path.is_relative_to(flocq) and path.with_suffix(".vo").exists():
                continue
            elapsed += run([*compiler, "-w", "-all", *loads, str(path)], out,
                           out / (name + "-" + path.stem + ".log"))
        if not args.statement_only:
            objects = {str(path.with_suffix(".vo").relative_to(out)): digest(path.with_suffix(".vo"))
                       for path in order}
        if args.statement_only:
            if (report["closures"][name]["sources_sha256"] != identities or
                    report["closures"][name]["objects_sha256"] != objects):
                raise ValueError(f"changed upstream closure: {name}")
        else:
            report["closures"][name] = {"sources_sha256": identities,
                                     "objects_sha256": objects,
                                     "compile_seconds": elapsed,
                                     "upstream_diagnostics": "-w -all; unchanged legacy sources"}
        namespaces += loads if not namespaces else loads[3:]
    source = Path(__file__).with_name("Bridge.v")
    upstream_receipt.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    authored = out / "statement"
    authored.mkdir(exist_ok=True)
    staged = authored / "Bridge.v"
    shutil.copyfile(source, staged)
    # Authored statement, witnesses and refusal use strict diagnostics.
    run([*compiler, "-w", "@all", *namespaces,
         "-Q", str(authored), "BridgeTrial", str(staged)], out, out / "statement.log")
    report["statement_sha256"] = digest(source)
    report["statement_log_sha256"] = digest(out / "statement.log")
    report["prover"] = (out / "prover.log").read_text(encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"statement compile passed: {out / 'report.json'}")


if __name__ == "__main__":
    main()
