# SPDX-License-Identifier: Apache-2.0
"""Retained evidence copies sit at their cited paths and keep their recorded bytes.

[The retained-evidence directory](../../docs/implementation/retained-evidence/README.md)
keeps verbatim copies of native and `out/` records that tracked files cite by path. A
copy serves only while three relations hold: a tracked file cites its path, a Markdown
citation of that path links the copy, and a SHA-256 recorded beside a citation or bound
to the path in a JSON record names the copy's bytes. The live case checks all three over
the git index; the control case shows each check refusing its defect.
"""

import hashlib
import json
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path

from tests.harness import TOOLS, Case, ensure, sandbox_tree

EVIDENCE = "docs/implementation/retained-evidence"
# A Markdown link whose text is a code span, and the hash a note may record after it.
_LINK = re.compile(r"\[`(?P<cited>[^`]+)`\]\((?P<target>[^)\s]+)\)"
                   r"(?:\s*[,(]?\s*(?:has\s+)?SHA-?256\s+`(?P<sha>[0-9a-f]{64})`)?")


def _cited(rel: str) -> str:
    """The path a citation names for the copy at `rel`; guest paths are absolute."""
    return "/" + rel if rel.startswith("root/") else rel


def _tracked(root: Path) -> list[str]:
    done = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True,
                          check=True, timeout=60)
    return [name for name in done.stdout.decode("utf-8").split("\0") if name]


def _bindings(value: object) -> Iterator[tuple[str, str]]:
    """Every JSON object that binds a path to a SHA-256."""
    if isinstance(value, dict):
        path, sha = value.get("path"), value.get("sha256")
        if isinstance(path, str) and isinstance(sha, str):
            yield path, sha
        for item in value.values():
            yield from _bindings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _bindings(item)


def _findings(root: Path) -> tuple[list[str], int]:
    """Each disagreement between the copies and their citations, and the hashes compared."""
    tracked = _tracked(root)
    prefix = EVIDENCE + "/"
    copies = {name[len(prefix):]: hashlib.sha256((root / name).read_bytes()).hexdigest()
              for name in tracked if name.startswith(prefix) and name != prefix + "README.md"}
    by_cited = {_cited(rel): rel for rel in copies}
    evidence = (root / EVIDENCE).resolve()
    findings: list[str] = []
    compared = 0
    for rel in copies:
        if rel.endswith(".json"):
            try:
                json.loads((root / prefix / rel).read_text(encoding="utf-8"))
            except ValueError as err:
                findings.append(f"{rel}: not valid JSON ({err})")
    seen: set[str] = set()
    for name in tracked:
        if name.startswith(prefix) or not name.endswith((".md", ".json")):
            continue
        text = (root / name).read_text(encoding="utf-8", errors="replace")
        present = [cited for cited in by_cited if cited in text]
        if not present:
            continue
        seen.update(present)
        if name.endswith(".json"):
            for path, sha in _bindings(json.loads(text)):
                if path in by_cited:
                    compared += 1
                    if sha != copies[by_cited[path]]:
                        findings.append(f"{name}: binds {path} to {sha}, "
                                        f"not its retained copy's bytes")
            continue
        for match in _LINK.finditer(text):
            target = ((root / name).parent / match["target"]).resolve()
            if not target.is_relative_to(evidence):
                continue
            rel = target.relative_to(evidence).as_posix()
            if rel not in copies:
                findings.append(f"{name}: links {match['target']}, which is not a retained copy")
                continue
            if match["cited"] != _cited(rel):
                findings.append(f"{name}: link text {match['cited']} does not name the "
                                f"path {_cited(rel)} its copy retains")
            if match["sha"]:
                compared += 1
                if match["sha"] != copies[rel]:
                    findings.append(f"{name}: records SHA256 {match['sha']} beside "
                                    f"{_cited(rel)}, not its retained copy's bytes")
        findings.extend(f"{name}: cites {cited} without linking its retained copy"
                        for cited in present
                        if re.search(r"(?<!\[)" + re.escape(f"`{cited}`"), text))
    findings.extend(f"{by_cited[cited]}: no tracked file cites {cited}"
                    for cited in sorted(set(by_cited) - seen))
    return findings, compared


def _live() -> None:
    findings, compared = _findings(TOOLS.parent)
    ensure(not findings, "retained evidence disagrees with its citations:\n  "
           + "\n  ".join(findings))
    ensure(compared > 0, "no recorded hash was compared, so the hash check decided nothing")


def _controls() -> None:
    report = '{"ok": true}\n'
    sha = hashlib.sha256(report.encode()).hexdigest()
    other = "0" * 64
    note = ("Receipt [`/root/build/a/report.json`](retained-evidence/root/build/a/report.json),"
            f"\n  SHA256 `{sha}`, and [`out/b.json`](retained-evidence/out/b.json).\n")
    base = {
        f"{EVIDENCE}/README.md": "# copies\n",
        f"{EVIDENCE}/root/build/a/report.json": report,
        f"{EVIDENCE}/out/b.json": "{}\n",
        "docs/implementation/log.md": note,
        "record.json": json.dumps({"x": {"path": "/root/build/a/report.json", "sha256": sha}}),
    }
    with sandbox_tree(base) as root:
        findings, compared = _findings(root)
        ensure(findings == [] and compared == 2,
               f"the agreeing control must pass with two comparisons: {findings}, {compared}")
    defects = {
        "recorded hash": {"docs/implementation/log.md": note.replace(sha, other)},
        "bound hash": {"record.json": json.dumps({"path": "/root/build/a/report.json",
                                                  "sha256": other})},
        "unlinked citation": {"docs/other.md": "See `out/b.json`.\n"},
        "link text": {"docs/implementation/log.md":
                      note.replace("[`out/b.json`]", "[`out/c.json`]")},
        "uncited copy": {f"{EVIDENCE}/out/c.json": "{}\n"},
        "invalid copy": {f"{EVIDENCE}/out/b.json": "{\n"},
    }
    for label, change in defects.items():
        with sandbox_tree(base | change) as root:
            findings, _ = _findings(root)
            ensure(len(findings) == 1, f"the {label} defect must yield one finding: {findings}")


def cases() -> list[Case]:
    return [Case("retained-copies-match-their-citations", _live),
            Case("retained-copy-defects-are-refused", _controls)]
