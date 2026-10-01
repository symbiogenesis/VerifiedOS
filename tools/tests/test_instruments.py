# SPDX-License-Identifier: Apache-2.0
"""K-117 over fixture sources and trees: each form read, each look-alike passed, the set
derived from the table, and every reading failing closed.

The live tree exercises the clean path on every `check.py` run, and the selftest seeds
the defect the rule exists for, a proof source the Wasm oracle compiles rewritten into
Rocq 9.3's syntax. What only a fixture can pin is the rest: each of the four forms read
where a comment, a string or a neighbouring construct does not hide it, each construct
that resembles one passing, the set following the `Require` closure and the release, and
each reading that cannot be made being a finding rather than a smaller set. The clean
path does not say which proof sources the live set holds, so one case reads that too.
"""

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import corpus, env, gallina
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
        # a recursive notation's `..` ends no sentence, so its `if` still pends
        'Notation "f[ x ; .. ; y ]" :=\n'
        "  (if cons x .. (cons y nil) .. is cons _ _ then 1 else 0).": [(2, IF)],
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


def _a_rig_constant_the_instrument_binds_is_read() -> None:
    head = "import argparse\n{imports}\np = argparse.ArgumentParser()\n"
    body = ("SWITCH = {module}.ORACLE_SWITCH\nRELEASE = {module}.ORACLE_ROCQ_VERSION\n"
            'p.add_argument("--switch", default=SWITCH)\n')
    forms = {"from vos import gallina": "gallina", "from vos import env, gallina as g": "g",
             "import vos.gallina as rig": "rig"}
    for imports, module in forms.items():
        files: dict[str, str | bytes] = {
            "tools/c.py": head.format(imports=imports) + body.format(module=module)}
        with _tree(files) as root:
            switch = k117.literal(root, k117.Literal("tools/c.py", "--switch"))
            release = k117.literal(root, k117.Literal("tools/c.py", "RELEASE"))
        ensure(switch == (gallina.ORACLE_SWITCH, "") and
               release == (gallina.ORACLE_ROCQ_VERSION, ""),
               f"{imports}: the rig's constants read through the file's names: "
               f"{switch} {release}")
    unread = {
        "a module named gallina outside vos": ("import gallina", "gallina.ORACLE_ROCQ_VERSION"),
        "a constant the rig does not hold": ("from vos import gallina", "gallina.ABSENT"),
        "a constant that is no string": ("from vos import gallina", "gallina.ENTRY_POINTS"),
        "a rig name the module rebinds": ("from vos import gallina\ngallina = None",
                                          "gallina.ORACLE_ROCQ_VERSION"),
        "a rig name defined again": ("from vos import gallina\ndef gallina() -> None: ...",
                                     "gallina.ORACLE_ROCQ_VERSION"),
        "a rig imported only in a function": (
            "def load() -> object:\n    from vos import gallina\n    return gallina",
            "gallina.ORACLE_ROCQ_VERSION"),
    }
    for label, (imports, value) in unread.items():
        files = {"tools/c.py": head.format(imports=imports) + f"RELEASE = {value}\n"}
        with _tree(files) as root:
            got = k117.literal(root, k117.Literal("tools/c.py", "RELEASE"))
        ensure(got[0] is None and "module-level string RELEASE" in got[1],
               f"{label} is unread, not a release: {got}")


