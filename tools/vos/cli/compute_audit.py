# SPDX-License-Identifier: Apache-2.0
"""Check the feature audit against the frozen external OpenCL core registry."""

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path

from vos.compute_audit import AUDIT_PATH, REGISTRY_REVISION, REGISTRY_URL, compare


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py compute-audit", description=__doc__)
    parser.add_argument("registry", type=Path, help=f"unmodified bytes from {REGISTRY_URL}")
    parser.add_argument("--json", action="store_true", help="emit identities and derived membership")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    try:
        registry = args.registry.read_bytes()
        document = (root / AUDIT_PATH).read_bytes()
        result = compare(registry, document.decode("utf-8"))
    except (OSError, UnicodeError, ValueError, ET.ParseError) as error:
        if args.json:
            print(json.dumps({"verdict": "incomplete", "reason": str(error)}, indent=2))
        else:
            print(f"FAIL compute-audit: {error}")
        return 1
    if args.json:
        print(json.dumps({"verdict": "covered" if result.complete else "incomplete",
                          "registry_revision": REGISTRY_REVISION,
                          "registry_sha256": hashlib.sha256(registry).hexdigest(),
                          "audit_sha256": hashlib.sha256(document).hexdigest(),
                          "semantic_verdict": "requires attended review",
                          **asdict(result)}, indent=2))
    else:
        word = "ok" if result.complete else "FAIL"
        print(f"{word} compute-audit: {len(result.commands)} core commands; "
              f"missing={list(result.missing)}, unknown={list(result.unknown)}, "
              f"duplicate={list(result.duplicate)}")
    return 0 if result.complete else 1
