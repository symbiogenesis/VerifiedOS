# SPDX-License-Identifier: Apache-2.0
"""Check published cryptographic constants paired between Gallina proofs and the Sail model (`K-107`).

Three proof files derive or state published standard tables that the curated Sail model
transcribes independently:
- [proofs/AesGcm.v](../../../proofs/AesGcm.v) and
  [model/model/extensions/K/types_kext.sail](../../../model/model/extensions/K/types_kext.sail)
  (forward S-box, round constants, inverse MixColumns coefficients).
- [proofs/Keccak.v](../../../proofs/Keccak.v) and
  [model/model/extensions/keccak/keccak_p1600.sail](../../../model/model/extensions/keccak/keccak_p1600.sail)
  (Keccak-f round constants and rho rotation offsets).
- [proofs/Sha256.v](../../../proofs/Sha256.v) and
  [model/model/extensions/vector_crypto/zvk_utils.sail](../../../model/model/extensions/vector_crypto/zvk_utils.sail)
  (SHA-256 sigma rotation amounts at `SEW = 32`).

Each `Pair` in `PAIRS` specifies how both sides encode the constant (`gread` and `sread`)
and its expected element count (`size`). `K-107` decodes both sides to integer sequences
and verifies that they agree, failing closed on missing/untracked files, unparsed or
`Fail`/`Succeed`-decorated definitions, unrecognized `match` arm key orders, or size
mismatches. Disagreements are never auto-repaired by `--fix`.
"""

import re
from collections.abc import Callable
from math import isqrt
from typing import TYPE_CHECKING, TypedDict

from vos import prooflex
from vos.proofs import SENTENCE_END, VOID, decorations

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
    """Specification of a paired constant across Gallina and Sail (`PAIRS`)."""

    what: str
    gallina: str
    name: str
    gread: str
    sail: str
    sites: tuple[str, ...]
    sread: str
    size: int


# Paired constant tables checked by K-107.
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

    # `sites` orders the four sigma functions to match `Sha256.v`'s `rotation_amounts` list.
    {"what": "the SHA-256 sigma rotation amounts",
     "gallina": SHA256_V, "name": "rotation_amounts", "gread": "definition",
     "sail": ZVK_UTILS,
     "sites": ("zvk_sum0", "zvk_sum1", "zvk_sig0", "zvk_sig1"),
     "sread": "rotates", "size": 10},
]

# Byte count per big-endian integer in `be8` readings.
BE_GROUP = 8

# Element width for the SEW-keyed arm of `rotates` sites.
SEW = 32

# Hexadecimal or decimal integer literal.
_LIT_RE = re.compile(r"0[xX]([0-9A-Fa-f]+)|(?<![\w.])(\d+)(?![\w.])")

# Standalone `=` (excluding `=>`, `:=`, and comparisons) introducing an `Example`'s RHS.
_ASSIGN_RE = re.compile(r"(?<![:<>=!])=(?![=>])")

# `:=` introducing a `Definition`'s RHS.
_DEFINE_RE = re.compile(r":=")

# Characters that continue a Coq identifier.
_CONTINUES_RE = re.compile(r"[\w']")

# Literal-valued and nested-match arms in a Sail `match` expression.
_ARM_RE = re.compile(r"(0[xX][0-9A-Fa-f]+|\d+|_)\s*=>\s*(0[xX][0-9A-Fa-f]+|\d+)\b")
_NESTED_RE = re.compile(r"(0[xX][0-9A-Fa-f]+|\d+|_)\s*=>\s*match\s+\w+\s*\{")

# SEW arm header and `>>>` rotation operator (distinct from `>>` shifts) in Sail.
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
    """Return whether `keys` are `0` through `size - 2` followed by `_` (see [vos/provenance.py](../provenance.py))."""
    if len(keys) != size or keys[-1] != "_":
        return False
    return all(key != "_" and int(key, 0) == i for i, key in enumerate(keys[:-1]))


def _only(pair: Pair) -> tuple[str | None, str]:
    """The one model name a single-site reading wants, or why the row cannot be read."""
    if len(pair["sites"]) != 1:
        return None, (f"{pair['what']} names {len(pair['sites'])} site(s) in the model "
                      f"where its {pair['sread']} reading takes exactly one")
    return pair["sites"][0], ""


def _spaces(span: str) -> str:
    """A span as blank space of its own length, its line breaks kept."""
    return "\n".join(" " * len(line) for line in span.split("\n"))


def _blanked(raw: str) -> str:
    """Replace comments (including nested comments) and string contents with spaces while preserving offsets and newlines."""
    pieces: list[str] = []
    at = 0
    for region in prooflex.regions(raw, strings_in_comments=True):
        if region.kind == "comment":
            pieces.append(raw[at:region.start])
            pieces.append(_spaces(raw[region.start:region.end]))
            at = region.end
        elif region.kind == "string":
            closed = region.end - region.start >= 2 and raw[region.end - 1] == '"'
            inner_end = region.end - 1 if closed else region.end
            pieces.append(raw[at:region.start + 1])
            pieces.append(_spaces(raw[region.start + 1:inner_end]))
            at = inner_end
    pieces.append(raw[at:])
    return "".join(pieces)


def _decorations(lead: str, spaced: bool = False) -> list[str] | None:
    """Parse Gallina statement decorations ([vos/proofs.py](../proofs.py)) from `lead`, or return `None` if unrecognized text remains."""
    found, at = decorations(lead, len(lead) - len(lead.lstrip()) if spaced else 0)
    if at < len(lead):
        return None
    return [str(decoration.group("word") or (decoration.group("bullet") or "#[").strip())
            for decoration in found]


def _lead(blank: str, opened: int) -> list[str] | None:
    """Return the decorations preceding the statement keyword at `opened`, or `None` if non-decoration text precedes it on the line."""
    start = blank.rfind("\n", 0, opened) + 1
    flags = _decorations(blank[start:opened])
    if flags is None:
        return None
    stop = start
    while (stop := blank.rfind(".", 0, stop)) >= 0:
        if SENTENCE_END.match(blank, stop):
            break
    run = _decorations(blank[stop + 1:opened], spaced=True)
    return flags if run is None else run


def _gallina_body(raw: str, pair: Pair, keyword: str) -> tuple[str | None, str]:
    """Locate a named Gallina statement and return `(sentence, error)`.

    Matches `pair['name']` as a complete identifier, allows leading decorations from
    [vos/proofs.py](../proofs.py), and rejects statements decorated with `Fail` or
    `Succeed`.
    """
    head = f"{keyword} {pair['name']}"
    blank = _blanked(raw)
    opened = blank.find(head)
    while opened >= 0:
        if not _CONTINUES_RE.match(raw, opened + len(head)):
            flags = _lead(blank, opened)
            if flags is not None:
                void = next((flag for flag in flags if flag in VOID), None)
                if void is not None:
                    return None, (f"{pair['gallina']} states {keyword} {pair['name']} "
                                  f"under `{void}`, which keeps nothing it states, so "
                                  "no table is read out of it")
                end = SENTENCE_END.search(blank, opened)
                return blank[opened:end.end() if end else len(blank)], ""
        opened = blank.find(head, opened + 1)
    return None, f"{pair['gallina']} states no {keyword} named {pair['name']}"


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
