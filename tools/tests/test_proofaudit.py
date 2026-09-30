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
# the pinned Rocq 9.3.0 writes it for a module whose environment is the prelude alone.
# The head alone is a summary that stops before the indices section, which the gate
# refuses.
_KERNEL_HEAD = ("\nCONTEXT SUMMARY\n===============\n\n* Theory: Set is predicative\n  \n"
                "* Theory: Rewrite rules are not allowed\n  \n* Axioms: <none>\n  \n"
                "* Constants/Inductives relying on type-in-type: <none>\n  \n"
                "* Constants/Inductives relying on unsafe (co)fixpoints: <none>\n  \n"
                "* Inductives whose positivity is assumed: <none>\n  \n")
_INDICES = ("* Inductives relying on indices not mattering:\n"
            "    Corelib.Init.Datatypes.eq_true\n    Corelib.Init.Logic.eq\n  \n")
KERNEL_CLEAN = _KERNEL_HEAD + _INDICES
_LOADED_AXIOM = KERNEL_CLEAN.replace(
    "* Axioms: <none>\n", "* Axioms:\n    Stdlib.Logic.Eqdep.Eq_rect_eq.eq_rect_eq\n    M.a\n")


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


def _prefixed_abstractions_fail_closed() -> None:
    # The pinned Rocq 9.3.0 compiles the Time forms; it refuses a local Module Type, which
    # is refused here too, loudly either way.
    for text in ("Time Module Type T.", "#[local] Module Type T.", "Local Module Type T.",
                 "Time Declare Module M : T.", "Succeed Module F (X : T).",
                 'Redirect "log" Module N : T.', "Time\n  Module Type T."):
        ensure(proofaudit.unsupported_abstractions(text) == [text.removesuffix(".")],
               f"a prefixed functor or signature escaped the refusal: {text!r}")
    # A prefix's own brackets and colon belong to no functor or signature.
    for text in ("#[universes(polymorphic)] Module N. End N.", 'Profile "a:b" Module N. End N.',
                 "Time Module Import N. End N.", "Module Types. End Types."):
        ensure(not proofaudit.unsupported_abstractions(text),
               f"an ordinary prefixed module was refused: {text!r}")


