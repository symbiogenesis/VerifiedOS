# SPDX-License-Identifier: Apache-2.0
"""Declared source views reach generated inventories and receipt boundaries."""

import json
import shutil
import tempfile
from collections.abc import Callable, Generator
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import admission_production, composition
from vos import source_bindings as bindings
from vos.checks import generated
from vos.cli import composer as cli
from vos.receipts import digest

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def _fixture() -> Generator[Path]:
    with tempfile.TemporaryDirectory(prefix="vos-source-bindings-") as temporary:
        root = Path(temporary)
        for name in {name for view in bindings.GROUPS for name in bindings.sources(view)}:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if name.endswith(".py"):
                shutil.copyfile(ROOT / name, path)
            else:
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
    for path in ("tools/vos/jsonc.py", "tools/vos/__init__.py", "tools/generated/dialect-table.json",
                 "tools/pyproject.toml", "tools/uv.lock"):
        ensure(path in bindings.sources("projection"), f"actual projection dependency is bound: {path}")
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
        (root / name).write_bytes(b"# new shared implementation\n")
        with patch.dict(bindings.GROUPS, shared=(*bindings.GROUPS["shared"], name)):
            for view in ("composer-package", "admission-package", "composer-reference",
                         "admission-reference", "projection", "admission-comparison", "admission-production"):
                refs = bindings.references(root, view)
                ensure(sum(ref["path"] == name for ref in refs) == 1, f"{view}: shared dependency propagates")
                before = next(ref for ref in refs if ref["path"] == name)
                (root / name).write_bytes((root / name).read_bytes() + b"# changed\n")
                after = next(ref for ref in bindings.references(root, view) if ref["path"] == name)
                ensure(before["sha256"] != after["sha256"], f"{view}: substitution changes identity")
            (root / name).unlink()
            _refused(lambda: bindings.references(root, "composer-package"), "new-shared-fixture.py")


def _current_import_closure() -> None:
    with _fixture() as root:
        before = bindings.references(root, "projection")
        helper = root / "tools/vos/jsonc.py"
        helper.write_bytes(helper.read_bytes() + b"\n# changed parser implementation\n")
        after = bindings.references(root, "projection")
        changed = {left["path"] for left, right in zip(before, after, strict=True) if left != right}
        ensure(changed == {"tools/vos/jsonc.py"}, "transitive parser bytes change the projection identity")
        unrelated = root / "tools/vos/unrelated_fixture.py"
        unrelated.write_text("raise RuntimeError('must not execute')\n", encoding="utf-8")
        ensure(bindings.references(root, "projection") == after,
               "unimported tools do not change the projection identity")

        seed = root / "tools/vos/composition.py"
        seed.write_bytes(seed.read_bytes() + b"\nfrom vos import dependency_fixture\n")
        imported = root / "tools/vos/dependency_fixture.py"
        imported.write_text("from . import nested_fixture\nraise RuntimeError('must not execute')\n",
                            encoding="utf-8")
        nested = root / "tools/vos/nested_fixture.py"
        nested.write_text("value = 1\n", encoding="utf-8")
        current = bindings.sources("projection", root=root)
        ensure({"tools/vos/dependency_fixture.py", "tools/vos/nested_fixture.py"} <= set(current),
               "new direct and transitive imports join the selected checkout's next identity")
        ensure("tools/vos/dependency_fixture.py" not in composition.PRODUCERS,
               "the fixture dependency was not present in the module's import-time compatibility view")
        with patch.object(composition, "_bound"), patch.object(composition, "_package", return_value=None):
            binding = composition._binding(root, {"configuration": {}, "producers": [], "members": []}, {}, {})
        ensure(binding["projection_producers"] == bindings.references(root, "projection"),
               "receipt construction derives current membership from its explicit checkout")
        ensure(bindings.sources("projection", root=root) == current, "closure ordering is deterministic")
        nested.unlink()
        _refused(lambda: bindings.references(root, "projection"), "nested_fixture")


def _source_refusals() -> None:
    with _fixture() as root:
        path = root / "tools/vos/composition.py"
        path.write_text("def incomplete(\n", encoding="utf-8")
        _refused(lambda: bindings.references(root, "projection"), "composition.py")
        path.unlink()
        _refused(lambda: bindings.references(root, "projection"), "composition.py")


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


