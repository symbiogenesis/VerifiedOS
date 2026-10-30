# SPDX-License-Identifier: Apache-2.0
"""Shared probe printing and the unchanged independent RTL wire consumer."""

import argparse
import re
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import oracle, rtl_vectors
from vos.cli import rtl

ROOT = Path(__file__).resolve().parents[2]


def _typed_and_derived_inputs() -> None:
    text = oracle.printer_functions((rtl_vectors.PRINTERS[0],))
    ensure("function probe_dec(c : CapBits)" in text,
           "the printer lost its model-owned argument type")
    ensure('b1(t)' in text and 'hex_16(zero_extend(c))' in text,
           "derived tags and capability bits lost their distinct wire fields")
    ensure(text.index("let t : bool") < text.index('print_endline('),
           "a derived input was printed before being computed")


def _refuses_invalid_printers() -> None:
    sample = rtl_vectors.PRINTERS[0]
    invalid = (
        (), (sample, sample), (replace(sample, kind="DEC"),),
        (replace(sample, arguments=(("inc", "CapBits"),)),),
        (replace(sample, arguments=(("c", ""),)),),
        (replace(sample, arguments=(("c", "CapBits"), ("c", "CapBits"))),),
        (replace(sample, shows=()),),
        (replace(sample, shows=(oracle.Show("", "h1"),)),),
        (replace(sample, shows=(oracle.Show("c", "unknown"),)),),
        (replace(sample, body=("let c = other;",)),),
    )
    for printers in invalid:
        try:
            oracle.printer_functions(printers)
        except oracle.SpecError:
            continue
        raise AssertionError(f"malformed printer declarations were accepted: {printers!r}")


def _wire_shapes_match_independent_consumer() -> None:
    bench = (ROOT / rtl.HARNESS).read_text(encoding="utf-8")
    shapes = dict(re.findall(r'\$fwrite\(fd_out, "([a-z]+) ([^"\n]+)\\n"', bench))
    ensure(set(shapes) == {printer.kind for printer in rtl_vectors.PRINTERS},
           "the typed questions and independent consumer carry different kinds")
    for printer in rtl_vectors.PRINTERS:
        inputs, outputs = shapes[printer.kind].split(" -> ")
        ensure(inputs.split() == ["%x"] * len(printer.inputs),
               f"{printer.kind}: input field count differs from the consumer")
        ensure(outputs.split() == ["%x"] * len(printer.shows),
               f"{printer.kind}: answer field count differs from the consumer")


def _campaign_reuses_mechanics_and_emits_deterministically() -> None:
    text = rtl_vectors.harness(ROOT)
    ensure(text == rtl_vectors.harness(ROOT), "campaign emission is not deterministic")
    ensure(text.count("function lfsr36(") == 1, "the shift register has multiple owners")
    for printer in rtl_vectors.PRINTERS:
        ensure(text.count(f"function probe_{printer.kind}(") == 1,
               f"{printer.kind}: missing or duplicated printer")
    domain = (ROOT / rtl_vectors.CAMPAIGN).read_text(encoding="utf-8")
    ensure("print_endline(\n" not in domain,
           "the authored domain still carries model-answer printing")
    ensure("function lfsr36" not in domain and "function nib(" not in domain,
           "the domain duplicated shared generation mechanics")


def _refuses_bad_domain_boundary() -> None:
    for domain in ("", rtl_vectors.SPLIT * 2):
        with sandbox_tree({rtl_vectors.CAMPAIGN: domain}) as root:
            try:
                rtl_vectors.harness(root)
            except oracle.SpecError:
                continue
            raise AssertionError("a missing or repeated campaign boundary was accepted")


def _generation_failure_precedes_native_build() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as temporary:
        root = Path(temporary)
        with (patch.object(rtl.env, "load"), patch.object(rtl, "find_root", return_value=root),
              patch.object(rtl, "_equiv_dir", return_value=root),
              patch.object(rtl.sailrig, "build") as build):
            code = rtl.cmd_vectors(argparse.Namespace())
        ensure(code == 1 and not build.called,
               "generation failure launched a build or supplied passing evidence")


def cases() -> list[Case]:
    return [
        Case("model argument types and derived input tags survive printing",
             _typed_and_derived_inputs),
        Case("malformed typed printers fail before emitting a harness", _refuses_invalid_printers),
        Case("wire fields match the independently authored RTL consumer",
             _wire_shapes_match_independent_consumer),
        Case("campaign emission shares mechanics and is deterministic",
             _campaign_reuses_mechanics_and_emits_deterministically),
        Case("missing and repeated domain boundaries are refused", _refuses_bad_domain_boundary),
        Case("generation failures stop before native builds", _generation_failure_precedes_native_build),
    ]
