# SPDX-License-Identifier: Apache-2.0
"""consttab: the published constants two artifacts each state, against each other.

Three files under [proofs/](../../../proofs/) name a file of the curated model as
transcribing what they themselves derive, which is narrower than naming one at all:
[MemoryPlan.v](../../../proofs/MemoryPlan.v) names two as composition-time declarations
it takes as inputs and is not one of the three. What the three mean by it each time is
that a table some standard publishes is transcribed once in Sail and derived a second
time in Gallina, so that a defect in either is a disagreement with the standard rather
than a disagreement between two things this repository wrote.
[Keccak.v](../../../proofs/Keccak.v) says it of
[the permutation](../../../model/model/extensions/keccak/keccak_p1600.sail),
[AesGcm.v](../../../proofs/AesGcm.v) of
[the crypto extension's shared types](../../../model/model/extensions/K/types_kext.sail),
and [Sha256.v](../../../proofs/Sha256.v) of the vector-crypto unit whose sigma amounts
sit one file over in
[its utilities](../../../model/model/extensions/vector_crypto/zvk_utils.sail).

**A discipline with no holder is a sentence**, which is K-91's ground one object over.
That rule holds the three permutation *answers* both Keccak files quote and reaches no
table. The *tables those answers are computed from* are what this rule holds, and the
tree names that gap twice: the completion log's M3.4d block records the AES pair as a
finding owing a checker id, and Sha256.v writes at its own fourth reading that no rule
reads the two together. This rule is the id the first of those asks for, and its subject
is the tables.

**The subject is the constants and never the functions.** Sha256.v declines its pair
because the thing transcribed on both sides is four *functions*, and no text comparison
decides that two functions agree. What this rule takes out of that pair is the ten
rotation amounts the model spells at its own SEW-32 arms, which is the part text can
decide; the functions stay unheld and the file's own note stays true.

**At this gate the tables and the answers are independent transcriptions.**
`check.py` runs on the host with no prover and no Sail, so nothing here proves an
`Example` or runs a harness: what connects a file's tables to its answers is that file's
own gate, and neither gate runs when this rule does. That is the whole of what this rule
adds over the Keccak rows' other holders, and it is worth the rows: the guest gates run
by hand before anything lands and CI runs the host wave at every push, so on the day a
table moves on one side alone, this is what is running.

**Neither side is normalized into the other's shape by hand**, on K-91's ground. Each
row names how each side is read, and the row is what makes a rewrite that preserves the
constants a non-finding: a Sail vector literal is `dec`-ordered and both tables read
that way are written so that the written order is the index order, each with the
subtracting accessor beside it that makes it true; a `match` is read by its arm keys
rather than by its written order; an `@` concatenation is most-significant-first, so it
is read backwards; a Gallina `Example` states its list in the standard's own order and
radix. Both sides are decoded to integers and compared as numbers, so a byte written
`0x01` against a word written `0x00000001` is not a finding and a byte that moved is.

**What is a row is decided by there being two statements**, never by there being one
worth checking. Four constants of this shape were considered and are not rows, each for
a reason about the model's side. The model's `aes_sbox_inv_table` is a table AesGcm.v
states no published counterpart for. Its *forward* MixColumns coefficients are two
literals and two implicit ones, `gfmul(so, 0x3) @ so @ so @ gfmul(so, 0x2)`, so half the
row has nothing to read where the inverse spells all four. The field modulus's low byte
is a literal inside `xt2`'s conditional rather than a named constant, its value being
what the S-box row already ranges over. And the GHASH reduction byte AesGcm.v names
`sail_reduction` for the model is written inside two instruction clauses of
`zvkg_insts.sail` rather than as a definition, so locating it means an expression
pattern where every row here reads a name.

**Reaching into `proofs/` and `model/` costs no corpus-window change**, on the precedent
K-42 and K-91 both set: this checker's corpus is the git index and is what the
total-class rules are stated over, where a rule naming its own paths reads them itself.
Membership is taken off the corpus's own tracked list rather than a `git cat-file` per
path, so the files cost no subprocess in the green case, and the index is consulted only
to word a failure. Membership is by name accordingly, the rows held in this module, so
nothing about a pair can quietly narrow under an edit to either file, and the rule owes
the floors group no member count on the ground K-83, K-97 and K-101 each state: a site
that has stopped matching reports here, on the day it stops.

Fail-closed in seven places on K-67's and K-75's ground. A file the index does not carry
is outside this checker's corpus and every claim about it is vacuous; a file the index
carries and the working tree does not has no bytes to read; a statement this module
cannot locate by name on either side is a finding rather than a pair dropped out of the
comparison; a side that does not decode to the row's own size is the same; a `match`
whose arms are not the keys this module reads them by is a form it does not recognise
and asks for a person about; a row naming no site or no values would decide nothing, so
it is refused where it is written; and the row table reading empty would leave the rule
agreeing with every one of no constants, so its size is a floor stated here rather than
a count taken from a document.

**`--fix` does not repair it**, on the ground K-89, K-91 and the co-read ledger already
state: either side may be the one that is right, the interesting fact is which file
moved, and a published constant rewritten by the wave that was supposed to report it is
a differential pair repaired into agreement with itself.
"""

