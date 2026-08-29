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

import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import gallina, proofs

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


def _a_require_cycle_is_refused() -> None:
    with _tree({"A.v": "Require Import B.\n", "B.v": "Require Import A.\n"}) as td:
        root = Path(td)
        try:
            proofs.waves(sorted(root.glob("*.v")))
        except SystemExit as err:
            ensure("Require cycle" in str(err), f"the refusal said {err!r}")
            return
    raise AssertionError("a cycle was given a compile order")


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


def cases() -> list[Case]:
    return [
        Case("the waves follow the Requires", _waves_follow_requires),
        Case("a Require cycle is refused", _a_require_cycle_is_refused),
        Case("a library Require orders nothing", _a_library_require_is_not_ordered),
        Case("staging leaves compiled artifacts behind",
             _staging_leaves_the_compiled_artifacts_behind),
        Case("staging is a fresh tree every time", _staging_is_a_fresh_tree_every_time),
        Case("the quoted segments are the vectors", _quoted_segments_are_the_vectors),
        Case("an unterminated quote yields nothing more",
             _an_unterminated_quote_yields_nothing_more),
        Case("written vectors are one per line", _written_vectors_are_one_per_line),
        Case("the two switches are named apart", _the_two_switches_are_named_apart),
    ]
