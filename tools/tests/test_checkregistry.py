# SPDX-License-Identifier: Apache-2.0
"""Rule metadata binds executable callbacks and generates its readable views."""

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import check
from tests.harness import TOOLS, Case, ensure, sandbox_tree
from vos import checkregistry
from vos import corpus as corpus_mod
from vos.checks import Context, meta
from vos.cli import selftest
from vos.register import read_artifacts, read_register
from vos.report import Reporter

INDEPENDENT_CASES = True

_TEMPLATE = ("# Rules\n\n" + checkregistry.TABLE_BEGIN + "\n" + checkregistry.TABLE_END
             + "\n\nAuthored explanation.\n\n" + checkregistry.REACH_BEGIN + "\n"
             + checkregistry.REACH_END + "\n")


def _owner() -> dict[str, object]:
    return {"version": 1, "rules": [
        {"id": ident, "group": group, "meaning": "Decides an obligation.",
         "ground": "Fixture contract.", "reach": str(reach)}
        for ident, group, reach in (
            ("K-00", "meta", checkregistry.Reach.TOTAL),
            ("K-01", "fixture", checkregistry.Reach.NAME),
            ("K-02", "fixture", checkregistry.Reach.COMPUTED),
            ("K-03", "fixture", checkregistry.Reach.PATTERN))],
        "inactive": [{"id": "K-40", "kind": "retired", "ground": "Removed."}]}


def _files(owner: object) -> dict[str, str]:
    return {checkregistry.SOURCE: json.dumps(owner),
            checkregistry.SCHEMA: (TOOLS.parent / checkregistry.SCHEMA).read_text(encoding="utf-8"),
            checkregistry.DOCUMENT: _TEMPLATE,
            "docs/requirements-register.md": "# Register\n"}


def _context(root: Path) -> Context:
    corpus = corpus_mod.load(root)
    return Context(root, corpus, read_register(corpus), read_artifacts(corpus),
                   Reporter(), fix=True, registry=checkregistry.read(root))


def _required_metadata_refuses_malformed_owners() -> None:
    good = _owner()
    damaged: list[object] = [None, {}, {**good, "version": True}, {**good, "version": 1.0},
                             {**good, "rules": []}, {**good, "extra": "unread"}]
    for key, value in (("reach", "marker"), ("group", ""), ("meaning", ""),
                       ("id", "bad"), ("extra", "unread")):
        rows = json.loads(json.dumps(good))["rules"]
        rows[0][key] = value
        damaged.append({**good, "rules": rows})
    rows = json.loads(json.dumps(good))["rules"]
    del rows[0]["reach"]
    damaged.append({**good, "rules": rows})
    rows = json.loads(json.dumps(good))["rules"]
    rows[1]["id"] = rows[0]["id"]
    damaged.append({**good, "rules": rows})
    damaged.append({**good, "inactive": [{"id": "K-00", "kind": "retired", "ground": "x"}]})
    for owner in damaged:
        with sandbox_tree(_files(owner)) as root:
            try:
                checkregistry.read(root)
            except ValueError:
                pass
            else:
                raise AssertionError(f"malformed rule metadata was accepted: {owner!r}")
    with sandbox_tree({checkregistry.SOURCE: '{"version":1,"version":1}'}) as root:
        try:
            checkregistry.read(root)
        except ValueError as exc:
            ensure("duplicate JSON key" in str(exc), "duplicate keys must fail before schema reading")
        else:
            raise AssertionError("duplicate JSON members were accepted")


def _schema_inputs_fail_closed() -> None:
    for contents in (None, "{", '{"type":"not-a-type"}',
                     '{"type":"object","type":"object"}'):
        files = _files(_owner())
        if contents is None:
            del files[checkregistry.SCHEMA]
        else:
            files[checkregistry.SCHEMA] = contents
        with sandbox_tree(files) as root:
            try:
                checkregistry.read(root)
            except ValueError as error:
                ensure("check-registry.schema.json" in str(error), "schema findings name their owner")
            else:
                raise AssertionError("an invalid schema supplied a rule-registry verdict")


def _nothing(ctx: Context) -> None:
    return None


