# SPDX-License-Identifier: Apache-2.0
"""Independent coordinate/overlay/formatter oracle and seeded-fault controls for Q25x."""

import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos.cli import vela as vela_cli
from vos.vela.generated_tests import (
    CANDIDATE_VERSIONS,
    EXPECTED_LICENSE_SHA256,
    EXPECTED_NATIVE_SHA256,
    HELD_OUT_FAULT,
    NONMINIMAL_FAULT_TRACES,
    SEEDED_FAULTS,
    FormatTemplate,
    OracleTextModel,
    case_complexity,
    evaluate_seeded_fault,
    execute_explicit_case,
    replay_overlay_trace,
    verify_coordinate_observations,
    verify_format_template,
)

INDEPENDENT_CASES = True


def _coordinate_oracle_and_utf16_controls() -> None:
    for newline in ("\n", "\r\n", "\r"):
        text = newline.join((
            "// 😀 supplementary",
            "module Coord;",
            "public Nat Entry(Nat input) {",
            "  return input;",
            "}",
        )) + newline
        oracle = OracleTextModel.from_text(text)
        ensure(len(oracle.lines) == 6, f"expected 6 lines for {newline!r}, got {len(oracle.lines)}")
        # '// ' is 3 UTF-16 units; '😀' is 2 UTF-16 units (4 UTF-8 bytes); ' supplementary' is 14 units.
        ensure(oracle.expected_position_byte_offset(0, 3) == 3, "UTF-16 start of emoji should be byte 3")
        ensure(oracle.expected_position_byte_offset(0, 4) is None, "interior surrogate offset must fail closed")
        ensure(oracle.expected_position_byte_offset(0, 5) == 7, "after 4-byte emoji should be byte 7")
        # Clamping past line end:
        line0_end_byte = oracle.lines[0].end_byte
        ensure(
            oracle.expected_position_byte_offset(0, 999) == line0_end_byte,
            "character past line end did not clamp to line end byte",
        )
        if newline == "\r\n":
            ensure(
                oracle.expected_byte_position(line0_end_byte + 1) is None,
                "interior CRLF byte offset was not rejected",
            )
        verify_coordinate_observations(
            "untitled:coord-test.vela",
            1,
            text,
            queries=[
                (0, 0),
                (0, 3),
                (0, 4),
                (0, 5),
                (0, 999),
                (1, 0),
                (2, 11),
                (-1, 0),
                (0, -1),
                (99, 0),
                (True, 0),
            ],
            byte_queries=[-1, 0, 3, 4, 5, 6, 7, line0_end_byte, line0_end_byte + 1, 9999],
            diagnostic_sites=[(1, 1), (1, 4), (1, 5), (1, 99), (0, 1), (99, 1)],
        )


