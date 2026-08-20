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
import sys

import jsonc


def is_value(node):
    """True where a dict is one configuration *value* rather than more surface.

    Two shapes reach here. An option is spelled `{"Some": ...}` or `{"None": ...}`,
    and a bitvector literal is spelled `{"len": n, "value": "0x..."}`. Descending
    into either compares payloads instead of keys: `dtb_address` is the row a cut
    can delete, and `dtb_address.value` is just the address it holds.

    Recognized by shape and not by name, deliberately. A leaf-name match (`value$`,
    `len$`) drops any key so called at any depth, including one a cut really did
    leave on a single side, and the run then still prints "key sets agree". An
    exclusion that widens on its own is worse than none in a tool whose whole job
    is to notice what widened.
    """
    if not isinstance(node, dict) or not node:
        return False
    return set(node) == {"len", "value"} or set(node) <= {"Some", "None"}


def keys(node, prefix=""):
    # `memory.regions` needs no exclusion: it is a list, whose entries differ between
    # the two files by design and are never keys, and the walk does not enter lists.
    found = set()
    if isinstance(node, dict) and not is_value(node):
        for key, value in node.items():
            found.add(prefix + key)
            found |= keys(value, prefix + key + ".")
    return found


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    left, right = (keys(jsonc.load(p)) for p in sys.argv[1:3])
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
