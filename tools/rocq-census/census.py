# SPDX-License-Identifier: Apache-2.0
"""Replay the native support census without changing the common inventory guard.

This module is deliberately stdlib-only: the cold hosted route runs before a tools
environment exists. Its schema reader supports exactly the vocabulary used by the
checked-in schema, and refuses an unfamiliar keyword rather than ignoring it.
Native provenance is input evidence; acceptance additionally needs the runner's
unchanged-input, native-control, exact-assumption and recursive-kernel joins.
"""

import copy
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

from vos import proofaudit

SCHEMA = Path(__file__).with_name("census-schema.json")
_KEYWORDS = {"$schema", "$id", "$defs", "$ref", "title", "description", "type",
             "const", "enum", "oneOf", "anyOf", "properties", "required",
             "additionalProperties", "items", "minItems", "maxItems", "uniqueItems",
             "minLength", "minimum", "maximum", "pattern"}
_ROW = re.compile(r"^([\w']+(?:\.[\w']+)*):\s*(.*)$")
_ABSTRACT = {"module-type", "functor-parameter", "functor-result"}


class CensusError(ValueError):
    """Incomplete or inconsistent native evidence cannot establish a census."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CensusError(message)


def _key(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _schema_vocabulary(schema: dict[str, Any]) -> None:
    """Check the schema itself, including branches a particular value never uses."""
    _require(not schema.keys() - _KEYWORDS, "unsupported census schema keyword")
    _require("pattern" not in schema or schema["pattern"] in {r"^[0-9]+$", r"^(?:[0-9a-f]{2})*$"},
             "unsupported census schema pattern")
    _require("type" not in schema or schema["type"] in {"object", "array", "string", "integer", "boolean", "null"},
             "unsupported census schema type")
    for name in ("$defs", "properties"):
        for child in schema.get(name, {}).values():
            _schema_vocabulary(child)
    for name in ("oneOf", "anyOf"):
        for child in schema.get(name, []):
            _schema_vocabulary(child)
    if "items" in schema:
        _schema_vocabulary(schema["items"])
    _require(schema.get("additionalProperties", False) is False,
             "unsupported census schema additionalProperties")


def _validate(value: object, schema: dict[str, Any], document: dict[str, Any], site: str) -> None:
    if "$ref" in schema:
        reference = schema["$ref"]
        _require(reference.startswith("#/$defs/") and reference[8:] in document["$defs"],
                 "unsupported census schema reference")
        _validate(value, document["$defs"][reference[8:]], document, site)
    for keyword, exact in (("oneOf", True), ("anyOf", False)):
        if keyword not in schema:
            continue
        passed = 0
        for branch in schema[keyword]:
            try:
                _validate(value, branch, document, site)
            except CensusError:
                continue
            passed += 1
        _require(passed == 1 if exact else passed > 0, f"{site}: no unique schema shape")
    if "const" in schema:
        _require(_key(value) == _key(schema["const"]), f"{site}: unexpected constant")
    if "enum" in schema:
        _require(_key(value) in {_key(item) for item in schema["enum"]},
                 f"{site}: unsupported native shape")
    if "type" in schema:
        kinds = {"object": isinstance(value, dict), "array": isinstance(value, list),
                 "string": isinstance(value, str), "integer": type(value) is int or (type(value) is float and value.is_integer()),
                 "boolean": type(value) is bool, "null": value is None}
        _require(schema["type"] in kinds and kinds[schema["type"]],
                 f"{site}: incorrect native value type")
    if isinstance(value, dict):
        _require(set(schema.get("required", [])) <= value.keys(), f"{site}: missing native member")
        properties = schema.get("properties")
        if properties is not None:
            if schema.get("additionalProperties") is False:
                _require(not value.keys() - properties.keys(), f"{site}: unexpected native member")
            for name in value.keys() & properties.keys():
                _validate(value[name], properties[name], document, site + "." + name)
    if isinstance(value, list):
        _require(len(value) >= schema.get("minItems", 0), f"{site}: incomplete native array")
        _require("maxItems" not in schema or len(value) <= schema["maxItems"],
                 f"{site}: ambiguous native array")
        if schema.get("uniqueItems"):
            _require(len({_key(item) for item in value}) == len(value), f"{site}: duplicate native member")
        if "items" in schema:
            for index, item in enumerate(value):
                _validate(item, schema["items"], document, f"{site}[{index}]")
    if isinstance(value, str):
        _require(len(value) >= schema.get("minLength", 0), f"{site}: empty native string")
        if "pattern" in schema:
            _require(re.search(schema["pattern"], value) is not None, f"{site}: invalid native string encoding")
    if type(value) in {int, float}:
        _require("minimum" not in schema or value >= schema["minimum"], f"{site}: invalid native index")
        _require("maximum" not in schema or value <= schema["maximum"], f"{site}: invalid native index")


def validate_schema(value: object, *, schema: dict[str, Any] | None = None) -> dict[str, Any]:
    """Strict schema validation; the focused tests compare this reader with Draft 2020-12."""
    definition = json.loads(SCHEMA.read_text(encoding="utf-8")) if schema is None else schema
    try:
        _schema_vocabulary(definition)
        _validate(value, definition, definition, "census")
    except (RecursionError, KeyError, TypeError) as error:
        raise CensusError("unsupported or excessively nested census/schema") from error
    return cast("dict[str, Any]", value)


def _search(stdout: str) -> list[dict[str, Any]]:
    lines = stdout.splitlines()
    _require(bool(lines) and lines[0].strip() == proofaudit.EMPTY_BLACKLIST,
             "Rocq did not confirm an empty search blacklist")
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in lines[1:]:
        if not line.strip():
            continue
        match = _ROW.fullmatch(line)
        if match:
            spelling, typ = match.groups()
            _require(spelling not in seen, f"duplicate native Search row {spelling}")
            seen.add(spelling)
            found.append({"row_index": len(found), "spelling": spelling, "type": typ,
                          "raw_lines": [line]})
        elif line[:1].isspace() and found:
            found[-1]["type"] += " " + line.strip()
            found[-1]["raw_lines"].append(line)
        else:
            raise CensusError(f"unrecognized native Search output: {line}")
    _require(all(row["type"] for row in found), "a native Search row has no type")
    return found


def parse_search_requests(searches: dict[str, str], *, expected_modules: list[str]) -> list[dict[str, Any]]:
    _require(bool(expected_modules) and len(set(expected_modules)) == len(expected_modules),
             "missing or duplicate requested roots")
    _require(set(searches) == set(expected_modules), "Search population differs from requested roots")
    return [{"id": f"{root}:{row['row_index']}", "requested_root": root,
             "row_index": row["row_index"], "spelling": row["spelling"]}
            for root in expected_modules for row in _search(searches[root])]


def reading_targets(metadata: object) -> list[tuple[str, str]]:
    value = validate_schema(metadata)
    return list(dict.fromkeys((module["query"]["kind"], module["query"]["target"])
                              for module in value["modules"]))


def _reading(text: str, kind: str, target: str) -> None:
    """Check the locked printer's framing without interpreting printed term syntax."""
    _require(isinstance(text, str) and bool(text.strip()), "missing complete native module reading")
    header = re.match(r"\s*Module\s+(Type\s+)?([\w']+(?:\.[\w']+)*)\s*(?=[:=(])", text)
    suffixes = {".".join(target.split(".")[index:]) for index in range(len(target.split(".")))}
    _require(header is not None and header.group(2) in suffixes
             and bool(header.group(1)) == (kind == "module-type"), "native module reading header differs from query")
    # Strings can contain punctuation/keywords that are not printer framing.
    framed = re.sub(r'"(?:[^"]|"")*"', '""', text)
    _require("..." not in framed and "…" not in framed and "<elided>" not in framed,
             "truncated native module reading")
    _require(re.search(r"(?m)^\s*(?:Error|Warning|Anomaly|Fatal error)\s*[:!]", framed) is None,
             "native module reading contains a diagnostic")
    depth = 0
    for keyword in re.findall(r"(?<![\w'])\b(?:Struct|Sig|End)\b(?![\w'])", framed):
        depth += -1 if keyword == "End" else 1
        _require(depth >= 0, "native module reading has an unmatched closing body")
    _require(depth == 0, "native module reading is missing its closing body")


