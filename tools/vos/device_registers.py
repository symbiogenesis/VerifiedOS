# SPDX-License-Identifier: Apache-2.0
"""Checked register layouts and pure accessors for the modeled MMIO surface.

The declaration owns fields, not physical placement or authority. Sail bindings
are checked against its existing bundle reader and against current source bytes.
The reviewed function fingerprints close the enumeration: adding a read, even to
an existing dispatch function, refuses until the declaration is reviewed again.
Fingerprints are review records, not a proof that Sail implements a HAL contract.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from vos import jsonc, sailbundle, socmap
from vos.jsonc import Json

DECLARATION = "interfaces/device-registers.json"
PROOF_ARTIFACT = "proofs/DeviceRegisters.v"
RTL_ARTIFACT = "rtl/generated/device_registers_pkg.sv"
PLATFORM = "model/model/sys/platform.sail"
ARTIFACTS = (PROOF_ARTIFACT, RTL_ARTIFACT)
_IDENT = re.compile(r"[a-z][a-z0-9_]*\Z")
_COMMENT = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.DOTALL)


class RegisterError(ValueError):
    """A layout, coverage record, or model binding cannot be established."""


def normalized(source: str) -> str:
    """Ignore comments and whitespace but retain string literals and tokens."""
    source = _COMMENT.sub(lambda match: match[0] if match[0].startswith('"') else "", source)
    tokens = re.finditer(r'"(?:\\.|[^"\\])*"|[A-Za-z_][A-Za-z_0-9]*|[0-9]+|[^\s]', source)
    return " ".join(token[0] for token in tokens)


def fingerprint(source: str) -> str:
    return hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()


def coverage_fingerprint(platform: Json, harness: Json) -> str:
    """Bind the reviewed declaration to the function review, as a co-read record.

    Recomputing this value is a semantic review act, never an emitter repair.
    It prevents deleting a field while retaining the old source-review evidence.
    """
    encoded = json.dumps([platform, harness], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _object(value: Json, where: str) -> dict[str, Json]:
    if not isinstance(value, dict):
        raise RegisterError(f"{where}: expected an object")
    return value


def _array(value: Json, where: str) -> list[Json]:
    if not isinstance(value, list):
        raise RegisterError(f"{where}: expected an array")
    return value


def _text(value: Json, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise RegisterError(f"{where}: expected nonempty text")
    return value


def _number(value: Json, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RegisterError(f"{where}: expected a nonnegative integer")
    return value


def _keys(node: dict[str, Json], allowed: set[str], where: str) -> None:
    if set(node) != allowed:
        raise RegisterError(f"{where}: expected keys {sorted(allowed)}, found {sorted(node)}")


def _name(value: Json, where: str) -> str:
    name = _text(value, where)
    if _IDENT.fullmatch(name) is None:
        raise RegisterError(f"{where}: invalid portable identifier {name!r}")
    return name


def _pairs(pairs: list[tuple[str, Json]]) -> dict[str, Json]:
    result: dict[str, Json] = {}
    for key, value in pairs:
        if key in result:
            raise RegisterError(f"duplicate declaration key {key}")
        result[key] = value
    return result


@dataclass(frozen=True)
class Field:
    name: str
    lsb: int
    width: int

    @property
    def mask(self) -> int:
        return (1 << self.width) - 1


@dataclass(frozen=True)
class Register:
    name: str
    offset: int
    access: str
    repeat: str
    fields: tuple[Field, ...]
    views: tuple[Field, ...]


@dataclass(frozen=True)
class Device:
    name: str
    kind: str
    rationale: str
    registers: tuple[Register, ...]


@dataclass(frozen=True)
class Layout:
    devices: tuple[Device, ...]

    @property
    def fields(self) -> tuple[tuple[str, Field], ...]:
        return tuple((f"{device.name}_{reg.name}_{field.name}", field)
                     for device in self.devices for reg in device.registers
                     for field in (*reg.fields, *reg.views))


def _function(bundle: sailbundle.Bundle, name: str) -> str:
    clauses = bundle.function_bodies(name)
    if not clauses:
        constructors = bundle.constructor_bodies(name)
        if len(constructors) == 1:
            return next(iter(constructors.values()))
    if len(clauses) != 1:
        raise RegisterError(f"{name}: expected one modeled function body")
    return clauses[0][1]


def _binding(node: Json, bundle: sailbundle.Bundle, substitutions: dict[str, str], where: str) -> None:
    binding = _object(node, where)
    _keys(binding, {"kind", "symbol", "contains"}, where)
    symbol = _text(binding["symbol"], where)
    kind = binding["kind"]
    if kind == "function":
        source = _function(bundle, symbol)
    elif kind == "let":
        source = bundle.let_text(symbol)
    elif kind == "type":
        source = bundle.type_text(symbol)
    else:
        raise RegisterError(f"{where}: unsupported binding kind {kind!r}")
    template = _text(binding["contains"], where)
    for key, value in substitutions.items():
        template = template.replace("${" + key + "}", value)
    if "${" in template:
        raise RegisterError(f"{where}: unresolved layout substitution")
    needle = normalized(template)
    pattern = (r"(?<![A-Za-z0-9_])" if needle[0].isalnum() or needle[0] == "_" else "")
    pattern += re.escape(needle)
    pattern += r"(?![A-Za-z0-9_])" if needle[-1].isalnum() or needle[-1] == "_" else ""
    if re.search(pattern, normalized(source)) is None:
        raise RegisterError(f"{where}: declared layout does not match {symbol}: {template}")


def _fields(raw: Json, bundle: sailbundle.Bundle, where: str, *, views: bool) -> tuple[Field, ...]:
    result: list[Field] = []
    occupied = 0
    for value in _array(raw, where):
        node = _object(value, where)
        _keys(node, {"name", "lsb", "width", "bindings"}, where)
        field = Field(_name(node["name"], where), _number(node["lsb"], where),
                      _number(node["width"], where))
        if field.width == 0 or field.lsb + field.width > 64:
            raise RegisterError(f"{where}.{field.name}: field outside the 64-bit word")
        if any(previous.name == field.name for previous in result):
            raise RegisterError(f"{where}.{field.name}: field declared twice")
        mask = field.mask << field.lsb
        if not views and mask & occupied:
            raise RegisterError(f"{where}.{field.name}: overlapping fields; use an explicit view")
        occupied |= mask
        substitutions = {"lsb": str(field.lsb), "width": str(field.width),
                         "high": str(field.lsb + field.width - 1),
                         "mask64": f"0x{mask:016x}"}
        bindings = _array(node["bindings"], where)
        if not bindings:
            raise RegisterError(f"{where}.{field.name}: no model correspondence")
        for binding in bindings:
            _binding(binding, bundle, substitutions, f"{where}.{field.name}")
        result.append(field)
    return tuple(result)


def read(root: Path, bundle: sailbundle.Bundle | None = None) -> Layout:
    """Read the declaration and refuse missing devices, coverage, or correspondence."""
    try:
        raw = cast(Json, json.loads((root / DECLARATION).read_text(encoding="utf-8"),
                                    object_pairs_hook=_pairs))
        top = _object(raw, DECLARATION)
        _keys(top, {"schema", "platform", "harness", "reviewed_functions", "reviewed_layout_sha256"}, DECLARATION)
        if type(top["schema"]) is not int or top["schema"] != 1:
            raise RegisterError("unsupported register-description schema")
        if bundle is None:
            bundle = sailbundle.load(root)
        if bundle is None:
            raise RegisterError("no model bundle")
        owners = bundle.owners()
        # The three files contain every binding and every dispatched MMIO reader.
        sources = (PLATFORM, "model/model/sys/rot.sail", "model/model/sys/block_device.sail")
        for path in sources:
            current = hashlib.md5((root / path).read_bytes(), usedforsecurity=False).hexdigest()
            if owners.get(path) != current:
                raise RegisterError(f"{path}: model bundle is stale; regenerate before checking layouts")
        review = _object(top["reviewed_functions"], "reviewed_functions")
        platform = (root / PLATFORM).read_text(encoding="utf-8")
        # Names are not reparsed as Sail definitions: this scan closes the reviewed
        # function roster; their bodies come only from the established bundle reader.
        required = set(re.findall(r"\bfunction\s+(\w+(?:_load|_store)|mmio_read|mmio_write)\b", platform))
        required |= {"blkdev_load", "blkdev_store", "otp_fuse_index", "monotonic_door_index",
                     "revocation_word_index"}
        if set(review) != required:
            raise RegisterError(f"reviewed function coverage differs: missing {sorted(required - set(review))}; "
                                f"extra {sorted(set(review) - required)}")
        for name, digest in review.items():
            if fingerprint(_function(bundle, name)) != digest:
                raise RegisterError(f"{name}: MMIO body changed; review its complete field coverage")
        composition = _object(jsonc.load(root / socmap.COMPOSITION), socmap.COMPOSITION)
        composed = _object(composition.get("platform"), "composition.platform")
        apertures = {key for key, node in composed.items() if isinstance(node, dict)
                     and isinstance(node.get("supported"), bool) and type(node.get("base")) is int}
        declarations = _object(top["platform"], "platform")
        if set(declarations) != apertures:
            raise RegisterError(f"device coverage differs: missing {sorted(apertures - set(declarations))}; "
                                f"extra {sorted(set(declarations) - apertures)}")
        harness = _object(top["harness"], "harness")
        if set(harness) != {"htif"}:
            raise RegisterError("harness must describe exactly the model's HTIF port")
        if top["reviewed_layout_sha256"] != coverage_fingerprint(declarations, harness):
            raise RegisterError("declaration changed: review complete field coverage against the modeled readers")
        result: list[Device] = []
        for key, value in (*declarations.items(), *harness.items()):
            _name(key, "device")
            node = _object(value, key)
            _keys(node, {"kind", "rationale", "registers"}, key)
            kind = _text(node["kind"], key)
            if kind not in {"registers", "refused", "memory", "external"}:
                raise RegisterError(f"{key}: unknown device kind")
            registers: list[Register] = []
            for raw_register in _array(node["registers"], key):
                reg = _object(raw_register, key)
                _keys(reg, {"name", "offset", "access", "repeat", "bindings", "fields", "views"}, key)
                name = _name(reg["name"], key)
                offset = _number(reg["offset"], name)
                access = _text(reg["access"], name)
                if access not in {"ro", "wo", "rw", "command"} or offset % 8:
                    raise RegisterError(f"{key}.{name}: invalid access or unaligned register")
                if any(old.name == name or old.offset == offset for old in registers):
                    raise RegisterError(f"{key}.{name}: duplicate register name or offset")
                for binding in _array(reg["bindings"], name):
                    _binding(binding, bundle, {"offset": str(offset), "offset_hex": f"0x{offset:05x}"}, name)
                fields = _fields(reg["fields"], bundle, f"{key}.{name}", views=False)
                views = _fields(reg["views"], bundle, f"{key}.{name}.views", views=True)
                if bool(fields) == (access == "command") or (access == "command" and views):
                    raise RegisterError(f"{key}.{name}: only argument-free commands have no fields")
                declared_mask = sum(field.mask << field.lsb for field in fields)
                if any((view.mask << view.lsb) & ~declared_mask for view in views):
                    raise RegisterError(f"{key}.{name}: view extends outside declared fields")
                if {field.name for field in fields} & {field.name for field in views}:
                    raise RegisterError(f"{key}.{name}: field and view names collide")
                registers.append(Register(name, offset, access, _text(reg["repeat"], name), fields, views))
            if bool(registers) != (kind == "registers"):
                raise RegisterError(f"{key}: device kind disagrees with register presence")
            result.append(Device(key, kind, _text(node["rationale"], key), tuple(registers)))
        layout = Layout(tuple(result))
        names = [name for name, _field in layout.fields]
        if not names or len(set(names)) != len(names):
            raise RegisterError("empty layout or generated identifier collision")
    except (OSError, sailbundle.BundleError) as error:
        raise RegisterError(str(error)) from error
    else:
        return layout


def emit_gallina(root: Path, bundle: sailbundle.Bundle | None = None) -> str:
    layout = read(root, bundle)
    lines = ["(* SPDX-License-Identifier: Apache-2.0 *)",
             "(* GENERATED by python tools/run.py device-registers emit; K-88 checks it.",
             f"   Owner: {DECLARATION}. R-05-083: pure field access, no MMIO authority.",
             "   R-05-138 and R-15-002b: offsets alone never construct a capability.",
             "   These theorems check layouts, not device behavior or HAL refinement. *)",
             "From Stdlib Require Import NArith.", "Open Scope N_scope.", "",
             "Definition declared_extract (word shift width : N) : N :=",
             "  (word / 2 ^ shift) mod 2 ^ width.", "",
             "Lemma shift_mask_correct : forall word shift width : N,",
             "  N.land (N.shiftr word shift) (N.ones width) = declared_extract word shift width.",
             "Proof. intros; rewrite N.land_ones, N.shiftr_div_pow2; reflexivity. Qed.", ""]
    for device in layout.devices:
        lines.append(f"(* {device.name}: {device.kind}. *)")
        lines.extend(f"Definition {device.name}_{reg.name}_offset : N := {reg.offset}."
                     for reg in device.registers)
    for name, field in layout.fields:
        lines += ["", f"Definition {name}_shift : N := {field.lsb}.",
                  f"Definition {name}_width : N := {field.width}.",
                  f"Definition {name}_get (word : N) : N :=",
                  f"  N.land (N.shiftr word {field.lsb}) {field.mask}.",
                  f"Theorem {name}_correct : forall word : N,",
                  f"  {name}_get word = declared_extract word {name}_shift {name}_width.",
                  f"Proof. intro word; change (N.land (N.shiftr word {field.lsb}) (N.ones {field.width})",
                  f"  = declared_extract word {field.lsb} {field.width}); apply shift_mask_correct. Qed."]
    lines += ["", "Print Assumptions shift_mask_correct.", ""]
    return "\n".join(lines)


def emit_sv(root: Path, bundle: sailbundle.Bundle | None = None) -> str:
    layout = read(root, bundle)
    lines = ["// SPDX-License-Identifier: Apache-2.0",
             "// GENERATED by python tools/run.py device-registers emit; K-88 checks it.",
             f"// Owner: {DECLARATION}. Relative offsets confer no device authority.",
             "package device_registers_pkg;"]
    for device in layout.devices:
        lines.append(f"  // {device.name}: {device.kind}.")
        lines.extend(f"  localparam logic [63:0] {device.name.upper()}_{reg.name.upper()}_OFFSET = 64'h{reg.offset:016x};"
                     for reg in device.registers)
    for name, field in layout.fields:
        prefix = name.upper()
        lines += [f"  localparam int unsigned {prefix}_SHIFT = {field.lsb};",
                  f"  localparam int unsigned {prefix}_WIDTH = {field.width};",
                  f"  localparam logic [63:0] {prefix}_MASK = 64'h{field.mask:016x};"]
    lines += ["endpackage : device_registers_pkg", ""]
    return "\n".join(lines)


def generated(root: Path) -> dict[str, str]:
    bundle = sailbundle.load(root)
    return {PROOF_ARTIFACT: emit_gallina(root, bundle), RTL_ARTIFACT: emit_sv(root, bundle)}


def check(root: Path) -> list[str]:
    """Byte comparison used by the CLI and mutation tests; no writes."""
    return [f"{path}: differs from declared layouts" for path, expected in generated(root).items()
            if not (root / path).is_file() or (root / path).read_bytes() != expected.encode("utf-8")]
