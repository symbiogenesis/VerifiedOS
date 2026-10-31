# SPDX-License-Identifier: Apache-2.0
"""The maintained table rules cover widths, pipes and suppressed-looking input."""

import json
import multiprocessing
import tempfile
from collections.abc import Callable
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


def _partitions_are_complete_and_byte_balanced() -> None:
    documents = [(0, "a" * 20), (1, "字" * 6), (2, "b" * 4), (3, "c" * 2)]
    groups = markdownlint._partitions(documents, 2)
    ensure(groups == [[documents[0], documents[3]], [documents[1], documents[2]]],
           f"partitions must balance actual UTF-8 bytes deterministically: {groups}")
    ensure(sorted(item for group in groups for item in group) == documents,
           "parallel partitions changed the complete document population")


def _parallel_selection_is_bounded() -> None:
    documents = [corpus.from_text("| ordinary text\n", name) for name in ("a.md", "b.md")]
    for cpus, threshold in ((1, 0), (None, 0), (8, 1 << 20)):
        with (patch.object(markdownlint.os, "process_cpu_count", return_value=cpus),
              patch.object(markdownlint, "PARALLEL_BYTES", threshold),
              patch.object(markdownlint, "_parallel") as parallel):
            ensure(not markdownlint.document_findings(documents, CONFIG), "fixture should pass")
            ensure(not parallel.called, "small or single-CPU calls must retain serial parsing")
    with (patch.object(markdownlint.os, "process_cpu_count", return_value=64),
          patch.object(markdownlint, "PARALLEL_BYTES", 0),
          patch.object(markdownlint, "_parallel", return_value=({0: [], 1: []}, 2)) as parallel):
        metrics: dict[str, int] = {}
        markdownlint.document_findings(documents, CONFIG, metrics=metrics)
        ensure(parallel.call_args.args[2] == 2 and metrics["workers"] == 2,
               "the host-wave parser budget must remain at most two workers")


def _unencodable_sources_keep_the_string_provider() -> None:
    for raw in ("| \ud800 | b |\n| --- | --- |\n| 1 |\n", "| ordinary \udfff text\n"):
        documents = [corpus.from_text(raw, name) for name in ("a.md", "b.md")]
        expected = _serial(documents, CONFIG)
        with (patch.object(markdownlint.os, "process_cpu_count", return_value=2),
              patch.object(markdownlint, "PARALLEL_BYTES", 0),
              patch.object(markdownlint, "_parallel", side_effect=AssertionError("wrong provider"))):
            ensure(markdownlint.document_findings(documents, CONFIG) == expected,
                   "unencodable source strings must preserve the original provider's diagnostics")


def _spawned_workers_preserve_complete_diagnostics() -> None:
    header = "| 标题 | b |\n| --- | --- |\n"
    inputs = [header + "| 1 |\n", "```md\n" + header + "| 1 |\n```\n",
              "<!-- pyml disable md056 -->\n\n" + header + "| 1 | 2 | 3 |\n",
              "a | b\n--- | ---\n1 | 2", header + "| a\\|b | `value` |\n",
              header.replace("\n", "\r\n") + "| 1 |\r\n", ""]
    documents = [corpus.from_text(raw, f"{len(inputs) - index} ü.md")
                 for index, raw in enumerate(inputs)]
    with (patch.object(markdownlint.os, "process_cpu_count", return_value=2),
          patch.object(markdownlint, "PARALLEL_BYTES", 0)):
        metrics: dict[str, int] = {}
        ensure(markdownlint.document_findings(documents, CONFIG, metrics=metrics)
               == _serial(documents, CONFIG), "spawned parsers changed complete ordered diagnostics")
        ensure(metrics["parallel_attempts"] == 1 and metrics["parallel_fallbacks"] == 0
               and metrics["worker_limit"] == 2 and 1 <= metrics["workers"] <= 2,
               f"the fixture must exercise real successful spawned workers: {metrics}")


class _Pool:
    def __init__(self, events: list[str], result: object = None,
                 error: Exception | None = None,
                 inspect: Callable[[list[tuple[markdownlint.Batch, Path, Path]]], None] | None = None
                 ) -> None:
        self.events = events
        self.result = result
        self.error = error
        self.inspect = inspect

    def starmap_async(self, _worker: object,
                      arguments: list[tuple[markdownlint.Batch, Path, Path]]) -> SimpleNamespace:
        if self.inspect is not None:
            self.inspect(arguments)

        def get(timeout: int) -> object:
            ensure(timeout == markdownlint.PARALLEL_TIMEOUT, "the pool needs its complete deadline")
            if self.error is not None:
                raise self.error
            return self.result

        return SimpleNamespace(get=get)

    def close(self) -> None:
        self.events.append("close")

    def terminate(self) -> None:
        self.events.append("terminate")

    def join(self) -> None:
        self.events.append("join")


def _pool_failures_stop_before_complete_serial_replay() -> None:
    documents = [corpus.from_text("| a | b |\n| --- | --- |\n| 1 |\n", name)
                 for name in ("a.md", "b.md")]
    expected = _serial(documents, CONFIG)
    for error in (OSError("worker failed"), multiprocessing.TimeoutError("deadline")):
        events: list[str] = []
        pool = _Pool(events, error=error)
        original = markdownlint._batch

        def serial(raw: list[str], config: Path, events: list[str] = events,
                   original: Callable[[list[str], Path], list[list[str]]] = original
                   ) -> list[list[str]]:
            events.append("serial")
            return original(raw, config)

        with (patch.object(markdownlint.os, "process_cpu_count", return_value=2),
              patch.object(markdownlint, "PARALLEL_BYTES", 0),
              patch.object(markdownlint.multiprocessing, "get_context",
                           return_value=SimpleNamespace(Pool=lambda pool=pool, **_kwargs: pool)),
              patch.object(markdownlint, "_batch", side_effect=serial)):
            ensure(markdownlint.document_findings(documents, CONFIG) == expected,
                   "worker failure must retain every original string diagnostic")
        ensure(events == ["terminate", "join", "serial"],
               f"failed workers must be dead before serial replay starts: {events}")
    with (patch.object(markdownlint.os, "process_cpu_count", return_value=2),
          patch.object(markdownlint, "PARALLEL_BYTES", 0),
          patch.object(markdownlint.multiprocessing, "get_context", side_effect=OSError("startup")),
          patch.object(markdownlint, "_batch", wraps=markdownlint._batch) as replay):
        ensure(markdownlint.document_findings(documents, CONFIG) == expected and replay.call_count == 1,
               "pool startup failure must replay the complete original population")


