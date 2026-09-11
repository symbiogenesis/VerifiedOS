# SPDX-License-Identifier: Apache-2.0
"""Qualify the finite revocation barrier and reuse contract on the host."""

import argparse
import json

from vos import corpus, revocation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable evidence")
    args = parser.parse_args(argv)
    try:
        report = revocation.qualify(corpus.find_root())
    except (OSError, revocation.RevocationError) as exc:
        print(f"FAIL: {exc}")
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(report["scope"])
        print(f"positive interleavings: {report['positive_interleavings']}; "
              f"refusal cases: {report['refusal_cases']}")
        print("illustrative schedule bounds: " + json.dumps(report["illustrative_bounds"],
                                                           sort_keys=True))
        print("FAIL: " + str(report["errors"]) if report["errors"] else "qualification: PASS")
    return 1 if report["errors"] else 0
