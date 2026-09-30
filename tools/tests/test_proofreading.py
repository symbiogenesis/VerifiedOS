# SPDX-License-Identifier: Apache-2.0
"""The elaborated reading's framing, parse and comparison, and its native controls.

The host cases hold the parse against answers transcribed from the pinned Rocq 9.3.0,
each beside the shape it must refuse, and hold the command to reading only a compile
that passed. The toolchain case reads a two-module fixture, which the command compiles
with the proof gate's flags, and holds the comparison to naming exactly the change each
control makes to the leaf module, and nothing for the edits that change no meaning.
"""

import contextlib
import io
import json
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import IO, Any
from unittest.mock import patch

from jsonschema import Draft202012Validator

from tests.harness import TOOLS, Case, ensure
from vos import env, proofaudit, proofreading, receipts
from vos.cli import proof_reading as cli
from vos.cli import proofs as proofs_cli

_SHA = "0" * 64

# `About A.five_is.` and `About A.color.` in a module declaring them, under the
# reading's settings: a statement, a blank line, then one sentence per fact.
_ABOUT_OPAQUE = """\
A.five_is : @eq nat A.five (S (S (S (S (S O)))))

A.five_is is not universe polymorphic
A.five_is is opaque
Expands to: Constant A.five_is
Declared in library A, line 3, characters 6-13"""

_ABOUT_INDUCTIVE = """\
A.color : Set

A.color is not universe polymorphic
Expands to: Inductive A.color
Declared in library A, line 6, characters 10-15"""

# Rocq 9.3 names the template level and what it may be instantiated to.
_ABOUT_TEMPLATE = """\
A.mkbox : forall (A : Type@{A.box.u0}) (_ : A), A.box A

A.mkbox is template universe polymorphic on A.box.u0 (can be instantiated to Prop)
Arguments A.mkbox A%_type_scope unbox
Expands to: Constructor A.mkbox
Declared in library A, line 8, characters 28-33"""

_ABOUT_PROJECTION = """\
A.px : forall _ : A.pt, nat

A.px is not universe polymorphic
A.px is a projection of A.pt
Arguments A.px p
A.px is transparent
Expands to: Constant A.px
Declared in library A, line 7, characters 27-29"""

_ABOUT_POLYMORPHIC = """\
A.pid@{u} : forall (A : Type@{u}) (_ : A), A
(* u |  *)

A.pid is universe polymorphic
Arguments A.pid A%_type_scope a
A.pid is transparent
Expands to: Constant A.pid
Declared in library A, line 11, characters 37-40"""

# `Check @B.upoly.` twice and then `Check @A.pid.` in one query process: the fresh
# levels are named after the query file and a counter over the whole process.
_CHECK_POLYMORPHIC = """\
B.upoly@{VosReadingFacts_B.22}
     : forall (A : Type@{VosReadingFacts_B.22}) (_ : A), A
(* {VosReadingFacts_B.22} |
Normalized constraints:
 {VosReadingFacts_B.22} |  *)"""


def _refused(action: Callable[[], object], why: str) -> None:
    try:
        action()
    except proofreading.ReadingError:
        return
    raise AssertionError(why)


def _entry(name: str, body: str | None = "= 0", *, kind: str = "Constant",
           opacity: str = "transparent") -> proofreading.Entry:
    return {"kind": kind, "opacity": opacity, "universes": "monomorphic",
            "check": f"{name}\n     : nat", "about": f"{name} : nat\n\n{name} is {opacity}",
            "print": None if body is None else f"{name} {body}"}


def _reading(modules: dict[str, dict[str, proofreading.Entry]],
             prover: str = "The Rocq Prover, version 9.3.0") -> proofreading.Reading:
    return {"format": proofreading.FORMAT, "schema": proofreading.SCHEMA,
            "reader": {"prover": prover, "prover_sha256": _SHA,
                       "query_flags": list(proofs_cli.STRICT),
                       "inventory_settings": proofaudit.SETTINGS,
                       "reading_settings": proofreading.SETTINGS},
            "modules": {stem: {"constants": constants} for stem, constants in modules.items()},
            "provenance": {"sources": {f"{stem}.v": _SHA for stem in modules},
                           "objects": {f"{stem}.vo": _SHA for stem in modules}}}


def _queries_frame_every_answer() -> None:
    facts = proofreading.facts_query("M", ["M.a", "M.N.b'"])
    for key, command in (("M.a|check", "Check @M.a."), ("M.a|about", "About M.a."),
                         ("M.N.b'|check", "Check @M.N.b'."), ("M.N.b'|about", "About M.N.b'.")):
        frame = f'Goal True. Proof. idtac "{proofreading.MARKER}{key}". Abort.\n{command}\n'
        ensure(frame in facts, f"{key} is not framed by its own marker: {facts!r}")
    bodies = proofreading.bodies_query("M", ["M.a"])
    ensure(bodies.count("Goal True. Proof. ") == 1 and "Print M.a.\n" in bodies,
           f"a body query frames each Print: {bodies!r}")
    ensure(facts.startswith("Require M.\n" + proofreading.SETTINGS),
           "the query Requires its module alone, then states the reading's settings")
    for line in ("Set Printing All.", "Set Printing Universes.",
                 "Set Printing Depth 1000000.", "Set Printing Width 1000000."):
        ensure(line in proofreading.SETTINGS.splitlines(), f"{line} is not set")
        ensure(line == "Set Printing Universes." or line in proofaudit.SETTINGS,
               f"{line} is not the audit's own setting")
    _refused(lambda: proofreading.facts_query("M", ["M.a. Axiom x : False"]),
             "a name that is not a qualified identifier cannot reach a query")
    _refused(lambda: proofreading.check_module("VosReadingFacts_M"),
             "a module named like a query file would share its universe names")
    _refused(lambda: proofreading.check_module("M-1"), "a module name Require cannot name")


