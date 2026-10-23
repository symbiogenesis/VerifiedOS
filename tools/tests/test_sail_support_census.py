# SPDX-License-Identifier: Apache-2.0
"""Python-only adapter fixtures; these supply no native census qualification."""

import copy
import json
import runpy
import unittest
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

from tests.harness import Case
from vos import proofaudit

_DIRECTORY = Path(__file__).resolve().parents[1] / "rocq-census"
_ADAPTER = runpy.run_path(str(_DIRECTORY / "census.py"))
_SCHEMA = json.loads((_DIRECTORY / "census-schema.json").read_text(encoding="utf-8"))


def _example(schema: dict[str, Any]) -> object:
    if "$ref" in schema:
        return _example(_SCHEMA["$defs"][schema["$ref"][8:]])
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    if "oneOf" in schema or "anyOf" in schema:
        return _example(schema.get("oneOf", schema.get("anyOf"))[0])
    kind = schema["type"]
    if kind == "object":
        return {name: _example(schema["properties"][name]) for name in schema["required"]}
    if kind == "array":
        return [_example(schema["items"]) for _ in range(schema.get("minItems", 0))]
    return {"null": None, "boolean": False, "integer": schema.get("minimum", 0), "string": "x"}[kind]


def _path(name: str) -> dict[str, Any]:
    root, *labels = name.split(".")
    result: dict[str, Any] = {"tag": "MPfile", "directory_reversed": [root]}
    for label in labels:
        result = {"tag": "MPdot", "parent": result, "label": label}
    return result


def _reference(module: str, label: str = "x") -> dict[str, Any]:
    kernel = {"path": _path(module), "label": label}
    return {"kind": "constant", "exported_name": module + "." + label,
            "canonical_name": module + "." + label, "user": kernel,
            "canonical": copy.deepcopy(kernel), "packet_index": None, "constructor_index": None}


def _fixture(root: str = "Root") -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
    metadata = cast("dict[str, Any]", _example(_SCHEMA["$defs"]["constant_metadata"]))
    metadata.update(type={"tag": "Sort", "sort": {"tag": "Prop"}}, body_kind="Undef",
                    transparent_body=None, inline_level=None, primitive=None)
    value = {"schema": "verifiedos-sail-support-census/1", "producer": "rocq-9.3.0-constructor-api",
             "requested_roots": [root], "roots": [{"requested": root, "native_path": _path(root), "module_id": root}],
             "modules": [], "fields": [], "declarations": [], "abbreviations": [], "resolvers": [],
             "contexts": [], "resolution_requests": [], "resolutions": [],
             "environment": _example(_SCHEMA["$defs"]["environment"])}
    _module(value, root, None, "concrete-root")
    _constant(value, root, metadata)
    searches = {root: proofaudit.EMPTY_BLACKLIST + "\n" + root + ".x: Prop\n"}
    value["resolution_requests"] = _ADAPTER["parse_search_requests"](searches, expected_modules=[root])
    value["resolutions"] = [{"request_id": root + ":0", "root_module_id": root, "candidates": [
        {"mode": "global", "field_id": root + ":x", "declaration_id": root + ":x:declaration",
         "abbreviation_id": None, "reference": _reference(root)}]}]
    return _finish(value, searches)


def _module(value: dict[str, Any], name: str, parent: str | None, context_kind: str,
            *, kind: str = "module") -> dict[str, Any]:
    identifier = name
    context = name + ":context"
    root = value["requested_roots"][0]
    value["contexts"].append({"id": context, "parent_id": parent + ":context" if parent is not None else None,
                               "kind": context_kind, "owner_path": _path(name), "parameter_identifier": None,
                               "parameter_signature_module_id": None})
    module = {"id": identifier, "parent_field_id": name + ":field" if parent is not None else None,
              "kind": kind, "native_path": _path(name), "context_id": context,
              "query": {"owner_root_id": root, "kind": "module-type" if kind == "module-type" else "module",
                        "target": name, "target_module_id": identifier, "coverage_path": []},
              "signature": {"parameters": [], "result_context_id": context, "field_count": 0, "field_ids": []},
              "implementation": {"kind": "NotApplicable" if kind == "module-type" else "FullStruct", "expression": None,
                                 "algebraic_type": None, "structure": None, "resolver_id": identifier + ":resolver"},
              "abbreviation_ids": [], "empty_evidence": "native-empty"}
    value["modules"].append(module)
    value["resolvers"].append({"id": identifier + ":resolver", "owner_module_id": identifier, "role": "implementation",
                               "coverage": "finite-enumerated-domain", "root": _path(name),
                               "module_effects": [], "kernel_effects": [], "inline_keys": []})
    if parent is not None:
        parent_module = next(row for row in value["modules"] if row["id"] == parent)
        field = {"id": name + ":field", "parent_module_id": parent, "namespace": "module", "label": name.rsplit(".", 1)[1],
                 "kind": kind, "context_id": parent_module["signature"]["result_context_id"], "classification": "interface" if kind == "module-type" else "owned",
                 "metadata": None, "child_module_id": identifier, "declaration_ids": []}
        value["fields"].append(field)
        parent_module["signature"]["field_ids"].append(field["id"])
    return module


