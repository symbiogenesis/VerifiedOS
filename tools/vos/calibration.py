# SPDX-License-Identifier: Apache-2.0
"""Unpopulated calibration field classes and their qualification boundary."""

import json
from pathlib import Path
from typing import cast

from vos.jsonutil import unique_object
from vos.schema import validate

SOURCE = "interfaces/calibration-schema.json"
ARTIFACT = "docs/hardware/calibration-manifest.md"
SCHEMA = "interfaces/calibration-owner.schema.json"
FIELD_SCHEMA = "interfaces/calibration-field.schema.json"


def load(root: Path) -> dict[str, object]:
    """Refuse malformed classes and any attempt to populate measured values."""
    raw: object = json.loads((root / SOURCE).read_text(encoding="utf-8"),
                             object_pairs_hook=unique_object)
    validate(root / SCHEMA, raw)
    data = cast(dict[str, object], raw)
    register = (root / "docs/requirements-register.md").read_text(encoding="utf-8")
    for row in cast(list[dict[str, str]], data["classes"]):
        owner = row["ceiling_owner"]
        if f"**{owner}**" not in register:
            raise ValueError(f"calibration: missing ceiling owner {owner}")
    return data


def validate_field(root: Path, declaration: object) -> None:
    """Check a proposed field's class and ceiling owner, never its physical value."""
    data = load(root)
    validate(root / FIELD_SCHEMA, declaration)
    field = cast(dict[str, str], declaration)
    for row in cast(list[dict[str, str]], data["classes"]):
        if row["id"] == field["class"]:
            if field["ceiling_owner"] != row["ceiling_owner"]:
                raise ValueError("calibration: field names another class's ceiling owner")
            return
    raise ValueError("calibration: field outside the declared classes")


def emit(root: Path) -> str:
    """Generate the reviewable schema boundary from the single declaration."""
    data = load(root)
    rows = cast(list[dict[str, str]], data["classes"])
    lines = [
        "# Calibration manifest field classes", "",
        "<!-- Generated from interfaces/calibration-schema.json by vos.calibration; repair with python tools/run.py check --fix. -->", "",
        "This unpopulated schema is U-07's prerequisite under [the implementation checklist](../../PLAN.md). "
        "It supplies field classes and reserves the device-tree digest binding. It contains no trim values, certified magnitudes or admitted manifest.", "",
        "| Field class | Ceiling owner | Physical qualification owner | Required containment | Required evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend("| " + " | ".join(row[key] for key in
                 ("id", "ceiling_owner", "qualification_owner", "containment", "required_evidence")) + " |"
                 for row in rows)
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
        "and their population remain separate qualification work.", ""]
    return "\n".join(lines)
