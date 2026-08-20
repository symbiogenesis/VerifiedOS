#!/usr/bin/env python3
"""Compare the key sets of two model configuration files.

The generated configuration (build/config/rv64d_v256_e64.json, from
model/config/config.json.in) is the max configuration every curation batch is
built against; model/config/verifiedos.json is the frozen profile. A deletion
batch must leave the two agreeing on *keys* even where they disagree on values,
because a key present in only one of them is either dead configuration surface
the cut missed or a profile row the generated file no longer offers.

Usage: tools/config-keys.py <generated.json> <verifiedos.json>
"""
import json
import re
import sys


def load(path):
    text = open(path, encoding="utf-8").read()
    # The model's configuration dialect allows // comments.
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
    return json.loads(text)


def keys(node, prefix=""):
    found = set()
    if isinstance(node, dict):
        for key, value in node.items():
            found.add(prefix + key)
            found |= keys(value, prefix + key + ".")
    return found


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    left, right = (keys(load(p)) for p in sys.argv[1:3])
    # `memory.regions` is a list whose entries differ by design, and the option
    # payloads (`Some`/`None`) are values rather than configuration keys.
    ignore = re.compile(r"(^|\.)(Some|None|len|value)$")
    left = {k for k in left if not ignore.search(k)}
    right = {k for k in right if not ignore.search(k)}
    status = 0
    for label, missing in (("only in %s" % sys.argv[1], left - right),
                           ("only in %s" % sys.argv[2], right - left)):
        if missing:
            status = 1
            print(label + ":")
            for key in sorted(missing):
                print("  " + key)
    if status == 0:
        print("key sets agree (%d keys)" % len(left))
    return status


if __name__ == "__main__":
    sys.exit(main())
