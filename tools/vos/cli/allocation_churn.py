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
                         "docs/implementation/contracts/roster-measurement.md")
        }
        inputs: dict[str, bytes] = {}
        read_errors: list[OSError] = []
        for name, path in (("capture", args.capture), ("expected_identity", args.expected_identity)):
            try:
                inputs[name] = path.read_bytes()
            except OSError as err:
                read_errors.append(err)
            else:
                report[f"{name}_sha256"] = sha256(inputs[name]).hexdigest()
        # Retain every readable input's actual byte identity even if the other
        # read fails. The first error gives a deterministic refusal diagnostic.
        if read_errors:
            raise read_errors[0]
        expected = expected_identity(inputs["expected_identity"])
        measured = analyze(inputs["capture"], expected)
        # A decoded expectation is not yet a matched capture identity. Publish
        # this only after analysis validates the capture and all of its fields.
        report["identity"] = measured["identity"]
        # Individually decodable integers can produce an exact sum or rate that
        # exceeds this interpreter's decimal conversion limit. Refuse before
        # emitting a success line or adding unrenderable measurements to output.
        try:
            rendered = json.dumps({**report, **measured}, indent=2)
        except ValueError as err:
            raise ValueError(f"exact measurement report cannot be encoded as JSON: {err}") from err
        report.update(measured)
        code = 0 if report["within_declared_limits"] else 1
    except (OSError, TypeError, ValueError) as err:
        report["error"] = str(err)
        code = 2
        rendered = json.dumps(report, indent=2)
    if args.json:
        print(rendered)
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
        for field in ("identity", "capture_sha256", "expected_identity_sha256", "sources_sha256"):
            if field in report:
                print(f"  {field}: {json.dumps(report[field], sort_keys=True)}")
        print(f"  {SCOPE}")
    return code
