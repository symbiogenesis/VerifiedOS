# SPDX-License-Identifier: Apache-2.0
"""K-117 over fixture sources and trees: each form read, each look-alike passed, the set
derived from the table, and every reading failing closed.

The live tree exercises the clean path on every `check.py` run, and the selftest seeds
the defect the rule exists for, a proof source the Wasm oracle compiles rewritten into
Rocq 9.3's syntax. What only a fixture can pin is the rest: each of the four forms read
where a comment, a string or a neighbouring construct does not hide it, each construct
that resembles one passing, the set following the `Require` closure and the release, and
each reading that cannot be made being a finding rather than a smaller set.
"""

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import env, gallina
from vos.checks import instruments as k117

IF, WITH, AMP, OF = k117.FORM_IF, k117.FORM_WITH, k117.FORM_AMP, k117.FORM_OF


@contextmanager
def _tree(files: dict[str, str | bytes]) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="vos-k117-") as td:
        root = Path(td)
        for rel, content in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8", newline="")
        yield root


def _row(release: str | k117.Literal | None = "9.1.1", *, harnesses: tuple[str, ...] = (),
         beside: str = "", whole: bool = False) -> k117.Instrument:
    return k117.Instrument("old", "tools/x.py", "some-switch", release,
                           harnesses=harnesses, beside=beside, whole=whole)


def _decide(files: dict[str, str | bytes],
            rows: list[k117.Instrument]) -> tuple[list[str], str]:
    with _tree(files) as root:
        return k117.decide(root, files, rows)


def _each_form_is_read() -> None:
    cases = {
        "Definition f (o : option nat) : nat :=\n  if o is Some n then n else 0.": [(2, IF)],
        "Definition f (b : bool) (o : option nat) :=\n"
        "  if b then (if o is Some n then n else 0) else 1.": [(2, IF)],
        "Definition g (r : R) : R := {| r with f1 := 0 |}.": [(1, WITH)],
        "Definition g r := {| (match r with | _ => r end) with f1 := 0 |}.": [(1, WITH)],
        "Definition h (n : nat) & n = 0 : nat := n.": [(1, AMP)],
        "Definition h := (fun (n : nat) & n = 0 => n).": [(1, AMP)],
        "Variant t := C1 of nat & bool.": [(1, OF), (1, AMP)],
        # a focusing brace opens the sentence and is not the bracket around its text
        "Proof.\n{ intros n & H.": [(2, AMP)],
        # a binder list open inside a brace, whether a field list's or a sigma type's
        "Record R := { f : forall & nat, nat }.": [(1, AMP)],
        "Record R := Mk { g : nat; h : forall (n : nat) & n = 0, True }.": [(1, AMP)],
        "Definition s := {x : nat & forall & x = 0, True}.": [(1, AMP)],
        "Definition s := {x : nat | forall & x = 0, True}.": [(1, AMP)],
        "Class C := { m : forall & nat, nat }.": [(1, AMP)],
        "Definition t := {x : nat & fun & nat => x}.": [(1, AMP)],
        "Definition e := {x : nat & exists & x = 0, True}.": [(1, AMP)],
        "Definition l := {x : nat & let h & nat := True in h}.": [(1, AMP)],
        "Definition s := {x : nat & x = 0 & forall & x = 0, True}.": [(1, AMP)],
        # a field's own binders, directly inside the braces of a declaration's fields
        "Record R := { f (n : nat) & n = 0 : nat }.": [(1, AMP)],
        "#[global] Instance i : C := { m & nat := 0 }.": [(1, AMP)],
        "Inductive I := MkI { i & nat : nat }.": [(1, AMP)],
    }
    for source, want in cases.items():
        got = k117.forms(source)
        ensure(got == want, f"{source!r} read as {got}, not {want}")


