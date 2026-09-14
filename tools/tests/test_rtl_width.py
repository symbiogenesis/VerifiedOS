# SPDX-License-Identifier: Apache-2.0
"""Guard semantic staging against source drift and partial or invented output."""

import json
from dataclasses import replace
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import rtl_width as width

_TEXT = "// upstream notice\npackage p; old old endpackage\n"
_NOTICE = "// Modified by VerifiedOS test\n"
_PIN = "a" * 40
_SOURCE = width.Source("core/p.sv", width.digest(_TEXT),
                       width.digest(_NOTICE + _TEXT.replace("old", "new")),
                       (width.Edit("old", "new", 2),))


def _refused(source: width.Source, text: str = _TEXT) -> None:
    try:
        width.transform(text, source, _NOTICE)
    except ValueError:
        return
    raise AssertionError("drifting transform accepted")


def _exact_edits_retain_notices() -> None:
    actual = width.transform(_TEXT, _SOURCE, _NOTICE)
    ensure(actual == _NOTICE + _TEXT.replace("old", "new"), "only named edits apply")
    ensure("// upstream notice" in actual, "upstream notice survives staging")


def _identity_and_match_guards() -> None:
    _refused(_SOURCE, _TEXT + "// drift\n")
    _refused(replace(_SOURCE, edits=(width.Edit("old", "new", 1),)))
    _refused(replace(_SOURCE, edits=(width.Edit("missing", "new", 1),)))
    _refused(replace(_SOURCE, output_sha256="0" * 64))
    _refused(replace(_SOURCE, edits=(width.Edit("", "new", 1),)))


def _registry() -> str:
    return json.dumps({"schema": "vos.rtl-width-transforms/1", "pin": _PIN,
                       "notice": _NOTICE, "sources": [{"path": _SOURCE.path,
                       "source_sha256": _SOURCE.source_sha256,
                       "output_sha256": _SOURCE.output_sha256,
                       "edits": [{"old": "old", "new": "new", "count": 2}]}]})


def _staging_requires_one_member_and_exact_pin() -> None:
    with sandbox_tree({width.REGISTRY: _registry(), f"{width.CORE}/core/p.sv": _TEXT}) as root:
        source = root / width.CORE / "core/p.sv"
        work = root / "out"
        with patch.object(width.subprocess, "run", return_value=CompletedProcess([], 0, _PIN, "")):
            for lines in ((), (str(source), str(source))):
                try:
                    width.stage(root, lines, work)
                except ValueError:
                    pass
                else:
                    raise AssertionError("missing or duplicated member accepted")
            ensure(not work.exists(), "refusal precedes every staged write")
            result = width.stage(root, ("unrelated.sv", str(source)), work)
            ensure(result[0] == "unrelated.sv" and Path(result[1]).is_file(),
                   "only the declared member is replaced")
            ensure((work / "scalar-width/core/p.diff").is_file(), "exact source diff retained")
            ensure((work / "scalar-width/receipt.json").is_file(), "identities retained")
        with patch.object(width.subprocess, "run", return_value=CompletedProcess([], 0, "b" * 40, "")):
            try:
                width.stage(root, (str(source),), work)
            except ValueError:
                pass
            else:
                raise AssertionError("wrong checkout pin accepted")


def _registry_rejects_unsafe_and_duplicate_sources() -> None:
    for path in ("../escape", "core/../../escape", "core\\p.sv"):
        data = json.loads(_registry())
        data["sources"][0]["path"] = path
        with sandbox_tree({width.REGISTRY: json.dumps(data)}) as root:
            try:
                width.load(root)
            except ValueError:
                pass
            else:
                raise AssertionError("unsafe source accepted")
    data = json.loads(_registry())
    data["sources"] *= 2
    with sandbox_tree({width.REGISTRY: json.dumps(data)}) as root:
        try:
            width.load(root)
        except ValueError:
            pass
        else:
            raise AssertionError("duplicate source accepted")


def cases() -> list[Case]:
    return [Case(fn.__name__.lstrip("_"), fn) for fn in (
        _exact_edits_retain_notices, _identity_and_match_guards,
        _staging_requires_one_member_and_exact_pin, _registry_rejects_unsafe_and_duplicate_sources,
    )]
