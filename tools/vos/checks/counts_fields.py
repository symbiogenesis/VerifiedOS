# SPDX-License-Identifier: Apache-2.0
"""Regexes reading the tag granule (`R-15-203`) and ECC codeword data payload (`R-15-181a`), shared by [counts_tagplane.py](counts_tagplane.py) and [counts_geometry.py](counts_geometry.py)."""

import re

GRANULE_RE = re.compile(r"one validity tag per \*\*(\d+)-bit\*\* granule")
PAYLOAD_RE = re.compile(r"data payload is (\d+) bits")
