# SPDX-License-Identifier: Apache-2.0
"""Research receipts bind actual inputs and preserve typed command failures."""

import hashlib
import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

from tests.harness import Case, ensure
from vos import static_memory_corpus as witnesses
from vos.cli import static_memory as cli


def _invoke(argv: list[str]) -> tuple[int, dict[str, Any]]:
    output = StringIO()
    with redirect_stdout(output):
        code = cli.main([*argv, "--json"])
    return code, json.loads(output.getvalue())


def _corpus_receipt() -> None:
    name = witnesses.corpus("fixture")[0]["name"]
    code, report = _invoke(["corpus", "--case", name])
    ensure(code == 0 and len(report["cases"]) == 1, "named corpus selection")
    root = Path(__file__).resolve().parents[2]
    for name, digest in report["sources_sha256"].items():
        ensure(digest == hashlib.sha256((root / name).read_bytes()).hexdigest(),
               "receipt must identify working-tree bytes")
    ensure(report["cases"][0]["timeline"], "receipt requires actual event accounting")


def _unknown_case() -> None:
    code, report = _invoke(["compare", "--case", "missing-witness"])
    ensure(code == 2 and report["status"] == "malformed-or-unreadable",
           "bad selection must not fall back to the whole corpus")


def _candidate_identity_and_refusal() -> None:
    raw = witnesses.corpus("fixture")[0]
    with tempfile.TemporaryDirectory() as directory:
        contract = Path(directory) / "contract.json"
        candidate = Path(directory) / "candidate.json"
        contract.write_text(json.dumps(raw), encoding="utf-8")
        candidate.write_text('[{"id":"absent","arena":"absent","base":0}]',
                             encoding="utf-8")
        code, report = _invoke(["check", "--contract", str(contract),
                                "--candidate", str(candidate)])
        ensure(code == 1 and not report["cases"][0]["accepted"], "invalid candidate refused")
        for path, key in ((contract, "contract_sha256"), (candidate, "candidate_sha256")):
            ensure(report[key] == hashlib.sha256(path.read_bytes()).hexdigest(),
                   "exact supplied input binding")
        ensure(json.loads(contract.read_text(encoding="utf-8")) == raw,
               "checking must not rewrite the standing contract")


def _malformed_input() -> None:
    with tempfile.TemporaryDirectory() as directory:
        contract = Path(directory) / "contract.json"
        contract.write_text("{", encoding="utf-8")
        code, report = _invoke(["check", "--contract", str(contract)])
        ensure(code == 2 and report["status"] == "malformed-or-unreadable",
               "malformed input is not a candidate infeasibility result")
        raw = witnesses.corpus("fixture")[0]
        raw["requests"] = [{"size": 1}]
        contract.write_text(json.dumps(raw), encoding="utf-8")
        code, report = _invoke(["corpus", "--contract", str(contract)])
        ensure(code == 2 and report["status"] == "malformed-or-unreadable",
               "malformed diagnostic metadata requires a typed failure")


def _comparison_cutoff_and_replay() -> None:
    code, report = _invoke(["compare", "--case", "adversarial-alignment", "--max-nodes", "1"])
    item = report["cases"][0]
    ensure(code == 0 and item["exact"]["status"] == "incomplete"
           and item["exact"]["standing_preserved"],
           "an unfinished comparison must keep the incumbent and report incomplete")
    ensure("optimality_replay" not in item, "a cutoff must not claim checked optimality")
    ensure(all(row["nodes"] <= 1 for row in item["heuristics"]),
           "the command budget must reach every heuristic")
    code, report = _invoke(["compare", "--case", "adversarial-alignment"])
    item = report["cases"][0]
    ensure(code == 0 and item["optimality_replay"]["status"] == "verified",
           "complete optimum must carry independently replayed evidence")
    ensure(item["exact"]["arenas"][0]["best_span_over_load"] > 0
           and item["exact"]["arenas"][0]["optimality_gap"] == 0,
           "a proved optimum must not erase the difference from live load")


def cases() -> list[Case]:
    return [Case("corpus receipt", _corpus_receipt),
            Case("unknown case", _unknown_case),
            Case("candidate binding and refusal", _candidate_identity_and_refusal),
            Case("malformed input", _malformed_input),
            Case("comparison cutoff and replay", _comparison_cutoff_and_replay)]
