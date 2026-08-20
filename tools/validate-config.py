#!/usr/bin/env python3
"""Validate the frozen profile against the schema a fresh emission regenerates.

This catches the class the Sail typechecker cannot see: a stray `config
extensions.<Name>` read left behind by a cut, which surfaces as a schema/config
collision only at emission (the c1 "sixth touch" finding). It is an approximation of
the simulator's own --validate-config, which also runs the model's semantic
config_is_valid, so the full build stays the exit criterion for each batch.

Two directions are checked, because the generated schema closes only its
bitvector-literal leaves (`additionalProperties: false`) and plain validation
therefore misses a config key whose schema entry a cut deleted. c1's verified state
is required-key set == config-key set, so an undeclared key is always drift.

Usage: tools/validate-config.py <schema.json> <verifiedos.json>
"""
import json
import sys

import jsonschema

import jsonc


def undeclared_keys(cfg, sch, path=""):
    # Recurse only where the subschema plainly declares "properties"; anyOf/oneOf
    # nodes are left alone.
    found = []
    if isinstance(cfg, dict) and isinstance(sch, dict) and isinstance(sch.get("properties"), dict):
        props = sch["properties"]
        for k, v in cfg.items():
            p = f"{path}/{k}" if path else k
            if k not in props:
                found.append(p)
            else:
                found.extend(undeclared_keys(v, props[k], p))
    return found


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    schema_path, config_path = sys.argv[1:3]

    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    config = jsonc.load(config_path)

    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    errors = sorted(cls(schema).iter_errors(config), key=lambda e: list(e.absolute_path))
    for e in errors:
        path = "/".join(str(p) for p in e.absolute_path) or "<root>"
        print(f"SCHEMA MISMATCH at {path}: {e.message}")

    undeclared = undeclared_keys(config, schema)
    for p in undeclared:
        print(f"UNDECLARED CONFIG KEY {p}: not in the regenerated schema")

    if errors or undeclared:
        return 1
    print("verifiedos.json validates against the regenerated schema (key sets consistent)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
