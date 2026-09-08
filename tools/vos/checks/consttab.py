# SPDX-License-Identifier: Apache-2.0
"""consttab: the published constants two artifacts each transcribe, against each other.

Three files in this tree say in their own prose that they form a differential pair with
a second file, and mean the same thing by it each time: a published table is
transcribed once in the curated Sail model and derived a second time in Gallina, so
that a defect in either is a disagreement with a standard rather than a disagreement
between two things this repository wrote. [proofs/Keccak.v](../../../proofs/Keccak.v)
says it of [the permutation](../../../model/model/extensions/keccak/keccak_p1600.sail)
and [proofs/AesGcm.v](../../../proofs/AesGcm.v) says it of
[the crypto extension's shared types](../../../model/model/extensions/K/types_kext.sail).

**A discipline with no holder is a sentence**, which is K-91's ground one object over.
That rule holds the three permutation *answers* both Keccak files quote. What neither it
nor anything else reads is the *tables those answers are computed from*, although
Keccak.v's own comment names them as "the whole of what makes the pair a differential
pair", and the AES pair has no holder at all. The completion log records both gaps as
open findings owing a checker id, and this rule is that id.

**At this gate the answers and the tables are four independent transcriptions.**
`check.py` runs on the host with no prover and no Sail, so nothing here proves an
`Example` or runs a harness: what connects a file's tables to its answers is that
file's own gate, and neither gate runs when this rule does. Holding the answers
therefore decides nothing about the tables, which is why K-91 is not generalised into
this table and this table does not restate K-91's three rows.

**Neither side is normalized into the other's shape by hand**, on K-91's ground. Each
row names how each side is read, and the row is what makes a rewrite that preserves the
constants a non-finding: a Sail vector literal is `dec`-ordered so its written order is
its index order, a `match` is read by its arm keys rather than by its written order, and
a Gallina `Example` states its list in the standard's own order and radix. Both sides
are decoded to integers and compared as numbers.

**What is a row is decided by there being two statements**, never by there being one
worth checking. Three constants of this shape were considered and are not rows, each for
the same reason from the other direction: the model's `aes_sbox_inv_table` is a table the
Gallina file states no published counterpart for, the AES mix matrices are coefficients
in Gallina and `xt2`/`xt3` applications in the model, so the model states no literal to
read, and the field modulus's low byte is a literal inside `xt2`'s conditional rather
than a named constant, its value being what the S-box row already ranges over.

**Reaching into `proofs/` and `model/` costs no corpus-window change**, on the precedent
K-42 and K-91 both set: this checker's corpus is the git index and is what the
total-class rules are stated over, where a rule naming two paths reads them itself. The
index reading is the corpus's own tracked list rather than a `git cat-file` per path, so
six paths cost no subprocess. Membership is by name accordingly, four rows held in this
module, so nothing about a pair can quietly narrow under an edit to either file, and the
rule owes the floors group no member count on the ground K-83, K-97 and K-101 each
state: a site that has stopped matching reports here, on the day it stops.

Fail-closed in six places on K-67's and K-75's ground. A file the index does not carry is
outside this checker's corpus and every claim about it is vacuous; a file the working
tree does not carry has no bytes to read; an `Example` or a Sail definition this module
cannot locate by name is a finding rather than a pair dropped out of the comparison; a
side that does not decode to the row's own size is the same; a `match` whose arms are not
the keys this module reads them by is a form it does not recognise and asks for a person
about; and the row table reading empty would leave the rule agreeing with every one of no
constants, so its size is a floor stated here rather than a count taken from a document.

**`--fix` does not repair it**, on the ground K-89, K-91 and the co-read ledger already
state: either side may be the one that is right, the interesting fact is which file
moved, and a published constant rewritten by the wave that was supposed to report it is a
differential pair repaired into agreement with itself.
"""

import re
from math import isqrt
from typing import TYPE_CHECKING, TypedDict

# `Context` lives in this package's __init__, which imports this module in turn.
if TYPE_CHECKING:
    from . import Context