def _constant(value: dict[str, Any], module_name: str, metadata: dict[str, Any], *, abstract: bool = False) -> None:
    module = next(row for row in value["modules"] if row["id"] == module_name)
    field_id, declaration_id = module_name + ":x", module_name + ":x:declaration"
    context = module["signature"]["result_context_id"]
    reference = _reference(module_name)
    locator = {"module_path": _path(module_name), "namespace": "object", "label": "x", "packet_index": None, "constructor_index": None}
    link = {"lookup_succeeded": True, "exported_reference": reference, "source_field": locator,
            "instantiated_field": copy.deepcopy(locator), "source_reference": copy.deepcopy(reference),
            "implementation_reference": copy.deepcopy(reference), "source_metadata": metadata, "instantiated_metadata": copy.deepcopy(metadata),
            "steps": [{"tag": "structure-field", "field": locator, "implementation_kind": "FullStruct", "resolver_id": module_name + ":resolver"},
                      {"tag": "direct-lookup", "reference": reference, "lookup_succeeded": True}], "audit_query_name": module_name + ".x"}
    value["fields"].append({"id": field_id, "parent_module_id": module_name, "namespace": "object", "label": "x", "kind": "constant",
                            "context_id": context, "classification": "interface" if abstract else "owned", "metadata": metadata,
                            "child_module_id": None, "declaration_ids": [declaration_id]})
    value["declarations"].append({"id": declaration_id, "field_id": field_id, "namespace": "object", "kind": "constant", "label": "x",
                                  "packet_index": None, "constructor_index": None, "classification": "interface" if abstract else "owned",
                                  "context_id": context, "exported_name": module_name + ".x", "native_reference": None if abstract else reference,
                                  "type": metadata["type"], "implementation_connection": None if abstract else link, "alias": None})
    module["signature"]["field_ids"].append(field_id)


def _finish(value: dict[str, Any], searches: dict[str, str]) -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
    for module in value["modules"]:
        count = len(module["signature"]["field_ids"])
        module["signature"]["field_count"] = count
        module["empty_evidence"] = "nonempty" if count else "native-alias-only" if module["abbreviation_ids"] else "native-empty"
    paths, kernels = _ADAPTER["_domains"](value)
    for resolver in value["resolvers"]:
        resolver["module_effects"] = [{"input": json.loads(path), "output": json.loads(path), "is_alias": False} for path in sorted(paths)]
        resolver["kernel_effects"] = [{"input": json.loads(kernel), "output": json.loads(kernel)} for kernel in sorted(kernels)]
    readings = {kind + ":" + name: "Module " + ("Type " if kind == "module-type" else "") + name + " := Struct End\n"
                for kind, name in _ADAPTER["reading_targets"](value)}
    return value, searches, readings


def _sealed(value: dict[str, Any], root: str, label: str) -> None:
    name = root + "." + label
    module = _module(value, name, root, "concrete-module")
    metadata = copy.deepcopy(value["fields"][0]["metadata"])
    _constant(value, name, metadata)
    declaration = value["declarations"][-1]
    link = declaration["implementation_connection"]
    source = copy.deepcopy(value["declarations"][0]["implementation_connection"]["source_field"])
    expression = {"tag": "MEident", "path": _path(root)}
    module["implementation"].update(kind="Algebraic", expression=expression)
    link.update(source_field=source, source_reference=_reference(root))
    link["steps"] = [{"tag": "module-alias", "source": _path(name), "target": _path(root), "expression": expression,
                      "resolver_id": name + ":resolver"},
                     {"tag": "structure-field", "field": source, "implementation_kind": "FullStruct", "resolver_id": name + ":resolver"},
                     {"tag": "substitution", "source": source, "target": link["instantiated_field"], "resolver_id": name + ":resolver"},
                     {"tag": "direct-lookup", "reference": declaration["native_reference"], "lookup_succeeded": True}]


