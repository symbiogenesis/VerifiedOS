# SPDX-License-Identifier: Apache-2.0
"""Check reviewed corpus images or explicitly extend their per-member baseline."""

import argparse
from pathlib import Path

from vos import corpus_images
from vos.corpus import find_root
from vos.dialect import AsmError


def _check(root: Path) -> str:
    faults = corpus_images.check(root)
    if faults:
        raise ValueError("; ".join(faults))
    return "every reviewed source and encoded image unchanged"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "migrate", "extend"))
    args = parser.parse_args(argv)
    root = find_root()
    try:
        if args.action == "migrate":
            corpus_images.migrate(root)
            message = "legacy aggregate reproduced; recorded each reviewed member"
        elif args.action == "extend":
            added = corpus_images.extend(root)
            message = f"{added} new member(s); every old source and image unchanged"
        else:
            message = _check(root)
    except (OSError, ValueError, TypeError, KeyError, AsmError) as exc:
        print(f"FAIL corpus-images: {exc}")
        return 1
    print(f"ok corpus-images: {message}")
    return 0
