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
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

from vos import proofaudit

SCHEMA = Path(__file__).with_name("census-schema.json")
_KEYWORDS = {"$schema", "$id", "$defs", "$ref", "title", "description", "type",
             "const", "enum", "oneOf", "anyOf", "properties", "required",
             "additionalProperties", "items", "minItems", "maxItems", "uniqueItems",
             "minLength", "minimum", "maximum", "pattern"}
_SEARCH_NAME = r"[\w']+(?:\.[\w']+)*"
_ROW = re.compile(rf"^({_SEARCH_NAME}):\s*(.*)$")
_ABOUT = re.compile(r'\(use "About" for full details on the implicit arguments of '
                    rf"({_SEARCH_NAME}(?:(?:, {_SEARCH_NAME})* and {_SEARCH_NAME})?)\)")
_SEARCH_DIAGNOSTIC = re.compile(r'^\s*(?:(?:Error|Warning|Anomaly|Fatal error)\s*[:!]|File ")')
_ABSTRACT = {"module-type", "functor-parameter", "functor-result"}


class CensusError(ValueError):
    """Incomplete or inconsistent native evidence cannot establish a census."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CensusError(message)


def _key(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _literal_equal(left: object, right: object) -> bool:
    if type(left) is str and type(right) is str:
        return left == right
    if type(left) is bool and type(right) is bool:
        return left is right
    if left is None and right is None:
        return True
    return _key(left) == _key(right)


def _has_type(value: object, kind: str) -> bool:
    if kind == "object":
        return isinstance(value, dict)
    if kind == "array":
        return isinstance(value, list)
    if kind == "string":
        return isinstance(value, str)
    if kind == "integer":
        return type(value) is int or (type(value) is float and value.is_integer())
    if kind == "boolean":
        return type(value) is bool
    return kind == "null" and value is None


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
    """Validate a caller-supplied subtree through an invocation-local plan."""
    try:
        shape = _compile_schema(schema, document)
    except _UncompiledSchemaError:
        # Only canonical checked schemas take the compiled route. Preserve the
        # recursive reader's precise traversal/error behavior for unusual caller
        # supplied schemas, including constraints on an unvisited value kind.
        _recursive_validate(value, schema, document, site)
    else:
        _visit(value, shape, [], site)


class _UncompiledSchemaError(Exception):
    """The schema needs the unchanged recursive constraint interpreter."""


class _Shape:
    """One schema node, shared only inside a single complete validation."""

    def __init__(self, schema: dict[str, Any]) -> None:
        self.schema = schema
        self.reference: _Shape | None = None
        self.alternatives: tuple[tuple[bool, tuple[_Shape, ...]], ...] = ()
        self.members: tuple[tuple[str, _Shape], ...] = ()
        self.required = frozenset(schema.get("required", ()))
        self.allowed: frozenset[str] | None = None
        self.items: _Shape | None = None
        self.discriminators: tuple[tuple[str, dict[str, Any]], ...] = ()


def _compile_schema(schema: dict[str, Any], document: dict[str, Any]) -> _Shape:
    """Resolve recursive nodes and property order once, without caching a verdict.

    Malformed or unresolved supplied schema nodes fall back to the recursive
    interpreter, which decides whether the actual value ever visits that node.
    """
    shapes: dict[int, _Shape] = {}

    def compile_node(node: dict[str, Any]) -> _Shape:
        if id(node) in shapes:
            return shapes[id(node)]
        required = node.get("required", [])
        properties = node.get("properties", {})
        if (type(node) is not dict or not isinstance(required, list)
                or any(type(name) is not str for name in required)
                or type(properties) is not dict or any(type(name) is not str for name in properties)):
            raise _UncompiledSchemaError
        result = shapes[id(node)] = _Shape(node)
        if "$ref" in node:
            reference = node["$ref"]
            try:
                if reference.startswith("#/$defs/") and reference[8:] in document["$defs"]:
                    result.reference = compile_node(document["$defs"][reference[8:]])
                else:
                    raise _UncompiledSchemaError
            except (KeyError, TypeError, AttributeError) as error:
                raise _UncompiledSchemaError from error
        result.alternatives = tuple((exact, tuple(compile_node(branch) for branch in node[keyword]))
                                    for keyword, exact in (("oneOf", True), ("anyOf", False)) if keyword in node)
        if "properties" in node:
            properties = node["properties"]
            names = sorted(properties, key=lambda name: (
                "const" not in properties[name] and "enum" not in properties[name], name))
            result.allowed = frozenset(properties)
            result.members = tuple((name, compile_node(properties[name])) for name in names)
            candidates = tuple((name, properties[name]) for name in names
                               if "const" in properties[name] or "enum" in properties[name])
            if (not node.keys() - {"type", "properties", "required", "additionalProperties", "title", "description"}
                    and all(
                        not constraint.keys() - {"const", "enum", "type", "title", "description"}
                        and ("const" not in constraint or type(constraint["const"]) in {str, bool, type(None)})
                        and ("enum" not in constraint or (isinstance(constraint["enum"], list)
                             and all(type(item) in {str, bool, type(None)} for item in constraint["enum"])))
                        for _, constraint in candidates)):
                result.discriminators = candidates
        if "items" in node:
            result.items = compile_node(node["items"])
        return result

    return compile_node(schema)


def _failure(path: list[str | int], site: str, message: str) -> None:
    location = site + "".join(f"[{part}]" if isinstance(part, int) else "." + part for part in path)
    raise CensusError(location + ": " + message)


def _compatible(value: object, shape: _Shape) -> bool:
    """Discard only union branches contradicted by a scalar property constraint."""
    if not isinstance(value, dict):
        return True
    if any(name in value and type(value[name]) not in {str, bool, type(None)} for name, _ in shape.discriminators):
        return True
    for name, constraint in shape.discriminators:
        if name not in value:
            continue
        if "const" in constraint and not _literal_equal(value[name], constraint["const"]):
            return False
        if "enum" in constraint and not any(_literal_equal(value[name], item) for item in constraint["enum"]):
            return False
    return True


def _visit(value: object, shape: _Shape, path: list[str | int], site: str) -> None:
    schema = shape.schema
    if "$ref" in schema:
        reference = shape.reference
        if reference is None:
            raise CensusError("unsupported census schema reference")
        _visit(value, reference, path, site)
    for exact, branches in shape.alternatives:
        passed = 0
        for branch in branches:
            if not _compatible(value, branch):
                continue
            try:
                _visit(value, branch, path, site)
            except CensusError:
                continue
            passed += 1
        if not (passed == 1 if exact else passed > 0):
            _failure(path, site, "no unique schema shape")
    if "const" in schema and not _literal_equal(value, schema["const"]):
        _failure(path, site, "unexpected constant")
    if "enum" in schema and not any(_literal_equal(value, item) for item in schema["enum"]):
        _failure(path, site, "unsupported native shape")
    if "type" in schema and not _has_type(value, schema["type"]):
        _failure(path, site, "incorrect native value type")
    if isinstance(value, dict):
        if not shape.required <= value.keys():
            _failure(path, site, "missing native member")
        if shape.allowed is not None:
            if schema.get("additionalProperties") is False and value.keys() - shape.allowed:
                _failure(path, site, "unexpected native member")
            for name, member in shape.members:
                if name in value:
                    path.append(name)
                    try:
                        _visit(value[name], member, path, site)
                    finally:
                        path.pop()
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            _failure(path, site, "incomplete native array")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            _failure(path, site, "ambiguous native array")
        if schema.get("uniqueItems") and len({_key(item) for item in value}) != len(value):
            _failure(path, site, "duplicate native member")
        if shape.items is not None:
            for index, item in enumerate(value):
                path.append(index)
                try:
                    _visit(item, shape.items, path, site)
                finally:
                    path.pop()
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            _failure(path, site, "empty native string")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            _failure(path, site, "invalid native string encoding")
    if type(value) in {int, float}:
        if "minimum" in schema and not value >= schema["minimum"]:
            _failure(path, site, "invalid native index")
        if "maximum" in schema and not value <= schema["maximum"]:
            _failure(path, site, "invalid native index")


def _recursive_validate(value: object, schema: dict[str, Any], document: dict[str, Any], site: str) -> None:
    """Original interpreter for supplied schemas outside the compiled shape."""
    if "$ref" in schema:
        reference = schema["$ref"]
        _require(reference.startswith("#/$defs/") and reference[8:] in document["$defs"],
                 "unsupported census schema reference")
        _recursive_validate(value, document["$defs"][reference[8:]], document, site)
    for keyword, exact in (("oneOf", True), ("anyOf", False)):
        if keyword not in schema:
            continue
        passed = 0
        for branch in schema[keyword]:
            try:
                _recursive_validate(value, branch, document, site)
            except CensusError:
                continue
            passed += 1
        _require(passed == 1 if exact else passed > 0, f"{site}: no unique schema shape")
    if "const" in schema:
        _require(_literal_equal(value, schema["const"]), f"{site}: unexpected constant")
    if "enum" in schema:
        _require(any(_literal_equal(value, item) for item in schema["enum"]), f"{site}: unsupported native shape")
    if "type" in schema:
        _require(_has_type(value, schema["type"]), f"{site}: incorrect native value type")
    if isinstance(value, dict):
        _require(set(schema.get("required", [])) <= value.keys(), f"{site}: missing native member")
        properties = schema.get("properties")
        if properties is not None:
            if schema.get("additionalProperties") is False:
                _require(not value.keys() - properties.keys(), f"{site}: unexpected native member")
            names = sorted(value.keys() & properties.keys(), key=lambda name: (
                "const" not in properties[name] and "enum" not in properties[name], name))
            for name in names:
                _recursive_validate(value[name], properties[name], document, site + "." + name)
    if isinstance(value, list):
        _require(len(value) >= schema.get("minItems", 0), f"{site}: incomplete native array")
        _require("maxItems" not in schema or len(value) <= schema["maxItems"], f"{site}: ambiguous native array")
        if schema.get("uniqueItems"):
            _require(len({_key(item) for item in value}) == len(value), f"{site}: duplicate native member")
        if "items" in schema:
            for index, item in enumerate(value):
                _recursive_validate(item, schema["items"], document, f"{site}[{index}]")
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


def _search_evidence(stdout: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    lines = stdout.splitlines()
    _require(bool(lines) and lines[0].strip() == proofaudit.EMPTY_BLACKLIST,
             "Rocq did not confirm an empty search blacklist")
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    footer: dict[str, Any] | None = None
    for line in lines[1:]:
        if not line.strip():
            continue
        _require(footer is None, "native Search notice is repeated or nonterminal")
        _require(_SEARCH_DIAGNOSTIC.match(line) is None, "native Search contains a diagnostic")
        notice = _ABOUT.fullmatch(line)
        if notice is not None:
            spellings = re.split(r", | and ", notice.group(1))
            _require(len(set(spellings)) == len(spellings) and set(spellings) <= seen,
                     "native Search notice names duplicate or unlisted declarations")
            footer = {"raw": line, "spellings": spellings}
            continue
        _require(not line.lstrip().startswith('(use '), "malformed native Search notice")
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
    return found, footer


def _search(stdout: str) -> list[dict[str, Any]]:
    return _search_evidence(stdout)[0]


def parse_search_requests(searches: dict[str, str], *, expected_modules: list[str]) -> list[dict[str, Any]]:
    _require(bool(expected_modules) and len(set(expected_modules)) == len(expected_modules),
             "missing or duplicate requested roots")
    _require(set(searches) == set(expected_modules), "Search population differs from requested roots")
    return [{"id": f"{root}:{row['row_index']}", "requested_root": root,
             "row_index": row["row_index"], "spelling": row["spelling"]}
            for root in expected_modules for row in _search(searches[root])]


def reading_targets(metadata: object) -> list[tuple[str, str]]:
    return _reading_targets(validate_schema(metadata))


def _reading_targets(value: dict[str, Any]) -> list[tuple[str, str]]:
    """Collect query targets only after the caller validates the complete schema."""
    return list(dict.fromkeys((module["query"]["kind"], module["query"]["target"])
                              for module in value["modules"]))


def _module_alias(text: str) -> bool:
    """Recognize the locked printer's path and parenthesized application suffixes."""
    tokens: list[str] = []
    cursor = 0
    for match in re.finditer(r"[\w']+(?:\.[\w']+)*|[()]", text):
        if text[cursor:match.start()].strip():
            return False
        tokens.append(match.group())
        cursor = match.end()
    if text[cursor:].strip() or not tokens:
        return False
    def atom(index: int) -> int:
        if index >= len(tokens) or tokens[index] == ")":
            return -1
        if tokens[index] != "(":
            return index + 1
        index = atom(index + 1)
        while index >= 0 and index < len(tokens) and tokens[index] != ")":
            index = atom(index)
        return index + 1 if index >= 0 and index < len(tokens) else -1
    return atom(0) == len(tokens)


