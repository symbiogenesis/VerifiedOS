# SPDX-License-Identifier: Apache-2.0
"""Generate or check the block-device architectural authority corpus member."""

import argparse

from vos import block_authority
from vos.corpus import find_root
from vos.dialect import AsmError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("emit", "check"))
    args = parser.parse_args(argv)
    root = find_root()
    try:
        if args.action == "emit":
            (root / block_authority.ARTIFACT).write_text(
                block_authority.emit(root), encoding="utf-8", newline="\n")
            findings: list[str] = []
        else:
            findings = block_authority.check(root)
    except (OSError, ValueError, AsmError) as exc:
        findings = [str(exc)]
    if findings:
        print("FAIL block-authority: " + "; ".join(findings))
        return 1
    print(f"ok block-authority: {args.action} {block_authority.ARTIFACT}")
    return 0
