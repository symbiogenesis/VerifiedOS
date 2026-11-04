# SPDX-License-Identifier: Apache-2.0
"""Serve Vela's pure and dependent mathematical playground in the native lane."""

from vos.cli.vela_playground import serve


def main(argv: list[str] | None = None) -> int:
    return serve(argv, mathematical=True)
