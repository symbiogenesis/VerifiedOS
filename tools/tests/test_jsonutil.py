# SPDX-License-Identifier: Apache-2.0
"""Ordered JSON objects and ambiguous members, through the real decoder."""

import json
from functools import partial

from tests.harness import Case, ensure
from vos.jsonutil import unique_object


def _ordered_objects() -> None:
    decoded = json.loads('{"z": null, "a": [{"y": false, "x": 0}], "b": ""}',
                         object_pairs_hook=unique_object)
    ensure(list(decoded) == ["z", "a", "b"], "JSON member order changed")
    ensure(list(decoded["a"][0]) == ["y", "x"], "nested member order changed")
    ensure(decoded == {"z": None, "a": [{"y": False, "x": 0}], "b": ""},
           "JSON member values changed")
    ensure(json.loads('{}', object_pairs_hook=unique_object) == {}, "empty object changed")
    ensure(json.loads('[{"a": 1}, {"a": 2}]', object_pairs_hook=unique_object)
           == [{"a": 1}, {"a": 2}], "independent objects must not share key state")


def _duplicate_members() -> None:
    for text, key in (
        ('{"a": 1, "a": 2}', "a"),
        ('{"a": null, "a": null}', "a"),
        ('{"outer": [{"a": false, "a": true}]}', "a"),
        (r'{"a": 1, "\u0061": 2}', "a"),
        ('{"": 0, "": 1}', ""),
        ('{"b": 0, "a": 1, "b": 2, "a": 3}', "b"),
    ):
        try:
            json.loads(text, object_pairs_hook=unique_object)
        except ValueError as error:
            ensure(str(error) == f"duplicate JSON key: {key}",
                   "the first repeated decoded key must receive the existing diagnostic")
        else:
            raise AssertionError("ambiguous JSON object was accepted")


def _domain_error() -> None:
    keys: list[str] = []
    refusal = RuntimeError("domain-specific refusal")

    def duplicate(key: str) -> RuntimeError:
        keys.append(key)
        return refusal

    hook = partial(unique_object, duplicate_error=duplicate)
    json.loads('{"a": 1, "nested": {"a": 2}}', object_pairs_hook=hook)
    ensure(not keys, "valid objects must not invoke the error factory")
    try:
        json.loads(r'{"nested": [{"a": 1, "\u0061": 2}]}', object_pairs_hook=hook)
    except RuntimeError as error:
        ensure(error is refusal, "the caller's exception must propagate unchanged")
        ensure(keys == ["a"], "the error factory must receive the repeated decoded key once")
    else:
        raise AssertionError("the caller's duplicate-key refusal was lost")


def cases() -> list[Case]:
    return [Case("ordered-objects", _ordered_objects),
            Case("duplicate-members", _duplicate_members),
            Case("domain-error", _domain_error)]
