# SPDX-License-Identifier: Apache-2.0
"""The quarantined instruments' own behavioral tests.

They moved here with the instruments they hold, so `python tools/test.py` no longer
discovers them and `python tools/quarantine/gate.py` runs them instead. Each module
keeps the shape every test module in this repository keeps, exporting `cases()` over
`tests.harness.Case`, which is a read of `tools/tests/` and so runs in the permitted
direction.
"""