def _answers_refuse_what_was_not_asked() -> None:
    marker = proofreading.MARKER
    stdout = (f"{marker}M.a|check\nM.a\n     : nat\n{marker}M.a|about\n"
              f"M.a : nat\n\nM.a is transparent\n\n")
    keys = ["M.a|check", "M.a|about"]
    found = proofreading.answers(stdout, keys)
    ensure(found == {"M.a|check": "M.a\n     : nat",
                     "M.a|about": "M.a : nat\n\nM.a is transparent"},
           f"each answer belongs to its marker, blank edges trimmed and inside kept: {found}")
    for label, text, asked in (
            ("unframed", "Warning: stray\n" + stdout, keys),
            ("missing", stdout, [*keys, "M.b|check"]),
            ("unasked", stdout, keys[:1]),
            ("repeated", stdout + f"{marker}M.a|about\nagain\n", keys),
            ("reordered", stdout, keys[::-1]),
            ("empty", f"{marker}M.a|check\n\n{marker}M.a|about\nM.a : nat\n", keys)):
        _refused(lambda text=text, asked=asked: proofreading.answers(text, asked),
                 f"a {label} answer was accepted")


def _about_keeps_every_fact_but_locations() -> None:
    opaque = proofreading.parse_about("A.five_is", _ABOUT_OPAQUE)
    ensure((opaque.kind, opaque.opacity, opaque.universes, opaque.printed)
           == ("Constant", "opaque", "monomorphic", False), f"an opaque constant: {opaque}")
    ensure("Declared in" not in opaque.text and opaque.text.endswith("Constant A.five_is"),
           f"the location line is dropped and nothing else: {opaque.text!r}")
    inductive = proofreading.parse_about("A.color", _ABOUT_INDUCTIVE)
    ensure((inductive.kind, inductive.opacity, inductive.printed) == ("Inductive", "n/a", True),
           f"an inductive states no opacity and is printed: {inductive}")
    template = proofreading.parse_about("A.mkbox", _ABOUT_TEMPLATE)
    ensure((template.kind, template.universes, template.printed)
           == ("Constructor", "template", False), f"9.3's template sentence: {template}")
    projection = proofreading.parse_about("A.px", _ABOUT_PROJECTION)
    ensure(projection.printed and "A.px is a projection of A.pt\nArguments A.px p"
           in projection.text, f"About's other lines are kept: {projection.text!r}")
    polymorphic = proofreading.parse_about("A.pid", _ABOUT_POLYMORPHIC)
    ensure(polymorphic.universes == "polymorphic" and "(* u |  *)" in polymorphic.text,
           f"a polymorphic constant keeps its declared universe binders: {polymorphic}")
    for label, text in (
            ("no sentence block", _ABOUT_OPAQUE.replace("\n\n", "\n")),
            ("no expansion", _ABOUT_OPAQUE.replace("Expands to: Constant A.five_is\n", "")),
            ("another expansion", _ABOUT_OPAQUE.replace("Constant A.five_is", "Constant A.x")),
            ("an unplaced kind", _ABOUT_OPAQUE.replace("Constant A.five_is", "Module A.five_is")),
            ("no universe sentence", _ABOUT_OPAQUE.replace(
                "A.five_is is not universe polymorphic\n", "")),
            ("two universe sentences", _ABOUT_OPAQUE.replace(
                "A.five_is is opaque", "A.five_is is universe polymorphic\nA.five_is is opaque")),
            ("a constant with no opacity", _ABOUT_OPAQUE.replace("A.five_is is opaque\n", "")),
            ("an inductive with an opacity", _ABOUT_INDUCTIVE.replace(
                "Expands", "A.color is transparent\nExpands"))):
        name = "A.color" if "inductive" in label else "A.five_is"
        _refused(lambda name=name, text=text: proofreading.parse_about(name, text),
                 f"About with {label} was placed")


def _fresh_universes_are_renamed_by_appearance() -> None:
    renamed = proofreading.fresh_universes(_CHECK_POLYMORPHIC, "VosReadingFacts_B")
    ensure(renamed == _CHECK_POLYMORPHIC.replace("VosReadingFacts_B.22", "?u1"),
           f"one fresh level is one name throughout its answer: {renamed!r}")
    two = proofreading.fresh_universes(
        "@M.c@{VosReadingFacts_M.40 VosReadingFacts_M.31} : Type@{VosReadingFacts_M.31}",
        "VosReadingFacts_M")
    ensure(two == "@M.c@{?u1 ?u2} : Type@{?u2}", f"levels are numbered by appearance: {two}")
    kept = "Type@{A.box.u0} Type@{Other.VosReadingFacts_M.3} Type@{VosReadingFacts_Mx.3}"
    ensure(proofreading.fresh_universes(kept, "VosReadingFacts_M") == kept,
           "a declared level, and a level of any other file, keeps its name")


