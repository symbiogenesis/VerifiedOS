# SPDX-License-Identifier: Apache-2.0
"""The maintained table rules cover widths, pipes, pragmas and binary installation."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from tests.pinned_binary_fixture import InstallerFixture
from vos import corpus, markdownlint
from vos.markdownlint import table_findings

CONFIG = TOOLS.parent / ".rumdl.toml"


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
    table = "| a | b |\n| --- | --- |\n| 1 |\n"
    directives = (
        "<!-- pyml disable md056 -->",
        "<!-- rumdl-disable MD056 -->",
        "<!-- rumdl-disable -->",
        "<!-- markdownlint-disable MD056 -->",
        '<!-- markdownlint-configure-file { "MD056": false } -->',
        '<!-- rumdl-configure-file { "MD056": false } -->',
        "<!-- prettier-ignore -->",
        "> <!-- rumdl-disable MD056 -->",
        "<!--\nrumdl-disable MD056\n-->",
    )
    for directive in directives:
        raw = f"{directive}\n\n{table}"
        findings = table_findings(raw, CONFIG)
        expected_line = raw.count("\n")
        ensure(any(finding.startswith(f"{expected_line}: MD056 ") for finding in findings),
               f"document directive suppressed or shifted table validation ({directive!r}): {findings}")


def _pipe_style() -> None:
    raw = "a | b\n--- | ---\n1 | 2\n"
    ensure(any("MD055" in finding for finding in table_findings(raw, CONFIG)),
           "machine-read tables must keep their leading and trailing pipes")


def _serial(documents: list[corpus.Document], config: Path) -> list[str]:
    findings: list[str] = []
    for doc in documents:
        try:
            findings.extend(f"{doc.name}:{finding}" for finding in table_findings(doc.raw, config))
        except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
            findings.append(f"{doc.name}: Markdown validation failed: {exc}")
    return findings


def _batch_preserves_complete_ordered_findings() -> None:
    header = "| 标题 | b |\n| --- | --- |\n"
    inputs = [header + "| 1 |\n", "```md\n" + header + "| 1 |\n```\n",
              "<!-- rumdl-disable MD056 -->\n\n" + header + "| 1 | 2 | 3 |\n",
              "a | b\n--- | ---\n1 | 2", "```md\n| unclosed fence",
              header + "| 合法 | `x` |\n", header + "| a\\|b | x |\n",
              "> " + header.replace("\n", "\n> ") + "| 1 |\n", "", "| ordinary text"]
    documents = [corpus.from_text(raw, f"{len(inputs) - i:02d} ü.md")
                 for i, raw in enumerate(inputs)]
    expected = _serial(documents, CONFIG)
    with (patch.object(markdownlint, "_batch", wraps=markdownlint._batch) as batch,
          patch.object(markdownlint, "table_findings", wraps=table_findings) as strings):
        actual = markdownlint.document_findings(documents, CONFIG)
    ensure(batch.call_count == 1 and strings.call_count == 1 and actual == expected,
           f"batched documents changed ordered findings: {actual!r} != {expected!r}")
    ensure(any("MD055" in line for line in actual) and any("MD056" in line for line in actual),
           "the comparison must include both rule refusals")


def _batch_refusal_retains_each_string_error() -> None:
    documents = [corpus.from_text("| a | b |\n| --- | --- |\n| 1 |\n", name)
                 for name in ("a.md", "b.md")]
    expected = _serial(documents, CONFIG)
    for error in (OSError("placement denied"), ValueError("population mismatch"),
                  subprocess.TimeoutExpired(["rumdl"], 120)):
        with patch.object(markdownlint, "_batch", side_effect=error):
            ensure(markdownlint.document_findings(documents, CONFIG) == expected,
                   f"a refused batch must replay every original string: {error}")
    with (patch.object(markdownlint, "_batch", side_effect=ValueError("refused")),
          patch.object(markdownlint, "table_findings", side_effect=[OSError("denied"), ["finding"]])):
        ensure(markdownlint.document_findings(documents, CONFIG)
               == ["a.md: Markdown validation failed: denied", "b.md:finding"],
               "a document error must not hide the following document's findings")


def _batch_preserves_index_membership_and_edits() -> None:
    raw = "| a | b |\n| --- | --- |\n| 1 | 2 |\n"
    with sandbox_tree({".rumdl.toml": CONFIG.read_text(encoding="utf-8"),
                       "a.md": raw, "b.md": raw}) as root:
        (root / "ignored.md").write_text(raw.replace("1 | 2", "1"), encoding="utf-8")
        ensure(not markdownlint.run(root).findings, "untracked Markdown entered the batch")
        (root / "a.md").write_text(raw.replace("1 | 2", "1"), encoding="utf-8", newline="")
        ensure(markdownlint.run(root).findings == 1, "a changed source reused a prior verdict")
        config = root / ".rumdl.toml"
        config.write_text(CONFIG.read_text(encoding="utf-8") + '\nexclude = ["*.md"]\n', encoding="utf-8")
        expected = _serial(corpus.load(root).docs, config)
        report = markdownlint.run(root)
        ensure(report.findings == len(expected) and report.out[2:] == [f"       {f}" for f in expected],
               "unreviewed configuration keys must refuse rather than hiding indexed inputs")
        config.write_text("[global\n", encoding="utf-8")
        expected = _serial(corpus.load(root).docs, config)
        report = markdownlint.run(root)
        ensure(report.findings == len(expected) and report.out[2:] == [f"       {f}" for f in expected],
               "malformed configuration must retain the per-document decisions and diagnostics")


def _structured_verdicts() -> None:
    ensure(markdownlint.read_result(2, 0, "[]", "") == [[], []],
           "a complete structured success must pass")
    valid = json.dumps([{"file": "00000001.md", "line": 3, "rule": "MD056", "message": "width"}])
    ensure(markdownlint.read_result(2, 1, valid, "") == [[], ["3: MD056 width"]],
           "a valid diagnostic must map back to its ordinal document")
    invalid = [
        (0, "{}"),
        (0, valid),
        (1, "[]"),
        (2, "[]"),
        (1, '[{"file":"00000000.md","file":"00000000.md","line":1,"rule":"MD056","message":"x"}]'),
        (1, json.dumps([{"file": "unknown.md", "line": 1, "rule": "MD056", "message": "x"}])),
        (1, json.dumps([{"file": "00000000.md", "line": 0, "rule": "MD056", "message": "x"}])),
        (1, json.dumps([{"file": "00000000.md", "line": True, "rule": "MD056", "message": "x"}])),
        (1, json.dumps([{"file": "00000000.md", "line": 1, "rule": "MD013", "message": "x"}])),
        (1, json.dumps([{"file": "00000000.md", "line": 1, "rule": "MD056", "message": ""}])),
    ]
    for code, output in invalid:
        try:
            markdownlint.read_result(1, code, output, "stopped")
        except (ValueError, TypeError):
            continue
        raise AssertionError(f"an incomplete or failed tool verdict passed: {code}, {output}")


def _carriage_returns_and_unencodable_sources() -> None:
    for ending in ("\r\n", "\r"):
        documents = [corpus.from_text(("| a | b |\n| --- | --- |\n| 1 |\n").replace("\n", ending),
                                      name) for name in ("a.md", "b.md")]
        expected = _serial(documents, CONFIG)
        actual = markdownlint.document_findings(documents, CONFIG)
        ensure(actual == expected and len(actual) == 2
               and all(":3: MD056 " in line for line in actual),
               f"carriage-return content must preserve line numbers and width diagnostics: {actual}")
    for bad in ("| \ud800 | b |\n| --- | --- |\n| 1 |\n", "| a | \x00 |\n| --- | --- |\n| 1 |\n"):
        documents = [corpus.from_text(bad, "bad.md"),
                     corpus.from_text("| a | b |\n| --- | --- |\n| 1 |\n", "good.md")]
        expected = _serial(documents, CONFIG)
        actual = markdownlint.document_findings(documents, CONFIG)
        ensure(actual == expected and len(actual) == 2
               and actual[0].startswith("bad.md: Markdown validation failed:")
               and actual[1].startswith("good.md:3: MD056 "),
               f"unencodable or NUL-containing input must fail closed without hiding peers: {actual}")


def cases() -> list[Case]:
    return [Case("maintained Markdown table rules", _table_rules),
            Case("document pragmas cannot disable table validation", _pragmas_cannot_disable_validation),
            Case("table pipe style remains explicit", _pipe_style),
            Case("batch preserves complete ordered findings", _batch_preserves_complete_ordered_findings),
            Case("batch refusals retain string errors", _batch_refusal_retains_each_string_error),
            Case("batch preserves index membership and edits", _batch_preserves_index_membership_and_edits),
            Case("tool crashes and malformed verdicts refuse", _structured_verdicts),
            Case("carriage returns and unencodable sources retain exact diagnostics",
                 _carriage_returns_and_unencodable_sources),
            *InstallerFixture(markdownlint, "rumdl", f"rumdl-v{markdownlint.VERSION}-{{target}}",
                              "{exe}").cases()]
