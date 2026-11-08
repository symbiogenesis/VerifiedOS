# SPDX-License-Identifier: Apache-2.0
"""Check known-answer permutation states shared by the Gallina and Sail FIPS 202 transcriptions (`K-91`).

[proofs/Keccak.v](../../../proofs/Keccak.v) and
[model/model/unit_tests/test_keccak.sail](../../../model/model/unit_tests/test_keccak.sail)
each state three known-answer 1600-bit permutation outputs (`PAIRS`): the Sail unit
writes 25 64-bit words in standard lane order, while the Coq `Example` sentences write
200 bytes (8 little-endian bytes per lane, per FIPS 202 §B.1).

`K-91` decodes both representations to 25 lane integers and verifies that they match.
It fails closed if either file is untracked or missing, if `PAIRS` is empty, if any
named constant is missing or decorated with `Fail`/`Succeed`, or if a constant does not
decode to 25 lanes. Disagreements are never auto-repaired by `--fix`.
"""

import re
from typing import TYPE_CHECKING

from vos.proofs import VOID, decorations, sentences

if TYPE_CHECKING:
    from . import Context

HEADING = "=== keccak: the two FIPS 202 transcriptions against the answers both quote ==="

GALLINA = "proofs/Keccak.v"
SAIL = "model/model/unit_tests/test_keccak.sail"

LANES = 25
LANE_BYTES = 8

# Paired Coq `Example` names, Sail literal names, and descriptions.
PAIRS: list[tuple[str, str, str]] = [
    ("keccak_f1600_of_the_all_zero_state",
     "keccak_kat_zero_24",
     "Keccak-f[1600] of the all-zero state"),
    ("keccak_f1600_applied_twice_to_the_all_zero_state",
     "keccak_kat_zero_24_twice",
     "Keccak-f[1600] applied twice to the all-zero state"),
    ("keccak_p1600_12_of_the_all_zero_state",
     "keccak_kat_zero_12",
     "Keccak-p[1600,12] of the all-zero state"),
]

_BYTE_RE = re.compile(r"0x([0-9A-Fa-f]{2})\b")
_WORD_RE = re.compile(r"0x([0-9A-Fa-f]{16})\b")


def _gallina_state(raw: str, name: str) -> tuple[list[int] | None, str]:
    """Decode the 25 64-bit lanes from a Coq `Example` of 200 little-endian bytes."""
    head = re.compile(rf"Example\s+{re.escape(name)}\s*:")
    for sentence in sentences(raw):
        found, at = decorations(sentence)
        stated = head.match(sentence, at)
        if stated is None:
            continue
        void = next((str(decoration.group("word")) for decoration in found
                     if decoration.group("word") in VOID), None)
        if void is not None:
            return None, (f"{GALLINA} states Example {name} under `{void}`, which keeps "
                          "nothing it states, so no answer is read out of it")
        body = sentence[stated.end():]
        break
    else:
        return None, f"{GALLINA} states no Example named {name}"
    eq = body.find("=")
    if eq < 0:
        return None, f"{GALLINA}'s {name} states no equation to read an answer out of"
    octets = [int(b, 16) for b in _BYTE_RE.findall(body[eq:])]
    if len(octets) != LANES * LANE_BYTES:
        return None, (f"{GALLINA}'s {name} states {len(octets)} byte(s) where a 1600-bit "
                      f"state is {LANES * LANE_BYTES}")
    return [sum(octets[i * LANE_BYTES + j] << (8 * j) for j in range(LANE_BYTES))
            for i in range(LANES)], ""


def _sail_state(raw: str, name: str) -> tuple[list[int] | None, str]:
    """The twenty-five lanes one Sail literal states, or why they could not be read.

    Written in the standard's lane order and read through `keccak_state_of_literal`, a
    Sail vector literal being `dec`-ordered, so the order the words are written in is the
    lane order and this reads them as written.
    """
    m = re.search(rf"(?s)\blet {re.escape(name)}\s*:\s*keccak_state\s*=\s*\[(.*?)\]", raw)
    if m is None:
        return None, f"{SAIL} states no keccak_state literal named {name}"
    words = [int(w, 16) for w in _WORD_RE.findall(m.group(1))]
    if len(words) != LANES:
        return None, (f"{SAIL}'s {name} states {len(words)} lane(s) where a 1600-bit "
                      f"state is {LANES}")
    return words, ""


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)

    findings: list[str] = []
    texts: dict[str, str] = {}
    for path in (GALLINA, SAIL):
        if path not in ctx.corpus.indexed:
            findings.append(f"the git index does not carry {path}, so nothing this rule "
                            f"decides about the pair means anything")
            continue
        here = ctx.root / path
        if not here.is_file():
            findings.append(f"{path} is in the index and not in the working tree, so "
                            f"there are no bytes here to read")
            continue
        texts[path] = here.read_text(encoding="utf-8")

    if not PAIRS:
        findings.append("the known-answer pair table is empty, so this rule would agree "
                        "with every one of no answers")

    decided = 0
    if len(texts) == 2:
        for coq_name, sail_name, what in PAIRS:
            got, why = _gallina_state(texts[GALLINA], coq_name)
            if got is None:
                findings.append(why)
                continue
            want, why = _sail_state(texts[SAIL], sail_name)
            if want is None:
                findings.append(why)
                continue
            off = [i for i in range(LANES) if got[i] != want[i]]
            if off:
                i = off[0]
                findings.append(
                    f"{what} differs between the two transcriptions at {len(off)} lane(s), "
                    f"the first being lane {i}: {GALLINA}'s {coq_name} states "
                    f"{got[i]:#018x} where {SAIL}'s {sail_name} states {want[i]:#018x}")
            else:
                decided += 1

    rep.report("K-91", "known answer(s) the two FIPS 202 transcriptions disagree about:",
               findings,
               f"the {decided} known answer(s) {GALLINA} and {SAIL} both quote are the "
               f"same {LANES}-lane state, read through each file's own order")
    rep.line()