def _entries_hold_a_body_exactly_where_one_belongs() -> None:
    opaque = proofreading.parse_about("A.five_is", _ABOUT_OPAQUE)
    projection = proofreading.parse_about("A.px", _ABOUT_PROJECTION)
    made = proofreading.entry("A.px\n     : forall _ : A.pt, nat", projection, "A.px = ...")
    ensure(made["print"] == "A.px = ..." and made["opacity"] == "transparent",
           f"a transparent constant carries its body: {made}")
    ensure(proofreading.entry("A.five_is", opaque, None)["print"] is None,
           "an opaque constant carries none")
    _refused(lambda: proofreading.entry("A.five_is", opaque, "A.five_is = ..."),
             "an opaque body entered the reading")
    _refused(lambda: proofreading.entry("A.px", projection, None),
             "a transparent constant went unprinted")


def _compare_names_every_difference() -> None:
    base = _reading({"M": {"M.a": _entry("M.a"), "M.b": _entry("M.b", None, opacity="opaque"),
                           "M.gone": _entry("M.gone")},
                     "Old": {"Old.x": _entry("Old.x")}})
    ensure(proofreading.compare(base, base) == [], "a reading equals itself")
    moved = json.loads(json.dumps(base))
    moved["provenance"]["objects"]["M.vo"] = "1" * 64
    ensure(proofreading.compare(base, moved) == [],
           "provenance names the compile and is never compared")
    changed = json.loads(json.dumps(base))
    constants = changed["modules"]["M"]["constants"]
    constants["M.a"]["print"] = "M.a = 1"
    constants["M.b"] = _entry("M.b", "= 0")
    del constants["M.gone"]
    constants["M.new"] = _entry("M.new")
    del changed["modules"]["Old"]
    changed["modules"]["New"] = {"constants": {}}
    changed["reader"]["prover"] = "The Rocq Prover, version 9.3.1"
    found = proofreading.compare(base, changed)
    named = [(difference.subject, difference.what) for difference in found]
    ensure(named == [("reader", "prover"), ("Old", "module removed"), ("New", "module added"),
                     ("M.gone", "removed"), ("M.new", "added"), ("M.a", "print"),
                     ("M.b", "opacity"), ("M.b", "about"), ("M.b", "print")],
           f"every difference, in a fixed order: {named}")
    detail = {(difference.subject, difference.what): difference.detail for difference in found}
    ensure(detail[("M.a", "print")] == "M.a = 0 -> M.a = 1"
           and detail[("M.b", "print")] == "not printed -> printed"
           and detail[("M.b", "opacity")] == "opaque -> transparent",
           f"each difference says what changed: {detail}")
    long_old = "\n".join(["same", "x" * 200])
    ensure(proofreading.compare(
        _reading({"M": {"M.a": _entry("M.a", long_old)}}),
        _reading({"M": {"M.a": _entry("M.a", long_old + "y")}}))[0].detail.startswith("line 2: "),
        "a long answer names the first line that differs")


def _schema_describes_and_refuses() -> None:
    schema = json.loads((TOOLS / "proof-reading.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    good = _reading({"M": {"M.a": _entry("M.a"), "M.b": _entry("M.b", None, opacity="opaque"),
                           "M.T": _entry("M.T", ": Set", kind="Inductive", opacity="n/a"),
                           "M.C": _entry("M.C", None, kind="Constructor", opacity="n/a")}})
    proofreading.validate(good)
    # Each mutation edits a decoded copy, which is JSON and so untyped here.
    refused: list[tuple[str, Callable[[Any], object]]] = [
        ("an opaque body", lambda r: r["modules"]["M"]["constants"]["M.b"].update(print="x")),
        ("an unprinted inductive",
         lambda r: r["modules"]["M"]["constants"]["M.T"].update(print=None)),
        ("an inductive's opacity",
         lambda r: r["modules"]["M"]["constants"]["M.T"].update(opacity="opaque")),
        ("a constant with no opacity",
         lambda r: r["modules"]["M"]["constants"]["M.a"].update(opacity="n/a")),
        ("an unqualified name",
         lambda r: r["modules"]["M"]["constants"].update(a=_entry("a"))),
        ("an unknown field", lambda r: r["reader"].update(extra="x")),
        ("a malformed digest", lambda r: r["provenance"]["objects"].update({"M.vo": "abc"})),
        ("another schema", lambda r: r.update(schema=2))]
    for label, mutate in refused:
        bad = json.loads(json.dumps(good))
        mutate(bad)
        _refused(lambda bad=bad: proofreading.validate(bad), f"the schema accepted {label}")


