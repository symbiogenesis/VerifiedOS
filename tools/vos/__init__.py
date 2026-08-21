# SPDX-License-Identifier: Apache-2.0
"""Shared machinery for this repository's tools.

Every tool in `tools/` is Python and imports what it needs from here, so a fact is
parsed once and read by whoever wants it. The package carries no checks of its own:
it holds the artifacts (`corpus`, `register`, `apex`), the reporting convention
(`report`), the configuration dialect (`jsonc`), and the build environment (`env`).
The checks themselves live in `vos.checks`, one module per rule group.
"""

__all__ = ["apex", "checks", "corpus", "env", "jsonc", "register", "report"]
