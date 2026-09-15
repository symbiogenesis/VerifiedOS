# SPDX-License-Identifier: Apache-2.0
"""Compare observed allocation churn with declared sweep and quarantine budgets."""

import argparse
import json
from hashlib import sha256
from pathlib import Path

from vos.allocation_churn import SCOPE, analyze, expected_identity
from vos.jsonc import Json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py allocation-churn", description=__doc__)
    parser.add_argument("capture", type=Path, help="complete observation capture JSON")
    parser.add_argument("--expected-identity", required=True, type=Path,
                        help="independently supplied roster, image, composition and capture identities")
    parser.add_argument("--json", action="store_true", help="emit exact measurements and identities")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    report: dict[str, Json] = {"scope": SCOPE, "milestone_acceptance": "open"}
    try:
        report["sources_sha256"] = {
            name: sha256((root / name).read_bytes()).hexdigest()
            for name in ("tools/vos/allocation_churn.py", "tools/vos/cli/allocation_churn.py",
                         "docs/implementation/roster-measurement-contract.md")
        }
        expected = expected_identity(args.expected_identity.read_bytes())
        report.update(analyze(args.capture.read_bytes(), expected))
        code = 0 if report["within_declared_limits"] else 1
    except (OSError, TypeError, ValueError) as err:
        report["error"] = str(err)
        code = 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        reason = (report["error"] if "error" in report else
                  "within declared limits" if code == 0 else report["findings"])
        # Keep free-form diagnostics as printable as the JSON fields below,
        # including when Windows redirects stdout through a legacy code page.
        reason_text = str(reason).encode("ascii", errors="backslashreplace").decode("ascii")
        print(f"{'ok' if code == 0 else 'FAIL'} allocation-churn: {reason_text}")
        if "totals" in report:
            print(f"  measurements: {json.dumps(report['totals'], sort_keys=True)}")
            print(f"  domains: {json.dumps(report['domains'], sort_keys=True)}")
            print(f"  identity: {json.dumps(report['identity'], sort_keys=True)}")
        if "sources_sha256" in report:
            print(f"  sources_sha256: {json.dumps(report['sources_sha256'], sort_keys=True)}")
        print(f"  {SCOPE}")
    return code
