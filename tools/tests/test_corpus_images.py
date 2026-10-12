# SPDX-License-Identifier: Apache-2.0
"""Extensions preserve reviewed source and image bytes; checks never rebaseline."""

import json
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import corpus_images
from vos.cli import corpus_images as cli


def _fixture(root: Path, names: tuple[str, ...] = ("first",)) -> None:
    directory = root / "corpus"
    directory.mkdir(exist_ok=True)
    for name in names:
        path = directory / f"{name}.s"
        if not path.exists():
            path.write_text(".text\n_start:\naddi t0, t0, 1\necall\n", encoding="utf-8", newline="\n")
    (directory / "manifest.json").write_text(json.dumps(
        {"version": 1, "trace_schema": 1,
         "members": [{"name": name, "source": f"{name}.s"} for name in names]}), encoding="utf-8")


def _baseline(root: Path) -> bytes:
    rows, _, _ = corpus_images.capture(root)
    corpus_images.publish(root / corpus_images.BASELINE, rows, None)
    return (root / corpus_images.BASELINE).read_bytes()


def _extension() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        _fixture(root)
        _baseline(root)
        previous = corpus_images.read(root / corpus_images.BASELINE)
        _fixture(root, ("first", "second"))
        before = (root / corpus_images.BASELINE).read_bytes()
        ensure(any("new member" in fault for fault in corpus_images.check(root)), "addition silently accepted")
        ensure((root / corpus_images.BASELINE).read_bytes() == before, "check rewrote the baseline")
        ensure(corpus_images.extend(root) == 1, "new member not recorded")
        reviewed = corpus_images.read(root / corpus_images.BASELINE)
        ensure(reviewed[:1] == previous and len(reviewed) == 2, "extension changed an old member")
        ensure(not corpus_images.check(root), "extended corpus refused")
        before = (root / corpus_images.BASELINE).read_bytes()
        ensure(corpus_images.extend(root) == 0, "idempotent extension claimed an addition")
        ensure((root / corpus_images.BASELINE).read_bytes() == before, "empty extension rewrote evidence")
        with patch.object(cli, "find_root", return_value=root):
            ensure(cli.main(["check"]) == 0, "registered host checker refused fixture")


def _old_source_and_removal() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        _fixture(root)
        before = _baseline(root)
        source = root / "corpus/first.s"
        original = source.read_bytes()
        source.write_bytes(original + b"# a source-only change\n")
        for operation in (corpus_images.check, corpus_images.extend):
            try:
                result = operation(root)
            except ValueError as exc:
                ensure("source_sha256" in str(exc), f"wrong source refusal: {exc}")
            else:
                ensure(isinstance(result, list) and any("source_sha256" in fault for fault in result),
                       "changed old source was rebaselined")
        ensure((root / corpus_images.BASELINE).read_bytes() == before, "refused extension changed baseline")
        source.write_bytes(original)
        _fixture(root, ("second",))
        try:
            corpus_images.extend(root)
        except ValueError as exc:
            ensure("removed" in str(exc), f"wrong removal refusal: {exc}")
        else:
            raise AssertionError("removed old member accepted")
        ensure((root / corpus_images.BASELINE).read_bytes() == before, "removal rewrote evidence")


def _changed_encoder() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        _fixture(root)
        before = _baseline(root)
        assemble = corpus_images.asm.assemble_file

        def changed(source: Path, target: Path) -> int:
            result = assemble(source, target)
            image = bytearray(target.read_bytes())
            image[-1] ^= 1
            target.write_bytes(image)
            return result

        with patch.object(corpus_images.asm, "assemble_file", side_effect=changed):
            ensure(any("image_sha256" in fault for fault in corpus_images.check(root)), "encoder drift invisible")
            try:
                corpus_images.extend(root)
            except ValueError as exc:
                ensure("image_sha256" in str(exc), f"wrong encoding refusal: {exc}")
            else:
                raise AssertionError("changed encoder rebaselined")
        ensure((root / corpus_images.BASELINE).read_bytes() == before, "encoding drift rewrote baseline")


