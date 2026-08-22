# SPDX-License-Identifier: Apache-2.0
"""The co-read pairing and its ledger, held to what the recorded digests pin.

The 1338 recorded digests pin `digest()`'s flattening exactly: any change to it
dirties the whole ledger at once and forces a mass re-bless, so the flattening is
held here against the two-regex semantics it was proven byte-identical to, and
against golden values that a rewrite cannot drift past. The ledger writer is the
one mutating path in the cluster, so its fixpoint (a no-op write leaves the file
untouched) and its atomicity seam (a temp file and one replace, no strays) are
proven in tempdirs that never reach the real tree; blessing is a judgment, and
nothing here blesses anything.
"""

import hashlib
import re
import tempfile
from pathlib import Path

from tests.harness import Case, ensure, sandbox_tree
from vos import coread
from vos import corpus as corpus_mod
from vos.corpus import PROSE
from vos.register import REGISTER, read_register

_SPACE_RE = re.compile(r"\s+")


def _reference_digest(text: str) -> str:
    """The documented two-regex flattening: drop anchor tags, collapse whitespace
    runs, strip the ends. digest() computes the same in one pass; this reference
    is what "the same" means."""
    flat = _SPACE_RE.sub(" ", coread._TAG_RE.sub(" ", text)).strip()
    return hashlib.sha256(flat.encode("utf-8")).hexdigest()[:coread._DIGEST_CHARS]


def _ledger_root(td: str) -> Path:
    root = Path(td).resolve()
    (root / "tools").mkdir()
    return root


def _digest_goldens() -> None:
    # golden values pinning sha256, the 12-hex truncation, and the flattening at
    # once; a deliberate digest change rerecords them with
    # `python -c "import sys; sys.path.insert(0, 'tools'); from vos import coread;
    # print(coread.digest(...))"` and dirties every ledger row, which is the cost
    # the module docstring names
    ensure(coread.digest("") == "e3b0c44298fc",
           "digest('') is sha256 of the empty flattening, truncated to 12 hex")
    ensure(coread.digest("one  two") == "8ab63e29a4ba",
           "a whitespace run collapses to one space before hashing")
    ensure(coread.digest("one two") == coread.digest("one  two"),
           "reflow is not an edit")
    ensure(coread.digest("a\tb\r\nc") == "0e9f64031fcb",
           "tabs and CRLF flatten exactly as spaces do")


def _digest_equals_reference() -> None:
    # the one-pass flattening against the two-regex semantics it replaced, on the
    # shapes that could tell them apart
    trials = [
        "",
        " ",
        "\t\r\n",
        "a\tb",
        "a\r\nb",
        "a  b\n\nc",
        "  lead and trail  ",
        'x<a id="r-01-001"></a>y',
        '<a id="a"></a><a id="b"></a>',
        'word<a id="r"></a>\r\nnext',
        "a\u00a0b",  # a no-break space is whitespace to both flattenings
    ]
    for text in trials:
        ensure(coread.digest(text) == _reference_digest(text),
               f"digest diverges from the documented flattening on {text!r}")


def _ledger_round_trip() -> None:
    rows = {"R-01-001": ("aaaaaaaaaaaa", "bbbbbbbbbbbb"),
            "R-01-002": ("cccccccccccc", "dddddddddddd")}
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = _ledger_root(td)
        coread.write_ledger(root, rows)
        # golden bytes: one row per pair is what makes a diff of blessings
        # readable, and the selftest's K-61 mutant parses exactly this shape; a
        # deliberate format change rerecords this literal and that mutant together
        ensure((root / coread.LEDGER).read_bytes() == (
            b'{\n'
            b'  "R-01-001": ["aaaaaaaaaaaa", "bbbbbbbbbbbb"],\n'
            b'  "R-01-002": ["cccccccccccc", "dddddddddddd"]\n'
            b'}\n'),
            "the ledger's one-row-per-pair shape moved")
        ensure(coread.read_ledger(root) == rows,
               "read_ledger must hand back exactly what write_ledger recorded")

        coread.write_ledger(root, {})
        ensure((root / coread.LEDGER).read_bytes() == b"{}\n",
               "an empty ledger is the two-brace file, newline-terminated")
        ensure(coread.read_ledger(root) == {}, "and it reads back empty")


def _ledger_noop_skip() -> None:
    rows = {"R-01-001": ("aaaaaaaaaaaa", "bbbbbbbbbbbb")}
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = _ledger_root(td)
        coread.write_ledger(root, rows)
        path = root / coread.LEDGER
        before = path.stat()
        coread.write_ledger(root, rows)
        after = path.stat()
        # byte-identical rows leave bytes, mtime, and the file itself alone: a
        # replace would have landed a new file with a new index
        ensure(path.read_bytes().endswith(b"}\n"), "the ledger still stands")
        ensure(after.st_mtime_ns == before.st_mtime_ns,
               "a no-op write must not touch the mtime")
        ensure(after.st_ino == before.st_ino,
               "a no-op write must not replace the file")