def _compare_command_exits_on_the_verdict() -> None:
    base = _reading({"M": {"M.a": _entry("M.a")}})
    other = _reading({"M": {"M.a": _entry("M.a", "= 1")}})
    with tempfile.TemporaryDirectory(prefix="vos-reading-") as temporary:
        folder = Path(temporary)
        paths: dict[str, Path] = {}
        for label, value in (("base", base), ("other", other)):
            paths[label] = folder / f"{label}.json"
            receipts.write(paths[label], value)
        (folder / "repeated.json").write_text('{"format": 1, "format": 2}', encoding="utf-8")
        (folder / "list.json").write_text("[]", encoding="utf-8")

        def run(*argv: str) -> tuple[int, str]:
            with contextlib.redirect_stdout(io.StringIO()) as said:
                code = cli.main(list(argv))
            return code, said.getvalue()

        code, said = run("compare", str(paths["base"]), str(paths["base"]))
        ensure(code == 0 and said.startswith("ok proof-reading:"), f"equal readings: {said}")
        code, said = run("compare", str(paths["base"]), str(paths["other"]))
        ensure(code == 1 and "  M.a: print: M.a = 0 -> M.a = 1" in said,
               f"a difference is named and exits 1: {said}")
        for broken in ("repeated.json", "list.json", "absent.json"):
            code, said = run("compare", str(paths["base"]), str(folder / broken))
            ensure(code == 1 and said.startswith("FAIL proof-reading:"),
                   f"{broken} was compared rather than refused: {said}")


def _read_answered(answers: dict[str, str],
                   ) -> tuple[dict[str, proofreading.Entry], dict[str, str]]:
    """Module A read from scripted answers, and the query text each process was given."""
    asked: dict[str, str] = {}

    def query(_objects: Path, _scratch: Path, name: str, text: str, _bound: int) -> str:
        asked[name] = text
        return answers[name]

    with patch.object(cli, "_query", side_effect=query):
        return cli.read_module(Path("objects"), Path("scratch"), "A"), asked


def _module_reading_asks_bodies_only_where_they_belong() -> None:
    marker = proofreading.MARKER
    about = ("A.{0} : nat\n\nA.{0} is not universe polymorphic\nA.{0} is {1}\n"
             "Expands to: Constant A.{0}\nDeclared in library A, line 1, characters 0-1")
    read, asked = _read_answered({
        "VosReadingInventory_A": f"{proofaudit.EMPTY_BLACKLIST}\nA.t: nat\nA.o: nat\n",
        "VosReadingFacts_A": "".join(
            f"{marker}A.{name}|check\nA.{name}\n     : nat\n{marker}A.{name}|about\n"
            + about.format(name, opacity) + "\n"
            for name, opacity in (("o", "opaque"), ("t", "transparent"))),
        "VosReadingBodies_A": f"{marker}A.t|print\nA.t = O\n     : nat\n"})
    ensure(asked["VosReadingInventory_A"] == proofaudit.inventory_query("A"),
           "the inventory is the audit's own query")
    ensure("Print A.t." in asked["VosReadingBodies_A"]
           and "A.o" not in asked["VosReadingBodies_A"], "only the transparent body is asked")
    ensure(read["A.o"]["print"] is None and read["A.t"]["print"] == "A.t = O\n     : nat",
           f"the entries: {read}")
    ensure("Declared in" not in read["A.o"]["about"], "locations never enter the reading")


def _module_reading_renames_its_own_levels() -> None:
    """A polymorphic constant reads the same however many were asked before it.

    Rocq names a level a query instantiates after the query file and a counter over
    its whole process, and Check is where the pinned prover does so. A level so named
    is renamed in every answer, About and Print included; a declared level is not.
    """
    marker = proofreading.MARKER

    def read(counter: int) -> proofreading.Entry:
        fresh, printed = f"VosReadingFacts_A.{counter}", f"VosReadingBodies_A.{counter + 7}"
        about = _ABOUT_POLYMORPHIC.replace("(* u |  *)", f"(* u | u <= {fresh} *)")
        answered, _ = _read_answered({
            "VosReadingInventory_A": f"{proofaudit.EMPTY_BLACKLIST}\n"
                                     "A.pid: forall (A : Type) (_ : A), A\n",
            "VosReadingFacts_A": (
                f"{marker}A.pid|check\nA.pid@{{{fresh}}}\n"
                f"     : forall (A : Type@{{{fresh}}}) (_ : A), A\n(* {{{fresh}}} |  *)\n"
                f"{marker}A.pid|about\n{about}\n"),
            "VosReadingBodies_A": (
                f"{marker}A.pid|print\nA.pid@{{u}} = fun (A : Type@{{u}}) (a : A) => a\n"
                f"     : forall (A : Type@{{u}}) (_ : A), A\n(* u | u <= {printed} *)\n")})
        return answered["A.pid"]

    first = read(21)
    ensure(first == read(34), "one constant's reading depends on its query's counter")
    for field in ("check", "about", "print"):
        text = first[field] or ""
        ensure("?u1" in text and "VosReading" not in text,
               f"{field} keeps a level its query named: {text!r}")
    ensure("A.pid@{u}" in first["about"] and "Type@{u}" in (first["print"] or ""),
           f"a declared level keeps its name: {first}")


