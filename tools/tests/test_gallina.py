# SPDX-License-Identifier: Apache-2.0
"""The Gallina rig's three host-decidable parts: the Require order, the staging, and
the reading of what a harness printed.

The prover itself is the guest's and is not exercised here; what is exercised is
everything that decides *what* the prover is handed and *what is read back out of it*,
because each of those fails quietly. A compile order that is not a dependency order is
satisfied by a stale `.vo`; a stage that copies a `.vo` in hands the prover the answer
it was supposed to recompute; and a reading of the printed vectors that dropped the
last entry would compare two files that agree on everything they carry.
"""

import argparse
import io
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stdout, suppress
from pathlib import Path
from unittest.mock import Mock, patch

from tests.harness import Case, ensure
from vos import env, gallina, proofs
from vos.cli import kernel, quickchick, seed

_A = "Definition a : nat := 1.\n"
_B = "Require Import A.\nDefinition b : nat := a.\n"
_C = "Require Import B.\nDefinition c : nat := b.\n"


def _tree(files: dict[str, str]) -> tempfile.TemporaryDirectory[str]:
    handle = tempfile.TemporaryDirectory(prefix="vos-test-")
    root = Path(handle.name)
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="")
    return handle


def _waves_follow_requires() -> None:
    """Name order is not a dependency order: C requires B requires A, and the three
    sort in the reverse of the order a directory listing gives them."""
    with _tree({"C.v": _C, "B.v": _B, "A.v": _A}) as td:
        root = Path(td)
        order = [[p.stem for p in wave]
                 for wave in proofs.waves(sorted(root.glob("*.v")))]
    ensure(order == [["A"], ["B"], ["C"]], f"the waves came out {order}")


def _dependents_are_the_require_closure() -> None:
    """C requires B requires A. A mutation in A is readable by all three; one in C is
    readable by C alone, which is the whole saving: the population loop compiles the
    closure and leaves the rest standing on the baseline's `.vo`."""
    with _tree({"C.v": _C, "B.v": _B, "A.v": _A}) as td:
        sources = sorted(Path(td).glob("*.v"))
        low = [[p.stem for p in wave] for wave in proofs.dependents(sources, "A")]
        high = [[p.stem for p in wave] for wave in proofs.dependents(sources, "C")]
        mid = [[p.stem for p in wave] for wave in proofs.dependents(sources, "B")]
    ensure(low == [["A"], ["B"], ["C"]], f"A's closure came out {low}")
    ensure(mid == [["B"], ["C"]], f"B's closure came out {mid}")
    ensure(high == [["C"]], f"C's closure came out {high}")


def _a_dependent_closure_keeps_the_compile_order() -> None:
    """The closure is still a dependency order and not a filtered name order, so a
    proof in it is never handed to the prover before the proof it Requires."""
    with _tree({"C.v": _C, "B.v": _B, "A.v": _A}) as td:
        sources = sorted(Path(td).glob("*.v"))
        order = [[p.stem for p in wave] for wave in proofs.dependents(sources, "A")]
    seen: set[str] = set()
    for wave in order:
        for stem in wave:
            need = {"A": set(), "B": {"A"}, "C": {"B"}}[stem]
            ensure(need <= seen, f"{stem} was compiled before {need - seen}")
        seen |= set(wave)


def _a_stem_no_source_carries_has_no_closure() -> None:
    """And the caller decides what that means. `compile_dependents` reads the empty
    list as "narrow nothing" and compiles the whole directory, because an empty compile
    would report a green baseline for a tree nobody built."""
    with _tree({"A.v": _A}) as td:
        sources = sorted(Path(td).glob("*.v"))
        got = proofs.dependents(sources, "Absent")
    ensure(got == [], f"a stem outside the directory produced {got}")


def _a_require_cycle_is_refused() -> None:
    with _tree({"A.v": "Require Import B.\n", "B.v": "Require Import A.\n"}) as td:
        root = Path(td)
        try:
            proofs.waves(sorted(root.glob("*.v")))
        except SystemExit as err:
            ensure("Require cycle" in str(err), f"the refusal said {err!r}")
            return
    raise AssertionError("a cycle was given a compile order")


def _branched_dependencies_keep_sorted_waves() -> None:
    files = {"A.v": _A, "B.v": _B, "C.v": "Require A.\n", "X.v": "",
             "D.v": "Require B C X.\n"}
    with _tree(files) as td:
        sources = sorted(Path(td).glob("*.v"), reverse=True)
        waves = [[p.stem for p in wave] for wave in proofs.waves(sources)]
        with patch.object(proofs, "local_requires", wraps=proofs.local_requires) as read:
            closure = [[p.stem for p in wave] for wave in proofs.dependents(sources, "B")]
        ensure(read.call_count == len(sources), "the closure reparsed its source graph")
    ensure(waves == [["A", "X"], ["B", "C"], ["D"]],
           f"independent branches lost deterministic waves: {waves}")
    ensure(closure == [["B"], ["D"]], f"a mutation pulled unrelated branches in: {closure}")
    ensure(proofs.waves([]) == [] and proofs.dependents([], "Absent") == [],
           "an empty source directory gained a compile wave")


def _cycle_refusals_include_only_blocked_sources() -> None:
    files = {"A.v": "", "B.v": "Require C.\n", "C.v": "Require B.\n",
             "D.v": "Require B.\n", "Z.v": "Require A.\n"}
    expected = "FAIL: a Require cycle among B.v, C.v, D.v; no compile order satisfies it"
    with _tree(files) as td:
        sources = sorted(Path(td).glob("*.v"), reverse=True)
        for stem in ("A", "Absent"):
            try:
                proofs.dependents(sources, stem)
            except SystemExit as err:
                ensure(str(err) == expected, f"the cycle refusal changed: {err}")
            else:
                raise AssertionError("narrowing to an unrelated source hid a Require cycle")
    with _tree({"A.v": "Require A.\n"}) as td:
        try:
            proofs.waves(list(Path(td).glob("*.v")))
        except SystemExit as err:
            ensure("among A.v;" in str(err), f"a self-cycle refusal changed: {err}")
        else:
            raise AssertionError("a self-Require was given a compile order")


