# SPDX-License-Identifier: Apache-2.0
"""Python-only adapter fixtures; these supply no native census qualification."""

import copy
import json
import runpy
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from jsonschema import Draft202012Validator

from tests.harness import Case
from vos import proofaudit

_DIRECTORY = Path(__file__).resolve().parents[1] / "rocq-census"
_ADAPTER = runpy.run_path(str(_DIRECTORY / "census.py"))
_SCHEMA = json.loads((_DIRECTORY / "census-schema.json").read_text(encoding="utf-8"))

# Exact terminal line retained from candidate8 native-search-23.stdout.log.
# Rows below use fixture types; this records printer framing, not native qualification.
_NATIVE_ABOUT_FOOTER = (
    '(use "About" for full details on the implicit arguments of '
    "State_monad.NMap.Raw.Proofs.remove_min_gt_tree, State_monad.NMap.Raw.Proofs.L.PX.ltk_compat, "
    "State_monad.NMap.Raw.Proofs.PX.ltk_compat, State_monad.NMap.Raw.Proofs.PX.ltk_compat', "
    "State_monad.NMap.Raw.Proofs.lt_tree_node, State_monad.NMap.Raw.Proofs.gt_tree_node, "
    "State_monad.NMap.Raw.Proofs.L.PX.ltk_compat', State_monad.NMap.Raw.Proofs.lt_right, "
    "State_monad.NMap.Raw.Proofs.gt_left, State_monad.NMap.Raw.Proofs.gt_right, "
    "State_monad.NMap.Raw.Proofs.lt_left, State_monad.NMap.Raw.Proofs.MX.IsTO.lt_compat, "
    "State_monad.NMap.Raw.Proofs.PX.MO.IsTO.lt_compat, State_monad.NMap.Raw.Proofs.L.MX.lt_compat, "
    "State_monad.NMap.Raw.Proofs.split_lt_tree, State_monad.NMap.Raw.Proofs.PX.MO.lt_compat, "
    "State_monad.NMap.Raw.Proofs.MX.lt_compat, State_monad.NMap.Raw.Proofs.L.PX.MO.IsTO.lt_compat, "
    "State_monad.NMap.Raw.Proofs.L.PX.MO.lt_compat, State_monad.NMap.Raw.Proofs.L.MX.IsTO.lt_compat, "
    "State_monad.NMap.Raw.Proofs.split_gt_tree, State_monad.NMap.Raw.Proofs.gt_tree_trans, "
    "State_monad.NMap.Raw.Proofs.lt_tree_trans, State_monad.NMap.Raw.Proofs.is_empty_2, "
    "State_monad.NMap.Raw.Proofs.L.is_empty_2, State_monad.NMap.is_empty_2, "
    "State_monad.NMap.Raw.Proofs.gt_leaf, State_monad.NMap.Raw.Proofs.lt_leaf, "
    "State_monad.NMap.Raw.Proofs.empty_1, State_monad.NMap.Raw.Proofs.L.empty_1 and State_monad.NMap.empty_1)"
)


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


def _kernel_reference(module: str, label: str = "x") -> dict[str, Any]:
    reference = _reference(module, label)
    del reference["exported_name"], reference["canonical_name"]
    return reference


