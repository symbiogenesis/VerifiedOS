# SPDX-License-Identifier: Apache-2.0
"""K-107's Gallina reading, held at where a statement starts and where it stops.

`vos/checks/consttab.py` reads a published table out of a named Gallina statement and
compares it with the model's, and a size check stands behind every row. That check is
loud about a table that grew or shrank, and silent about one whose extra numerals
happen not to arrive: what has to be pinned here is that the reading takes the
statement, the whole statement and nothing but the statement.

Five boundaries, one case each. A statement under an attribute or a locality is the
statement and is read; one under `Fail` or `Succeed`, on its line or above it past blank
lines and comments, states nothing the file keeps and is refused by name, while one
after `Fail }` or `Succeed {` is read, the flag being the brace's; and one a comment
quotes is no statement at all. And a statement stops at its own full stop, so the
`Proof using` line, the decorated declaration or the comment around its table adds no
value to it, where the list of next constructs this replaces read the first two as more
table.
"""

from tests.harness import Case, ensure
from vos.checks import consttab

_TABLE = "Definition table : list nat := 3 :: 5 :: 7 :: nil.\n"


def _pair(gread: str) -> consttab.Pair:
    """One row over a fixture: a three-value table, stated as a `Definition`'s list or
    as the right of an `Example`'s equation."""
    return {"what": "a fixture table", "gallina": "proofs/Fixture.v", "name": "table",
            "gread": gread, "sail": "model/fixture.sail", "sites": ("fixture",),
            "sread": "vector", "size": 3}


def _values(text: str, gread: str = "definition") -> tuple[list[int] | None, str]:
    return consttab._gallina("(* a fixture *)\n" + text, _pair(gread))


def _a_decorated_statement_is_read() -> None:
    for decoration in ("#[local] ", "#[local]\n", "Local ", "Global ", "Program ",
                       "Time ", '#[deprecated(note="a ] b")]\nLocal '):
        got, why = _values(decoration + _TABLE)
        ensure(got == [3, 5, 7] and not why,
               f"under {decoration!r} the table read {got} ({why})")
    got, why = _values("#[local] Example table : map id l = 3 :: 5 :: 7 :: nil.\n"
                       "Proof. reflexivity. Qed.\n", "example")
    ensure(got == [3, 5, 7], f"a decorated Example read {got} ({why})")
    # the shared lexer's grammar, spelled as Rocq's lexer reads it: no blank after a word
    # or a string, a doubled quote in a quoted target, and a bullet inside a proof
    for decoration in ("Time#[local]", 'Profile"p"', 'Redirect "a""b" ', "Timeout 5Local ",
                       "Lemma l : True.\nProof.\n- "):
        got, why = _values(decoration + _TABLE)
        ensure(got == [3, 5, 7] and not why,
               f"under {decoration!r} the table read {got} ({why})")


def _a_void_statement_is_refused() -> None:
    # on the statement's line or above it, however many blank lines, comments or
    # attributes stand between the flag and the keyword
    for lead, flag in (("Fail ", "Fail"), ("Succeed ", "Succeed"),
                       ("#[local] Fail ", "Fail"), ("Fail\n", "Fail"),
                       ("Fail\n\n", "Fail"), ("Fail (* why. *)\n", "Fail"),
                       ("Fail\n(* a note\n   spanning lines *)\n", "Fail"),
                       ('Succeed\n#[deprecated(note="a. b")]\n', "Succeed"),
                       ("Succeed#[local]", "Succeed"), ("Succeed#[local]\n", "Succeed"),
                       ('Redirect "a""b" Fail\n', "Fail"), ('Profile"p"Fail ', "Fail")):
        got, why = _values(lead + _TABLE)
        ensure(got is None and f"under `{flag}`" in why,
               f"a table under {lead!r} was read as {got} ({why})")
    got, why = _values("  " + _TABLE)
    ensure(got is None and "states no Definition named table" in why,
           f"an indented statement opens no statement here: {got} ({why})")
    # a flag that ends the sentence before is no flag of this one
    got, why = _values("Check Fail.\n" + _TABLE)
    ensure(got == [3, 5, 7], f"a word of the sentence before voided the table: {got} ({why})")