def _kernel_context_is_exact() -> None:
    ensure(proofaudit.kernel_context(KERNEL_CLEAN) == [], "a clean summary names no axiom")
    ensure(proofaudit.kernel_context(_LOADED_AXIOM)
           == ["Stdlib.Logic.Eqdep.Eq_rect_eq.eq_rect_eq", "M.a"], "every loaded axiom is named")
    none = _KERNEL_HEAD + "* Inductives relying on indices not mattering: <none>\n  \n"
    ensure(proofaudit.kernel_context(none) == [],
           "an empty indices section of the fixed theory refused a clean summary")
    refused = [
        _KERNEL_HEAD,
        KERNEL_CLEAN.replace("not mattering:\n", "not mattering: <none>\n"),
        _KERNEL_HEAD + "* Inductives relying on indices not mattering:\n  \n",
        KERNEL_CLEAN.replace("    Corelib.Init.Logic.eq\n", "    Fatal Error: unexpected\n"),
        KERNEL_CLEAN + _INDICES,
        _KERNEL_HEAD.replace("* Inductives whose positivity", _INDICES + "* Inductives whose positivity"),
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


def _audit_goals_open_with_proof() -> None:
    # The pinned Rocq 9.3 reports an interactive proof that Proof does not open, and the
    # gate refuses any diagnostic, so a generated goal without Proof fails every audit.
    claimed: proofaudit.Symbol = {"name": "M.a", "type": "True", "assumptions": [],
                                  "claims": ["R-05-163"]}
    query = proofaudit.assumption_query("M", [claimed])
    ensure(query.count("Goal True.") == 2 and query.count("Goal True. Proof. ") == 2,
           f"a generated audit goal opened without Proof: {query!r}")


def _kernel_verdict_needs_a_clean_summary() -> None:
    def fault(code: int, stdout: str, stderr: str) -> str:
        # With nothing admitted, a worker answers for every library it loaded.
        def unreachable(*_: object) -> tuple[str, frozenset[str]]:
            raise AssertionError("a worker that admitted nothing ran a load-only pass")
        result = subprocess.CompletedProcess([], code, stdout=stdout, stderr=stderr)
        verdict, covered = gate._worker_fault([Path("M.v")], frozenset(), result, unreachable)
        ensure(not covered, "a worker that admitted nothing covered an axiom")
        return verdict

    ensure(fault(0, "", KERNEL_CLEAN) == "", "a clean kernel run was refused")
    ensure(bool(fault(0, "", _KERNEL_HEAD)), "a summary without the indices section passed")
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
               # Every control flag and legacy attribute Rocq 9.3 lets precede a command.
               "Instructions Set Allow StrictProp.", 'Profile "p" Set Indices Matter.',
               "Profile Unset Guard Checking.", "Fail Instructions Timeout 1 Check 0.",
               "Time Instructions Local Unset Universe Checking.",
               "Polymorphic Set Definitional UIP.", "Fail AllocLimit 1 kw Check 0.",
               "Fail AllocLimit 9 Mw Timeout 1 Check 0.",
               "Proof. Unset Guard Checking. exact I. Qed.",
               "#[bypass_check(guard)] Fixpoint f (n : nat) : nat := f n.",
               '#[warnings="-non-recursive"] Fixpoint f (n : nat) : nat := 0.',
               # A quoted bracket does not close the attribute that holds it.
               '#[deprecated(since="2", note="see [old]"), warnings="-all"] '
               "Definition use := old.",
               '#[deprecated(since="2", note="]"), bypass_check(guard)] Fixpoint f (n : nat) '
               ': nat := f n.')
    for text in refused:
        ensure(bool(proofaudit.pinned_overrides(text)), f"a pinned-setting override passed: {text}")
    allowed = ("Set Implicit Arguments.", "Local Open Scope nat_scope.", "Set Printing Width 80.",
               '(* Set Warnings "-all". *) Definition x := 0.',
               '#[deprecated(since="2", note="see warnings [x]")] Definition old := 0.',
               'Definition label := "Set Warnings".', "#[local] Arguments id {A} x.",
               "Definition timeout_bound := 5.", "Time Instructions Check 0.",
               'Profile "p" Set Printing Width 80.', "Polymorphic Definition pid := 0.")
    for text in allowed:
        ensure(not proofaudit.pinned_overrides(text), f"an unpinned sentence was refused: {text}")


def _rocq_93_settings_are_pinned() -> None:
    # Each setting under a locality and under an attribute; printing it changes nothing.
    refused = ("Set Kernel Conversion Dep Heuristic.",
               "Local Set Kernel Conversion Dep Heuristic.",
               "#[local] Unset Kernel Conversion Dep Heuristic.",
               "Global Set Kernel\n  Conversion Dep Heuristic.",
               'Set Default Proof Using "Type".', 'Local Set Default Proof Using "All".',
               '#[export] Set Default Proof Using "Type".', "Export Unset Default Proof Using.")
    for text in refused:
        ensure(proofaudit.pinned_overrides(text) == [text.removesuffix(".")],
               f"a Rocq 9.3 pinned-setting override passed: {text}")
    allowed = ("Test Kernel Conversion Dep Heuristic.", "Test Default Proof Using.",
               "Lemma kept : True. Proof using. exact I. Qed.",
               "Definition Default_Proof_Using := 0.")
    for text in allowed:
        ensure(not proofaudit.pinned_overrides(text), f"reading a pinned setting was refused: {text}")


def _settings_read_as_the_lexer_reads_them() -> None:
    # Each compiles under the gate's flags in the pinned Rocq 9.3.0 with the setting or
    # tactical in effect: a comment is a separator, a `(*` quoted inside a comment opens
    # nothing, and a full stop quoted in an attribute ends no sentence, so the `warnings`
    # attribute after it silences the deprecation that refuses the declaration without it.
    refused = ("Set(* c *)Kernel Conversion Dep Heuristic.",
               "Local(* c *)Set(* c *)Kernel(* c *)Conversion Dep Heuristic.",
               '(* "(*" *) Set Kernel Conversion Dep Heuristic. (* c *)',
               '(* "x" *)Set(* "y" *)Kernel Conversion Dep Heuristic.',
               '#[deprecated(since="1", note="old")] Definition old := 0.\n'
               '#[deprecated(since="2", note="see x. y"), warnings="-all"] '
               "Definition use := old.",
               'Lemma a : True. Proof. idtac "a"". b"; timeout 5 (exact I). Qed.')
    for text in refused:
        ensure(len(proofaudit.pinned_overrides(text)) == 1,
               f"a pinned setting the lexer reads passed: {text!r}")
    allowed = ("Test(* c *)Kernel Conversion Dep Heuristic.",
               '(* "x" Set Kernel Conversion Dep Heuristic. *) Definition x := 0.',
               "(* (* Set Guard Checking. *) Unset Guard Checking. *) Definition x := 0.",
               'Definition label := "a. Set Warnings ""-all"" b".',
               '#[deprecated(since="2", note="see x. Set Guard Checking. y")] '
               "Definition old := 0.")
    for text in allowed:
        ensure(not proofaudit.pinned_overrides(text),
               f"a setting inside a comment was refused: {text!r}")