def _reading(text: str, kind: str, target: str) -> None:
    """Check the locked printer's framing without interpreting printed term syntax."""
    _require(isinstance(text, str) and bool(text.strip()), "missing complete native module reading")
    header = re.match(r"\s*Module\s+(Type\s+)?([\w']+(?:\.[\w']+)*)\s*(?=[:=(])", text)
    suffixes = {".".join(target.split(".")[index:]) for index in range(len(target.split(".")))}
    if header is None:
        raise CensusError("native module reading header differs from query")
    _require(header.group(2) in suffixes
             and bool(header.group(1)) == (kind == "module-type"), "native module reading header differs from query")
    # Strings can contain punctuation/keywords that are not printer framing.
    framed = re.sub(r'"(?:[^"]|"")*"', '""', text)
    _require(re.match(r"(?::=|:|=)\s*\S", framed[header.end():]) is not None,
             "native module reading has an incomplete header")
    _require("..." not in framed and "…" not in framed and "<elided>" not in framed,
             "truncated native module reading")
    _require(re.search(r"(?m)^\s*(?:Error|Warning|Anomaly|Fatal error)\s*[:!]", framed) is None,
             "native module reading contains a diagnostic")
    if re.search(r"(?<![\w'.])(?:Struct|Sig)(?![\w'])", framed):
        closing = re.search(r"(?<![\w'.])End\s*(?::=\s*(.*?))?\s*$", framed, re.DOTALL)
        if closing is None:
            raise CensusError("native module reading is missing its outer closing body")
        _require(closing.group(1) is None or _module_alias(closing.group(1)),
                 "native module reading has an incomplete implementation suffix")


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
            for field in node["fields"]:
                is_module = field["kind"] in {"module", "module-type"}
                _require(field["namespace"] == ("module" if is_module else "object")
                         and (field["metadata"] is None) == is_module
                         and (field["module"] is not None) == is_module, "native structure field payload differs from kind")
                if is_module:
                    _require(field["module"]["kind"] == field["kind"]
                             and field["module"]["path"] == {"tag": "MPdot", "parent": node["path"], "label": field["label"]},
                             "native child module path/kind differs from its selected field")
                else:
                    _require(field["metadata"]["kind"] == field["kind"], "native structure object metadata kind differs")
        if {"path", "kind", "signature", "implementation"} == node.keys():
            signature = node["signature"]
            while signature["tag"] == "MoreFunctor":
                _require(signature["parameter"]["path"] == {"tag": "MPbound", "identifier": signature["parameter_identifier"]},
                         "native module formal lost its bound path")
                signature = signature["result"]
            _require(signature["structure"]["path"] == node["path"], "native module signature structure has another owner path")
        if {"packet_count", "packets"} <= node.keys():
            _require(node["packet_count"] == len(node["packets"]), "incomplete inductive packets")
        if {"constructor_count", "constructors"} <= node.keys():
            _require(node["constructor_count"] == len(node["constructors"]), "incomplete inductive constructors")
        if "body_kind" in node:
            _require(node["transparent_body"] is None, "executable native body payload is prohibited")
            _require((node["transparent_body_identity"] is not None) == (node["body_kind"] == "Def"),
                     "constant body discriminator disagrees with native body identity")
            _require((node["primitive"] is not None) == (node["body_kind"] == "Primitive"),
                     "primitive discriminator disagrees with native body")
            _require(node["inline_level"] is None or node["body_kind"] == "Undef",
                     "inline level on a non-abstract body")
        if {"algorithm", "encoding", "digest", "module_paths", "kernel_names"} == node.keys():
            _require(re.fullmatch(r"[0-9a-f]{64}", node["digest"]) is not None,
                     "native body identity is not an exact lowercase BLAKE2b-256 digest")
        if {"kind", "expression", "structure", "algebraic_type", "resolver_id"} == node.keys():
            kind = node["kind"]
            _require((node["expression"] is not None) == (kind == "Algebraic"),
                     "implementation expression discriminator disagrees")
            _require((node["structure"] is not None) == (kind == "Struct"),
                     "implementation structure discriminator disagrees")


