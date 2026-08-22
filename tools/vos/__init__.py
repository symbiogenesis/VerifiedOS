# SPDX-License-Identifier: Apache-2.0
"""Shared machinery for this repository's tools.

Every tool in `tools/` is Python and imports what it needs from here, so a fact is
parsed once and read by whoever wants it. The package holds parses and conventions,
never decisions: the document corpus and the register beside the other counted
artifacts, the apex statement, the derived-figure spellings and repairs, the model's
configuration dialect and the model facts a document restates, the entry-prose
pairing and its ledger, the differential corpus with its dialect, assembler, image
and trace machinery, the reporting convention, and the build environment. The checks
themselves live in `vos.checks`, one module per rule group, and tools/README.md's
inventory says which module owns which parse.
"""