import re
from collections.abc import Callable
from math import isqrt
from typing import TYPE_CHECKING, TypedDict

# `Context` lives in this package's __init__, which imports this module in turn.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== consttab: the published constants two transcriptions each state ==="

AESGCM = "proofs/AesGcm.v"
KECCAK_V = "proofs/Keccak.v"
SHA256_V = "proofs/Sha256.v"
KEXT = "model/model/extensions/K/types_kext.sail"
KECCAK_SAIL = "model/model/extensions/keccak/keccak_p1600.sail"
ZVK_UTILS = "model/model/extensions/vector_crypto/zvk_utils.sail"


class Pair(TypedDict):
    """One constant two artifacts state, and how each side states it.

    `gread` and `sread` are the readings and not the files: two rows over one file may
    be read differently and two rows over two files may be read the same way. `sites`
    is the model's own names in the order this row reads them, which is the row's and
    not the file's: the four sigma functions are written in the model in one order and
    grouped in the Gallina list in another, and the row is where that correspondence is
    stated. `size` is how many integers the constant is, held on both sides so that a
    truncated list and a truncated table are findings rather than a shorter comparison.
    """

    what: str
    gallina: str
    name: str
    gread: str
    sail: str
    sites: tuple[str, ...]
    sread: str
    size: int


# Every pair, each named by what it is of. Held here rather than located by a pattern,
# so the set cannot narrow under an edit to either transcription.
PAIRS: list[Pair] = [
    {"what": "the AES forward S-box",
     "gallina": AESGCM, "name": "the_derived_sbox_is_the_published_table",
     "gread": "example",
     "sail": KEXT, "sites": ("aes_sbox_fwd_table",), "sread": "vector", "size": 256},

    {"what": "the AES round constants",
     "gallina": AESGCM,
     "name": "the_derived_round_constants_are_the_published_table",
     "gread": "example",
     "sail": KEXT, "sites": ("aes_decode_rcon",), "sread": "arms", "size": 10},

    {"what": "the AES inverse MixColumns coefficients",
     "gallina": AESGCM, "name": "inv_mix_polynomial", "gread": "definition",
     "sail": KEXT, "sites": ("aes_mixcolumn_byte_inv",), "sread": "concat", "size": 4},

    {"what": "the Keccak-f round constants",
     "gallina": KECCAK_V,
     "name": "the_derived_round_constants_are_the_published_table",
     "gread": "be8",
     "sail": KECCAK_SAIL, "sites": ("keccak_round_constants",), "sread": "vector",
     "size": 24},

    {"what": "the Keccak rho rotation offsets",
     "gallina": KECCAK_V, "name": "the_derived_rho_offsets_are_the_published_table",
     "gread": "example",
     "sail": KECCAK_SAIL, "sites": ("keccak_rho",), "sread": "grid", "size": 25},

    # The model groups the four sigmas as sigma-0, sigma-1, Sigma-0, Sigma-1 and the
    # Gallina list groups them the other way up, so the site order here is the list's.
    {"what": "the SHA-256 sigma rotation amounts",
     "gallina": SHA256_V, "name": "rotation_amounts", "gread": "definition",
     "sail": ZVK_UTILS,
     "sites": ("zvk_sum0", "zvk_sum1", "zvk_sig0", "zvk_sig1"),
     "sread": "rotates", "size": 10},
]

# how many bytes a big-endian group of the `be8` reading composes
BE_GROUP = 8

# the element width the SEW-keyed arm of a `rotates` site is read at
SEW = 32

# A numeric literal on either side: a hexadecimal one first, so that `0x01` is one
# literal rather than a zero and a one.
_LIT_RE = re.compile(r"0[xX]([0-9A-Fa-f]+)|(?<![\w.])(\d+)(?![\w.])")