def _a_subject_the_instrument_names_is_read() -> None:
    driver = ("import argparse\nfrom pathlib import Path\n"
              "HERE = Path(__file__).resolve().parent\n"
              "OWNER = HERE.parent.parent / {owner}\n"
              "p = argparse.ArgumentParser()\n"
              'p.add_argument("--owner", default=str(OWNER))\n')
    files: dict[str, str | bytes] = {
        "tools/low/drive.py": driver.format(owner='"proofs" / "Owner.v"'),
        "tools/low/D.v": "Definition d := 0.\n",
        "proofs/Owner.v": "Require Import Dep.\n",
        "proofs/Dep.v": "Definition c (o : option nat) := if o is Some n then n else 0.\n",
        "proofs/Far.v": "Definition far (o : option nat) := if o is Some n then n else 0.\n",
    }
    owner = k117.Literal("tools/low/drive.py", "--owner")
    row = k117.Instrument("low", "tools/low/drive.py", "some-switch", "9.1.1",
                          beside="tools/low", subjects=(owner,))
    with _tree(files) as root:
        read = k117.literal(root, owner)
    ensure(read == ("proofs/Owner.v", ""), f"the default owner reads as its path: {read}")
    found, _ = _decide(files, [row])
    ensure([f.split(" ")[0] for f in found] == ["proofs/Dep.v:1"],
           f"the owner brings its closure and nothing past it: {found}")
    for escape in (driver.format(owner='".." / "Owner.v"'),
                   driver.replace("HERE.parent", "HERE.parent.parent").format(owner='"x.v"')):
        left, _ = _decide({**files, "tools/low/drive.py": escape}, [row])
        ensure(any("0 string default of its --owner option" in f for f in left),
               f"a path that leaves the checkout is unread, not dropped: {left}")
    moved = {**files, "tools/low/drive.py": driver.format(owner='"proofs" / "Gone.v"')}
    gone, _ = _decide(moved, [row])
    ensure(any("'proofs/Gone.v', which the git index does not carry" in f for f in gone),
           f"an owner the index does not carry is a finding: {gone}")


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
    spelled: dict[str, str | bytes] = {
        "tools/vos/alias.py": "from vos.gallina import prover as locate\nfound = locate('s')\n",
        "tools/vos/spaced.py": "from vos import gallina as g\nfound = g.prover ('s')\n",
        "tools/vos/relative.py": "from .. import gallina\nfound = gallina.prover('s')\n"}
    other, _ = _decide(spelled, [_row(release="9.3.0")])
    ensure(sorted(f.split(" ")[0] for f in other) == sorted(spelled),
           f"a call under another name or spacing is a call: {other}")


def _each_rig_module_asks_for_its_rows_switches() -> None:
    oracle, quickchick = gallina.ORACLE_SWITCH, gallina.QUICKCHICK_SWITCH

    def row(switch: str) -> k117.Instrument:
        return k117.Instrument(switch, "tools/vos/m.py", switch, "9.3.0")

    sources = {
        "the constant": ("from vos import gallina\nfound = gallina.prover(gallina.ORACLE_SWITCH)\n",
                         {oracle}),
        "a loop's tuple": ("from vos import gallina\n"
                           "def f():\n    for s in (gallina.ORACLE_SWITCH, "
                           "gallina.QUICKCHICK_SWITCH):\n        gallina.prover(s)\n",
                           {oracle, quickchick}),
        "a choice": ("from vos import gallina\n"
                     "def f(a):\n    s = gallina.QUICKCHICK_SWITCH if a else "
                     "gallina.ORACLE_SWITCH\n    return gallina.prover(s)\n",
                     {oracle, quickchick}),
        "a name bound through another": (
            "from vos import gallina\nPAIR = (gallina.ORACLE_SWITCH,)\n"
            "def f():\n    got = {s: 1 for s in PAIR}\n"
            "    s = next(k for k, v in got.items() if v)\n    return gallina.prover(s)\n",
            {oracle}),
    }
    for label, (source, asks) in sources.items():
        rows = [row(s) for s in sorted(asks)]
        quiet, _ = _decide({"tools/vos/m.py": source}, rows)
        ensure(not quiet, f"{label}: the rows state what the module asks for: {quiet}")
        moved, _ = _decide({"tools/vos/m.py": source}, [row(gallina.VECTOR_SWITCH)])
        ensure(len(moved) == 1 and "can ask gallina.prover for" in moved[0],
               f"{label}: a row stating another switch is a finding: {moved}")
    loose, _ = _decide({"tools/vos/m.py": "from vos import gallina\n"
                                          "def f(switch):\n    return gallina.prover(switch)\n"},
                       [row(oracle)])
    ensure(len(loose) == 1 and loose[0].startswith("tools/vos/m.py:3 passes gallina.prover"),
           f"an argument naming no switch constant is undecided: {loose}")
    idle, _ = _decide({"tools/vos/m.py": "found = None\n"}, [row(oracle)])
    ensure(len(idle) == 1 and "resolves no prover" in idle[0],
           f"a row naming a module that asks for nothing is a finding: {idle}")


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
    owners = [k117.literal(root, spec) for spec in lowering.subjects
              if isinstance(spec, k117.Literal)]
    ensure(owners == [("proofs/RingContract.v", "")],
           f"the lowering's default owner is read out of its driver: {owners}")
    compare = by_name["compare_component.py"]
    if not (isinstance(compare.switch, k117.Literal)
            and isinstance(compare.release, k117.Literal)):
        raise TypeError("compare_component.py states its switch and release in its own file")
    stated = (k117.literal(root, compare.switch), k117.literal(root, compare.release))
    ensure(stated == ((gallina.ORACLE_SWITCH, ""), (gallina.ORACLE_ROCQ_VERSION, "")),
           f"compare_component.py's default and release are the oracle's declared ones: "
           f"{stated}")
    named = {row.selects for row in k117.INSTRUMENTS}
    ensure({"tools/vos/copy_service.py", "tools/vos/supervisor.py"} <= named,
           "every rig caller the tree carries is a row")
    properties = {row.switch for row in k117.INSTRUMENTS
                  if row.selects == "tools/vos/cli/quickchick.py"}
    ensure(properties == {gallina.QUICKCHICK_SWITCH},
           f"quickchick properties runs in QuickChick's own switch alone: {properties}")