HEADING = ("=== consttab: the published constants two transcriptions each state ===")

AESGCM = "proofs/AesGcm.v"
KECCAK_V = "proofs/Keccak.v"
KEXT = "model/model/extensions/K/types_kext.sail"
KECCAK_SAIL = "model/model/extensions/keccak/keccak_p1600.sail"


class Pair(TypedDict):
    """One constant two artifacts state, and how each side states it.

    `gread` and `sread` are the readings, not the files: two rows over one file may be
    read differently, and two rows over two files may be read the same way. `size` is
    how many integers the constant is, held on both sides so that a truncated list and
    a truncated table are findings rather than a shorter comparison.
    """

    what: str
    gallina: str
    example: str
    gread: str
    sail: str
    name: str
    sread: str
    size: int


# The four pairs, each named by what it is of. Held here rather than located by a
# pattern, so the set cannot narrow under an edit to either transcription.
PAIRS: list[Pair] = [
    {"what": "the AES forward S-box",
     "gallina": AESGCM, "example": "the_derived_sbox_is_the_published_table",
     "gread": "flat",
     "sail": KEXT, "name": "aes_sbox_fwd_table", "sread": "vector", "size": 256},
    {"what": "the AES round constants",
     "gallina": AESGCM,
     "example": "the_derived_round_constants_are_the_published_table",
     "gread": "flat",
     "sail": KEXT, "name": "aes_decode_rcon", "sread": "arms", "size": 10},
    {"what": "the Keccak-f round constants",
     "gallina": KECCAK_V,
     "example": "the_derived_round_constants_are_the_published_table",
     "gread": "be8",
     "sail": KECCAK_SAIL, "name": "keccak_round_constants", "sread": "vector",
     "size": 24},
    {"what": "the Keccak rho rotation offsets",
     "gallina": KECCAK_V,
     "example": "the_derived_rho_offsets_are_the_published_table",
     "gread": "flat",
     "sail": KECCAK_SAIL, "name": "keccak_rho", "sread": "grid", "size": 25},
]

# how many bytes a big-endian group of the `be8` reading composes
BE_GROUP = 8

# A numeric literal on either side: a hexadecimal one first, so that `0x01` is one
# literal rather than a zero and a one.
_LIT_RE = re.compile(r"0[xX]([0-9A-Fa-f]+)|(?<![\w.])(\d+)(?![\w.])")

# The statement's own `=`, which is neither `=>` nor `:=` nor a comparison. The Gallina
# side's left-hand side may itself contain a `fun _ => _`, so the first `=` in an
# `Example` body is not reliably the one the answer follows.
_ASSIGN_RE = re.compile(r"(?<![:<>=!])=(?![=>])")

# Where an `Example` body stops. Every construct here opens at column zero in the
# artifacts this rule reads, and the two endings both artifacts use, a `Proof.` block
# and a trailing `:= eq_refl.`, are covered by the first and by the next construct.
_BLOCK_END_RE = re.compile(
    r"(?m)^(?:Proof\.|Qed\.|Example |Definition |Lemma |Theorem |Corollary |"
    r"Fixpoint |Notation |Section |End |\(\*)")

# One arm of a Sail `match` whose value is a literal, and one whose value is a nested
# `match`. A wildcard arm is a key like any other here: the model writes the last arm of
# a total match as `_`, so the keys are checked as a sequence rather than as a set.
_ARM_RE = re.compile(r"(0[xX][0-9A-Fa-f]+|\d+|_)\s*=>\s*(0[xX][0-9A-Fa-f]+|\d+)\b")
_NESTED_RE = re.compile(r"(0[xX][0-9A-Fa-f]+|\d+|_)\s*=>\s*match\s+\w+\s*\{")


def _literals(text: str) -> list[int]:
    """Every numeric literal the text states, in written order."""
    return [int(hexed, 16) if hexed else int(dec)
            for hexed, dec in _LIT_RE.findall(text)]