def _a_flag_before_a_brace_is_the_braces() -> None:
    # A bullet, a brace or a goal selector is a command of its own, and the locked
    # compiler runs `Fail }` and `Succeed {` as the brace's flag and keeps the statement
    # after it, on the brace's line or below it, so that statement is read.
    proof = "Lemma l : True.\nProof.\n"
    for lead in ("Fail }\n", "Fail } ", "Succeed { ", "Succeed 1: {\n", "Fail\n} "):
        got, why = _values(proof + lead + _TABLE)
        ensure(got == [3, 5, 7] and not why, f"after {lead!r} the table read {got} ({why})")
    # the control: a flag after a bullet, on its line or below it, is the statement's
    for lead in ("- Succeed ", "{ Succeed\n"):
        got, why = _values(proof + lead + _TABLE)
        ensure(got is None and "under `Succeed`" in why,
               f"a table after {lead!r} was read as {got} ({why})")


def _a_statement_inside_a_comment_is_none() -> None:
    # a statement a comment quotes at column zero is prose, and the table is the one
    # the file states
    got, why = _values("(* the table once read:\n"
                       "Definition table : list nat := 9 :: 9 :: 9 :: nil.\n"
                       "*)\n" + _TABLE)
    ensure(got == [3, 5, 7], f"the table a comment quotes was read: {got} ({why})")


def _a_statement_stops_at_its_own_full_stop() -> None:
    followers = (
        "Proof using. exact (f 11). Qed.\n",
        "#[local] Definition other : list nat := 11 :: nil.\n",
        "Local Definition other : list nat := 11 :: nil.\n",
        "Compute (11 + 0).\n",
    )
    for follower in followers:
        got, why = _values(_TABLE + follower)
        ensure(got == [3, 5, 7], f"after {follower!r} the table read {got} ({why})")
        got, why = _values("Example table : l = 3 :: 5 :: 7 :: nil.\n" + follower,
                           "example")
        ensure(got == [3, 5, 7], f"after {follower!r} the Example read {got} ({why})")
    # a comment inside the statement is no value and its full stop ends nothing, nested
    # comments included, and a string's full stop ends nothing either
    got, why = _values("Definition table : list nat :=\n"
                       "  3 :: (* the second. It was 4 once. *) 5 :: 7 :: nil.\n")
    ensure(got == [3, 5, 7], f"a comment inside the table read {got} ({why})")
    got, why = _values("Definition table : list nat :=\n"
                       "  3 :: (* outer (* inner. *) 4. *) 5 :: 7 :: nil.\n")
    ensure(got == [3, 5, 7], f"a nested comment inside the table read {got} ({why})")
    got, why = _values("Definition table : list nat :=\n"
                       '  let _ := "a. b" in 3 :: 5 :: 7 :: nil.\n')
    ensure(got == [3, 5, 7], f"a string's full stop ended the table: {got} ({why})")
    # and a qualified name's period is no full stop
    got, why = _values("Definition table : list N := N.of_nat 3 :: 5 :: 7 :: nil.\n")
    ensure(got == [3, 5, 7], f"a qualified name ended the statement: {got} ({why})")


def cases() -> list[Case]:
    return [
        Case("a-decorated-statement-is-read", _a_decorated_statement_is_read),
        Case("a-void-statement-is-refused", _a_void_statement_is_refused),
        Case("a-flag-before-a-brace-is-the-braces", _a_flag_before_a_brace_is_the_braces),
        Case("a-statement-inside-a-comment-is-none", _a_statement_inside_a_comment_is_none),
        Case("a-statement-stops-at-its-own-full-stop",
             _a_statement_stops_at_its_own_full_stop),
    ]