def _default_objects_need_a_passing_receipt() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-reading-gate-") as temporary:
        work = Path(temporary)
        objects = work / proofs_cli.PROOFS
        objects.mkdir()
        (objects / "A.v").write_text("Definition a := 0.\n", encoding="utf-8")
        (objects / "A.vo").write_bytes(b"compiled")
        receipt = {"status": "passed", "kernel_recheck": "passed",
                   "inputs": {**receipts.snapshot(work, [objects / "A.v"]),
                              "tools/vos/cli/proofs.py": _SHA},
                   "outputs": receipts.snapshot(work, [objects / "A.vo"])}
        with patch.object(proofs_cli, "workspace", return_value=work):
            receipts.write(work / proofs_cli.RECEIPT, receipt)
            ensure(cli.gate_objects(Path("root")) == (objects, cli._snapshot(objects)),
                   "a passing compile is read, bound to the staged files the receipt names")
            for label, change in (
                    ("a failed run", {"status": "failed"}),
                    ("a failed kernel recheck", {"kernel_recheck": "failed"}),
                    ("a receipt with no outputs", {"outputs": None}),
                    ("a receipt with no staged source", {"inputs": {}, "outputs": {}})):
                receipts.write(work / proofs_cli.RECEIPT, {**receipt, **change})
                _refused(lambda: cli.gate_objects(Path("root")), f"{label} was read")
            receipts.write(work / proofs_cli.RECEIPT, [receipt])
            _refused(lambda: cli.gate_objects(Path("root")), "a receipt that is no object")
            (work / proofs_cli.RECEIPT).unlink()
            _refused(lambda: cli.gate_objects(Path("root")), "a lane with no receipt was read")


def _modules_need_their_objects() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-reading-modules-") as temporary:
        objects = Path(temporary)
        for stem in ("A", "B"):
            (objects / f"{stem}.v").write_text("", encoding="utf-8")
            (objects / f"{stem}.vo").write_bytes(b"")
        ensure(cli.modules_in(objects) == ["A", "B"], "every source in the directory")
        ensure(cli.modules_in(objects, ["B", "B"]) == ["B"], "or the ones named")
        _refused(lambda: cli.modules_in(objects, ["C"]), "a module with no source was read")
        (objects / "B.vo").unlink()
        _refused(lambda: cli.modules_in(objects), "a source with no object was read")
        _refused(lambda: cli.modules_in(objects / "empty"), "an empty directory was read")


def _prover_stub() -> tuple[str, str]:
    return "The Rocq Prover, version 9.3.0", _SHA


def _lane_scratch(_root: Path, prefix: str) -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix=f"vos-reading-{prefix}")


def _record_reads_only_the_compile_that_passed() -> None:
    """A directory is read only while it holds the bytes its compile was recorded with."""
    def read(_objects: Path, _scratch: Path, module: str, _bound: int) -> dict[str, Any]:
        return {f"{module}.a": _entry(f"{module}.a")}

    with (tempfile.TemporaryDirectory(prefix="vos-reading-record-") as temporary,
          patch.object(cli, "_prover", side_effect=_prover_stub),
          patch.object(cli, "_scratch", side_effect=_lane_scratch),
          patch.object(cli, "read_module", side_effect=read),
          contextlib.redirect_stdout(io.StringIO())):
        objects = Path(temporary)
        (objects / "A.v").write_text("Definition a := 0.\n", encoding="utf-8")
        (objects / "A.vo").write_bytes(b"compiled")
        passed = cli._snapshot(objects)
        reading = cli.record(Path("root"), objects, passed, None, 1)
        ensure(reading["provenance"] == {"sources": {"A.v": passed["A.v"]},
                                         "objects": {"A.vo": passed["A.vo"]}},
               f"the provenance is the compile's own digests: {reading['provenance']}")
        for label, digests in (
                ("a stale object", {**passed, "A.vo": _SHA}),
                ("a changed source", {**passed, "A.v": _SHA}),
                ("a file the compile did not make", {"A.v": passed["A.v"]})):
            _refused(lambda digests=digests: cli.record(Path("root"), objects, digests, None, 1),
                     f"{label} was read")


def _a_reading_that_moves_writes_nothing() -> None:
    """A source or an object rewritten while it is read refuses the reading unwritten."""
    with (tempfile.TemporaryDirectory(prefix="vos-reading-moved-") as temporary,
          patch.object(cli, "_prover", side_effect=_prover_stub),
          patch.object(cli, "_scratch", side_effect=_lane_scratch)):
        folder = Path(temporary)
        objects = folder / proofs_cli.PROOFS
        objects.mkdir()
        (objects / "A.v").write_text("Definition a := 0.\n", encoding="utf-8")
        (objects / "A.vo").write_bytes(b"compiled")
        passed = cli._snapshot(objects)

        def run(moved: str | None) -> tuple[int, str, Path]:
            """The default route over the directory, with `moved` rewritten mid-read."""
            def read(_objects: Path, _scratch: Path, module: str, _bound: int,
                     ) -> dict[str, Any]:
                if moved:
                    (objects / moved).write_bytes(b"rewritten")
                return {f"{module}.a": _entry(f"{module}.a")}

            target = folder / f"{moved or 'unmoved'}.json"
            with (patch.object(cli, "gate_objects", return_value=(objects, passed)),
                  patch.object(cli, "read_module", side_effect=read),
                  contextlib.redirect_stdout(io.StringIO()) as said):
                code = cli.main(["record", "--out", str(target), "--jobs", "1"])
            return code, said.getvalue(), target

        code, said, target = run(None)
        ensure(code == 0 and target.is_file(), f"an unmoved compile is read and written: {said}")
        for moved in ("A.v", "A.vo"):
            original = (objects / moved).read_bytes()
            code, said, target = run(moved)
            ensure(code == 1 and "changed while they were read" in said and not target.exists(),
                   f"{moved} rewritten mid-read was written: {code} {said}")
            (objects / moved).write_bytes(original)


