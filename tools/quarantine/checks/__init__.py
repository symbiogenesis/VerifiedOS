# SPDX-License-Identifier: Apache-2.0
"""The quarantined checks, one module per rule group.

The shape is `vos.checks`' shape, one `=== group ===` heading per module and one
`run(ctx)` over the `Context` a run is handed, because these two groups ran there
until their instruments were quarantined and nothing about what they decide has
changed. What changed is who runs them: `check.py` no longer does, and
`tools/quarantine/gate.py` does.

`Context` is re-exported here rather than redefined, so a module that moved in
carries the same guarded `from . import Context` it always carried and the two
packages cannot come to hold two different ideas of what a run is.
"""

from vos.checks import Context

# Below the re-export and not above it, on `vos.checks`' own ground: each module
# names `Context` through this one.
from . import banks, freeze

__all__ = ["Context", "banks", "freeze"]

GROUPS = [
    banks,
    freeze,
]
