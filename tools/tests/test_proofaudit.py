# SPDX-License-Identifier: Apache-2.0
"""Assumption omissions, misleading claims, stale dependencies and native evidence."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import proofaudit, proofcites, proofs, receipts
from vos.cli import evidence
from vos.cli import proofs as gate

# What `rocqchk -silent -o` writes to stderr for a clean environment, byte for byte as
# the pinned Rocq 9.2 writes it.
KERNEL_CLEAN = ("\nCONTEXT SUMMARY\n===============\n\n* Theory: Set is predicative\n  \n"
                "* Theory: Rewrite rules are not allowed\n  \n* Axioms: <none>\n  \n"
                "* Constants/Inductives relying on type-in-type: <none>\n  \n"
                "* Constants/Inductives relying on unsafe (co)fixpoints: <none>\n  \n"
                "* Inductives whose positivity is assumed: <none>\n  \n")
_LOADED_AXIOM = KERNEL_CLEAN.replace(
    "* Axioms: <none>\n", "* Axioms:\n    Stdlib.Logic.Eqdep.Eq_rect_eq.eq_rect_eq\n    M.a\n")
# Rocq 9.3 appends one section, written here byte for byte as it follows the others for
# a module whose environment is the prelude alone.
_INDICES = ("* Inductives relying on indices not mattering:\n"
            "    Corelib.Init.Datatypes.eq_true\n    Corelib.Init.Logic.eq\n  \n")
KERNEL_CLEAN_93 = KERNEL_CLEAN + _INDICES


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


def _kernel_context_is_exact() -> None:
    ensure(proofaudit.kernel_context(KERNEL_CLEAN) == [], "a clean summary names no axiom")
    ensure(proofaudit.kernel_context(_LOADED_AXIOM)
           == ["Stdlib.Logic.Eqdep.Eq_rect_eq.eq_rect_eq", "M.a"], "every loaded axiom is named")
    none = KERNEL_CLEAN + "* Inductives relying on indices not mattering: <none>\n  \n"
    for summary in (KERNEL_CLEAN_93, none):
        ensure(proofaudit.kernel_context(summary) == [],
               "the indices section of the fixed theory refused a clean summary")
    ensure(proofaudit.kernel_context(_LOADED_AXIOM + _INDICES)
           == ["Stdlib.Logic.Eqdep.Eq_rect_eq.eq_rect_eq", "M.a"],
           "the indices section hid a loaded axiom")
    refused = [
        KERNEL_CLEAN_93.replace("not mattering:\n", "not mattering: <none>\n"),
        KERNEL_CLEAN + "* Inductives relying on indices not mattering:\n  \n",
        KERNEL_CLEAN_93.replace("    Corelib.Init.Logic.eq\n", "    Fatal Error: unexpected\n"),
        KERNEL_CLEAN_93 + _INDICES,
        KERNEL_CLEAN_93 + "* Constants relying on a new assumption: <none>\n",
        KERNEL_CLEAN.replace("* Inductives whose positivity", _INDICES + "* Inductives whose positivity"),
        KERNEL_CLEAN_93.replace("positivity is assumed: <none>", "positivity is assumed:\n    M.Bad"),
        "",
        KERNEL_CLEAN.replace("unsafe (co)fixpoints: <none>", "unsafe (co)fixpoints:\n    M.f"),
        KERNEL_CLEAN.replace("positivity is assumed: <none>", "positivity is assumed:\n    M.Bad"),
        KERNEL_CLEAN.replace("type-in-type: <none>", "type-in-type:\n    M.U"),
        KERNEL_CLEAN.replace("Rewrite rules are not allowed", "Rewrite rules are allowed"),
        KERNEL_CLEAN.replace("Set is predicative", "Set is impredicative"),
        KERNEL_CLEAN.replace("* Axioms: <none>\n", "* Axioms:\n"),
        KERNEL_CLEAN.replace("* Axioms: <none>\n", ""),
        KERNEL_CLEAN + "* Constants relying on a new assumption: <none>\n",
        KERNEL_CLEAN + "Fatal Error: unexpected\n"]
    for summary in refused:
        try:
            proofaudit.kernel_context(summary)
        except proofaudit.AuditError:
            continue
        raise AssertionError(f"an unclean or unrecognized kernel summary passed: {summary!r}")


def _kernel_verdict_needs_a_clean_summary() -> None:
    def fault(code: int, stdout: str, stderr: str) -> str:
        return gate._kernel_fault(subprocess.CompletedProcess([], code, stdout=stdout, stderr=stderr))

    ensure(fault(0, "", KERNEL_CLEAN) == "", "a clean kernel run was refused")
    ensure(fault(0, "", KERNEL_CLEAN_93) == "", "a clean Rocq 9.3 kernel run was refused")
    ensure("eq_rect_eq" in fault(0, "", _LOADED_AXIOM), "a loaded but unused axiom passed")
    for code, stdout, stderr in ((1, "", KERNEL_CLEAN), (0, "chatter", KERNEL_CLEAN),
                                 (0, "", ""), (0, "", "Fatal Error: Type error")):
        ensure(bool(fault(code, stdout, stderr)),
               f"kernel run without a clean verdict passed: {code} {stdout!r} {stderr!r}")
    with patch.object(gate, "DECLARED", {"Stdlib.Logic.Eqdep.Eq_rect_eq.eq_rect_eq : Prop",
                                         "M.a : False"}):
        ensure(fault(0, "", _LOADED_AXIOM) == "", "a declared axiom was refused by name")


def _pinned_settings_cannot_be_overridden() -> None:
    refused = ('Set Warnings "-all".', 'Local Set Warnings "-notation-overridden".',
               '#[local] Set Default Goal Selector "1".', 'Global Unset Guard Checking.',
               "Unset Positivity Checking.", "Unset Universe Checking.",
               "Set Definitional UIP.", "Set Allow StrictProp.", 'Set Bullet Behavior "None".',
               "Set Nested Proofs Allowed.", "Unset Strict Universe Declaration.",
               "Set Default Timeout 5.", "Fail Timeout 1 Check 0.",
               "Set Indices Matter.", "Local Unset Indices Matter.",
               "Proof. Unset Guard Checking. exact I. Qed.",
               "#[bypass_check(guard)] Fixpoint f (n : nat) : nat := f n.",
               '#[warnings="-non-recursive"] Fixpoint f (n : nat) : nat := 0.')
    for text in refused:
        ensure(bool(proofaudit.pinned_overrides(text)), f"a pinned-setting override passed: {text}")
    allowed = ("Set Implicit Arguments.", "Local Open Scope nat_scope.", "Set Printing Width 80.",
               '(* Set Warnings "-all". *) Definition x := 0.',
               'Definition label := "Set Warnings".', "#[local] Arguments id {A} x.",
               "Definition timeout_bound := 5.")
    for text in allowed:
        ensure(not proofaudit.pinned_overrides(text), f"an unpinned sentence was refused: {text}")


def _nested_sources_cannot_be_omitted() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-nested-proof-") as temporary:
        root = Path(temporary)
        folder = root / "proofs"
        (folder / "nested").mkdir(parents=True)
        (folder / "ApexTheorem.v").write_text("", encoding="utf-8")
        (folder / "nested" / "Hidden.v").write_text("Axiom hidden : False.", encoding="utf-8")
        work = root / "output"
        receipts.write(work / gate.RECEIPT, {"schema": gate.RECEIPT_SCHEMA, "status": "passed"})
        with patch.object(gate, "workspace", return_value=work), \
                patch.object(gate, "_hold", side_effect=lambda _: os.open(os.devnull, os.O_RDONLY)), \
                contextlib.redirect_stdout(io.StringIO()):
            ensure(gate._run(root, 2) == 1, "nested source silently escaped the proof run")
            ensure(gate._status(root) == 1, "nested source silently escaped receipt validation")


def _parallel_wave_blocks_stale_dependents() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-proof-wave-") as temporary:
        root = Path(temporary)
        folder = root / "proofs"
        folder.mkdir()
        work = root / "output"
        staged_folder = work / "proofs"
        staged_folder.mkdir(parents=True)
        for name, text in {"ApexTheorem": "Require Bad.", "Bad": "", "Good": ""}.items():
            (folder / f"{name}.v").write_text(text, encoding="utf-8")
            (folder / f"{name}.vo").write_bytes(b"previous-run")
            (staged_folder / f"{name}.vo").write_bytes(b"previous-run")
        barrier = threading.Barrier(2, timeout=5)
        called: list[str] = []

        def check(_root: Path, source: Path, _sources: list[Path]) -> gate.Checked:
            called.append(source.stem)
            ensure(_root == work and source.parent == staged_folder,
                   "the compiler must receive the native staging area")
            ensure(not source.with_suffix(".vo").exists(), "stale .vo survived into this wave")
            barrier.wait()
            return gate.Checked(source, error="seeded compile failure" if source.stem == "Bad" else "")

        with patch.object(gate, "workspace", return_value=work), \
                patch.object(gate, "_inputs", side_effect=receipts.snapshot), \
                patch.object(gate, "_toolchain", return_value={}), \
                patch.object(gate, "_cache_context", return_value={}), \
                patch.object(gate, "_hold", side_effect=lambda _: os.open(os.devnull, os.O_RDONLY)), \
                patch.object(gate, "_check_source", side_effect=check), \
                contextlib.redirect_stdout(io.StringIO()):
            result = gate._run(root, 2)
        ensure(result == 1 and set(called) == {"Bad", "Good"},
               "independent sources run concurrently and failed dependencies block consumers")
        ensure(not (staged_folder / "ApexTheorem.vo").exists(),
               "blocked consumer retained stale evidence")
        ensure((folder / "ApexTheorem.vo").read_bytes() == b"previous-run",
               "the gate must neither consume nor delete legacy checkout outputs")


def _staged_run_binds_original_inputs() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-proof-staging-") as temporary:
        root = Path(temporary) / "source"
        folder = root / "proofs"
        folder.mkdir(parents=True)
        source = folder / "ApexTheorem.v"
        original = "Theorem sound : True. Proof. exact I. Qed.\n"
        work = Path(temporary) / "output"
        work.mkdir()
        copying = shutil.copyfile
        for phase in ("copy", "compile", "addition", "staged"):
            source.write_text(original, encoding="utf-8")
            (folder / "Added.v").unlink(missing_ok=True)

            def copy(src: Path, dst: Path, phase: str = phase) -> Path:
                if phase == "copy":
                    src.write_text(original + "(* changed before copy *)", encoding="utf-8")
                return copying(src, dst)

            def check(_root: Path, staged: Path, _sources: list[Path],
                      phase: str = phase) -> gate.Checked:
                ensure(staged.read_text(encoding="utf-8") == original,
                       "the compiler must consume the captured original")
                staged.with_suffix(".vo").write_bytes(b"compiled")
                if phase == "compile":
                    source.write_text(original + "(* changed while compiling *)", encoding="utf-8")
                elif phase == "addition":
                    (folder / "Added.v").write_text("Definition added := 1.", encoding="utf-8")
                elif phase == "staged":
                    staged.write_text(original + "(* changed staging *)", encoding="utf-8")
                return gate.Checked(staged, symbols=[{
                    "name": "ApexTheorem.sound", "type": "True", "claims": [], "assumptions": []}])

            with patch.object(gate, "workspace", return_value=work), \
                    patch.object(gate, "_inputs", side_effect=receipts.snapshot), \
                    patch.object(gate, "_toolchain", return_value={}), \
                    patch.object(gate, "_cache_context", return_value={}), \
                    patch.object(gate, "_hold", side_effect=lambda _: os.open(os.devnull, os.O_RDONLY)), \
                    patch.object(gate.shutil, "copyfile", side_effect=copy), \
                    patch.object(gate, "_check_source", side_effect=check), \
                    patch.object(gate, "_recheck", return_value=subprocess.CompletedProcess(
                        [], 0, stdout="", stderr=KERNEL_CLEAN)), \
                    contextlib.redirect_stdout(io.StringIO()):
                ensure(gate._run(root, 1) == 1, f"{phase} mutation produced successful evidence")
            ensure(not (work / gate.RECEIPT).exists(), "a failed run left a success receipt")
            ensure(not source.with_suffix(".vo").exists(), "the gate wrote to the input directory")


def _workspace_is_lane_native() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-proof-layout-") as temporary:
        root = Path(temporary) / "source"
        root.mkdir()
        (root / ".git").write_text("gitdir: C:/repo/.git/worktrees/first\n", encoding="utf-8")
        native = Path("/root/build/proof-layout-fixture").resolve()
        with patch.dict(os.environ, {"VOS_BUILD_ROOT": str(native)}, clear=True), \
                patch.object(gate.env, "filesystem", return_value="ext4"):
            first = gate.workspace(root)
            (root / ".git").write_text("gitdir: C:/repo/.git/worktrees/second\n", encoding="utf-8")
            second = gate.workspace(root)
            ensure(first == native / "lane-first" / "proof-gate"
                   and second == native / "lane-second" / "proof-gate",
                   "proof workspaces must follow the Git worktree identity")
            for path, filesystem in ((root, "ext4"), (native, "9p"), (native, "tmpfs")):
                with patch.dict(os.environ, {"VOS_BUILD_ROOT": str(path)}), \
                        patch.object(gate.env, "filesystem", return_value=filesystem):
                    try:
                        gate.workspace(root)
                    except ValueError:
                        continue
                    raise AssertionError("a checkout, cross-OS or volatile output was accepted")


def _native_gate_regressions() -> None:
    """The actual compiler and kernel rechecker, in an isolated guest directory.

    Program is Corelib's alone: Stdlib's Program closure declares three axioms, which
    the kernel summary refuses even unused, so the obligation is discharged by hand.
    """
    positive = ("Module N.\n"
                "Local Lemma hidden_subproof : True. Proof. exact I. Qed.\nEnd N.\n"
                "Record Load := { level : nat }.\n"
                "Program Definition bounded : { n : nat | n = 0 } := 0.\n"
                "Next Obligation. reflexivity. Qed.\n")
    # Each refusal with the diagnostic that must carry it, so that none passes for
    # another reason. Rocq 9.2's Print Assumptions misses the type-only axiom.
    bad = [("Theorem good : True. Proof. exact I. Qed.\nPrint Assumptions good.\n"
            "Axiom injected : False. Theorem bad : False. Proof. exact injected. Qed.\n",
            "undeclared assumptions"),
           ("Theorem unchecked : False. Proof. Admitted.\n", "undeclared assumptions"),
           ("(*| discharges: R-05-163 |*)\nTheorem term : nat. Proof. exact 0. Qed.\n",
            "Assumptions failed"),
           ("Program Definition impossible : { n : nat | False } := 0.\n"
            "Next Obligation. Admitted.\n", "undeclared assumptions"),
           ("From Stdlib Require Import FunctionalExtensionality.\n"
            "Definition t : (fun _ => True) (@functional_extensionality_dep) := I.\n",
            "functional_extensionality_dep"),
           ("Theorem both : True /\\ True.\nProof. split. exact I. exact I. Qed.\n",
            "single focused goal"),
           ("Fixpoint idle (n : nat) : nat := 0.\n", "non-recursive"),
           ('Set Warnings "-non-recursive".\nFixpoint idle (n : nat) : nat := 0.\n',
            "pinned settings"),
           ("Inductive squashed : SProp := squash.\n", "StrictProp")]
    lane = gate.workspace(Path(__file__).resolve().parents[2])
    lane.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-test-", dir=lane) as temporary:
        root = Path(temporary) / "sources"
        root.mkdir()
        work = Path(temporary) / "output"
        (root / "proofs").mkdir()
        source = root / "proofs" / "ApexTheorem.v"
        with patch.object(gate, "workspace", return_value=work), \
                patch.object(gate, "_inputs", side_effect=receipts.snapshot):
            source.write_text(positive, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                result = gate._run(root, 2)
            ensure(result == 0, "native local/generated proof without an authored footer must pass")
            ensure(not source.with_suffix(".vo").exists(), "guest compile wrote into its inputs")
            record = json.loads(gate.receipt_path(root).read_text(encoding="utf-8"))
            ensure(record.get("cache_context") is not None,
                   "the pinned native toolchain must have a reusable content identity")
            with patch.object(gate, "_compile", side_effect=AssertionError("unexpected compile")), \
                    patch.object(gate, "_recheck", side_effect=AssertionError("unexpected recheck")), \
                    contextlib.redirect_stdout(io.StringIO()):
                ensure(gate._run(root, 2) == 0, "identical native run did not reuse kernel evidence")
            names = [symbol["name"] for symbol in record["artifacts"][source.name]["symbols"]]
            ensure("ApexTheorem.bounded_obligation_1" in names
                   and "ApexTheorem.N.hidden_subproof" in names,
                   "native inventory omitted local or generated constants")
            with contextlib.redirect_stdout(io.StringIO()):
                ensure(gate._status(root) == 0, "fresh native evidence should be reusable")
                exported = evidence._proof_record(root)
                ensure(exported["receipt"] == record
                       and exported["sha256"] == receipts.digest(gate.receipt_path(root)),
                       "the evidence consumer must lock and read the relocated receipt")
                staged = work / "proofs" / source.name
                staged.write_text(positive + "\n(* altered staged source *)\n", encoding="utf-8")
                ensure(gate._status(root) == 1, "staged source change must invalidate evidence")
                staged.write_text(positive, encoding="utf-8")
                compiled = staged.with_suffix(".vo")
                saved = compiled.read_bytes()
                compiled.write_bytes(saved + b"modified")
                ensure(gate._status(root) == 1, "compiled output change must invalidate evidence")
                compiled.write_bytes(saved)
                source.write_text(positive + "\n(* moved *)\n", encoding="utf-8")
                ensure(gate._status(root) == 1, "source change must invalidate native evidence")
            for text, diagnostic in bad:
                source.write_text(text, encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()) as said:
                    ensure(gate._run(root, 2) == 1, f"a refused source passed: {text!r}")
                ensure(diagnostic in said.getvalue(),
                       f"{text!r} was refused without {diagnostic!r}: {said.getvalue()}")


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
            Case("kernel-context-is-exact", _kernel_context_is_exact),
            Case("kernel-verdict-needs-a-clean-summary", _kernel_verdict_needs_a_clean_summary),
            Case("pinned-settings-cannot-be-overridden", _pinned_settings_cannot_be_overridden),
            Case("nested-sources-cannot-be-omitted", _nested_sources_cannot_be_omitted),
            Case("parallel-wave-blocks-stale-dependents", _parallel_wave_blocks_stale_dependents),
            Case("staged-run-binds-original-inputs", _staged_run_binds_original_inputs),
            Case("workspace-is-lane-native", _workspace_is_lane_native),
            Case("release-version-banner-is-exact", _release_version_banner_is_exact),
            Case("native-proof-gate-regressions", _native_gate_regressions, lane="toolchain")]