def _parallel_rejects_incomplete_or_invalid_results() -> None:
    documents = [corpus.from_text("| ordinary text\n", name) for name in ("a.md", "b.md")]
    malformed = [[], [(1, [(0, [])])], [(1, [(0, []), (0, [])])],
                 [(1, [(0, []), (2, [])])], [(1, [(0, []), (1, [3])])],
                 [(False, [(0, []), (1, [])])], [(1, [(0, []), (True, [])])],
                 [(1, [(0, []), (1, None)])], [(1,)]]
    malformed += [[(1, [(1, [])]), (2, [(0, [])])],
                  [(1, [(0, [])]), (2, [(1, [])]), (3, [])]]
    for result in malformed:
        events: list[str] = []
        with (patch.object(markdownlint.os, "process_cpu_count", return_value=2),
              patch.object(markdownlint, "PARALLEL_BYTES", 0),
              patch.object(markdownlint.multiprocessing, "get_context", return_value=SimpleNamespace(
                  Pool=lambda events=events, result=result, **_kwargs: _Pool(events, result=result))),
              patch.object(markdownlint, "_batch", wraps=markdownlint._batch) as serial):
            ensure(not markdownlint.document_findings(documents, CONFIG), "serial fixture should pass")
            ensure(serial.call_count == 1 and events == ["close", "join"],
                   f"invalid worker output must supply no accepted findings: {result}")


def _workers_use_configuration_snapshot_and_refresh_between_calls() -> None:
    raw = "| a | b |\n| --- | --- |\n| 1 |\n"
    documents = [corpus.from_text(raw, name) for name in ("a.md", "b.md")]
    original = CONFIG.read_bytes()
    with tempfile.TemporaryDirectory(prefix="vos-markdown-settings-") as temporary:
        config = Path(temporary) / "config.json"
        config.write_bytes(original)

        def inspect(arguments: list[tuple[markdownlint.Batch, Path, Path]]) -> None:
            ensure(all(snapshot.read_bytes() == original for _, snapshot, _ in arguments),
                   "workers must read an immutable copy of the selected configuration bytes")
            config.write_text("{", encoding="utf-8")
            ensure(all(snapshot.read_bytes() == original for _, snapshot, _ in arguments),
                   "a changed owner must not alter an active worker snapshot")

        with (patch.object(markdownlint.os, "process_cpu_count", return_value=2),
              patch.object(markdownlint, "PARALLEL_BYTES", 0),
              patch.object(markdownlint.multiprocessing, "get_context", return_value=SimpleNamespace(
                  Pool=lambda **_kwargs: _Pool([], result=[(1, [(0, ["fixture"])]), (2, [(1, [])])],
                                              inspect=inspect)))):
            ensure(markdownlint.document_findings(documents, config) == ["a.md:fixture"],
                   "the pool's complete result must retain document order")
            expected = _serial(documents, config)
            ensure(markdownlint.document_findings(documents, config) == expected,
                   "a later invocation must read changed configuration and retain original paths")
        settings = json.loads(original)
        settings["plugins"]["unknown"] = {"enabled": False, "path": "relative/path"}
        config.write_text(json.dumps(settings), encoding="utf-8")
        expected = _serial(documents, config)
        with (patch.object(markdownlint.os, "process_cpu_count", return_value=2),
              patch.object(markdownlint, "PARALLEL_BYTES", 0),
              patch.object(markdownlint.multiprocessing, "get_context") as context):
            ensure(markdownlint.document_findings(documents, config) == expected and not context.called,
                   "unfamiliar plugin settings must retain their original configuration location")


def cases() -> list[Case]:
    return [Case("maintained Markdown table rules", _table_rules),
            Case("document pragmas cannot disable table validation", _pragmas_cannot_disable_validation),
            Case("table pipe style remains explicit", _pipe_style),
            Case("batch preserves complete ordered findings", _batch_preserves_complete_ordered_findings),
            Case("batch refusals retain string errors", _batch_refusal_retains_each_string_error),
            Case("batch preserves index membership and edits", _batch_preserves_index_membership_and_edits),
            Case("batch rejects omissions and unknown results", _batch_rejects_omissions_and_unknown_results),
            Case("carriage returns retain string provider", _carriage_returns_keep_the_string_provider),
            Case("parallel partitions preserve and balance UTF-8 bytes", _partitions_are_complete_and_byte_balanced),
            Case("parallel selection respects host budget", _parallel_selection_is_bounded),
            Case("unencodable sources retain string provider", _unencodable_sources_keep_the_string_provider),
            Case("spawned parsers preserve complete ordered findings", _spawned_workers_preserve_complete_diagnostics),
            Case("failed pools stop before complete serial replay", _pool_failures_stop_before_complete_serial_replay),
            Case("worker population errors retain serial validation", _parallel_rejects_incomplete_or_invalid_results),
            Case("worker configuration snapshots refresh between calls", _workers_use_configuration_snapshot_and_refresh_between_calls)]
