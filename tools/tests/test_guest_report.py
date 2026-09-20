# SPDX-License-Identifier: Apache-2.0
"""Guest diagnostics retain failures and never present an unexecuted proof as fresh."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

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
    valid = {"name": "proofs", "exit_code": 0, "seconds": 1}
    records: tuple[object, ...] = (
        None, [], {}, {"members": None}, {"members": [None]},
        {"members": [valid, valid]}, {"members": [valid, {"name": "broken"}]},
        *({"members": [valid | override]} for override in (
            {"name": ""}, {"name": 5}, {"exit_code": False}, {"exit_code": "0"},
            {"seconds": -1}, {"seconds": True}, {"seconds": "1"},
            {"seconds": float("nan")}, {"seconds": float("inf")}, {"seconds": 10 ** 400},
        )),
    )
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for index, payload in enumerate(("{", *(json.dumps(record) for record in records))):
            logs = root / str(index)
            logs.mkdir()
            (logs / "evidence.json").write_text(payload, encoding="utf-8")
            (logs / "proof-evidence.json").write_text("stale", encoding="utf-8")
            summary = report(logs, root / "absent-console", root / "absent-proof",
                             {"evidence": {"outcome": "failure"}}, "abc")
            ensure("Evidence report could not be read" in summary, "bad evidence aborted reporting")
            ensure("| Evidence member |" not in summary, "a partial evidence table was published")
            ensure((logs / "results.json").is_file(), "command outcomes were not retained")
            ensure(not (logs / "proof-evidence.json").exists(), "bad evidence published a proof")


def _skipped_evidence_ignores_old_record() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "evidence.json").write_text(json.dumps({"members": [
            {"name": "proofs", "exit_code": 0, "seconds": 1},
        ]}), encoding="utf-8")
        (root / "proof-evidence.json").write_text("old retained receipt", encoding="utf-8")
        proof = root / "proof.json"
        proof.write_text("old tracked receipt", encoding="utf-8")
        summary = report(root, root / "absent-console", proof, {}, "abc")
        ensure("| proofs |" not in summary, "skipped evidence reused a previous member verdict")
        ensure(not (root / "proof-evidence.json").exists(), "old proof receipt survived reporting")


def _diagnostic_copy_failure_keeps_summary() -> None:
    def fail_copy(source: Path, destination: Path) -> None:
        destination.write_bytes(b"partial")
        raise PermissionError("copy interrupted")

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        console = root / "console.log"
        console.write_text("bootstrap output", encoding="utf-8")
        (root / "evidence.json").write_text(json.dumps({"members": [
            {"name": "proofs", "exit_code": 0, "seconds": 1},
        ]}), encoding="utf-8")
        with patch("ci.report_guest.shutil.copyfile", side_effect=fail_copy):
            summary = report(root, console, root / "proof.json",
                             {"evidence": {"outcome": "failure"}}, "abc")
        ensure("| proofs | 0 | 1.0 |" in summary, "copy failure suppressed evidence diagnostics")
        for filename in ("bootstrap-console.log", "proof-evidence.json"):
            ensure(f"Could not retain {filename}" in summary, "copy failure was not reported")
            ensure(not (root / filename).exists(), "an incomplete diagnostic was published")
        ensure(not list(root.glob(".retain-*")), "failed copies left temporary artifacts")
        record = json.loads((root / "results.json").read_text(encoding="utf-8"))
        ensure(record["commands"]["evidence"] == "failure", "copy failure discarded gate outcomes")


def _member_names_cannot_break_table() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "evidence.json").write_text(json.dumps({"members": [
            {"name": "a|b\n<script>", "exit_code": 1, "seconds": 1},
        ]}), encoding="utf-8")
        summary = report(root, root / "absent-console", root / "absent-proof",
                         {"evidence": {"outcome": "failure"}}, "abc")
        ensure("| a&#124;b &lt;script&gt; | 1 | 1.0 |" in summary,
               "member name was interpreted as table or HTML syntax")


def cases() -> list[Case]:
    return [
        Case("bootstrap failure retains diagnostics without stale proofs", _bootstrap_failure),
        Case("proof receipt follows its member verdict", _proof_outcomes),
        Case("unreadable evidence preserves command outcomes", _unreadable_evidence),
        Case("skipped evidence refuses stale records and proof receipts", _skipped_evidence_ignores_old_record),
        Case("diagnostic copy failure preserves the remaining report", _diagnostic_copy_failure_keeps_summary),
        Case("member names are escaped in Markdown tables", _member_names_cannot_break_table),
    ]