def _stream_prover(code: int, stderr: bytes, answer: bytes,
                   ) -> Callable[..., subprocess.CompletedProcess[bytes]]:
    """A query process that writes `answer` to its output file, as `_query` directs it."""
    def run(command: list[str], *, stdout: IO[bytes], **_: object,
            ) -> subprocess.CompletedProcess[bytes]:
        stdout.write(answer)
        return subprocess.CompletedProcess(command, code, None, stderr)
    return run


def _query_reads_only_a_clean_bounded_answer() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-reading-query-") as temporary:
        scratch = Path(temporary)

        def ask(code: int, stderr: bytes, answer: bytes) -> str:
            with (patch.object(env, "rocq_command", return_value=["rocq", "c"]),
                  patch.object(cli.subprocess, "run",
                               side_effect=_stream_prover(code, stderr, answer))):
                return cli._query(Path("objects"), scratch, "VosReadingFacts_M", "Check 0.\n", 16)

        ensure(ask(0, b"", b"0\n     : nat\n") == "0\n     : nat\n", "a clean answer is read")
        ensure(ask(0, b"", b"x" * 16) == "x" * 16, "an answer at the bound is read")
        for label, code, stderr, answer in (
                ("a diagnostic", 0, b"Warning: a deprecated notation", b"0\n     : nat\n"),
                ("a failed query", 1, b"", b""),
                ("an answer past the bound", 0, b"", b"x" * 17)):
            _refused(lambda code=code, stderr=stderr, answer=answer: ask(code, stderr, answer),
                     f"{label} was read")
        ensure([path.name for path in scratch.iterdir()] == ["VosReadingFacts_M.v"],
               "the answer file outlived its query")


def _fake_compiler(commands: list[list[str]], said: dict[str, tuple[int, str]],
                   ) -> Callable[..., subprocess.CompletedProcess[str]]:
    """A prover that writes each object it is asked for, or answers as `said` scripts."""
    def run(command: list[str], *, cwd: Path, **_: object) -> subprocess.CompletedProcess[str]:
        name = command[-1]
        commands.append(command)
        code, text = said.get(name, (0, ""))
        if not code:
            (Path(cwd) / name).with_suffix(".vo").write_text(f"compiled {name}", encoding="utf-8")
        return subprocess.CompletedProcess(command, code, "", text)
    return run


def _sources_compile_as_the_gate_compiles() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-reading-sources-") as temporary:
        folder = Path(temporary)

        def attempt(sources: dict[str, str], said: dict[str, tuple[int, str]] | None = None,
                    ) -> tuple[list[str], list[str], dict[str, str] | str]:
            """The sources compiled, the first command, and the digests or the refusal."""
            for old in folder.iterdir():
                shutil.rmtree(old)
            given, objects = folder / "given", folder / "objects"
            given.mkdir()
            objects.mkdir()
            for name, text in sources.items():
                (given / name).write_text(text, encoding="utf-8")
            # A stale object beside the sources, which the compile must never carry over.
            (given / "B.vo").write_text("stale", encoding="utf-8")
            commands: list[list[str]] = []
            with (patch.object(env, "rocq_command", return_value=["rocq", "c"]),
                  patch.object(cli.subprocess, "run",
                               side_effect=_fake_compiler(commands, said or {}))):
                try:
                    result: dict[str, str] | str = cli.compile_sources(given, objects, 2)
                except proofreading.ReadingError as error:
                    result = str(error)
            return ([command[-1] for command in commands], commands[0] if commands else [],
                    result)

        sources = {"B.v": "Require Import A.\nDefinition b := a.\n",
                   "A.v": "Definition a := 0.\n"}
        compiled, command, result = attempt(sources)
        ensure(compiled == ["A.v", "B.v"], f"the gate's dependency order: {compiled}")
        ensure(command[2:] == ["-q", "-Q", str(folder / "objects"), "", *proofs_cli.STRICT,
                               "A.v"], f"the gate's flags over the copies: {command}")
        ensure(isinstance(result, dict) and sorted(result) == ["A.v", "A.vo", "B.v", "B.vo"]
               and (folder / "objects" / "B.vo").read_text(encoding="utf-8")
               == "compiled B.v", f"the copies and the objects compiled from them: {result}")
        for label, changed, said in (
                ("a pinned setting reset", {"A.v": 'Set Warnings "-all".\n'}, None),
                ("a module type", {"A.v": "Module Type T.\nEnd T.\n"}, None),
                ("a Require cycle", {"A.v": "Require Import B.\n"}, None),
                ("a diagnostic", {}, {"A.v": (0, "Warning: something")}),
                ("a failed compile", {}, {"A.v": (1, "")})):
            compiled, _, result = attempt({**sources, **changed}, said)
            ensure(isinstance(result, str) and "B.v" not in compiled
                   and not (folder / "objects" / "B.vo").exists(),
                   f"{label} was compiled past: {compiled} {result}")
        _, _, result = attempt({})
        ensure(isinstance(result, str), "a directory with no source was compiled")