def _callbacks_and_metadata_are_total() -> None:
    with sandbox_tree(_files(_owner())) as root:
        registry = checkregistry.read(root)
        bound = registry.bind((("fixture", _nothing), ("meta", _nothing)))
        ensure([group.name for group in bound] == ["fixture", "meta"],
               "binding must preserve execution order")
        ensure(bound[0].run is _nothing and len(bound[0].rules) == 3,
               "bound groups carry the actual callback and its declarations")
        for callbacks in ((), (("fixture", _nothing),),
                          (("fixture", _nothing), ("fixture", _nothing), ("meta", _nothing)),
                          (("fixture", _nothing), ("meta", _nothing), ("extra", _nothing))):
            try:
                registry.bind(callbacks)
            except ValueError:
                pass
            else:
                raise AssertionError(f"incomplete or duplicate callback binding was accepted: {callbacks!r}")


def _generated_regions_preserve_authored_bytes() -> None:
    with sandbox_tree(_files(_owner())) as root:
        registry = checkregistry.read(root)
        for template in (_TEMPLATE, _TEMPLATE.replace("\n", "\r\n")):
            rendered = checkregistry.render(registry, template)
            ensure(rendered == checkregistry.render(registry, rendered),
                   "generation must be a fixed point")
            ensure("Authored explanation." in rendered and "| ~~K-40~~ | retired |" in rendered,
                   "authored prose and permanent inactive IDs must remain")
            ensure("| K-01 | fixture |" in rendered and "| name | K-01 |" in rendered,
                   "the rule table and reach membership derive from the same record")
            if "\r\n" in template:
                ensure("\n" not in rendered.replace("\r\n", ""),
                       "generation must retain CRLF without mixed line endings")
        for broken in (_TEMPLATE.replace(checkregistry.TABLE_BEGIN, ""),
                       _TEMPLATE + checkregistry.REACH_END,
                       _TEMPLATE.replace(checkregistry.TABLE_BEGIN, "SWAPPED MARKER")
                       .replace(checkregistry.TABLE_END, checkregistry.TABLE_BEGIN)
                       .replace("SWAPPED MARKER", checkregistry.TABLE_END)):
            try:
                checkregistry.render(registry, broken)
            except ValueError:
                pass
            else:
                raise AssertionError("malformed generated-region markers were accepted")


def _region_layouts_refuse_before_any_repair() -> None:
    begin, end = checkregistry.TABLE_BEGIN, checkregistry.TABLE_END
    reach_begin, reach_end = checkregistry.REACH_BEGIN, checkregistry.REACH_END
    # Every marker occurs once in these arrangements: individual region counts
    # cannot detect the crossed, nested or reversed relationship between them.
    for markers in ((begin, reach_begin, end, reach_end),
                    (begin, reach_begin, reach_end, end),
                    (reach_begin, begin, end, reach_end),
                    (reach_begin, reach_end, begin, end)):
        broken = "\n".join(markers) + "\n"
        files = {**_files(_owner()), checkregistry.DOCUMENT: broken}
        with sandbox_tree(files) as root:
            context = _context(root)
            meta._registry(context)
            ensure(context.rep.findings > 0 and not context.fixed,
                   f"ambiguous generated regions must refuse before repair: {markers}")
            ensure((root / checkregistry.DOCUMENT).read_text(encoding="utf-8") == broken,
                   "a refused render must preserve its original source")


def _suffixed_ids_keep_identity_in_views_and_holder_readers() -> None:
    owner = _owner()
    owner = json.loads(json.dumps(owner))
    owner["rules"][1]["id"] = "K-01a"
    owner["inactive"][0]["id"] = "K-40a"
    files = {**_files(owner), meta.PLAN: "# Plan\n\nLanded: Tier B under **K-01a**.\n",
             meta.LOG: "# Evidence\n\nLanded: Tier B under **K-40a**.\n",
             meta.Q_RULES: "# Deferred\n\n| K-58a | deferred | meaning | ground |\n",
             "docs/current.md": "# Current\n\nA fact held by **K-58a**.\n"}
    with sandbox_tree(files) as root:
        registry = checkregistry.read(root)
        rendered = checkregistry.render(registry, _TEMPLATE)
        ensure("| K-01a | fixture |" in rendered and "| ~~K-40a~~ | retired |" in rendered,
               "active and retired suffixed IDs must retain their exact identities")
        (root / checkregistry.DOCUMENT).write_text(rendered, encoding="utf-8", newline="")
        context = _context(root)
        deferred = meta._quarantined_rules(context)
        ensure(deferred == {"K-58a"}, "deferred registry readers must retain suffixes")
        meta._landings(context, set(registry.identifiers) | deferred)
        ensure(context.rep.findings == 0,
               f"valid suffixed holders and historical retirements must resolve: {context.rep.out}")
        (root / "docs/current.md").write_text("# Current\n\nHeld by **K-40a**.\n",
                                             encoding="utf-8", newline="")
        context = _context(root)
        meta._landings(context, set(registry.identifiers) | deferred)
        ensure(context.rep.findings > 0 and any("K-40a" in line for line in context.rep.out),
               "a retired suffixed holder must still refuse current claims")


