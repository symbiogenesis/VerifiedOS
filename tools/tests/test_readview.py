# SPDX-License-Identifier: Apache-2.0
"""The `view` command end to end, in a sandbox checkout small enough to derive by hand.

What is held: the view opens by declaring itself generated, every entry renders as
a quoted block directly beneath the bookmark that cites it, a `-n` repeat bookmark
gets a pointer rather than a second copy, an entry with no bookmark of its own
renders beneath the bookmark its written-out trace names, the run is deterministic
to the byte across a doubled invocation, and the writer touches nothing but its
output path (the git status bracket the entrypoint tests apply to read-only tools,
applied here around a declared write).
"""

import subprocess
import tempfile
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from tests.harness import TOOLS, Case, cli_argv, ensure, sandbox_tree

_SOURCES = ("tools/vos/cli/__init__.py", "tools/vos/cli/view.py",
            "tools/vos/__init__.py", "tools/vos/coread.py",
            "tools/vos/corpus.py", "tools/vos/proofenv.py", "tools/vos/register.py")

# Three entries: one plain, one whose bookmark the prose repeats under a -2 suffix,
# and one with no bookmark of its own that pairs through its neighbour's.
_REGISTER = """\
# Requirements register (fixture)

## §1 Fixture obligations

**R-01-001** MUST hold the first fixture obligation.
· Accept: the first criterion is measured.
· Trace: [spec 1](spec.md#r-01-001)

**R-01-002** MUST hold the second fixture obligation.
· Accept: the second criterion is measured.
· Trace: [spec 1](spec.md#r-01-002), [spec 1](spec.md#r-01-002-2)

**R-01-003** MUST NOT drop the third fixture obligation.
· Accept: the third criterion is measured.
· Trace: [spec 1](spec.md#r-01-002)
"""

_SPEC = """\
# Design (fixture)

## 1. The fixture claims

The first claim's prose stands here. <a id="r-01-001"></a>

The second claim's prose stands here. <a id="r-01-002"></a>

The second claim recurs here. <a id="r-01-002-2"></a>
"""


def _fixture() -> dict[str, str]:
    root = TOOLS.parent
    files = {rel: (root / rel).read_text(encoding="utf-8") for rel in _SOURCES}
    files["docs/requirements-register.md"] = _REGISTER
    files["docs/spec.md"] = _SPEC
    files[".gitignore"] = "/out/\n"
    return files


def _run(root: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cli_argv(root, "vos.cli.view", *args), cwd=cwd or root,
        capture_output=True, encoding="utf-8", errors="replace", check=False,
        timeout=120)


@dataclass
class _Flow:
    stack: ExitStack | None = None
    root: Path | None = None


_FLOW = _Flow()


def _root() -> Path:
    if _FLOW.root is None:
        raise AssertionError("the sandbox setup case did not run or did not survive")
    return _FLOW.root


def _weave_places_every_entry() -> None:
    stack = ExitStack()
    _FLOW.stack = stack
    _FLOW.root = stack.enter_context(sandbox_tree(_fixture()))

    done = _run(_root())
    ensure(done.returncode == 0 and "wove 3 entries into the prose" in done.stdout,
           f"the weave places all three entries, got {done.returncode}: "
           f"{done.stdout!r} {done.stderr!r}")

    text = (_root() / "out" / "spec-woven.md").read_text(encoding="utf-8")
    ensure(text.startswith("*A generated reading view, never a source"),
           f"the view opens by declaring itself generated, got {text[:80]!r}")

    lines = text.split("\n")
    first = lines.index('The first claim\'s prose stands here. <a id="r-01-001"></a>')
    ensure(lines[first + 2] == "> **R-01-001** MUST hold the first fixture obligation."
           and lines[first + 3] == "> · Accept: the first criterion is measured.",
           f"the entry renders quoted beneath its bookmark, got {lines[first:first + 4]!r}")

    second = lines.index('The second claim\'s prose stands here. <a id="r-01-002"></a>')
    beneath = "\n".join(lines[second:second + 9])
    ensure("> **R-01-002** MUST hold the second fixture obligation." in beneath
           and "> **R-01-003** MUST NOT drop the third fixture obligation." in beneath,
           f"the trace-departing entry renders beneath the bookmark it cites, got "
           f"{beneath!r}")

    recur = lines.index('The second claim recurs here. <a id="r-01-002-2"></a>')
    ensure("cited here again: R-01-002, stated in full at their own bookmarks."
           in lines[recur + 2]
           and "**R-01-002**" not in "\n".join(lines[recur:]),
           f"a repeat bookmark gets a direction-neutral pointer and never a second "
           f"copy, got {lines[recur:recur + 3]!r}")


