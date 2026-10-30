# SPDX-License-Identifier: Apache-2.0
"""Version consumers have one explicit owner and no guessed interpreter default."""

import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import pyversion


def _supported_minor() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-pyversion-") as name:
        root = Path(name)
        path = root / pyversion.PROJECT
        path.parent.mkdir()
        for minor in ("3.12", "3.14", "3.99"):
            major, lower = map(int, minor.split("."))
            path.write_text(f'[project]\nrequires-python = ">={minor},<{major}.{lower + 1}"\n',
                            encoding="utf-8", newline="")
            ensure(pyversion.supported_minor(root) == minor,
                   "the target must come from the manifest instead of the running interpreter")


def _invalid_owner_refuses() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-pyversion-") as name:
        root = Path(name)
        path = root / pyversion.PROJECT
        path.parent.mkdir()
        for text in (None, "[broken\n", "", '[project]\nname = "tools"\n',
                     '[project]\nrequires-python = false\n',
                     *('[project]\nrequires-python = "' + value + '"\n' for value in
                       (">=3.12", ">=3.12,<3.15", ">=3.14,<3.14", ">=3.14,<4.15",
                        ">=3.14.0,<3.15", ">=03.14,<3.15", ">=3.014,<3.15",
                        ">=3.14, <3.15", "==3.14", ">=3.14,<3.15,!=3.14.1"))):
            if text is not None:
                path.write_text(text, encoding="utf-8", newline="")
            try:
                pyversion.supported_minor(root)
            except (OSError, ValueError):
                pass
            else:
                raise AssertionError(f"invalid or missing interpreter owner accepted: {text!r}")


def cases() -> list[Case]:
    return [Case("supported minor follows the manifest", _supported_minor),
            Case("missing and malformed version owners refuse", _invalid_owner_refuses)]
