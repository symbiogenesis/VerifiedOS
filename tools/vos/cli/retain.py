# SPDX-License-Identifier: Apache-2.0
"""Retain explicit source files in a new contained evidence bundle.

    python tools/run.py retain --bundle q40/hosted --note docs/implementation/completion-log.md
                              --label "Hosted compiler qualification"
                              --file report.json=out/qualification/report.json
                              --gzip logs/compile.log.gz=out/qualification/compile.log.gz

The bundle name is relative to docs/implementation/retained-evidence. Each repeated
--file or --gzip maps one portable member name to one source file; --gzip preserves
already compressed bytes and binds their decoded content too. No glob selects files.
The printed citation is relative to --note; that file is never edited. No files are
staged, no existing evidence is replaced and no build or proof acceptance is granted.
"""

import argparse
import zlib
from pathlib import Path

from vos import retained_evidence
from vos.corpus import find_root


def _selection(value: str, encoding: str) -> retained_evidence.Member:
    member, separator, source = value.partition("=")
    if not separator or not member or not source:
        raise ValueError(f"a selection must be MEMBER=SOURCE: {value!r}")
    return retained_evidence.Member(Path(source), member, encoding)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bundle", required=True, metavar="NAME",
                        help="new directory beneath docs/implementation/retained-evidence")
    parser.add_argument("--note", required=True, type=Path, metavar="PATH",
                        help="owning note's path, used only to make its relative citation")
    parser.add_argument("--label", default="Retained evidence bundle",
                        help="readable Markdown label for the manifest citation")
    parser.add_argument("--file", action="append", default=[], metavar="MEMBER=SOURCE",
                        help="copy one explicitly selected file verbatim; repeat as needed")
    parser.add_argument("--gzip", action="append", default=[], metavar="MEMBER=SOURCE",
                        help="preserve one gzip source, binding stored and decoded bytes")
    args = parser.parse_args(argv)
    try:
        members = [_selection(value, "identity") for value in args.file]
        members.extend(_selection(value, "gzip") for value in args.gzip)
        bundle = retained_evidence.produce(find_root(), args.bundle, members,
                                          note=args.note, label=args.label)
    except (OSError, ValueError, EOFError, zlib.error) as error:
        print(f"FAIL {error}")
        return 1
    print(f"Retained {len(members)} file(s) in {bundle.manifest.parent}")
    print(bundle.citation)
    return 0