def _source_index_is_one_immutable_snapshot() -> None:
    files = {"A.v": _A, "B.v": _B, "C.v": "Require A.\n", "X.v": "",
             "D.v": "Require B C X.\n"}
    with _tree(files) as td:
        sources = sorted(Path(td).glob("*.v"))
        read_text = Path.read_text
        with patch.object(Path, "read_text", autospec=True, side_effect=read_text) as read:
            index = proofs.SourceIndex.read(sources)
        ensure(read.call_count == len(sources), "the source snapshot read a proof more than once")
        ensure([list(wave) for wave in index.ordered] == proofs.waves(sources),
               "the shared source snapshot changed dependency order")
        root = Path(td)
        ensure([path.stem for path in index.imports[root / "D.v"]] == ["A", "B", "C", "X"],
               "a diamond import closure duplicated or omitted a dependency")
        original = index.texts[root / "B.v"]
        source = root / "B.v"
        stamp = source.stat()
        source.write_text(original.replace("Require Import A.", "Require Import C."),
                          encoding="utf-8", newline="")
        os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        ensure(source.stat().st_size == stamp.st_size, "the fixture changed source length")
        changed = proofs.SourceIndex.read(sources)
        ensure(index.texts[source] == original and changed.texts[source] != original,
               "an edit changed an existing snapshot or escaped a new one")
        ensure(changed.needs[source] == frozenset({root / "C.v"}),
               "preserved timestamps hid a changed dependency")
        source.write_text("Require D.\n", encoding="utf-8")
        try:
            proofs.SourceIndex.read(sources)
        except SystemExit as err:
            ensure("Require cycle among B.v, D.v" in str(err), f"cycle refusal changed: {err}")
        else:
            raise AssertionError("an old snapshot hid a newly introduced cycle")


def _comment_lexing_preserves_source_and_newlines() -> None:
    # Read as the locked Rocq 9.3.0's lexer reads each: a comment is a separator, and a
    # string literal inside a comment is read whole, so a quoted `(*` or `*)` there
    # opens or closes nothing and an unterminated one runs the comment to the end.
    fixtures = {
        "before(* hidden *)after": "before after",
        "a(* first\n(* nested\n*)tail\n*)b": "a\n\n\nb",
        'Definition s := "(* literal *)". (* hidden *)': 'Definition s := "(* literal *)".  ',
        'Definition s := "a ""(* literal *)"" b".': 'Definition s := "a ""(* literal *)"" b".',
        '"unterminated (* literal': '"unterminated (* literal',
        "before(* first\n(* second\n*)": "before\n\n",
        "before(* unterminated": "before ",
        'a(* " *)b': "a ",
        'a(* "(*" *)b': "a b",
        'a(* "*)" *)b': "a b",
        'a(* """*)" *)b': "a b",
        'a(* "x" *)b(* "\n" *)c': "a b\nc",
        "a *) b": "a *) b",
        "a(* one\r\ntwo *)b": "a\nb",
    }
    for source, expected in fixtures.items():
        ensure(proofs.strip_comments(source) == expected,
               f"comment boundaries changed for {source!r}")
        # the same reading at the source's own offsets: each comment is blank space of
        # its length, its line breaks where the source has them
        kept = proofs.strip_comments(source, keep_offsets=True)
        ensure(len(kept) == len(source)
               and [i for i, c in enumerate(kept) if c == "\n"]
               == [i for i, c in enumerate(source) if c == "\n"]
               and kept.split() == expected.split(),
               f"the offset-keeping reading of {source!r} is {kept!r}")


def _sentences_end_outside_strings() -> None:
    # A full stop followed by whitespace ends a sentence only outside a string literal,
    # whose doubled quote Rocq reads as one quote inside it.
    fixtures = {
        'Definition a := "x. y". Definition b := 0.': ['Definition a := "x. y"',
                                                       "Definition b := 0"],
        '#[deprecated(note="see x. y")] Lemma l : True.': [
            '#[deprecated(note="see x. y")] Lemma l : True'],
        # A string spans lines as Rocq reads it, a full stop before its line break too.
        '#[deprecated(note="see x.\ny")] Lemma l : True.': [
            '#[deprecated(note="see x.\ny")] Lemma l : True'],
        'Goal True. idtac "a"". b". exact I.': ["Goal True", 'idtac "a"". b"', "exact I"],
        'Definition s := "unterminated. x': ['Definition s := "unterminated. x'],
        "Check m.(f). Check Nat.add.\nQed.": ["Check m.(f)", "Check Nat.add", "Qed"],
        "a(* . *)b. c": ["a b", "c"],
        '(* "x. y" *) Lemma l : True.': ["Lemma l : True"],
        # Rocq reads `..` as a token that ends nothing and `...` as a sentence end.
        'Notation "[ x ; .. ; y ]" := (cons x .. (cons y nil) ..).\nCheck [ 1 ; 2 ].': [
            'Notation "[ x ; .. ; y ]" := (cons x .. (cons y nil) ..)', "Check [ 1 ; 2 ]"],
        "Lemma l : (∀.. (x : TeleO), True) -> P. Qed.": [
            "Lemma l : (∀.. (x : TeleO), True) -> P", "Qed"],
        "Proof with auto. split... Qed.": ["Proof with auto", "split..", "Qed"],
    }
    for source, expected in fixtures.items():
        got = proofs.sentences(source)
        ensure(got == expected, f"sentence boundaries changed for {source!r}: {got!r}")


def _the_decoration_grammar_is_one_reading() -> None:
    # The run a head pattern opens with and the walk a reader takes one decoration at a
    # time are one grammar: each stops where the other does, a comment already read as a
    # separator, and the walk says which decoration it read.
    fixtures = {
        "Time#[local]Lemma l": [("word", "Time"), ("attributes", "local")],
        'Redirect"a""b"Succeed Lemma l': [("word", "Redirect"), ("word", "Succeed")],
        'Profile "p" Fail\n#[deprecated(note="x. ] y")]\nLocal Program Definition d': [
            ("word", "Profile"), ("word", "Fail"),
            ("attributes", 'deprecated(note="x. ] y")'), ("word", "Local"),
            ("word", "Program")],
        "- Lemma l": [("bullet", "-")], "+ Lemma l": [("bullet", "+")],
        "* Lemma l": [("bullet", "*")], "{ Lemma l": [("bullet", "{")],
        "} Lemma l": [("bullet", "}")], "2: { Lemma l": [("bullet", "2: {")],
        "[x]: { Lemma l": [("bullet", "[x]: {")],
        "!: { Timeout 5AllocLimit 3 Mw Instructions Lemma l": [
            ("bullet", "!: {"), ("word", "Timeout"), ("word", "AllocLimit"),
            ("word", "Instructions")],
        "AllocLimit 2 kw Lemma l": [("word", "AllocLimit")],
        "Export Set Printing All": [("word", "Export")],
        "TimeLemma l": [], "Local' l": [], "Timeout l": [], "Lemma l": [],
    }
    for source, expected in fixtures.items():
        found, at = proofs.decorations(source)
        got = [next((kind, (value or "").strip()) for kind, value in decoration.groupdict()
                    .items() if value is not None) for decoration in found]
        ensure(got == expected, f"the walk read {source!r} as {got!r}")
        run = re.match(proofs.CONTROL_PREFIXES, source)
        ensure(run is not None and run.end() == at,
               f"the run and the walk stop apart over {source!r}")


