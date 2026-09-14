#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Emit the store-side JSON record for one or more named closures, whole.

Usage: store.py <name>=<root>[:<suffix>,<suffix>...] ...

Predicate: every regular file under each named root, filtered to the suffixes given
after the colon where any are given and unfiltered where none are, counted by its
`st_size` and named by the SHA-256 of its bytes. Symbolic links are not followed and
are not counted, so a file reached twice through one is counted once.

Two totals are reported per closure and one over the union, because a content-addressed
store holds one object per distinct hash (R-13-008): `bytes` is the sum over files and
`unique_bytes` the sum over distinct digests. The union's `unique_bytes` is the figure a
device holding every closure at once would occupy, and it is where the deduplication is
credited: crediting it inside each closure and again across them would count one saving
twice, so the per-closure `unique_bytes` is reported as a property of that closure alone
and only the union figure is summed against a capacity.

This script measures what is on this machine. It does not know what a device's store
would be obliged to hold, and it invents no member that is absent from the roots it is
given: a closure whose producer does not exist here is absent from its output entirely.

A spec it cannot measure is refused rather than reported as zero. `os.walk` on an absent
root yields nothing and raises nothing, so a ghost root would otherwise emit a well-formed
empty closure indistinguishable from a real one, and a root carrying a colon would parse
its own tail as a suffix list and do the same. Both are caught here: the root must be an
existing directory and every suffix must begin with a dot.
"""
import hashlib
import json
import os
import sys
from pathlib import Path


def walk(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    found = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if not Path(dirpath, d).is_symlink()]
        for name in filenames:
            path = Path(dirpath, name)
            if path.is_symlink() or not path.is_file():
                continue
            if suffixes and not name.endswith(suffixes):
                continue
            found.append(path)
    return found


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return sha.hexdigest()


def measure(root: Path, suffixes: tuple[str, ...]) -> tuple[dict, dict[str, int]]:
    sizes: dict[str, int] = {}
    by_suffix: dict[str, list[int]] = {}
    total = 0
    files = walk(root, suffixes)
    for path in files:
        size = path.stat().st_size
        total += size
        sizes.setdefault(digest(path), size)
        by_suffix.setdefault(path.suffix or "<none>", []).append(size)
    return ({
        "root": str(root),
        "suffixes": list(suffixes),
        "files": len(files),
        "bytes": total,
        "unique_objects": len(sizes),
        "unique_bytes": sum(sizes.values()),
        "by_suffix": {suffix: {"files": len(v), "bytes": sum(v)}
                      for suffix, v in sorted(by_suffix.items())},
    }, sizes)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    closures, union = {}, {}
    for spec in argv:
        name, assigned, rest = spec.partition("=")
        root_text, _, suffix_list = rest.partition(":")
        suffixes = tuple(s for s in suffix_list.split(",") if s)
        if not assigned or not name or not root_text:
            print(f"not a <name>=<root>[:<suffix>,...] spec: {spec}", file=sys.stderr)
            return 2
        undotted = [s for s in suffixes if not s.startswith(".")]
        if undotted:
            print(f"every suffix begins with a dot, and {undotted} does not: {spec}",
                  file=sys.stderr)
            return 2
        root = Path(root_text)
        if not root.is_dir():
            print(f"no such directory, so no closure is measurable there: {root_text}",
                  file=sys.stderr)
            return 2
        record, sizes = measure(root, suffixes)
        closures[name] = record
        union.update(sizes)
    json.dump({
        "closures": closures,
        "union": {
            "bytes": sum(c["bytes"] for c in closures.values()),
            "files": sum(c["files"] for c in closures.values()),
            "unique_objects": len(union),
            "unique_bytes": sum(union.values()),
        },
        "predicate": ("every regular non-symlink file under each root, filtered by suffix "
                      "where given, sized by st_size and named by the SHA-256 of its bytes; "
                      "the union credits one object per distinct digest exactly once"),
    }, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
