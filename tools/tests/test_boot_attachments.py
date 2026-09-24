# SPDX-License-Identifier: Apache-2.0
"""Join the offline reference programs to the actual ELF and boot refusal path."""

import json
import shutil
import struct
from pathlib import Path
from typing import cast

from tests.harness import Case, ensure
from tests.test_boot import ROOT, _compose, _recipe_raw, _refused, _scratch, _write
from vos import admission, boot, composer


def _attached_recipe(root: Path) -> str:
    raw = _recipe_raw(root)
    raw.update(schema_version=2, expected=None)
    roster = boot.load_roster(root, cast("str", raw["roster"]))
    descriptors = composer.CompositionInput(
        tuple(composer.Descriptor(m.id, 1, ()) for m in roster.members),
        tuple(range(len(roster.members))), 1, 1, 1, frozenset({0}), frozenset({0}), 1)
    source = _write(root, "descriptors", composer.document(descriptors))
    raw["composer"] = {"source": source, "address": "0x80003000"}
    (root / "proofs").mkdir(exist_ok=True)
    (root / "tools" / "vos").mkdir(exist_ok=True)
    for relative in (admission.SOURCE, admission.CHECKER, "tools/vos/composer.py"):
        shutil.copyfile(ROOT / relative, root / relative)
    reference = admission.read_reference(root)
    members = cast("list[dict[str, object]]", raw["members"])
    request: dict[str, object] = {
        "schema_version": 1, "scope": "fixture-reference", "profile": "AdmissionPath.demo",
        "members": [{"member": m["id"], "artifact": m["source"], "tier": 0,
                     "certificate": {
                         "versions": reference.versions,
                         "binds_sha256": boot.digest_file(root / cast("str", m["source"])),
                         "steps": [{"judgment": reference.judgments.index("InstructionTransfer"),
                                    "move": reference.routing[facet],
                                    "facet": facet, "site": site}
                                   for site, facet in enumerate(reference.required[0])]}}
                    for m in members]}
    raw["admission"] = _write(root, "admission-request", request)
    return _write(root, "attached-recipe", raw)


def _reference_composition() -> None:
    with _scratch() as root:
        recipe = _attached_recipe(root)
        record = _compose(root, recipe)
        out = root / "out"
        ensure(record["accepted"] is False, "reference metadata never admits a production image")
        ensure(boot.stale(root, record, out) == [], "fresh attachments validate")
        ensure(boot.load_record(out) == record, "version 2 record reads back")
        graph = (out / "handler-graph.json").read_bytes()
        elf = (out / "image.elf").read_bytes()
        offset = struct.unpack_from("<Q", elf, 32)[0]
        size, count = struct.unpack_from("<HH", elf, 54)
        segments = [struct.unpack_from("<IIQQQQQQ", elf, offset + i * size)
                    for i in range(count)]
        matching = [p for p in segments if p[4] == 0x80003000]
        ensure(len(matching) == 1, "graph occupies one load segment")
        segment = matching[0]
        ensure(segment[1] == 4, "graph segment is read-only and non-executable")
        ensure(elf[segment[2]:segment[2] + segment[5]] == graph,
               "the image contains the exact graph whose digest the admission record binds")


def _attachment_refusals() -> None:
    with _scratch() as root:
        recipe = _attached_recipe(root)
        raw = cast("dict[str, object]", json.loads((root / recipe).read_text(encoding="utf-8")))
        placement = cast("dict[str, object]", raw["composer"])
        for bad in ({k: v for k, v in raw.items() if k != "composer"},
                    {**raw, "admission": None}, {**raw, "schema_version": True}):
            _refused(boot.RecipeError, lambda bad=bad: boot.parse_recipe(json.dumps(bad).encode(), "bad"),
                     "bad")
        for address in ("0x80000000", "0x80008000", "0x8000f000", "0xffffffffffff"):
            placement["address"] = address
            changed = _write(root, "bad-placement", raw)
            _refused(boot.RefusalError, lambda changed=changed: _compose(root, changed), "handler graph")
        placement["address"] = "0x80003000"
        changed = _write(root, "bad-admission", raw)
        _compose(root, changed)
        request_path = root / cast("str", raw["admission"])
        request = json.loads(request_path.read_text(encoding="utf-8"))
        request["members"][0]["certificate"] = None
        request_path.write_text(json.dumps(request), encoding="utf-8")
        _refused(boot.RefusalError, lambda: _compose(root, changed), "whole generation")
        ensure(not (root / "out" / "record.json").exists(),
               "a refused member removes the earlier composition record")


