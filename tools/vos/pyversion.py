# SPDX-License-Identifier: Apache-2.0
"""The project's single supported Python minor, read from its package metadata."""

import re
import tomllib
from pathlib import Path

PROJECT = "tools/pyproject.toml"
_SINGLE_MINOR = re.compile(r">=([1-9][0-9]*)\.(0|[1-9][0-9]*),<([1-9][0-9]*)\.(0|[1-9][0-9]*)")


def supported_minor(root: Path) -> str:
    """Require a canonical lower bound and the exclusive next-minor upper bound."""
    project = tomllib.loads((root / PROJECT).read_text(encoding="utf-8"))
    try:
        required = project["project"]["requires-python"]
    except (KeyError, TypeError) as error:
        raise ValueError(f"{PROJECT} must declare project.requires-python") from error
    match = _SINGLE_MINOR.fullmatch(required) if isinstance(required, str) else None
    if match is None:
        raise ValueError(f"{PROJECT} requires-python must select exactly one canonical minor")
    major, minor, upper_major, upper_minor = map(int, match.groups())
    if (upper_major, upper_minor) != (major, minor + 1):
        raise ValueError(f"{PROJECT} requires-python must exclude the next minor")
    return f"{major}.{minor}"