# The native controls' fixture: a base module the leaf Requires, and a leaf whose
# declarations the controls edit one at a time. The comment is one the comment control
# edits, which also moves every later declaration's location.
_BASE = """\
Record pt : Set := mkpt { px : nat; py : nat }.
Definition origin : pt := {| px := 0; py := 0 |}.
Lemma origin_px : px origin = 0.
Proof. reflexivity. Qed.
"""

_LEAF = """\
Require Import Base.

(* A leaf module whose declarations the controls edit one at a time. *)
Definition conv : nat := 2 + 2.
Definition nconv : nat := 3.
Lemma stmt : forall n : nat, n + 0 = n.
Proof. intros n. induction n as [|n IH]. - reflexivity. - simpl. rewrite IH. reflexivity. Qed.
Definition dq : True.
Proof. exact I. Defined.
Lemma removable : True.
Proof. exact I. Qed.
Definition upoly (A : Type) (a : A) : A := a.
Inductive sw : Set := First | Second.
Lemma opaque_script : 2 + 2 = 4.
Proof. reflexivity. Qed.
Definition ifis (x : option nat) : nat := match x with Some n => n | None => 0 end.
Definition upd (r : pt) : pt := {| px := 3; py := py r |}.
Definition amp (n : nat) (_ : n = 0) : nat := n.
#[universes(polymorphic)] Definition zpoly (A B : Type) (a : A) (_ : B) : A := a.
"""

_SCHEMES = ("Leaf.sw_ind", "Leaf.sw_rec", "Leaf.sw_rect")

# Each control: the leaf text it replaces, its replacement, and exactly the differences
# the comparison must name. An empty set is a control that must change nothing.
_CONTROLS: tuple[tuple[str, str, str, set[tuple[str, str]]], ...] = (
    ("changed-statement",
     "Lemma stmt : forall n : nat, n + 0 = n.\nProof. intros n. induction n as [|n IH]. "
     "- reflexivity. - simpl. rewrite IH. reflexivity. Qed.",
     "Lemma stmt : forall n : nat, 0 + n = n.\nProof. intros n. reflexivity. Qed.",
     {("Leaf.stmt", "check"), ("Leaf.stmt", "about")}),
    ("convertible-body", "Definition conv : nat := 2 + 2.", "Definition conv : nat := 4.",
     {("Leaf.conv", "print")}),
    ("different-body", "Definition nconv : nat := 3.", "Definition nconv : nat := 7.",
     {("Leaf.nconv", "print")}),
    ("defined-to-qed", "Proof. exact I. Defined.", "Proof. exact I. Qed.",
     {("Leaf.dq", "opacity"), ("Leaf.dq", "about"), ("Leaf.dq", "print")}),
    ("removed-symbol", "Lemma removable : True.\nProof. exact I. Qed.\n", "",
     {("Leaf.removable", "removed")}),
    ("universe-polymorphic", "Definition upoly", "#[universes(polymorphic)] Definition upoly",
     {("Leaf.upoly", what) for what in ("universes", "check", "about", "print")}),
    # A polymorphic constant asked before `zpoly` moves the counter Rocq names the levels
    # of zpoly's Check after, which the reading must not see.
    ("polymorphic-added-first", "Definition conv : nat := 2 + 2.",
     "#[universes(polymorphic)] Definition apoly (A : Type) (a : A) : A := a.\n"
     "Definition conv : nat := 2 + 2.", {("Leaf.apoly", "added")}),
    ("swapped-constructors", "First | Second", "Second | First",
     {("Leaf.sw", "print"), *((scheme, what) for scheme in _SCHEMES
                              for what in ("check", "about", "print"))}),
    ("comment-edit",
     "(* A leaf module whose declarations the controls edit one at a time. *)",
     "(* A leaf module whose declarations\n   the controls edit, one at a time. *)\n(* added *)",
     set()),
    ("opaque-script", "Lemma opaque_script : 2 + 2 = 4.\nProof. reflexivity. Qed.",
     "Lemma opaque_script : 2 + 2 = 4.\n"
     "Proof. exact (f_equal (fun k : nat => k) (eq_refl 4)). Qed.", set()),
    ("if-is", "match x with Some n => n | None => 0 end", "if x is Some n then n else 0",
     set()),
    ("record-with", "{| px := 3; py := py r |}", "{| r with px := 3 |}", set()),
    ("anonymous-binder", "(n : nat) (_ : n = 0)", "(n : nat) & n = 0", set()),
)