def _the_look_back_reads_only_decorations() -> None:
    # The flag a command stands under is read from the full stop ending the sentence
    # before, a string's aside, through the command's own line; a head with anything
    # else between it and that full stop opens inside a sentence and is under no flag.
    fixtures = (
        ('Definition a := 0.\nFail #[deprecated(note="x. y")]\nDefinition b := 1.\n',
         "Definition b", "Fail"),
        ("Fail\nTime Definition b := 1.\n", "Time", "Fail"),
        ("Definition a := 0. Succeed#[local]\nDefinition b := 1.\n", "Definition b",
         "Succeed"),
        ("Definition a := 0. Time\nDefinition b := 1.\n", "Definition b", None),
        ("Definition a := 0.\nFail Check x\nDefinition b := 1.\n", "Definition b", None),
    )
    for code, head, flag in fixtures:
        got = proofs.void_flag(code, code.index(head), proofs.sentence_ends(code))
        ensure(got == flag, f"the look-back from {head!r} in {code!r} read {got!r}")


def _a_bullet_starts_the_run_again() -> None:
    # A bullet, a brace or a goal selector is a command of its own, and the locked
    # compiler runs `Fail }` and `Succeed {` as the brace's flag and keeps the declaration
    # after it. So the walk starts again at each, the last standing first in what it
    # returns, while the run a head pattern opens with still reads past them all.
    fixtures = {
        "Fail } Definition g": [("bullet", "}")],
        "Succeed { Time Definition g": [("bullet", "{"), ("word", "Time")],
        "Succeed 1: {\nDefinition g": [("bullet", "1: {")],
        "#[local] Fail }\nLocal Definition g": [("bullet", "}"), ("word", "Local")],
        "- Succeed Definition g": [("bullet", "-"), ("word", "Succeed")],
    }
    for source, expected in fixtures.items():
        found, at = proofs.decorations(source)
        got = [next((kind, (value or "").strip()) for kind, value in decoration.groupdict()
                    .items() if value is not None) for decoration in found]
        ensure(got == expected and source[at:] == "Definition g",
               f"the walk read {source!r} as {got!r}, the command at {at}")
        run = re.match(proofs.CONTROL_PREFIXES, source)
        ensure(run is not None and run.end() == at,
               f"the run and the walk stop apart over {source!r}")
    # and the look-back reads the flag a declaration stands under the same way
    proof = "Lemma l : True.\nProof.\n"
    for lead, flag in (("Fail }\n", None), ("Fail } ", None), ("Succeed { ", None),
                       ("Succeed 1: {\n", None), ("Fail\n}\n", None),
                       ("- Succeed ", "Succeed"), ("{ Succeed\n", "Succeed")):
        code = proof + lead + "Definition g := 1.\n"
        got = proofs.void_flag(code, code.index("Definition g"), proofs.sentence_ends(code))
        ensure(got == flag, f"the look-back over {lead!r} read {got!r}")


def _a_library_require_is_not_ordered() -> None:
    """What a library provides is not this module's to order, so `From Stdlib Require
    Import String` names no local dependency and opens no wave of its own."""
    with _tree({"A.v": "From Stdlib Require Import String List.\n" + _A}) as td:
        root = Path(td)
        need = proofs.local_requires(root / "A.v", {"A"})
    ensure(need == set(), f"a stdlib Require was read as a local one: {need}")


def _staging_leaves_the_compiled_artifacts_behind() -> None:
    """A `.vo` copied into the scratch tree is the answer the prover was supposed to
    recompute, and a mutation loop reading one would report a kill nobody seeded."""
    with _tree({"proofs/A.v": _A, "proofs/A.vo": "stale",
                "proofs/.A.aux": "stale",
                "tools/quickchick/Vectors.v": "(* harness *)\n"}) as td:
        root = Path(td)
        with tempfile.TemporaryDirectory(prefix="vos-work-") as wd:
            work = Path(wd) / "gallina"
            gallina.stage(root, work)
            ensure((work / "proofs" / "A.v").is_file(), "the proof was not staged")
            ensure(not (work / "proofs" / "A.vo").exists(),
                   "a compiled artifact was staged with its source")
            ensure((work / "harness" / "Vectors.v").is_file(),
                   "the harness was not staged beside the proofs")


def _staging_is_a_fresh_tree_every_time() -> None:
    with _tree({"proofs/A.v": _A}) as td:
        root = Path(td)
        with tempfile.TemporaryDirectory(prefix="vos-work-") as wd:
            work = Path(wd) / "gallina"
            gallina.stage(root, work)
            (work / "proofs" / "left-over.v").write_text("(* from a previous run *)\n",
                                                         encoding="utf-8")
            gallina.stage(root, work)
            ensure(not (work / "proofs" / "left-over.v").exists(),
                   "a previous run's file survived into the next one")


def _quoted_segments_are_the_vectors() -> None:
    printed = ('     = ["ce 100 -> 1 0"; "ce 200 -> 0 1"]\n'
               "     : list string\n")
    got = gallina._quoted(printed)
    ensure(got == ["ce 100 -> 1 0", "ce 200 -> 0 1"], f"the reading gave {got}")


def _an_unterminated_quote_yields_nothing_more() -> None:
    """Fail short rather than long: a truncated print is a comparison that must not
    silently gain a half-line as its last vector."""
    got = gallina._quoted('= ["a"; "b')
    ensure(got == ["a"], f"the reading gave {got}")


def _written_vectors_are_one_per_line() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        target = gallina.write(["a b", "c d"], Path(td) / "vectors.txt")
        got = target.read_bytes()
    ensure(got == b"a b\nc d\n", f"the file held {got!r}")


def _the_two_switches_are_named_apart() -> None:
    ensure(gallina.ORACLE_SWITCH != gallina.QUICKCHICK_SWITCH,
           "the oracle's switch and QuickChick's are the same name, which is the "
           "install this repository priced rather than made")
    ensure(gallina.HARNESS_DIR != gallina.PROOFS,
           "the harness would live inside the proof gate's own subject")


