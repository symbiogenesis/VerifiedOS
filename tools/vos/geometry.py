# SPDX-License-Identifier: Apache-2.0
"""Parse welded block-size declarations across the Sail model, configurations, unit-test harness, and SystemVerilog package for [counts_geometry.py](checks/counts_geometry.py) (`K-57`)."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import capformat, config, sailbundle

DOCUMENT = "docs/hardware/block-geometry-constraint.md"

# Sail type synonyms resolved by name from `sailbundle`.
GRANULE = "log2_cap_size"
BLOCK = "log2_cap_block_size"

HARNESS_RE = re.compile(r"assert\(caps_per_block == (\d+)\)")

PACKAGE = "rtl/vos_cheri_pkg.sv"
PACKAGE_RE = re.compile(r"(?m)^\s*localparam int unsigned Log2CapBlockSize = (\d+);")

CONFIG_KEY = ("platform", "cache_block_size_exp")

# `config.json.in` contains `@VARIABLE@` CMake placeholders, so `cache_block_size_exp` is matched by regex.
TEMPLATE_RE = re.compile(rf'"{CONFIG_KEY[-1]}"\s*:\s*(\d+)')


@dataclass
class Geometry:
    """Welded block-size exponent at each site (`sites`) and the granule exponent (`granule_exp`)."""

    sites: dict[str, int | None] = field(default_factory=dict)
    granule_exp: int | None = None


def _int(pattern: re.Pattern[str], text: str) -> int | None:
    m = pattern.search(text)
    return int(m.group(1)) if m else None


def _declared(bundle: sailbundle.Bundle | None, name: str) -> int | None:
    """Return the integer value of Sail type synonym `name` in `bundle`, or `None`."""
    if bundle is None:
        return None
    try:
        text = bundle.type_text(name)
    except sailbundle.BundleError:
        return None
    found = capformat.SAIL_VALUE_RE.search(text.strip())
    return int(found.group(1)) if found else None


def read(root: Path, bundle: sailbundle.Bundle | None) -> Geometry:
    """Read the granule exponent and the five welded block-size declarations across `bundle` and `root`."""
    geo = Geometry()

    def text(rel: str) -> str:
        path = root / rel
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    geo.granule_exp = _declared(bundle, GRANULE)
    geo.sites["the model's declaration"] = _declared(bundle, BLOCK)
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