def _overlay_and_supported_requests_without_subprocess() -> None:
    doc_a = "untitled:doc-a.vela"
    valid_text = "\r\n".join((
        "// 😀 header",
        "module Overlay;",
        "public Nat Entry(Nat input) {",
        "  let local = input;",
        "  return local;",
        "}",
    )) + "\r\n"
    error_text = valid_text.replace("return local;", "return SYNTAX_ERROR;")

    trace: list[dict[str, object]] = [
        {"action": "open", "uri": doc_a, "version": 1, "text": valid_text},
        {"action": "query", "uri": doc_a, "method": "textDocument/documentSymbol"},
        {"action": "query", "uri": doc_a, "method": "textDocument/semanticTokens/full"},
        {
            "action": "query",
            "uri": doc_a,
            "method": "textDocument/inlayHint",
            "line": 0,
            "character": 0,
            "end_line": 5,
            "end_character": 1,
        },
        {"action": "query", "uri": doc_a, "method": "textDocument/hover", "line": 2, "character": 11},
        {"action": "query", "uri": doc_a, "method": "textDocument/definition", "line": 4, "character": 9},
        {
            "action": "query",
            "uri": doc_a,
            "method": "textDocument/references",
            "line": 2,
            "character": 21,
            "include_declaration": True,
        },
        {"action": "query", "uri": doc_a, "method": "textDocument/formatting"},
        {"action": "cancel", "id": 77},
        # Multi-change sequential ranged edit batch:
        {
            "action": "change",
            "uri": doc_a,
            "version": 2,
            "changes": [
                {
                    "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}},
                    "text": "// inserted 0\n",
                },
                {
                    "range": {"start": {"line": 1, "character": 0}, "end": {"line": 1, "character": 0}},
                    "text": "// inserted 1\n",
                },
            ],
        },
        {"action": "query", "uri": doc_a, "method": "textDocument/definition", "line": 6, "character": 9},
        {"action": "invalidate", "method": "workspace/didChangeConfiguration"},
        {"action": "save", "uri": doc_a},
        # Invalid later edit rolls back earlier edit and marks document desynchronized:
        {
            "action": "change",
            "uri": doc_a,
            "version": 3,
            "changes": [
                {
                    "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}},
                    "text": "// uncommitted\n",
                },
                {
                    "range": {"start": {"line": 99, "character": 0}, "end": {"line": 99, "character": 1}},
                    "text": "out of bounds",
                },
            ],
        },
        # Queries while desynchronized must refuse with -32801 and never expose prior facts:
        {"action": "query", "uri": doc_a, "method": "textDocument/hover", "line": 4, "character": 11},
        {"action": "query", "uri": doc_a, "method": "textDocument/documentSymbol"},
        {"action": "query", "uri": doc_a, "method": "textDocument/formatting"},
        # Full replacement with strictly newer version recovers synchronization:
        {
            "action": "change",
            "uri": doc_a,
            "version": 4,
            "changes": [{"text": error_text}],
        },
        {"action": "query", "uri": doc_a, "method": "textDocument/documentSymbol"},
        {"action": "close", "uri": doc_a},
        # Closed document queries must refuse with -32602:
        {"action": "query", "uri": doc_a, "method": "textDocument/documentSymbol"},
        # Reopen with fresh version:
        {"action": "open", "uri": doc_a, "version": 1, "text": valid_text},
        {"action": "query", "uri": doc_a, "method": "textDocument/documentSymbol"},
    ]

    with patch("subprocess.run", side_effect=AssertionError("overlay stub launched a subprocess")):
        replay_overlay_trace(trace)


def _pure_formatting_template_oracle() -> None:
    templates = (
        FormatTemplate(
            module_name="FormatMod",
            header_comment="// 😀 header comment",
            doc_comment="/// Computes the bounded value.",
            detach_doc=False,
            const_decl=("Nat", "BaseLimit", "1_000"),
            fn_name="Compute",
            param_name="input",
            local_name="localVal",
            operator="+",
            literal="42",
            inline_comment="// inline 😀",
            newline="\r\n",
            indent_spaces=2,
            inner_spaces=3,
        ),
        FormatTemplate(
            module_name="DetachedDoc",
            header_comment=None,
            doc_comment="/// Detached by following blank line.",
            detach_doc=True,
            const_decl=("bool", "Enabled", "true"),
            fn_name="Evaluate",
            param_name="count",
            local_name="stepVal",
            operator="/",
            literal="1_000",
            inline_comment=None,
            newline="\r",
            indent_spaces=0,
            inner_spaces=2,
        ),
    )
    for tmpl in templates:
        verify_format_template(tmpl)


