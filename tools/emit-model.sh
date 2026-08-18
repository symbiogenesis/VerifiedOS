#!/bin/bash
# The middle loop for the M0.6c deletion campaign, between tools/check-model.sh
# (typecheck only, ~30s) and tools/build-model.sh (full build + ctest, ~15min):
# run the full C++ emission (~2min), which regenerates the config schema, then
# validate model/config/verifiedos.json against the fresh schema. This catches
# the class the typechecker cannot see -- a stray `config extensions.<Name>`
# read left behind by a cut, which surfaces as a schema/config collision only
# at emission (the c1 "sixth touch" finding). No C++ is compiled; the schema
# check is an approximation of the sim's own --validate-config (which also runs
# the model's semantic config_is_valid), so the full build stays the exit
# criterion for each batch.
ulimit -s 131072
eval $(opam env --switch=default)
SRC=/mnt/c/Users/symbi/source/repos/VerifiedOS/model
BLD=/root/build/verifiedos-model
# Reuse build-model.sh's configured canonical build tree; configure if absent.
if [ ! -f "$BLD/build.ninja" ]; then
  cmake -S "$SRC" -B "$BLD" -GNinja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DDOWNLOAD_GMP=FALSE -DENABLE_RISCV_TESTS=TRUE || exit 1
fi
cmake --build "$BLD" --target generated_sail_riscv_model || exit 1
python3 - "$BLD/sail_riscv_config_schema.json" "$SRC/config/verifiedos.json" <<'EOF'
import json
import sys

import jsonschema


def strip_comments(text):
    # The config is JSONC (jsoncons accepts // and /* */ comments; json does not).
    out = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
        elif c == '"':
            in_str = True
            out.append(c)
            i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def undeclared_keys(cfg, sch, path=""):
    # The generated schema closes only its bitvector-literal leaves
    # (additionalProperties: false), so plain validation misses a config key
    # whose schema entry a cut deleted -- the other half of the collision
    # class. c1's verified state is required-key set == config-key set, so an
    # undeclared key is always drift here. Recurse only where the subschema
    # plainly declares "properties"; anyOf/oneOf nodes are left alone.
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


with open(sys.argv[1]) as f:
    schema = json.load(f)
with open(sys.argv[2]) as f:
    config = json.loads(strip_comments(f.read()))

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
    sys.exit(1)
print("verifiedos.json validates against the regenerated schema (key sets consistent)")
EOF
