# SPDX-License-Identifier: Apache-2.0
"""The maintained local-link checker preserves the indexed corpus's boundaries."""

import json
import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from tests.pinned_binary_fixture import InstallerFixture
from vos import lychee


def _ordinary_links() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-lychee-links-") as directory:
        root = Path(directory)
        (root / "docs").mkdir()
        (root / "docs/target.md").write_text(
            '# Hello\n\n## caf\u00e9\n\n<a id="custom"></a>\n', encoding="utf-8")
        (root / "docs/a.md").write_text(
            '[relative](target.md#hello) [Unicode](target.md#caf%C3%A9)\n'
            '[explicit](target.md#custom) [reference][target]\n'
            '<a href="target.md#hello">HTML</a>\n'
            '[bad fragment](target.md#absent) [missing](absent.md)\n'
            '[network](https://never-contact.invalid/)\n'
            '```md\n[example](not-a-real-file.md)\n```\n\n'
            '[target]: target.md#hello\n', encoding="utf-8")
        found = lychee.findings(root, ["docs/a.md", "docs/target.md"], {})
        ensure(len(found) == 2 and any("#absent" in item for item in found)
               and any("/absent.md" in item for item in found),
               f"local file and fragment failures must be reported: {found}")


def _gitlink_roots() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-lychee-gitlinks-") as directory:
        root = Path(directory)
        (root / "README.md").write_text(
            '[pin](upstream/core) [fragment](upstream/core#section)\n'
            '[unfetched child](upstream/core/missing.md)\n', encoding="utf-8")
        found = lychee.findings(root, ["README.md"], {"upstream/core": "1" * 40})
        ensure(len(found) == 1 and "upstream/core/missing.md" in found[0],
               f"only the tracked gitlink root is checkout-independent: {found}")


def _explicit_inputs_ignore_ambient_policy() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-lychee-inputs-") as directory:
        root = Path(directory)
        (root / ".docs").mkdir()
        (root / ".docs/a.md").write_text("[broken](missing.md)\n", encoding="utf-8")
        (root / ".gitignore").write_text(".docs/\n", encoding="utf-8")
        (root / "lychee.toml").write_text('exclude = [".*"]\n', encoding="utf-8")
        found = lychee.findings(root, [".docs/a.md"], {})
        ensure(len(found) == 1 and "missing.md" in found[0],
               f"hidden/ignored indexed inputs cannot disappear behind ambient policy: {found}")
        try:
            lychee.findings(root, ["missing.md"], {})
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("a missing explicit input must refuse before dispatch")


def _structured_verdicts() -> None:
    root = Path.cwd()
    ensure(not lychee.read_result(root, 0, '{"errors":0,"error_map":{}}', ""),
           "a complete structured success must pass")
    invalid = [(0, "{}"), (0, '{"errors":1,"error_map":{}}'),
               (2, '{"errors":0,"error_map":{}}'),
               (0, '{"errors":0,"errors":0,"error_map":{}}'),
               (0, json.dumps({"errors": 1, "error_map": {"a.md": [{}]}})),
               (9, "")]
    for code, report in invalid:
        try:
            lychee.read_result(root, code, report, "stopped")
        except ValueError, TypeError:
            continue
        raise AssertionError(f"an incomplete or failed tool verdict passed: {code}, {report}")


def cases() -> list[Case]:
    return [Case("relative/reference/HTML/Unicode links and offline boundaries", _ordinary_links),
            Case("uninitialized gitlinks exempt only the tracked root", _gitlink_roots),
            Case("explicit hidden inputs ignore ambient exclusions", _explicit_inputs_ignore_ambient_policy),
            Case("tool crashes and malformed verdicts refuse", _structured_verdicts),
            *InstallerFixture(lychee, "Lychee", "lychee-{target}",
                              "lychee-{target}/{exe}").cases()]
