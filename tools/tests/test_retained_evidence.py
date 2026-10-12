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
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from vos import receipts, retained_evidence
from vos.cli import retain
from vos.retained_evidence import EVIDENCE
from vos.retained_evidence import findings as _findings


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
        "invalid citation record": {"record.json": '{"path": "/root/build/a/report.json",'},
        "unlinked citation": {"docs/other.md": "See `out/b.json`.\n"},
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


def _descriptive_citations() -> None:
    base = _bundle_tree(explicit=True)
    note = "docs/implementation/log.md"
    owner = "q39/bundle/manifest.json"
    readable = base[note].replace(f"[`{owner}`]".encode(), b"[Hosted compiler results]")
    findings, compared = _audit_bytes(base | {note: readable})
    ensure(not findings and compared >= 2,
           f"a descriptive label must retain independently checked target and hash: {findings}")
    for text, expected in (
            (readable.replace(hashlib.sha256(base[f"{EVIDENCE}/{owner}"]).hexdigest().encode(),
                              b"0" * 64), "no externally linked SHA-bound root"),
            (readable.replace(b"retained-evidence/q39/bundle/manifest.json", b"../../outside.json"),
             "no externally linked SHA-bound root")):
        findings, _ = _audit_bytes(base | {note: text})
        ensure(any(expected in finding for finding in findings),
               f"readable labels must not bypass a root's target or hash: {findings}")
    manifest = json.loads(base[f"{EVIDENCE}/{owner}"])
    manifest["files"]["alias"] = manifest["files"]["record"]
    findings, _ = _audit_bytes(_replace_manifest(base, manifest))
    ensure(any("colliding member path" in finding for finding in findings),
           f"different map keys may not conceal the same member target: {findings}")


def _malformed_citation_record() -> None:
    owner = "q39/bundle/manifest.json"
    files = _bundle_tree(explicit=True) | {
        "docs/implementation/log.md": b"No external citation.\n",
        "record.json": f'{{"path": "{owner}", "sha256": '.encode()}
    findings, _ = _audit_bytes(files)
    ensure(any("record.json: not valid JSON" in finding for finding in findings),
           f"a malformed external citation must report a finding: {findings}")
    ensure(any(f"{owner}: bundle has no externally linked SHA-bound root" in finding
               for finding in findings)
           and any(f"{owner}: no tracked file cites" in finding for finding in findings),
           f"malformed JSON cannot cite or root its named bundle: {findings}")


def _produced_bundle() -> None:
    note = "docs/implementation/log.md"
    payload = b'{"observed": true}\n'
    compressed = gzip.compress(b"compile log\n", mtime=0)
    with sandbox_tree({note: "Owning note stays unchanged.\n", "raw/source.json": "{}\n",
                       "raw/source.gz": "placeholder"}) as root:
        source = root / "raw/source.json"
        source.write_bytes(payload)
        (root / "raw/source.gz").write_bytes(compressed)
        index = receipts.digest(root / ".git/index")
        result = retained_evidence.produce(root, "q40/bundle space", [
            retained_evidence.Member(source, "record data.json"),
            retained_evidence.Member(root / "raw/source.gz", "logs/compile.gz", "gzip")],
            note=Path(note), label="Hosted compiler results")
        ensure((root / note).read_text() == "Owning note stays unchanged.\n"
               and receipts.digest(root / ".git/index") == index,
               "producing a bundle must edit neither its note nor the Git index")
        ensure(result.sha256 == receipts.digest(result.manifest)
               and "[Hosted compiler results]" in result.citation
               and "bundle%20space" in result.citation,
               "the generated citation must identify the published manifest relative to its note")
        files = {f"{EVIDENCE}/README.md": b"# copies\n", note: result.citation.encode()}
        files.update({path.relative_to(root).as_posix(): path.read_bytes()
                      for path in result.manifest.parent.rglob("*") if path.is_file()})
        findings, compared = _audit_bytes(files)
        ensure(not findings and compared == 4,
               f"produced identity/gzip files must satisfy the indexed retention relation: {findings}")
        copied = f"{EVIDENCE}/q40/bundle space/record data.json"
        ensure(files[copied] == payload
               and files[f"{EVIDENCE}/q40/bundle space/logs/compile.gz"] == compressed,
               "the producer must preserve both plain and compressed source bytes verbatim")
        findings, _ = _audit_bytes(files | {copied: b'{"observed": false}\n'})
        ensure(any("content hash or size" in finding for finding in findings),
               f"later changed retained bytes must fail their generated identity: {findings}")