def _compile(folder: Path, name: str) -> None:
    done = subprocess.run([*env.rocq_command(), "-q", "-Q", str(folder), "",
                           *proofs_cli.STRICT, name],
                          cwd=folder, capture_output=True, text=True, encoding="utf-8",
                          check=False)
    ensure(done.returncode == 0 and not (done.stdout + done.stderr).strip(),
           f"{folder.name}/{name} did not compile cleanly under the gate's flags: "
           f"{done.returncode} {done.stdout}{done.stderr}")


def _native_controls() -> None:
    """The pinned prover over the fixture, each control against the base reading.

    The whole fixture is read twice through the command, which compiles its sources
    each time and must write the same bytes both times. Each control then changes the
    leaf's source and reads the leaf alone, two controls at a time, which is the guest's
    budget of prover processes. The base fixture's own objects lie beside every changed
    source, newer than it, which is the directory a reading of objects rather than of
    sources would take the base's meaning from.
    """
    root = Path(__file__).resolve().parents[2]
    with cli._scratch(root, "native-test-") as temporary:
        work = Path(temporary)
        base = work / "base"
        base.mkdir()
        (base / "Base.v").write_text(_BASE, encoding="utf-8")
        (base / "Leaf.v").write_text(_LEAF, encoding="utf-8")
        readings = [work / "first.json", work / "second.json"]
        for target in readings:
            with contextlib.redirect_stdout(io.StringIO()) as said:
                code = cli.main(["record", "--sources", str(base), "--out", str(target),
                                 "--jobs", "2"])
            ensure(code == 0, f"the base reading was refused: {said.getvalue()}")
        _compile(base, "Base.v")
        _compile(base, "Leaf.v")
        ensure(readings[0].read_bytes() == readings[1].read_bytes(),
               "two readings of one compile differ")
        with contextlib.redirect_stdout(io.StringIO()) as said:
            code = cli.main(["compare", str(readings[0]), str(readings[1])])
        ensure(code == 0, f"the command refused two equal readings: {said.getvalue()}")
        whole = proofreading.load(readings[0])
        constants = whole["modules"]["Leaf"]["constants"]
        ensure(set(whole["modules"]) == {"Base", "Leaf"} and "Leaf.sw" in constants
               and constants["Leaf.zpoly"]["universes"] == "polymorphic"
               and "?u1" in constants["Leaf.zpoly"]["check"],
               f"the fixture's modules and constants: {sorted(whole['modules'])}")
        leaf: proofreading.Reading = {**whole, "modules": {"Leaf": whole["modules"]["Leaf"]}}

        def control(label: str, old: str, new: str, expected: set[tuple[str, str]]) -> str:
            text = _LEAF.replace(old, new)
            if text == _LEAF:
                return f"{label}: the control no longer applies to the fixture"
            variant = work / label
            variant.mkdir()
            shutil.copyfile(base / "Base.v", variant / "Base.v")
            (variant / "Leaf.v").write_text(text, encoding="utf-8")
            for name in ("Base.vo", "Leaf.vo"):
                shutil.copyfile(base / name, variant / name)
            candidate = cli.record_sources(root, variant, ["Leaf"], 1)
            found = {(difference.subject, difference.what)
                     for difference in proofreading.compare(leaf, candidate)}
            return "" if found == expected else (
                f"{label}: named {sorted(found)}, expected {sorted(expected)}")

        with contextlib.redirect_stdout(io.StringIO()), ThreadPoolExecutor(2) as pool:
            failures = [failure for failure in pool.map(lambda args: control(*args), _CONTROLS)
                        if failure]
        ensure(not failures, "; ".join(failures))


def cases() -> list[Case]:
    return [
        Case("queries-frame-every-answer", _queries_frame_every_answer),
        Case("answers-refuse-what-was-not-asked", _answers_refuse_what_was_not_asked),
        Case("about-keeps-every-fact-but-locations", _about_keeps_every_fact_but_locations),
        Case("fresh-universes-renamed-by-appearance", _fresh_universes_are_renamed_by_appearance),
        Case("entries-hold-a-body-where-one-belongs",
             _entries_hold_a_body_exactly_where_one_belongs),
        Case("compare-names-every-difference", _compare_names_every_difference),
        Case("schema-describes-and-refuses", _schema_describes_and_refuses),
        Case("compare-command-exits-on-the-verdict", _compare_command_exits_on_the_verdict),
        Case("module-reading-asks-bodies-where-they-belong",
             _module_reading_asks_bodies_only_where_they_belong),
        Case("module-reading-renames-its-own-levels", _module_reading_renames_its_own_levels),
        Case("default-objects-need-a-passing-receipt", _default_objects_need_a_passing_receipt),
        Case("modules-need-their-objects", _modules_need_their_objects),
        Case("record-reads-only-the-compile-that-passed",
             _record_reads_only_the_compile_that_passed),
        Case("a-reading-that-moves-writes-nothing", _a_reading_that_moves_writes_nothing),
        Case("query-reads-only-a-clean-bounded-answer", _query_reads_only_a_clean_bounded_answer),
        Case("sources-compile-as-the-gate-compiles", _sources_compile_as_the_gate_compiles),
        Case("native-reading-controls", _native_controls, lane="toolchain"),
    ]
