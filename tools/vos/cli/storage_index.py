# SPDX-License-Identifier: Apache-2.0
"""Compare bounded storage index cases under one conditional redo contract."""

import argparse
import hashlib
import json
from pathlib import Path

from vos.storage_index import experiment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print reproducible measurements and source identities")
    args = parser.parse_args(argv)
    try:
        result = experiment()
    except (AssertionError, ValueError) as error:
        print(f"FAIL storage-index: {error}")
        return 1
    root = Path(__file__).resolve().parents[3]
    result["sources_sha256"] = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in ("tools/vos/storage_index.py", "tools/vos/cli/storage_index.py",
                     "tools/tests/test_storage_index.py", "proofs/JournalIndex.v",
                     "docs/implementation/storage-index-comparison.md")}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"ok storage-index: {result['exhaustive_streams']} exhaustive streams, "
              f"{result['crash_checks']} crash/recovery checks")
        print(json.dumps(result["budget_dispositions"]))
        print("retain incumbent; synthetic cases do not admit a target composition or establish WCET")
    return 0 if result["passed"] else 1
