# SPDX-License-Identifier: Apache-2.0
"""Independent bounded-emission controls for specialization and publication."""

import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import vela
from vos.cli import vela as cli

INDEPENDENT_CASES = True


def _expanding_source(levels: int = 5) -> str:
    source = "module Bound;\npublic Nat F0(const Nat k, Nat x) => x + x;\n"
    return source + "".join(
        f"public Nat F{index}(const Nat k, Nat x) => F{index - 1}(k, x) + F{index - 1}(k, x);\n"
        for index in range(1, levels + 1))


def _refuses(source: str, bound: int) -> vela.VelaError:
    with patch.object(vela, "MAX_OUTPUT_BYTES", bound):
        try:
            vela.translate(source.encode())
        except vela.VelaError as error:
            ensure(error.kind == "limit" and "output byte budget" in error.message,
                   f"emission did not stop at its bound: {error.kind}: {error.message}")
            return error
    raise AssertionError("emission exceeded its byte bound")


def _exact_complete_output_bound() -> None:
    source = "// Unicode comment 😀 is not emitted.\nmodule Bound; public Nat One() => 1;"
    expected = vela.translate(source.encode())
    size = len(expected.gallina.encode())
    with patch.object(vela, "MAX_OUTPUT_BYTES", size):
        ensure(vela.translate(source.encode()) == expected,
               "exact output bound changed admitted bytes or source provenance")
    _refuses(source, size - 1)


def _cumulative_definitions_stop_at_the_limit() -> None:
    prefix = "module Bound;\npublic Nat One() => 1;\n"
    budget = len(vela.translate(prefix.encode()).gallina.encode())
    source = prefix + "public Nat Two() => 2;\npublic Nat Later() => Missing();\n"
    error = _refuses(source, budget)
    ensure((error.line, error.column) == (3, 12),
           "cumulative emission bound was not located at the overflowing declaration")


def _specialization_and_wide_siblings_stop_early() -> None:
    source = _expanding_source() + "public Nat Run(Nat x) => F5(1, x);\n"
    ensure(len(vela.translate(_expanding_source().encode()).gallina) < 4096,
           "symbolic fixture already exceeds the selected bound")
    error = _refuses(source, 4096)
    ensure((error.line, error.column) == (7, 47),
           "specialization did not locate the expanding source expression")

    # Every closed F2 call expands, despite its short source spelling. Retained
    # siblings must exhaust the budget before checking a later invalid actual.
    parameters = ", ".join(f"Nat p{index}" for index in range(32))
    source = (_expanding_source(2) + f"public Nat First({parameters}) => p0;\n"
              + "public Nat Run(Nat x) => First("
              + ", ".join(["F2(1, x)"] * 31 + ["Missing()"])
              + ");\n")
    error = _refuses(source, 4096)
    ensure((error.line, error.column) == (6, 26),
           "wide specialization did not stop at the overflowing application")


def _oversized_specialization_preserves_publication() -> None:
    source_bytes = (_expanding_source() + "public Nat Run(Nat x) => F5(1, x);\n").encode()
    with tempfile.TemporaryDirectory(prefix="vos-vela-emission-limit-") as directory:
        root = Path(directory)
        source, output = root / "source.vela", root / "output.v"
        source.write_bytes(source_bytes)
        output.write_bytes(b"previous generated artifact")
        with (patch.object(vela, "MAX_OUTPUT_BYTES", 4096),
              redirect_stdout(stdout := StringIO()), redirect_stderr(stderr := StringIO())):
            code = cli.main(["emit", str(source), "--output", str(output)])
        ensure(code == 1 and not stdout.getvalue() and ": limit:" in stderr.getvalue(),
               "oversized specialization was not reported as a failed emission")
        ensure(source.read_bytes() == source_bytes and output.read_bytes() == b"previous generated artifact",
               "oversized specialization changed source or previous output")
        ensure(not list(root.glob(".*.tmp")), "refused emission leaked pending publication files")


def cases() -> list[Case]:
    return [Case("exact-complete-emission-byte-bound", _exact_complete_output_bound),
            Case("cumulative-definitions-stop-before-later-work", _cumulative_definitions_stop_at_the_limit),
            Case("specialization-and-wide-argument-bounds", _specialization_and_wide_siblings_stop_early),
            Case("bounded-specialization-refuses-before-publication", _oversized_specialization_preserves_publication)]