def _the_live_reading_reaches_only_the_older_instruments_proofs() -> None:
    """The proof sources K-117's reading of the live tree reaches: `Properties.v`'s
    closure, which `seed coq --quickchick` compiles alone, with the Wasm oracle's
    EndpointIPC.v and the lowering's RingContract.v while QuickChick's switch is older
    than Rocq 9.3.0, and those two alone once it is not. While it is older, the seed
    row's own label reaches `Properties.v` and that closure's proof sources and no other.
    The control restores that row to every proof source and finds the reading reaching
    each of them."""
    root = TOOLS.parent
    files = corpus.read_index(root).files
    proof_sources = sorted(rel for rel in files if rel.startswith(f"{k117.PROOFS}/")
                           and rel.endswith(k117.SUFFIX) and rel.count("/") == 1)

    def read(rows: tuple[k117.Instrument, ...]) -> tuple[dict[str, list[str]], list[str]]:
        found, labels, findings = k117.reach(root, files, rows)
        ensure(not findings, f"the live table reads cleanly: {findings}")
        return found, labels

    def reached(rows: tuple[k117.Instrument, ...]) -> list[str]:
        return sorted(rel for rel in read(rows)[0] if rel in proof_sources)

    def sources(*names: str) -> list[str]:
        return [f"{k117.PROOFS}/{name}{k117.SUFFIX}" for name in names]

    release = k117.release_of(gallina.QUICKCHICK_ROCQ_VERSION)
    ensure(release is not None, f"QuickChick's release reads: {gallina.QUICKCHICK_ROCQ_VERSION}")
    older = release is not None and release < k117.SINCE
    closed = ("BoundaryCost", "CyclicExecutive", "EndpointIPC", "PartitionContext")
    want = sources(*sorted({*closed, "RingContract"} if older
                           else {"EndpointIPC", "RingContract"}))
    got = reached(k117.INSTRUMENTS)
    ensure(got == want, f"the reading reaches {got}, not {want}")
    if older:
        # The seed row's own reach, apart from the "quickchick properties" rows that
        # compile the same closure: Properties.v itself and its proofs, and no more.
        found, labels = read(k117.INSTRUMENTS)
        label = next((name for name in labels if name.startswith("seed coq --quickchick ")),
                     "")
        own = sorted(rel for rel in proof_sources if label in found.get(rel, []))
        ensure(own == sources(*closed),
               f"the seed row reaches {own}, not Properties.v's closure {sources(*closed)}")
        ensure(bool(label) and label in found.get(f"{k117.RIG}/{gallina.RANDOMIZED}", []),
               f"the seed row compiles {gallina.RANDOMIZED} itself: {label!r}")
        widened = tuple(replace(row, whole=True) if row.name == "seed coq --quickchick"
                        else row for row in k117.INSTRUMENTS)
        every = reached(widened)
        ensure(every == proof_sources and len(every) > len(want),
               f"a row compiling every proof source reaches each of them: {every}")


def cases() -> list[Case]:
    return [Case(fn.__name__, fn) for fn in (
        _each_form_is_read,
        _look_alikes_pass,
        _code_keeps_lines_and_blanks_strings,
        _the_set_follows_closure_and_release,
        _readings_fail_closed,
        _an_option_default_is_read,
        _a_rig_constant_the_instrument_binds_is_read,
        _a_subject_the_instrument_names_is_read,
        _an_unlisted_prover_caller_is_a_finding,
        _each_rig_module_asks_for_its_rows_switches,
        _the_live_rows_read_their_instruments,
        _the_live_reading_reaches_only_the_older_instruments_proofs,
    )]
