# SPDX-License-Identifier: Apache-2.0
"""The apex record parse, held at the shapes it must not answer short.

`vos/apex.py` is the one reading of proofs/ApexTheorem.v, and both its callers refuse
on its residue rather than narrowing, so what has to be pinned is not the answer on a
well-formed statement but the boundary: every shape this parse cannot read has to
arrive in `unread`, because a field it never named has no row to disagree with it and
a consumer it never saw leaves a cell that was already written without it. Neither
narrowing moves a count off zero, so no floor sees either.

The cases are the four shapes that were silent, one each: a `Definition` indented
inside a `Module`, which the column-anchored pattern cannot match; a record built from
another record by application, where the field is assigned and consumed in one line; a
seam written `f v` rather than `v.(f)`; and the record absent altogether. The fifth
case is the other direction and is why the discount is positional: a record update
written `f := v.(f)` genuinely consumes the field, and refusing it would be this parse
inventing a residue rather than reporting one.
"""

import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import apex

# Small enough to derive by hand: five declarations, three of them Prop, `witness`
# consuming alpha and beta through its type, and two definitions consuming the rest.
_APEX = """\
(* a fixture apex statement (* with a nested comment *) *)
Record Vocabulary : Type := {
  Carrier : Type;
  alpha : Prop;
  beta : Prop;
  gamma : Prop;
  witness : alpha -> beta
}.

Definition uses_alpha (v : Vocabulary) : Prop := v.(alpha).
Definition seam_one (v : Vocabulary) : Prop := v.(beta) -> v.(gamma).
"""


def _read(text: str) -> apex.ApexRecord:
    with tempfile.TemporaryDirectory() as held:
        path = Path(held) / "ApexTheorem.v"
        path.write_text(text, encoding="utf-8")
        return apex.read(path)


def _reads_the_record_whole() -> None:
    rec = _read(_APEX)
    ensure(rec.unread == [], f"a readable statement leaves no residue: {rec.unread!r}")
    ensure(rec.fields == ["alpha", "beta", "gamma"],
           f"the Prop fields in declaration order read back as {rec.fields!r}")
    ensure(rec.declarations == 5,
           f"every declaration is counted, Type fields and coercions too, got "
           f"{rec.declarations}")
    ensure(rec.consumers == {"alpha": ["witness", "uses_alpha"],
                             "beta": ["witness", "seam_one"],
                             "gamma": ["seam_one"]},
           f"the consumers map read back as {rec.consumers!r}")
    ensure(rec.def_fields == {"uses_alpha": ["alpha"], "seam_one": ["beta", "gamma"]},
           f"the fields each definition reads came back as {rec.def_fields!r}")


def _indented_definition_is_a_residue() -> None:
    # A definition inside a `Module` or a `Section` is indented, and the pattern that
    # reads definitions anchors at column 0. The count that audits it therefore admits
    # indentation: anchored where the audited pattern is anchored it would have been
    # that pattern restating its own answer, green over a consumer nobody saw.
    rec = _read(_APEX + "\nModule Extra.\n"
                        "  Definition inner (v : Vocabulary) : Prop := v.(alpha).\n"
                        "End Extra.\n")
    ensure(any("spells 3 `Definition` sentences and this parse reads 2" in said
               for said in rec.unread),
           f"an indented definition is a residue, got {rec.unread!r}")
    ensure(rec.consumers["alpha"] == ["witness", "uses_alpha"],
           f"and the consumer it would have added is not silently in the map: "
           f"{rec.consumers['alpha']!r}")


def _record_update_by_application_is_a_residue() -> None:
    # `f := f v` assigns the field and consumes it in one line. What the second reading
    # discounts is the assigned occurrence and never the name, or this body would read
    # as consuming nothing and agree with the first reading over a loss.
    rec = _read(_APEX + "\nDefinition harden (v : Vocabulary) : Vocabulary := {|\n"
                        "  alpha := alpha v\n"
                        "|}.\n")
    ensure(any("'harden' reads no field through the record value and names alpha" in said
               for said in rec.unread),
           f"a field both assigned and applied is a residue, got {rec.unread!r}")
    ensure("harden" not in rec.def_fields,
           "and the parse states neither reading rather than the shorter one")