def _look_alikes_pass() -> None:
    sources = [
        "(* if o is Some n then n else 0; {| r with f := 0 |}; & ; C of nat *)",
        'Definition s := "if o is x then {| r with f := 0 |} & of".',
        'Definition s := "a ""quoted"" if x is y". Definition t := 0.',
        "Definition b (x : bool) := if x then 1 else 0.",
        "Definition r x := {| f1 := match x with | A => 1 | B => 2 end; f2 := 0 |}.",
        "Definition r := {| f1 := {| g := 1 |}; f2 := 0 |}.",
        "Definition sg := {x : nat & x = 0}. Definition sg2 := { x & P x & Q x }.",
        "Definition sg3 := {x | P x & Q x}. Definition a x y z := x && y && z.",
        "Definition is_true b := b = true. Definition this := of_nat offset.",
        "Definition is' := 0. Definition of' := is'. Definition x'is := 1.",
        "Proof. { exact (existT _ 0 eq_refl : {x : nat & x = 0}). } Qed.",
        "Definition r := {| f := [| 1; 2 | 0 |]; g := 0 |}.",
        # `exists2`'s own separator, after its binders, and a sigma body's closed binders
        "Definition e := exists2 x, x = 0 & x = 1.",
        "Definition e := (exists2 x : nat, forall y : nat, y = x & x = 1) /\\ True.",
        "Definition e := {x : nat & exists2 y, x = y & y = 0}.",
        "Definition s := {x : nat & forall y : nat, x = y & True}.",
        "Definition s := {x : nat & (fun y : nat => True) x & True}.",
        # a sigma type where a declaration's fields would be, and one exists2 among them
        "Record R (p : {x : nat & x = 0}) := { f : {x : nat | x = 0 & True} }.",
        "Inductive t := K : {x : nat & x = 0} -> t.",
        "Record R := { e : exists2 x, x = 0 & x = 1 }.",
    ]
    for source in sources:
        got = k117.forms(source)
        ensure(got == [], f"{source!r} read as {got}")


def _code_keeps_lines_and_blanks_strings() -> None:
    source = 'Definition s := "a\nb".\n(* c\nd *) Definition t := 0.'
    blanked = k117.code(source)
    ensure(blanked.count("\n") == source.count("\n"),
           "blanking moved a line break, so every later finding names the wrong line")
    ensure(blanked.startswith("Definition s :=") and not blanked[15:21].strip()
           and blanked.rstrip().endswith("Definition t := 0."),
           f"a string's inside survived blanking, or code went with it: {blanked!r}")


def _the_set_follows_closure_and_release() -> None:
    files: dict[str, str | bytes] = {
        "proofs/A.v": "Variant a := A1 of nat.\n",
        "proofs/B.v": "Require Import A.\nDefinition b := 0.\n",
        "proofs/C.v": "Definition c (o : option nat) := if o is Some n then n else 0.\n",
        "tools/h/H.v": "From Stdlib Require Import List.\nRequire Import B.\n",
    }
    closure, _ = _decide(files, [_row(harnesses=("tools/h/H.v",))])
    ensure(len(closure) == 1 and closure[0].startswith("proofs/A.v:1 writes an `of`"),
           f"the harness reaches A through B and never C: {closure}")
    whole, _ = _decide(files, [_row(whole=True)])
    ensure(sorted(f.split(" ")[0] for f in whole) == ["proofs/A.v:1", "proofs/C.v:1"],
           f"a row compiling every proof source reads all of them: {whole}")
    current, ok = _decide(files, [_row(release="9.3.0", whole=True),
                                  _row(release="10.0.0", harnesses=("tools/h/H.v",))])
    ensure(not current and "0 of the table's 2" in ok,
           f"a row at 9.3.0 or later contributes nothing: {current} / {ok}")
    unstated, _ = _decide(files, [_row(release=None, beside="tools/h")])
    ensure(len(unstated) == 1 and "no stated release" in unstated[0],
           f"a row stating no release is held older: {unstated}")


def _readings_fail_closed() -> None:
    files: dict[str, str | bytes] = {
        "proofs/A.v": "Definition a := 0.\n",
        "proofs/Loop.v": "Require Import Again.\n",
        "tools/c/Again.v": "Require Import Loop.\n",
        "tools/d/A.v": "Definition twin := 0.\n",
        "tools/e/Bad.v": b"Definition \xff := 0.\n",
        "tools/lit.py": 'NAME: str = "verifiedos-x-9.1.1-ocaml-5.4.1"\n',
    }
    missing = k117.Literal("tools/lit.py", "ABSENT")
    cases: list[tuple[list[k117.Instrument], str]] = [
        ([], "the instrument table is empty"),
        ([_row(release=missing, beside="tools/d")], "0 module-level string ABSENT"),
        ([_row(release=k117.Literal("tools/lit.py", "NAME", r"-z-(\d+)"))],
         "carries no value"),
        ([_row(release="9.x")], "which is not a release"),
        ([_row(harnesses=("tools/h/H.v",))], "the git index does not carry"),
        ([_row(beside="tools/empty")], "carries none there"),
        ([_row()], "derives no file"),
        ([_row(beside="tools/d")], "share the stem A"),
        ([_row(beside="tools/c")], "cannot be ordered"),
        ([_row(beside="tools/e")], "cannot be read"),
    ]
    for rows, said in cases:
        found, _ = _decide(files, rows)
        ensure(any(said in finding for finding in found),
               f"{said!r} was not reported for {rows}: {found}")
    read = k117.literal
    with _tree(files) as root:
        value, why = read(root, k117.Literal("tools/lit.py", "NAME", r"-x-(\d+\.\d+\.\d+)-"))
    ensure((value, why) == ("9.1.1", ""), f"an annotated literal reads: {value!r} {why!r}")


