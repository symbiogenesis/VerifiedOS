# SPDX-License-Identifier: Apache-2.0
"""Assumption omissions, misleading claims, stale dependencies and native evidence."""

import contextlib
import io
import json
import os
import subprocess
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import proofaudit, proofcites, proofs, receipts
from vos.cli import proofs as gate


def _inventory_filters_and_framing() -> None:
    valid = (proofaudit.EMPTY_BLACKLIST + "\nM.f: nat\n"
             "M.generated_obligation_1: True\nM.N.local_subproof: True\n")
    symbols = proofaudit.inventory(valid, "M")
    ensure(len(symbols) == 3, "native nested and generated symbols are retained")
    bad = [valid.replace(proofaudit.EMPTY_BLACKLIST, 'Current search blacklist : "secret".'),
           valid + "diagnostic chatter\n", valid + "M.f: nat\n",
           valid + "Other.hidden: False\n"]
    for output in bad:
        try:
            proofaudit.inventory(output, "M")
        except proofaudit.AuditError:
            continue
        raise AssertionError(f"incomplete or filtered inventory passed: {output!r}")


def _every_query_needs_one_answer() -> None:
    symbols = proofaudit.inventory(proofaudit.EMPTY_BLACKLIST + "\nM.a: True\nM.b: True\n", "M")
    marker = proofaudit.MARKER
    valid = f"{marker}M.a\nClosed under the global context\n{marker}M.b\nAxioms:\nM.x : False\n"
    proofaudit.assumptions(valid, symbols)
    ensure(symbols[1]["assumptions"] == ["M.x : False"], "native axioms survive parsing")
    for output in (valid.split(f"{marker}M.b", maxsplit=1)[0], valid + f"{marker}M.a\n",
                   valid.replace("Axioms:", "unrecognized result:")):
        try:
            proofaudit.assumptions(output, symbols)
        except proofaudit.AuditError:
            continue
        raise AssertionError("missing, repeated or malformed native result passed")


def _claims_need_real_declarations() -> None:
    annotation = "(*| discharges: R-05-163 |*)\nTheorem ghost : True.\n"
    for text in (f"(* outside\n{annotation}*)", f'"{annotation}"'):
        found, faults = proofcites.discharges(text)
        ensure(not found and bool(faults), "commented/string claims cannot enter the ledger")
    symbols = proofaudit.inventory(proofaudit.EMPTY_BLACKLIST + "\nM.real: True\n", "M")
    try:
        proofaudit.bind_claims(annotation, symbols)
    except proofaudit.AuditError:
        pass
    else:
        raise AssertionError("claim for a nonexistent compiled symbol passed")
    derived = f"(* prose\n{proofcites.DERIVED_BEGIN}\n**R-05-163** MUST hold.\n{proofcites.DERIVED_END}\n*)"
    ensure(proofcites.discharges(derived) == ([], []), "generated headers are not discharge claims")


def _requires_follow_vernacular() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-requires-") as temporary:
        source = Path(temporary) / "M.v"
        source.write_text("(* Require Fake. *)\nFrom Stdlib Require Import List.\n"
                          "Require\n Import Real.\n", encoding="utf-8")
        ensure(proofs.local_requires(source, {"Fake", "List", "Real"}) == {"Real"},
               "comments and library namespaces must not create local dependencies")


def _claim_names_resolve_uniquely_across_nested_modules() -> None:
    annotation = "(*| discharges: R-05-163 |*)\nTheorem claim : True.\n"
    symbols = proofaudit.inventory(
        proofaudit.EMPTY_BLACKLIST + "\nM.N.claim: True\nM.other_claim: True\n", "M")
    proofaudit.bind_claims(annotation, symbols)
    ensure(symbols[0]["claims"] == ["R-05-163"] and not symbols[1]["claims"],
           "the claim must bind its exact leaf name inside a nested module")
    ambiguous = proofaudit.inventory(
        proofaudit.EMPTY_BLACKLIST + "\nM.N.claim: True\nM.claim: True\n", "M")
    for candidates, count in ((symbols, "more than one discharge"), (ambiguous, "2 native symbols")):
        try:
            proofaudit.bind_claims(annotation, candidates)
        except proofaudit.AuditError as err:
            ensure(count in str(err), f"claim uniqueness refusal changed: {err}")
        else:
            raise AssertionError("an ambiguous or repeated claim was accepted")