def _ledger_atomic_no_strays() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = _ledger_root(td)
        coread.write_ledger(root, {"R-01-001": ("aaaaaaaaaaaa", "bbbbbbbbbbbb")})
        coread.write_ledger(root, {"R-01-001": ("eeeeeeeeeeee", "ffffffffffff")})
        coread.write_ledger(root, {"R-01-001": ("eeeeeeeeeeee", "ffffffffffff")})
        names = sorted(p.name for p in (root / "tools").iterdir())
        ensure(names == ["co-read.json"],
               f"the temp file must be gone after every write: {names!r}")
        ensure(coread.read_ledger(root)["R-01-001"] == ("eeeeeeeeeeee", "ffffffffffff"),
               "the changed rows landed")


def _ledger_damage_reads_empty() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = _ledger_root(td)
        ensure(coread.read_ledger(root) == {}, "an absent ledger is empty, not an error")

        path = root / coread.LEDGER
        path.write_text("{broken", encoding="utf-8")
        ensure(coread.read_ledger(root) == {}, "unparseable JSON reads as empty")

        path.write_text("[1, 2]", encoding="utf-8")
        ensure(coread.read_ledger(root) == {}, "a non-dict document reads as empty")

        path.write_text('{"a": ["only-one"], "b": "x", "c": ["p", "e"]}',
                        encoding="utf-8")
        ensure(coread.read_ledger(root) == {"c": ("p", "e")},
               "a malformed row is dropped and its well-formed neighbours kept")


_SPEC = '''# Spec

## 1. One

Alpha claim. <a id="r-01-001"></a><a id="r-01-002"></a>
continuation line
More alpha.

### 1.1 Cut

Beta claim. <a id="r-01-003"></a>
beta body

Gamma repeat. <a id="r-01-001-2"></a>
gamma body

## 2. Two

```
<a id="r-01-004"></a>
```
'''

_REGISTER = """# Register

## §1

### 1.1 Alpha

**R-01-001** MUST alpha.
· Accept: criterion one.
· Trace: [§1](spec.md#r-01-001)

**R-01-003** MUST beta.
· Trace: [§1](spec.md#r-01-003)

**R-99-001** MUST delta.
· Trace: [§1](spec.md#r-01-003)

**R-05-005** MUST epsilon.
· Trace: stated above.
"""


def _spans_boundaries() -> None:
    with sandbox_tree({PROSE: _SPEC, REGISTER: _REGISTER}) as root:
        sp = coread.spans(corpus_mod.load(root))
        ensure(sp["r-01-001"] == sp["r-01-002"],
               "bookmarks sharing a line share its span")
        alpha = sp["r-01-001"]
        ensure("continuation line" in alpha and "More alpha." in alpha,
               f"a span owns the lines continuing its claim: {alpha!r}")
        ensure("###" not in alpha and "Beta claim" not in alpha,
               f"a span ends at the next heading, and never crosses into the "
               f"next bookmark's: {alpha!r}")
        beta = sp["r-01-003"]
        ensure("beta body" in beta and "Gamma" not in beta,
               f"the next bookmark's line cuts the span above it: {beta!r}")
        ensure("r-01-004" not in sp,
               "an anchor a fence displays is text, not a bookmark")


def _pairs_rules() -> None:
    with sandbox_tree({PROSE: _SPEC, REGISTER: _REGISTER}) as root:
        corpus = corpus_mod.load(root)
        reg = read_register(corpus)
        pr = coread.pairs(corpus, reg)
        ensure(set(pr) == {"R-01-001", "R-01-003", "R-99-001", "R-05-005"},
               f"every register entry pairs, and nothing else does: {sorted(pr)!r}")

        prose = pr["R-01-001"][0]
        ensure("Alpha claim" in prose and "Gamma repeat" in prose,
               f"the -n suffix places join the derived bookmark's prose: {prose!r}")
        ensure(prose.index("Alpha claim") < prose.index("Gamma repeat"),
               "joined spans keep the sorted-target order the digests pin")

        ensure(pr["R-99-001"][0] == pr["R-01-003"][0],
               "an entry citing a neighbour's bookmark pairs through its trace "
               "exactly as the neighbour pairs through its id")
        ensure(pr["R-05-005"][0] == "",
               "an entry reaching no span pairs with the empty string, for the "
               "rule to report rather than pass")

        entry = pr["R-01-001"][1]
        ensure("MUST alpha" in entry and "criterion one" in entry,
               f"the entry side carries the body and its criteria: {entry!r}")

        cur = coread.current(corpus, reg)
        ensure(cur["R-01-001"] == (coread.digest(prose), coread.digest(entry)),
               "current() is digest() over pairs(), nothing more")


def cases() -> list[Case]:
    return [
        Case("digest-goldens", _digest_goldens),
        Case("digest-equals-reference", _digest_equals_reference),
        Case("ledger-round-trip", _ledger_round_trip),
        Case("ledger-noop-skip", _ledger_noop_skip),
        Case("ledger-atomic-no-strays", _ledger_atomic_no_strays),
        Case("ledger-damage-reads-empty", _ledger_damage_reads_empty),
        Case("spans-boundaries", _spans_boundaries),
        Case("pairs-rules", _pairs_rules),
    ]