def _table(value: dict[str, Any], name: str) -> dict[str, dict[str, Any]]:
    rows = value[name]
    result = {row["id"]: row for row in rows}
    _require(len(result) == len(rows), f"duplicate {name} ID")
    return result


def _path(path: dict[str, Any]) -> str:
    if path["tag"] == "MPfile":
        return ".".join(reversed(cast("list[str]", path["directory_reversed"])))
    if path["tag"] == "MPdot":
        return _path(path["parent"]) + "." + cast("str", path["label"])
    raise CensusError("a bound module has no global query name")


def _nodes(value: object) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _nodes(child)


def _domains(value: dict[str, Any]) -> tuple[set[str], set[str]]:
    paths: set[str] = set()
    kernels: set[str] = set()
    domain = {key: item for key, item in value.items() if key != "resolvers"}
    domain["resolver_roots_and_inlines"] = [{"root": row["root"], "inline_keys": row["inline_keys"]}
                                            for row in value["resolvers"]]
    for node in _nodes(domain):
        if node.get("tag") in {"MPfile", "MPbound", "MPdot"}:
            paths.add(_key(node))
        if node.keys() == {"path", "label"}:
            kernels.add(_key(node))
    return paths, kernels


def _native_semantics(value: dict[str, Any]) -> None:
    """Cross-check repeated counts/body discriminators in all nested native metadata."""
    for node in _nodes(value):
        if {"field_count", "fields"} <= node.keys():
            _require(node["field_count"] == len(node["fields"]), "incomplete native structure fields")
            keys = [(field["namespace"], field["label"]) for field in node["fields"]]
            _require(len(set(keys)) == len(keys), "duplicate native structure namespace/label")
        if {"packet_count", "packets"} <= node.keys():
            _require(node["packet_count"] == len(node["packets"]), "incomplete inductive packets")
        if {"constructor_count", "constructors"} <= node.keys():
            _require(node["constructor_count"] == len(node["constructors"]), "incomplete inductive constructors")
        if "body_kind" in node:
            _require((node["transparent_body"] is not None) == (node["body_kind"] == "Def"),
                     "constant body discriminator disagrees with native body")
            _require((node["primitive"] is not None) == (node["body_kind"] == "Primitive"),
                     "primitive discriminator disagrees with native body")
            _require(node["inline_level"] is None or node["body_kind"] == "Undef",
                     "inline level on a non-abstract body")
        if {"kind", "expression", "structure", "algebraic_type", "resolver_id"} == node.keys():
            kind = node["kind"]
            _require((node["expression"] is not None) == (kind == "Algebraic"),
                     "implementation expression discriminator disagrees")
            _require((node["structure"] is not None) == (kind == "Struct"),
                     "implementation structure discriminator disagrees")