def _settings_after_bullets_are_refused() -> None:
    # The pinned Rocq 9.3.0 compiles a setting or a Timeout after a bullet, a brace or a
    # focusing selector, and the setting outlives the proof. Program is a legacy attribute.
    refused = ('Lemma a : True. Proof. - Set Warnings "-all". exact I. Qed.',
               'Lemma a : True. Proof. { Set Warnings "-all". exact I. } Qed.',
               "Lemma a : True. Proof. 1: { Set Kernel Conversion Dep Heuristic. exact I. } Qed.",
               "Lemma a : True. Proof. [a]:{ Unset Guard Checking. exact I. } Qed.",
               'Lemma a : True. Proof. -- Local Set Default Proof Using "Type". exact I. Qed.',
               "Lemma a : True. Proof.\n  -\n  Timeout 5 exact I. Qed.",
               "Lemma a : True /\\ True. Proof. split. { exact I. } * + Set Indices Matter. "
               "exact I. Qed.",
               'Program Set Warnings "-all".')
    for text in refused:
        ensure(len(proofaudit.pinned_overrides(text)) == 1,
               f"a pinned setting after a bullet or brace passed: {text!r}")
    allowed = ("Lemma a : True. Proof. - exact I. Qed.",
               "Lemma a : True. Proof. { idtac. exact I. } Qed.",
               "Lemma a : True. Proof. 1: { exact I. } Qed.",
               "Lemma a : True. Proof. - Set Printing Width 80. exact I. Qed.",
               "Program Definition p : nat := 0.")
    for text in allowed:
        ensure(not proofaudit.pinned_overrides(text),
               f"a bullet or brace alone was refused: {text!r}")


def _control_prefixes_need_no_blank() -> None:
    # Rocq's lexer ends a word where an attribute or a string begins, and a string where it
    # closes, doubled quotes inside it. The pinned Rocq 9.3.0 compiles `Time#[local]Set`,
    # `Instructions#[export]Set` and `Timeout 5Set` with the setting in effect, and
    # `Redirect"out"Load` and `Profile "a""b" Set` once their output warning is silenced.
    setting = "Set Kernel Conversion Dep Heuristic."
    for prefix in ("Time#[local]", "Instructions#[export]", "Succeed#[local]", "Fail#[local]",
                   'Redirect"out"', 'Redirect "a""b" ', 'Profile"p"', 'Profile "a""b" ',
                   'Time Redirect"o"Local ', "Timeout 5", "-#[local]", "Time(* c *)#[local]"):
        text = prefix + setting
        ensure(len(proofaudit.pinned_overrides(text)) == 1,
               f"a pinned setting after a tight prefix passed: {text!r}")
        text = prefix + 'Load "/elsewhere/hidden.v".'
        ensure(len(proofaudit.dynamic_sources(text)) == 1,
               f"a Load after a tight prefix passed: {text!r}")
        text = prefix + "Module Type T. End T."
        ensure(len(proofaudit.unsupported_abstractions(text)) == 1,
               f"a signature after a tight prefix passed: {text!r}")
    # A prefix word is a whole word: an identifier that only begins with one is the head.
    for text in ("TimeSet Kernel Conversion Dep Heuristic.", "Local'Set Warnings \"-all\".",
                 "Fail_Set Guard Checking."):
        ensure(not proofaudit.pinned_overrides(text), f"a longer identifier was a prefix: {text!r}")
    for text in ('Timeloaded "x".', "ProgramLoad.", "Fail'Load x."):
        ensure(not proofaudit.dynamic_sources(text), f"a longer identifier was a prefix: {text!r}")


