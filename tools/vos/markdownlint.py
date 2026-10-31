# SPDX-License-Identifier: Apache-2.0
"""Standard table syntax validation, separate from semantic-rule mutation replay."""

import json
import multiprocessing
import os
import tempfile
from contextlib import nullcontext
from pathlib import Path

from pymarkdown.api import PyMarkdownApi, PyMarkdownApiException, PyMarkdownScanFailure

from vos import corpus
from vos.report import Reporter

# A host wave already runs other gates. Bound this CPU-heavy parser to two workers,
# and retain the serial path for small calls, including behavioral test fixtures.
PARALLEL_BYTES = 1 << 20
PARALLEL_TIMEOUT = 300

type Batch = list[tuple[int, str]]
type BatchResult = tuple[int, list[tuple[int, list[str]]]]


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


def _batch(documents: list[str], config: Path, *, directory: Path | None = None) -> list[list[str]]:
    """Initialize the pinned parser once over an exact immutable file population.

    A private directory contains only the selected source strings, with ordinal names
    rather than authored paths. The linter's own discovery must return that exact set;
    exclusions, parser errors and unfamiliar output fall back to the string route.
    Full documents stay separate, so fences and parser state cannot cross files.
    """
    settings = json.loads(config.read_text(encoding="utf-8"))
    if not isinstance(settings, dict) or set(settings) - {"extensions", "plugins"}:
        raise ValueError("Markdown configuration requires the original string route")
    with (tempfile.TemporaryDirectory(prefix="vos-markdown-") if directory is None
          else nullcontext(directory)) as temporary:
        paths = [Path(temporary) / f"{index:08d}.md" for index in range(len(documents))]
        for path, raw in zip(paths, documents, strict=True):
            path.write_text(raw or "\n", encoding="utf-8", newline="")
        api = _api(config)
        expected = {path.resolve(): index for index, path in enumerate(paths)}
        discovered = [Path(path).resolve() for path in api.list_path(str(temporary)).matching_files]
        if len(discovered) != len(expected) or set(discovered) != set(expected):
            raise ValueError("Markdown batch discovery changed the indexed population")
        result = api.scan_path(str(temporary))
        if result.critical_errors or result.pragma_errors:
            raise ValueError("Markdown batch returned non-rule diagnostics")
        findings: list[list[str]] = [[] for _ in documents]
        for failure in result.scan_failures:
            index = expected.get(Path(failure.scan_file).resolve())
            if index is None:
                raise ValueError("Markdown batch returned a finding outside its input set")
            findings[index].append(_finding(failure))
        return findings


def _partitions(documents: Batch, workers: int) -> list[Batch]:
    """Place each immutable document exactly once, balancing UTF-8 source bytes."""
    groups: list[Batch] = [[] for _ in range(workers)]
    sizes = [0] * workers
    weighted = [(index, raw, len(raw.encode("utf-8"))) for index, raw in documents]
    for index, raw, size in sorted(weighted, key=lambda item: (-item[2], item[0])):
        target = min(range(workers), key=lambda worker: (sizes[worker], worker))
        groups[target].append((index, raw))
        sizes[target] += size
    return groups


def _batch_task(documents: Batch, config: Path, directory: Path) -> BatchResult:
    """A fresh spawned parser sees only complete source strings and private settings."""
    groups = _batch([raw for _, raw in documents], config, directory=directory)
    return os.getpid(), [(index, group) for (index, _), group
                         in zip(documents, groups, strict=True)]


