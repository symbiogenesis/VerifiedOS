# SPDX-License-Identifier: Apache-2.0
"""Review identities remain authored while generated prose and owners are checked."""

import copy
import json
from typing import cast

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from vos import corpus, devtools


def _data() -> dict[str, object]:
    return {"schema": 2, "reviews": [{"id": "demo", "tool": "Demo", "subject": "release",
                                      "reviewed": ["1.2.3"], "owners": [
                                          {"kind": "uv", "path": "tools/uv.lock", "key": "demo"}]}],
            "rows": [{"id": "Demo", "tool": "Demo", "license": "MIT",
                      "standing": "Reviewed ${demo_0}, licence evidence stays authored.",
                      "reviews": ["demo"]}],
            "template": ["", "${development_tools_table}", "", ""]}


def _files(data: dict[str, object] | None = None) -> dict[str, str]:
    selected = _data() if data is None else data
    body = "\n".join(cast("list[str]", selected["template"]))
    body = body.replace("${development_tools_table}", "| Tool | License | Standing |\n"
                        "| --- | --- | --- |\n"
                        "| Demo | MIT | Reviewed 1.2.3, licence evidence stays authored. |")
    return {devtools.DATA: json.dumps(selected),
            devtools.SCHEMA: (TOOLS / "development-tools.schema.json").read_text(encoding="utf-8"),
            devtools.RECORD: ("# Licences\n\n" + devtools.HEADING + "\n" + devtools.BEGIN + "\n"
                             + body + devtools.END + "\n#### Other\n\nUntouched 9.9.9.\n"),
            "tools/uv.lock": '[[package]]\nname = "demo"\nversion = "1.2.3"\n',
            devtools.HOOK_CONFIG: "repos: []\n", devtools.HOOK_CONSTRAINTS: "# no pin\n",
            devtools.HOOK_BUILD_CONSTRAINTS: "# no pin\n"}


def _inspect(files: dict[str, str]) -> tuple[str | None, list[str]]:
    with sandbox_tree(files) as root:
        return devtools.inspect(root, frozenset(files), files.get(devtools.RECORD, ""))


def _identity_and_generated_bytes_are_independent() -> None:
    files = _files()
    expected, faults = _inspect(files)
    ensure(expected == files[devtools.RECORD] and not faults, f"review agreement: {faults!r}")
    moved = files[devtools.RECORD].replace("Reviewed 1.2.3", "Reviewed 2.0.0")
    expected, faults = _inspect({**files, devtools.RECORD: moved})
    ensure(expected == files[devtools.RECORD] and not faults,
           "a corrupt generated view is reproducible without editing the review")
    expected, faults = _inspect({**files, "tools/uv.lock": files["tools/uv.lock"].replace(
        '"1.2.3"', '"2.0.0"')})
    ensure(expected == files[devtools.RECORD] and len(faults) == 1
           and "reviewed 1.2.3, owners fix 2.0.0" in faults[0],
           f"a new dependency cannot manufacture a reading: {faults!r}")
    data = _data()
    reviews = cast("list[dict[str, object]]", data["reviews"])
    reviews[0]["reviewed"] = ["2.0.0"]
    _expected, faults = _inspect({**files, devtools.DATA: json.dumps(data)})
    ensure(len(faults) == 1 and "reviewed 2.0.0, owners fix 1.2.3" in faults[0],
           f"a moved review cannot pass over the installed edition: {faults!r}")


def _shape_and_template_membership_fail_closed() -> None:
    base = _data()
    bad: list[dict[str, object]] = [{**base, "schema": 3}, {**base, "reviews": []},
                                  {**base, "unknown": True}]
    for field, value in (("owners", []), ("reviewed", []), ("tool", ""),
                         ("reviewed", ["1.2.3", "1.2.3"])):
        changed = copy.deepcopy(base)
        cast("list[dict[str, object]]", changed["reviews"])[0][field] = value
        bad.append(changed)
    duplicate = copy.deepcopy(base)
    cast("list[object]", duplicate["reviews"]).append(
        cast("list[object]", duplicate["reviews"])[0])
    bad.append(duplicate)
    bad.extend({**base, "template": template} for template in (
        ["${unknown}"], ["nothing reviewed"], ["${demo_0"], ["${demo_1}"]))
    for data in bad:
        expected, faults = _inspect(_files(data))
        ensure(expected is None and bool(faults), f"malformed review/template passed: {data!r}")
    files = _files()
    duplicate_key = files[devtools.DATA].replace('"schema": 2', '"schema": 2, "schema": 2')
    expected, faults = _inspect({**files, devtools.DATA: duplicate_key})
    ensure(expected is None and bool(faults) and "duplicate JSON key" in faults[0],
           "duplicate source fields are refused before validation")
    expected, faults = _inspect({**files, devtools.SCHEMA: '{"type":"not-a-type"}'})
    ensure(expected is None and bool(faults), "an unreadable schema cannot pass")