def _the_oracle_candidates_build_from_released_packages() -> None:
    """Each candidate's recipe names released packages alone, in the switch it would be
    declared as: no pin, no checkout path or URL, and the CertiRocq release the rig
    holds. The declared switch is always one of them."""
    candidates = gallina.ORACLE_CANDIDATE_OCAML_VERSIONS
    ensure(len(candidates) > 0 and len(set(candidates)) == len(candidates),
           "the candidates are a nonempty order without repeats")
    ensure(gallina.oracle_candidate_switch(gallina.ORACLE_OCAML_VERSION)
           == gallina.ORACLE_SWITCH
           and gallina.ORACLE_OCAML_VERSION in gallina.ORACLE_CANDIDATE_OCAML_VERSIONS,
           "the declared oracle switch is not one a candidate recipe builds")
    released = re.compile(r"[a-z][a-z0-9-]*\.[0-9][0-9A-Za-z.+~-]*")
    for ocaml in gallina.ORACLE_CANDIDATE_OCAML_VERSIONS:
        steps = gallina.oracle_candidate_build(ocaml)
        switch = gallina.oracle_candidate_switch(ocaml)
        words = [word for step in steps for word in step]
        ensure(steps[0][:4] == ("opam", "switch", "create", switch)
               and all(step[:2] == ("opam", "install") and f"--switch={switch}" in step
                       for step in steps[1:]),
               f"{ocaml}: the recipe creates the candidate's switch, then only installs "
               f"into it: {steps}")
        ensure([word for word in words if word.startswith("--repos=")]
               == ["--repos=rocq-released,default"],
               f"{ocaml}: the switch reads the released repository and the default "
               f"alone: {steps}")
        ensure(not any("/" in word or word.startswith((".", "~")) for word in words),
               f"{ocaml}: a candidate reads no path and no URL: {words}")
        ensure(all(released.fullmatch(word)
                   for step in steps[1:] for word in step[2:] if not word.startswith("-")),
               f"{ocaml}: every package installed is a released version: {steps}")
        ensure(f"--packages=ocaml-base-compiler.{ocaml}" in steps[0]
               and f"rocq-certirocq.{gallina.CERTIROCQ_VERSION}" in steps[-1]
               and f"ocamlfind.{env.OCAMLFIND_VERSION}" in steps[-1],
               f"{ocaml}: the recipe builds the rig's CertiRocq at that compiler: {steps}")


def _the_stdlib_harnesses_compile_in_the_proof_switch() -> None:
    """The vector instruments ask for the gate's own switch and the randomized one for
    QuickChick's, each by the constant that names it. Asked of the prover lookup rather
    than read off the source, so an instrument that spelled another switch is caught
    wherever it spells it."""
    ensure(gallina.VECTOR_SWITCH == env.ROCQ_SWITCH
           and gallina.VECTOR_ROCQ_VERSION == env.ROCQ_VERSION,
           "the vector harnesses no longer compile in the proof gate's switch")
    asked: list[str] = []

    def absent(switch: str) -> None:
        asked.append(switch)

    with patch.object(gallina, "prover", side_effect=absent):
        said: list[str] = []
        ensure(gallina.emit(Path(), Path(), said) is None
               and kernel.emit(Path(), Path(), said) is None,
               "an absent prover must stop the run before staging")
        ensure(all(gallina.VECTOR_SWITCH in line for line in said),
               f"the refusal must name the switch it looked in: {said}")
        with (patch.object(seed, "lane_env", return_value=Mock()),
              patch.object(quickchick, "installed", return_value=None),
              redirect_stdout(io.StringIO())):
            for randomized, recipe in ((False, False), (True, False), (True, True)):
                args = argparse.Namespace(file=seed.COQ_SUBJECT, quickchick=randomized,
                                          recipe=recipe)
                ensure(seed.cmd_coq(args) == 1, "an absent prover must be refused")
            args = argparse.Namespace(file=seed.COQ_SUBJECT, quickchick=False, recipe=True)
            ensure(seed.cmd_coq(args) == 1, "--recipe without --quickchick is refused")
    want = [gallina.VECTOR_SWITCH, gallina.VECTOR_SWITCH, gallina.VECTOR_SWITCH,
            gallina.QUICKCHICK_SWITCH, gallina.QUICKCHICK_RECIPE_SWITCH]
    ensure(asked == want, f"the instruments asked for {asked}, not {want}")


def _the_randomized_support_is_built_for_that_half_alone() -> None:
    """IPCProperties.v is support only Properties.v and Walks.v Require. The shared
    sources a vector instrument compiles leave it out, so one it does not compile over
    stops no vector run; asked for the randomized half, they build it after what it
    Requires."""
    files = {"proofs/A.v": _A, "tools/quickchick/Probe.v": "Require Import A.\n",
             "tools/quickchick/IPCProperties.v": "Require Import Probe.\n",
             f"tools/quickchick/{gallina.ENUMERATIVE}": "Require Import Probe.\n"}
    compiled: list[str] = []

    def compile_one(found: gallina.Prover, work: Path, source: Path,
                    timeout: int = 900) -> subprocess.CompletedProcess[str]:
        del found, work, timeout
        compiled.append(source.stem)
        if source.name == "IPCProperties.v":
            return subprocess.CompletedProcess([], 1, "", "Error: broken")
        return subprocess.CompletedProcess([], 0, '= ["v 1"] : list string\n', "")

    found = gallina.Prover("s", ("rocq", "c"))
    with (_tree(files) as td, tempfile.TemporaryDirectory(prefix="vos-work-") as wd,
          patch.object(gallina, "compile_one", side_effect=compile_one),
          patch.object(gallina, "prover", return_value=found)):
        work = Path(wd) / "gallina"
        said: list[str] = []
        lines = gallina.emit(Path(td), work, said)
        ensure(lines == ["v 1"] and "IPCProperties" not in compiled,
               f"a vector run compiled the randomized half's support: {compiled} {said}")
        ensure("IPCProperties.v" in gallina.RANDOMIZED_SUPPORT
               and not gallina.compile_support(found, work),
               "the shared sources a vector run compiles hold the randomized half's support")
        compiled.clear()
        failures = gallina.compile_support(found, work, randomized=True)
    ensure([f.source for f in failures] == ["IPCProperties.v"]
           and compiled == ["Probe", "IPCProperties"],
           f"the randomized half's support is built after what it Requires: {compiled}")


_SEEDED = ('From QuickChick Require Import QuickChick.\n'
           'Extract Constant newRandomSeed => "(Random.State.make [|7|])".\n')


