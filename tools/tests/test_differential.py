# SPDX-License-Identifier: Apache-2.0
"""The corpus manifest: its parse, its rewrite fixpoint, and the check count.

The manifest is versioned evidence, so its rewrite path is held to the repair
discipline: only the measured fields move, a refresh that measured what is
already recorded writes nothing at all, and a second application of any rewrite
is a byte-identical no-op. Every mutating case runs on a temp copy of the real
manifest, never the tracked one.
"""

import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from tests.harness import Case, ensure
from vos import differential
from vos.corpus import find_root

# A sentinel mtime far from now: a skipped write leaves it standing, and a real
# write moves it however coarse the filesystem clock is.
_SENTINEL_NS = 1_000_000_000


@contextmanager
def _corpus_copy() -> Iterator[tuple[Path, differential.Corpus]]:
    """The real manifest, copied byte-for-byte under a throwaway root."""
    manifest = find_root() / differential.CORPUS_DIR / differential.MANIFEST
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        (root / differential.CORPUS_DIR).mkdir()
        copy = root / differential.CORPUS_DIR / differential.MANIFEST
        copy.write_bytes(manifest.read_bytes())
        yield root, differential.load(root)


def _stamp(path: Path) -> int:
    os.utime(path, ns=(_SENTINEL_NS, _SENTINEL_NS))
    return path.stat().st_mtime_ns


def _load_round_trip() -> None:
    with _corpus_copy() as (root, corpus):
        raw = json.loads((root / differential.CORPUS_DIR / differential.MANIFEST)
                         .read_text(encoding="utf-8"))
        ensure(corpus.version == raw["version"], "the corpus version must round-trip")
        ensure(corpus.trace_schema == raw["trace_schema"],
               "the trace schema must round-trip")
        ensure(len(corpus.members) == len(raw["members"]),
               f"load kept {len(corpus.members)} of {len(raw['members'])} members")
        for member, row in zip(corpus.members, raw["members"], strict=True):
            ensure((member.name, member.source, member.checks, member.records,
                    member.digest)
                   == (row["name"], row["source"], row.get("checks", 0),
                       row.get("records", 0), row.get("digest", "")),
                   f"member {row['name']} did not round-trip: {member}")
        first = corpus.members[0]
        ensure(corpus.source(first)
               == root / differential.CORPUS_DIR / first.source,
               "source() must compose the member's path under the corpus directory")


def _member_defaults() -> None:
    # A row declaring only name and source is a member nothing has measured yet.
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        (root / differential.CORPUS_DIR).mkdir()
        (root / differential.CORPUS_DIR / differential.MANIFEST).write_text(
            '{"version": 1, "trace_schema": 1,\n'
            ' "members": [{"name": "a", "source": "a.s"}]}\n', encoding="utf-8")
        member = differential.load(root).members[0]
        ensure((member.checks, member.records, member.digest) == (0, 0, ""),
               f"an unmeasured member must default to (0, 0, ''), got {member}")


def _rewrite_fixpoint() -> None:
    # A refresh that measured exactly what the manifest records writes nothing:
    # neither the bytes nor the mtime may move.
    with _corpus_copy() as (root, corpus):
        path = root / differential.CORPUS_DIR / differential.MANIFEST
        before = path.read_bytes()
        stamp = _stamp(path)
        measured = {m.name: (m.checks, m.records, m.digest) for m in corpus.members}
        differential.rewrite(corpus, measured)
        ensure(path.read_bytes() == before,
               "a rewrite of already-recorded measurements changed the bytes")
        ensure(path.stat().st_mtime_ns == stamp,
               "a rewrite of already-recorded measurements rewrote the file anyway")


def _rewrite_updates_then_settles() -> None:
    with _corpus_copy() as (root, corpus):
        path = root / differential.CORPUS_DIR / differential.MANIFEST
        first = corpus.members[0]
        measured = {first.name: (first.checks + 1, first.records + 7,
                                 "0123456789abcdef")}
        differential.rewrite(corpus, measured)

        after = differential.load(root)
        ensure((after.members[0].checks, after.members[0].records,
                after.members[0].digest) == measured[first.name],
               f"the measured fields must land: {after.members[0]}")
        ensure(after.members[1:] == corpus.members[1:],
               "a rewrite may touch no member it was not handed a measurement for")
        ensure((after.version, after.trace_schema)
               == (corpus.version, corpus.trace_schema),
               "the declared fields are not the rewrite's to move")

        # The second application is the fixpoint: byte-identical, mtime untouched.
        settled = path.read_bytes()
        stamp = _stamp(path)
        differential.rewrite(after, measured)
        ensure(path.read_bytes() == settled and path.stat().st_mtime_ns == stamp,
               "the second application of one rewrite must be a byte-level no-op")


def _rewrite_drops_unknown_name() -> None:
    # Pins current behavior: a measured name absent from the manifest is silently
    # ignored, so a member renamed between assemble and rewrite drops its
    # measurement without a word. The audit flags this as a gap; making it a
    # finding is a decision for `rewrite`'s caller, and this case is rerecorded
    # the day that decision lands.
    with _corpus_copy() as (root, corpus):
        path = root / differential.CORPUS_DIR / differential.MANIFEST
        before = path.read_bytes()
        differential.rewrite(corpus, {"renamed-member": (9, 9, "beef")})
        ensure(path.read_bytes() == before,
               "an unknown measured name must currently change nothing")


def _count_checks() -> None:
    # `li gp, N` is the convention: gp by that name, at any indentation, and the
    # highest N is the count. `x3` is the same register but not the convention,
    # and zero is the pass marker rather than a check.
    source = ("start:\n"
              "    li gp, 3\n"
              "li gp,12\n"
              "    li x3, 5\n"
              "    li t0, 99\n"
              "    li gp, 7\n")
    ensure(differential.count_checks(source) == 12,
           f"the highest gp check must win, got {differential.count_checks(source)}")
    ensure(differential.count_checks("    li x3, 5\n") == 0,
           "li x3 is not the convention's spelling and must not count")
    ensure(differential.count_checks("    li gp, 0\n") == 0,
           "zero is the pass marker, not a check")
    ensure(differential.count_checks("") == 0, "no checks is zero")


def cases() -> list[Case]:
    return [
        Case("load-round-trip", _load_round_trip),
        Case("member-defaults", _member_defaults),
        Case("rewrite-fixpoint", _rewrite_fixpoint),
        Case("rewrite-updates-then-settles", _rewrite_updates_then_settles),
        Case("rewrite-drops-unknown-name", _rewrite_drops_unknown_name),
        Case("count-checks", _count_checks),
    ]
