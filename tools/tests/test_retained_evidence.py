# SPDX-License-Identifier: Apache-2.0
"""Retained evidence copies sit at their cited paths and keep their recorded bytes.

[The retained-evidence directory](../../docs/implementation/retained-evidence/README.md)
keeps verbatim copies of native and `out/` records that tracked files cite by path. A
copy serves only while three relations hold: a tracked file cites its path, a Markdown
citation of that path links the copy, and a SHA-256 recorded beside a citation or bound
to the path in a JSON record names the copy's bytes. The live case checks all three over
the git index; the control cases show each check refusing its defect. Independently
linked, SHA-bound `manifest.json` files may bind contained indexed members. Their
identity and gzip records bind both byte extents and hashes; internal bundle links
cannot supply an external root.
"""

import gzip
import hashlib
import json
import re
import subprocess
import zlib
from collections.abc import Iterator
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import cast

from tests.harness import TOOLS, Case, ensure, sandbox_tree

EVIDENCE = "docs/implementation/retained-evidence"
# A Markdown link whose text is a code span, and the hash a note may record after it.
_LINK = re.compile(r"\[`(?P<cited>[^`]+)`\]\((?P<target>[^)\s]+)\)"
                   r"(?:\s*[,(]?\s*(?:has\s+)?SHA-?256\s+`(?P<sha>[0-9a-f]{64})`)?")
_SHA256 = re.compile(r"[0-9a-f]{64}")


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


def _manifest_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """A retained map may not conceal a member beneath a duplicate JSON key."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate manifest key {key!r}")
        result[key] = value
    return result


def _manifest_files(blob: bytes) -> dict[str, object]:
    document = json.loads(blob.decode("utf-8"), object_pairs_hook=_manifest_object)
    files = document.get("files") if isinstance(document, dict) else None
    if not isinstance(files, dict) or not files:
        raise ValueError("bundle manifest requires a nonempty files map")
    return cast("dict[str, object]", files)


def _member_path(root: Path, owner: str, path: object) -> str:
    """Portable relative names must stay beneath their manifest's own directory."""
    if not isinstance(path, str) or not path:
        raise ValueError("member path must be a nonempty relative name")
    portable = path.replace("\\", "/")
    windows, posix = PureWindowsPath(path), PurePosixPath(portable)
    if windows.drive or windows.root or posix.is_absolute() or ".." in posix.parts:
        raise ValueError(f"absolute or traversing member path {path!r}")
    manifest = (root / EVIDENCE / owner).resolve()
    target = (manifest.parent / portable).resolve()
    if target == manifest or not target.is_relative_to(manifest.parent):
        raise ValueError(f"self or escaping member path {path!r}")
    return target.relative_to((root / EVIDENCE).resolve()).as_posix()


def _identity(data: bytes, sha: object, count: object, role: str) -> None:
    if (not isinstance(sha, str) or _SHA256.fullmatch(sha) is None
            or type(count) is not int or count < 0):
        raise ValueError(f"{role} identity requires SHA-256 and a nonnegative byte count")
    if len(data) != count or hashlib.sha256(data).hexdigest() != sha:
        raise ValueError(f"{role} hash or size does not match the retained bytes")


def _member_bytes(blob: bytes, entry: dict[str, object]) -> int:
    """Check the stored bytes and, for gzip, the decoded content separately."""
    encoding = entry.get("encoding", "identity")
    if encoding not in ("identity", "gzip"):
        raise ValueError(f"unknown member encoding {encoding!r}")
    stored = encoding == "gzip" or "stored_sha256" in entry or "stored_bytes" in entry
    if stored:
        _identity(blob, entry.get("stored_sha256"), entry.get("stored_bytes"), "stored")
    content = blob
    if encoding == "gzip":
        if not blob.startswith(b"\x1f\x8b"):
            raise ValueError("gzip member lacks a gzip header")
        content = gzip.decompress(blob)
    _identity(content, entry.get("sha256"), entry.get("bytes"), "content")
    return 1 + int(stored)


