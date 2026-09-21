# SPDX-License-Identifier: Apache-2.0
"""Unpopulated calibration field classes and their qualification boundary."""

import json
import re
from pathlib import Path

SOURCE = "interfaces/calibration-schema.json"
ARTIFACT = "docs/hardware/calibration-manifest.md"
CLASS_IDS = frozenset({"emission-trim", "emission-limit", "sram-assist", "sensor-trim"})


def _keys(value: object, keys: set[str], where: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{where}: expected exactly {sorted(keys)}")
    return {key: value[key] for key in keys}


def load(root: Path) -> dict[str, object]:
    """Refuse malformed classes and any attempt to populate measured values."""
    data = _keys(json.loads((root / SOURCE).read_text(encoding="utf-8")),
                 {"schema", "status", "requirements", "device_tree", "classes"}, SOURCE)
    if type(data["schema"]) is not int or data["schema"] != 1 or data["status"] != "unpopulated":
        raise ValueError("calibration: expected schema 1 and unpopulated status")
    requirements = data["requirements"]
    if requirements != ["R-15-126", "R-15-127", "R-15-128", "R-17-062"]:
        raise ValueError("calibration: missing lifecycle or containment requirement")
    binding = _keys(data["device_tree"], {"property", "encoding", "length", "absence"}, "device_tree")
    if binding != {"property": "verifiedos,calibration-manifest-sha256", "encoding": "bytes",
                   "length": 32, "absence": "calibration-not-qualified"}:
        raise ValueError("calibration: malformed digest binding")
    classes = data["classes"]
    if not isinstance(classes, list) or len(classes) != len(CLASS_IDS):
        raise ValueError("calibration: every field class must be present once")
    seen: set[str] = set()
    register = (root / "docs/requirements-register.md").read_text(encoding="utf-8")
    for raw in classes:
        row = _keys(raw, {"id", "ceiling_owner", "qualification_owner", "containment", "required_evidence"}, "class")
        for key, value in row.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"calibration: empty {key}")
        name = str(row["id"])
        if name not in CLASS_IDS or name in seen:
            raise ValueError(f"calibration: duplicate or unknown class {name}")
        seen.add(name)
        owner = str(row["ceiling_owner"])
        if not re.fullmatch(r"R-\d{2}-\d{3}[a-z]*", owner) or f"**{owner}**" not in register:
            raise ValueError(f"calibration: missing ceiling owner {owner}")
        if row["qualification_owner"] != "R5":
            raise ValueError("calibration: physical field population belongs to R5")
    return data


def validate_field(root: Path, declaration: object) -> None:
    """Check a proposed field's class and ceiling owner, never its physical value."""
    data = load(root)
    field = _keys(declaration, {"name", "class", "ceiling_owner"}, "field")
    name = field["name"]
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", name):
        raise ValueError("calibration: invalid field name")
    classes = data["classes"]
    if not isinstance(classes, list):
        raise TypeError("calibration: missing classes")
    for row in classes:
        if isinstance(row, dict) and row["id"] == field["class"]:
            if field["ceiling_owner"] != row["ceiling_owner"]:
                raise ValueError("calibration: field names another class's ceiling owner")
            return
    raise ValueError("calibration: field outside the declared classes")


def emit(root: Path) -> str:
    """Generate the reviewable schema boundary from the single declaration."""
    data = load(root)
    rows = data["classes"]
    if not isinstance(rows, list):
        raise TypeError("calibration: missing classes")
    lines = [
        "# Calibration manifest field classes", "",
        "<!-- Generated from interfaces/calibration-schema.json by vos.calibration; repair with python tools/run.py check --fix. -->", "",
        "This unpopulated schema is U-07's prerequisite under [the implementation checklist](../implementation/implementation-checklist.md). "
        "It supplies field classes and reserves the device-tree digest binding. It contains no trim values, certified magnitudes or admitted manifest.", "",
        "| Field class | Ceiling owner | Physical qualification owner | Required containment | Required evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("calibration: malformed class")
        lines.append("| " + " | ".join(str(row[key]) for key in
                     ("id", "ceiling_owner", "qualification_owner", "containment", "required_evidence")) + " |")
    lines += ["", "## Identity and admission boundary", "",
        "R-15-126 owns the schema-bounded manifest's device serial, provisioning signature and RoT anchoring under monotonic state. "
        "R-15-128 owns worst-case trim qualification and explicit attested maintenance. R-17-062 retains factory measurement as trusted input.", "",
        "The device-tree binding reserves `verifiedos,calibration-manifest-sha256` as exactly 32 bytes identifying the accepted manifest's canonical bytes. "
        "Absence means `calibration-not-qualified`; it is never a zero digest, a default manifest or permission to enable calibrated hardware. "
        "The current Sail device tree does not populate this property. R5 supplies physical fields and certified bounds; the measured-boot integration must "
        "bind the signed, serial-specific, freshness-checked manifest to this property before that hardware can be qualified.", "",
        "A proposed field declaration has exactly `name`, `class` and `ceiling_owner`. The validator refuses unknown classes, a mismatched ceiling owner, "
        "duplicate classes, malformed identity bindings and extra keys including measured values. Acceptance classifies a declaration only. "
        "It neither authenticates a manifest nor establishes the class's physical containment claim.", "",
        "The concrete wire descriptor, canonical parser and serializer remain with U-12/U-14; the executable RoT and RTL checks, physical trim domains "
        "and their population remain separate qualification work. This schema does not change the crown-jewel review status.", ""]
    return "\n".join(lines)
