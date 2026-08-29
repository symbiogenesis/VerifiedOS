# SPDX-License-Identifier: Apache-2.0
"""The welded block size, read out of every artifact that writes it.

This parse reaches past the documents into the curated model, as `banks.py`,
`capformat.py`, `coreclass.py` and `decode.py` do, and each such reach is declared
rather than habitual: the exception is the point and not an oversight. The block size
is written at five sites, twice in Sail, twice in the model's configuration dialect and
once in the authored SystemVerilog, and every one of them is outside the checker's
ordinary corpus, so without this the number the document beside them constrains is a
copy nothing holds and the defect the tool exists to catch would be sitting in the
tool's own view of the parameter.

The document that constrains it is *inside* the corpus, so its own statements of the
set and the bound are claims like any other document's, held and repaired in
`vos/checks/counts_geometry.py` with every other claim about it. What is read here is
what the corpus does not carry: four sites in the curated model and one in the
authored SystemVerilog, which is what makes this module's whole reason the reach.

Everything here is a parse and never a decision, as everywhere else in this package.
What the sites mean and which of them may disagree is `vos/checks/counts_geometry.py`'s.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config

DOCUMENT = "docs/block-geometry-constraint.md"

# `type <name> : Int = <n>`, the form both of cap_format.sail's declarations take
_SAIL_INT_RE = r"(?m)^type {} : Int = (\d+)\s*$"

GRANULE_RE = re.compile(_SAIL_INT_RE.format("log2_cap_size"))
BLOCK_RE = re.compile(_SAIL_INT_RE.format("log2_cap_block_size"))
HARNESS_RE = re.compile(r"assert\(caps_per_block == (\d+)\)")

# The fifth site, and the one that is not in the model: the authored capability
# package writes the block size as a SystemVerilog localparam. It is a transcription
# with no assertion behind it, exactly as the harness and the generated
# configurations are, and it is here rather than under the rule that holds the
# package's other widths because a parameter two rules hold is a parameter two rules
# can disagree about.
PACKAGE = "rtl/vos_cheri_pkg.sv"
PACKAGE_RE = re.compile(r"(?m)^\s*localparam int unsigned Log2CapBlockSize = (\d+);")

CONFIG_KEY = ("platform", "cache_block_size_exp")

# `config.json.in` is a CMake template carrying `@VARIABLE@` placeholders where the
# generated configurations carry numbers, so it is not JSON in any dialect and is read
# as the template it is. The key is unique in it, which is what makes that safe.
TEMPLATE_RE = re.compile(rf'"{CONFIG_KEY[-1]}"\s*:\s*(\d+)')


@dataclass
class Geometry:
    """Every site's answer, keyed by what the site is rather than where it is."""

    # site -> the exponent or count it writes, or None where the site has moved
    sites: dict[str, int | None] = field(default_factory=dict)
    granule_exp: int | None = None


def _int(pattern: re.Pattern[str], text: str) -> int | None:
    m = pattern.search(text)
    return int(m.group(1)) if m else None


def read(root: Path) -> Geometry:
    """One pass over the five sites and the granule they are read against. A file that
    is not there yields `None` for its site rather than raising, because a missing
    artifact is a finding the caller words and not an exception it has to catch."""
    geo = Geometry()

    def text(rel: str) -> str:
        path = root / rel
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    declaration = text("model/model/core/cap_format.sail")
    geo.granule_exp = _int(GRANULE_RE, declaration)
    geo.sites["the model's declaration"] = _int(BLOCK_RE, declaration)
    geo.sites["the frozen profile's configuration"] = config.integer(
        root / "model/config/verifiedos.json", *CONFIG_KEY)
    template = TEMPLATE_RE.findall(text("model/config/config.json.in"))
    geo.sites["the generated configurations"] = (
        int(template[0]) if len(template) == 1 else None)

    # the harness writes the group in granules where every other site writes the
    # block's exponent in bytes, so it is converted here rather than compared as if
    # the two were the same quantity
    granules = _int(HARNESS_RE, text("model/model/unit_tests/test_cheri_insts.sail"))
    geo.sites["the model's own harness"] = (
        None if granules is None or granules < 1 or granules & (granules - 1)
        else granules.bit_length() - 1 + (geo.granule_exp or 0))

    geo.sites["the authored capability package"] = _int(PACKAGE_RE, text(PACKAGE))
    return geo