def _doubled_run_is_byte_identical() -> None:
    view = _root() / "out" / "spec-woven.md"
    before = view.read_bytes()
    porcelain = subprocess.run(["git", "status", "--porcelain"], cwd=_root(),
                               capture_output=True, encoding="utf-8", check=False)
    done = _run(_root())
    ensure(done.returncode == 0, f"the second run exits 0, got {done.returncode}")
    ensure(view.read_bytes() == before,
           "a doubled run must land byte-identical output")
    after = subprocess.run(["git", "status", "--porcelain"], cwd=_root(),
                           capture_output=True, encoding="utf-8", check=False)
    ensure(porcelain.stdout == after.stdout,
           "the writer touches nothing but its ignored output path")


def _teardown() -> None:
    if _FLOW.stack is not None:
        _FLOW.stack.close()
        _FLOW.stack = None
        _FLOW.root = None


def _source_destinations_are_refused() -> None:
    with sandbox_tree(_fixture()) as root:
        source = root / "docs/spec.md"
        before = source.read_bytes()
        done = _run(root, "--out", str(source))
        ensure(done.returncode == 1 and "FAIL view:" in done.stdout,
               f"a source destination must be refused, got {done.returncode}: "
               f"{done.stdout!r} {done.stderr!r}")
        ensure(source.read_bytes() == before, "refusing output must preserve source bytes")

        output = root / "docs/generated/view.md"
        done = _run(root, "--out", str(output))
        ensure(done.returncode == 1 and not output.parent.exists(),
               "nonignored contained output must be refused before creating its directory")

        tracked = root / "out/tracked.md"
        tracked.parent.mkdir()
        tracked.write_bytes(b"retained source\n")
        added = subprocess.run(["git", "add", "--force", "--", "out/tracked.md"], cwd=root,
                               capture_output=True, text=True, check=False, timeout=30)
        ensure(added.returncode == 0, f"could not stage ignored source fixture: {added.stderr}")
        done = _run(root, "--out", str(tracked))
        ensure(done.returncode == 1 and tracked.read_bytes() == b"retained source\n",
               "a tracked path must be refused even when its directory is ignored")

        alias = root / "out/source-alias.md"
        alias.symlink_to(source)
        done = _run(root, "--out", str(alias))
        ensure(done.returncode == 1 and source.read_bytes() == before,
               "an ignored symlink must not authorize overwriting its source target")


def _explicit_outputs_remain_supported() -> None:
    with sandbox_tree(_fixture()) as root, tempfile.TemporaryDirectory(prefix="vos-view-output-") as name:
        elsewhere = Path(name).resolve()
        for spelling, output in (("out/custom/view.md", root / "out/custom/view.md"),
                                 (str(elsewhere / "external/view.md"), elsewhere / "external/view.md")):
            done = _run(root, "--out", spelling, cwd=elsewhere)
            ensure(done.returncode == 0 and output.read_text(encoding="utf-8").startswith(
                   "*A generated reading view, never a source"),
                   f"explicit ignored or external output must work: {done.stdout!r} {done.stderr!r}")


def cases() -> list[Case]:
    return [
        Case("weave-places-every-entry", _weave_places_every_entry, lane="host"),
        Case("doubled-run-is-byte-identical", _doubled_run_is_byte_identical,
             lane="host"),
        Case("teardown", _teardown, lane="host"),
        Case("source-destinations-are-refused", _source_destinations_are_refused, lane="host"),
        Case("explicit-outputs-remain-supported", _explicit_outputs_remain_supported, lane="host"),
    ]