def _record_update_by_projection_is_read() -> None:
    # The same shape written with the abbreviation is unambiguous and must not be
    # refused: a parse that invented a residue here would be as wrong as one that
    # narrowed, and the two record constructions the live statement carries name every
    # field in assignment position while consuming none, which stays clean.
    rec = _read(_APEX + "\nDefinition tighten (v : Vocabulary) : Vocabulary := {|\n"
                        "  alpha := v.(alpha)\n"
                        "|}.\n")
    ensure(rec.unread == [], f"an assigned field that is also projected is read, not "
                            f"refused: {rec.unread!r}")
    ensure(rec.def_fields.get("tighten") == ["alpha"]
           and rec.consumers["alpha"] == ["witness", "uses_alpha", "tighten"],
           f"and it is counted as the consumer it is: {rec.consumers['alpha']!r}")


def _projection_free_seam_is_a_residue() -> None:
    # `v.(f)` abbreviates the projection `f` applied to `v`, so `f v` consumes the
    # field in Gallina and in no scan for the abbreviation.
    rec = _read(_APEX + "\nDefinition seam_two (v : Vocabulary) : Prop :=\n"
                        "  alpha v -> gamma v.\n")
    ensure(any("'seam_two' reads no field through the record value and names "
               "alpha, gamma" in said for said in rec.unread),
           f"a seam written without the abbreviation is a residue, got {rec.unread!r}")


def _grouped_declaration_is_a_residue() -> None:
    # `a b : Prop` declares two fields and is legal Gallina; read as one it would name
    # neither, so the piece is handed back whole.
    rec = _read(_APEX.replace("  gamma : Prop;", "  gamma delta : Prop;"))
    ensure(any("'gamma delta : Prop' is in no `name : type` form" in said
               for said in rec.unread),
           f"a grouped declaration is a residue, got {rec.unread!r}")
    ensure("gamma" not in rec.field_set and "delta" not in rec.field_set,
           "and neither name is guessed out of it")


def _brace_inside_the_body_does_not_truncate() -> None:
    # The body is brace-matched rather than cut at the first `}`, so a field at a type
    # that carries one is read past instead of ending the record early.
    rec = _read(_APEX.replace("  Carrier : Type;",
                              "  Carrier : Type;\n  bound : { n : nat | n = n };"))
    ensure(rec.unread == [] and rec.declarations == 6
           and rec.fields == ["alpha", "beta", "gamma"],
           f"a braced type is one more declaration and truncates nothing: "
           f"{rec.declarations} declarations, {rec.fields!r}, {rec.unread!r}")


def _missing_record_is_a_residue() -> None:
    # The floor: the subject absent entirely is a worded finding, not an empty field
    # list that every pairing then passes over.
    rec = _read("Definition uses_alpha (v : Vocabulary) : Prop := v.(alpha).\n")
    ensure(rec.fields == [] and any("no `Record Vocabulary" in said
                                    for said in rec.unread),
           f"a statement with no record is refused by name, got {rec.unread!r}")


def cases() -> list[Case]:
    return [
        Case("reads-the-record-whole", _reads_the_record_whole),
        Case("indented-definition-is-a-residue", _indented_definition_is_a_residue),
        Case("record-update-by-application-is-a-residue",
             _record_update_by_application_is_a_residue),
        Case("record-update-by-projection-is-read", _record_update_by_projection_is_read),
        Case("projection-free-seam-is-a-residue", _projection_free_seam_is_a_residue),
        Case("grouped-declaration-is-a-residue", _grouped_declaration_is_a_residue),
        Case("brace-inside-the-body-does-not-truncate",
             _brace_inside_the_body_does_not_truncate),
        Case("missing-record-is-a-residue", _missing_record_is_a_residue),
    ]
