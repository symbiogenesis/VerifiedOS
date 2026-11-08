# SPDX-License-Identifier: Apache-2.0
"""Quarantined check groups run by [gate.py](../gate.py#run).

Each module exposes `HEADING` and `run(ctx)` over [`Context`](../../vos/checks/__init__.py#Context),
which is re-exported here for the check modules in this package.
"""

from vos.checks import Context

from . import banks, freeze

__all__ = ["Context", "banks", "freeze"]

GROUPS = [
    banks,
    freeze,
]
