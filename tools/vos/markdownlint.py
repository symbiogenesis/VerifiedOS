# SPDX-License-Identifier: Apache-2.0
"""Standard table syntax validation, separate from semantic-rule mutation replay."""

import json
import tempfile
from pathlib import Path

from pymarkdown.api import PyMarkdownApi, PyMarkdownApiException, PyMarkdownScanFailure

from vos import corpus
from vos.report import Reporter


def _api(config: Path) -> PyMarkdownApi:
    """The same explicit rules for string and isolated multi-file scans."""
    return (PyMarkdownApi().configuration_file_path(str(config))
           .disable_rule_by_identifier("*")
           .enable_rule_by_identifier("MD055")
           .enable_rule_by_identifier("MD056")
           .enable_extension_by_identifier("markdown-tables")
           .set_boolean_property("extensions.linter-pragmas.enabled", False))


def _finding(failure: PyMarkdownScanFailure) -> str:
    return (f"{failure.line_number}: {failure.rule_id} {failure.rule_description}"
            f"{failure.extra_error_information}")


def table_findings(raw: str, config: Path) -> list[str]:
    """Delegate table syntax to the pinned Markdown linter, without document pragmas."""
    return [_finding(failure) for failure in _api(config).scan_string(raw or "\n").scan_failures]


def _batch(documents: list[corpus.Document], config: Path) -> list[list[str]]:
    """Initialize the pinned parser once over an exact immutable file population.

    A private directory contains only the selected source strings, with ordinal names
    rather than authored paths. The linter's own discovery must return that exact set;
    exclusions, parser errors and unfamiliar output fall back to the string route.
    Full documents stay separate, so fences and parser state cannot cross files.
    """
    settings = json.loads(config.read_text(encoding="utf-8"))
    if not isinstance(settings, dict) or set(settings) - {"extensions", "plugins"}:
        raise ValueError("Markdown configuration requires the original string route")
    with tempfile.TemporaryDirectory(prefix="vos-markdown-") as temporary:
        paths = [Path(temporary) / f"{index:08d}.md" for index in range(len(documents))]
        for path, doc in zip(paths, documents, strict=True):
            path.write_text(doc.raw or "\n", encoding="utf-8", newline="")
        api = _api(config)
        expected = {path.resolve(): index for index, path in enumerate(paths)}
        discovered = [Path(path).resolve() for path in api.list_path(temporary).matching_files]
        if len(discovered) != len(expected) or set(discovered) != set(expected):
            raise ValueError("Markdown batch discovery changed the indexed population")
        result = api.scan_path(temporary)
        if result.critical_errors or result.pragma_errors:
            raise ValueError("Markdown batch returned non-rule diagnostics")
        findings: list[list[str]] = [[] for _ in documents]
        for failure in result.scan_failures:
            index = expected.get(Path(failure.scan_file).resolve())
            if index is None:
                raise ValueError("Markdown batch returned a finding outside its input set")
            findings[index].append(_finding(failure))
        return findings


def document_findings(documents: list[corpus.Document], config: Path) -> list[str]:
    """Ordered decisions, with the original per-document error path as fallback.

    FileSourceProvider normalizes carriage returns while scan_string does not; keep
    those inputs on the string route. There is no cached parser or verdict between
    calls, and a refused batch supplies no acceptance evidence of its own.
    """
    eligible = [(index, doc) for index, doc in enumerate(documents)
                if doc.raw.strip() and "\r" not in doc.raw]
    batched: dict[int, list[str]] = {}
    if len(eligible) > 1:
        try:
            groups = _batch([doc for _, doc in eligible], config)
            batched = {index: group for (index, _), group in zip(eligible, groups, strict=True)}
        except (OSError, ValueError, PyMarkdownApiException):
            pass
    findings: list[str] = []
    for index, doc in enumerate(documents):
        try:
            group = batched[index] if index in batched else table_findings(doc.raw, config)
            findings.extend(f"{doc.name}:{finding}" for finding in group)
        except (OSError, ValueError, PyMarkdownApiException) as exc:
            findings.append(f"{doc.name}: Markdown validation failed: {exc}")
    return findings


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
    findings.extend(document_findings([doc for doc in documents if "|" in doc.raw],
                                      root / ".pymarkdown.json"))
    rep.report("markdown", "table syntax finding(s):", findings,
               "the pinned MD055 and MD056 checks accept every indexed table")
    return rep
