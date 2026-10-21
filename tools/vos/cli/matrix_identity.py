# SPDX-License-Identifier: Apache-2.0
"""Replay the pinned finite rank-48 identity without executing upstream code."""

import argparse
import json
import tempfile
from pathlib import Path
from urllib.request import urlopen

from vos import matrix_identity as identity
from vos.corpus import find_root


def run(args: argparse.Namespace, root: Path) -> str:
    if args.action == "check-report":
        if args.source_dir or args.fetch or args.output:
            raise ValueError("check-report consumes no source or output options")
        identity.check_report(root)
        return "rank48 receipt identities agree; this check does not rerun external inputs\n"
    if not args.fetch and args.source_dir is None:
        raise ValueError("replay requires --source-dir or explicit --fetch")
    if args.source_dir is not None and not args.source_dir.is_absolute():
        raise ValueError("source directory must be absolute")
    if args.output is not None and not args.output.is_absolute():
        raise ValueError("output path must be absolute")
    with tempfile.TemporaryDirectory(prefix="vos-rank48-") as temporary:
        directory = Path(temporary) if args.fetch else args.source_dir
        if directory is None:
            raise ValueError("no external input directory")
        if args.fetch:
            pin = identity.pin(root)
            for key, digest in pin["files"].items():
                name = f"4x4x4_48_204_{key}"
                url = f"https://raw.githubusercontent.com/jgdumas/plinopt/{pin['revision']}/data/{name}"
                with urlopen(url, timeout=30) as stream:
                    data = stream.read(identity.LIMIT + 1)
                if len(data) > identity.LIMIT or identity.sha(data) != digest:
                    raise ValueError(f"download differs from pinned input: {name}")
                (directory / name).write_bytes(data)
        report = identity.replay(root, directory)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8", newline="")
    return rendered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("replay", "check-report"))
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--source-dir", type=Path)
    inputs.add_argument("--fetch", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        rendered = run(args, find_root())
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"matrix identity refused: {error}")
        return 1
    else:
        print(rendered, end="")
        return 0