def _controls_fixture() -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
    root = "CensusControls"
    value, searches, _ = _fixture(root)
    metadata = copy.deepcopy(value["fields"][0]["metadata"])
    _module(value, root + ".S", root, "module-type", kind="module-type")
    _constant(value, root + ".S", metadata, abstract=True)
    functor = _module(value, root + ".F", root, "concrete-module")
    parameter = _module(value, root + ".F.Parameter", None, "functor-parameter", kind="functor-parameter-signature")
    identifier = {"stamp": 1, "id": "X", "directory_reversed": [root]}
    bound = {"tag": "MPbound", "identifier": identifier}
    parameter.update(native_path=bound, query={"owner_root_id": root, "kind": "module", "target": root + ".F",
                                              "target_module_id": root + ".F", "coverage_path": [{"tag": "functor-parameter", "identifier": identifier}]})
    context = next(row for row in value["contexts"] if row["id"] == parameter["context_id"])
    context.update(parent_id=functor["context_id"], owner_path=bound, parameter_identifier=identifier,
                   parameter_signature_module_id=parameter["id"])
    next(row for row in value["resolvers"] if row["owner_module_id"] == parameter["id"])["root"] = bound
    result_context = {"id": root + ".F:result", "parent_id": context["id"], "kind": "functor-result", "owner_path": _path(root + ".F"),
                      "parameter_identifier": None, "parameter_signature_module_id": None}
    value["contexts"].append(result_context)
    functor["signature"].update(parameters=[{"identifier": identifier, "context_id": context["id"], "signature_module_id": parameter["id"]}],
                                result_context_id=result_context["id"])
    _constant(value, functor["id"], copy.deepcopy(metadata), abstract=True)
    for label in ("Sealed", "Applied", "HiddenSealed"):
        _sealed(value, root, label)
    _module(value, root + ".Empty", root, "concrete-module")
    alias = _module(value, root + ".AliasOnly", root, "concrete-module")
    alias["abbreviation_ids"] = ["control-alias"]
    value["abbreviations"].append({"id": "control-alias", "module_id": alias["id"], "exported_name": root + ".AliasOnly.alias",
                                   "native_abbreviation_path": root + ".AliasOnly.alias", "enabled": True, "only_parsing": False,
                                   "interpretation": {"kind": "direct-reference", "bound_variables": [], "target_reference": _reference("Foreign")}})
    for actual_root, label in (("SailStdpp.TypeCasts", "ZEqdep"), ("SailStdpp.State_monad", "NMap")):
        actual, actual_search, _ = _fixture(actual_root)
        _sealed(actual, actual_root, label)
        searches.update(actual_search)
        value["requested_roots"].append(actual_root)
        for table in ("roots", "modules", "fields", "declarations", "abbreviations", "resolvers", "contexts", "resolutions"):
            value[table].extend(actual[table])
    value["resolution_requests"] = _ADAPTER["parse_search_requests"](searches, expected_modules=value["requested_roots"])
    return _finish(value, searches)