def _same_native(left: object, right: object, resolvers: dict[str, dict[str, Any]]) -> bool:
    """Compare validated metadata by complete native finite resolver effects.

    The census's complete schema and resolver-membership scans precede every
    caller, so a short-circuit comparison cannot hide a malformed reference.
    """
    compared: dict[tuple[str, str], bool] = {}

    def equal(first: object, second: object) -> bool:
        if isinstance(first, list):
            return isinstance(second, list) and len(first) == len(second) and all(
                equal(a, b) for a, b in zip(first, second, strict=True))
        if isinstance(first, dict):
            if not isinstance(second, dict) or first.keys() != second.keys():
                return False
            for key, item in first.items():
                if key == "resolver_id":
                    other = second[key]
                    pair = item, other
                    if pair not in compared:
                        a, b = resolvers[item], resolvers[other]
                        compared[pair] = all(a[name] == b[name] for name in (
                            "root", "module_effects", "kernel_effects", "inline_keys"))
                    if not compared[pair]:
                        return False
                elif not equal(item, second[key]):
                    return False
            return True
        return first == second

    return equal(left, right)


def _ordered_subset(keys: list[str], ranks: dict[str, int]) -> bool:
    previous = -1
    for key in keys:
        rank = ranks.get(key)
        if rank is None or rank <= previous:
            return False
        previous = rank
    return True


