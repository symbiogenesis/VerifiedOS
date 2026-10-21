# SPDX-License-Identifier: Apache-2.0
"""Validate and generate research metadata and finite host composer shapes."""

import argparse
import json
from pathlib import Path

from vos import math_evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("emit", "check", "shapes"))
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    try:
        if args.action == "emit":
            math_evidence.emit(root)
            print(f"ok math-evidence: emitted {math_evidence.ARTIFACT}")
        elif args.action == "shapes":
            print(json.dumps(math_evidence.shape_report(root), indent=2, sort_keys=True))
        else:
            if errors := math_evidence.check(root):
                print("FAIL math-evidence: " + "; ".join(errors))
                return 1
            print("ok math-evidence: metadata and finite reference view reproduce; no theorem verdict")
    except (ValueError, OSError) as error:
        print(f"FAIL math-evidence: {error}")
        return 1
    return 0
