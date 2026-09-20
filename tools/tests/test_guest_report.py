# SPDX-License-Identifier: Apache-2.0
"""Guest diagnostics retain failures and never present an unexecuted proof as fresh."""

import json
import tempfile
from pathlib import Path

from ci.report_guest import report
from tests.harness import Case, ensure


def _bootstrap_failure() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        console = root / "console.log"
        console.write_text("bootstrap failed\n", encoding="utf-8")
        proof = root / "proof.json"
        proof.write_text("old tracked receipt\n", encoding="utf-8")
        logs = root / "logs"
        summary = report(logs, console, proof, {"bootstrap": {"outcome": "failure"}}, "abc")
        result = json.loads((logs / "results.json").read_text(encoding="utf-8"))
        ensure(result["revision"] == "abc", "source revision was lost")
        ensure(result["commands"]["bootstrap"] == "failure", "bootstrap failure was hidden")
        ensure(result["commands"]["evidence"] == "skipped", "unexecuted evidence was not skipped")
        ensure("No evidence record" in summary, "absent evidence was not explained")
        ensure((logs / "bootstrap-console.log").read_bytes() == console.read_bytes(),
               "bootstrap console was not retained")
        ensure(not (logs / "proof-evidence.json").exists(), "old proof was published as fresh")


def _proof_outcomes() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        proof = root / "proof.json"
        proof.write_text('{"receipt": "fresh"}\n', encoding="utf-8")
        for code in (0, 1):
            logs = root / str(code)
            logs.mkdir()
            evidence = {"members": [{"name": "proofs", "exit_code": code, "seconds": 12.25}]}
            (logs / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
            summary = report(logs, root / "absent-console", proof,
                             {"evidence": {"outcome": "failure"}}, "abc")
            ensure(f"| proofs | {code} | 12.2 |" in summary, "proof outcome or timing was lost")
            ensure("| evidence | failure |" in summary, "the evidence failure was hidden")
            retained = logs / "proof-evidence.json"
            ensure(retained.exists() == (code == 0), "proof receipt ignored its producing verdict")
            if code == 0:
                ensure(retained.read_bytes() == proof.read_bytes(), "proof receipt bytes changed")


def _unreadable_evidence() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for index, payload in enumerate(("{", "{}", '{"members": null}')):
            logs = root / str(index)
            logs.mkdir()
            (logs / "evidence.json").write_text(payload, encoding="utf-8")
            summary = report(logs, root / "absent-console", root / "absent-proof", {}, "abc")
            ensure("Evidence report could not be read" in summary, "bad evidence aborted reporting")
            ensure((logs / "results.json").is_file(), "command outcomes were not retained")
            ensure(not (logs / "proof-evidence.json").exists(), "bad evidence published a proof")


def cases() -> list[Case]:
    return [
        Case("bootstrap failure retains diagnostics without stale proofs", _bootstrap_failure),
        Case("proof receipt follows its member verdict", _proof_outcomes),
        Case("unreadable evidence preserves command outcomes", _unreadable_evidence),
    ]