def _seeded_faults_shrinking_and_mutation_vocabulary() -> None:
    # Unmutated baseline must pass every nonminimal fault trace.
    for fault_name, trace in NONMINIMAL_FAULT_TRACES.items():
        execute_explicit_case(trace)
        survived_check = evaluate_seeded_fault(
            fault_name,
            runner=lambda: None,
        )
        ensure(
            survived_check["status"] == "survived",
            f"no-op runner should classify as survived, got {survived_check!r}",
        )

    # Synthetic unexecutable mutant must be classified as stillborn.
    stillborn_verdict = evaluate_seeded_fault("stillborn-mutant")
    ensure(
        stillborn_verdict["status"] == "stillborn",
        f"unexecutable mutant was not classified as stillborn: {stillborn_verdict!r}",
    )

    # All 3 required seeded defects must be executable, killed, shrunk, and replayed from explicit data.
    held_out_count = 0
    for fault_name in SEEDED_FAULTS:
        verdict = evaluate_seeded_fault(fault_name)
        ensure(
            verdict["status"] == "killed",
            f"seeded fault {fault_name} was not killed: {verdict!r}",
        )
        if verdict["held_out"]:
            held_out_count += 1
        init_size = cast("int", verdict["initial_complexity"])
        shrunk_size = cast("int", verdict["shrunk_complexity"])
        ensure(
            0 < shrunk_size < init_size,
            f"seeded fault {fault_name} did not shrink ({shrunk_size} vs {init_size})",
        )
        shrunk_case = cast("dict[str, object]", verdict["shrunk_case"])
        ensure(
            case_complexity(shrunk_case) == shrunk_size,
            f"shrunk case complexity mismatch for {fault_name}",
        )
        # Shrunk explicit case must pass on unmutated production code!
        execute_explicit_case(shrunk_case)

    ensure(
        held_out_count >= 1 and HELD_OUT_FAULT in SEEDED_FAULTS,
        "at least one seeded defect must remain held out from generator design",
    )


def _isolated_hypothesis_cli_qualification() -> None:
    with redirect_stdout(out := StringIO()), redirect_stderr(err := StringIO()):
        code = vela_cli.main([
            "generated-tests",
            "--seed",
            "20261107",
            "--max-examples",
            "16",
            "--step-count",
            "12",
            "--timeout",
            "60",
        ])
    ensure(code == 0 and not err.getvalue(), f"vela generated-tests failed: {err.getvalue()}")
    report = cast("dict[str, object]", json.loads(out.getvalue()))
    ensure(report.get("status") == "qualified-isolated", f"unexpected status: {report!r}")
    settings = cast("dict[str, object]", report["settings"])
    ensure(
        settings.get("database") is None and settings.get("derandomize") is True,
        f"campaign did not disable ambient database or enable derandomize: {settings!r}",
    )
    closure = cast("dict[str, object]", report["closure"])
    packages = cast("dict[str, dict[str, object]]", closure["packages"])
    for pkg, expected_ver in CANDIDATE_VERSIONS.items():
        pkg_info = packages.get(pkg, {})
        ensure(pkg_info.get("version") == expected_ver, f"wrong {pkg} version: {pkg_info!r}")
        ensure(
            pkg_info.get("license_sha256") == EXPECTED_LICENSE_SHA256[pkg][1],
            f"wrong license sha256 for {pkg}: {pkg_info!r}",
        )
    ensure(
        closure.get("hypothesis_native_sha256") in EXPECTED_NATIVE_SHA256,
        f"unrecognized _native binary sha256: {closure!r}",
    )
    subjects = cast("dict[str, dict[str, object]]", report["subjects"])
    for subj in ("source_coordinates", "synchronous_overlays", "supported_requests", "pure_formatting"):
        ensure(subjects.get(subj, {}).get("status") == "passed", f"subject {subj} failed: {subjects!r}")
    faults = cast("dict[str, dict[str, object]]", report["fault_controls"])
    for fault_name in SEEDED_FAULTS:
        f_verdict = faults.get(fault_name, {})
        ensure(
            f_verdict.get("status") == "killed"
            and cast("int", f_verdict.get("shrunk_complexity", 99))
            < cast("int", f_verdict.get("initial_complexity", 0)),
            f"fault {fault_name} not killed/shrunk in isolated campaign: {f_verdict!r}",
        )
    disposition = cast("dict[str, object]", report["adoption_disposition"])
    ensure(
        disposition.get("promote_to_ordinary_closure") is False,
        "MPL-2.0 candidate was marked for promotion into ordinary tool closure",
    )


def cases() -> list[Case]:
    return [
        Case("independent-coordinate-oracle-and-utf16-controls", _coordinate_oracle_and_utf16_controls),
        Case("independent-overlay-and-supported-request-model", _overlay_and_supported_requests_without_subprocess),
        Case("independent-pure-formatting-template-oracle", _pure_formatting_template_oracle),
        Case("seeded-fault-controls-shrinking-and-mutation-vocabulary", _seeded_faults_shrinking_and_mutation_vocabulary),
        Case("isolated-hypothesis-cli-qualification", _isolated_hypothesis_cli_qualification),
    ]
