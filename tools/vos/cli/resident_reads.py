# SPDX-License-Identifier: Apache-2.0
"""Run Q44's bounded host witness and executed Python controls."""

import argparse
import json

from vos import resident_reads
from vos.corpus import find_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="include source identities, bounds and every witness")
    args = parser.parse_args(argv)
    try:
        result = resident_reads.qualify(find_root())
    except (OSError, ValueError) as error:
        print(f"FAIL resident-reads: {error}")
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("ok resident-reads: finite two-session host witness and executed Python controls; target/proof joins open")
    return 0
