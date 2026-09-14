# SPDX-License-Identifier: Apache-2.0
"""Fail-closed, source-bound semantic staging for the frozen scalar seam."""

import difflib
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

REGISTRY = "tools/rtl-width-transforms.json"
CORE = "upstream/cva6-cheri"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Edit:
    old: str
    new: str
    count: int


@dataclass(frozen=True)
class Source:
    path: str
    source_sha256: str
    output_sha256: str
    edits: tuple[Edit, ...]


def transform(text: str, source: Source, notice: str) -> str:
    """Validate input, every exact edit and output before publishing any source."""
    if digest(text) != source.source_sha256:
        raise ValueError(f"{source.path}: input SHA-256 disagrees with {REGISTRY}")
    for edit in source.edits:
        if not edit.old or edit.count < 1 or text.count(edit.old) != edit.count:
            raise ValueError(f"{source.path}: replacement match count disagrees with {REGISTRY}")
        text = text.replace(edit.old, edit.new)
    text = notice + text
    if digest(text) != source.output_sha256:
        raise ValueError(f"{source.path}: output SHA-256 disagrees with {REGISTRY}")
    return text


def load(root: Path) -> tuple[str, str, tuple[Source, ...]]:
    data = json.loads((root / REGISTRY).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != "vos.rtl-width-transforms/1":
        raise ValueError(f"{REGISTRY}: unsupported registry")
    pin, notice, rows = data.get("pin"), data.get("notice"), data.get("sources")
    if not isinstance(pin, str) or re.fullmatch(r"[0-9a-f]{40}", pin) is None:
        raise ValueError(f"{REGISTRY}: expected exact source pin")
    if not isinstance(notice, str) or not notice.startswith("// Modified by VerifiedOS"):
        raise ValueError(f"{REGISTRY}: missing modification notice")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{REGISTRY}: empty transform population")
    sources: list[Source] = []
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError(f"{REGISTRY}: malformed source")
        path, before, after = row.get("path"), row.get("source_sha256"), row.get("output_sha256")
        if (not isinstance(path, str) or not path.startswith("core/")
                or ".." in PurePosixPath(path).parts or "\\" in path
                or any(source.path == path for source in sources)):
            raise ValueError(f"{REGISTRY}: unsafe or duplicate source path")
        if any(not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None
               for sha in (before, after)):
            raise ValueError(f"{REGISTRY}: malformed source identity")
        edits = row.get("edits")
        if not isinstance(edits, list) or not edits:
            raise ValueError(f"{REGISTRY}: empty edits")
        parsed: list[Edit] = []
        for edit in edits:
            if not isinstance(edit, dict):
                raise TypeError(f"{REGISTRY}: malformed edit")
            old, new, count = edit.get("old"), edit.get("new"), edit.get("count")
            if (not isinstance(old, str) or not old or not isinstance(new, str)
                    or type(count) is not int or count < 1):
                raise ValueError(f"{REGISTRY}: malformed replacement")
            parsed.append(Edit(old, new, count))
        sources.append(Source(path, str(before), str(after), tuple(parsed)))
    return pin, notice, tuple(sources)


def stage(root: Path, lines: tuple[str, ...], work: Path) -> tuple[str, ...]:
    pin, notice, sources = load(root)
    found = subprocess.run(["git", "-C", str(root / CORE), "rev-parse", "HEAD"],
                           capture_output=True, text=True, check=True).stdout.strip()
    if found != pin:
        raise ValueError(f"{CORE}: selected pin {found} disagrees with {pin}")
    staged = work / "scalar-width"
    pending: list[tuple[Path, str, str, Source]] = []
    for source in sources:
        original = root / CORE / source.path
        if sum(Path(line) == original for line in lines) != 1:
            raise ValueError(f"{source.path}: expected exactly one curated file-list member")
        text = original.read_text(encoding="utf-8")
        pending.append((original, text, transform(text, source, notice), source))
    # Every row is validated before writing; a stale row cannot leave a partial list.
    replacements: dict[Path, Path] = {}
    receipt = []
    for original, text, output, source in pending:
        destination = staged / source.path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(output, encoding="utf-8", newline="")
        difference = "".join(difflib.unified_diff(text.splitlines(keepends=True),
                                                output.splitlines(keepends=True),
                                                fromfile=str(original), tofile=str(destination)))
        destination.with_suffix(".diff").write_text(difference, encoding="utf-8", newline="")
        replacements[original] = destination
        receipt.append({"source": str(original), "staged": str(destination),
                        "source_sha256": source.source_sha256,
                        "output_sha256": source.output_sha256,
                        "edits": len(source.edits)})
    (staged / "receipt.json").write_text(json.dumps({"pin": pin, "sources": receipt}, indent=2)
                                       + "\n", encoding="utf-8", newline="")
    return tuple(str(replacements.get(Path(line), line)) for line in lines)