def _attachment_substitutions() -> None:
    with _scratch() as root:
        recipe = _attached_recipe(root)
        out = root / "out"
        record = _compose(root, recipe)
        image_path = out / "image.elf"
        image_path.write_bytes(image_path.read_bytes() + b"changed")
        cast("dict[str, object]", record["image"])["sha256"] = boot.digest_file(image_path)
        ensure(any("image digest differs" in finding for finding in boot.stale(root, record, out)),
               "rewriting the outer image binding cannot bypass the admission binding")
        record = _compose(root, recipe)
        attached_path = out / "admission.json"
        attached = json.loads(attached_path.read_text(encoding="utf-8"))
        attached["production_admission"] = True
        attached_path.write_text(json.dumps(attached), encoding="utf-8")
        cast("dict[str, object]", record["admission"])["sha256"] = boot.digest_file(attached_path)
        ensure(bool(boot.stale(root, record, out)), "a forged promotion is refused after full replay")
        record = _compose(root, recipe)
        graph_path = out / "handler-graph.json"
        graph_path.write_bytes(graph_path.read_bytes() + b" ")
        ensure(bool(boot.stale(root, record, out)), "a substituted graph is refused")
        record = _compose(root, recipe)
        record["accepted"] = True
        ensure(bool(boot.stale(root, record, out)), "a boot record cannot promote reference evidence")
        record = _compose(root, recipe)
        descriptors = root / "tools/boot/descriptors.json"
        original = descriptors.read_bytes()
        descriptors.write_bytes(original + b" ")
        ensure(bool(boot.stale(root, record, out)), "descriptor source byte changes are bound")
        descriptors.write_bytes(original)
        reference = root / admission.SOURCE
        original = reference.read_bytes()
        reference.write_bytes(original + b"\n(* changed reference bytes *)\n")
        ensure(bool(boot.stale(root, record, out)), "reference source byte changes are bound")
        reference.write_bytes(original)
        record = _compose(root, recipe)
        record["schema_version"] = 1
        del record["composer"]
        del record["admission"]
        ensure(bool(boot.stale(root, record, out)), "downgrading the record cannot discard attachments")


def _producer_and_member_bindings() -> None:
    with _scratch() as root:
        recipe_path = _attached_recipe(root)
        out = root / "out"
        record = _compose(root, recipe_path)
        producer = root / "tools/vos/composer.py"
        original = producer.read_bytes()
        producer.write_bytes(original + b"\n# changed producer\n")
        ensure(bool(boot.stale(root, record, out)), "composer implementation bytes are bound")
        producer.write_bytes(original)
        recipe = boot.load_recipe(root, recipe_path)
        request_path = root / cast("str", recipe.admission)
        raw = json.loads(request_path.read_text(encoding="utf-8"))
        first, second = raw["members"][:2]
        first["artifact"] = second["artifact"]
        first["certificate"]["binds_sha256"] = second["certificate"]["binds_sha256"]
        request_path.write_text(json.dumps(raw), encoding="utf-8")
        _refused(boot.RefusalError, lambda: _compose(root, recipe_path), "recipe source")
        # Even a rewritten outer sidecar binding must replay the source join.
        attached = admission.make_record(root, cast("str", recipe.admission),
                                         (out / "image.elf").read_bytes(),
                                         (out / "handler-graph.json").read_bytes(),
                                         boot.load_roster(root, recipe.roster))
        (out / "admission.json").write_bytes(admission.canonical(attached))
        cast("dict[str, object]", record["admission"])["sha256"] = boot.digest_file(out / "admission.json")
        ensure(any("recipe source" in f for f in boot.stale(root, record, out)),
               "replaying a rebound wrong-member fixture still refuses the source join")


def cases() -> list[Case]:
    return [Case("reference-graph-in-elf", _reference_composition),
            Case("whole-generation-and-extent-refusals", _attachment_refusals),
            Case("substitution-and-promotion-refusals", _attachment_substitutions),
            Case("producer-and-member-bindings", _producer_and_member_bindings)]