def _bundles(root: Path, names: set[str], data: dict[str, bytes],
             roots: set[str]) -> tuple[list[str], set[str], int]:
    """Only independently linked, SHA-bound manifests confer member citation.

    A nested manifest is retained as bytes; it needs its own external root before
    its children count. Internal links or a cycle never create an external root.
    """
    findings: list[str] = []
    seen: set[str] = set()
    compared = 0
    for owner in sorted(name for name in names if PurePosixPath(name).name == "manifest.json"):
        if owner not in roots:
            findings.append(f"{owner}: bundle has no externally linked SHA-bound root")
        if owner not in data:
            continue
        try:
            files = _manifest_files(data[owner])
        except ValueError as error:
            findings.append(f"{owner}: invalid bundle schema ({error})")
            continue
        for key, entry in files.items():
            if not isinstance(entry, dict):
                findings.append(f"{owner}: member {key!r} is not an identity record")
                continue
            try:
                member = _member_path(root, owner, entry.get("path", key))
                blob = data.get(member) if member in names else None
                if blob is None:
                    findings.append(f"{owner}: member {key!r} names no indexed readable copy: {member}")
                    continue
                checked = _member_bytes(blob, entry)
            except (OSError, ValueError, EOFError, zlib.error) as error:
                findings.append(f"{owner}: member {key!r} is invalid ({error})")
                continue
            compared += checked
            if owner in roots:
                seen.add(_cited(member))
    return findings, seen, compared


def _findings(root: Path) -> tuple[list[str], int]:
    """Each disagreement between the copies and their citations, and the hashes compared."""
    tracked = _tracked(root)
    prefix = EVIDENCE + "/"
    names = {name[len(prefix):] for name in tracked
             if name.startswith(prefix) and name != prefix + "README.md"}
    findings: list[str] = []
    data: dict[str, bytes] = {}
    for rel in sorted(names):
        try:
            data[rel] = (root / prefix / rel).read_bytes()
        except OSError as error:
            findings.append(f"{rel}: retained copy cannot be read ({error})")
    copies = {rel: hashlib.sha256(blob).hexdigest() for rel, blob in data.items()}
    by_cited = {_cited(rel): rel for rel in names}
    evidence = (root / EVIDENCE).resolve()
    compared = 0
    for rel in copies:
        if rel.endswith(".json"):
            try:
                json.loads(data[rel].decode("utf-8"))
            except ValueError as err:
                findings.append(f"{rel}: not valid JSON ({err})")
    seen: set[str] = set()
    roots: set[str] = set()
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
                    if sha != copies.get(by_cited[path]):
                        findings.append(f"{name}: binds {path} to {sha}, "
                                        f"not its retained copy's bytes")
                    else:
                        roots.add(by_cited[path])
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
                elif match["cited"] == _cited(rel):
                    roots.add(rel)
        findings.extend(f"{name}: cites {cited} without linking its retained copy"
                        for cited in present
                        if re.search(r"(?<!\[)" + re.escape(f"`{cited}`"), text))
    bundled, members, hashes = _bundles(root, names, data, roots)
    findings += bundled
    seen |= members
    compared += hashes
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


def _bundle_tree(encoding: str = "identity", *, explicit: bool = False) -> dict[str, bytes]:
    """Both current files-map shapes, with a member cited only through the manifest."""
    payload = b'{"ok": true}\n'
    stored = gzip.compress(payload, mtime=0) if encoding == "gzip" else payload
    member = "raw/record.json.gz" if encoding == "gzip" else "record.json"
    entry: dict[str, object] = {"sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
    if explicit:
        entry.update(path=member, encoding=encoding, stored_bytes=len(stored),
                     stored_sha256=hashlib.sha256(stored).hexdigest())
    owner = "q39/bundle/manifest.json"
    manifest = json.dumps({"files": {"record" if explicit else member: entry}}).encode()
    note = (f"Bundle [`{owner}`](retained-evidence/{owner}), "
            f"SHA256 `{hashlib.sha256(manifest).hexdigest()}`.\n").encode()
    return {f"{EVIDENCE}/README.md": b"# copies\n", f"{EVIDENCE}/{owner}": manifest,
            f"{EVIDENCE}/q39/bundle/{member}": stored, "docs/implementation/log.md": note}


def _audit_bytes(files: dict[str, bytes], *, untracked: dict[str, bytes] | None = None,
                 missing: str | None = None) -> tuple[list[str], int]:
    with sandbox_tree(dict.fromkeys(files, "placeholder")) as root:
        for name, blob in (files | (untracked or {})).items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob)
        if missing is not None:
            (root / missing).unlink()
        return _findings(root)


