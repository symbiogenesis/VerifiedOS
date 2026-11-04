# SPDX-License-Identifier: Apache-2.0
"""Source-only Python dependency discovery follows independent import fixtures."""

import tempfile
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import python_dependencies as dependencies


def _write(root: Path, name: str, source: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8", newline="")


def _refused(action: Callable[[], object], phrase: str) -> None:
    try:
        action()
    except (ValueError, OSError) as error:
        ensure(phrase in str(error), f"wrong dependency refusal: {error}")
        return
    raise AssertionError(f"dependency discovery accepted {phrase}")


def _transitive_imports() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-python-dependencies-") as temporary:
        root = Path(temporary).resolve()
        files = {
            "tools/start.py": "import vos.worker\n",
            "tools/vos/__init__.py": "from . import initialized\n",
            "tools/vos/initialized.py": "raise RuntimeError('never execute')\n",
            "tools/vos/worker.py": "import json\nfrom .nested import Child\n"
                                   "def later():\n    from . import helper\n"
                                   "if False:\n    import vos.conditional\n",
            "tools/vos/helper.py": "from . import worker\n",
            "tools/vos/conditional.py": "",
            "tools/vos/nested/__init__.py": "from .child import Child\n",
            "tools/vos/nested/child.py": "class Child:\n    pass\n",
            "tools/vos/unrelated.py": "not valid Python !\n",
        }
        for name, text in files.items():
            _write(root, name, text)
        expected = tuple(sorted(set(files) - {"tools/vos/unrelated.py"}))
        ensure(dependencies.sources(root, ("tools/start.py",)) == expected,
               "transitive imports, initializers, cycles and conditional imports differ")
        ensure(dependencies.sources(root, ("tools/vos/helper.py", "tools/start.py")) == expected,
               "multiple entry points must deduplicate deterministically")


def _exports_and_changed_edges() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-python-edges-") as temporary:
        root = Path(temporary).resolve()
        _write(root, "tools/vos/__init__.py", "Handler = int\ndef dispatch():\n    pass\n")
        _write(root, "tools/vos/start.py", "from . import Handler, dispatch\n")
        before = dependencies.sources(root, ("tools/vos/start.py",))
        ensure(before == ("tools/vos/__init__.py", "tools/vos/start.py"),
               "real exported values must not be mistaken for missing modules")
        _write(root, "tools/vos/helper.py", "")
        _write(root, "tools/vos/start.py", "from . import helper\n")
        ensure("tools/vos/helper.py" in dependencies.sources(root, ("tools/vos/start.py",)),
               "a new import edge must join the current checkout's closure")
        (root / "tools/vos/helper.py").unlink()
        _refused(lambda: dependencies.sources(root, ("tools/vos/start.py",)), "vos.helper")
        _write(root, "tools/vos/start.py", "def later():\n    helper = 1\nfrom . import helper\n")
        _refused(lambda: dependencies.sources(root, ("tools/vos/start.py",)), "vos.helper")


def _refusals() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-python-refusals-") as temporary:
        root = Path(temporary).resolve()
        _write(root, "tools/vos/__init__.py", "")
        entry = "tools/vos/start.py"
        _write(root, entry, "import vos.missing\n")
        _refused(lambda: dependencies.sources(root, (entry,)), "vos.missing")
        for text, phrase in (("from .missing import value\n", "vos.missing"),
                             ("from ... import outside\n", "escapes"),
                             ("from . import *\n", "wildcard"),
                             ("def broken(\n", "invalid Python")):
            _write(root, entry, text)
            _refused(lambda: dependencies.sources(root, (entry,)), phrase)
        _refused(lambda: dependencies.sources(root, ("tools/vos/absent.py",)), "entry point")
        _refused(lambda: dependencies.sources(root, ("../outside.py",)), "entry point")
        _refused(lambda: dependencies.sources(root, ()), "at least one")
        _write(root, entry, "")
        read = Path.read_text

        def unreadable(path: Path, encoding: str | None = None,
                       errors: str | None = None, newline: str | None = None) -> str:
            if path == root / entry:
                raise PermissionError("fixture unreadable Python source")
            return read(path, encoding=encoding, errors=errors, newline=newline)

        with patch.object(Path, "read_text", unreadable):
            _refused(lambda: dependencies.sources(root, (entry,)), "unreadable")


def cases() -> list[Case]:
    return [Case("transitive lexical imports without execution", _transitive_imports),
            Case("bound exports and current import edges", _exports_and_changed_edges),
            Case("missing unreadable and malformed inputs refuse", _refusals)]