def _trace(steps: list[dict[str, Any]], source: dict[str, Any], target: dict[str, Any],
           implementation: dict[str, Any], origin: dict[str, Any], *,
           source_value: object, target_value: object, resolvers: dict[str, dict[str, Any]],
           exported_reference: dict[str, Any] | None = None) -> None:
    """Replay one local native evaluation, separate from enclosing module descents."""
    if exported_reference is not None:
        _require(steps[-1]["tag"] == "direct-lookup" and steps[-1]["reference"] == exported_reference,
                 "implementation trace lacks its terminal exported native lookup")
        local = steps[:-1]
    else:
        local = steps
    structures = [index for index, step in enumerate(local) if step["tag"] == "structure-field"]
    _require(len(structures) == 1, "implementation trace lacks its unique native structure field")
    split = structures[0]
    _require(local[split]["field"] == source, "implementation trace changed its source field")
    _require(all(step["tag"] in {"module-alias", "functor-application"} for step in local[:split]),
             "implementation trace evaluation steps are reordered")
    substitutions = local[split + 1:]
    _require(len(substitutions) <= 1, "implementation trace has ambiguous final substitutions")
    if substitutions:
        _require(substitutions[0]["tag"] == "substitution" and substitutions[0]["source"] == source
                 and substitutions[0]["target"] == target, "implementation substitution endpoints differ")
    else:
        _require(source == target and _same_native(source_value, target_value, resolvers),
                 "implementation changed its field/metadata without substitution")
    pending: list[dict[str, Any]] = []
    actual_origin = origin
    for step in local[:split]:
        expression = step["expression"]
        while expression["tag"] in {"MENoFunctor", "MEMoreFunctor"}:
            expression = expression["body"]
        if step["tag"] == "module-alias":
            _require(not pending, "native application trace omitted an ordered argument")
            _require(step["source"] == actual_origin, "native alias trace rebased its original source path")
            while expression["tag"] == "MEapply":
                pending.append(expression)
                expression = expression["function"]
                while expression["tag"] in {"MENoFunctor", "MEMoreFunctor"}:
                    expression = expression["body"]
            pending.reverse()
            _require(expression["tag"] == "MEident" and expression["path"] == step["target"],
                     "native alias trace disagrees with its module expression")
            actual_origin = step["target"]
        else:
            _require(expression["tag"] == "MEapply" and expression["argument"] == step["argument"],
                     "native application trace disagrees with its module expression")
            _require(bool(pending) and expression == pending.pop(0), "native application trace reordered or added an argument")
    _require(not pending, "native application trace omitted an ordered argument")
    _require(source["module_path"] == actual_origin, "native structure source was rebased before its original reading")
    if implementation["kind"] in {"Struct", "FullStruct"}:
        _require(split == 0 and local[split]["implementation_kind"] == implementation["kind"],
                 "structure implementation trace is missing")
    elif implementation["kind"] == "Algebraic":
        _require(split > 0, "algebraic implementation trace is missing")
        expression = implementation["expression"]
        while expression["tag"] in {"MENoFunctor", "MEMoreFunctor"}:
            expression = expression["body"]
        _require(local[0]["expression"] == expression or local[0]["expression"] == implementation["expression"],
                 "implementation trace does not start with its native expression")
    else:
        raise CensusError("abstract module supplied a concrete implementation")