def _replace_manifest(files: dict[str, bytes], manifest: object) -> dict[str, bytes]:
    """Keep the root citation honest so each control reaches the member reading."""
    owner = "q39/bundle/manifest.json"
    raw = manifest if isinstance(manifest, bytes) else json.dumps(manifest).encode()
    note = (f"Bundle [`{owner}`](retained-evidence/{owner}), "
            f"SHA256 `{hashlib.sha256(raw).hexdigest()}`.\n").encode()
    return files | {f"{EVIDENCE}/{owner}": raw, "docs/implementation/log.md": note}


def _bundle_controls() -> None:
    for encoding, explicit in (("identity", False), ("identity", True), ("gzip", True)):
        findings, compared = _audit_bytes(_bundle_tree(encoding, explicit=explicit))
        ensure(not findings and compared >= 2,
               f"a rooted {encoding} bundle in either current map shape must pass: {findings}")
    base = _bundle_tree(explicit=True)
    owner = f"{EVIDENCE}/q39/bundle/manifest.json"
    member = f"{EVIDENCE}/q39/bundle/record.json"
    for field, wrong, expected in (
            ("sha256", "0" * 64, "content hash or size"),
            ("sha256", "bad", "content identity"),
            ("bytes", 999, "content hash or size"),
            ("bytes", True, "content identity"),
            ("encoding", "brotli", "unknown member encoding"),
            ("stored_sha256", "0" * 64, "stored hash or size"),
            ("stored_bytes", 999, "stored hash or size"),
            ("path", "/absolute/record.json", "absolute or traversing"),
            ("path", "C:\\outside\\record.json", "absolute or traversing"),
            ("path", "C:record.json", "absolute or traversing"),
            ("path", "../record.json", "absolute or traversing"),
            ("path", "..\\record.json", "absolute or traversing"),
            ("path", "manifest.json", "self or escaping"),
            ("path", "missing.json", "no indexed readable copy")):
        manifest = json.loads(base[owner])
        manifest["files"]["record"][field] = wrong
        findings, _ = _audit_bytes(_replace_manifest(base, manifest))
        ensure(any(expected in finding for finding in findings),
               f"{field}={wrong!r} must refuse the member binding: {findings}")
    for malformed in ({}, {"files": {}}, {"files": []}, {"files": {"record": []}},
                      {"files": {"record": {"path": "record.json"}}},
                      b'{"files": {}, "files": {}}', b"\xff"):
        findings, _ = _audit_bytes(_replace_manifest(base, malformed))
        ensure(any("invalid bundle schema" in finding or "not an identity record" in finding
                   or "content identity" in finding for finding in findings),
               f"malformed bundle schema must fail: {malformed!r}, {findings}")
    for missing in (False, True):
        if missing:
            findings, _ = _audit_bytes(base, missing=member)
        else:
            indexed = {path: blob for path, blob in base.items() if path != member}
            findings, _ = _audit_bytes(indexed, untracked={member: base[member]})
        ensure(any("no indexed readable copy" in finding for finding in findings),
               f"a missing or unindexed member must fail even if bytes exist: {findings}")
    without_root = base | {"docs/implementation/log.md": b"An internal manifest is insufficient.\n"}
    findings, _ = _audit_bytes(without_root)
    ensure(any("no externally linked SHA-bound root" in finding for finding in findings)
           and any("record.json: no tracked file cites" in finding for finding in findings),
           f"an unrooted map may not confer member citation: {findings}")
    bad_root = base | {"docs/implementation/log.md": base["docs/implementation/log.md"].replace(
        hashlib.sha256(base[owner]).hexdigest().encode(), b"0" * 64)}
    findings, _ = _audit_bytes(bad_root)
    ensure(any("no externally linked SHA-bound root" in finding for finding in findings)
           and any("record.json: no tracked file cites" in finding for finding in findings),
           f"an externally linked root with the wrong hash may not confer citation: {findings}")
    for sha, agrees in ((hashlib.sha256(base[owner]).hexdigest(), True), ("0" * 64, False)):
        external = without_root | {"record.json": json.dumps({
            "path": "q39/bundle/manifest.json", "sha256": sha}).encode()}
        findings, _ = _audit_bytes(external)
        if agrees:
            ensure(not findings, f"an exact external JSON binding must root its bundle: {findings}")
        else:
            ensure(any("no externally linked SHA-bound root" in finding for finding in findings)
                   and any("record.json: no tracked file cites" in finding for finding in findings),
                   f"an external JSON binding with the wrong hash may not confer citation: {findings}")


