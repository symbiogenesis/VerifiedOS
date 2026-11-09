# SPDX-License-Identifier: Apache-2.0
"""Verify explicit retained compiler helper/lock relocations without reuse."""

import argparse
import json
import sys
from pathlib import Path

from vos import compiler_relocation
from vos.corpus import find_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(suggest_on_error=True, prog="run.py compiler-relocation", description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--catalog-sha256", required=True,
                        help="trusted catalog identity, supplied independently of the mapping")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--seal", type=Path, required=True, help="raw or losslessly gzipped catalog-bound seal")
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="optional metadata report below this checkout's out/")
    args = parser.parse_args(argv)
    try:
        report = compiler_relocation.verify(args.catalog, args.catalog_sha256, args.candidate,
                                            args.seal, args.mapping, output=args.output,
                                            output_root=find_root() / "out")
    except (OSError, ValueError, TypeError) as error:
        print(f"compiler-relocation: refused: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0