def _braced(text: str, opened: int) -> str | None:
    """The body of the brace-delimited block opening at `opened`, or `None` unclosed."""
    depth = 0
    for i in range(opened, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[opened + 1:i]
    return None


def _keys_in_order(keys: list[str], size: int) -> bool:
    """Whether a match's arm keys are `0` to `size - 2` and then a wildcard.

    The model writes a total match over a finite range that way throughout, so this is
    the one form read: anything else is a form this rule does not recognise and reports
    rather than reads, on `vos/provenance.py`'s ground for the same choice.
    """
    if len(keys) != size:
        return False
    if keys[-1] != "_":
        return False
    return all(key != "_" and int(key, 0) == i for i, key in enumerate(keys[:-1]))


def _gallina(raw: str, pair: Pair) -> tuple[list[int] | None, str]:
    """The integers one `Example` states, or why they could not be read."""
    where = pair["gallina"]
    opened = raw.find(f"\nExample {pair['example']}")
    if opened < 0:
        return None, f"{where} states no Example named {pair['example']}"
    rest = raw[opened + 1:]
    end = _BLOCK_END_RE.search(rest, 1)
    body = rest[:end.start()] if end else rest

    assign = _ASSIGN_RE.search(body)
    if assign is None:
        return None, (f"{where}'s {pair['example']} states no equation to read a "
                      "published constant out of")
    values = _literals(body[assign.end():])

    if pair["gread"] == "be8":
        if len(values) != pair["size"] * BE_GROUP:
            return None, (f"{where}'s {pair['example']} states {len(values)} byte(s) "
                          f"where {pair['what']} is {pair['size']} groups of "
                          f"{BE_GROUP}")
        values = [sum(values[i * BE_GROUP + j] << (8 * (BE_GROUP - 1 - j))
                      for j in range(BE_GROUP))
                  for i in range(pair["size"])]
    elif len(values) != pair["size"]:
        return None, (f"{where}'s {pair['example']} states {len(values)} value(s) "
                      f"where {pair['what']} is {pair['size']}")
    return values, ""


def _sail_vector(raw: str, pair: Pair) -> tuple[list[int] | None, str]:
    """The integers one Sail vector literal states, in the order it writes them.

    A Sail vector literal is `dec`-ordered, so its first element is its highest index
    and both tables read here are written so that the written order is the index order,
    each with the subtracting accessor beside it that makes that true.
    """
    found = re.search(rf"\blet\s+{re.escape(pair['name'])}\s*:\s*vector\b[^=\[]*"
                      r"=\s*\[(.*?)\]", raw, re.DOTALL)
    if found is None:
        return None, f"{pair['sail']} states no vector literal named {pair['name']}"
    return _literals(found.group(1)), ""


def _match_body(raw: str, pair: Pair) -> tuple[str | None, str]:
    """The body of the `match` one Sail function is written as, or why it was not read."""
    header = raw.find(f"function {pair['name']}(")
    if header < 0:
        return None, f"{pair['sail']} states no function named {pair['name']}"
    scrutinee = raw.find("match", header)
    if scrutinee < 0:
        return None, f"{pair['sail']}'s {pair['name']} is not written as a match"
    opened = raw.find("{", scrutinee)
    body = _braced(raw, opened) if opened >= 0 else None
    if body is None:
        return None, f"{pair['sail']}'s {pair['name']} opens a match it does not close"
    return body, ""


def _sail_arms(raw: str, pair: Pair) -> tuple[list[int] | None, str]:
    """The integers one Sail `match` answers, indexed by its arm keys."""
    body, why = _match_body(raw, pair)
    if body is None:
        return None, why
    arms = _ARM_RE.findall(body)
    if len(arms) != pair["size"]:
        return None, (f"{pair['sail']}'s {pair['name']} answers {len(arms)} arm(s) "
                      f"with a literal where {pair['what']} is {pair['size']}")
    if not all(int(key, 0) == i for i, (key, _) in enumerate(arms) if key != "_"):
        return None, (f"{pair['sail']}'s {pair['name']} writes its arms in an order "
                      "this rule does not read, its keys not being 0 upwards")
    return [int(value, 0) for _, value in arms], ""


def _sail_grid(raw: str, pair: Pair) -> tuple[list[int] | None, str]:
    """The integers one Sail nested `match` answers, flattened row by row.

    The outer match is the first index and the inner is the second, and the flattening
    is the Gallina side's own: entry *i* is the pair *(i mod side, i div side)*, which
    is `idx x y = x + side * y`.
    """
    body, why = _match_body(raw, pair)
    if body is None:
        return None, why
    side = isqrt(pair["size"])
    if side * side != pair["size"]:
        return None, (f"{pair['what']} is {pair['size']} values, which is not a square, "
                      "so this rule has no rows and columns to read it by")

    outer: list[tuple[str, list[tuple[str, str]]]] = []
    for found in _NESTED_RE.finditer(body):
        inner = _braced(body, found.end() - 1)
        if inner is None:
            return None, (f"{pair['sail']}'s {pair['name']} opens an inner match it "
                          "does not close")
        outer.append((found.group(1), _ARM_RE.findall(inner)))

    if not _keys_in_order([key for key, _ in outer], side):
        return None, (f"{pair['sail']}'s {pair['name']} states {len(outer)} outer arm(s) "
                      f"in a form this rule does not read, where {pair['what']} wants "
                      f"{side} keyed 0 upwards and then a wildcard")
    for key, arms in outer:
        if not _keys_in_order([inner_key for inner_key, _ in arms], side):
            return None, (f"{pair['sail']}'s {pair['name']} states {len(arms)} arm(s) "
                          f"under its `{key}` arm in a form this rule does not read")

    return [int(outer[i % side][1][i // side][1], 0) for i in range(pair["size"])], ""


_SAIL_READINGS = {"vector": _sail_vector, "arms": _sail_arms, "grid": _sail_grid}


def _texts(ctx: Context) -> tuple[dict[str, str], list[str]]:
    """Every file the table names, and one finding per file that cannot be read."""
    tracked = set(ctx.corpus.tracked)
    texts: dict[str, str] = {}
    findings: list[str] = []
    named = dict.fromkeys([path for pair in PAIRS
                           for path in (pair["gallina"], pair["sail"])])
    for path in named:
        if path not in tracked:
            findings.append(f"the git index does not carry {path}, so nothing this rule "
                            "decides about the pairs it holds means anything")
            continue
        here = ctx.root / path
        if not here.is_file():
            findings.append(f"{path} is in the index and not in the working tree, so "
                            "there are no bytes here to read")
            continue
        texts[path] = here.read_text(encoding="utf-8")
    return texts, findings


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)

    texts, findings = _texts(ctx)

    if not PAIRS:
        findings.append("the published-constant table is empty, so this rule would "
                        "agree with every one of no constants")

    decided = 0
    values = 0
    for pair in PAIRS:
        if pair["gallina"] not in texts or pair["sail"] not in texts:
            continue
        got, why = _gallina(texts[pair["gallina"]], pair)
        if got is None:
            findings.append(why)
            continue
        want, why = _SAIL_READINGS[pair["sread"]](texts[pair["sail"]], pair)
        if want is None:
            findings.append(why)
            continue
        if len(want) != pair["size"]:
            findings.append(f"{pair['sail']}'s {pair['name']} states {len(want)} "
                            f"value(s) where {pair['what']} is {pair['size']}")
            continue
        off = [i for i in range(pair["size"]) if got[i] != want[i]]
        if off:
            i = off[0]
            findings.append(
                f"{pair['what']} differs between the two transcriptions at {len(off)} "
                f"of {pair['size']} value(s), the first at index {i}: "
                f"{pair['gallina']}'s {pair['example']} states {got[i]:#x} where "
                f"{pair['sail']}'s {pair['name']} states {want[i]:#x}")
            continue
        decided += 1
        values += pair["size"]

    rep.report("K-107", "published constant(s) two transcriptions disagree about:",
               findings,
               f"the {decided} published constant(s) the Gallina references and the "
               f"curated model both state are the same {values} value(s), read through "
               "each side's own order")
    rep.line()