def _census(metadata: object, searches: dict[str, str], readings: dict[str, str], *,
            expected_modules: list[str]) -> dict[str, dict[str, Any]]:
    """Return canonical guarded symbols and replayable, complete per-root provenance."""
    value = validate_schema(metadata)
    _require(value["requested_roots"] == expected_modules, "native requested population differs")
    _require([root["requested"] for root in value["roots"]] == expected_modules,
             "native root population/order differs")
    requests = parse_search_requests(searches, expected_modules=expected_modules)
    _require(value["resolution_requests"] == requests, "native requests differ from original Search rows")
    modules, fields, declarations, abbreviations, contexts, resolvers = (
        _table(value, name) for name in ("modules", "fields", "declarations", "abbreviations", "contexts", "resolvers"))
    _native_semantics(value)
    root_ids = {root["requested"]: root["module_id"] for root in value["roots"]}
    _require(len(set(root_ids.values())) == len(root_ids), "duplicate native roots")
    for root in value["roots"]:
        _require(root["module_id"] in modules, "missing native root module")
        module = modules[root["module_id"]]
        _require(root["native_path"] == module["native_path"] and _path(root["native_path"]) == root["requested"],
                 "native root ownership/path differs")
        _require(module["parent_field_id"] is None and module["kind"] == "module",
                 "a requested root is not an independent module")

    ancestry: dict[str, list[dict[str, Any]]] = {}
    def context_chain(identifier: str, pending: set[str] | None = None) -> list[dict[str, Any]]:
        if identifier in ancestry:
            return ancestry[identifier]
        active = set() if pending is None else pending
        _require(identifier in contexts and identifier not in active, "missing or cyclic native context")
        context = contexts[identifier]
        parent = context["parent_id"]
        chain = ([] if parent is None else context_chain(parent, active | {identifier})) + [context]
        ancestry[identifier] = chain
        return chain
    for identifier in contexts:
        context_chain(identifier)
        context = contexts[identifier]
        if context["kind"] != "functor-parameter":
            _require(context["parameter_identifier"] is None and context["parameter_signature_module_id"] is None,
                     "non-parameter context claims a bound signature")

    owners: dict[str, str] = {}
    def visit(identifier: str, root: str, active: set[str]) -> None:
        _require(identifier in modules and identifier not in active and identifier not in owners,
                 "missing, duplicate or cyclic module population")
        owners[identifier] = root
        module = modules[identifier]
        signature = module["signature"]
        ids = signature["field_ids"]
        _require(signature["field_count"] == len(ids), "omitted native module field")
        _require(set(ids) == {key for key, field in fields.items() if field["parent_module_id"] == identifier},
                 "native field population differs from its owner")
        namespace_labels: set[tuple[str, str]] = set()
        _require(module["context_id"] in contexts and signature["result_context_id"] in contexts,
                 "missing module context")
        _require(contexts[module["context_id"]]["owner_path"] == module["native_path"],
                 "module context belongs to another native path")
        base = module["context_id"]
        for parameter in signature["parameters"]:
            context = contexts.get(parameter["context_id"], {})
            _require(context.get("kind") == "functor-parameter" and context.get("parent_id") == base
                     and context.get("parameter_identifier") == parameter["identifier"]
                     and context.get("parameter_signature_module_id") == parameter["signature_module_id"],
                     "functor parameter context chain differs")
            child = modules.get(parameter["signature_module_id"], {})
            _require(child.get("kind") == "functor-parameter-signature"
                     and child.get("parent_field_id") is None and child.get("context_id") == parameter["context_id"],
                     "missing native functor parameter signature")
            _require(child["native_path"] == {"tag": "MPbound", "identifier": parameter["identifier"]},
                     "functor parameter lost its native bound path")
            visit(parameter["signature_module_id"], root, active | {identifier})
            base = parameter["context_id"]
        result_context = contexts[signature["result_context_id"]]
        if signature["parameters"]:
            _require(result_context["kind"] == "functor-result" and result_context["parent_id"] == base,
                     "functor result lost its formal context")
            _require(result_context["owner_path"] == module["native_path"], "functor result belongs to another module")
        else:
            _require(signature["result_context_id"] == module["context_id"], "unexpected result context")
        for field_id in ids:
            field = fields[field_id]
            key = field["namespace"], field["label"]
            _require(key not in namespace_labels, "duplicate native field namespace/label")
            namespace_labels.add(key)
            _require(field["context_id"] == signature["result_context_id"], "field context differs from native signature")
            abstract = field["kind"] == "module-type" or any(context["kind"] in _ABSTRACT for context in context_chain(field["context_id"]))
            _require((field["classification"] == "interface") == abstract, "signature field treated as a global declaration")
            is_module = field["kind"] in {"module", "module-type"}
            _require(field["namespace"] == ("module" if is_module else "object"), "native namespace differs from field kind")
            _require((field["metadata"] is None) == is_module and (field["child_module_id"] is not None) == is_module,
                     "native field payload differs from kind")
            if is_module:
                _require(not field["declaration_ids"], "module field owns a global declaration")
                child = modules.get(field["child_module_id"], {})
                _require(child.get("parent_field_id") == field_id and child.get("kind") == field["kind"],
                         "missing nested module/type")
                child_context = contexts.get(child.get("context_id"), {})
                expected_kind = "module-type" if field["kind"] == "module-type" else "concrete-module"
                _require(child_context.get("kind") == expected_kind and child_context.get("parent_id") == field["context_id"],
                         "nested module context differs")
                expected_path = {"tag": "MPdot", "parent": module["native_path"], "label": field["label"]}
                _require(child.get("native_path") == expected_path, "nested module path differs from field")
                visit(field["child_module_id"], root, active | {identifier})
            else:
                _require(field["metadata"]["kind"] == field["kind"], "field metadata differs from native kind")
        aliases = [row["id"] for row in value["abbreviations"] if row["module_id"] == identifier]
        _require(set(module["abbreviation_ids"]) == set(aliases), "incomplete native abbreviation population")
        expected_empty = "nonempty" if ids else "native-alias-only" if aliases else "native-empty"
        _require(module["empty_evidence"] == expected_empty, "unproved empty native module")
    for requested, identifier in root_ids.items():
        context = contexts.get(modules[identifier]["context_id"], {})
        _require(context.get("kind") == "concrete-root" and context.get("parent_id") is None,
                 "root context is not concrete")
        visit(identifier, requested, set())
    _require(set(owners) == set(modules), "orphan native module")
    used_contexts = {context["id"] for module in modules.values()
                     for context in context_chain(module["signature"]["result_context_id"])}
    _require(used_contexts == set(contexts), "orphan native context")

    # Complete raw readings are retained separately from structural provenance.
    targets = reading_targets(value)
    _require(set(readings) == {kind + ":" + name for kind, name in targets}, "missing or foreign module readings")
    for kind, name in targets:
        _require(bool(proofaudit.QUALIFIED.fullmatch(name)) or bool(re.fullmatch(r"[\w']+", name)),
                 "invalid native module reading target")
        _reading(readings[kind + ":" + name], kind, name)
    for module in modules.values():
        query = module["query"]
        target = modules.get(query["target_module_id"], {})
        _require(query["owner_root_id"] == root_ids[owners[module["id"]]] and bool(target),
                 "module reading has a foreign owner")
        _require(_path(target["native_path"]) == query["target"]
                 and query["kind"] == ("module-type" if target["kind"] == "module-type" else "module"),
                 "module reading target differs from native provenance")
        current = target
        for step in query["coverage_path"]:
            if step["tag"] == "field":
                matches = [fields[key] for key in current["signature"]["field_ids"]
                           if (fields[key]["namespace"], fields[key]["label"]) == (step["namespace"], step["label"])]
                _require(len(matches) == 1 and matches[0]["child_module_id"] is not None,
                         "native reading coverage omits a nested module")
                current = modules[matches[0]["child_module_id"]]
            else:
                parameters = [parameter for parameter in current["signature"]["parameters"]
                              if parameter["identifier"] == step["identifier"]]
                _require(len(parameters) == 1, "native reading coverage omits a functor context")
                if step["tag"] == "functor-parameter":
                    current = modules[parameters[0]["signature_module_id"]]
        _require(current["id"] == module["id"], "module reading coverage reaches another field")

    paths, kernels = _domains(value)
    for resolver in resolvers.values():
        _require(resolver["owner_module_id"] in modules, "foreign native resolver")
        inputs = [_key(effect["input"]) for effect in resolver["module_effects"]]
        _require(len(inputs) == len(set(inputs)) and set(inputs) == paths, "incomplete native resolver module domain")
        inputs = [_key(effect["input"]) for effect in resolver["kernel_effects"]]
        _require(len(inputs) == len(set(inputs)) and set(inputs) == kernels, "incomplete native resolver kernel domain")
    for module in modules.values():
        resolver = resolvers.get(module["implementation"]["resolver_id"], {})
        _require(resolver.get("owner_module_id") == module["id"], "module implementation names a foreign resolver")
    for node in _nodes({key: item for key, item in value.items() if key != "resolvers"}):
        if "resolver_id" in node:
            _require(node["resolver_id"] in resolvers, "missing native resolver connection")

    def connection(declaration: dict[str, Any], field: dict[str, Any]) -> None:
        reference, link = declaration["native_reference"], declaration["implementation_connection"]
        _require(reference is not None and link is not None, "missing concrete implementation connection")
        _require(reference["kind"] == declaration["kind"] and reference["exported_name"] == declaration["exported_name"]
                 and reference["packet_index"] == declaration["packet_index"]
                 and reference["constructor_index"] == declaration["constructor_index"], "native declaration reference differs")
        for key in ("user", "canonical"):
            # Inductive/constructor printable names use packet/constructor labels,
            # while the native kernel name identifies their mutual block.
            printable = reference["exported_name" if key == "user" else "canonical_name"]
            _require(printable == _path(reference[key]["path"]) + "." + declaration["label"],
                     "native printable reference differs from structural name")
        _require(link["exported_reference"] == reference and link["audit_query_name"] == reference["canonical_name"],
                 "implementation connection changed the exported audit identity")
        module_path = modules[field["parent_module_id"]]["native_path"]
        _require(reference["user"]["path"] == module_path
                 and reference["user"]["label"] == field["label"], "native reference escaped its owning field")
        _require(all(link[key]["kind"] == declaration["kind"] for key in ("source_reference", "implementation_reference")),
                 "implementation connection changed declaration kind")
        for name in ("source_field", "instantiated_field"):
            locator = link[name]
            _require(locator["namespace"] == "object" and locator["packet_index"] == declaration["packet_index"]
                     and locator["constructor_index"] == declaration["constructor_index"],
                     "implementation field locator changed native indices")
        _require(link["instantiated_field"]["module_path"] == reference["user"]["path"]
                 and link["instantiated_field"]["label"] == field["label"]
                 and link["implementation_reference"]["user"]["path"] == reference["user"]["path"]
                 and link["source_field"]["module_path"] == link["source_reference"]["user"]["path"]
                 and link["source_field"]["label"] == link["source_reference"]["user"]["label"],
                 "implementation connection field endpoints differ")
        _require(link["source_metadata"]["kind"] == field["kind"]
                 and link["instantiated_metadata"]["kind"] == field["kind"], "implementation metadata changed field kind")
        _require(link["source_metadata"]["typing_flags"] == link["instantiated_metadata"]["typing_flags"],
                 "implementation substitution changed native typing flags")
        if field["kind"] == "constant":
            invariant_members = ("body_kind", "relevance", "inline_level", "primitive", "inline_code")
            _require(all(link["source_metadata"][name] == link["instantiated_metadata"][name] for name in invariant_members),
                     "implementation substitution changed constant metadata")
        steps = link["steps"]
        _require(steps[-1]["tag"] == "direct-lookup" and steps[-1]["reference"] == reference,
                 "implementation trace lacks its terminal exported native lookup")
        structures = [index for index, step in enumerate(steps) if step["tag"] == "structure-field"]
        _require(len(structures) == 1, "implementation trace lacks its unique native structure field")
        split = structures[0]
        _require(steps[split]["field"] == link["source_field"], "implementation trace changed its source field")
        _require(all(step["tag"] in {"module-alias", "functor-application"} for step in steps[:split]),
                 "implementation trace evaluation steps are reordered")
        substitutions = steps[split + 1:-1]
        _require(len(substitutions) <= 1, "implementation trace has ambiguous final substitutions")
        if substitutions:
            _require(substitutions[0]["tag"] == "substitution"
                     and substitutions[0]["source"] == link["source_field"]
                     and substitutions[0]["target"] == link["instantiated_field"],
                     "implementation substitution endpoints differ")
        else:
            _require(link["source_field"] == link["instantiated_field"]
                     and link["source_metadata"] == link["instantiated_metadata"],
                     "implementation changed its field/metadata without substitution")
        for step in steps[:split]:
            expression = step["expression"]
            while expression["tag"] in {"MENoFunctor", "MEMoreFunctor"}:
                expression = expression["body"]
            if step["tag"] == "module-alias":
                _require(expression["tag"] == "MEident" and expression["path"] == step["target"],
                         "native alias trace disagrees with its module expression")
            else:
                _require(expression["tag"] == "MEapply" and expression["argument"] == step["argument"],
                         "native application trace disagrees with its module expression")
        implementation = modules[field["parent_module_id"]]["implementation"]
        if implementation["kind"] in {"Struct", "FullStruct"}:
            _require(split == 0 and steps[split]["implementation_kind"] == implementation["kind"],
                     "structure implementation trace is missing")
        elif implementation["kind"] == "Algebraic":
            _require(split > 0,
                     "algebraic implementation trace is missing")
            expression = implementation["expression"]
            while expression["tag"] in {"MENoFunctor", "MEMoreFunctor"}:
                expression = expression["body"]
            _require(steps[0]["expression"] == expression or steps[0]["expression"] == implementation["expression"],
                     "implementation trace does not start with its native expression")
        else:
            raise CensusError("abstract module supplied a concrete implementation")
        alias = declaration["alias"]
        if declaration["classification"] == "alias":
            _require(alias is not None and alias["exported_reference"] == reference
                     and alias["target_reference"]["canonical"] == reference["canonical"], "unproved native alias")
        else:
            _require(alias is None and reference["canonical_name"].startswith(owners[field["parent_module_id"]] + "."),
                     "foreign declaration supplied as owned")
            _require(reference["user"] == reference["canonical"], "native alias supplied as an owned declaration")

    owned: dict[str, list[dict[str, Any]]] = {root: [] for root in expected_modules}
    seen_canonical: set[str] = set()
    for field in fields.values():
        ids = field["declaration_ids"]
        _require(set(ids) == {key for key, declaration in declarations.items() if declaration["field_id"] == field["id"]},
                 "incomplete native declaration population")
        if field["kind"] in {"module", "module-type"}:
            continue
        expected: list[tuple[str, str, int | None, int | None, Any]] = []
        if field["kind"] == "constant":
            expected.append(("constant", field["label"], None, None, field["metadata"]["type"]))
        else:
            for packet_index, packet in enumerate(field["metadata"]["packets"]):
                expected.append(("inductive", packet["name"], packet_index, None, packet["type"]))
                expected.extend(("constructor", constructor["name"], packet_index, index, constructor["type"])
                                for index, constructor in enumerate(packet["constructors"], 1))
        _require(len(expected) == len(ids), "missing inductive packet/constructor or constant")
        for identifier, (kind, label, packet_index, constructor_index, typ) in zip(ids, expected, strict=True):
            declaration = declarations[identifier]
            _require((declaration["kind"], declaration["label"], declaration["packet_index"], declaration["constructor_index"], declaration["type"])
                     == (kind, label, packet_index, constructor_index, typ), "native declaration differs from field metadata/order")
            _require(declaration["classification"] == field["classification"]
                     and declaration["context_id"] == field["context_id"], "declaration classification/context differs from field")
            if declaration["classification"] == "interface":
                _require(all(declaration[key] is None for key in ("native_reference", "implementation_connection", "alias")),
                         "signature field treated as a global constant")
            else:
                connection(declaration, field)
                if declaration["classification"] == "owned":
                    canonical = declaration["native_reference"]["canonical_name"]
                    _require(canonical not in seen_canonical, "duplicate canonical declaration without alias provenance")
                    seen_canonical.add(canonical)
                    owned[owners[field["parent_module_id"]]].append(declaration)
    _require(all(field["parent_module_id"] in modules for field in fields.values()), "orphan native field")
    _require(all(row["field_id"] in fields for row in declarations.values()), "orphan native declaration")
    abbreviation_paths: set[str] = set()
    for abbreviation in abbreviations.values():
        _require(abbreviation["module_id"] in modules, "foreign abbreviation")
        owner = modules[abbreviation["module_id"]]
        _require(abbreviation["native_abbreviation_path"] == abbreviation["exported_name"]
                 and abbreviation["exported_name"].startswith(_path(owner["native_path"]) + "."),
                 "abbreviation ownership differs from native module")
        _require(abbreviation["native_abbreviation_path"] not in abbreviation_paths, "duplicate native abbreviation path")
        abbreviation_paths.add(abbreviation["native_abbreviation_path"])

    _require(len(value["resolutions"]) == len(requests), "missing native Search resolutions")
    resolved_ids: set[str] = set()
    search_types: dict[str, str] = {}
    original_rows = {root: _search(searches[root]) for root in expected_modules}
    for request, resolution in zip(requests, value["resolutions"], strict=True):
        _require(resolution["request_id"] == request["id"]
                 and resolution["root_module_id"] == root_ids[request["requested_root"]], "native resolution reordered or changed its root")
        candidate = resolution["candidates"][0]
        declaration_id, abbreviation_id = candidate["declaration_id"], candidate["abbreviation_id"]
        _require((declaration_id is None) != (abbreviation_id is None), "ambiguous native resolution target")
        if declaration_id is not None:
            _require(declaration_id in declarations, "foreign native Search declaration")
            declaration = declarations[declaration_id]
            field = fields[declaration["field_id"]]
            _require(owners[field["parent_module_id"]] == request["requested_root"], "foreign native Search owner")
            _require(candidate["field_id"] == field["id"], "native Search resolution changed its field")
            if declaration["classification"] == "interface":
                _require(candidate["mode"] == "interface-field" and declaration["native_reference"] is None
                         and candidate["reference"]["kind"] == declaration["kind"]
                         and candidate["reference"]["exported_name"] == declaration["exported_name"]
                         and candidate["reference"]["packet_index"] == declaration["packet_index"]
                         and candidate["reference"]["constructor_index"] == declaration["constructor_index"],
                         "interface Search row claimed a global lookup")
            else:
                _require(candidate["mode"] == "global" and candidate["reference"] == declaration["native_reference"],
                         "mismatched native global Search resolution")
            _require(declaration_id not in resolved_ids, "duplicate native Search declaration without alias provenance")
            resolved_ids.add(declaration_id)
            search_types[declaration_id] = original_rows[request["requested_root"]][request["row_index"]]["type"]
        else:
            _require(abbreviation_id in abbreviations, "foreign native Search abbreviation")
            abbreviation = abbreviations[abbreviation_id]
            _require(candidate["mode"] == "abbreviation" and candidate["field_id"] is None
                     and owners[abbreviation["module_id"]] == request["requested_root"]
                     and candidate["reference"] == abbreviation["interpretation"]["target_reference"],
                     "native Search abbreviation target differs")

    result: dict[str, dict[str, Any]] = {}
    for root in expected_modules:
        # Preserve the prover's Search type when present. A field outside Search
        # retains an explicitly identified constructor representation of its type.
        guard_text = proofaudit.EMPTY_BLACKLIST + "\n" + "".join(
            declaration["native_reference"]["canonical_name"] + ": "
            + search_types.get(declaration["id"], "native-constructor-json " + _key(declaration["type"])) + "\n"
            for declaration in owned[root])
        symbols = proofaudit.inventory(guard_text, root)
        module_ids = {identifier for identifier, owner in owners.items() if owner == root}
        root_fields = [row for row in value["fields"] if row["parent_module_id"] in module_ids]
        root_declarations = [row for row in value["declarations"] if row["field_id"] in {field["id"] for field in root_fields}]
        result[root] = {"symbols": symbols, "raw_search": searches[root], "search_rows": _search(searches[root]),
                        "modules": [row for row in value["modules"] if row["id"] in module_ids], "fields": root_fields,
                        "interfaces": [row for row in root_declarations if row["classification"] == "interface"],
                        "aliases": [row for row in root_declarations if row["classification"] == "alias"]
                                   + [row for row in value["abbreviations"] if row["module_id"] in module_ids],
                        "resolutions": [row for row in value["resolutions"] if row["root_module_id"] == root_ids[root]],
                        "readings": {module["query"]["kind"] + ":" + module["query"]["target"]:
                                     readings[module["query"]["kind"] + ":" + module["query"]["target"]]
                                     for module in modules.values() if module["id"] in module_ids},
                        "declarations": root_declarations}
    return result