def _machine_bound_tacticals_are_refused() -> None:
    # Each tactic here compiles silently under the gate's flags in the pinned Rocq 9.3.0,
    # the Ltac2 ones once Ltac2 is imported, except alloc_limit, which only this switch's
    # missing memprof-limits refuses. Ltac2 applies its first-class primitives through an
    # alias, a parenthesis or an imported short name, with no argument beside the word.
    refused = ("Lemma a : True. Proof. timeout 5 (exact I). Qed.",
               "Lemma a : True. Proof. alloc_limit 1 Mw (exact I). Qed.",
               "Lemma a : True /\\ True. Proof. split; [timeout 5 auto | exact I]. Qed.",
               "Lemma a : True. Proof. exact ltac:(timeout\n  5 (exact I)). Qed.",
               'Tactic Notation "budget" int_or_var(n) tactic(t) := timeout n t.',
               "Lemma a : True. Proof. let n := numgoals in timeout n (exact I). Qed.",
               "Lemma a : True. Proof. Control.timeout 5 (fun () => exact I). Qed.",
               "Lemma a : True. Proof. Control.timeout (Int.add 2 3) (fun () => exact I). Qed.",
               "Lemma a : True. Proof. Control.timeout(5) (fun () => exact I). Qed.",
               "Lemma a : True. Proof. (Control.timeout) 5 (fun () => exact I). Qed.",
               "Ltac2 budget := Control.timeout.", "Ltac2 budget := Control.timeoutf.",
               "Import Ltac2.Control. Ltac2 budget := timeout.",
               "Import Ltac2.Control. Lemma a : True. "
               "Proof. (timeout) 5 (fun () => exact I). Qed.",
               # Rocq's lexer reads a comment as a separator on either side of the word.
               "Lemma a : True. Proof. timeout(* c *)5 (exact I). Qed.",
               "Lemma a : True. Proof. try(* c *)timeout 5 (exact I). Qed.",
               # Gallina identifiers named exactly after a primitive: loud false refusals.
               "Definition wait := timeout 5.", "Record Budget := { timeout : nat }.",
               "Definition get (b : Budget) := b.(timeout).")
    for text in refused:
        ensure(len(proofaudit.pinned_overrides(text)) == 1,
               f"a machine-bound tactical passed: {text!r}")
    allowed = ("Definition timeout_bound := 5.", "Definition wait := my_timeout 5.",
               "Definition time := 1. Definition out := 2. "
               "Definition wait := Nat.add time(* c *)out.",
               "Definition cap := alloc_limit_words 1.", "Definition wait' := timeout' 5.",
               "Definition timeouts := 5.", "Definition timeoutf' := 5.",
               "(* timeout 5 (exact I) *) Definition x := 0.",
               'Definition label := "timeout 5".', 'Definition label := "a. timeout 5 b".',
               "Lemma a : True. Proof. exact I. Qed. (* alloc_limit 1 Mw (exact I). *)")
    for text in allowed:
        ensure(not proofaudit.pinned_overrides(text),
               f"a sentence with no tactical was refused: {text!r}")


