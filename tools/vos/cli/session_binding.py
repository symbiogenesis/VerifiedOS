# SPDX-License-Identifier: Apache-2.0
"""Run the Q22c bounded session-attestation assessment."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from vos.session_binding import experiment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the finite experiment as JSON")
    args = parser.parse_args(argv)
    result = experiment()
    root = Path(__file__).resolve().parents[3]
    sources = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
               for name in ("tools/vos/session_binding.py", "tools/vos/cli/session_binding.py",
                            "tools/tests/test_session_binding.py",
                            "docs/assurance/session-binding-qualification.md")}
    if args.json:
        print(json.dumps({"scope": "bounded-symbolic-assessment", "passed": result.passed,
                          "production_adoption": "open", "sources_sha256": sources,
                          **asdict(result)}, indent=2))
    else:
        print(f"{'ok' if result.passed else 'FAIL'} session-binding: "
              f"{result.substitutions} deliveries, {result.accepted} accepted, "
              f"{result.refused} refused, {result.replay_refusals} repeat refusals, "
              f"{result.reopen_refusals} reopen refusals")
        for case in result.scenarios:
            print(f"  {'ok' if case.passed else 'FAIL'} {case.name}: {case.observed}")
        for failure in result.relation_failures:
            print(f"  FAIL {failure}")
        print("bounded symbolic assessment only; protocol, theorem and implementation remain open")
    return 0 if result.passed else 1
