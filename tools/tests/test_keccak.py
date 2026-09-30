# SPDX-License-Identifier: Apache-2.0
"""K-91's Gallina reading, held at where an `Example` starts and where it stops.

`vos/checks/keccak.py` reads a known answer out of a named `Example` and compares it
with the Sail literal, and a byte count stands behind every pair. That count is loud
about an answer that grew, and it is loud for the wrong reason about one read past its
own end: what has to be pinned here is that the reading takes the statement, the whole
statement and nothing but the statement.

Three boundaries. A statement ends at its own full stop, as the shared lexer ends it,
so the proof after it adds nothing whether it opens `Proof.` or `Proof using`, and a
numeral a comment inside it quotes is no byte. A statement under any decoration of the
shared grammar is the statement and is read. And one under `Fail` or `Succeed` states
nothing the file keeps and is refused by name.
"""

from tests.harness import Case, ensure
from vos.checks import keccak

_NAME = "keccak_f1600_of_the_all_zero_state"

# Two hundred bytes, the ones FIPS 202 sB.1 would state for lane i being i + 1 in every
# byte, and the twenty-five lanes they recompose to.
_BYTES = " :: ".join(f"0x{lane + 1:02X}" for lane in range(keccak.LANES)
                     for _ in range(keccak.LANE_BYTES)) + " :: nil"
_LANES = [int.from_bytes(bytes([lane + 1] * keccak.LANE_BYTES), "little")
          for lane in range(keccak.LANES)]


def _example(name: str = _NAME, bytes_: str = _BYTES) -> str:
    return f"Example {name} :\n  bytes_of (bits_of_state (f zero_state)) =\n  {bytes_}\n.\n"


def _lanes(text: str) -> tuple[list[int] | None, str]:
    return keccak._gallina_state("(* a fixture *)\n" + text, _NAME)


def _a_statement_stops_at_its_own_full_stop() -> None:
    got, why = _lanes(_example() + "Proof. vm_compute. reflexivity. Qed.\n")
    ensure(got == _LANES and not why, f"the plain Example read {got} ({why})")
    # a proof opened with `Proof using`, and the next Example's `Proof.` below it, add
    # nothing to the statement above
    followed = _example() + "Proof using. vm_compute. reflexivity. Qed.\n" + _example(
        "the_next_answer") + "Proof. vm_compute. reflexivity. Qed.\n"
    got, why = _lanes(followed)
    ensure(got == _LANES and not why, f"after `Proof using` the Example read {got} ({why})")
    # a byte a comment inside the statement quotes is no byte, and its full stop ends
    # nothing
    commented = _example(bytes_=_BYTES.replace(" :: nil", " (* then 0xFF. *) :: nil"))
    got, why = _lanes(commented + "Proof. vm_compute. reflexivity. Qed.\n")
    ensure(got == _LANES and not why, f"a comment's byte was read: {got} ({why})")


def _a_decorated_statement_is_read() -> None:
    for decoration in ("#[local] ", "#[local]\n", "Local ", "Time#[local]", "Local(* c *)",
                       'Redirect "a""b" ', 'Profile"p"'):
        got, why = _lanes(decoration + _example() + "Proof. reflexivity. Qed.\n")
        ensure(got == _LANES and not why,
               f"under {decoration!r} the Example read {got} ({why})")


def _a_void_statement_is_refused() -> None:
    for lead, flag in (("Fail ", "Fail"), ("Succeed\n", "Succeed"),
                       ("Succeed#[local]", "Succeed"), ("Time Fail ", "Fail")):
        got, why = _lanes(lead + _example() + "Proof. reflexivity. Qed.\n")
        ensure(got is None and f"under `{flag}`" in why,
               f"an Example under {lead!r} was read as {got} ({why})")
    # a name the file does not state is still no answer, a longer one included
    got, why = _lanes(_example(_NAME + "_twice") + "Proof. reflexivity. Qed.\n")
    ensure(got is None and "states no Example named" in why,
           f"a longer name answered for the row's: {got} ({why})")


def cases() -> list[Case]:
    return [
        Case("a-statement-stops-at-its-own-full-stop",
             _a_statement_stops_at_its_own_full_stop),
        Case("a-decorated-statement-is-read", _a_decorated_statement_is_read),
        Case("a-void-statement-is-refused", _a_void_statement_is_refused),
    ]