def _dynamic_sources_are_refused_before_compiling() -> None:
    # Under the gate's flags the pinned Rocq 9.3.0 compiles Load of a path or a name, Time
    # Load, Declare ML Module and every Ltac2 external spelling here, a loaded file's
    # setting staying in effect. It refuses Cd as deprecated, the load-path commands as
    # option tables it lacks and a Load inside an open proof; they are refused here too.
    external = " budget : int -> (unit -> 'a) -> 'a := \"rocq-runtime.plugins.ltac2\" \"timeout\"."
    refused = ('Load "/elsewhere/hidden.v".', 'Load Verbose "/elsewhere/hidden.v".',
               "Load hidden.", 'Time Load "hidden.v".', 'Fail Load "hidden.v".',
               'Lemma a : True. Proof. - Load "hidden.v". exact I. Qed.',
               'Cd "/elsewhere".', "Cd.", 'Add LoadPath "/elsewhere" as Elsewhere.',
               'Add Rec LoadPath "/elsewhere" as Elsewhere.', 'Remove LoadPath "/elsewhere".',
               'Add ML Path "/elsewhere".', 'Declare ML Module "rocq-runtime.plugins.ltac2".',
               f"Ltac2 @ external{external}", f"Ltac2@external{external}",
               f"Ltac2(* c *)@(* c *)external{external}", f"#[local] Ltac2 @ external{external}",
               f"Local Ltac2 @\n  external{external}")
    for text in refused:
        ensure(len(proofaudit.dynamic_sources(text)) == 1,
               f"a source loading what the gate cannot read passed: {text!r}")
    allowed = ("Record Load := { level : nat }.", "Definition Loaded := 0.",
               "Ltac Loaded := idtac. Lemma a : True. Proof. Loaded. exact I. Qed.",
               "Definition Cd := 0.", "Ltac2 external := 0.", "Print LoadPath.",
               "Print ML Path.", "Pwd.", '(* Load "hidden.v". *) Definition x := 0.',
               'Definition label := "a. Declare ML Module ""p"". b".')
    for text in allowed:
        ensure(not proofaudit.dynamic_sources(text),
               f"a source that loads nothing was refused: {text!r}")
    with tempfile.TemporaryDirectory(prefix="vos-dynamic-source-") as temporary:
        root = Path(temporary)
        source = root / "proofs" / "M.v"
        source.parent.mkdir()
        for text in ('Load "hidden.v".', f"Ltac2 @ external{external}"):
            source.write_text(text, encoding="utf-8")
            with patch.object(gate, "_compile", side_effect=AssertionError("compiled")):
                checked = gate._check_source(root, source, [source])
            ensure(checked.error.startswith("sources may not load files, plugins or plugin "
                                            "primitives the gate cannot read: "),
                   f"a dynamic source was not refused by name: {checked.error!r}")


