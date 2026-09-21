# Calibration manifest field classes

<!-- Generated from interfaces/calibration-schema.json by vos.calibration; repair with python tools/run.py check --fix. -->

This unpopulated schema is U-07's prerequisite under [the implementation checklist](../implementation/implementation-checklist.md). It supplies field classes and reserves the device-tree digest binding. It contains no trim values, certified magnitudes or admitted manifest.

| Field class | Ceiling owner | Physical qualification owner | Required containment | Required evidence |
| --- | --- | --- | --- | --- |
| emission-trim | R-15-124 | R5 | The selected pre-certified passive path bounds emission independently of the trim. | A physical envelope qualification for every selectable path. |
| emission-limit | R-15-125 | R5 | Boot-latched limits are at or below the certified ceilings and have no runtime write path. | Certified ceilings, the limit comparison and immutable-until-reset register behavior. |
| sram-assist | R-15-127 | R5 | Mis-trim may degrade SRAM margin only within the ECC and fail-stop backstops. | The allowed trim domain and characterized ECC and fail-stop coverage. |
| sensor-trim | R-15-127 | R5 | Mis-trim costs sensor fidelity without granting authority or weakening integrity checks. | The allowed trim domain and the sensor-to-authority boundary qualification. |

## Identity and admission boundary

R-15-126 owns the schema-bounded manifest's device serial, provisioning signature and RoT anchoring under monotonic state. R-15-128 owns worst-case trim qualification and explicit attested maintenance. R-17-062 retains factory measurement as trusted input.

The device-tree binding reserves `verifiedos,calibration-manifest-sha256` as exactly 32 bytes identifying the accepted manifest's canonical bytes. Absence means `calibration-not-qualified`; it is never a zero digest, a default manifest or permission to enable calibrated hardware. The current Sail device tree does not populate this property. R5 supplies physical fields and certified bounds; the measured-boot integration must bind the signed, serial-specific, freshness-checked manifest to this property before that hardware can be qualified.

A proposed field declaration has exactly `name`, `class` and `ceiling_owner`. The validator refuses unknown classes, a mismatched ceiling owner, duplicate classes, malformed identity bindings and extra keys including measured values. Acceptance classifies a declaration only. It neither authenticates a manifest nor establishes the class's physical containment claim.

The concrete wire descriptor, canonical parser and serializer remain with U-12/U-14; the executable RoT and RTL checks, physical trim domains and their population remain separate qualification work.