def _an_option_default_is_read() -> None:
    files: dict[str, str | bytes] = {
        "tools/opt.py": "import argparse\np = argparse.ArgumentParser()\n"
                        'p.add_argument("--switch", default="legacy-9.1")\n'
                        'p.add_argument("--other", default="nothing")\n'}
    with _tree(files) as root:
        got = k117.literal(root, k117.Literal("tools/opt.py", "--switch"))
        none = k117.literal(root, k117.Literal("tools/opt.py", "--absent"))
    ensure(got == ("legacy-9.1", ""), f"the option's default reads: {got}")
    ensure(none[0] is None and "0 string default" in none[1], f"an absent option: {none}")


def _an_unlisted_prover_caller_is_a_finding() -> None:
    caller = "from vos import gallina\nfound = gallina.prover('s')\n"
    definer = "def prover(switch):\n    return None\n"
    files: dict[str, str | bytes] = {"tools/vos/new.py": caller,
                                     "tools/vos/own.py": definer,
                                     "tools/vos/checks/probe.py": caller}
    found, _ = _decide(files, [_row(release="9.3.0")])
    ensure(len(found) == 1 and found[0].startswith("tools/vos/new.py resolves a prover"),
           f"only the undeclared caller is a finding: {found}")
    named = k117.Instrument("new", "tools/vos/new.py", "s", "9.3.0")
    quiet, _ = _decide(files, [named])
    ensure(not quiet, f"a caller a row names is the table's: {quiet}")
    unread, _ = _decide({**files, "tools/vos/bad.py": b"x = '\xff'\n"}, [named])
    ensure(len(unread) == 1 and unread[0].startswith("tools/vos/bad.py cannot be read"),
           f"a module the scan cannot read is undecided, not skipped: {unread}")


def _the_live_rows_read_their_instruments() -> None:
    root = TOOLS.parent
    by_name = {row.name: row for row in k117.INSTRUMENTS}
    ensure(by_name["quickchick vectors"].release == env.ROCQ_VERSION
           == gallina.VECTOR_ROCQ_VERSION,
           "the vector rows compile at the gate's release")
    ensure(by_name["quickchick properties"].release == gallina.QUICKCHICK_ROCQ_VERSION
           and by_name["quickchick properties"].switch == gallina.QUICKCHICK_SWITCH,
           "the QuickChick rows read QuickChick's own constants")
    lowering = by_name["the Rupicola lowering"]
    switch_spec, release_spec = lowering.switch, lowering.release
    if not (isinstance(switch_spec, k117.Literal) and isinstance(release_spec, k117.Literal)):
        raise TypeError("the lowering has no constant to import and is read from its "
                        "own file")
    switch, _ = k117.literal(root, switch_spec)
    release, _ = k117.literal(root, release_spec)
    ensure(switch is not None and release is not None and release in switch,
           f"the lowering's release is read out of its switch: {switch!r}, {release!r}")
    compare = by_name["compare_component.py"]
    ensure(isinstance(compare.switch, k117.Literal) and compare.release is None,
           "compare_component.py states a switch and no release")
    named = {row.selects for row in k117.INSTRUMENTS}
    ensure({"tools/vos/copy_service.py", "tools/vos/supervisor.py"} <= named,
           "every rig caller the tree carries is a row")


def cases() -> list[Case]:
    return [Case(fn.__name__, fn) for fn in (
        _each_form_is_read,
        _look_alikes_pass,
        _code_keeps_lines_and_blanks_strings,
        _the_set_follows_closure_and_release,
        _readings_fail_closed,
        _an_option_default_is_read,
        _an_unlisted_prover_caller_is_a_finding,
        _the_live_rows_read_their_instruments,
    )]