def _malformed_inputs() -> None:
    with _fixture() as root:
        path = root / bindings.COMPOSITION
        original = path.read_bytes()
        packages = {name: (root / name).read_bytes() for name in bindings.PACKAGE_FILES.values()}
        for raw_root in (None, [], 1):
            path.write_text(json.dumps(raw_root), encoding="utf-8")
            _refused(lambda: bindings.emit(root), "input must be an object")
        for field in ("producers", "members"):
            for replacement in (None, {}, ["bad"], [{}], [{"id": 1}]):
                raw = json.loads(original)
                raw[field] = replacement
                path.write_text(json.dumps(raw), encoding="utf-8")
                _refused(lambda: bindings.emit(root), f"{field} must be an array of identified objects")
            raw = json.loads(original)
            del raw[field]
            path.write_text(json.dumps(raw), encoding="utf-8")
            output = StringIO()
            with patch.object(cli.corpus, "find_root", return_value=root), redirect_stdout(output):
                code = cli.main(["bind-sources"])
            ensure(code == 1 and output.getvalue().startswith("FAIL composer:"),
                   "malformed inventory inputs must return a named command refusal")
        for descriptor in (None, [], {}, {"path": "other.json"}):
            raw = json.loads(original)
            member = next(item for item in raw["members"] if item["id"] == "composer")
            member["descriptor"] = descriptor
            path.write_text(json.dumps(raw), encoding="utf-8")
            before = path.read_bytes()
            _refused(lambda: bindings.emit(root), "package path disagrees")
            ensure(path.read_bytes() == before, "refusal overwrote malformed authored input")
        ensure(all((root / name).read_bytes() == data for name, data in packages.items()),
               "a later malformed input must preserve every earlier output")


def _destination_preflight() -> None:
    with _fixture() as root:
        before = {name: (root / name).read_bytes()
                  for name in (*bindings.PACKAGE_FILES.values(), bindings.COMPOSITION)}
        with patch.dict(bindings.PACKAGE_FILES, admission=bindings.PACKAGE_FILES["composer"]):
            _refused(lambda: bindings.emit(root), "aliases another output or bound source")
        with patch.dict(bindings.GROUPS, shared=(*bindings.GROUPS["shared"], bindings.PACKAGE_FILES["composer"])):
            _refused(lambda: bindings.emit(root), "aliases another output or bound source")
        with patch.object(bindings, "COMPOSITION", "../outside.json"):
            _refused(lambda: bindings.emit(root), "must stay relative to the checkout")
        ensure(all((root / name).read_bytes() == data for name, data in before.items()),
               "destination refusal must precede every publication")


def _linked_destinations() -> None:
    with _fixture() as root, tempfile.TemporaryDirectory(prefix="vos-binding-outside-") as directory:
        outside = Path(directory)
        path = root / bindings.COMPOSITION
        data = path.read_bytes()
        target = outside / "composition.json"
        target.write_bytes(data)
        path.unlink()
        path.symlink_to(target)
        packages = {name: (root / name).read_bytes() for name in bindings.PACKAGE_FILES.values()}
        _refused(lambda: bindings.emit(root), "must stay relative to the checkout")
        redirect = root / "redirect"
        redirect.symlink_to(outside, target_is_directory=True)
        with patch.object(bindings, "COMPOSITION", "redirect/composition.json"):
            _refused(lambda: bindings.emit(root), "must stay relative to the checkout")
        ensure(target.read_bytes() == data, "linked publication changed outside bytes")
        ensure(all((root / name).read_bytes() == value for name, value in packages.items()),
               "an escaping later destination must preserve all earlier outputs")


def cases() -> list[Case]:
    return [Case("declared-consumer-views", _views), Case("generated-source-fields", _generation),
            Case("shared-dependency-propagation", _shared_dependency),
            Case("current transitive imports bind actual checkout bytes", _current_import_closure),
            Case("unreadable and malformed source dependencies refuse", _source_refusals),
            Case("source-declaration-refusals", _declaration_refusals),
            Case("malformed inputs preserve outputs", _malformed_inputs),
            Case("all destinations preflight before publication", _destination_preflight),
            Case("linked destinations preserve checkout and outside bytes", _linked_destinations, lane="guest")]
