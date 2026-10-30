# SPDX-License-Identifier: Apache-2.0
"""The maintained table rules cover widths, pipes and suppressed-looking input."""

from tests.harness import TOOLS, Case, ensure
from vos.markdownlint import table_findings

CONFIG = TOOLS.parent / ".pymarkdown.json"


def _table_rules() -> None:
    header = "| a | b |\n| --- | --- |\n"
    for row in ("| 1 |", "| 1 | 2 | 3 |"):
        findings = table_findings(header + row + "\n", CONFIG)
        ensure(any("MD056" in finding for finding in findings),
               f"ragged table escaped the maintained width rule: {findings}")
    ensure(not table_findings(header + "| a\\|b | `value` |\n", CONFIG),
           "an escaped pipe inside a cell must not add a column")
    ensure(not table_findings("```md\n" + header + "| 1 |\n```\n", CONFIG),
           "a displayed example is not a table declaration")


def _pragmas_cannot_disable_validation() -> None:
    raw = ("<!-- pyml disable md056 -->\n\n"
           "| a | b |\n| --- | --- |\n| 1 |\n")
    ensure(any("MD056" in finding for finding in table_findings(raw, CONFIG)),
           "document pragmas must not disable table validation")


def _pipe_style() -> None:
    raw = "a | b\n--- | ---\n1 | 2\n"
    ensure(any("MD055" in finding for finding in table_findings(raw, CONFIG)),
           "machine-read tables must keep their leading and trailing pipes")


def cases() -> list[Case]:
    return [Case("maintained Markdown table rules", _table_rules),
            Case("document pragmas cannot disable table validation", _pragmas_cannot_disable_validation),
            Case("table pipe style remains explicit", _pipe_style)]