# The statement's own `=`, which is neither `=>` nor `:=` nor a comparison. An
# `Example`'s left-hand side may itself contain a `fun _ => _`, so the first `=` in the
# body is not reliably the one the answer follows.
_ASSIGN_RE = re.compile(r"(?<![:<>=!])=(?![=>])")

# A `Definition`'s own `:=`, which is the same split one token over.
_DEFINE_RE = re.compile(r":=")

# What a Coq identifier continues into, so that a statement whose name merely starts with
# a row's is not the statement the row names.
_CONTINUES_RE = re.compile(r"[\w']")

# Where a Gallina body stops. Every construct here opens at column zero in the artifacts
# this rule reads, and the two endings both artifacts use, a `Proof.` block and a
# trailing `:= eq_refl.`, are covered by the first and by the next construct.
_BLOCK_END_RE = re.compile(
    r"(?m)^(?:Proof\.|Qed\.|Example |Definition |Lemma |Theorem |Corollary |"
    r"Fixpoint |Notation |Section |End |\(\*)")

# One arm of a Sail `match` whose value is a literal, and one whose value is a nested
# `match`. A wildcard arm is a key like any other here: the model writes the last arm of
# a total match as `_`, so the keys are checked as a sequence rather than as a set.
_ARM_RE = re.compile(r"(0[xX][0-9A-Fa-f]+|\d+|_)\s*=>\s*(0[xX][0-9A-Fa-f]+|\d+)\b")
_NESTED_RE = re.compile(r"(0[xX][0-9A-Fa-f]+|\d+|_)\s*=>\s*match\s+\w+\s*\{")

# One arm of a `match SEW`, and one rotation inside it. `>>>` is a rotate and `>>` is a
# shift, and the model spells them apart: the ten amounts this rule reads are the
# rotations, and the two shifts the lower-case sigmas also carry are not in the Gallina
# list either.
_SEW_ARM_RE = re.compile(r"(?m)^\s*(\d+)\s*=>")
_ROTATE_RE = re.compile(r">>>\s*(\d+)")


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
    if len(keys) != size or keys[-1] != "_":
        return False
    return all(key != "_" and int(key, 0) == i for i, key in enumerate(keys[:-1]))


def _only(pair: Pair) -> tuple[str | None, str]:
    """The one model name a single-site reading wants, or why the row cannot be read."""
    if len(pair["sites"]) != 1:
        return None, (f"{pair['what']} names {len(pair['sites'])} site(s) in the model "
                      f"where its {pair['sread']} reading takes exactly one")
    return pair["sites"][0], ""


def _gallina_body(raw: str, pair: Pair, keyword: str) -> tuple[str | None, str]:
    """The text of one named Gallina statement, or why it could not be located.

    The name is matched whole. A Coq identifier continues into a letter, a digit, an
    underscore or a prime, so a search for the name as a prefix locates a statement the
    row does not name: the row's own statement renamed to a longer one then reads green
    off its replacement, which is the one thing this rule promises to report. The
    boundary is checked at each hit rather than written into a pattern, a `(?m)^` scan
    of these files costing more than the whole of the rest of the rule.
    """
    head = f"\n{keyword} {pair['name']}"
    opened = raw.find(head)
    while opened >= 0 and _CONTINUES_RE.match(raw, opened + len(head)):
        opened = raw.find(head, opened + 1)
    if opened < 0:
        return None, f"{pair['gallina']} states no {keyword} named {pair['name']}"
    rest = raw[opened + 1:]
    end = _BLOCK_END_RE.search(rest, 1)
    return (rest[:end.start()] if end else rest), ""


def _gallina_values(raw: str, pair: Pair) -> tuple[list[int] | None, str]:
    """The integers one Gallina statement puts on the right of its own equation."""
    define = pair["gread"] == "definition"
    body, why = _gallina_body(raw, pair, "Definition" if define else "Example")
    if body is None:
        return None, why

    split = (_DEFINE_RE if define else _ASSIGN_RE).search(body)
    if split is None:
        return None, (f"{pair['gallina']}'s {pair['name']} states no equation to read "
                      "a published constant out of")
    return _literals(body[split.end():]), ""


def _gallina(raw: str, pair: Pair) -> tuple[list[int] | None, str]:
    """The integers one Gallina statement means, composed to the row's own size."""
    values, why = _gallina_values(raw, pair)
    if values is None:
        return None, why

    if pair["gread"] == "be8":
        if len(values) != pair["size"] * BE_GROUP:
            return None, (f"{pair['gallina']}'s {pair['name']} states {len(values)} "
                          f"byte(s) where {pair['what']} is {pair['size']} group(s) of "
                          f"{BE_GROUP}")
        values = [sum(values[i * BE_GROUP + j] << (8 * (BE_GROUP - 1 - j))
                      for j in range(BE_GROUP))
                  for i in range(pair["size"])]
    elif len(values) != pair["size"]:
        return None, (f"{pair['gallina']}'s {pair['name']} states {len(values)} "
                      f"value(s) where {pair['what']} is {pair['size']}")
    return values, ""