def _parallel(documents: Batch, config: Path, workers: int) -> tuple[dict[int, list[str]], int]:
    """Join a complete worker population, or stop it before the caller replays serially."""
    settings = config.read_bytes()
    decoded = json.loads(settings)
    if not isinstance(decoded, dict) or set(decoded) - {"extensions", "plugins"}:
        raise ValueError("Markdown configuration requires the original string route")
    # Relocating arbitrary plugin settings could change relative-path semantics.
    # Only the maintained table plugins' path-free vocabulary enters worker snapshots.
    supported: dict[str, dict[str, set[str]]] = {
        "extensions": {"markdown-tables": {"enabled"}, "linter-pragmas": {"enabled"}},
        "plugins": {"md055": {"enabled", "style"}, "md056": {"enabled"}},
    }
    for section, entries in decoded.items():
        if not isinstance(entries, dict) or set(entries) - supported[section].keys():
            raise ValueError("Markdown settings require their original configuration location")
        for name, options in entries.items():
            if not isinstance(options, dict) or set(options) - supported[section][name]:
                raise ValueError("Markdown options require their original configuration location")
    with tempfile.TemporaryDirectory(prefix="vos-markdown-workers-") as temporary:
        snapshot = Path(temporary) / "config.json"
        snapshot.write_bytes(settings)
        groups = _partitions(documents, workers)
        directories = [Path(temporary) / str(index) for index in range(workers)]
        for directory in directories:
            directory.mkdir()
        pool = multiprocessing.get_context("spawn").Pool(processes=workers)
        try:
            results = pool.starmap_async(
                _batch_task, list(zip(groups, [snapshot] * workers, directories, strict=True))
            ).get(timeout=PARALLEL_TIMEOUT)
            pool.close()
        except BaseException:
            # terminate() requests stopping; join() establishes it before replay or
            # removal of the parent-owned document and configuration directories.
            pool.terminate()
            raise
        finally:
            pool.join()
        joined: dict[int, list[str]] = {}
        processes: set[int] = set()
        for group, (process, result) in zip(groups, results, strict=True):
            if type(process) is not int or process < 1:
                raise ValueError("Markdown worker returned an invalid process identity")
            processes.add(process)
            returned: set[int] = set()
            for index, findings in result:
                if (type(index) is not int or index in joined
                        or not isinstance(findings, list)
                        or not all(isinstance(finding, str) for finding in findings)):
                    raise ValueError("Markdown worker returned invalid or duplicate findings")
                joined[index] = findings
                returned.add(index)
            if returned != {index for index, _ in group}:
                raise ValueError("Markdown worker changed its assigned document population")
        if set(joined) != {index for index, _ in documents}:
            raise ValueError("Markdown workers changed the selected document population")
        return joined, len(processes)


def document_findings(documents: list[corpus.Document], config: Path, *,
                      metrics: dict[str, int] | None = None) -> list[str]:
    """Ordered decisions, with the original per-document error path as fallback.

    FileSourceProvider normalizes carriage returns while scan_string does not; keep
    those inputs on the string route. There is no cached parser or verdict between
    calls, and a refused batch supplies no acceptance evidence of its own.
    """
    eligible = [(index, doc) for index, doc in enumerate(documents)
                if doc.raw.strip() and "\r" not in doc.raw]
    batched: dict[int, list[str]] = {}
    if metrics is not None:
        metrics.update(workers=1, worker_limit=1, parallel_attempts=0, parallel_fallbacks=0)
    workers = min(2, os.process_cpu_count() or 1, len(eligible))
    try:
        source_bytes = sum(len(doc.raw.encode("utf-8")) for _, doc in eligible)
    except UnicodeError:
        # Direct string callers can supply unpaired surrogates. Placement already
        # falls back to scan_string for them; sizing must preserve that route too.
        source_bytes = -1
    if workers > 1 and source_bytes >= PARALLEL_BYTES:
        if metrics is not None:
            metrics.update(worker_limit=workers, parallel_attempts=1)
        try:
            batched, actual_workers = _parallel([(index, doc.raw) for index, doc in eligible],
                                                 config, workers)
            if metrics is not None:
                metrics["workers"] = actual_workers
        except Exception:
            # Worker infrastructure supplies no verdict. Replay the original complete
            # batch/string route, retaining its original configuration-path diagnostics.
            if metrics is not None:
                metrics["parallel_fallbacks"] = 1
    if len(eligible) > 1:
        try:
            if not batched:
                groups = _batch([doc.raw for _, doc in eligible], config)
                batched = {index: group for (index, _), group in zip(eligible, groups, strict=True)}
        except OSError, ValueError, PyMarkdownApiException:
            pass
    findings: list[str] = []
    for index, doc in enumerate(documents):
        try:
            group = batched[index] if index in batched else table_findings(doc.raw, config)
            findings.extend(f"{doc.name}:{finding}" for finding in group)
        except (OSError, ValueError, PyMarkdownApiException) as exc:
            findings.append(f"{doc.name}: Markdown validation failed: {exc}")
    return findings


def run(root: Path, *, metrics: dict[str, int] | None = None) -> Reporter:
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
                                      root / ".pymarkdown.json", metrics=metrics))
    rep.report("markdown", "table syntax finding(s):", findings,
               "the pinned MD055 and MD056 checks accept every indexed table")
    return rep
