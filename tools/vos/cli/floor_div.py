# SPDX-License-Identifier: Apache-2.0
"""Plan checked signed floor division and emit experimental RV64 arithmetic."""

import argparse
import json
from dataclasses import asdict

from vos.floordiv import assembly, evaluate, plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--divisor", type=int, required=True)
    parser.add_argument("--value", type=int, action="append", default=[])
    parser.add_argument("--assembly", action="store_true",
                        help="emit a width-64 fragment; x10 in/out, x5/x6/x7 clobbered")
    args = parser.parse_args(argv)
    if args.assembly and args.value:
        parser.error("--assembly and --value are separate output modes")
    try:
        parameters = plan(args.width, args.divisor)
        if args.assembly:
            output = assembly(parameters)
        else:
            output = json.dumps({
                "scope": "constant-floor-division-reference",
                "target_adoption": "open",
                "parameters": asdict(parameters),
                "results": [{"value": value, "quotient": evaluate(parameters, value)}
                            for value in args.value],
            }, indent=2) + "\n"
    except (ValueError, OverflowError) as error:
        print(f"FAIL floor-div: {error}")
        return 1
    print(output, end="")
    return 0