def _the_randomized_harness_compiles_its_closure_alone() -> None:
    """`quickchick properties` compiles what Properties.v and Walks.v Require, through
    the harnesses they Require into the proofs they read, once, and then the two
    harnesses: never a proof outside that closure, nor another entry point."""
    files = {"proofs/A.v": _A, "proofs/B.v": _B, "proofs/C.v": _A, "proofs/Far.v": _A,
             "tools/quickchick/Probe.v": "Require Import A.\n",
             "tools/quickchick/IPCProperties.v": "Require Import Probe.\n",
             "tools/quickchick/Vectors.v": "Require Import Far.\n",
             f"tools/quickchick/{gallina.RANDOMIZED}":
                 _SEEDED + "Require Import B Probe IPCProperties.\n",
             f"tools/quickchick/{gallina.EXHAUSTIVE}": "Require Import C IPCProperties.\n"}
    compiled: list[str] = []

    def compile_one(found: gallina.Prover, work: Path, source: Path,
                    timeout: int = 900) -> subprocess.CompletedProcess[str]:
        del found, work, timeout
        compiled.append(source.stem)
        said = ('= ["prop_w 9 9 0 -"] : list string\n' if source.name == gallina.EXHAUSTIVE
                else "+++ Passed 10000 tests\n")
        return subprocess.CompletedProcess([], 0, said, "")

    with (_tree(files) as td, tempfile.TemporaryDirectory(prefix="vos-work-") as wd,
          patch.object(quickchick, "installed", return_value=quickchick.VERSION),
          patch.object(gallina, "prover", return_value=gallina.Prover("s", ("rocq", "c"))),
          patch.object(gallina, "compile_one", side_effect=compile_one),
          redirect_stdout(io.StringIO()) as output):
        code = quickchick._properties(argparse.Namespace(recipe=False), Mock(), Path(td),
                                      Path(wd) / "gallina")
    ensure(code == 0, f"the closure run failed: {output.getvalue()}")
    ensure(compiled[-2:] == ["Properties", "Walks"]
           and sorted(compiled[:-2]) == ["A", "B", "C", "IPCProperties", "Probe"],
           f"the run compiled {compiled}, not the harnesses' closure once and then each")
    ensure(compiled.index("A") < min(compiled.index("B"), compiled.index("Probe"))
           and compiled.index("Probe") < compiled.index("IPCProperties"),
           f"a Require was compiled after what reads it: {compiled}")
    ensure("from seed 7" in output.getvalue() and "1 walked set(s) held" in output.getvalue(),
           f"the report must carry the seed and the walks: {output.getvalue()}")


def _the_randomized_half_refuses_what_does_not_replay_or_hold() -> None:
    """A drawn harness fixing no seed is refused before anything compiles, a drawn
    harness that does not build is a build failure rather than sets that failed, and a
    walk a point refutes fails the run whatever the draws said."""
    files = {"proofs/A.v": _A,
             f"tools/quickchick/{gallina.RANDOMIZED}":
                 "From QuickChick Require Import QuickChick.\nRequire Import A.\n",
             f"tools/quickchick/{gallina.EXHAUSTIVE}": "Require Import A.\n"}

    def compile_one(found: gallina.Prover, work: Path, source: Path,
                    timeout: int = 900) -> subprocess.CompletedProcess[str]:
        del found, work, timeout
        if source.name == gallina.EXHAUSTIVE:
            return subprocess.CompletedProcess([], 0, '= ["prop_w 9 3 2 4"] : list string\n',
                                               "")
        if broken and source.name == gallina.RANDOMIZED:
            return subprocess.CompletedProcess([], 1, "", "Error: The reference x was not found")
        return subprocess.CompletedProcess([], 0, "+++ Passed 10000 tests\n", "")

    for seeded, broken, want in (
            (False, False, "fixes QuickChick's random state other than once"),
            (True, True, f"FAIL {gallina.RANDOMIZED} decided no property set under "
                         f"{quickchick.PACKAGE} in {gallina.QUICKCHICK_SWITCH}: it did not "
                         "build: Error: The reference x was not found"),
            (True, False, "2 of 9 point(s) refute it, the first at position 4")):
        if seeded:
            files[f"tools/quickchick/{gallina.RANDOMIZED}"] = _SEEDED + "Require Import A.\n"
        with (_tree(files) as td, tempfile.TemporaryDirectory(prefix="vos-work-") as wd,
              patch.object(quickchick, "installed", return_value=quickchick.VERSION),
              patch.object(gallina, "prover",
                           return_value=gallina.Prover("s", ("rocq", "c"))),
              patch.object(gallina, "compile_one", side_effect=compile_one) as compiled,
              redirect_stdout(io.StringIO()) as output):
            code = quickchick._properties(argparse.Namespace(recipe=False), Mock(), Path(td),
                                          Path(wd) / "gallina")
        ensure(code == 1 and want in output.getvalue(),
               f"seeded={seeded}, broken={broken}: the run said {output.getvalue()}")
        ensure(seeded or compiled.call_count == 0,
               "a harness that cannot replay must be refused before compiling")


