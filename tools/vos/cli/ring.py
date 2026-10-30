#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Emit or compare the ring interface artifact from its declaration and register."""

import argparse

from vos import corpus as corpus_mod
from vos.cli import Table, dispatch
from vos.ring import ARTIFACT, DECLARATION, RingError, emit


def _emit(args: argparse.Namespace) -> int:
    root = corpus_mod.find_root()
    try:
        text = emit(root)
    except RingError as exc:
        print(f"FAIL: {exc}")
        return 1
    path = root / ARTIFACT
    path.write_text(text, encoding="utf-8", newline="")
    print(f"emitted {ARTIFACT} from {DECLARATION} and the register "
          f"({len(text.splitlines())} lines)")
    return 0


def _check(args: argparse.Namespace) -> int:
    root = corpus_mod.find_root()
    try:
        text = emit(root)
    except RingError as exc:
        print(f"FAIL: {exc}")
        return 1
    path = root / ARTIFACT
    if not path.is_file():
        print(f"FAIL: {ARTIFACT} is not in the working tree; `run.py ring emit` "
              f"writes it")
        return 1
    on_disk = path.read_text(encoding="utf-8")
    if on_disk != text:
        want, got = text.splitlines(), on_disk.splitlines()
        where = next((i for i, (a, b) in enumerate(zip(want, got, strict=False))
                      if a != b), min(len(want), len(got)))
        print(f"FAIL: {ARTIFACT} is not what `run.py ring emit` writes; the first "
              f"difference is at line {where + 1}")
        return 1
    print(f"ok: {ARTIFACT} is byte-identical to what `run.py ring emit` writes from "
          f"{DECLARATION} and the register")
    return 0


TABLE: Table = {
    "emit": (_emit, "write the generated interface artifact from its owners"),
    "check": (_check, "re-emit and compare, byte for byte"),
}


def main(argv: list[str] | None = None) -> int:
    return dispatch(__doc__, TABLE, argv, prog="run.py ring")
