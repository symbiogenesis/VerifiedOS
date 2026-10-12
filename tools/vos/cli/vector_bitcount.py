# SPDX-License-Identifier: Apache-2.0
"""Generate or check the independent vector bit-count qualification artifacts."""

import argparse

from vos import vector_bitcount
from vos.corpus import find_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("emit", "check"))
    args = parser.parse_args(argv)
    root = find_root()
    try:
        if args.action == "emit":
            for artifact, emit in ((vector_bitcount.SAIL, vector_bitcount.emit_sail),
                                   (vector_bitcount.CORPUS, vector_bitcount.emit_corpus)):
                (root / artifact).write_text(emit(root), encoding="utf-8", newline="\n")
            findings: list[str] = []
        else:
            findings = vector_bitcount.check(root)
    except (OSError, ValueError, TypeError) as exc:
        findings = [str(exc)]
    if findings:
        print("FAIL vector-bitcount: " + "; ".join(findings))
        return 1
    print(f"ok vector-bitcount: {args.action} both generated artifacts")
    return 0