class SailSupportCensusTests(unittest.TestCase):
    def test_canonical_rows_preserve_search_types_and_native_provenance(self) -> None:
        value, searches, readings = _fixture()
        searches["Root"] = searches["Root"].replace("Root.x:", "x:")
        value["resolution_requests"] = _ADAPTER["parse_search_requests"](searches, expected_modules=["Root"])
        result = _ADAPTER["census"](value, searches, readings, expected_modules=["Root"])["Root"]
        self.assertEqual(result["symbols"], [{"name": "Root.x", "type": "Prop", "assumptions": [], "claims": []}])
        self.assertEqual(result["raw_search"], searches["Root"])
        self.assertEqual(result["search_rows"][0]["spelling"], "x")
        self.assertEqual(result["declarations"], value["declarations"])
        # Census fields remain audited even when Search does not list them.
        value["resolution_requests"], value["resolutions"] = [], []
        searches["Root"] = proofaudit.EMPTY_BLACKLIST + "\n"
        result = _ADAPTER["census"](value, searches, readings, expected_modules=["Root"])["Root"]
        self.assertTrue(result["symbols"][0]["type"].startswith("native-constructor-json "))

    def test_interface_search_row_is_accounted_without_global_audit(self) -> None:
        value, searches, _ = _fixture()
        _module(value, "Root.S", "Root", "module-type", kind="module-type")
        _constant(value, "Root.S", copy.deepcopy(value["fields"][0]["metadata"]), abstract=True)
        searches["Root"] += "S.x: Prop\n"
        value["resolution_requests"] = _ADAPTER["parse_search_requests"](searches, expected_modules=["Root"])
        value["resolutions"].append({"request_id": "Root:1", "root_module_id": "Root", "candidates": [
            {"mode": "interface-field", "field_id": "Root.S:x", "declaration_id": "Root.S:x:declaration", "abbreviation_id": None,
             "reference": _reference("Root.S")} ]})
        value, searches, readings = _finish(value, searches)
        result = _ADAPTER["census"](value, searches, readings, expected_modules=["Root"])["Root"]
        self.assertEqual([row["name"] for row in result["symbols"]], ["Root.x"])
        self.assertEqual(len(result["interfaces"]), 1)
        value["resolutions"][-1]["candidates"][0]["mode"] = "global"
        with self.assertRaises(ValueError):
            _ADAPTER["census"](value, searches, readings, expected_modules=["Root"])

    def test_empty_and_direct_reference_alias_only_need_complete_native_bodies(self) -> None:
        value, searches, _ = _fixture()
        _module(value, "Root.Empty", "Root", "concrete-module")
        alias = _module(value, "Root.AliasOnly", "Root", "concrete-module")
        abbreviation = {"id": "alias", "module_id": "Root.AliasOnly", "exported_name": "Root.AliasOnly.alias",
                        "native_abbreviation_path": "Root.AliasOnly.alias", "enabled": True, "only_parsing": False,
                        "interpretation": {"kind": "direct-reference", "bound_variables": [], "target_reference": _reference("Foreign")}}
        alias["abbreviation_ids"] = ["alias"]
        value["abbreviations"].append(abbreviation)
        value, searches, readings = _finish(value, searches)
        result = _ADAPTER["census"](value, searches, readings, expected_modules=["Root"])["Root"]
        self.assertEqual(len(result["aliases"]), 1)
        self.assertEqual([row["name"] for row in result["symbols"]], ["Root.x"])
        alias["empty_evidence"] = "native-empty"
        with self.assertRaises(ValueError):
            _ADAPTER["census"](value, searches, readings, expected_modules=["Root"])

    def test_graph_provenance_and_resolver_domain_corruptions_refuse(self) -> None:
        value, searches, readings = _fixture()
        mutations = {
            "field omission": lambda item: item["fields"].clear(),
            "declaration omission": lambda item: item["declarations"].clear(),
            "duplicate": lambda item: item["declarations"].append(copy.deepcopy(item["declarations"][0])),
            "missing connection": lambda item: item["declarations"][0].update(implementation_connection=None),
            "empty trace": lambda item: item["declarations"][0]["implementation_connection"].update(steps=[]),
            "lookup absent": lambda item: item["declarations"][0]["implementation_connection"]["steps"].pop(),
            "reordered trace": lambda item: item["declarations"][0]["implementation_connection"]["steps"].reverse(),
            "changed source endpoint": lambda item: item["declarations"][0]["implementation_connection"]["source_field"].update(label="different"),
            "changed implementation metadata": lambda item: item["declarations"][0]["implementation_connection"]["instantiated_metadata"].update(inline_code=True),
            "wrong audit name": lambda item: item["declarations"][0]["implementation_connection"].update(audit_query_name="Foreign.x"),
            "foreign owned name": lambda item: item["declarations"][0]["native_reference"].update(canonical_name="Foreign.x"),
            "foreign field": lambda item: item["fields"][0].update(parent_module_id="Foreign"),
            "context cycle": lambda item: item["contexts"][0].update(parent_id="Root:context"),
            "context path": lambda item: item["contexts"][0].update(owner_path=_path("Foreign")),
            "module resolver domain": lambda item: item["resolvers"][0]["module_effects"].pop(),
            "kernel resolver domain": lambda item: item["resolvers"][0]["kernel_effects"].pop(),
            "ambiguous resolution": lambda item: item["resolutions"][0]["candidates"].append(copy.deepcopy(item["resolutions"][0]["candidates"][0])),
            "missing resolution": lambda item: item["resolutions"].clear(),
            "foreign resolution": lambda item: item["resolutions"][0]["candidates"][0].update(declaration_id="Foreign"),
            "changed field join": lambda item: item["resolutions"][0]["candidates"][0].update(field_id="Foreign"),
            "unproved emptiness": lambda item: item["modules"][0].update(empty_evidence="native-empty"),
            "unsupported native form": lambda item: item["fields"][0].update(kind="rewrite-rule"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                candidate = copy.deepcopy(value)
                mutate(candidate)
                with self.assertRaises(ValueError):
                    _ADAPTER["census"](candidate, searches, readings, expected_modules=["Root"])
        with self.assertRaises(ValueError):
            _ADAPTER["census"](value, searches, {}, expected_modules=["Root"])
        with self.assertRaises(ValueError):
            _ADAPTER["census"](value, {"Root": searches["Root"] + "Root.x: Prop\n"}, readings, expected_modules=["Root"])

    def test_raw_native_reading_headers_truncation_and_diagnostics_refuse(self) -> None:
        value, searches, _ = _fixture()
        for reading in ("", "Module Foreign := Struct End", "Module Root := Struct",
                        "Module Root := Struct ... End", "Module Root := Struct End\nWarning: refusal",
                        "Module Type Root := Sig End"):
            with self.subTest(reading=reading), self.assertRaises(ValueError):
                _ADAPTER["census"](value, searches, {"module:Root": reading}, expected_modules=["Root"])

    def test_schema_reader_matches_draft202012_on_positive_and_corruptions(self) -> None:
        value, _, _ = _fixture()
        oracle = Draft202012Validator(_SCHEMA)
        fixtures = [value]
        for name in value:
            candidate = copy.deepcopy(value)
            del candidate[name]
            fixtures.append(candidate)
        for table in ("roots", "modules", "fields", "declarations", "contexts", "resolvers", "resolutions"):
            candidate = copy.deepcopy(value)
            candidate[table][0]["unrecognized"] = True
            fixtures.append(candidate)
        candidate = copy.deepcopy(value)
        candidate["declarations"][0]["implementation_connection"]["lookup_succeeded"] = 1
        fixtures.append(candidate)
        candidate = copy.deepcopy(value)
        candidate["modules"][0]["signature"]["field_count"] = True
        fixtures.append(candidate)
        candidate = copy.deepcopy(value)
        candidate["modules"][0]["signature"]["field_count"] = 1.0
        fixtures.append(candidate)
        for index, fixture in enumerate(fixtures):
            with self.subTest(index=index):
                try:
                    _ADAPTER["validate_schema"](fixture)
                except ValueError:
                    accepted = False
                else:
                    accepted = True
                self.assertEqual(accepted, oracle.is_valid(fixture))
        # A new schema construct is a refusal until this strict reader is extended.
        changed_schema = copy.deepcopy(_SCHEMA)
        changed_schema["$defs"]["term"]["unevaluatedProperties"] = False
        with self.assertRaises(ValueError):
            _ADAPTER["validate_schema"](value, schema=changed_schema)

    def test_control_replay_uses_three_complete_roots_and_distinguishes_adapter_evidence(self) -> None:
        value, searches, readings = _controls_fixture()
        report = _ADAPTER["qualify_controls"](value, searches, readings)
        self.assertEqual(report["evidence_kind"], "adapter-over-native-emitted-evidence")
        self.assertEqual(len(report["positive"]), 7)
        self.assertEqual(len(report["refusals"]), 12)
        self.assertTrue(all(row["verdict"] == "refused" for row in report["refusals"].values()))
        # This call uses Python fixtures; its report does not claim native execution.
        self.assertNotIn("native-prover-verdict", report)


def cases() -> list[Case]:
    checks = SailSupportCensusTests()
    return [Case("canonical-census-preserves-raw-search-and-complete-native-fields", checks.test_canonical_rows_preserve_search_types_and_native_provenance),
            Case("signature-search-field-remains-interface-only", checks.test_interface_search_row_is_accounted_without_global_audit),
            Case("empty-and-alias-only-modules-require-native-provenance", checks.test_empty_and_direct_reference_alias_only_need_complete_native_bodies),
            Case("native-graph-and-resolver-domain-corruptions-refuse", checks.test_graph_provenance_and_resolver_domain_corruptions_refuse),
            Case("raw-native-reading-framing-diagnostics-and-truncation-refuse", checks.test_raw_native_reading_headers_truncation_and_diagnostics_refuse),
            Case("stdlib-schema-reader-agrees-with-draft202012-oracle", checks.test_schema_reader_matches_draft202012_on_positive_and_corruptions),
            Case("control-replay-retains-three-roots-and-adapter-refusal-boundary", checks.test_control_replay_uses_three_complete_roots_and_distinguishes_adapter_evidence)]
