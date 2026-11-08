# SPDX-License-Identifier: Apache-2.0
"""Pair each requirement entry in [requirements-register.md](../../docs/requirements-register.md) with its cited prose span in [spec.md](../../docs/spec.md) and manage [tools/co-read.json](../co-read.json).

- A bookmark `<a id="r-..."></a>` in [spec.md](../../docs/spec.md) owns the lines from its
  declaration line up to the next bookmark line or Markdown heading (`#`). Bookmarks on
  the same line share that span.
- An entry's prose side is the union of the bookmark derived from its ID (`r-nn-nnn`),
  any `-2`/`-3` repeat bookmarks for that ID, and any explicit `(spec.md#...)` bookmark
  in its `· Trace:` line.
- Each side is hashed to a 12-hex-character SHA-256 prefix after stripping anchor tags
  and collapsing whitespace ([`digest`](#digest)).
- [checks/coread.py](checks/coread.py) (`K-61`) checks that every pair's current digests
  match [tools/co-read.json](../co-read.json); [cli/coread.py](cli/coread.py) (`run.py coread`)
  displays and blesses changed pairs.
"""

import contextlib
import hashlib
import json
import re
from pathlib import Path

from .atomic import atomic_path
from .corpus import ANCHOR_RE, PROSE, Corpus
from .register import REQ_ID_PATTERN, Register

LEDGER = "tools/co-read.json"

_TRACE_ANCHOR_RE = re.compile(r"\(spec\.md#([^)]+)\)")
_CITATION_SUFFIX_RE = re.compile(rf"^({REQ_ID_PATTERN.lower()})-\d+$")
_PROSE_ID_RE = re.compile(r"^r-\d\d-\d")
_TAG_RE = re.compile(r'<a id="[^"]*"></a>')
_DIGEST_CHARS = 12
_CONFERRAL_KINDS = ("Fail-closed", "RoT-fresh")


def digest(text: str) -> str:
    """Return the 12-hex-char SHA-256 digest of `text` with `<a id="..."></a>` stripped and whitespace collapsed."""
    flat = " ".join(_TAG_RE.sub(" ", text).split())
    return hashlib.sha256(flat.encode("utf-8")).hexdigest()[:_DIGEST_CHARS]


def spans(corpus: Corpus) -> dict[str, str]:
    """Return `{bookmark_id: owned_prose_text}` for every unfenced bookmark in [spec.md](../../docs/spec.md)."""
    doc = corpus.by_name[PROSE]
    lines = doc.lines

    at: dict[int, list[str]] = {}
    for m in ANCHOR_RE.finditer(doc.raw):
        i = doc.line_of(m.start())
        if not doc.fenced[i]:
            at.setdefault(i, []).append(m.group(1))

    starts = sorted(at)
    out: dict[str, str] = {}
    for n, start in enumerate(starts):
        stop = starts[n + 1] if n + 1 < len(starts) else len(lines)
        end = start + 1
        while end < stop and not lines[end].startswith("#"):
            end += 1
        text = "\n".join(lines[start:end])
        for ident in at[start]:
            out[ident] = text
    return out


def _bookmarks(by_span: dict[str, str], reg: Register) -> dict[str, list[str]]:
    """Return `{requirement_id: sorted_prose_bookmark_ids}` across `by_span`."""
    carried: dict[str, list[str]] = {}
    for ident in by_span:
        if _PROSE_ID_RE.match(ident):
            carried.setdefault(_CITATION_SUFFIX_RE.sub(r"\1", ident), []).append(ident)

    out: dict[str, list[str]] = {}
    for ident in reg.ids:
        derived = "r" + ident[1:].lower()
        targets = set(carried.get(derived, ()))
        trace = reg.trace_of.get(ident, "")
        if "(spec.md#" in trace:
            targets.update(a for a in _TRACE_ANCHOR_RE.findall(trace) if a in by_span)
        out[ident] = sorted(targets)
    return out


def bookmarks(corpus: Corpus, reg: Register) -> dict[str, list[str]]:
    """Return `{requirement_id: sorted_prose_bookmark_ids}` for `corpus` and `reg`."""
    return _bookmarks(spans(corpus), reg)


def pairs(corpus: Corpus, reg: Register) -> dict[str, tuple[str, str]]:
    """Return `{requirement_id: (prose_text, entry_text)}` for every requirement in `reg`."""
    by_span = spans(corpus)
    marks = _bookmarks(by_span, reg)
    return {ident: ("\n".join(by_span[t] for t in marks[ident]), entry_text(reg, ident))
            for ident in reg.ids}


def entry_text(reg: Register, ident: str) -> str:
    """Return the co-read text of `ident` (body, acceptance criteria, and conferrals, excluding `· Trace:`)."""
    parts = [reg.body.get(ident, ""), reg.accept_text.get(ident, "")]
    parts += [reg.confers.get(kind, {}).get(ident, "") for kind in _CONFERRAL_KINDS]
    return " ".join(p for p in parts if p)


def current(corpus: Corpus, reg: Register) -> dict[str, tuple[str, str]]:
    """Return `{requirement_id: (prose_digest, entry_digest)}` for the current tree."""
    return {i: (digest(p), digest(e)) for i, (p, e) in pairs(corpus, reg).items()}


def read_ledger(root: Path) -> dict[str, tuple[str, str]]:
    """Read [tools/co-read.json](../co-read.json) under `root`, returning `{}` if missing or malformed."""
    path = root / LEDGER
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    if not isinstance(raw, dict):
        return {}
    return {k: (v[0], v[1]) for k, v in raw.items()
            if isinstance(v, list) and len(v) == 2}


def write_ledger(root: Path, rows: dict[str, tuple[str, str]]) -> None:
    """Atomically write `rows` to [tools/co-read.json](../co-read.json), one requirement per line."""
    body = ",\n".join(f'  {json.dumps(k)}: [{json.dumps(p)}, {json.dumps(e)}]'
                      for k, (p, e) in rows.items())
    text = "{\n" + body + "\n}\n" if rows else "{}\n"
    path = root / LEDGER
    with contextlib.suppress(OSError):
        if path.read_bytes() == text.encode("utf-8"):
            return
    with (atomic_path(path) as pending,
          pending.open("w", encoding="utf-8", newline="\n") as stream):
        stream.write(text)
