# SPDX-License-Identifier: Apache-2.0
"""Conservative changed-path policy shared by Host CI and publication.

Known prose needs corpus and Markdown validation. Source families select their
guest consumers; shared inputs and anything this policy does not recognize keep
the complete suites. Markdown that supplies parsed tables is an executable input.
"""

import re
import subprocess
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import TypedDict, cast

ALL_GUEST_LANES = ("model", "rtl", "proofs")
_SHA = re.compile(r"[0-9a-f]{40}")
_ROOT_PROSE = frozenset({"README.md", "AGENTS.md", "PLAN.md", "COPYRIGHT.md", "THIRD-PARTY.md"})
_EXECUTABLE_PROSE = frozenset({
    "docs/spec.md", "docs/requirements-register.md", "docs/assurance/field-bindings.md",
    "docs/implementation/placement-search.md", "rtl/synthesis-provenance.md",
    "docs/implementation/compute-feature-map.md", "docs/assurance/wire-format-inventory.md",
    "docs/assurance/crown-jewels.md", "docs/background/static-memory-research.md",
    "docs/background/math-evidence.md", "docs/assurance/differential-corpus.md",
})
# New Markdown consumers must add their executable inputs here before receiving
# the prose exemption. Directory entries reserve families of parsed contracts.
_EXECUTABLE_PREFIXES = (
    "docs/hardware/", "docs/implementation/contracts/", "docs/implementation/phase-service/",
    "docs/languages/", "docs/implementation/static-memory/", "interfaces/",
)
_FULL_REASONS = frozenset({"full override", "comparison unavailable", "empty comparison"})


class Decision(TypedDict):
    host_full: bool
    model_hooks: bool
    guest_lanes: list[str]


class Selection(Decision):
    base: str | None
    revision: str
    paths: list[str]
    reason: str


def _full() -> Decision:
    return {"host_full": True, "model_hooks": True, "guest_lanes": list(ALL_GUEST_LANES)}


def _path(value: str) -> bool:
    """Git paths are relative POSIX names, never a pathspec or a parent traversal."""
    parsed = PurePosixPath(value)
    return (bool(value) and not parsed.is_absolute() and "\\" not in value
            and "\0" not in value and parsed.as_posix() == value
            and all(part not in {".", ".."} for part in parsed.parts))


def _prose(path: str) -> bool:
    if path in _EXECUTABLE_PROSE or path.startswith(_EXECUTABLE_PREFIXES):
        return False
    if path in _ROOT_PROSE:
        return True
    if not path.endswith(".md"):
        return False
    if path.startswith(("docs/", "model/", "proofs/", "rtl/", "kernel/", "firmware/")):
        return True
    # Tool fixtures may be Markdown too. Only these documentation directories
    # have a prose exemption; a new fixture elsewhere keeps all behavioral tests.
    return PurePosixPath(path).parent.as_posix() in {"tools", "tools/ci"}


def classify(paths: Sequence[str]) -> Decision:
    if not paths:
        return _full()
    host_full, hooks = False, False
    lanes: set[str] = set()
    for path in paths:
        if not _path(path):
            return _full()
        if _prose(path):
            hooks |= path.startswith("model/")
        elif path in _EXECUTABLE_PROSE or path.startswith(_EXECUTABLE_PREFIXES):
            return _full()
        elif path.startswith("model/"):
            host_full, hooks = True, True
            lanes.update(("model", "rtl"))
        elif path.startswith("rtl/"):
            host_full = True
            lanes.add("rtl")
        elif path.startswith("proofs/"):
            host_full = True
            lanes.add("proofs")
        else:
            return _full()
    return {"host_full": host_full, "model_hooks": hooks,
            "guest_lanes": [lane for lane in ALL_GUEST_LANES if lane in lanes]}


def changed_paths(root: Path, base: str, revision: str) -> list[str]:
    """Read the complete diff, including each side of renames and deleted paths."""
    if not _SHA.fullmatch(base) or not _SHA.fullmatch(revision) or base == "0" * 40:
        raise ValueError("comparison requires full nonzero commit IDs")
    subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", base, revision],
                   capture_output=True, check=True, timeout=30)
    result = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", "-z", "--no-renames", base, revision, "--"],
        capture_output=True, check=True, timeout=30)
    paths = sorted(set(result.stdout.decode("utf-8").removesuffix("\0").split("\0")))
    if paths == [""]:
        return []
    if not all(_path(path) for path in paths):
        raise ValueError("comparison contains an unsupported path")
    return paths


def select_changes(root: Path, base: str | None, revision: str, *,
                   force_full: bool = False) -> Selection:
    """A failed comparison broadens validation instead of silently omitting gates."""
    if not _SHA.fullmatch(revision):
        raise ValueError("selection requires a full lowercase revision")
    paths: list[str] = []
    reason = "changed paths"
    normalized_base = base if base is not None and _SHA.fullmatch(base) else None
    if normalized_base is None:
        reason = "comparison unavailable"
    else:
        try:
            paths = changed_paths(root, normalized_base, revision)
            if not paths:
                reason = "empty comparison"
        except (OSError, UnicodeError, ValueError, subprocess.SubprocessError):
            reason = "comparison unavailable"
    if force_full:
        reason = "full override"
    decision = classify(paths) if reason == "changed paths" else _full()
    return {**decision, "base": normalized_base, "revision": revision,
            "paths": paths, "reason": reason}


def validate_selection(raw: object, revision: str) -> Selection:
    """Refuse malformed journals and narrower decisions than their recorded paths."""
    if not isinstance(raw, dict) or set(raw) != {
            "base", "revision", "paths", "reason", "host_full", "model_hooks", "guest_lanes"}:
        raise ValueError("invalid CI selection fields")
    record = cast("dict[str, object]", raw)
    base, paths, reason = record["base"], record["paths"], record["reason"]
    if (record["revision"] != revision or not _SHA.fullmatch(revision)
            or (base is not None and (not isinstance(base, str) or not _SHA.fullmatch(base)))
            or not isinstance(paths, list) or not all(isinstance(path, str) and _path(path) for path in paths)
            or paths != sorted(set(paths)) or not isinstance(reason, str)
            or reason not in {*_FULL_REASONS, "changed paths"}
            or type(record["host_full"]) is not bool or type(record["model_hooks"]) is not bool):
        raise ValueError("invalid CI selection identity or comparison")
    selected_paths = cast("list[str]", paths)
    if reason == "changed paths" and (base is None or not selected_paths):
        raise ValueError("changed-path selection requires a base and paths")
    decision = classify(selected_paths) if reason == "changed paths" else _full()
    if any(record[key] != value for key, value in decision.items()):
        raise ValueError("CI selection does not match its recorded changed paths")
    return cast("Selection", record)