def _the_seed_and_the_walks_are_read() -> None:
    # Requiring QuickChick replays its own `Extract Constant newRandomSeed`, so a seed
    # stated ahead of a sentence that Requires it, however that sentence spells the
    # library, fixes nothing.
    stated = _SEEDED.splitlines(keepends=True)[1]
    qualified = "Require Import Stdlib.List QuickChick.QuickChick.\n"
    with _tree({"P.v": _SEEDED, "Twice.v": _SEEDED * 2,
                "Hidden.v": "(* " + _SEEDED.replace("(*", "").replace("*)", "") + " *)\n",
                "Unseeded.v": "From QuickChick Require Import QuickChick.\n",
                "Early.v": stated + "From QuickChick Require Import QuickChick.\n",
                "Between.v": _SEEDED + "From QuickChick Require Import Tactics.\n",
                "Qualified.v": qualified + stated,
                "QualifiedEarly.v": stated + qualified}) as td:
        root = Path(td)
        got = {name: gallina.seed(root / f"{name}.v")
               for name in ("P", "Twice", "Hidden", "Unseeded", "Absent", "Early",
                            "Between", "Qualified", "QualifiedEarly")}
    ensure(got == {"P": "7", "Twice": None, "Hidden": None, "Unseeded": None,
                   "Absent": None, "Early": None, "Between": None, "Qualified": "7",
                   "QualifiedEarly": None}, f"the seed readings were {got}")
    printed = {"held": '= ["prop_a 9 9 0 -"; "prop b, over c 392 81 0 -"] : list string\n',
               "refuted": '= ["prop_a 9 4 1 0"] : list string\n',
               "vacuous": '= ["prop_a 9 0 0 -"] : list string\n',
               "malformed": '= ["prop_a nine 9 0 -"] : list string\n',
               "short": '= ["prop_a 9 0 -"] : list string\n',
               "superscript": '= ["prop_a ² 9 0 -"] : list string\n',
               "premise past the domain": '= ["prop_a 9 12 0 -"] : list string\n',
               "refuted past the domain": '= ["prop_a 9 9 12 3"] : list string\n',
               "refuted with no first": '= ["prop_a 9 9 2 -"] : list string\n',
               "first with none refuted": '= ["prop_a 9 9 0 3"] : list string\n',
               "first past the domain": '= ["prop_a 9 9 1 9"] : list string\n',
               "empty": "= [] : list string\n"}
    read: dict[str, tuple[list[gallina.Walk], str]] = {}
    for label, text in printed.items():
        done = subprocess.CompletedProcess([], 0, text, "")
        with patch.object(gallina, "compile_one", return_value=done):
            read[label] = gallina.walks(gallina.Prover("s", ("rocq", "c")), Path(), Path())
    ensure(read["held"] == ([gallina.Walk("prop_a", 9, 9, 0, None),
                             gallina.Walk("prop b, over c", 392, 81, 0, None)], "")
           and not gallina.walk_failures(read["held"][0]),
           f"a held walk reads as held, its name kept whole: {read['held']}")
    ensure(gallina.walk_failures(read["refuted"][0])
           == ["prop_a: 1 of 9 point(s) refute it, the first at position 0"],
           f"a refuted walk is named with its first point: {read['refuted']}")
    ensure(gallina.walk_failures(read["vacuous"][0])
           == ["prop_a: no one of its 9 point(s) meets its premise, so it holds vacuously"],
           f"a walk no point of which meets its premise holds vacuously: {read['vacuous']}")
    for label in ("malformed", "short", "superscript"):
        ensure(read[label][0] == []
               and "not `name points premise refuted first`" in read[label][1],
               f"a line that is not a walk is an error: {read[label]}")
    for label in ("premise past the domain", "refuted past the domain",
                  "refuted with no first", "first with none refuted",
                  "first past the domain"):
        ensure(read[label][0] == [] and "whose counts disagree" in read[label][1],
               f"a walk whose counts disagree is an error, not a verdict: {read[label]}")
    ensure(read["empty"][0] == [] and "printed no quoted vector" in read["empty"][1],
           f"a walk harness printing nothing is an error: {read['empty']}")
    ensure(gallina.walk_failures([gallina.Walk("none", 0, 0, 0, None)])
           == ["none: its domain holds no point, so it decides nothing"],
           "an empty domain decides nothing")


def _a_drawn_harness_that_does_not_build_decides_nothing() -> None:
    """A compile of the drawn harness that failed and refuted no set decided nothing,
    the sets after the failure never having run, and neither did one that printed no
    verdict: each is read as no set passed or failed, with why, never as sets a draw
    refuted. A refuted set is read as one whether or not the compile failed after it. A
    set whose extracted program built and did not finish decided nothing either, and
    the reason names the program as QuickChick's plugin reports it, on the prover's
    `Error:` line or the one after it; a build error printed over several lines is
    named by its first line after the bare `Error:`."""
    error = "Error: The reference foo was not found"
    program = "time /tmp/QuickChick1/Properties.native"
    crashed = (f'File "./harness/Properties.v", line 9, characters 0-40:\nError:\n'
               f"{program}: Exited with status 2\n\nFatal error: exception Stack_overflow\n")
    printed = {"broken": (1, "", error),
               "broken after a pass": (1, "+++ Passed 10000 tests\n", error),
               "broken over lines": (1, "", "Error:\nThe reference foo was not found\n"
                                           "in the current environment.\n"),
               "crashed after a pass": (1, "+++ Passed 10000 tests\n", crashed),
               "killed": (1, "", f"Error: {program}: Killed (-7)\n"),
               "silent": (0, "", ""),
               "refuted": (0, "+++ Passed 10000 tests\n*** Failed after 3 tests\n", ""),
               "refuted then broken": (1, "*** Failed after 3 tests\n", error),
               "passed": (0, "+++ Passed 10000 tests\n" * 2, "")}
    read = {label: gallina.drawn_sets(subprocess.CompletedProcess([], code, out, err))
            for label, (code, out, err) in printed.items()}
    for label in ("broken", "broken after a pass", "broken over lines"):
        ensure(read[label] == (0, 0, f"it did not build: {error}"),
               f"a {label} harness is a build failure: {read[label]}")
    ensure(read["crashed after a pass"]
           == (0, 0, f"its extracted program did not finish: {program}: Exited with status 2")
           and read["killed"]
           == (0, 0, f"its extracted program did not finish: {program}: Killed (-7)"),
           f"a set whose program built and did not finish decided nothing, and says so: "
           f"{read['crashed after a pass']} {read['killed']}")
    ensure(read["silent"] == (0, 0, "it compiled and printed no verdict line"),
           f"a harness printing no verdict decided nothing: {read['silent']}")
    ensure(read["refuted"] == (1, 1, "*** Failed after 3 tests")
           and read["refuted then broken"] == (0, 1, "*** Failed after 3 tests"),
           f"a refuted set is read as refuted: {read}")
    ensure(read["passed"] == (2, 0, ""), f"two passing sets: {read['passed']}")


def _quickchick_rejects_other_versions() -> None:
    """QuickChick's own switch is the one asked, and a version it does not pin is refused
    there before anything is staged, the refusal naming both versions."""
    asked: list[str] = []

    def held(switch: str) -> str:
        asked.append(switch)
        return "2.1.0"

    with (patch.object(quickchick, "installed", side_effect=held),
          patch.object(gallina, "prover", return_value=["rocq", "c"]),
          patch.object(gallina, "version", return_value="9.1.1"),
          patch.object(gallina, "stage") as stage,
          redirect_stdout(io.StringIO()) as output):
        ensure(quickchick.cmd_check(argparse.Namespace(recipe=False)) == 1,
               "an old installed QuickChick must not pass the check")
        ensure(quickchick._properties(argparse.Namespace(recipe=False), Mock(), Path(), Path()) == 1,
               "an old installed QuickChick must not run the properties")
        ensure(stage.call_count == 0, "the wrong version must be refused before staging")
        ensure("2.1.0" in output.getvalue() and quickchick.VERSION in output.getvalue(),
               "a wrong-version refusal must name installed and required versions")
    ensure(set(asked) == {gallina.QUICKCHICK_SWITCH},
           f"the randomized half asked switches other than QuickChick's: {asked}")
    with (patch.object(quickchick, "installed", return_value=quickchick.VERSION),
          patch.object(gallina, "prover", return_value=["rocq", "c"]),
          patch.object(gallina, "version", return_value="9.1.1"),
          redirect_stdout(io.StringIO()) as output):
        ensure(quickchick.cmd_check(argparse.Namespace(recipe=False)) == 0
               and "`run.py quickchick properties` runs" in output.getvalue(),
               f"the configured QuickChick release must pass the check, naming the run in "
               f"its switch: {output.getvalue()}")