def _census(metadata: object, searches: dict[str, str], readings: dict[str, str], *,
            expected_modules: list[str]) -> dict[str, dict[str, Any]]:
    """Read evidence without mutating it; return guarded symbols and complete provenance."""
    value = validate_schema(metadata)
    # The strict resolver schema contains only paths, kernel names and scalar
    # effects. Native metadata/body checks cannot match any resolver subtree.
    metadata_view = {key: item for key, item in value.items() if key != "resolvers"}
    _require(value["requested_roots"] == expected_modules, "native requested population differs")
    _require([root["requested"] for root in value["roots"]] == expected_modules,
             "native root population/order differs")
    requests = parse_search_requests(searches, expected_modules=expected_modules)
    _require(value["resolution_requests"] == requests, "native requests differ from original Search rows")
    modules, fields, declarations, abbreviations, contexts, resolvers, descents = (
        _table(value, name) for name in ("modules", "fields", "declarations", "abbreviations", "contexts", "resolvers", "module_descents"))
    _native_semantics(metadata_view)
    fields_by_module: dict[str, set[str]] = {}
    declarations_by_field: dict[str, set[str]] = {}
    abbreviations_by_module: dict[str, set[str]] = {}
    for identifier, field in fields.items():
        fields_by_module.setdefault(field["parent_module_id"], set()).add(identifier)
    for identifier, declaration in declarations.items():
        declarations_by_field.setdefault(declaration["field_id"], set()).add(identifier)
    for identifier, abbreviation in abbreviations.items():
        abbreviations_by_module.setdefault(abbreviation["module_id"], set()).add(identifier)
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
        _require(set(ids) == fields_by_module.get(identifier, set()),
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
        aliases = abbreviations_by_module.get(identifier, set())
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
    targets = _reading_targets(value)
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
    path_order: list[str] | None = None
    kernel_order: list[str] | None = None
    for resolver in resolvers.values():
        _require(resolver["owner_module_id"] in modules, "foreign native resolver")
        inputs = [_key(effect["input"]) for effect in resolver["module_effects"]]
        _require(len(inputs) == len(set(inputs)) and set(inputs) == paths, "incomplete native resolver module domain")
        if path_order is None:
            path_order = inputs
        _require(inputs == path_order, "native resolver module domains disagree on key order")
        inputs = [_key(effect["input"]) for effect in resolver["kernel_effects"]]
        _require(len(inputs) == len(set(inputs)) and set(inputs) == kernels, "incomplete native resolver kernel domain")
        if kernel_order is None:
            kernel_order = inputs
        _require(inputs == kernel_order, "native resolver kernel domains disagree on key order")
    if path_order is None or kernel_order is None:
        raise CensusError("missing native resolver domain order")
    path_ranks = {key: index for index, key in enumerate(path_order)}
    kernel_ranks = {key: index for index, key in enumerate(kernel_order)}
    for node in _nodes(metadata_view):
        if {"algorithm", "encoding", "digest", "module_paths", "kernel_names"} != node.keys():
            continue
        body_paths = [_key(path) for path in node["module_paths"]]
        body_kernels = [_key(kernel) for kernel in node["kernel_names"]]
        body_path_set = set(body_paths)
        _require(_ordered_subset(body_paths, path_ranks),
                 "native body reference paths disagree with native key order")
        _require(_ordered_subset(body_kernels, kernel_ranks),
                 "native body kernel references disagree with native key order")
        for reference in _nodes([node["module_paths"], node["kernel_names"]]):
            if reference.get("tag") in {"MPfile", "MPbound", "MPdot"}:
                _require(_key(reference) in body_path_set,
                         "native body footprint omits a kernel path or parent module path")
    for module in modules.values():
        resolver = resolvers.get(module["implementation"]["resolver_id"], {})
        _require(resolver.get("owner_module_id") == module["id"], "module implementation names a foreign resolver")
    for node in _nodes(metadata_view):
        if "resolver_id" in node:
            _require(node["resolver_id"] in resolvers, "missing native resolver connection")

    concrete_nested = {identifier for identifier, module in modules.items()
                       if module["parent_field_id"] is not None and module["kind"] == "module"
                       and not any(context["kind"] in _ABSTRACT
                                   for context in context_chain(module["signature"]["result_context_id"]))}
    descent_by_module = {descent["owner_module_id"]: descent for descent in descents.values()}
    _require(len(descent_by_module) == len(descents) and set(descent_by_module) == concrete_nested,
             "native nested module descent population is missing, duplicate or foreign")
    enclosing: dict[str, list[str]] = {}
    def descent_chain(module_id: str, active: set[str] | None = None) -> list[str]:
        if module_id in enclosing:
            return enclosing[module_id]
        if module_id in root_ids.values():
            enclosing[module_id] = []
            return []
        pending = set() if active is None else active
        _require(module_id in descent_by_module and module_id not in pending, "missing or cyclic native module descent")
        descent = descent_by_module[module_id]
        field = fields[modules[module_id]["parent_field_id"]]
        parent_id = field["parent_module_id"]
        parent_chain = descent_chain(parent_id, pending | {module_id})
        _require(descent["parent_descent_id"] == (parent_chain[-1] if parent_chain else None),
                 "native module descent lost its direct parent")
        enclosing[module_id] = [*parent_chain, descent["id"]]
        return enclosing[module_id]

    def native_field(module: dict[str, Any], locator: dict[str, Any]) -> dict[str, Any] | None:
        implementation = module["implementation"]
        if implementation["kind"] == "FullStruct":
            _require(module["signature"]["tag"] == "NoFunctor", "concrete native module retained an unapplied functor")
            structure = module["signature"]["structure"]
        elif implementation["kind"] == "Struct":
            structure = implementation["structure"]
        else:
            return None
        matches = [field for field in structure["fields"]
                   if (field["namespace"], field["label"]) == (locator["namespace"], locator["label"])]
        _require(len(matches) == 1, "native original/instantiated module omits a selected field")
        return matches[0]

    for module_id, descent in descent_by_module.items():
        descent_chain(module_id)
        module = modules[module_id]
        field = fields[module["parent_field_id"]]
        parent = modules[field["parent_module_id"]]
        source, target = descent["source_field"], descent["instantiated_field"]
        for locator in (source, target):
            _require(locator["namespace"] == "module" and locator["label"] == field["label"]
                     and locator["packet_index"] is None and locator["constructor_index"] is None,
                     "native module descent changed its namespace, label or indices")
        _require(target["module_path"] == parent["native_path"], "native module descent changed its instantiated parent")
        for name, locator in (("source_module", source), ("instantiated_module", target)):
            child = descent[name]
            expected_path = {"tag": "MPdot", "parent": locator["module_path"], "label": locator["label"]}
            _require(child["kind"] == "module" and child["path"] == expected_path
                     and child["signature"]["tag"] == "NoFunctor", "native module descent child metadata/path differs")
        _require(descent["instantiated_module"]["path"] == module["native_path"],
                 "native module descent does not reach its exported child")
        parent_descent = descent_by_module.get(parent["id"])
        implementation = parent_descent["instantiated_module"]["implementation"] if parent_descent is not None else parent["implementation"]
        origin = parent_descent["source_module"]["path"] if parent_descent is not None else parent["native_path"]
        _trace(descent["steps"], source, target, implementation, origin,
               source_value=descent["source_module"], target_value=descent["instantiated_module"], resolvers=resolvers)
        if parent_descent is not None:
            for name, locator in (("source_module", source), ("instantiated_module", target)):
                selected = native_field(parent_descent[name], locator)
                if selected is not None:
                    _require(selected["kind"] == "module" and _same_native(selected["module"], descent[name], resolvers),
                             "native descent replaced its parent's actual before/after module field")

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
        _require(all((link[key]["kind"], link[key]["packet_index"], link[key]["constructor_index"])
                     == (declaration["kind"], declaration["packet_index"], declaration["constructor_index"])
                     for key in ("source_reference", "implementation_reference")),
                 "implementation connection changed declaration kind or native indices")
        for name in ("source_field", "instantiated_field"):
            locator = link[name]
            _require(locator["namespace"] == "object" and locator["packet_index"] == declaration["packet_index"]
                     and locator["constructor_index"] == declaration["constructor_index"],
                     "implementation field locator changed native indices")
        _require(link["instantiated_field"]["module_path"] == reference["user"]["path"]
                 and link["instantiated_field"]["label"] == field["label"]
                 and link["implementation_reference"]["user"]["path"] == reference["user"]["path"]
                 and link["implementation_reference"]["user"]["label"] == link["instantiated_field"]["label"]
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
        owner_id = field["parent_module_id"]
        _require(link["enclosing_descent_ids"] == descent_chain(owner_id), "object connection lost its exact enclosing module chain")
        owner_descent = descent_by_module.get(owner_id)
        implementation = owner_descent["instantiated_module"]["implementation"] if owner_descent is not None else modules[owner_id]["implementation"]
        origin = owner_descent["source_module"]["path"] if owner_descent is not None else modules[owner_id]["native_path"]
        _trace(link["steps"], link["source_field"], link["instantiated_field"], implementation, origin,
               source_value=link["source_metadata"], target_value=link["instantiated_metadata"],
               resolvers=resolvers, exported_reference=reference)
        if owner_descent is not None:
            for name, locator, metadata_name in (("source_module", link["source_field"], "source_metadata"),
                                                 ("instantiated_module", link["instantiated_field"], "instantiated_metadata")):
                selected = native_field(owner_descent[name], locator)
                if selected is not None:
                    _require(selected["kind"] == field["kind"] and _same_native(selected["metadata"], link[metadata_name], resolvers),
                             "object connection replaced its enclosing before/after native metadata")
        alias = declaration["alias"]
        if declaration["classification"] == "alias":
            _require(alias is not None and alias["exported_reference"] == reference
                     and alias["target_reference"] == link["implementation_reference"], "unproved native alias")
            _require(alias["resolver_id"] == implementation["resolver_id"],
                     "native alias lost its exact private implementation resolver")
            public_id = modules[owner_id]["implementation"]["resolver_id"]
            for resolver_id in (alias["resolver_id"], public_id):
                resolver = resolvers[resolver_id]
                _require(resolver["owner_module_id"] == owner_id and resolver["role"] == "signature",
                         "native alias canonicalization has a foreign owner or resolver role")
            public = resolvers[public_id]
            for native_input in (link["implementation_reference"]["canonical"], reference["user"], reference["canonical"]):
                index = kernel_ranks.get(_key(native_input))
                _require(index is not None, "native alias canonicalization is outside the complete kernel domain")
                effect = public["kernel_effects"][index]
                _require(effect["input"] == native_input and effect["output"] == reference["canonical"],
                         "native public signature resolver does not establish the exact alias canonicalization")
        else:
            _require(alias is None and reference["canonical_name"].startswith(owners[field["parent_module_id"]] + "."),
                     "foreign declaration supplied as owned")
            _require(reference["user"] == reference["canonical"], "native alias supplied as an owned declaration")

    owned: dict[str, list[dict[str, Any]]] = {root: [] for root in expected_modules}
    alias_audits: dict[str, list[dict[str, Any]]] = {root: [] for root in expected_modules}
    alias_obligations: dict[str, list[dict[str, Any]]] = {root: [] for root in expected_modules}
    seen_canonical: set[str] = set()
    for field in fields.values():
        ids = field["declaration_ids"]
        _require(set(ids) == declarations_by_field.get(field["id"], set()),
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
                else:
                    _require(proofaudit.QUALIFIED.fullmatch(declaration["implementation_connection"]["audit_query_name"]) is not None,
                             "declaration alias has no global native audit target")
                    alias_audits[owners[field["parent_module_id"]]].append({
                        "source_kind": "declaration-alias", "source_id": declaration["id"],
                        "exported_spelling": declaration["exported_name"],
                        "audit_query_name": declaration["implementation_connection"]["audit_query_name"],
                        "native_reference": declaration["native_reference"]})
    _require(all(field["parent_module_id"] in modules for field in fields.values()), "orphan native field")
    _require(all(row["field_id"] in fields for row in declarations.values()), "orphan native declaration")
    abbreviation_paths: set[str] = set()
    for abbreviation in abbreviations.values():
        _require(abbreviation["module_id"] in modules, "foreign abbreviation")
        owner = modules[abbreviation["module_id"]]
        abstract = any(context["kind"] in _ABSTRACT
                       for context in context_chain(owner["signature"]["result_context_id"]))
        _require(abbreviation["native_abbreviation_path"] == abbreviation["exported_name"],
                 "abbreviation ownership differs from native module")
        if not abstract:
            _require(abbreviation["exported_name"].startswith(_path(owner["native_path"]) + "."),
                     "concrete abbreviation escaped its native module")
        _require(abbreviation["native_abbreviation_path"] not in abbreviation_paths, "duplicate native abbreviation path")
        abbreviation_paths.add(abbreviation["native_abbreviation_path"])
        target = abbreviation["interpretation"]["target_reference"]
        binding = {"source_kind": "abbreviation", "source_id": abbreviation["id"],
                   "exported_spelling": abbreviation["exported_name"], "native_reference": target}
        root = owners[owner["id"]]
        if abstract:
            alias_obligations[root].append(binding | {"context_id": owner["signature"]["result_context_id"]})
        else:
            # A concrete alias cannot capture a bound/interface reference. Native
            # reference strings are retained; neither a prefix nor a type is made up.
            _path(target["user"]["path"])
            _path(target["canonical"]["path"])
            _require(proofaudit.QUALIFIED.fullmatch(target["canonical_name"]) is not None,
                     "concrete abbreviation has no global native audit target")
            if target["kind"] == "constant":
                for side, spelling in (("user", "exported_name"), ("canonical", "canonical_name")):
                    _require(target[spelling] == _path(target[side]["path"]) + "." + target[side]["label"],
                             "abbreviation audit target differs from its native reference")
            alias_audits[root].append(binding | {"audit_query_name": target["canonical_name"]})

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
            + (search_types[declaration["id"]] if declaration["id"] in search_types
               else "native-constructor-json " + _key(declaration["type"])) + "\n"
            for declaration in owned[root])
        symbols = proofaudit.inventory(guard_text, root)
        module_ids = {identifier for identifier, owner in owners.items() if owner == root}
        root_fields = [row for row in value["fields"] if row["parent_module_id"] in module_ids]
        root_field_ids = {field["id"] for field in root_fields}
        root_declarations = [row for row in value["declarations"] if row["field_id"] in root_field_ids]
        search_rows, search_footer = _search_evidence(searches[root])
        result[root] = {"symbols": symbols, "raw_search": searches[root], "search_rows": search_rows,
                        "search_footer": search_footer,
                        "modules": [row for row in value["modules"] if row["id"] in module_ids], "fields": root_fields,
                        "interfaces": [row for row in root_declarations if row["classification"] == "interface"],
                        "aliases": [row for row in root_declarations if row["classification"] == "alias"]
                                   + [row for row in value["abbreviations"] if row["module_id"] in module_ids],
                        "alias_audits": alias_audits[root], "alias_obligations": alias_obligations[root],
                        "module_descents": [row for row in value["module_descents"] if row["owner_module_id"] in module_ids],
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


def _control_copy(value: dict[str, Any], table: str) -> dict[str, Any]:
    """Isolate the one mutated table; full immutable native evidence remains shared."""
    _require(table in {"fields", "declarations", "resolutions", "modules"},
             "unsupported native-evidence mutation table")
    return value | {table: copy.deepcopy(value[table])}


def qualify_controls(metadata: object, searches: dict[str, str], readings: dict[str, str]) -> dict[str, Any]:
    """Adapter controls over retained native emission, distinct from prover refusals."""
    expected_roots = ["CensusControls", "SailStdpp.TypeCasts", "SailStdpp.State_monad"]
    all_accepted = census(metadata, searches, readings, expected_modules=expected_roots)
    value = cast("dict[str, Any]", metadata)  # The complete public census boundary succeeded without mutation.
    accepted = all_accepted["CensusControls"]
    modules = accepted["modules"]
    required = {"S", "F", "Sealed", "Applied", "Empty", "AliasOnly", "HiddenSealed", "HiddenAlias"}
    named = {module["native_path"].get("label"): module for module in modules}
    _require(required <= named.keys(), "native positive-control population is incomplete")
    for root, suffix in (("SailStdpp.TypeCasts", "ZEqdep"), ("SailStdpp.State_monad", "NMap")):
        actual = [module for module in all_accepted[root]["modules"] if module["native_path"].get("label") == suffix]
        _require(len(actual) == 1 and actual[0]["implementation"]["kind"] == "Algebraic",
                 "actual native functor-application control is missing")
    _require(named["S"]["kind"] == "module-type" and bool(named["F"]["signature"]["parameters"])
             and named["Empty"]["empty_evidence"] == "native-empty"
             and named["AliasOnly"]["empty_evidence"] == "native-alias-only"
             and named["HiddenAlias"]["kind"] == "module"
             and named["HiddenAlias"]["implementation"]["kind"] == "Algebraic", "native positive-control shapes differ")
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
    mutations: dict[str, tuple[str, Callable[[dict[str, Any]], None]]] = {
        "omitted-nested-field": ("fields", lambda item: item["fields"].remove(next(field for field in item["fields"] if field["id"] == nested_field_id))),
        "missing-implementation-connection": ("declarations", lambda item: next(row for row in item["declarations"] if row["id"] == concrete_id).update(implementation_connection=None)),
        "signature-as-global": ("declarations", lambda item: next(row for row in item["declarations"] if row["id"] == interface_id).update(native_reference=concrete_reference)),
        "foreign-declaration": ("resolutions", lambda item: item["resolutions"][0]["candidates"][0].update(declaration_id="foreign", abbreviation_id=None)),
        "ambiguous-resolution": ("resolutions", lambda item: item["resolutions"][0]["candidates"].append(copy.deepcopy(item["resolutions"][0]["candidates"][0]))),
        "duplicate-declaration": ("declarations", lambda item: item["declarations"].append(copy.deepcopy(item["declarations"][0]))),
        "unproved-empty": ("modules", lambda item: next(row for row in item["modules"] if row["id"] == named["Empty"]["id"]).update(empty_evidence="nonempty")),
        "unsupported-native-form": ("fields", lambda item: item["fields"][0].update(kind="rewrite-rule")),
        "reordered-implementation-trace": ("declarations", lambda item: next(row for row in item["declarations"] if row["id"] == concrete_id)["implementation_connection"]["steps"].reverse()),
        "instantiated-metadata-drift": ("declarations", lambda item: next(row for row in item["declarations"] if row["id"] == concrete_id)["implementation_connection"]["instantiated_metadata"].update(inline_code=changed_inline_code)),
        "missing-substitution": ("declarations", lambda item: next(row for row in item["declarations"] if row["id"] == substituted_id)["implementation_connection"].update(
            steps=[copy.deepcopy(step) for step in source_steps if step["tag"] != "substitution"])),
    }
    def swapped_substitution(item: dict[str, Any]) -> None:
        link = next(row for row in item["declarations"] if row["id"] == substituted_id)["implementation_connection"]
        step = next(step for step in link["steps"] if step["tag"] == "substitution")
        step["source"], step["target"] = step["target"], step["source"]
    mutations["swapped-substitution-endpoints"] = "declarations", swapped_substitution
    for name, (table, mutate) in mutations.items():
        candidate = _control_copy(value, table)
        mutate(candidate)
        try:
            census(candidate, searches, readings, expected_modules=expected_roots)
        except (CensusError, proofaudit.AuditError) as error:
            report["refusals"][name] = {"verdict": "refused", "reason": str(error)}
        else:
            raise CensusError(f"adapter native-evidence control survived: {name}")
        del candidate
    return report
