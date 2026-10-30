# SPDX-License-Identifier: Apache-2.0
"""Composed policy YAML preserves marks and refuses ambiguous interpretations."""

from yaml.nodes import MappingNode, ScalarNode

from tests.harness import Case, ensure
from vos import yamlutil


def _keys_and_source_marks() -> None:
    source = ('on: yes\nsteps:\n  - "u\\x73es": example/action\n'
              '    run: |\n      uses: text\n# uses: comment\n')
    root = yamlutil.read(source)
    if not isinstance(root, MappingNode):
        raise TypeError("the root must retain its mapping shape")
    fields = yamlutil.fields(root)
    ensure(list(fields) == ["on", "steps"], "plain YAML keys must stay text")
    ensure(isinstance(fields["on"], ScalarNode) and fields["on"].value == "yes",
           "plain yes must stay text without YAML 1.1 boolean coercion")
    found = [(key.value, yamlutil.start(key).line, yamlutil.start(key).column)
             for node in yamlutil.mappings(root) for key, _value in node.value]
    ensure(found == [("on", 0, 0), ("steps", 1, 0), ("uses", 2, 4), ("run", 3, 4)],
           f"keys must be decoded without treating scalar bodies as mappings: {found!r}")
    ensure(yamlutil.lines(source)[2] == '  - "u\\x73es": example/action',
           "marks must identify original source lines")


def _ambiguous_or_malformed_documents_refuse() -> None:
    for source, diagnostic in (
        ("", "empty YAML"),
        ("a: [", "invalid YAML"),
        ("a: b\n---\nc: d\n", "invalid YAML"),
        ("a: one\na: two\n", "duplicate YAML key 'a'"),
        ('a: one\n"\\x61": two\n', "duplicate YAML key 'a'"),
        ("a: {b: one, b: two}", "duplicate YAML key 'b'"),
        ("? [a, b]\n: c\n", "mapping keys must be strings"),
        ("a: &base {b: c}\nd: *base\n", "aliases and cycles"),
        ("a: &cycle [*cycle]\n", "aliases and cycles"),
        ("a: {<<: {b: c}}\n", "merge keys"),
        ("a: !unknown value\n", "tag '!unknown'"),
        ("a: !!python/object/apply:builtins.eval ['1 + 1']\n", "tag"),
        ("a: !!int 10\n", "tag"),
        ("a: !!map scalar\n", "not admitted for str"),
        ("a: !!str {}\n", "not admitted for map"),
        ("a: !!str []\n", "not admitted for seq"),
    ):
        try:
            yamlutil.read(source)
        except ValueError as error:
            ensure(diagnostic in str(error), f"wrong YAML refusal for {source!r}: {error}")
        else:
            raise AssertionError(f"ambiguous or malformed YAML was admitted: {source!r}")


def _yaml_line_breaks_keep_marks() -> None:
    for separator in ("\n", "\r\n", "\r", "\x85", "\u2028", "\u2029"):
        source = separator.join(("a: one", "b: two", ""))
        root = yamlutil.read(source)
        ensure(isinstance(root, MappingNode), "the root must be a mapping")
        ensure([yamlutil.start(key).line for key, _value in root.value] == [0, 1],
               f"YAML line breaks must agree with node marks: {separator!r}")
        ensure(yamlutil.lines(source) == ["a: one", "b: two", ""],
               f"source line splitting must follow YAML: {separator!r}")


def cases() -> list[Case]:
    return [Case("keys-and-source-marks", _keys_and_source_marks),
            Case("ambiguous-or-malformed-documents-refuse", _ambiguous_or_malformed_documents_refuse),
            Case("yaml-line-breaks-keep-marks", _yaml_line_breaks_keep_marks)]