def _the_recipe_pins_whole_commits_and_is_asked_by_name() -> None:
    """QuickChick's recipe pins each upstream to one whole commit, creates the switch the
    recipe's constants name at the repository's OCaml, pins before it installs, and
    installs every pinned package beside the Rocq, Stdlib and dune it states; and
    `check --recipe` asks that switch alone and holds the pinned commit, a release
    refused there."""
    convention = (f"verifiedos-quickchick-{gallina.QUICKCHICK_RECIPE_ROCQ_VERSION}-ocaml-"
                  f"{env.OCAML_VERSION}")
    ensure(convention == gallina.QUICKCHICK_RECIPE_SWITCH,
           "the recipe's switch does not follow the project's naming convention")
    pins = {name: (url, commit) for name, url, commit in quickchick.PINS}
    ensure(set(pins) == {"coq-ext-lib", "coq-simple-io", quickchick.PACKAGE}
           and all(re.fullmatch(r"[0-9a-f]{40}", commit) for _, commit in pins.values()),
           f"the recipe pins the three upstreams, each to one whole commit: {pins}")
    switch = gallina.QUICKCHICK_RECIPE_SWITCH
    create, *pinning, install = quickchick.RECIPE
    ensure(create[:4] == ("opam", "switch", "create", switch)
           and f"--packages=ocaml-base-compiler.{env.OCAML_VERSION}" in create,
           f"the recipe creates its switch at the repository's OCaml: {create}")
    ensure([step[:4] for step in pinning] == [("opam", "pin", "add", f"--switch={switch}")] * 3
           and [step[-2:] for step in pinning]
           == [(f"{name}.dev", f"git+{url}#{commit}") for name, (url, commit) in pins.items()],
           f"the recipe pins each package to its commit before installing: {pinning}")
    ensure(install[:3] == ("opam", "install", f"--switch={switch}")
           and {f"rocq-core.{gallina.QUICKCHICK_RECIPE_ROCQ_VERSION}",
                f"rocq-stdlib.{quickchick.STDLIB}", f"dune.{quickchick.DUNE}",
                *(f"{name}.dev" for name in pins)} <= set(install),
           f"the recipe installs the pinned packages beside its Rocq and dune: {install}")
    url, commit = pins[quickchick.PACKAGE]
    ensure(f"git+{url}#{commit}" == quickchick.RECIPE_PIN,
           "the pin a check holds is QuickChick's in the recipe")
    asked: list[str] = []
    for source, code in ((quickchick.RECIPE_PIN, 0), ("2.2.0", 1)):
        def held(switch: str, source: str = source) -> str:
            asked.append(switch)
            return source

        with (patch.object(quickchick, "installed", side_effect=held),
              patch.object(gallina, "prover", return_value=["rocq", "c"]),
              patch.object(gallina, "version", return_value="9.3.0"),
              redirect_stdout(io.StringIO()) as output):
            ensure(quickchick.cmd_check(argparse.Namespace(recipe=True)) == code,
                   f"a recipe switch holding {source} must exit {code}: {output.getvalue()}")
        ensure(code != 0
               or "`run.py quickchick properties --recipe` runs" in output.getvalue(),
               f"a passing `check --recipe` names the run in the recipe's switch: "
               f"{output.getvalue()}")
    ensure(set(asked) == {switch}, f"`check --recipe` asked other switches: {asked}")


def _the_installed_quickchick_is_read_without_answering() -> None:
    """The QuickChick a switch holds is asked of opam with no standard input and no
    answer inherited from the caller's environment, in any case the caller names it, so
    a format upgrade the list would ask about is declined; the root is passed on. What
    opam prints is read as the pinned source or the release, and a list that did not
    exit 0 reads as holding none."""
    answers = {"OPAMYES": "1", "OpamConfirmLevel": "unsafe-yes", "OPAMROOT": "/elsewhere"}
    printed = {"pinned": (0, f"dev {quickchick.RECIPE_PIN}\n", quickchick.RECIPE_PIN),
               "released": (0, f"{quickchick.VERSION}\n", quickchick.VERSION),
               "absent": (0, "", None),
               "declined": (1, f"{quickchick.VERSION}\n", None)}
    for label, (code, out, want) in printed.items():
        with (patch.dict(os.environ, answers),
              patch.object(quickchick.subprocess, "run",
                           return_value=subprocess.CompletedProcess(["opam"], code, out,
                                                                    "")) as run):
            read = quickchick.installed("s")
        passed = run.call_args.kwargs.get("env") or {}
        ensure(run.call_args.args[0] == ["opam", "list", "--switch", "s", "--installed",
                                         "--short", "--columns=version,pin",
                                         quickchick.PACKAGE]
               and run.call_args.kwargs.get("stdin") is subprocess.DEVNULL,
               f"{label}: opam lists the switch's installed QuickChick with its version "
               f"and pin, its standard input closed: {run.call_args.args} "
               f"stdin={run.call_args.kwargs.get('stdin')!r}")
        ensure(not {key.upper() for key in passed} & set(env.OPAM_ANSWERS)
               and passed.get("OPAMROOT") == "/elsewhere",
               f"{label}: opam list is passed no answer and keeps the root: {sorted(passed)}")
        ensure(read == want, f"{label}: opam's list reads as {read!r}, not {want!r}")


