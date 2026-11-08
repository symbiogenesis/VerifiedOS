# SPDX-License-Identifier: Apache-2.0
"""Match excluded instruction mnemonics against Sail assembly clauses and the corpus assembler for [counts_model.py](checks/counts_model.py) (`K-66`).

Matches written mnemonics (including `<field>` and `*` wildcard placeholders) against:
- Enumerated or skeleton `mapping clause assembly` entries from [sailbundle.py](sailbundle.py)
  ([`spelled_by`](#spelled_by)).
- Mnemonic rows in [dialect.py](dialect.py) ([`encoder_rows`](#encoder_rows)).
"""

import functools
import re

from . import dialect, sailbundle

# `<eew>` or `*` placeholders in written mnemonics.
_PLACEHOLDER_RE = re.compile(r"<[^>]*>|\*")

# Non-empty alphanumeric expansion for a single field placeholder (does not cross `.`).
_PLACEHOLDER_EXPANSION = r"[0-9a-z]+"


def fragments(name: str) -> tuple[str, ...]:
    """Return the non-empty literal substrings of `name` outside `<...>` and `*` placeholders."""
    parts: list[str] = [p for p in _PLACEHOLDER_RE.split(name) if isinstance(p, str)]
    return tuple(p for p in parts if p)


def spells(skeleton: str, name: str) -> bool:
    """Return True if all literal [`fragments`](#fragments) of `name` appear in `skeleton` in order."""
    at = 0
    for fragment in fragments(name):
        found = skeleton.find(fragment, at)
        if found < 0:
            return False
        at = found + len(fragment)
    return True


@functools.cache
def _expansion(name: str) -> re.Pattern[str]:
    """Compile a full-string regex expanding `<...>` and `*` placeholders in `name`."""
    parts = _PLACEHOLDER_RE.split(name)
    return re.compile(_PLACEHOLDER_EXPANSION.join(re.escape(p) for p in parts) + r"\Z")


def encoder_rows(name: str) -> list[str]:
    """Return all mnemonics in [`dialect.MNEMONICS`](dialect.py#MNEMONICS) matched by `name`."""
    pattern = _expansion(name)
    return [m for m in dialect.MNEMONICS if pattern.match(m)]


def spelled_by(clause: sailbundle.Spelled, name: str) -> list[str]:
    """Return all mnemonics (or skeletons) in `clause` matched by `name`."""
    if not clause.exact:
        return [s for s in clause.mnemonics if spells(s, name)]
    pattern = _expansion(name)
    return [m for m in clause.mnemonics if pattern.match(m)]