def _markers_and_missing_sources_fail_closed() -> None:
    files = _files()
    for absent in (devtools.DATA, devtools.SCHEMA, devtools.RECORD, "tools/uv.lock",
                   devtools.HOOK_CONFIG, devtools.HOOK_CONSTRAINTS,
                   devtools.HOOK_BUILD_CONSTRAINTS):
        _expected, faults = _inspect({path: text for path, text in files.items() if path != absent})
        ensure(bool(faults), f"a missing owner or source passed: {absent}")
    record = files[devtools.RECORD]
    for broken in (record.replace(devtools.BEGIN, "missing"),
                   record.replace(devtools.END, "missing"),
                   record + devtools.BEGIN + "\n", record + devtools.END + "\n",
                   record.replace(devtools.HEADING, "### Elsewhere")):
        expected, faults = _inspect({**files, devtools.RECORD: broken})
        ensure(expected is None and bool(faults), "ambiguous generation boundaries must refuse")


def _owner_readers_cover_every_supported_identity() -> None:
    commit = "a" * 40
    files = {"tools/uv.lock": '[[package]]\nname = "demo"\nversion = "1.2.3"\n',
             "tools/pyproject.toml": '[project]\nrequires-python = ">=3.14,<3.15"\n'
                                       '[tool.uv]\nrequired-version = "==1.2.3"\n',
             "tools/opam/x.lock": 'installed: ["demo.1.2.3"]\n'
                                  f'package "demo" {{\nurl {{ src: "git+x#{commit}" }}\n}}\n',
             "tools/opam/y.lock": 'installed: ["demo.1.2.3"]\n',
             "constant.py": 'VERSION = "1.2.3"\n', "constant.sh": 'version=1.2.3\n',
             "pins.txt": 'demo==1.2.3\n',
             devtools.HOOK_CONFIG: 'repos:\n  - repo: https://github.com/example/hooks\n'
                                  f'    rev: {commit} # frozen: v1.2.3\n'}
    rows = [("uv", "tools/uv.lock", "demo", "1.2.3"),
            ("uv-required", "tools/pyproject.toml", "tool.uv.required-version", "1.2.3"),
            ("python", "tools/pyproject.toml", "project.requires-python", "3.14"),
            ("opam", "tools/opam/x.lock", "demo", "1.2.3"),
            ("opam-pin", "tools/opam/x.lock", "demo", commit),
            ("opam-every", "tools/opam/", "demo", "1.2.3"),
            ("opam-any", "tools/opam/", "demo", "1.2.3"),
            ("assign", "constant.py", "VERSION", "1.2.3"),
            ("shell", "constant.sh", "version", "1.2.3"),
            ("pip", "pins.txt", "demo", "1.2.3"),
            ("pre-commit", devtools.HOOK_CONFIG, "https://github.com/example/hooks", "1.2.3"),
            ("pre-commit-rev", devtools.HOOK_CONFIG, "https://github.com/example/hooks", commit)]
    with sandbox_tree(files) as root:
        reader = devtools.Owners(root, frozenset(files))
        for kind, path, key, expected in rows:
            ensure(reader.releases(devtools.Owner(kind, path, key)) == {expected},
                   f"the {kind} owner lost its identity")
    # Every owner must still refuse an absent indexed source instead of assuming agreement.
    with sandbox_tree({}) as root:
        for kind, path, key, _expected in rows:
            reader = devtools.Owners(root, frozenset())
            try:
                reader.releases(devtools.Owner(kind, path, key))
            except devtools.OwnerError:
                ensure(bool(reader.faults), "an owner refusal must retain its diagnostic")
            else:
                raise AssertionError(f"missing {kind} source passed")


def _hook_and_pip_inventory_still_require_reviews() -> None:
    files = _files()
    for extra in ("repos:\n  - repo: local\n", "repos:\n  - repo: https://example.invalid/hooks\n"
                  + "    rev: " + "b" * 40 + " # frozen: v1.0.0\n",
                  "repos:\n  - {repo: unreviewed, rev: v1}\n"):
        _expected, faults = _inspect({**files, devtools.HOOK_CONFIG: extra})
        ensure(bool(faults), f"an unreviewed hook route passed: {extra!r}")
    for pin in ("unreviewed==1.0.0\n", "demo>=1.0\n", "-r more.txt\n",
                'demo==1.2.3 \\\n ; sys_platform == "never"\n'):
        _expected, faults = _inspect({**files, devtools.HOOK_CONSTRAINTS: pin})
        ensure(bool(faults), f"a pin without a reviewed owner passed: {pin!r}")