def _gzip_bundle_controls() -> None:
    base = _bundle_tree("gzip", explicit=True)
    owner = f"{EVIDENCE}/q39/bundle/manifest.json"
    member = f"{EVIDENCE}/q39/bundle/raw/record.json.gz"
    for field, wrong, expected in (("sha256", "0" * 64, "content hash or size"),
                                   ("bytes", 999, "content hash or size"),
                                   ("stored_sha256", "0" * 64, "stored hash or size"),
                                   ("stored_bytes", 999, "stored hash or size")):
        manifest = json.loads(base[owner])
        manifest["files"]["record"][field] = wrong
        findings, _ = _audit_bytes(_replace_manifest(base, manifest))
        ensure(any(expected in finding for finding in findings),
               f"gzip {field} must bind the appropriate bytes: {findings}")
    for corrupted in (b"", b"plaintext disguised as gzip", base[member][:-6]):
        manifest = json.loads(base[owner])
        manifest["files"]["record"].update(stored_bytes=len(corrupted),
            stored_sha256=hashlib.sha256(corrupted).hexdigest())
        findings, _ = _audit_bytes(_replace_manifest(base | {member: corrupted}, manifest))
        ensure(any("member 'record' is invalid" in finding for finding in findings),
               f"gzip corruption must fail after its honest stored identity passes: {findings}")


def _nested_bundles_need_independent_roots() -> None:
    child = json.dumps({"files": {"record.bin": {"sha256": hashlib.sha256(b"child").hexdigest(),
                                                 "bytes": 5}}}).encode()
    parent = json.dumps({"files": {"child/manifest.json": {
        "sha256": hashlib.sha256(child).hexdigest(), "bytes": len(child)}}}).encode()
    owner = "q39/bundle/manifest.json"
    nested = "q39/bundle/child/manifest.json"
    files = {f"{EVIDENCE}/README.md": b"# copies\n", f"{EVIDENCE}/{owner}": parent,
             f"{EVIDENCE}/{nested}": child, f"{EVIDENCE}/q39/bundle/child/record.bin": b"child",
             "docs/implementation/log.md": (f"[`{owner}`](retained-evidence/{owner}), "
                 f"SHA256 `{hashlib.sha256(parent).hexdigest()}`.\n").encode()}
    findings, _ = _audit_bytes(files)
    ensure(any(f"{nested}: bundle has no externally linked SHA-bound root" in finding
               for finding in findings) and any("record.bin: no tracked file cites" in finding
                                               for finding in findings),
           f"a manifest member cannot bootstrap its own children: {findings}")
    files["docs/implementation/log.md"] += (f"[`{nested}`](retained-evidence/{nested}), "
        f"SHA256 `{hashlib.sha256(child).hexdigest()}`.\n").encode()
    findings, _ = _audit_bytes(files)
    ensure(not findings, f"both independently rooted manifests must pass: {findings}")
    circular = json.dumps({"files": {"../manifest.json": {"sha256": "0" * 64, "bytes": 0}}}).encode()
    files[f"{EVIDENCE}/{nested}"] = circular
    files["docs/implementation/log.md"] = b"No external roots.\n"
    findings, _ = _audit_bytes(files)
    ensure(any("absolute or traversing" in finding for finding in findings)
           and sum("no externally linked SHA-bound root" in finding for finding in findings) == 2,
           f"an internal circular bundle reference must not establish roots: {findings}")


def cases() -> list[Case]:
    return [Case("retained-copies-match-their-citations", _live),
            Case("retained-copy-defects-are-refused", _controls),
            Case("rooted-bundle-members-bind-their-bytes", _bundle_controls),
            Case("gzip-bundle-members-bind-stored-and-decoded-bytes", _gzip_bundle_controls),
            Case("nested-bundles-need-independent-roots", _nested_bundles_need_independent_roots)]