def _fixture(root: str = "Root") -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
    metadata = cast("dict[str, Any]", _example(_SCHEMA["$defs"]["constant_metadata"]))
    metadata.update(type={"tag": "Sort", "sort": {"tag": "Prop"}}, body_kind="Undef",
                    transparent_body=None, transparent_body_identity=None, inline_level=None, primitive=None)
    value = {"schema": "verifiedos-sail-support-census/1", "producer": "rocq-9.3.0-constructor-api",
             "requested_roots": [root], "roots": [{"requested": root, "native_path": _path(root), "module_id": root}],
             "modules": [], "fields": [], "declarations": [], "abbreviations": [], "resolvers": [],
             "contexts": [], "module_descents": [], "resolution_requests": [], "resolutions": [],
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
    link = {"lookup_succeeded": True, "enclosing_descent_ids": [], "exported_reference": reference, "source_field": locator,
            "instantiated_field": copy.deepcopy(locator), "source_reference": _kernel_reference(module_name),
            "implementation_reference": _kernel_reference(module_name), "source_metadata": metadata, "instantiated_metadata": copy.deepcopy(metadata),
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
    if not value["module_descents"]:
        modules = {module["id"]: module for module in value["modules"]}
        contexts = {context["id"]: context for context in value["contexts"]}
        fields = {field["id"]: field for field in value["fields"]}
        def abstract(context_id: str) -> bool:
            context = contexts[context_id]
            return context["kind"] in {"module-type", "functor-parameter", "functor-result"} or (
                context["parent_id"] is not None and abstract(context["parent_id"]))
        concrete = {module["id"] for module in value["modules"] if module["kind"] == "module"
                    and module["parent_field_id"] is not None and not abstract(module["signature"]["result_context_id"])}
        def raw_module(module_id: str) -> dict[str, Any]:
            module = modules[module_id]
            native_fields = [{"label": fields[key]["label"], "namespace": fields[key]["namespace"], "kind": fields[key]["kind"],
                              "metadata": copy.deepcopy(fields[key]["metadata"]),
                              "module": raw_module(fields[key]["child_module_id"]) if fields[key]["child_module_id"] is not None else None}
                             for key in module["signature"]["field_ids"]]
            signature = {"tag": "NoFunctor", "structure": {"path": module["native_path"], "field_count": len(native_fields), "fields": native_fields}}
            for parameter in reversed(module["signature"]["parameters"]):
                signature = {"tag": "MoreFunctor", "parameter_identifier": parameter["identifier"],
                             "parameter": raw_module(parameter["signature_module_id"]), "result": signature}
            return {"path": module["native_path"], "kind": "module-type" if module["kind"] != "module" else "module",
                    "signature": signature, "implementation": copy.deepcopy(module["implementation"])}
        for module in value["modules"]:
            if module["id"] not in concrete:
                continue
            field = fields[module["parent_field_id"]]
            parent = modules[field["parent_module_id"]]
            locator = {"module_path": parent["native_path"], "namespace": "module", "label": field["label"],
                       "packet_index": None, "constructor_index": None}
            raw = raw_module(module["id"])
            value["module_descents"].append({"id": module["id"] + ":descent", "owner_module_id": module["id"],
                "parent_descent_id": parent["id"] + ":descent" if parent["id"] in concrete else None,
                "field_selection_succeeded": True, "source_field": locator, "instantiated_field": copy.deepcopy(locator),
                "source_module": raw, "instantiated_module": copy.deepcopy(raw),
                "steps": [{"tag": "structure-field", "field": locator, "implementation_kind": "FullStruct",
                           "resolver_id": parent["implementation"]["resolver_id"]}]})
        for declaration in value["declarations"]:
            if declaration["implementation_connection"] is None:
                continue
            owner = fields[declaration["field_id"]]["parent_module_id"]
            chain = []
            while owner in concrete:
                chain.insert(0, owner + ":descent")
                owner = fields[modules[owner]["parent_field_id"]]["parent_module_id"]
            declaration["implementation_connection"]["enclosing_descent_ids"] = chain
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
    link.update(source_field=source, source_reference=_kernel_reference(root))
    link["steps"] = [{"tag": "module-alias", "source": _path(name), "target": _path(root), "expression": expression,
                      "resolver_id": name + ":resolver"},
                     {"tag": "structure-field", "field": source, "implementation_kind": "FullStruct", "resolver_id": name + ":resolver"},
                     {"tag": "substitution", "source": source, "target": link["instantiated_field"], "resolver_id": name + ":resolver"},
                     {"tag": "direct-lookup", "reference": declaration["native_reference"], "lookup_succeeded": True}]


def _controls_fixture(*, hidden_alias: bool = True) -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
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
    if hidden_alias:
        _sealed(value, root, "HiddenAlias")
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
    def test_native_terminal_about_notice_preserves_every_row_and_raw_footer(self) -> None:
        names = _NATIVE_ABOUT_FOOTER.split(" arguments of ", 1)[1][:-1].replace(" and ", ", ").split(", ")
        stdout = proofaudit.EMPTY_BLACKLIST + "\n" + "".join(name + ": Prop\n" for name in names)
        rows, footer = _ADAPTER["_search_evidence"](stdout + _NATIVE_ABOUT_FOOTER + "\n")
        self.assertEqual(len(rows), 31)
        self.assertEqual([row["spelling"] for row in rows], names)
        self.assertEqual([row["raw_lines"] for row in rows], [[name + ": Prop"] for name in names])
        self.assertTrue(all(row["type"] == "Prop" for row in rows))
        self.assertEqual(footer, {"raw": _NATIVE_ABOUT_FOOTER, "spellings": names})
        self.assertEqual(_ADAPTER["parse_search_requests"]({"Root": stdout}, expected_modules=["Root"]),
                         _ADAPTER["parse_search_requests"]({"Root": stdout + _NATIVE_ABOUT_FOOTER + "\n"},
                                                          expected_modules=["Root"]))
        for listed in ("Root.x", "Root.x and Root.Other.x"):
            with self.subTest(listed=listed):
                value, searches, readings = _fixture()
                notice = '(use "About" for full details on the implicit arguments of ' + listed + ")"
                if "Root.Other.x" in listed:
                    _module(value, "Root.Other", "Root", "concrete-module")
                    _constant(value, "Root.Other", copy.deepcopy(value["fields"][0]["metadata"]))
                    searches["Root"] += "Root.Other.x: Prop\n"
                    value["resolution_requests"] = _ADAPTER["parse_search_requests"](searches, expected_modules=["Root"])
                    value["resolutions"].append({"request_id": "Root:1", "root_module_id": "Root", "candidates": [
                        {"mode": "global", "field_id": "Root.Other:x", "declaration_id": "Root.Other:x:declaration",
                         "abbreviation_id": None, "reference": _reference("Root.Other")} ]})
                    value, searches, readings = _finish(value, searches)
                searches["Root"] += notice + "\n"
                result = _ADAPTER["census"](value, searches, readings, expected_modules=["Root"])["Root"]
                self.assertEqual(result["raw_search"], searches["Root"])
                self.assertEqual(result["search_footer"], {"raw": notice, "spellings": listed.split(" and ")})
                self.assertEqual(result["symbols"][0]["type"], "Prop")

    def test_about_notice_refuses_malformed_nonterminal_and_hidden_diagnostic_shapes(self) -> None:
        rows = proofaudit.EMPTY_BLACKLIST + "\nRoot.x: Prop\nRoot.y: Type\n"
        prefix = '(use "About" for full details on the implicit arguments of '
        notice = prefix + "Root.x and Root.y)"
        bad = {
            "missing close": rows + notice[:-1],
            "trailing text": rows + notice + " ignored",
            "wrong wording": rows + notice.replace("full details", "details"),
            "empty list": rows + prefix + ")",
            "comma without final and": rows + prefix + "Root.x, Root.y)",
            "Oxford comma": rows + prefix + "Root.x, and Root.y)",
            "duplicate name": rows + prefix + "Root.x and Root.x)",
            "unlisted name": rows + prefix + "Root.x and Foreign.z)",
            "no declaration rows": proofaudit.EMPTY_BLACKLIST + "\n" + notice,
            "repeated notice": rows + notice + "\n" + notice,
            "nonterminal row": rows + notice + "\nRoot.z: Prop\n",
            "nonterminal continuation": rows + notice + "\n  forall x, x\n",
            "indented notice": rows + "  " + notice,
            "multiline notice": rows + prefix + "Root.x\n and Root.y)",
            "unknown indented notice": rows + '  (use "Check" for details)\n',
        }
        for diagnostic in ("Error: omitted", "Warning: omitted", "Anomaly: omitted", "Fatal error: omitted",
                           'File "query.v", line 1, characters 0-1:'):
            for indentation in ("", "  "):
                bad[indentation + diagnostic] = rows + indentation + diagnostic + "\n" + notice
        for name, stdout in bad.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                _ADAPTER["parse_search_requests"]({"Root": stdout}, expected_modules=["Root"])

    def test_canonical_rows_preserve_search_types_and_native_provenance(self) -> None:
        value, searches, readings = _fixture()
        searches["Root"] = searches["Root"].replace("Root.x:", "x:")
        value["resolution_requests"] = _ADAPTER["parse_search_requests"](searches, expected_modules=["Root"])
        result = _ADAPTER["census"](value, searches, readings, expected_modules=["Root"])["Root"]
        self.assertEqual(result["symbols"], [{"name": "Root.x", "type": "Prop", "assumptions": [], "claims": []}])
        self.assertEqual(result["raw_search"], searches["Root"])
        self.assertEqual(result["search_rows"][0]["spelling"], "x")
        self.assertIsNone(result["search_footer"])
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
        self.assertEqual(result["alias_audits"], [{"source_kind": "abbreviation", "source_id": "alias",
                                                  "exported_spelling": "Root.AliasOnly.alias", "audit_query_name": "Foreign.x",
                                                  "native_reference": _reference("Foreign")}])
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
        self.assertEqual(len(report["positive"]), 8)
        self.assertEqual(report["positive"]["HiddenAlias"], "accepted")
        self.assertEqual(len(report["refusals"]), 12)
        self.assertTrue(all(row["verdict"] == "refused" for row in report["refusals"].values()))
        # This call uses Python fixtures; its report does not claim native execution.
        self.assertNotIn("native-prover-verdict", report)
        incomplete, raw, printed = _controls_fixture(hidden_alias=False)
        with self.assertRaisesRegex(ValueError, "positive-control population is incomplete"):
            _ADAPTER["qualify_controls"](incomplete, raw, printed)

    def test_control_mutations_share_untouched_evidence_and_match_whole_copy_refusals(self) -> None:
        value, searches, readings = _controls_fixture()
        # Native JSON has no Python cross-table aliases. Use that same small-fixture
        # shape to compare the former full-copy path with the bounded table copies.
        value = json.loads(json.dumps(value))
        original = copy.deepcopy(value)
        original_searches, original_readings = dict(searches), dict(readings)
        _ADAPTER["census"](value, searches, readings, expected_modules=value["requested_roots"])
        self.assertEqual(value, original)
        def mutable_ids(item: object) -> set[int]:
            if isinstance(item, dict):
                return {id(item)}.union(*(mutable_ids(child) for child in item.values()))
            if isinstance(item, list):
                return {id(item)}.union(*(mutable_ids(child) for child in item))
            return set()
        clone = _ADAPTER["_control_copy"]
        observed: list[str] = []
        def isolated_table(evidence: dict[str, Any], table: str) -> dict[str, Any]:
            self.assertIs(evidence, value)
            candidate = clone(evidence, table)
            self.assertIsNot(candidate, evidence)
            self.assertTrue(mutable_ids(candidate[table]).isdisjoint(mutable_ids(evidence[table])))
            for key in evidence.keys() - {table}:
                self.assertIs(candidate[key], evidence[key], key)
            # In particular, the full native resolver matrices and context graph
            # remain shared by identity, including their nested mutable objects.
            self.assertIs(candidate["resolvers"][0]["kernel_effects"], evidence["resolvers"][0]["kernel_effects"])
            self.assertIs(candidate["contexts"][0], evidence["contexts"][0])
            observed.append(table)
            return candidate
        qualify = _ADAPTER["qualify_controls"]
        with patch.dict(qualify.__globals__, {"_control_copy": isolated_table}):
            bounded = qualify(value, searches, readings)
        self.assertEqual(len(observed), 12)
        self.assertEqual(set(observed), {"fields", "declarations", "resolutions", "modules"})
        self.assertEqual(value, original)
        with patch.dict(qualify.__globals__, {"_control_copy": lambda evidence, _table: copy.deepcopy(evidence)}):
            former = qualify(value, searches, readings)
        self.assertEqual(bounded, former)
        self.assertEqual(value, original)
        self.assertEqual(searches, original_searches)
        self.assertEqual(readings, original_readings)
        for forbidden in ("resolvers", "contexts", "environment", "unknown"):
            with self.subTest(table=forbidden), self.assertRaises(ValueError):
                clone(value, forbidden)

    def test_body_identity_replaces_executable_ast_and_retains_complete_reference_domain(self) -> None:
        value, searches, _ = _fixture()
        identity = {"algorithm": "blake2b-256", "encoding": "verifiedos-rocq-native-term-json/1", "digest": "a" * 64,
                    "module_paths": [_path("Foreign"), _path("Foreign.Nested")],
                    "kernel_names": [{"path": _path("Foreign.Nested"), "label": "dependency"}]}
        for node in _ADAPTER["_nodes"](value):
            if "body_kind" in node:
                node.update(body_kind="Def", transparent_body_identity=copy.deepcopy(identity))
        value, searches, readings = _finish(value, searches)
        result = _ADAPTER["census"](value, searches, readings, expected_modules=["Root"])["Root"]
        self.assertIsNone(result["fields"][0]["metadata"]["transparent_body"])
        self.assertEqual(result["fields"][0]["metadata"]["transparent_body_identity"], identity)
        mutations = {
            "missing Def identity": lambda item: item["fields"][0]["metadata"].update(transparent_body_identity=None),
            "non-Def identity": lambda item: item["fields"][0]["metadata"].update(body_kind="Undef"),
            "executable AST": lambda item: item["fields"][0]["metadata"].update(transparent_body={"tag": "Rel", "index_one_based": 1}),
            "short digest": lambda item: item["fields"][0]["metadata"]["transparent_body_identity"].update(digest="a" * 63),
            "long digest": lambda item: item["fields"][0]["metadata"]["transparent_body_identity"].update(digest="a" * 65),
            "uppercase digest": lambda item: item["fields"][0]["metadata"]["transparent_body_identity"].update(digest="A" * 64),
            "nonhex digest": lambda item: item["fields"][0]["metadata"]["transparent_body_identity"].update(digest="z" * 64),
            "unapproved digest": lambda item: item["fields"][0]["metadata"]["transparent_body_identity"].update(algorithm="md5"),
            "omitted kernel module": lambda item: item["fields"][0]["metadata"]["transparent_body_identity"]["module_paths"].pop(),
            "omitted parent module": lambda item: item["fields"][0]["metadata"]["transparent_body_identity"]["module_paths"].pop(0),
            "wrong native key order": lambda item: item["fields"][0]["metadata"]["transparent_body_identity"]["module_paths"].reverse(),
            "duplicate body reference": lambda item: item["fields"][0]["metadata"]["transparent_body_identity"]["kernel_names"].append(copy.deepcopy(identity["kernel_names"][0])),
            "missing global body domain": lambda item: item["resolvers"][0]["kernel_effects"].pop(),
        }
        for name, mutate in mutations.items():
            candidate = copy.deepcopy(value)
            mutate(candidate)
            with self.subTest(name=name), self.assertRaises(ValueError):
                _ADAPTER["census"](candidate, searches, readings, expected_modules=["Root"])

    def test_private_kernel_references_cannot_replace_exported_globals(self) -> None:
        value, searches, _ = _fixture()
        value["modules"][0]["abbreviation_ids"] = ["private-boundary-alias"]
        value["abbreviations"].append({"id": "private-boundary-alias", "module_id": "Root", "exported_name": "Root.alias",
                                      "native_abbreviation_path": "Root.alias", "enabled": True, "only_parsing": False,
                                      "interpretation": {"kind": "direct-reference", "bound_variables": [],
                                                         "target_reference": _reference("Foreign")}})
        value, searches, readings = _finish(value, searches)
        result = _ADAPTER["census"](value, searches, readings, expected_modules=["Root"])["Root"]
        self.assertEqual([row["name"] for row in result["symbols"]], ["Root.x"])
        link = result["declarations"][0]["implementation_connection"]
        for name in ("source_reference", "implementation_reference"):
            self.assertEqual(set(link[name]), {"kind", "user", "canonical", "packet_index", "constructor_index"})
        self.assertEqual(result["alias_audits"][0]["audit_query_name"], "Foreign.x")
        mutations = {
            "source printable exported name": lambda item: item["declarations"][0]["implementation_connection"]["source_reference"].update(exported_name="Root.x"),
            "source printable canonical name": lambda item: item["declarations"][0]["implementation_connection"]["source_reference"].update(canonical_name="Root.x"),
            "instantiated printable name": lambda item: item["declarations"][0]["implementation_connection"]["implementation_reference"].update(exported_name="Root.x"),
            "source packet drift": lambda item: item["declarations"][0]["implementation_connection"]["source_reference"].update(packet_index=0),
            "instantiated constructor drift": lambda item: item["declarations"][0]["implementation_connection"]["implementation_reference"].update(constructor_index=1),
            "source kind drift": lambda item: item["declarations"][0]["implementation_connection"]["source_reference"].update(kind="inductive"),
            "private declaration global": lambda item: item["declarations"][0].update(native_reference=_kernel_reference("Root")),
            "private exported connection": lambda item: item["declarations"][0]["implementation_connection"].update(exported_reference=_kernel_reference("Root")),
            "private direct lookup": lambda item: item["declarations"][0]["implementation_connection"]["steps"][-1].update(reference=_kernel_reference("Root")),
            "private native resolution": lambda item: item["resolutions"][0]["candidates"][0].update(reference=_kernel_reference("Root")),
            "private abbreviation target": lambda item: item["abbreviations"][0]["interpretation"].update(target_reference=_kernel_reference("Foreign")),
        }
        for name, mutate in mutations.items():
            candidate = copy.deepcopy(value)
            mutate(candidate)
            with self.subTest(name=name), self.assertRaises(ValueError):
                _ADAPTER["census"](candidate, searches, readings, expected_modules=["Root"])

    def test_external_sealed_declaration_alias_has_supplementary_assumption_binding(self) -> None:
        value, searches, _ = _fixture()
        _sealed(value, "Root", "Alias")
        declaration = value["declarations"][-1]
        field = next(row for row in value["fields"] if row["id"] == declaration["field_id"])
        module = next(row for row in value["modules"] if row["id"] == field["parent_module_id"])
        field["classification"] = declaration["classification"] = "alias"
        target = _reference("Foreign.HiddenSealed")
        reference = declaration["native_reference"]
        reference.update(canonical=copy.deepcopy(target["canonical"]), canonical_name=target["canonical_name"])
        declaration["alias"] = {"kind": "module-alias", "exported_reference": reference, "target_reference": _kernel_reference("Foreign.HiddenSealed"),
                                "resolver_id": module["implementation"]["resolver_id"]}
        expression = {"tag": "MEident", "path": _path("Foreign.HiddenSealed")}
        module["implementation"]["expression"] = expression
        link = declaration["implementation_connection"]
        source = {"module_path": _path("Foreign.HiddenSealed"), "namespace": "object", "label": "x",
                  "packet_index": None, "constructor_index": None}
        link.update(source_field=source, source_reference=_kernel_reference("Foreign.HiddenSealed"), audit_query_name=target["canonical_name"])
        link["implementation_reference"].update(canonical=copy.deepcopy(target["canonical"]))
        declaration["alias"]["target_reference"] = copy.deepcopy(link["implementation_reference"])
        link["steps"][0].update(target=_path("Foreign.HiddenSealed"), expression=expression)
        link["steps"][1]["field"] = source
        link["steps"][2]["source"] = source
        value, searches, readings = _finish(value, searches)
        result = _ADAPTER["census"](value, searches, readings, expected_modules=["Root"])["Root"]
        self.assertEqual([row["name"] for row in result["symbols"]], ["Root.x"])
        self.assertEqual(result["alias_audits"], [{"source_kind": "declaration-alias", "source_id": declaration["id"],
                                                  "exported_spelling": "Root.Alias.x", "audit_query_name": "Foreign.HiddenSealed.x",
                                                  "native_reference": reference}])
        self.assertEqual(result["alias_obligations"], [])
        for replacement in (target, _kernel_reference("Foreign.HiddenSealed")):
            candidate = copy.deepcopy(value)
            candidate["declarations"][-1]["alias"]["target_reference"] = replacement
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                _ADAPTER["census"](candidate, searches, readings, expected_modules=["Root"])

    def test_bound_interface_abbreviation_remains_an_obligation(self) -> None:
        value, searches, _ = _fixture()
        signature = _module(value, "Root.S", "Root", "module-type", kind="module-type")
        identifier = {"stamp": 1, "id": "X", "directory_reversed": ["Root"]}
        bound = {"tag": "MPbound", "identifier": identifier}
        target = _reference("X")
        target["user"]["path"] = target["canonical"]["path"] = bound
        abbreviation = {"id": "abstract-alias", "module_id": "Root.S", "exported_name": "Root.S.alias",
                        "native_abbreviation_path": "Root.S.alias", "enabled": True, "only_parsing": False,
                        "interpretation": {"kind": "direct-reference", "bound_variables": [], "target_reference": target}}
        signature["abbreviation_ids"] = [abbreviation["id"]]
        value["abbreviations"].append(abbreviation)
        value, searches, readings = _finish(value, searches)
        result = _ADAPTER["census"](value, searches, readings, expected_modules=["Root"])["Root"]
        self.assertEqual(result["alias_audits"], [])
        self.assertEqual(result["alias_obligations"], [{"source_kind": "abbreviation", "source_id": "abstract-alias",
                                                       "exported_spelling": "Root.S.alias", "native_reference": target,
                                                       "context_id": signature["context_id"]}])
        # A concrete abbreviation cannot turn the bound target into a global query.
        root_module = value["modules"][0]
        concrete = copy.deepcopy(abbreviation)
        concrete.update(id="concrete-bound", module_id="Root", exported_name="Root.bound", native_abbreviation_path="Root.bound")
        root_module["abbreviation_ids"].append(concrete["id"])
        value["abbreviations"].append(concrete)
        with self.assertRaises(ValueError):
            _ADAPTER["census"](value, searches, readings, expected_modules=["Root"])

    def test_native_applied_functor_trace_keeps_full_expression_head_and_ordered_arguments(self) -> None:
        value, searches, _ = _fixture()
        _sealed(value, "Root", "Applied")
        declaration = value["declarations"][-1]
        link = declaration["implementation_connection"]
        module = next(row for row in value["modules"] if row["id"] == "Root.Applied")
        head = {"tag": "MEident", "path": _path("Foreign.F")}
        first = {"tag": "MEapply", "function": head, "argument": _path("Arguments.A")}
        second = {"tag": "MEapply", "function": first, "argument": _path("Arguments.B")}
        expression = {"tag": "MENoFunctor", "body": second}
        module["implementation"]["expression"] = expression
        source = copy.deepcopy(link["source_field"])
        source["module_path"] = _path("Foreign.F")
        link.update(source_field=source, source_reference=_kernel_reference("Foreign.F"))
        structure, substitution, lookup = copy.deepcopy(link["steps"][1:])
        structure["field"], substitution["source"] = source, source
        resolver = module["implementation"]["resolver_id"]
        link["steps"] = [{"tag": "module-alias", "source": _path("Root.Applied"), "target": _path("Foreign.F"),
                          "expression": expression, "resolver_id": resolver},
                         *[{"tag": "functor-application", "parameter_identifier": {"stamp": index, "id": name, "directory_reversed": ["Foreign"]},
                            "argument": prefix["argument"], "expression": prefix, "resolver_id": resolver}
                           for index, (name, prefix) in enumerate((("X", first), ("Y", second)), 1)],
                         structure, substitution, lookup]
        value, searches, readings = _finish(value, searches)
        result = _ADAPTER["census"](value, searches, readings, expected_modules=["Root"])["Root"]
        self.assertEqual([row["name"] for row in result["symbols"]], ["Root.Applied.x", "Root.x"])
        mutations = {
            "wrong head": lambda item: item["declarations"][-1]["implementation_connection"]["steps"][0].update(target=_path("Foreign.Other")),
            "wrong argument": lambda item: item["declarations"][-1]["implementation_connection"]["steps"][1].update(argument=_path("Arguments.B")),
            "swapped argument steps": lambda item: item["declarations"][-1]["implementation_connection"]["steps"].__setitem__(slice(1, 3),
                list(reversed(item["declarations"][-1]["implementation_connection"]["steps"][1:3]))),
            "omitted argument": lambda item: item["declarations"][-1]["implementation_connection"]["steps"].pop(2),
        }
        for name, mutate in mutations.items():
            candidate = copy.deepcopy(value)
            mutate(candidate)
            candidate, _, candidate_readings = _finish(candidate, searches)
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "native (?:alias|application) trace"):
                _ADAPTER["census"](candidate, searches, candidate_readings, expected_modules=["Root"])

    def test_nested_applied_module_keeps_original_parent_substitution_and_private_metadata(self) -> None:
        value, searches, _ = _fixture()
        _sealed(value, "Root", "Applied")
        _module(value, "Root.Applied.Raw", "Root.Applied", "concrete-module")
        instance = {"qualities": [], "levels": []}
        target_type = {"tag": "Const", "name": {key: _reference("Arguments.N", "T")[key] for key in ("user", "canonical")}, "instance": instance}
        identifier = {"stamp": 42, "id": "X", "directory_reversed": ["Foreign"]}
        bound_name = {"path": {"tag": "MPbound", "identifier": identifier}, "label": "T"}
        source_type = {"tag": "Const", "name": {"user": bound_name, "canonical": copy.deepcopy(bound_name)}, "instance": instance}
        metadata = copy.deepcopy(value["fields"][0]["metadata"])
        metadata["type"] = target_type
        _constant(value, "Root.Applied.Raw", metadata)
        _module(value, "Root.Applied.Raw.Inner", "Root.Applied.Raw", "concrete-module")
        expression = {"tag": "MEapply", "function": {"tag": "MEident", "path": _path("Foreign.Make")}, "argument": _path("Arguments.N")}
        applied = next(module for module in value["modules"] if module["id"] == "Root.Applied")
        applied["implementation"]["expression"] = expression
        parent_link = next(row for row in value["declarations"] if row["field_id"] == "Root.Applied:x")["implementation_connection"]
        parent_source = copy.deepcopy(parent_link["source_field"])
        parent_source["module_path"] = _path("Foreign.Make")
        parent_link.update(source_field=parent_source, source_reference=_kernel_reference("Foreign.Make"))
        parent_link["steps"][0].update(expression=expression, target=_path("Foreign.Make"))
        parent_link["steps"][1]["field"] = parent_link["steps"][2]["source"] = parent_source
        parent_link["steps"].insert(1, {"tag": "functor-application", "parameter_identifier": identifier,
                                        "argument": expression["argument"], "expression": expression, "resolver_id": "Root.Applied:resolver"})
        value, searches, _ = _finish(value, searches)
        raw_descent = next(row for row in value["module_descents"] if row["owner_module_id"] == "Root.Applied.Raw")
        inner_descent = next(row for row in value["module_descents"] if row["owner_module_id"] == "Root.Applied.Raw.Inner")
        def rebase(item: object) -> Any:  # noqa: ANN401 - recursive fixture JSON
            if item == _path("Root.Applied.Raw"):
                return _path("Foreign.Make.Raw")
            if isinstance(item, dict):
                return {key: rebase(child) for key, child in item.items()}
            if isinstance(item, list):
                return [rebase(child) for child in item]
            return item
        raw_descent["source_module"] = rebase(raw_descent["source_module"])
        raw_descent["source_module"]["signature"]["structure"]["fields"][0]["metadata"]["type"] = source_type
        raw_descent["source_field"]["module_path"] = _path("Foreign.Make")
        raw_source = raw_descent["source_field"]
        raw_descent["steps"] = [*copy.deepcopy(parent_link["steps"][:2]),
            {"tag": "structure-field", "field": raw_source, "implementation_kind": "FullStruct", "resolver_id": "Root.Applied:resolver"},
            {"tag": "substitution", "source": raw_source, "target": raw_descent["instantiated_field"], "resolver_id": "Root.Applied:resolver"}]
        # The next ordinary descent selects both complete private Raw bodies.
        inner_descent["source_module"] = rebase(inner_descent["source_module"])
        inner_descent["source_field"]["module_path"] = _path("Foreign.Make.Raw")
        inner_descent["steps"][0]["field"] = inner_descent["source_field"]
        inner_descent["steps"].append({"tag": "substitution", "source": inner_descent["source_field"],
            "target": inner_descent["instantiated_field"], "resolver_id": "Root.Applied.Raw:resolver"})
        raw_link = next(row for row in value["declarations"] if row["field_id"] == "Root.Applied.Raw:x")["implementation_connection"]
        raw_source_object = copy.deepcopy(raw_link["source_field"])
        raw_source_object["module_path"] = _path("Foreign.Make.Raw")
        raw_link.update(source_field=raw_source_object, source_reference=_kernel_reference("Foreign.Make.Raw"),
                        source_metadata=copy.deepcopy(raw_descent["source_module"]["signature"]["structure"]["fields"][0]["metadata"]))
        raw_link["steps"][0]["field"] = raw_source_object
        raw_link["steps"].insert(1, {"tag": "substitution", "source": raw_source_object, "target": raw_link["instantiated_field"],
                                    "resolver_id": "Root.Applied.Raw:resolver"})
        value, searches, readings = _finish(value, searches)
        result = _ADAPTER["census"](value, searches, readings, expected_modules=["Root"])["Root"]
        self.assertEqual(len(result["module_descents"]), 3)
        self.assertNotEqual(raw_link["source_metadata"]["type"], raw_link["instantiated_metadata"]["type"])
        self.assertEqual(raw_link["enclosing_descent_ids"], ["Root.Applied:descent", "Root.Applied.Raw:descent"])
        mutations = {
            "missing parent descent": lambda item: item["module_descents"].pop(0),
            "missing direct parent": lambda item: item["module_descents"][1].update(parent_descent_id=None),
            "swapped enclosing chain": lambda item: item["declarations"][-1]["implementation_connection"]["enclosing_descent_ids"].reverse(),
            "omitted enclosing parent": lambda item: item["declarations"][-1]["implementation_connection"]["enclosing_descent_ids"].pop(0),
            "omitted aggregate substitution": lambda item: item["module_descents"][1]["steps"].pop(),
            "swapped aggregate endpoints": lambda item: item["module_descents"][1]["steps"][-1].update(
                source=copy.deepcopy(raw_descent["instantiated_field"]), target=copy.deepcopy(raw_descent["source_field"])),
            "lost original metadata": lambda item: item["module_descents"][1]["source_module"]["signature"]["structure"]["fields"][0]["metadata"].update(type=target_type),
            "wrong original inner module": lambda item: item["module_descents"][-1].update(source_module=copy.deepcopy(inner_descent["instantiated_module"])),
            "wrong child namespace": lambda item: item["module_descents"][1]["source_field"].update(namespace="object"),
        }
        def substituted_as_original(item: dict[str, Any]) -> None:
            descent = item["module_descents"][1]
            descent["source_module"] = copy.deepcopy(descent["instantiated_module"])
            descent["source_field"] = copy.deepcopy(descent["instantiated_field"])
            descent["steps"][2]["field"] = descent["source_field"]
            descent["steps"].pop()
        mutations["substituted child as original"] = substituted_as_original
        for name, mutate in mutations.items():
            candidate = copy.deepcopy(value)
            mutate(candidate)
            with self.subTest(name=name), self.assertRaises(ValueError):
                _ADAPTER["census"](candidate, searches, readings, expected_modules=["Root"])


def cases() -> list[Case]:
    checks = SailSupportCensusTests()
    return [Case("canonical-census-preserves-raw-search-and-complete-native-fields", checks.test_canonical_rows_preserve_search_types_and_native_provenance),
            Case("native-terminal-about-notice-preserves-rows-and-raw-footer", checks.test_native_terminal_about_notice_preserves_every_row_and_raw_footer),
            Case("about-notice-refuses-malformed-nonterminal-and-hidden-diagnostic-shapes", checks.test_about_notice_refuses_malformed_nonterminal_and_hidden_diagnostic_shapes),
            Case("signature-search-field-remains-interface-only", checks.test_interface_search_row_is_accounted_without_global_audit),
            Case("empty-and-alias-only-modules-require-native-provenance", checks.test_empty_and_direct_reference_alias_only_need_complete_native_bodies),
            Case("native-graph-and-resolver-domain-corruptions-refuse", checks.test_graph_provenance_and_resolver_domain_corruptions_refuse),
            Case("raw-native-reading-framing-diagnostics-and-truncation-refuse", checks.test_raw_native_reading_headers_truncation_and_diagnostics_refuse),
            Case("stdlib-schema-reader-agrees-with-draft202012-oracle", checks.test_schema_reader_matches_draft202012_on_positive_and_corruptions),
            Case("control-replay-retains-three-roots-and-adapter-refusal-boundary", checks.test_control_replay_uses_three_complete_roots_and_distinguishes_adapter_evidence),
            Case("control-mutations-share-native-evidence-and-match-whole-copy-refusals", checks.test_control_mutations_share_untouched_evidence_and_match_whole_copy_refusals),
            Case("body-identities-refuse-executable-asts-and-incomplete-reference-domains", checks.test_body_identity_replaces_executable_ast_and_retains_complete_reference_domain),
            Case("private-kernel-reference-boundary-retains-exported-global-audits", checks.test_private_kernel_references_cannot_replace_exported_globals),
            Case("external-sealed-declaration-alias-keeps-supplementary-native-audit", checks.test_external_sealed_declaration_alias_has_supplementary_assumption_binding),
            Case("bound-interface-abbreviation-remains-an-obligation", checks.test_bound_interface_abbreviation_remains_an_obligation),
            Case("applied-functor-trace-preserves-native-head-and-ordered-arguments", checks.test_native_applied_functor_trace_keeps_full_expression_head_and_ordered_arguments),
            Case("nested-applied-module-preserves-original-parent-substitutions", checks.test_nested_applied_module_keeps_original_parent_substitution_and_private_metadata)]