def _view_preserves_unrelated_document_bytes() -> None:
    before = "outside\r\n" + devtools.HEADING + "\n" + devtools.BEGIN + "\n"
    after = devtools.END + "\nother\r\n"
    ensure(devtools.view(before + "old\n" + after, "new\n") == before + "new\n" + after,
           "generation may replace only its marked body")


def _rows_require_explicit_owners_or_dispositions() -> None:
    base = _data()
    damaged: list[dict[str, object]] = [
        {**base, "template": ["", extra, "${development_tools_table}", ""]}
        for extra in ("| Rogue | MIT | Unreviewed 9.9.9. |", "  | Rogue | MIT | Unreviewed. |",
                      "prefix ${development_tools_table}")]
    for key, value in (("reviews", []), ("reviews", ["unreviewed"]),
                       ("standing", "Unreviewed 9.9.9."),
                       ("tool", "Demo\n| Rogue | MIT | Unreviewed. |"),
                       ("license", "MIT | BSD-3-Clause"),
                       ("disposition", "A second conflicting treatment.")):
        changed = copy.deepcopy(base)
        cast("list[dict[str, object]]", changed["rows"])[0][key] = value
        damaged.append(changed)
    for key in ("reviews", "id", "license", "standing"):
        changed = copy.deepcopy(base)
        del cast("list[dict[str, object]]", changed["rows"])[0][key]
        damaged.append(changed)
    changed = copy.deepcopy(base)
    rows = cast("list[dict[str, object]]", changed["rows"])
    rows.append(copy.deepcopy(rows[0]))
    damaged.append(changed)
    changed = copy.deepcopy(base)
    cast("list[dict[str, object]]", changed["rows"]).append(
        {"id": "Rogue", "tool": "Rogue", "license": "MIT", "standing": "Unreviewed 9.9.9."})
    damaged.append(changed)
    for data in damaged:
        expected, faults = _inspect(_files(data))
        ensure(expected is None and bool(faults), f"unowned or malformed table input passed: {data!r}")
    declared = copy.deepcopy(base)
    cast("list[dict[str, object]]", declared["rows"]).append(
        {"id": "Measured", "tool": "Measured", "license": "MIT", "standing": "Measured at 9.9.9.",
         "disposition": "Historical measurement; no current dependency pin is claimed."})
    expected, faults = _inspect(_files(declared))
    ensure(not faults and expected is not None and "| Measured | MIT | Measured at 9.9.9. |" in expected,
           f"an explicit existing-style disposition remains allowed: {faults!r}")


def _fixed_owner_descriptors_cannot_name_ignored_fields() -> None:
    files = {"tools/opam/x.lock": 'installed: ["demo.1.2.3"]\n',
             "tools/pyproject.toml": '[tool.uv]\nrequired-version = "==1.2.3"\n'}
    with sandbox_tree(files) as root:
        for owner in (devtools.Owner("opam-any", "elsewhere/", "demo"),
                      devtools.Owner("opam-every", "tools/opam/unread/", "demo"),
                      devtools.Owner("uv-required", "tools/pyproject.toml", "ignored.field")):
            reader = devtools.Owners(root, frozenset(files))
            try:
                reader.releases(owner)
            except devtools.OwnerError:
                ensure(bool(reader.faults), "invalid owner descriptors must retain a refusal")
            else:
                raise AssertionError(f"an ignored owner path or key was accepted: {owner!r}")


def _shipped_review_view_and_owners_agree() -> None:
    root = TOOLS.parent
    text = (root / devtools.RECORD).read_text(encoding="utf-8")
    expected, faults = devtools.inspect(root, frozenset(corpus.read_index(root).files), text)
    ensure(expected == text and not faults,
           f"the structured migration must preserve all current review evidence: {faults!r}")


def cases() -> list[Case]:
    return [Case("identity-and-generated-bytes-are-independent",
                 _identity_and_generated_bytes_are_independent),
            Case("shape-and-template-membership-fail-closed", _shape_and_template_membership_fail_closed),
            Case("markers-and-missing-sources-fail-closed", _markers_and_missing_sources_fail_closed),
            Case("owner-readers-cover-every-supported-identity", _owner_readers_cover_every_supported_identity),
            Case("hook-and-pip-inventory-still-require-reviews", _hook_and_pip_inventory_still_require_reviews),
            Case("view-preserves-unrelated-document-bytes", _view_preserves_unrelated_document_bytes),
            Case("rows-require-explicit-owners-or-dispositions", _rows_require_explicit_owners_or_dispositions),
            Case("fixed-owner-descriptors-cannot-name-ignored-fields",
                 _fixed_owner_descriptors_cannot_name_ignored_fields),
            Case("shipped-review-view-and-owners-agree", _shipped_review_view_and_owners_agree)]
