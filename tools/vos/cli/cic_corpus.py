#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Export and verify CIC feature reports over the compiled proof corpus.

- `report`: queries the pinned Rocq over the proof gate's staged objects in
  `<lane_root>/proof-gate/` for each symbol's transitive dependency closure,
  declaration facts, and printed term, and writes `out/cic-corpus-report.json`
  ([cic-checker-qualification.md](../../../docs/assurance/cic-checker-qualification.md)).
- `check`: re-verifies an existing report's freshness against the current checkout,
  portable proof receipt, staged objects, and exporter digests.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import cast

from vos import cic_corpus, env, proofaudit, receipts
from vos.cli import Table, dispatch
from vos.cli import proofs as proofs_cli
from vos.corpus import find_root

REPORT = "out/cic-corpus-report.json"
FORMAT = "verifiedos-cic-corpus-feature-report"
SCHEMA = 1

# Per-query captured output ceiling in bytes.
MAX_QUERY_BYTES = 64 * 1024 * 1024

# Exporter and proof-gate files hashed into the report's provenance.
EXPORTER_FILES: tuple[str, ...] = (
    "tools/vos/cic_corpus.py", "tools/vos/cli/cic_corpus.py",
    "tools/vos/proofaudit.py", "tools/vos/proofs.py", "tools/vos/prooflex.py",
    "tools/vos/cli/proofs.py",
)

REPLAY: tuple[str, ...] = (
    "python tools/run.py proofs",
    "python tools/run.py cic-corpus report",
    "python tools/run.py cic-corpus check --report out/cic-corpus-report.json",
)


def _query(work: Path, name: str, text: str, *, bound: int) -> str | None:
    """Run one Rocq query against `work`'s compiled proof objects; return None if output exceeds `bound`."""
    scratch = work / "cic-corpus-query"
    scratch.mkdir(parents=True, exist_ok=True)
    source = scratch / f"{name}.v"
    source.write_text(text, encoding="utf-8", newline="")
    answer = scratch / f"{name}.out"
    try:
        with answer.open("wb") as stream:
            done = subprocess.run(
                [*env.rocq_command(), "-q", "-Q", str(work / proofs_cli.PROOFS), "",
                 str(source)],
                cwd=work, stdout=stream, stderr=subprocess.PIPE, check=False)
        said = done.stderr.decode("utf-8", errors="replace").strip()
        if done.returncode or said:
            raise cic_corpus.ParseError(
                f"{name} query exited {done.returncode}: {said[:2000] or 'no diagnostic'}")
        if answer.stat().st_size > bound:
            return None
        return answer.read_text(encoding="utf-8")
    finally:
        answer.unlink(missing_ok=True)


def _reading_query(module: str, names: list[str], *, bodies: bool) -> str:
    lines = [f"Require {module}.\n", cic_corpus.QUERY_SETTINGS]
    for name in names:
        if cic_corpus.QUALIFIED.fullmatch(name) is None:
            raise cic_corpus.ParseError(f"invalid symbol name {name!r}")
        if bodies:
            lines += [f'Goal True. Proof. idtac "{cic_corpus.MARKER}{name}". Abort.\n',
                      f"Print {name}.\n"]
        else:
            lines += [f'Goal True. Proof. idtac "{cic_corpus.MARKER}{name}|deps". Abort.\n',
                      f"Print All Dependencies {name}.\n",
                      f'Goal True. Proof. idtac "{cic_corpus.MARKER}{name}|about". Abort.\n',
                      f"About {name}.\n"]
    return "".join(lines)


