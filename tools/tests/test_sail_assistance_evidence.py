# SPDX-License-Identifier: Apache-2.0
"""Published native observations conform to the interfaces that produced them."""

import json

from jsonschema import Draft202012Validator

from tests.harness import TOOLS, Case, ensure


def _published_reports() -> None:
    evidence = TOOLS.parent / "docs/assurance/sail-assistance-evidence"
    contracts = {
        "assist": TOOLS / "sail-assist.schema.json",
        "assist-controls": TOOLS / "sail-assist.schema.json",
        "lsp": TOOLS / "sail-lsp.schema.json",
        "isla": TOOLS / "sail-isla/report.schema.json",
        "modular": TOOLS / "sail-modular/report.schema.json",
    }
    reports = {}
    for name, path in contracts.items():
        schema = json.loads(path.read_text(encoding="utf-8"))
        report = json.loads((evidence / f"{name}.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(report)
        reports[name] = report
    ensure(reports["assist"]["state"] == "closed" and
           reports["assist"]["completion"]["acceptance_established"] is False,
           "a closed historical journal must not confer acceptance")
    ensure(reports["isla"]["passed"] and reports["modular"]["verdict"] == "pass",
           "published successful comparisons must retain their complete verdicts")
    ensure([attempt["outcome"] for attempt in reports["assist-controls"]["attempts"]] == ["failed", "passed"],
           "actual compiler controls must retain both the negative and restored-source positive verdict")


def cases() -> list[Case]:
    return [Case("published-native-report-contracts", _published_reports)]