def _sail_vector(raw: str, pair: Pair) -> tuple[list[int] | None, str]:
    """The integers one Sail vector literal states, in the order it writes them.

    A Sail vector literal is `dec`-ordered, so its first element is its highest index,
    and both tables read this way are written so that the written order is the index
    order, each with the subtracting accessor beside it that makes that true.
    """
    name, why = _only(pair)
    if name is None:
        return None, why
    found = re.search(rf"\blet\s+{re.escape(name)}\s*:\s*vector\b[^=\[]*=\s*\[(.*?)\]",
                      raw, re.DOTALL)
    if found is None:
        return None, f"{pair['sail']} states no vector literal named {name}"
    return _literals(found.group(1)), ""


def _function_at(raw: str, pair: Pair, name: str) -> tuple[int | None, str]:
    """Where one Sail function's definition opens, or why it was not found."""
    header = raw.find(f"function {name}(")
    if header < 0:
        return None, f"{pair['sail']} states no function named {name}"
    return header, ""


def _match_body(raw: str, pair: Pair, name: str) -> tuple[str | None, str]:
    """The body of the `match` one Sail function is written as, or why it was not read."""
    header, why = _function_at(raw, pair, name)
    if header is None:
        return None, why
    scrutinee = raw.find("match", header)
    if scrutinee < 0:
        return None, f"{pair['sail']}'s {name} is not written as a match"
    opened = raw.find("{", scrutinee)
    body = _braced(raw, opened) if opened >= 0 else None
    if body is None:
        return None, f"{pair['sail']}'s {name} opens a match it does not close"
    return body, ""


def _sail_arms(raw: str, pair: Pair) -> tuple[list[int] | None, str]:
    """The integers one Sail `match` answers, indexed by its arm keys."""
    name, why = _only(pair)
    if name is None:
        return None, why
    body, why = _match_body(raw, pair, name)
    if body is None:
        return None, why

    arms = _ARM_RE.findall(body)
    if len(arms) != pair["size"]:
        return None, (f"{pair['sail']}'s {name} answers {len(arms)} arm(s) with a "
                      f"literal where {pair['what']} is {pair['size']}")
    if not all(int(key, 0) == i for i, (key, _) in enumerate(arms) if key != "_"):
        return None, (f"{pair['sail']}'s {name} writes its arms in an order this rule "
                      "does not read, its keys not being 0 upwards")
    return [int(value, 0) for _, value in arms], ""


