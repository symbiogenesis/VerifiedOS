# SPDX-License-Identifier: Apache-2.0
"""Shared region boundaries and the proof readers' distinct malformed-input policies."""

from tests.harness import Case, ensure
from vos import prooflex, proofs, proofsearch


def _regions_keep_source_boundaries() -> None:
    fixtures: list[tuple[str, list[tuple[str, str, bool]]]] = [
        ('x(* outer (* inner *) tail *)y',
         [("comment", "(* outer (* inner *) tail *)", True)]),
        ('x"a""(* literal *)"y', [("string", '"a""(* literal *)"', True)]),
        ('x(* "*)" *)y', [("comment", '(* "*)" *)', True)]),
        ('x(* "never *)y', [("comment", '(* "never *)y', False)]),
        ('x"never (*', [("string", '"never (*', False)]),
        ('x*)y', [("unmatched-end", '*)', False)]),
    ]
    for source, expected in fixtures:
        regions = list(prooflex.regions(source, strings_in_comments=True))
        ensure([(region.kind, source[region.start:region.end], region.closed)
                for region in regions] == expected, f"region boundary changed: {source!r}")
        ensure(all(0 <= region.start < region.end <= len(source) for region in regions),
               "every region must refer to existing source characters")


def _reader_malformed_input_policies() -> None:
    # Navigation deliberately ignores quotes while inside a comment; the gate's
    # source reading treats them as strings. Sharing mechanics must not promote
    # either caller's tolerance or quoted-comment rule to a universal policy.
    fixtures = [
        ('a *) b', 'a *) b', "line 1: unmatched comment ending"),
        ('a\r\n*)', 'a\r\n*)', "line 2: unmatched comment ending"),
        ('a(* never', 'a ', "unterminated comment"),
        ('"never(*', '"never(*', "unterminated string"),
        ('a(* "*)" *)b', 'a b', "unterminated string"),
        ('a(* "(*" *)b', 'a b', "unterminated comment"),
    ]
    for source, tolerant, diagnostic in fixtures:
        ensure(proofs.strip_comments(source) == tolerant,
               f"the tolerant reader changed its malformed-input reading: {source!r}")
        try:
            proofsearch._masked(source)
        except ValueError as error:
            ensure(str(error) == diagnostic, f"navigation diagnostic changed: {error}")
        else:
            raise AssertionError(f"navigation accepted malformed input: {source!r}")
    source = 'a(* " *)b'
    ensure(proofs.strip_comments(source) == 'a ',
           "an unfinished quoted comment must extend to EOF in the gate's reading")
    ensure(proofsearch._masked(source) == 'a' + ' ' * 7 + 'b',
           "navigation's comment delimiters must stay active inside quoted comment text")


def _generated_nested_comments_and_strings() -> None:
    # Independent constructions provide their known boundaries: nested comments
    # surround harmless text, and doubled quotes encode string payloads whose
    # comment-like text must remain inside the string.
    for depth in range(1, 6):
        for ending in ('', '\n', '\r\n'):
            comment = '(*' * depth + 'hidden' + ending + '*)' * depth
            source = 'before' + comment + 'after'
            separator = '\n' if ending else ' '
            ensure(proofs.strip_comments(source) == 'before' + separator + 'after',
                   "nested comments must remain token separators")
            kept = proofs.strip_comments(source, keep_offsets=True)
            masked = proofsearch._masked(source)
            ensure(len(kept) == len(masked) == len(source), "source offsets moved")
            ensure([i for i, char in enumerate(kept) if char == '\n']
                   == [i for i, char in enumerate(source) if char == '\n'],
                   "the gate's source line offsets moved")
            ensure([i for i, char in enumerate(masked) if char in '\r\n']
                   == [i for i, char in enumerate(source) if char in '\r\n'],
                   "navigation's CRLF positions moved")
    for payload in ('', 'a', '(* x *)', 'a"b', '"(*"', 'x\r\ny'):
        quoted = '"' + payload.replace('"', '""') + '"'
        source = 'before' + quoted + 'after'
        ensure(proofs.strip_comments(source) == source, "string contents became comments")
        expected = 'before"' + ''.join(char if char in '\r\n' else ' '
                                      for char in quoted[1:-1]) + '"after'
        ensure(proofsearch._masked(source) == expected,
               "navigation must mask doubled quotes and retain the outer quotes")


def cases() -> list[Case]:
    return [
        Case("regions-keep-source-boundaries", _regions_keep_source_boundaries),
        Case("reader-malformed-input-policies", _reader_malformed_input_policies),
        Case("generated-nested-comments-and-strings", _generated_nested_comments_and_strings),
    ]