def _unqualified_native_names_cannot_bind_claims() -> None:
    annotation = "(*| discharges: R-05-163 |*)\nTheorem claim : True.\n"
    unqualified: proofaudit.Symbol = {
        "name": "claim", "type": "True", "assumptions": [], "claims": []}
    try:
        proofaudit.bind_claims(annotation, [unqualified])
    except proofaudit.AuditError as err:
        ensure("0 native symbols" in str(err), f"unqualified-name refusal changed: {err}")
    else:
        raise AssertionError("an unqualified native name bound a discharge claim")
    qualified = proofaudit.inventory(
        proofaudit.EMPTY_BLACKLIST + "\nM.claim: True\n", "M")
    proofaudit.bind_claims(annotation, [unqualified, *qualified])
    ensure(not unqualified["claims"] and qualified[0]["claims"] == ["R-05-163"],
           "an unqualified name must neither receive nor make a valid claim ambiguous")


def _inaccessible_modules_fail_closed() -> None:
    ensure(not proofaudit.unsupported_abstractions("Module N. Definition x := 0. End N."),
           "ordinary nested modules are supported")
    for text in ("Module F (X : T).", "Module N : T.", "Module Type T."):
        ensure(bool(proofaudit.unsupported_abstractions(text)),
               "inaccessible module bodies cannot get partial evidence")


def _nested_sources_cannot_be_omitted() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-nested-proof-") as temporary:
        root = Path(temporary)
        folder = root / "proofs"
        (folder / "nested").mkdir(parents=True)
        (folder / "ApexTheorem.v").write_text("", encoding="utf-8")
        (folder / "nested" / "Hidden.v").write_text("Axiom hidden : False.", encoding="utf-8")
        receipts.write(root / gate.RECEIPT, {"schema": gate.RECEIPT_SCHEMA, "status": "passed"})
        with patch.object(gate, "_hold", side_effect=lambda _: os.open(os.devnull, os.O_RDONLY)), \
                contextlib.redirect_stdout(io.StringIO()):
            ensure(gate._run(root, 2) == 1, "nested source silently escaped the proof run")
            ensure(gate._status(root) == 1, "nested source silently escaped receipt validation")


def _parallel_wave_blocks_stale_dependents() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-proof-wave-") as temporary:
        root = Path(temporary)
        folder = root / "proofs"
        folder.mkdir()
        for name, text in {"ApexTheorem": "Require Bad.", "Bad": "", "Good": ""}.items():
            (folder / f"{name}.v").write_text(text, encoding="utf-8")
            (folder / f"{name}.vo").write_bytes(b"previous-run")
        barrier = threading.Barrier(2, timeout=5)
        called: list[str] = []

        def check(_root: Path, source: Path, _sources: list[Path]) -> gate.Checked:
            called.append(source.stem)
            ensure(not source.with_suffix(".vo").exists(), "stale .vo survived into this wave")
            barrier.wait()
            return gate.Checked(source, error="seeded compile failure" if source.stem == "Bad" else "")

        with patch.object(gate, "_inputs", return_value={}), \
                patch.object(gate, "_toolchain", return_value={}), \
                patch.object(gate, "_hold", side_effect=lambda _: os.open(os.devnull, os.O_RDONLY)), \
                patch.object(gate, "_check_source", side_effect=check), \
                contextlib.redirect_stdout(io.StringIO()):
            result = gate._run(root, 2)
        ensure(result == 1 and set(called) == {"Bad", "Good"},
               "independent sources run concurrently and failed dependencies block consumers")
        ensure(not (folder / "ApexTheorem.vo").exists(), "blocked consumer retained stale evidence")


