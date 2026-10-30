# SPDX-License-Identifier: Apache-2.0
"""Declared source views reach generated inventories and receipt boundaries."""

import json
import shutil
import tempfile
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import admission_production, composition
from vos import source_bindings as bindings
from vos.checks import generated
from vos.receipts import digest

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def _fixture() -> Generator[Path]:
    with tempfile.TemporaryDirectory(prefix="vos-source-bindings-") as temporary:
        root = Path(temporary)
        for name in {name for view in bindings.GROUPS for name in bindings.sources(view)}:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"fixture source: {name}\n", encoding="utf-8")
        for name in (*bindings.PACKAGE_FILES.values(), bindings.COMPOSITION):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, path)
        yield root


def _refused(action: Callable[[], object], phrase: str) -> None:
    try:
        action()
    except (ValueError, OSError) as error:
        ensure(phrase in str(error), f"wrong source-binding refusal: {error}")
        return
    raise AssertionError(f"expected source-binding refusal: {phrase}")


def _views() -> None:
    ensure(bindings.sources("projection") == composition.PRODUCERS, "projection consumes declaration")
    ensure(bindings.sources("admission-production") == admission_production.CHECKERS,
           "production receipts consume declaration")
    for view in bindings.GROUPS:
        sources = bindings.sources(view)
        ensure(len(sources) == len(set(sources)), f"{view}: repeated joins are deduplicated")
        ensure(bindings.OWNER in sources and "tools/vos/jsonutil.py" in sources,
               f"{view}: declaration and shared parser are bound")
    rows = {row.path: row for row in generated.GENERATED}
    ordered = list(rows)
    for path in bindings.PACKAGE_FILES.values():
        ensure(rows[path].lane == "host" and rows[path].emit is not None,
               "source view is checked and repairable")
        ensure(ordered.index(path) < ordered.index(bindings.COMPOSITION),
               "packages settle before input descriptor digests")
    ensure(ordered.index(bindings.COMPOSITION) < ordered.index(f"{composition.GENERATED}/manifest.json"),
           "input settles before projections")


def _generation() -> None:
    with _fixture() as root:
        original = json.loads((root / bindings.COMPOSITION).read_bytes())
        for name, relative in bindings.PACKAGE_FILES.items():
            before = json.loads((root / relative).read_bytes())
            text = bindings.render(root, relative)
            package = json.loads(text)
            ensure(package["sources"] == bindings.references(root, f"{name}-package"),
                   "package list derives from owner")
            ensure({key: value for key, value in package.items() if key != "sources"}
                   == {key: value for key, value in before.items() if key != "sources"},
                   "interface and handler choices remain authored")
            (root / relative).write_text(text, encoding="utf-8", newline="")
            ensure(bindings.render(root, relative) == text, "package generation reaches a fixpoint")
        text = bindings.render(root, bindings.COMPOSITION)
        result = json.loads(text)
        for producer in result["producers"]:
            ensure(producer["sources"] == bindings.references(root, bindings.PRODUCER_VIEWS[producer["id"]]),
                   "producer list derives from owner")
        for member in result["members"]:
            if member["id"] in bindings.PACKAGE_FILES:
                ensure(member["sources"] == bindings.references(root, f"{member['id']}-package"),
                       "tool member list derives from same package view")
                ensure(member["descriptor"]["sha256"]
                       == digest(root / bindings.PACKAGE_FILES[member["id"]]),
                       "composition binds regenerated package bytes")
            else:
                ensure(member == next(item for item in original["members"] if item["id"] == member["id"]),
                       "runtime member choices remain authored")
        (root / bindings.COMPOSITION).write_text(text, encoding="utf-8", newline="")
        ensure(bindings.render(root, bindings.COMPOSITION) == text, "composition generation reaches a fixpoint")
        hashes = bindings.emit(root)
        ensure(set(hashes) == {*bindings.PACKAGE_FILES.values(), bindings.COMPOSITION},
               "owner command publishes exactly its declared files")
        ensure(hashes == bindings.emit(root), "whole inventory publication reaches a fixpoint")


def _shared_dependency() -> None:
    with _fixture() as root:
        name = "tools/vos/new-shared-fixture.py"
        (root / name).write_bytes(b"new shared implementation\n")
        with patch.dict(bindings.GROUPS, shared=(*bindings.GROUPS["shared"], name)):
            for view in ("composer-package", "admission-package", "composer-reference",
                         "admission-reference", "projection", "admission-comparison", "admission-production"):
                refs = bindings.references(root, view)
                ensure(sum(ref["path"] == name for ref in refs) == 1, f"{view}: shared dependency propagates")
                before = next(ref for ref in refs if ref["path"] == name)
                (root / name).write_bytes((root / name).read_bytes() + b"changed\n")
                after = next(ref for ref in bindings.references(root, view) if ref["path"] == name)
                ensure(before["sha256"] != after["sha256"], f"{view}: substitution changes identity")
            (root / name).unlink()
            _refused(lambda: bindings.references(root, "composer-package"), "new-shared-fixture.py")


def _declaration_refusals() -> None:
    _refused(lambda: bindings.sources("absent"), "unknown source-binding group")
    with patch.dict(bindings.GROUPS, broken=("@broken",)):
        _refused(lambda: bindings.sources("broken"), "recursive source-binding group")
    for members in ((), ("same.py", "same.py")):
        with patch.dict(bindings.GROUPS, broken=members):
            _refused(lambda: bindings.sources("broken"), "empty or repeated")
    with _fixture() as root:
        path = root / bindings.COMPOSITION
        raw = json.loads(path.read_bytes())
        raw["producers"].pop()
        path.write_text(json.dumps(raw), encoding="utf-8")
        _refused(lambda: bindings.render(root, bindings.COMPOSITION), "producer must occur once")


def cases() -> list[Case]:
    return [Case("declared-consumer-views", _views), Case("generated-source-fields", _generation),
            Case("shared-dependency-propagation", _shared_dependency),
            Case("source-declaration-refusals", _declaration_refusals)]
