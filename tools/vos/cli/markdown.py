# SPDX-License-Identifier: Apache-2.0
"""Validate authored Markdown table syntax with the locked standard linter."""

import argparse

from vos import corpus, markdownlint


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    report = markdownlint.run(corpus.find_root())
    print("\n".join(report.out))
    return int(bool(report.findings))