def _native_gate_regressions() -> None:
    """The actual compiler and kernel rechecker, in an isolated guest directory."""
    positive = ("From Stdlib Require Import Program.\nModule N.\n"
                "Local Lemma hidden_subproof : True. Proof. exact I. Qed.\nEnd N.\n"
                "Program Definition bounded : { n : nat | n = 0 } := 0.\n")
    bad = ["Theorem good : True. Proof. exact I. Qed.\nPrint Assumptions good.\n"
           "Axiom injected : False. Theorem bad : False. Proof. exact injected. Qed.\n",
           "Theorem unchecked : False. Admitted.\n",
           "(*| discharges: R-05-163 |*)\nTheorem term : nat. Proof. exact 0. Qed.\n",
           "From Stdlib Require Import Program.\n"
           "Program Definition impossible : { n : nat | False } := 0.\n"
           "Next Obligation. Admitted.\n"]
    with tempfile.TemporaryDirectory(prefix="vos-native-proof-test-") as temporary:
        root = Path(temporary)
        (root / "proofs").mkdir()
        source = root / "proofs" / "ApexTheorem.v"
        with patch.object(gate, "_inputs", side_effect=receipts.snapshot):
            source.write_text(positive, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                result = gate._run(root, 2)
            ensure(result == 0, "native local/generated proof without an authored footer must pass")
            record = json.loads((root / gate.RECEIPT).read_text(encoding="utf-8"))
            names = [symbol["name"] for symbol in record["artifacts"][source.name]["symbols"]]
            ensure("ApexTheorem.bounded_obligation_1" in names
                   and "ApexTheorem.N.hidden_subproof" in names,
                   "native inventory omitted local or generated constants")
            with contextlib.redirect_stdout(io.StringIO()):
                ensure(gate._status(root) == 0, "fresh native evidence should be reusable")
                source.write_text(positive + "\n(* moved *)\n", encoding="utf-8")
                ensure(gate._status(root) == 1, "source change must invalidate native evidence")
            for text in bad:
                source.write_text(text, encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()):
                    ensure(gate._run(root, 2) == 1,
                           "an unqueried axiom, admitted obligation or non-Prop claim passed")


def _release_version_banner_is_exact() -> None:
    """A missing zero patch is a release spelling, not permission for version drift."""
    samples = [("9.2.0", "9.2", True), ("9.2.0", "9.2.0", True),
               ("9.2.0", "9.2.1", False), ("9.2.0", "9.2+dev", False),
               ("9.2.0", "9.2~rc1", False), ("9.2.0", "9.1.1", False),
               ("9.2.1", "9.2", False), ("9.2.1", "9.2.1", True)]
    for pin, banner, accepted in samples:
        answer = subprocess.CompletedProcess(
            ["rocq", "c", "--version"], 0,
            stdout=f"The Rocq Prover, version {banner}\ncompiled with OCaml 5.4.1\n")
        with patch.object(gate.env, "ROCQ_VERSION", pin), \
                patch.object(gate.env, "rocq_command", return_value=["rocq", "c"]), \
                patch.object(gate.env, "rocqchk_command", return_value=["rocqchk"]), \
                patch.object(gate.subprocess, "run", return_value=answer), \
                patch.object(gate.receipts, "digest", return_value="fixture"):
            try:
                record = gate._toolchain()
            except proofaudit.AuditError:
                ensure(not accepted, f"release banner {banner} was refused for {pin}")
            else:
                ensure(accepted and record["pin"] == pin,
                       f"release banner {banner} incorrectly satisfied {pin}")


def cases() -> list[Case]:
    return [Case("native-inventory-filters-and-framing", _inventory_filters_and_framing),
            Case("every-native-query-needs-an-answer", _every_query_needs_one_answer),
            Case("claims-need-real-declarations", _claims_need_real_declarations),
            Case("claim-names-resolve-uniquely", _claim_names_resolve_uniquely_across_nested_modules),
            Case("unqualified-native-names-cannot-bind", _unqualified_native_names_cannot_bind_claims),
            Case("requires-follow-vernacular", _requires_follow_vernacular),
            Case("inaccessible-modules-fail-closed", _inaccessible_modules_fail_closed),
            Case("nested-sources-cannot-be-omitted", _nested_sources_cannot_be_omitted),
            Case("parallel-wave-blocks-stale-dependents", _parallel_wave_blocks_stale_dependents),
            Case("release-version-banner-is-exact", _release_version_banner_is_exact),
            Case("native-proof-gate-regressions", _native_gate_regressions, lane="toolchain")]