def _migration_and_shapes() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        _fixture(root)
        try:
            corpus_images.migrate(root)
        except ValueError as exc:
            ensure("legacy aggregate mismatch" in str(exc), f"wrong migration refusal: {exc}")
        else:
            raise AssertionError("migration accepted unreproduced legacy aggregate")
        ensure(not (root / corpus_images.BASELINE).exists(), "failed migration published a baseline")
        _baseline(root)
        try:
            corpus_images.migrate(root)
        except ValueError as exc:
            ensure("already exists" in str(exc), f"wrong collision refusal: {exc}")
        else:
            raise AssertionError("migration overwrote an existing baseline")
        path = root / corpus_images.BASELINE
        raw = json.loads(path.read_text())
        for rows in ([], raw["members"] * 2, [{**raw["members"][0], "image_bytes": True}]):
            path.write_text(json.dumps({**raw, "members": rows}), encoding="utf-8")
            try:
                corpus_images.read(path)
            except ValueError:
                pass
            else:
                raise AssertionError("malformed baseline accepted")


def _member_comparison() -> None:
    row = corpus_images.MemberImage("first", "first.s", "0" * 64, "1" * 64, 64)
    ensure(corpus_images.compare((row,), (row,)) == [], "identical member refused")
    for field, value in (("source", "renamed.s"), ("source_sha256", "2" * 64),
                         ("image_sha256", "3" * 64), ("image_bytes", 65)):
        ensure(any(field in fault for fault in corpus_images.compare((row,), (replace(row, **{field: value}),))),
               f"changed {field} accepted")


def _refuse_link(root: Path, rows: tuple[corpus_images.MemberImage, ...], previous: bytes | None) -> None:
    path = root / corpus_images.BASELINE
    try:
        corpus_images.publish(path, rows, previous)
    except ValueError as exc:
        ensure("regular file" in str(exc), f"wrong publication refusal: {exc}")
    else:
        raise AssertionError("publication replaced a linked baseline")
    with patch.object(corpus_images, "capture") as captured:
        try:
            corpus_images.migrate(root)
        except ValueError as exc:
            ensure("already exists" in str(exc), f"wrong linked migration refusal: {exc}")
        else:
            raise AssertionError("migration replaced a linked baseline")
    ensure(not captured.called, "linked migration assembled before refusing its output path")


def _linked_baseline_metadata() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        path = root / corpus_images.BASELINE
        path.parent.mkdir()
        rows = (corpus_images.MemberImage("first", "first.s", "0" * 64, "1" * 64, 64),)

        def linked(candidate: Path) -> bool:
            return candidate == path

        # Link metadata is sufficient to refuse even when Windows cannot create a link.
        for method in ("is_symlink", "is_junction"):
            with patch.object(Path, method, autospec=True, side_effect=linked):
                _refuse_link(root, rows, None)
            ensure(not path.exists(), f"{method} publication created an artifact")


def _baseline_symlinks() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        _fixture(root)
        previous = _baseline(root)
        path = root / corpus_images.BASELINE
        rows = corpus_images.read(path)
        target = root / "reviewed.json"
        path.replace(target)
        for present in (True, False):
            try:
                path.symlink_to(target)
            except OSError as exc:
                if getattr(exc, "winerror", None) == 1314:
                    return  # Windows without link privileges still runs the metadata control.
                raise
            linked_target = path.readlink()
            _refuse_link(root, rows, previous if present else None)
            ensure(path.is_symlink() and path.readlink() == linked_target, "refusal replaced the baseline link")
            if present:
                ensure(target.read_bytes() == previous, "refusal changed the baseline target")
            else:
                ensure(not target.exists(), "refusal created the dangling link's target")
            path.unlink()
            if present:
                target.unlink()


def cases() -> list[Case]:
    return [Case("append-only reviewed members and read-only checks", _extension),
            Case("changed source and removed member refused", _old_source_and_removal),
            Case("changed encoder refused without rebaseline", _changed_encoder),
            Case("legacy migration and malformed records refuse", _migration_and_shapes),
            Case("each recorded member field binds identity", _member_comparison),
            Case("linked baseline refuses before assembly or publication", _linked_baseline_metadata),
            Case("live and dangling baseline symlinks stay untouched", _baseline_symlinks)]