def _producer_refusals() -> None:
    with sandbox_tree({"source.txt": "observed", "docs/note.md": "note"}) as root:
        source = root / "source.txt"
        base = root / EVIDENCE
        member = retained_evidence.Member(source, "record.txt")
        for name in ("../escape", "/absolute", "C:/outside", "a\\b", "a//b", "a/./b",
                     "%SystemDrive%/outside", "CON", "a."):
            try:
                retained_evidence.produce(root, name, [member], note=Path("docs/note.md"))
            except ValueError:
                pass
            else:
                raise AssertionError(f"invalid bundle name {name!r} must be refused")
        for names in (("same.txt", "same.txt"), ("same.txt", "SAME.txt"),
                      ("record.txt", "record.txt/child"), ("Folder/a", "folder/b"),
                      ("../escape",), ("manifest.json",), ("child/manifest.json",),
                      ("a//b",), ("C:record",), ("a:stream",), ("NUL.txt",)):
            selected = [retained_evidence.Member(source, name) for name in names]
            try:
                retained_evidence.produce(root, "bundle", selected, note=Path("docs/note.md"))
            except ValueError:
                pass
            else:
                raise AssertionError(f"ambiguous or escaping members {names!r} must be refused")
            ensure(not (base / "bundle").exists(), "a refused selection must publish no bundle")
        (base / "existing").mkdir(parents=True)
        for name in ("existing", "EXISTING"):
            try:
                retained_evidence.produce(root, name, [member], note=Path("docs/note.md"))
            except (FileExistsError, ValueError):
                pass
            else:
                raise AssertionError("an existing empty destination or casing alias must be refused")
        with patch.object(Path, "is_symlink", side_effect=lambda: True):
            try:
                retained_evidence.produce(root, "linked", [member], note=Path("docs/note.md"))
            except ValueError as error:
                ensure("symlink" in str(error), "a symlink must be refused before resolving it")
            else:
                raise AssertionError("a linked root or parent must be refused")
        for encoding in ("gzip", "brotli"):
            try:
                retained_evidence.produce(root, "bad-encoding", [
                    retained_evidence.Member(source, "record", encoding)], note=Path("docs/note.md"))
            except (ValueError, OSError):
                pass
            else:
                raise AssertionError(f"an invalid {encoding} input must be refused")
        ensure(not (base / "bad-encoding").exists(), "invalid gzip must publish no destination")


def _producer_interruption_and_collision() -> None:
    with sandbox_tree({"source.txt": "observed", "docs/note.md": "note"}) as root:
        member = retained_evidence.Member(root / "source.txt", "record.txt")
        target = root / EVIDENCE / "bundle"
        with patch("vos.retained_evidence.receipts.write", side_effect=KeyboardInterrupt):
            try:
                retained_evidence.produce(root, "bundle", [member], note=Path("docs/note.md"))
            except KeyboardInterrupt:
                pass
            else:
                raise AssertionError("an interrupted manifest write must propagate")
        ensure(not target.exists() and not list(target.parent.glob(".retain-*")),
               "interrupted production must leave no published or partial bundle")
        write = receipts.write

        def collide(path: Path, payload: object) -> None:
            write(path, payload)
            target.mkdir()

        with patch("vos.retained_evidence.receipts.write", side_effect=collide):
            try:
                retained_evidence.produce(root, "bundle", [member], note=Path("docs/note.md"))
            except FileExistsError:
                pass
            else:
                raise AssertionError("a destination created during copying must not be overwritten")
        ensure(target.is_dir() and not list(target.iterdir())
               and not list(target.parent.glob(".retain-*")),
               "publication collision must preserve the other destination and remove private staging")


def _producer_source_symlink() -> None:
    with sandbox_tree({"source.txt": "observed", "docs/note.md": "note"}) as root:
        source = root / "linked.txt"
        source.symlink_to(root / "source.txt")
        try:
            retained_evidence.produce(root, "bundle", [retained_evidence.Member(source, "record")],
                                     note=Path("docs/note.md"))
        except ValueError as error:
            ensure("symlink" in str(error), "source symlinks must be refused")
        else:
            raise AssertionError("a source symlink must not be followed")


def _retain_command() -> None:
    with sandbox_tree({"source.txt": "observed", "docs/note.md": "note"}) as root:
        for argv, expected in ((["--file", "record.txt=source.txt"], 0),
                               (["--file", "missing-separator"], 1)):
            output = StringIO()
            with patch("vos.cli.retain.find_root", return_value=root), redirect_stdout(output):
                status = retain.main(["--bundle", "command", "--note", "docs/note.md",
                                      "--label", "Hosted run logs", *argv])
            ensure(status == expected, f"CLI selection must return {expected}: {output.getvalue()}")
            if status == 0:
                ensure("[Hosted run logs](implementation/retained-evidence/command/manifest.json)"
                       in output.getvalue(), "CLI citation must be relative to the requested note")


def cases() -> list[Case]:
    return [Case("retained-copies-match-their-citations", _live),
            Case("retained-copy-defects-are-refused", _controls),
            Case("rooted-bundle-members-bind-their-bytes", _bundle_controls),
            Case("gzip-bundle-members-bind-stored-and-decoded-bytes", _gzip_bundle_controls),
            Case("nested-bundles-need-independent-roots", _nested_bundles_need_independent_roots),
            Case("descriptive-labels-keep-target-and-hash-checks", _descriptive_citations),
            Case("malformed-external-json-cannot-cite-or-root-bundles", _malformed_citation_record),
            Case("produced-bundles-bind-verbatim-stored-and-decoded-bytes", _produced_bundle),
            Case("producer-refuses-ambiguous-escaping-and-existing-paths", _producer_refusals),
            Case("interruption-and-publication-collision-preserve-destination", _producer_interruption_and_collision),
            Case("producer-refuses-source-symlinks", _producer_source_symlink, lane="guest"),
            Case("retain-command-prepares-a-readable-citation", _retain_command)]