def _sail_grid(raw: str, pair: Pair) -> tuple[list[int] | None, str]:
    """The integers one Sail nested `match` answers, flattened row by row.

    The outer match is the first index and the inner is the second, and the flattening
    is the Gallina side's own: entry *i* is the pair *(i mod side, i div side)*, which
    is `idx x y = x + side * y`.
    """
    name, why = _only(pair)
    if name is None:
        return None, why
    body, why = _match_body(raw, pair, name)
    if body is None:
        return None, why

    side = isqrt(pair["size"])
    if side * side != pair["size"]:
        return None, (f"{pair['what']} is {pair['size']} value(s), which is not a "
                      "square, so this rule has no rows and columns to read it by")

    outer: list[tuple[str, list[tuple[str, str]]]] = []
    for found in _NESTED_RE.finditer(body):
        inner = _braced(body, found.end() - 1)
        if inner is None:
            return None, (f"{pair['sail']}'s {name} opens an inner match it does not "
                          "close")
        outer.append((found.group(1), _ARM_RE.findall(inner)))

    if not _keys_in_order([key for key, _ in outer], side):
        return None, (f"{pair['sail']}'s {name} states {len(outer)} outer arm(s) in a "
                      f"form this rule does not read, where {pair['what']} wants {side} "
                      "keyed 0 upwards and then a wildcard")
    for key, arms in outer:
        if not _keys_in_order([inner_key for inner_key, _ in arms], side):
            return None, (f"{pair['sail']}'s {name} states {len(arms)} arm(s) under its "
                          f"`{key}` arm in a form this rule does not read")

    return [int(outer[i % side][1][i // side][1], 0) for i in range(pair["size"])], ""


def _sail_concat(raw: str, pair: Pair) -> tuple[list[int] | None, str]:
    """The integers one Sail function concatenates, read from the low byte upwards.

    Sail's `@` is most-significant-first, so the leftmost coefficient is the highest
    byte and the written order is the reverse of the index order the Gallina list is in.
    """
    name, why = _only(pair)
    if name is None:
        return None, why
    header, why = _function_at(raw, pair, name)
    if header is None:
        return None, why
    opened = raw.find("{", header)
    body = _braced(raw, opened) if opened >= 0 else None
    if body is None:
        return None, f"{pair['sail']}'s {name} opens a body it does not close"
    return list(reversed(_literals(body))), ""


def _sail_rotates(raw: str, pair: Pair) -> tuple[list[int] | None, str]:
    """The rotation amounts the SEW-keyed arm of each named function states.

    One row over several functions, read in the row's own order, because the model
    states the four sigmas as four functions and the Gallina side states their amounts
    as one list. Only the rotations are read: the model writes a shift as `>>` and a
    rotation as `>>>`, and the two shifts the lower-case sigmas also carry are not in
    the Gallina list.
    """
    values: list[int] = []
    for name in pair["sites"]:
        body, why = _match_body(raw, pair, name)
        if body is None:
            return None, why
        arms = list(_SEW_ARM_RE.finditer(body))
        chosen = [i for i, arm in enumerate(arms) if int(arm.group(1)) == SEW]
        if len(chosen) != 1:
            return None, (f"{pair['sail']}'s {name} states {len(chosen)} arm(s) keyed "
                          f"{SEW} where this rule reads exactly one")
        at = chosen[0]
        end = arms[at + 1].start() if at + 1 < len(arms) else len(body)
        values += [int(amount) for amount in
                   _ROTATE_RE.findall(body[arms[at].end():end])]
    return values, ""


_SAIL_READINGS: dict[str, Callable[[str, Pair], tuple[list[int] | None, str]]] = {
    "vector": _sail_vector,
    "arms": _sail_arms,
    "grid": _sail_grid,
    "concat": _sail_concat,
    "rotates": _sail_rotates,
}


def _texts(ctx: Context) -> tuple[dict[str, str], list[str]]:
    """Every file the table names, and one finding per file that cannot be read.

    The corpus keeps indexed files apart from files still in the working tree, so
    these distinguish an unstaged deletion from an artifact no longer tracked.
    """
    tracked = set(ctx.corpus.tracked)
    texts: dict[str, str] = {}
    findings: list[str] = []
    named = dict.fromkeys(path for pair in PAIRS
                          for path in (pair["gallina"], pair["sail"]))
    for path in named:
        if path not in tracked:
            if path not in ctx.corpus.indexed:
                findings.append(f"the git index does not carry {path}, so nothing this "
                                "rule decides about the pairs it holds means anything")
            else:
                findings.append(f"{path} is in the index and not in the working tree, "
                                "so there are no bytes here to read")
            continue
        texts[path] = (ctx.root / path).read_text(encoding="utf-8")
    return texts, findings


def _malformed(pair: Pair) -> str:
    """Why a row would decide nothing as it is written, or the empty string."""
    if pair["size"] < 1:
        return (f"{pair['what']} is written as {pair['size']} value(s), so the row "
                "would compare two empty readings and agree")
    if not pair["sites"]:
        return f"{pair['what']} names no site in {pair['sail']} to read"
    if pair["sread"] not in _SAIL_READINGS:
        return (f"{pair['what']} asks for a {pair['sread']} reading of {pair['sail']}, "
                "which this rule does not carry")
    return ""


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
        why = _malformed(pair)
        if why:
            findings.append(why)
            continue
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
            findings.append(f"{pair['sail']}'s {', '.join(pair['sites'])} states "
                            f"{len(want)} value(s) where {pair['what']} is "
                            f"{pair['size']}")
            continue
        off = [i for i in range(pair["size"]) if got[i] != want[i]]
        if off:
            i = off[0]
            findings.append(
                f"{pair['what']} differs between the two transcriptions at {len(off)} "
                f"of {pair['size']} value(s), the first at index {i}: "
                f"{pair['gallina']}'s {pair['name']} states {got[i]:#x} where "
                f"{pair['sail']}'s {', '.join(pair['sites'])} states {want[i]:#x}")
            continue
        decided += 1
        values += pair["size"]

    rep.report("K-107", "published constant(s) two transcriptions disagree about:",
               findings,
               f"the {decided} published constant(s) this rule pairs between the "
               f"Gallina references and the curated model are the same {values} "
               f"value(s), read through each side's own order")
    rep.line()