def _a_switch_environment_answers_no_question() -> None:
    """`opam env` for a prover's switch, its output captured, reads no standard input and
    inherits no answer from the caller's environment, in any case the caller names it,
    so a format upgrade it would ask about is declined rather than left on a prompt the
    caller cannot see or answered by the caller's settings; the rest of the environment,
    the root among it, is passed on, and what it prints is read back."""
    answers = {"OPAMYES": "1", "OpamConfirmLevel": "unsafe-yes", "OPAMROOT": "/elsewhere"}
    printed = "OPAMSWITCH='s'; export OPAMSWITCH;\n"
    with (patch.dict(os.environ, answers),
          patch.object(gallina.subprocess, "run",
                       return_value=subprocess.CompletedProcess(["opam"], 0, printed)) as run):
        read = gallina.switch_env("s")
    passed = run.call_args.kwargs.get("env") or {}
    ensure(run.call_args.args[0][:2] == ["opam", "env"]
           and run.call_args.kwargs.get("stdin") is subprocess.DEVNULL,
           f"opam env's standard input is closed: {run.call_args}")
    ensure(not {key.upper() for key in passed} & set(env.OPAM_ANSWERS)
           and passed.get("OPAMROOT") == "/elsewhere",
           f"opam env is passed no answer and keeps the root: {sorted(passed)}")
    ensure(read == {"OPAMSWITCH": "s"}, f"what opam env prints is read back: {read}")


# A child that beats into a file until it is ended, and a prover that starts one, as
# QuickChick's prover starts a drawn set's extracted program, and then outlasts any limit
# a case lowers to. The prover writes the child's pid beside the beats, so a case that
# fails can still end it, and sleeps only once the child has beaten.
_BEAT = """\
import sys
import time
from pathlib import Path

while True:
    with Path(sys.argv[1]).open("a", encoding="utf-8") as beats:
        beats.write(".")
    time.sleep(0.05)
"""
_SPAWNING_PROVER = """\
import subprocess
import sys
import time
from pathlib import Path

here = Path(__file__).parent
child = subprocess.Popen([sys.executable, str(here / "beat.py"), str(here / "beats")],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
(here / "child.pid").write_text(str(child.pid), encoding="utf-8")
while not (here / "beats").exists():
    time.sleep(0.01)
time.sleep(120)
"""


def _a_stopped_compile_ends_what_the_prover_started() -> None:
    """A compile stopped at its limit ends the prover's whole process group, not the
    prover alone: a drawn set's extracted program, which QuickChick runs as the prover's
    child, left running would load every later compile of the run. Here the stub
    prover's child stops beating once the compile is stopped."""
    if sys.platform == "win32":
        raise AssertionError("process groups are POSIX-only; this case runs in the guest")
    with tempfile.TemporaryDirectory(prefix="vos-group-") as td:
        work = Path(td)
        (work / "beat.py").write_text(_BEAT, encoding="utf-8")
        (work / "prover.py").write_text(_SPAWNING_PROVER, encoding="utf-8")
        source = work / "harness" / "A.v"
        source.parent.mkdir()
        source.write_text("", encoding="utf-8")
        beats = work / "beats"
        found = gallina.Prover("stub", (sys.executable, str(work / "prover.py")))
        try:
            with patch.object(gallina, "switch_env", return_value={}):
                try:
                    gallina.compile_one(found, work, source, timeout=5)
                except gallina.CompileTimeout:
                    pass
                else:
                    raise AssertionError("the stub prover was not stopped at its limit")
            ensure(beats.is_file(), "the stub prover's child never beat, so nothing was "
                                    "decided about it")
            time.sleep(0.5)
            settled = beats.stat().st_size
            time.sleep(1.5)
            ensure(beats.stat().st_size == settled,
                   "the prover's child went on beating after its compile was stopped")
        finally:
            with suppress(OSError, ValueError):
                os.kill(int((work / "child.pid").read_text(encoding="utf-8")),
                        signal.SIGKILL)


def cases() -> list[Case]:
    return [
        Case("the waves follow the Requires", _waves_follow_requires),
        Case("the dependents are the Require closure",
             _dependents_are_the_require_closure),
        Case("a dependent closure keeps the compile order",
             _a_dependent_closure_keeps_the_compile_order),
        Case("a stem no source carries has no closure",
             _a_stem_no_source_carries_has_no_closure),
        Case("a Require cycle is refused", _a_require_cycle_is_refused),
        Case("branched dependencies keep sorted waves", _branched_dependencies_keep_sorted_waves),
        Case("cycle refusals include only blocked sources", _cycle_refusals_include_only_blocked_sources),
        Case("source index is one immutable snapshot", _source_index_is_one_immutable_snapshot),
        Case("comment lexing preserves source and newlines", _comment_lexing_preserves_source_and_newlines),
        Case("sentences end outside strings", _sentences_end_outside_strings),
        Case("the decoration grammar is one reading", _the_decoration_grammar_is_one_reading),
        Case("the look-back reads only decorations", _the_look_back_reads_only_decorations),
        Case("a bullet starts the run again", _a_bullet_starts_the_run_again),
        Case("a library Require orders nothing", _a_library_require_is_not_ordered),
        Case("staging leaves compiled artifacts behind",
             _staging_leaves_the_compiled_artifacts_behind),
        Case("staging is a fresh tree every time", _staging_is_a_fresh_tree_every_time),
        Case("the quoted segments are the vectors", _quoted_segments_are_the_vectors),
        Case("an unterminated quote yields nothing more",
             _an_unterminated_quote_yields_nothing_more),
        Case("written vectors are one per line", _written_vectors_are_one_per_line),
        Case("the two switches are named apart", _the_two_switches_are_named_apart),
        Case("the oracle candidates build from released packages",
             _the_oracle_candidates_build_from_released_packages),
        Case("the Stdlib harnesses compile in the proof switch",
             _the_stdlib_harnesses_compile_in_the_proof_switch),
        Case("the randomized support is built for that half alone",
             _the_randomized_support_is_built_for_that_half_alone),
        Case("the randomized harness compiles its closure alone",
             _the_randomized_harness_compiles_its_closure_alone),
        Case("the randomized half refuses what does not replay or hold",
             _the_randomized_half_refuses_what_does_not_replay_or_hold),
        Case("the seed and the walks are read", _the_seed_and_the_walks_are_read),
        Case("a drawn harness that does not build decides nothing",
             _a_drawn_harness_that_does_not_build_decides_nothing),
        Case("QuickChick rejects other versions", _quickchick_rejects_other_versions),
        Case("the recipe pins whole commits and is asked by name",
             _the_recipe_pins_whole_commits_and_is_asked_by_name),
        Case("the installed QuickChick is read without answering",
             _the_installed_quickchick_is_read_without_answering),
        Case("a switch's opam environment answers no question",
             _a_switch_environment_answers_no_question),
        Case("a stopped compile ends what the prover started",
             _a_stopped_compile_ends_what_the_prover_started, lane="guest"),
    ]
