# SPDX-License-Identifier: Apache-2.0
"""The maintained table rules cover widths, pipes and suppressed-looking input."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pymarkdown.api import PyMarkdownApiException

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from vos import corpus, markdownlint
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


def _serial(documents: list[corpus.Document], config: Path) -> list[str]:
    findings: list[str] = []
    for doc in documents:
        try:
            findings.extend(f"{doc.name}:{finding}" for finding in table_findings(doc.raw, config))
        except (OSError, ValueError, PyMarkdownApiException) as exc:
            findings.append(f"{doc.name}: Markdown validation failed: {exc}")
    return findings


def _batch_preserves_complete_ordered_findings() -> None:
    header = "| 标题 | b |\n| --- | --- |\n"
    inputs = [header + "| 1 |\n", "```md\n" + header + "| 1 |\n```\n",
              "<!-- pyml disable md056 -->\n\n" + header + "| 1 | 2 | 3 |\n",
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
                  PyMarkdownApiException("parser refused")):
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
    with sandbox_tree({".pymarkdown.json": CONFIG.read_text(encoding="utf-8"),
                       "a.md": raw, "b.md": raw}) as root:
        (root / "ignored.md").write_text(raw.replace("1 | 2", "1"), encoding="utf-8")
        ensure(not markdownlint.run(root).findings, "untracked Markdown entered the batch")
        (root / "a.md").write_text(raw.replace("1 | 2", "1"), encoding="utf-8", newline="")
        ensure(markdownlint.run(root).findings == 1, "a changed source reused a prior verdict")
        config = root / ".pymarkdown.json"
        settings = json.loads(config.read_text(encoding="utf-8"))
        settings["system"] = {"exclude_path": "*.md"}
        config.write_text(json.dumps(settings), encoding="utf-8")
        ensure(markdownlint.run(root).findings == 1,
               "batch discovery exclusions must not hide indexed string inputs")
        config.write_text("{", encoding="utf-8")
        expected = _serial(corpus.load(root).docs, config)
        report = markdownlint.run(root)
        ensure(report.findings == len(expected) and report.out[2:] == [f"       {f}" for f in expected],
               "malformed configuration must retain the original string decisions and diagnostics")


def _batch_rejects_omissions_and_unknown_results() -> None:
    documents = [corpus.from_text("| a | b |\n| --- | --- |\n| 1 |\n", name)
                 for name in ("a.md", "b.md")]
    expected = _serial(documents, CONFIG)
    original = markdownlint._api(CONFIG)
    for mode in ("omitted", "unknown", "critical", "pragma"):
        def discovered(directory: str, mode: str = mode) -> SimpleNamespace:
            paths = sorted(str(path) for path in Path(directory).glob("*.md"))
            return SimpleNamespace(matching_files=paths[:1] if mode == "omitted" else paths)

        result = SimpleNamespace(critical_errors=["error"] if mode == "critical" else [],
                                 pragma_errors=["error"] if mode == "pragma" else [],
                                 scan_failures=[SimpleNamespace(scan_file="unknown.md")]
                                 if mode == "unknown" else [])
        fake = SimpleNamespace(list_path=discovered, scan_path=lambda _directory, result=result: result,
                               scan_string=original.scan_string)
        with patch.object(markdownlint, "_api", return_value=fake):
            ensure(markdownlint.document_findings(documents, CONFIG) == expected,
                   f"batch {mode} must replay the original complete string population")


def _carriage_returns_keep_the_string_provider() -> None:
    for ending in ("\r\n", "\r"):
        documents = [corpus.from_text(("| a | b |\n| --- | --- |\n| 1 |\n").replace("\n", ending),
                                      name) for name in ("a.md", "b.md")]
        expected = _serial(documents, CONFIG)
        with patch.object(markdownlint, "_batch", side_effect=AssertionError("wrong provider")):
            ensure(markdownlint.document_findings(documents, CONFIG) == expected,
                   "carriage-return content must retain the original provider's decisions")


def cases() -> list[Case]:
    return [Case("maintained Markdown table rules", _table_rules),
            Case("document pragmas cannot disable table validation", _pragmas_cannot_disable_validation),
            Case("table pipe style remains explicit", _pipe_style),
            Case("batch preserves complete ordered findings", _batch_preserves_complete_ordered_findings),
            Case("batch refusals retain string errors", _batch_refusal_retains_each_string_error),
            Case("batch preserves index membership and edits", _batch_preserves_index_membership_and_edits),
            Case("batch rejects omissions and unknown results", _batch_rejects_omissions_and_unknown_results),
            Case("carriage returns retain string provider", _carriage_returns_keep_the_string_provider)]
