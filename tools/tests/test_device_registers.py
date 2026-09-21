# SPDX-License-Identifier: Apache-2.0
"""Register layout refusals bind model coverage and the generated bit accessors."""

import hashlib
import json
from functools import cache
from typing import Any

from tests.harness import Case, ensure, sandbox_tree
from vos import corpus, sailbundle, socmap
from vos import device_registers as regs


@cache
def _fixture() -> dict[str, str]:
    root = corpus.find_root()
    paths = (regs.DECLARATION, socmap.COMPOSITION, sailbundle.BUNDLE, regs.PLATFORM,
             "model/model/sys/rot.sail", "model/model/sys/block_device.sail")
    return {relative: (root / relative).read_text(encoding="utf-8") for relative in paths}


def _review_layout(declaration: dict[str, Any]) -> str:
    declaration["reviewed_layout_sha256"] = regs.coverage_fingerprint(
        declaration["platform"], declaration["harness"])
    return json.dumps(declaration)


def _refused(tree: dict[str, str], expected: str) -> None:
    with sandbox_tree(tree) as root:
        try:
            regs.read(root)
        except regs.RegisterError as error:
            ensure(expected in str(error), f"wrong refusal: {error}")
        else:
            raise AssertionError(f"accepted defect requiring {expected!r}")


def _current_layout_and_shift_mutant() -> None:
    with sandbox_tree(_fixture()) as root:
        layout = regs.read(root)
        ensure(any(name == "trng_health_complete" and field.lsb == 32
                   for name, field in layout.fields), "health complete bit must be bound")
        artifacts = regs.generated(root)
        for relative, text in artifacts.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="")
        ensure(not regs.check(root), "fresh emission must agree")
        path = root / regs.RTL_ARTIFACT
        original = path.read_text(encoding="utf-8")
        changed = original.replace("TRNG_HEALTH_COMPLETE_SHIFT = 32", "TRNG_HEALTH_COMPLETE_SHIFT = 31")
        ensure(changed != original, "shift mutation must execute")
        path.write_text(changed, encoding="utf-8", newline="")
        ensure(regs.check(root) == [f"{regs.RTL_ARTIFACT}: differs from declared layouts"],
               "artifact-only shift must be rejected")


def _omitted_field_loses_review() -> None:
    tree = dict(_fixture())
    declaration = json.loads(tree[regs.DECLARATION])
    declaration["harness"]["htif"]["registers"][0]["fields"].pop()
    tree[regs.DECLARATION] = json.dumps(declaration)
    _refused(tree, "review complete field coverage")


def _invalid_layouts_refuse() -> None:
    for defect in ("overlap", "outside", "duplicate", "view"):
        tree = dict(_fixture())
        declaration = json.loads(tree[regs.DECLARATION])
        register = declaration["harness"]["htif"]["registers"][0]
        if defect == "overlap":
            # Identical binding still matches; overlap is a separate structural check.
            field = dict(register["fields"][0])
            field["name"] = "duplicate_payload"
            register["fields"].append(field)
            expected = "overlapping fields"
        elif defect == "outside":
            register["fields"][0]["width"] = 65
            expected = "outside the 64-bit word"
        elif defect == "duplicate":
            register["fields"].append(register["fields"][0])
            expected = "field declared twice"
        else:
            declaration["platform"]["trng"]["registers"][1]["views"] = register["views"][:1]
            expected = "view extends outside declared fields"
        tree[regs.DECLARATION] = _review_layout(declaration)
        _refused(tree, expected)


def _new_aperture_and_duplicate_key_refuse() -> None:
    tree = dict(_fixture())
    tree[socmap.COMPOSITION] = tree[socmap.COMPOSITION].replace(
        '"platform": {', '"platform": { "new_device": { "supported": true, "base": 0 },', 1)
    _refused(tree, "device coverage differs")
    tree = dict(_fixture())
    tree[regs.DECLARATION] = tree[regs.DECLARATION].replace('"schema": 1', '"schema": 1, "schema": 1', 1)
    _refused(tree, "duplicate declaration key schema")


def _source_drift_refuses() -> None:
    tree = dict(_fixture())
    tree[regs.PLATFORM] = tree[regs.PLATFORM].replace("0x0000000100000000", "0x0000000080000000")
    _refused(tree, "model bundle is stale")
    bundle = json.loads(tree[sailbundle.BUNDLE])
    source_key = next(key for key in bundle["hashes"] if key.endswith("sys/platform.sail"))
    bundle["hashes"][source_key]["md5"] = hashlib.md5(tree[regs.PLATFORM].encode(), usedforsecurity=False).hexdigest()
    body = bundle["functions"]["trng_load"]["function"]["body"]
    body["contents"] = body["contents"].replace("0x0000000100000000", "0x0000000080000000")
    tree[sailbundle.BUNDLE] = json.dumps(bundle)
    _refused(tree, "MMIO body changed")
    declaration = json.loads(tree[regs.DECLARATION])
    declaration["reviewed_functions"]["trng_load"] = regs.fingerprint(body["contents"])
    tree[regs.DECLARATION] = json.dumps(declaration)
    _refused(tree, "declared layout does not match trng_load")


def cases() -> list[Case]:
    return [Case("current-layout-and-shift-mutant", _current_layout_and_shift_mutant),
            Case("omitted-field-loses-review", _omitted_field_loses_review),
            Case("invalid-layouts-refuse", _invalid_layouts_refuse),
            Case("new-aperture-and-duplicate-key-refuse", _new_aperture_and_duplicate_key_refuse),
            Case("source-drift-refuses", _source_drift_refuses)]
