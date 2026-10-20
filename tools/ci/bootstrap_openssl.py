#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the reviewed private OpenSSL oracle and export its explicit selection."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vos import openssl


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--jobs", type=int, choices=range(1, 7), default=2)
    parser.add_argument("--github-env", type=Path)
    parser.add_argument("--github-path", type=Path)
    args = parser.parse_args()
    prefix = args.prefix
    if any(c in str(prefix) for c in "\r\n\0"):
        parser.error("prefix must not contain line breaks or NUL bytes")
    result = openssl.install(prefix, args.jobs)
    values = openssl.environment(prefix)
    for path in (args.github_env, args.github_path):
        if path is not None and not path.is_absolute():
            parser.error("GitHub environment files must be absolute")
    if args.github_env:
        with args.github_env.open("a", encoding="utf-8") as stream:
            for key, value in values.items():
                stream.write(f"{key}={value}\n")
    if args.github_path:
        with args.github_path.open("a", encoding="utf-8") as stream:
            stream.write(str(prefix / "bin") + "\n")
    print(json.dumps({"environment": values, "path": str(prefix / "bin"), "identity": result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