def _module_report(work: Path, source: Path, stems: set[str], bound: int) -> tuple[
        dict[str, object], list[cic_corpus.Constant], dict[str, int]]:
    """Query and classify all constants in one proof module."""
    stem = source.stem
    listed = _query(work, f"Inventory_{stem}", proofaudit.inventory_query(stem),
                    bound=bound)
    if listed is None:
        raise cic_corpus.ParseError(f"{stem}'s symbol inventory exceeded {bound} bytes")
    inventory = proofaudit.inventory(listed, stem)
    names = [symbol["name"] for symbol in inventory]
    facts: dict[str, str] = {}
    if names:
        answered = _query(work, f"Facts_{stem}", _reading_query(stem, names, bodies=False),
                          bound=bound)
        if answered is None:
            raise cic_corpus.ParseError(
                f"{stem}'s declaration and dependency answers exceeded {bound} bytes")
        facts = cic_corpus.blocks(
            answered, [f"{name}|{kind}" for name in names for kind in ("deps", "about")])
    bodies: dict[str, str] | None = None
    if names:
        printed = _query(work, f"Bodies_{stem}", _reading_query(stem, names, bodies=True),
                         bound=bound)
        bodies = None if printed is None else cic_corpus.blocks(printed, names)
    constants: list[cic_corpus.Constant] = []
    for symbol in inventory:
        name = symbol["name"]
        constants.append(cic_corpus.classify(
            name, symbol["type"], cic_corpus.parse_about(facts[f"{name}|about"]),
            cic_corpus.parse_dependencies(facts[f"{name}|deps"]),
            None if bodies is None else bodies[name]))
    foreign: dict[str, int] = {}
    records: list[dict[str, object]] = []
    for constant in constants:
        entry: dict[str, object] = {
            "name": constant.name, "kind": constant.kind, "opacity": constant.opacity,
            "universes": constant.universes,
            "term_reading": "printed" if constant.body_printed else "unavailable",
            "features": constant.features, "type": constant.type}
        split: dict[str, object] = {}
        reached: set[str] = set()
        for key, members in constant.dependencies.items():
            local, outside = cic_corpus.local_names(members, stems)
            reached.update(outside)
            split[key] = {"total": len(members), "corpus": local,
                          "foreign": len(outside)}
        for name in reached:
            foreign[name] = foreign.get(name, 0) + 1
        entry["dependencies"] = split
        records.append(entry)
    report: dict[str, object] = {
        "source_declarations": cic_corpus.source_declarations(
            source.read_text(encoding="utf-8")),
        "term_reading": "printed" if bodies is not None else "unavailable",
        "foreign_dependencies": dict(sorted(foreign.items())),
        "constants": records}
    return report, constants, foreign


def _object(path: Path) -> dict[str, object]:
    """Load a JSON object from `path`."""
    loaded: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError(f"{path} is not a JSON object")
    return cast("dict[str, object]", loaded)


def _freshness(root: Path, work: Path) -> dict[str, object]:
    """Check whether this lane's compiled objects match the checkout's proofs and portable receipt."""
    findings: list[str] = []
    portable = root / proofs_cli.RECEIPT
    try:
        record = _object(portable)
    except (OSError, TypeError, ValueError) as error:
        return {"verdict": "stale", "findings": [f"portable proof receipt: {error}"]}
    inputs = record.get("inputs")
    outputs = record.get("outputs")
    if not isinstance(inputs, dict) or not isinstance(outputs, dict):
        return {"verdict": "stale", "findings": ["the receipt carries no input manifest"]}
    sources = sorted((root / proofs_cli.PROOFS).glob("*.v"))
    live = receipts.snapshot(root, sources)
    recorded = {name: value for name, value in inputs.items()
                if isinstance(name, str) and name.startswith(proofs_cli.PROOFS + "/")}
    if live != recorded:
        findings.append("the checkout's proof sources differ from the receipt's inputs")
    staged = [work / proofs_cli.PROOFS / source.name for source in sources]
    objects: dict[str, str] = {}
    stale_objects: list[str] = []
    try:
        if receipts.snapshot(work, staged) != recorded:
            findings.append("the staged proof sources differ from the receipt's inputs")
        objects = receipts.snapshot(work, (path.with_suffix(".vo") for path in staged))
        stale_objects = sorted(
            path.name for path in staged
            if path.with_suffix(".vo").stat().st_mtime < path.stat().st_mtime)
    except OSError as error:
        findings.append(f"this lane has no complete staged compile: {error}")
    if stale_objects:
        findings.append(f"{len(stale_objects)} staged object(s) are older than the "
                        f"source beside them, first {stale_objects[0]}")
    if record.get("status") != "passed" or record.get("kernel_recheck") != "passed":
        findings.append("the receipt carries no successful proof verdict")
    differing = sorted(name for name, digest in objects.items()
                       if outputs.get(name) != digest)
    return {"verdict": "stale" if findings else "current", "findings": findings,
            "proof_receipt": receipts.digest(portable),
            "proof_sources": recorded,
            "lane_objects": objects,
            "objects_matching_recorded_run": len(objects) - len(differing),
            "objects_differing_from_recorded_run": differing}


def _exporter(root: Path) -> dict[str, object]:
    compiler = Path(env.rocq_command()[0]).resolve()
    done = subprocess.run([*env.rocq_command(), "--version"], capture_output=True,
                          text=True, encoding="utf-8", check=False)
    return {"files": receipts.snapshot(root, (root / name for name in EXPORTER_FILES)),
            "rocq_pin": env.ROCQ_VERSION,
            "rocq_version": done.stdout.strip(),
            "rocq_path": str(compiler), "rocq_sha256": receipts.digest(compiler)}


