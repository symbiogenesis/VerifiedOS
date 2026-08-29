# SPDX-License-Identifier: Apache-2.0
"""counts: the two register fields the group's array arithmetic is taken over.

The granule and the ECC codeword's data payload are one entry's statement each, and
two of this group's rules are arithmetic over them: the tag plane, whose density the
granule fixes, and the welded block, under which the codeword sets a floor. Neither
rule owns them, so they are read once here and imported by both rather than written
out twice, which is the defect this checker exists to catch appearing inside it.

They are patterns and never widths. Both figures are read from the entries that fix
them, so no module here states a width of its own: a granule is R-15-203's and a
codeword payload is R-15-181a's.
"""

import re

GRANULE_RE = re.compile(r"one validity tag per \*\*(\d+)-bit\*\* granule")
PAYLOAD_RE = re.compile(r"data payload is (\d+) bits")