def census(metadata: object, searches: dict[str, str], readings: dict[str, str], *,
           expected_modules: list[str]) -> dict[str, dict[str, Any]]:
    """Refuse malformed graph joins consistently, including missing foreign keys."""
    try:
        return _census(metadata, searches, readings, expected_modules=expected_modules)
    except (KeyError, IndexError, TypeError, RecursionError) as error:
        raise CensusError("incomplete or unsupported native census graph") from error


def qualify_controls(metadata: object, searches: dict[str, str], readings: dict[str, str]) -> dict[str, Any]:
    """Adapter controls over retained native emission, distinct from prover refusals."""
    value = validate_schema(metadata)
    expected_roots = ["CensusControls", "SailStdpp.TypeCasts", "SailStdpp.State_monad"]
    all_accepted = census(value, searches, readings, expected_modules=expected_roots)
    accepted = all_accepted["CensusControls"]
    modules = accepted["modules"]
    required = {"S", "F", "Sealed", "Applied", "Empty", "AliasOnly", "HiddenSealed"}
    named = {module["native_path"].get("label"): module for module in modules}
    _require(required <= named.keys(), "native positive-control population is incomplete")
    for root, suffix in (("SailStdpp.TypeCasts", "ZEqdep"), ("SailStdpp.State_monad", "NMap")):
        actual = [module for module in all_accepted[root]["modules"] if module["native_path"].get("label") == suffix]
        _require(len(actual) == 1 and actual[0]["implementation"]["kind"] == "Algebraic",
                 "actual native functor-application control is missing")
    _require(named["S"]["kind"] == "module-type" and bool(named["F"]["signature"]["parameters"])
             and named["Empty"]["empty_evidence"] == "native-empty"
             and named["AliasOnly"]["empty_evidence"] == "native-alias-only", "native positive-control shapes differ")
    concrete = next((row for row in value["declarations"] if row["classification"] == "owned" and row["kind"] == "constant"), None)
    interface = next((row for row in value["declarations"] if row["classification"] == "interface"), None)
    if concrete is None or interface is None or not value["resolution_requests"]:
        raise CensusError("native controls lack owned/interface/resolution witnesses")
    concrete_id, interface_id = concrete["id"], interface["id"]
    concrete_reference = concrete["native_reference"]
    substituted = next((row for row in value["declarations"] if row["implementation_connection"] is not None
                        and row["implementation_connection"]["source_field"] != row["implementation_connection"]["instantiated_field"]
                        and any(step["tag"] == "substitution" for step in row["implementation_connection"]["steps"])), None)
    if substituted is None:
        raise CensusError("native controls lack a nontrivial substitution witness")
    substituted_id = substituted["id"]
    source_steps = substituted["implementation_connection"]["steps"]
    changed_inline_code = not concrete["implementation_connection"]["instantiated_metadata"]["inline_code"]
    nested_module_ids = {module["id"] for module in value["modules"] if module["parent_field_id"] is not None}
    nested_field = next((field for field in value["fields"] if field["parent_module_id"] in nested_module_ids), None)
    if nested_field is None:
        raise CensusError("native controls lack a nested field omission witness")
    nested_field_id = nested_field["id"]
    report: dict[str, Any] = {"schema": "verifiedos-sail-support-adapter-controls/1",
                              "evidence_kind": "adapter-over-native-emitted-evidence",
                              "positive": dict.fromkeys(sorted(required), "accepted"), "refusals": {}}
    mutations = {
        "omitted-nested-field": lambda item: item["fields"].remove(next(field for field in item["fields"] if field["id"] == nested_field_id)),
        "missing-implementation-connection": lambda item: next(row for row in item["declarations"] if row["id"] == concrete_id).update(implementation_connection=None),
        "signature-as-global": lambda item: next(row for row in item["declarations"] if row["id"] == interface_id).update(native_reference=concrete_reference),
        "foreign-declaration": lambda item: item["resolutions"][0]["candidates"][0].update(declaration_id="foreign", abbreviation_id=None),
        "ambiguous-resolution": lambda item: item["resolutions"][0]["candidates"].append(copy.deepcopy(item["resolutions"][0]["candidates"][0])),
        "duplicate-declaration": lambda item: item["declarations"].append(copy.deepcopy(item["declarations"][0])),
        "unproved-empty": lambda item: next(row for row in item["modules"] if row["id"] == named["Empty"]["id"]).update(empty_evidence="nonempty"),
        "unsupported-native-form": lambda item: item["fields"][0].update(kind="rewrite-rule"),
        "reordered-implementation-trace": lambda item: next(row for row in item["declarations"] if row["id"] == concrete_id)["implementation_connection"]["steps"].reverse(),
        "instantiated-metadata-drift": lambda item: next(row for row in item["declarations"] if row["id"] == concrete_id)["implementation_connection"]["instantiated_metadata"].update(inline_code=changed_inline_code),
        "missing-substitution": lambda item: next(row for row in item["declarations"] if row["id"] == substituted_id)["implementation_connection"].update(
            steps=[copy.deepcopy(step) for step in source_steps if step["tag"] != "substitution"]),
    }
    def swapped_substitution(item: dict[str, Any]) -> None:
        link = next(row for row in item["declarations"] if row["id"] == substituted_id)["implementation_connection"]
        step = next(step for step in link["steps"] if step["tag"] == "substitution")
        step["source"], step["target"] = step["target"], step["source"]
    mutations["swapped-substitution-endpoints"] = swapped_substitution
    for name, mutate in mutations.items():
        candidate = copy.deepcopy(value)
        mutate(candidate)
        try:
            census(candidate, searches, readings, expected_modules=expected_roots)
        except (CensusError, proofaudit.AuditError) as error:
            report["refusals"][name] = {"verdict": "refused", "reason": str(error)}
        else:
            raise CensusError(f"adapter native-evidence control survived: {name}")
    return report