def _unreadable_tokens_are_refused_before_compiling() -> None:
    # Under the gate's flags the pinned Rocq 9.3.0 compiles each declaration here and then
    # reads its token whole: after `^"` or `*(*` a Set or a Load compiles with the setting
    # on, and after `^.` a statement's later binder quantifies unread. The shared lexer
    # would open a string, open a comment, or end the sentence there.
    add = "(Nat.add a b) (at level 50)."
    refused = (f'Notation "a ^"" b" := {add}',
               'Notation "x a"" y" := (Nat.add x y) (at level 50).',
               'Infix "^""" := Nat.add (at level 50).', 'Reserved Notation "a ^"" b" (at level 50).',
               f'Time Notation "a ^"" b" := {add}', 'Tactic Notation "foo" "a""" := idtac.',
               'Ltac2 Notation "foo" "a""" := ().',
               "Ltac2 Notation \"foo\" l(list1(constr, \"a\"\"\")) := let _ := l in ().",
               f'Notation "a *(* b" := {add}', f'Local Notation "a ^. b" := {add}',
               f'#[local] Notation "a ^. b" := {add}', f'Notation "a x. b" := {add}',
               f"Notation \"a '^.' b\" := {add}",
               'Notation "a .\u00a0b c" := (Nat.add a c) (at level 50).')
    for text in refused:
        ensure(proofaudit.unreadable_tokens(text) == [text.removesuffix(".")],
               f"a token the lexer cannot follow was declared: {text!r}")
    # Rocq's own `..` and `...`, a full stop inside a token, a quote or a full stop in a
    # notation's body or an attribute, and the same words in a comment all read alike.
    allowed = (f'Notation "a ^^ b" := {add}', f'Notation "a ^.^ b" := {add}',
               'Notation "[: x ; .. ; y :]" := (cons x .. (cons y nil) ..).',
               f'#[deprecated(since="1", note="Use a ^^ b instead.")] Notation "a ^^^ b" := {add}',
               'Tactic Notation "finish" := idtac "done.".',
               'Tactic Notation "quote" := idtac "a""b"; idtac "(*".',
               'Lemma a : True. Proof. idtac "a""b"; idtac "(*". exact I. Qed.',
               '(* Notation "a ^"" b" := x. *) Definition x := 0.',
               'Lemma a : True. Proof. idtac "Notation ""a. b"" c". exact I. Qed.')
    for text in allowed:
        ensure(not proofaudit.unreadable_tokens(text),
               f"a declaration the lexer follows was refused: {text!r}")
    with tempfile.TemporaryDirectory(prefix="vos-unreadable-token-") as temporary:
        root = Path(temporary)
        source = root / "proofs" / "M.v"
        source.parent.mkdir()
        hidden = ('Definition x := 1 ^" 2.\nSet Kernel Conversion Dep Heuristic.\n'
                  'Definition y := 3 ^" 4.\n')
        machine = "Record Machine : Type := { unit_count : nat }.\n"
        for text in (f'Notation "a ^"" b" := {add}\n{hidden}',
                     'Notation "x a"" y" := (Nat.add x y) (at level 50).\n'
                     + hidden.replace("^", "a"),
                     f'Notation "a *(* b" := {add}\nDefinition x := 1 *(* 2.\n'
                     'Load "/elsewhere/hidden.v".\n',
                     f'{machine}Notation "a ^. b" := {add}\nLemma counted : 1 ^. 2 = 3 -> '
                     "forall m : Machine, unit_count m = unit_count m.\n"
                     "Proof. intros _ m. reflexivity. Qed.\n"):
            source.write_text(text, encoding="utf-8")
            with patch.object(gate, "_compile", side_effect=AssertionError("compiled")):
                checked = gate._check_source(root, source, [source])
            ensure(checked.error.startswith("sources may not declare tokens the gate's "
                                            "lexer cannot follow: "),
                   f"an unreadable token was not refused by name: {checked.error!r}")
        # The control: with a token the lexer follows, the Set after it is read and refused.
        source.write_text(f'Notation "a ^^ b" := {add}\n' + hidden.replace('^"', "^^"),
                          encoding="utf-8")
        with patch.object(gate, "_compile", side_effect=AssertionError("compiled")):
            checked = gate._check_source(root, source, [source])
        ensure(checked.error.startswith("sources may not change the gate's pinned settings: "),
               f"the setting after a readable token was not refused: {checked.error!r}")


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
                    patch.object(gate, "_recheck", return_value=""), \
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
    # another reason. The type-only axiom is named by both assumption readings.
    bad = [("Theorem unopened : True.\nexact I.\nQed.\n", "missing-proof-command"),
           ("Theorem good : True. Proof. exact I. Qed.\nPrint Assumptions good.\n"
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
           ("Instructions Set Allow StrictProp.\nInductive squashed : SProp := squash.\n",
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
    samples = [("9.3.0", "9.3.0", True), ("9.3.0", "9.3", True),
               ("9.3.0", "9.3.1", False), ("9.3.0", "9.3+dev", False),
               ("9.3.0", "9.3~rc1", False), ("9.3.0", "9.2.0", False),
               ("9.3.1", "9.3", False), ("9.3.1", "9.3.1", True)]
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
            Case("prefixed-abstractions-fail-closed", _prefixed_abstractions_fail_closed),
            Case("kernel-context-is-exact", _kernel_context_is_exact),
            Case("audit-goals-open-with-proof", _audit_goals_open_with_proof),
            Case("kernel-verdict-needs-a-clean-summary", _kernel_verdict_needs_a_clean_summary),
            Case("pinned-settings-cannot-be-overridden", _pinned_settings_cannot_be_overridden),
            Case("rocq-93-settings-are-pinned", _rocq_93_settings_are_pinned),
            Case("settings-read-as-the-lexer-reads-them", _settings_read_as_the_lexer_reads_them),
            Case("settings-after-bullets-are-refused", _settings_after_bullets_are_refused),
            Case("control-prefixes-need-no-blank", _control_prefixes_need_no_blank),
            Case("machine-bound-tacticals-are-refused", _machine_bound_tacticals_are_refused),
            Case("dynamic-sources-are-refused-before-compiling",
                 _dynamic_sources_are_refused_before_compiling),
            Case("unreadable-tokens-are-refused-before-compiling",
                 _unreadable_tokens_are_refused_before_compiling),
            Case("nested-sources-cannot-be-omitted", _nested_sources_cannot_be_omitted),
            Case("parallel-wave-blocks-stale-dependents", _parallel_wave_blocks_stale_dependents),
            Case("staged-run-binds-original-inputs", _staged_run_binds_original_inputs),
            Case("workspace-is-lane-native", _workspace_is_lane_native),
            Case("release-version-banner-is-exact", _release_version_banner_is_exact),
            Case("native-proof-gate-regressions", _native_gate_regressions, lane="toolchain")]