def _sandbox_failure_ids_require_the_whole_colon_delimited_id() -> None:
    output = ("FAIL K-12a: 1 finding\nFAIL K-12: 1 finding\n"
              "FAIL K-12ab: invalid suffix\nFAIL K-1234: invalid width\n"
              "FAIL K-12 trailing text\n    FAIL K-12a: repeated finding\n")
    result = subprocess.CompletedProcess([], 1, stdout=output, stderr="")
    with sandbox_tree({}) as root, patch.object(selftest.subprocess, "run", return_value=result):
        code, _out, failed = selftest.Sandbox(root, root).check()
    ensure(code == 1 and failed == ["K-12", "K-12a"],
           f"failure extraction must preserve suffixes without reading ID prefixes: {failed!r}")


def _verdict_inventory_preserves_prerequisite_failures() -> None:
    rule = checkregistry.Rule("K-01", "fixture", "meaning", "ground", checkregistry.Reach.NAME)
    ensure(checkregistry.verdict_faults((rule,), ("K-01", "K-01"), clean=True) == [],
           "a rule may emit separate domain verdicts")
    ensure(checkregistry.verdict_faults((rule,), (), clean=True)
           == ["declared rule produced no verdict: K-01"],
           "a clean callback cannot silently omit a registered rule")
    ensure(checkregistry.verdict_faults((rule,), (), clean=False) == [],
           "an already-failed prerequisite does not manufacture dependent verdicts")
    ensure(checkregistry.verdict_faults((rule,), ("K-99",), clean=False)
           == ["undeclared rule verdict: K-99"],
           "undeclared verdicts always fail")


@dataclass(frozen=True)
class _Group:
    name: str
    run: Callable[[Context], None]

    @property
    def __name__(self) -> str:
        return self.name


def _driver_checks_actual_callback_verdicts() -> None:
    def fixture(ctx: Context) -> None:
        for ident in ("K-01", "K-02", "K-03"):
            ctx.rep.report(ident, "fixture", [])

    def omitted(ctx: Context) -> None:
        ctx.rep.report("K-01", "fixture", [])

    with sandbox_tree(_files(_owner())) as root:
        registry = checkregistry.read(root)
        (root / checkregistry.DOCUMENT).write_text(checkregistry.render(registry, _TEMPLATE),
                                                  encoding="utf-8", newline="")
        for callback, clean in ((fixture, True), (omitted, False)):
            with patch.object(check, "GROUPS", [_Group("fixture", callback),
                                                _Group("meta", meta._registry)]):
                report = check.run(root)
            ensure((report.findings == 0) == clean,
                   f"driver verdict coverage did not follow executed callbacks: {report.out!r}")
            if not clean:
                ensure(any("declared rule produced no verdict: K-02" in line for line in report.out),
                       "the missing executed rule must be identified by K-00")


def cases() -> list[Case]:
    return [
        Case("required-metadata-refuses-malformed-owners", _required_metadata_refuses_malformed_owners),
        Case("schema-inputs-fail-closed", _schema_inputs_fail_closed),
        Case("callbacks-and-metadata-are-total", _callbacks_and_metadata_are_total),
        Case("generated-regions-preserve-authored-bytes", _generated_regions_preserve_authored_bytes),
        Case("region-layouts-refuse-before-any-repair", _region_layouts_refuse_before_any_repair),
        Case("suffixed-ids-keep-identity-in-views-and-holder-readers",
             _suffixed_ids_keep_identity_in_views_and_holder_readers),
        Case("sandbox-failure-ids-require-the-whole-colon-delimited-id",
             _sandbox_failure_ids_require_the_whole_colon_delimited_id),
        Case("verdict-inventory-preserves-prerequisite-failures",
             _verdict_inventory_preserves_prerequisite_failures),
        Case("driver-checks-actual-callback-verdicts", _driver_checks_actual_callback_verdicts),
    ]
