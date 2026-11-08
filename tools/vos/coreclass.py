# SPDX-License-Identifier: Apache-2.0
"""Parse core-class vector geometries, core rosters, and `hartSupports` extension gates for [counts_coreclass.py](checks/counts_coreclass.py) (`K-60`) and [counts_configs.py](checks/counts_configs.py) (`K-78`, `K-87`)."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config, sailbundle

CONFIG = "model/config/verifiedos.json"

# Core classes in the order declared by `model/model/core/core_class.sail`.
CLASSES = ("C", "V", "M", "S", "RoT")

ROW_RE = re.compile(r"(?m)^\| \*\*(C|V|M|S|RoT)(?:-class)?\*\* \|(.*)$")
REG_SEG_RE = re.compile(r"(?:(C|V|M|S)-class|the (RoT)) \(([^)]*)\)")
VLEN_RE = re.compile(r"VLEN=(\d+)")
# `\u00d7` (`×`) avoids ruff's RUF001 ambiguous-unicode warning.
COUNT_RE = re.compile(r"\u00d7(\d+)")


@dataclass
class CoreClasses:
    """Parsed core-class vector geometries and core-roster counts across prose and composition."""

    stated: dict[str, dict[str, int] | None] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    declared: dict[str, int] | None = None
    roster: dict[str, int] | None = None


def _table(text: str, cell: int) -> dict[str, int] | None:
    """Parse a Markdown core-class table into `{class_name: vlen_bits}`, reading `VLEN` from column `cell` after the class name."""
    found: dict[str, int] = {}
    for m in ROW_RE.finditer(text):
        name = m.group(1)
        if name in found:
            return None
        cells = m.group(2).split("|")
        if len(cells) <= cell:
            return None
        vlen = VLEN_RE.search(cells[cell])
        found[name] = int(vlen.group(1)) if vlen else 0
    return found if set(found) == set(CLASSES) else None


def _counts(text: str) -> dict[str, int]:
    """Sum `×N` core counts from the first column after the class name in [spec.md](../../docs/spec.md)."""
    found: dict[str, int] = {}
    for m in ROW_RE.finditer(text):
        cells = m.group(2).split("|")
        if not cells:
            continue
        total = sum(int(n) for n in COUNT_RE.findall(cells[0]))
        if total:
            found[m.group(1)] = total
    return found


def _register(body: str) -> dict[str, int] | None:
    found: dict[str, int] = {}
    for m in REG_SEG_RE.finditer(body):
        name = m.group(1) or m.group(2)
        if name in found:
            return None
        vlen = VLEN_RE.search(m.group(3))
        found[name] = int(vlen.group(1)) if vlen else 0
    return found if set(found) == set(CLASSES) else None


def _composition(root: Path) -> tuple[dict[str, int] | None, dict[str, int] | None]:
    """Read `(declared_vlen_by_class, roster_count_by_class)` from `CONFIG`."""
    path = root / CONFIG
    table = config.value(path, "platform", "core_classes")
    entries = config.value(path, "platform", "core_roster")

    declared: dict[str, int] | None = {}
    if isinstance(table, dict):
        for name in CLASSES:
            row = table.get(name.lower())
            exp = row.get("vlen_exp") if isinstance(row, dict) else None
            if not isinstance(exp, int) or isinstance(exp, bool):
                declared = None
                break
            declared[name] = (1 << exp) if exp else 0
    else:
        declared = None

    roster: dict[str, int] | None = None
    if isinstance(entries, list):
        roster = dict.fromkeys(CLASSES, 0)
        for entry in entries:
            token = entry.get("class") if isinstance(entry, dict) else None
            name = token.removeprefix("CoreClass_") if isinstance(token, str) else ""
            if name not in roster:
                roster = None
                break
            roster[name] += 1
    return declared, roster


EXT_PREFIX = "Ext_"
SUPPORTS = "hartSupports"

ZVL_NAME_RE = re.compile(r"\AZvl\d+b\Z")
ZVL_BODY_RE = re.compile(r"\Asizeof\(vlen_exp\)\s*>=\s*(\d+)\Z")
CONFIG_GATED_BODY_RE = re.compile(r"\Aconfig extensions\.(\w+)\.supported\Z")
VECTOR_PREFIX = "Zv"

EXTENSIONS_SAIL = "model/model/core/extensions.sail"


def _supports(bundle: sailbundle.Bundle | None) -> list[tuple[str, str]]:
    """Return `(extension_name, body_text)` for every `hartSupports` clause in `bundle`."""
    if bundle is None:
        return []
    try:
        clauses = bundle.function_clauses(SUPPORTS)
    except sailbundle.BundleError:
        return []
    return [(ident.removeprefix(EXT_PREFIX), body.strip())
            for ident, body, _ in clauses if ident.startswith(EXT_PREFIX)]


def zvl_rungs(bundle: sailbundle.Bundle | None) -> dict[str, int]:
    """Return `{zvl_extension: min_vlen_exp}` from `hartSupports` in `bundle`."""
    out: dict[str, int] = {}
    for name, body in _supports(bundle):
        rung = ZVL_BODY_RE.match(body)
        if ZVL_NAME_RE.match(name) and rung:
            out[name] = int(rung.group(1))
    return out


def config_gated_extensions(bundle: sailbundle.Bundle | None) -> dict[str, str]:
    """Return `{extension_name: config_key_path}` for extensions gated on `config extensions.<Name>.supported`."""
    out: dict[str, str] = {}
    for name, body in _supports(bundle):
        gate = CONFIG_GATED_BODY_RE.match(body)
        if gate:
            out[name] = f"extensions.{gate.group(1)}.supported"
    return out


def config_gated_vector_extensions(bundle: sailbundle.Bundle | None) -> dict[str, str]:
    """Return the `Zv*` subset of [`config_gated_extensions`](#config_gated_extensions)."""
    return {name: key for name, key in config_gated_extensions(bundle).items()
            if name.startswith(VECTOR_PREFIX)}


def composed(path: Path) -> tuple[str, int] | None:
    """Return `(class_name, class_vlen_exp)` for the hart selected by `platform.hartid` in `path`."""
    hartid = config.integer(path, "platform", "hartid")
    entries = config.value(path, "platform", "core_roster")
    if hartid is None or not isinstance(entries, list):
        return None
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("hartid") != hartid:
            continue
        token = entry.get("class")
        if not isinstance(token, str):
            return None
        name = token.removeprefix("CoreClass_")
        if name not in CLASSES:
            return None
        exp = config.integer(path, "platform", "core_classes", name.lower(), "vlen_exp")
        return None if exp is None else (name, exp)
    return None


def read(root: Path, register_body: str) -> CoreClasses:
    """Read core-class tables and counts from [spec.md](../../docs/spec.md), [isa-profile.md](../../docs/hardware/isa-profile.md), `R-15-113`, and `CONFIG`."""
    cc = CoreClasses()

    def text(rel: str) -> str:
        path = root / rel
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    spec = text("docs/spec.md")
    cc.stated["the specification's core-class table"] = _table(spec, 1)
    cc.stated["the profile's core-class table"] = _table(
        text("docs/hardware/isa-profile.md"), 0)
    cc.stated["the register's class enumeration"] = _register(register_body)
    cc.counts = _counts(spec)
    cc.declared, cc.roster = _composition(root)
    return cc
