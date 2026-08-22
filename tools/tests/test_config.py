# SPDX-License-Identifier: Apache-2.0
"""The configuration decoder, held to its absent-answers-None contract.

`config` is the one decoder over the model's configuration, and every check
group that reads a figure stands on three promises here: an absent or broken
file answers `None` rather than raising, the key-set walk recognizes a *value*
by shape and never by leaf name, and the per-process parse memo still sees an
edit whose mtime moved. The corner pinned hardest is `_is_value`, because the
failure mode of widening it is a run that still prints "key sets agree".
"""

import os
import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import config
from vos.jsonc import Json


def _value_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        absent = Path(td) / "nowhere.json"
        ensure(config.value(absent, "a") is None, "an absent file must answer None")
        ensure(config.integer(absent, "a") is None,
               "integer over an absent file must answer None")

        broken = Path(td) / "broken.json"
        broken.write_text("{ not json", encoding="utf-8")
        ensure(config.value(broken, "a") is None,
               "an unparseable file must answer None, not raise")

        good = Path(td) / "good.json"
        good.write_text('{"a": {"b": 1}}', encoding="utf-8")
        ensure(config.value(good, "a", "b") == 1, "a keyed value must be found")
        ensure(config.value(good) == {"a": {"b": 1}},
               "no keys at all names the whole configuration")
        ensure(config.value(good, "a", "missing") is None,
               "a key that is not there must answer None")
        ensure(config.value(good, "a", "b", "deeper") is None,
               "a key path running past a leaf must answer None")


def _integer_excludes_bool() -> None:
    # `True` is an `int` in Python and a boolean in the configuration, so the
    # narrowing excludes it by name.
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        path = Path(td) / "c.json"
        path.write_text('{"flag": true, "n": 3, "s": "4"}', encoding="utf-8")
        ensure(config.value(path, "flag") is True,
               "value must still answer the boolean itself")
        ensure(config.integer(path, "flag") is None,
               "integer must exclude a boolean, True being an int in Python")
        ensure(config.integer(path, "n") == 3, "a whole number must narrow through")
        ensure(config.integer(path, "s") is None, "a string of digits is not an integer")


def _is_value_shapes() -> None:
    # The two shapes are an option and a bitvector literal, recognized by shape
    # and never by leaf name: a dict merely *called* `value` is surface a cut can
    # delete, and dropping it from the walk is how "key sets agree" goes blind.
    ensure(config._is_value({"len": 64, "value": "0x0"}),
           "a bitvector literal is one value")
    ensure(config._is_value({"Some": "SecondClass"}), "a Some option is one value")
    ensure(config._is_value({"None": None}), "a None option is one value")
    ensure(not config._is_value({}), "an empty dict is not a value")
    ensure(not config._is_value({"value": "0x0"}),
           "a bare key named value is surface, not a value: leaf-name matching "
           "is the exclusion that widens on its own")
    ensure(not config._is_value({"len": 64, "value": "0x0", "extra": 1}),
           "a widened literal shape is surface again")
    ensure(not config._is_value([1, 2]), "a non-dict is not a value")


# The walk fixture: one option, one bitvector literal, one dict merely named
# like a value's key, and one list the walk must not enter.
_NODE: Json = {"opt": {"Some": 5}, "bits": {"len": 8, "value": "0xff"},
               "plain": {"value": 1}, "regions": [1, {"a": 2}]}


def _keys_and_flat() -> None:
    ensure(config.keys(_NODE) == {"opt", "bits", "plain", "plain.value", "regions"},
           f"keys walked to {sorted(config.keys(_NODE))}: values must not be "
           f"descended, a value-named leaf must be, and lists are never entered")
    ensure(config.flat(_NODE) == {"opt": {"Some": 5},
                                  "bits": {"len": 8, "value": "0xff"},
                                  "plain.value": 1, "regions": [1, {"a": 2}]},
           f"flat gave {config.flat(_NODE)}: a value and a list are each one leaf")
    ensure(config.flat(5) == {"": 5},
           "flat on a non-dict root is the empty key naming the root")


def _flat_of_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        ensure(config.flat_of(Path(td) / "nowhere.json") == {},
               "flat_of over an absent file must answer empty")
        broken = Path(td) / "broken.json"
        broken.write_text("{ not json", encoding="utf-8")
        ensure(config.flat_of(broken) == {},
               "flat_of over an unparseable file must answer empty")
        good = Path(td) / "good.json"
        good.write_text('{"a": {"b": 1}}', encoding="utf-8")
        ensure(config.flat_of(good) == {"a.b": 1}, "flat_of must flatten a real file")


def _compare_keys_both_directions() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        left = Path(td) / "left.json"
        right = Path(td) / "right.json"
        left.write_text('{"common": {"x": 1}, "left_only": 2}', encoding="utf-8")
        right.write_text('{"common": {"x": 9}, "right_only": 3}', encoding="utf-8")
        code, out = config.compare_keys(left, right)
        ensure(code == 1, "a key on one side only is a finding")
        ensure(out == [f"only in {left}:", "  left_only",
                       f"only in {right}:", "  right_only"],
               f"the report must name both directions, got {out}")

        code, out = config.compare_keys(left, left)
        ensure(code == 0, "one file against itself must agree")
        ensure(out == ["key sets agree (3 keys)"],
               f"agreement is one line with the count, got {out}")


def _memo_sees_mtime() -> None:
    # The parse memo is keyed on (path, mtime_ns), so a rewrite whose mtime moved
    # must be re-read rather than answered from the earlier parse. The bump is
    # explicit `os.utime` because a same-instant rewrite is below the filesystem
    # clock's resolution, and that case is deliberately not promised.
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        path = Path(td) / "c.json"
        path.write_text('{"k": 1}', encoding="utf-8")
        ensure(config.value(path, "k") == 1, "the first parse must answer the file")
        stamp = path.stat().st_mtime_ns
        path.write_text('{"k": 2}', encoding="utf-8")
        os.utime(path, ns=(stamp + 1_000_000_000, stamp + 1_000_000_000))
        ensure(config.value(path, "k") == 2,
               "an mtime-visible rewrite must be re-read, not served from the memo")


def _undeclared_walk() -> None:
    # The back-direction of validate: recurse only under a literal "properties",
    # leave anyOf/oneOf combinators alone, and name every config key the schema
    # does not declare.
    schema: Json = {"properties": {"a": {"properties": {"b": {}}},
                                   "c": {"anyOf": [{"properties": {"x": {}}}]}}}
    cfg: Json = {"a": {"b": 1, "z": 2}, "c": {"x": 1}, "d": 3}
    ensure(config._undeclared(cfg, schema) == ["a/z", "d"],
           f"_undeclared found {config._undeclared(cfg, schema)}: it must descend "
           f"declared properties, skip combinators, and name the two stray keys")


def cases() -> list[Case]:
    return [
        Case("value-contract", _value_contract),
        Case("integer-excludes-bool", _integer_excludes_bool),
        Case("is-value-shapes", _is_value_shapes),
        Case("keys-and-flat", _keys_and_flat),
        Case("flat-of-contract", _flat_of_contract),
        Case("compare-keys-both-directions", _compare_keys_both_directions),
        Case("memo-sees-mtime", _memo_sees_mtime),
        Case("undeclared-walk", _undeclared_walk),
    ]