def _build(root: Path, bound: int, only: str | None) -> dict[str, object]:
    work = proofs_cli.workspace(root)
    sources = sorted((root / proofs_cli.PROOFS).glob("*.v"))
    if bool(only):
        sources = [source for source in sources if only in source.name]
    if not sources:
        raise cic_corpus.ParseError("no proof source matched, so there is nothing to read")
    stems = {source.stem for source in sources}
    modules: dict[str, object] = {}
    every: list[cic_corpus.Constant] = []
    reached: dict[str, int] = {}
    for source in sources:
        report, constants, foreign = _module_report(work, source, stems, bound)
        modules[source.name] = report
        every.extend(constants)
        for name, count in foreign.items():
            reached[name] = reached.get(name, 0) + count
        print(f"  {source.name}: {len(constants)} symbol(s)", flush=True)
    return {
        "format": FORMAT, "schema": SCHEMA,
        "subject": "the proof sources this checkout carries, as this lane compiled them",
        "predicates": [
            "a constant is a symbol Rocq's own Search enumerated inside its module, "
            "with both search filters disabled",
            "a dependency is a name Print All Dependencies placed under one of its "
            "four headings, so the closure is transitive and reaches through Qed bodies",
            "a term feature is a declared lexical predicate over the declaration Print "
            "wrote under Set Printing All; vos/cic_corpus.py states each one and the "
            "direction it errs in",
            "no-transparent-dependency names a constant whose closure holds no "
            "transparent constant, which is the only conversion statement this report "
            "makes; the positive case is not decided here",
        ],
        "replay": list(REPLAY),
        "freshness": _freshness(root, work),
        "exporter": _exporter(root),
        "totals": cic_corpus.totals(every),
        "foreign_dependencies": dict(sorted(reached.items())),
        "modules": modules,
    }


def _report(args: argparse.Namespace) -> int:
    root = find_root()
    target = Path(args.out) if args.out else root / REPORT
    try:
        payload = _build(root, args.max_bytes, args.only)
    except (OSError, ValueError, KeyError) as error:
        print(f"FAIL cic-corpus: {error}")
        return 1
    receipts.write(target, payload)
    freshness = cast("dict[str, object]", payload["freshness"])
    totals = cast("dict[str, int]", payload["totals"])
    print(f"{'ok' if freshness['verdict'] == 'current' else 'FAIL'} cic-corpus: "
          f"{totals['constants']} symbol(s) over {len(cast('dict[str, object]', payload['modules']))} "
          f"module(s); evidence: {target}; freshness: {freshness['verdict']}")
    for finding in cast("list[str]", freshness["findings"]):
        print(f"  {finding}")
    return 0 if freshness["verdict"] == "current" else 1


def _check(args: argparse.Namespace) -> int:
    root = find_root()
    target = Path(args.report) if args.report else root / REPORT
    try:
        payload = _object(target)
        stated = (payload.get("format"), payload.get("schema"))
        current = _freshness(root, proofs_cli.workspace(root))
        exporter = _exporter(root)
    except (OSError, TypeError, ValueError) as error:
        print(f"FAIL cic-corpus: {error}")
        return 1
    if stated != (FORMAT, SCHEMA):
        print(f"FAIL cic-corpus: {target} is not this exporter's report")
        return 1
    findings = list(cast("list[str]", current["findings"]))
    if payload.get("exporter") != exporter:
        findings.append("the exporter or the prover has changed since this report")
    recorded = cast("dict[str, object]", payload.get("freshness") or {})
    if recorded.get("proof_sources") != current.get("proof_sources"):
        findings.append("the report was taken over different proof sources")
    if recorded.get("lane_objects") != current.get("lane_objects"):
        findings.append("the objects this report was read from are no longer the ones "
                        "in this lane")
    print(f"{'ok' if not findings else 'FAIL'} cic-corpus: {target} "
          f"{'still describes' if not findings else 'no longer describes'} this checkout")
    for finding in findings:
        print(f"  {finding}")
    return 0 if not findings else 1


TABLE: Table = {
    "report": (_report, "read the compiled corpus and write the feature report"),
    "check": (_check, "re-decide an existing report's freshness against this checkout"),
}


def _flags(name: str, parser: argparse.ArgumentParser) -> None:
    if name == "report":
        parser.add_argument("--out", help=f"where to write the report (default {REPORT})")
        parser.add_argument("--only", help="read only the proof sources whose name contains this")
        parser.add_argument("--max-bytes", type=int, default=MAX_QUERY_BYTES,
                            help="bound on one query's captured output")
    else:
        parser.add_argument("--report", help=f"the report to re-decide (default {REPORT})")


def main(argv: list[str] | None = None) -> int:
    return dispatch(__doc__, TABLE, argv, _flags, prog="run.py cic-corpus")


if __name__ == "__main__":
    sys.exit(main())
