# SPDX-License-Identifier: Apache-2.0
"""K-107's Gallina reading, held at where a statement starts and where it stops.

`vos/checks/consttab.py` reads a published table out of a named Gallina statement and
compares it with the model's, and a size check stands behind every row. That check is
loud about a table that grew or shrank, and silent about one whose extra numerals
happen not to arrive: what has to be pinned here is that the reading takes the
statement, the whole statement and nothing but the statement.

Three boundaries, one case each. A statement under an attribute or a locality is the
statement and is read; one under `Fail` or `Succeed` states nothing the file keeps and
is refused by name. And a statement stops at its own full stop, so the `Proof using`
line, the decorated declaration or the comment around its table adds no value to it,
where the list of next constructs this replaces read the first two as more table.
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


def _a_void_statement_is_refused() -> None:
    for flag in ("Fail ", "Succeed ", "#[local] Fail ", "Fail\n"):
        got, why = _values(flag + _TABLE)
        ensure(got is None and f"under `{flag.split()[-1]}`" in why,
               f"a table under {flag!r} was read as {got} ({why})")
    got, why = _values("  " + _TABLE)
    ensure(got is None and "states no Definition named table" in why,
           f"an indented statement opens no statement here: {got} ({why})")


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
    # a comment inside the statement is no value and its full stop ends nothing
    got, why = _values("Definition table : list nat :=\n"
                       "  3 :: (* the second. It was 4 once. *) 5 :: 7 :: nil.\n")
    ensure(got == [3, 5, 7], f"a comment inside the table read {got} ({why})")
    # and a qualified name's period is no full stop
    got, why = _values("Definition table : list N := N.of_nat 3 :: 5 :: 7 :: nil.\n")
    ensure(got == [3, 5, 7], f"a qualified name ended the statement: {got} ({why})")


def cases() -> list[Case]:
    return [
        Case("a-decorated-statement-is-read", _a_decorated_statement_is_read),
        Case("a-void-statement-is-refused", _a_void_statement_is_refused),
        Case("a-statement-stops-at-its-own-full-stop",
             _a_statement_stops_at_its_own_full_stop),
    ]
