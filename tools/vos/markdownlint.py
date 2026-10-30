# SPDX-License-Identifier: Apache-2.0
"""Standard table syntax validation, separate from semantic-rule mutation replay."""

from pathlib import Path

from pymarkdown.api import PyMarkdownApi, PyMarkdownApiException

from vos import corpus
from vos.report import Reporter


def table_findings(raw: str, config: Path) -> list[str]:
    """Delegate table syntax to the pinned Markdown linter, without document pragmas."""
    api = (PyMarkdownApi().configuration_file_path(str(config))
           .disable_rule_by_identifier("*")
           .enable_rule_by_identifier("MD055")
           .enable_rule_by_identifier("MD056")
           .enable_extension_by_identifier("markdown-tables")
           .set_boolean_property("extensions.linter-pragmas.enabled", False))
    result = api.scan_string(raw or "\n")
    return [f"{failure.line_number}: {failure.rule_id} {failure.rule_description}"
            f"{failure.extra_error_information}" for failure in result.scan_failures]


def run(root: Path) -> Reporter:
    """Validate indexed authored Markdown once per host wave, preserving its bytes."""
    rep = Reporter()
    rep.line("=== markdown: standard table syntax ===")
    findings: list[str] = []
    try:
        documents = corpus.load(root).docs
    except (OSError, ValueError, RuntimeError) as exc:
        findings.append(f"cannot read the indexed Markdown corpus: {exc}")
        documents = []
    if not documents and not findings:
        findings.append("the index supplies no Markdown documents to validate")
    for doc in documents:
        if "|" not in doc.raw:
            continue
        try:
            findings.extend(f"{doc.name}:{finding}" for finding in
                            table_findings(doc.raw, root / ".pymarkdown.json"))
        except (OSError, ValueError, PyMarkdownApiException) as exc:
            findings.append(f"{doc.name}: Markdown validation failed: {exc}")
    rep.report("markdown", "table syntax finding(s):", findings,
               "the pinned MD055 and MD056 checks accept every indexed table")
    return rep
