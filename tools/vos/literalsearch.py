# SPDX-License-Identifier: Apache-2.0
"""Bounded native literal searches; unsupported shapes retain their original reader."""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

MAX_NAMES = 256
MAX_NAME_LENGTH = 64
MAX_CHARACTERS = 4096


class LegacyRequiredError(ValueError):
    """The unchanged literal scan or complete parser must handle this input."""


@dataclass
class Node:
    terminal: bool = False
    children: dict[int, Node] = field(default_factory=dict)


def build(literals: tuple[bytes, ...]) -> Node:
    root = Node()
    for literal in literals:
        node = root
        for character in literal:
            if character not in node.children:
                node.children[character] = Node()
            node = node.children[character]
        node.terminal = True
    return root


def _alternatives(branches: list[bytes]) -> bytes:
    return branches[0] if len(branches) == 1 else b"(?:" + b"|".join(branches) + b")"


def _suffix(node: Node, terminal: bytes) -> bytes:
    branches = [re.escape(bytes((character,))) + _suffix(child, terminal)
                for character, child in sorted(node.children.items())]
    if node.terminal:
        branches.append(terminal)
    return _alternatives(branches)


def expression(root: Node, terminal: bytes) -> bytes:
    branches = []
    for character, child in sorted(root.children.items()):
        first = re.escape(bytes((character,)))
        branches.append(first + b"(?<![\\w-]" + first + b")" + _suffix(child, terminal))
    return _alternatives(branches)


def _lowered(text: str) -> str:
    low = text.lower()
    if len(low) != len(text):
        raise LegacyRequiredError("lowercase changes source offsets")
    return low


def _skip_expression(root: str, first: str) -> str:
    # Valid names start only at the beginning of a [\w-] run. Consume every
    # unmatched word/nonword block once and stop before the first possible name.
    # Neither a separator run nor a word starting outside the literal first-set
    # can contain a valid start. Avoid testing the full trie at those positions.
    # An arbitrary initial offset may lie inside a word. Skip that remainder
    # once; each later alternative consumes a complete word or separator run,
    # establishing the left boundary without a lookbehind in every trie branch.
    return (r"(?:(?<=[\w-])[\w-]*+)?+(?:[^\w-]++|(?!" + first + r")[\w-]++|(?!"
            + root + r")[\w-]++)*+(" + root + ")")


@dataclass(frozen=True)
class CandidateTrie:
    names: tuple[str, ...]
    complete: re.Pattern[str]
    known_right: re.Pattern[str]
    ascii_complete: re.Pattern[str]
    ascii_known_right: re.Pattern[str]

    def _span(self, low: str, *, pos: int, final: bool) -> tuple[int, int] | None:
        if low.isascii():
            # The whole lowered window, including both boundary characters,
            # establishes that ASCII and Unicode word classes are identical.
            pattern = self.ascii_complete if final else self.ascii_known_right
        else:
            pattern = self.complete if final else self.known_right
        # search() would retry a failed suffix scan at every position. One
        # anchored match owns the forward scan; group 1 excludes skipped text.
        match = pattern.match(low, pos)
        return match.span(1) if match is not None else None

    def present(self, text: str, *, first: bool, final: bool) -> bool:
        """One anchored scan with all window-edge constraints inside its scope."""
        # Offset zero has no known preceding character in an interior window.
        # Starting at one also preserves overlapping alternatives at later starts.
        return self._span(_lowered(text), pos=0 if first else 1, final=final) is not None

    def lines(self, text: str, *, lowered: str | None = None) -> Iterator[tuple[int, int, int]]:
        """Whole name-bearing source lines with unchanged indices and offsets.

        The input starts at a real line boundary and ends at a real line boundary
        or source EOF. The streaming caller must buffer incomplete source lines.
        """
        low = _lowered(text) if lowered is None else lowered
        if len(low) != len(text):
            raise LegacyRequiredError("lowercase changes source offsets")
        span = self._span(low, pos=0, final=True)
        cursor = index = 0
        while span is not None:
            start = text.rfind("\n", 0, span[0]) + 1
            end = text.find("\n", span[1])
            index += text.count("\n", cursor, start)
            yield index, start, end if end >= 0 else len(text)
            if end < 0:
                break
            cursor = start
            # Every match on this line is covered by retaining the whole line;
            # attribution and every id remain the legacy parser's decisions.
            span = self._span(low, pos=end + 1, final=True)


def compile_names(names: tuple[str, ...]) -> CandidateTrie:
    """Compile small, checked, normalized literal sets, or require legacy use.

    Bounds precede recursive construction/compilation. No persistent cache or
    acceptance result is created, and the original attribution list is untouched.
    """
    if type(names) is not tuple or not names or len(names) > MAX_NAMES:
        raise LegacyRequiredError("empty or excessive name population")
    total = 0
    for name in names:
        if (type(name) is not str or not name or len(name) > MAX_NAME_LENGTH or not name.isascii()
                or name != name.lower() or "\n" in name or "\r" in name
                or not (name[0].isalnum() or name[0] in "_-")):
            raise LegacyRequiredError("literal needs the complete legacy reader")
        total += len(name)
        if total > MAX_CHARACTERS:
            raise LegacyRequiredError("excessive aggregate literal size")
    root = build(tuple(name.encode("ascii") for name in names))
    first = "[" + re.escape("".join(sorted({name[0] for name in names}))) + "]"
    try:
        complete_source = _skip_expression(_suffix(root, b"(?!\\w)").decode("ascii"), first)
        complete = re.compile(complete_source)
        # Keeping this constraint at each terminal allows a failed longer EOF
        # alternative to fall back to a valid shorter literal at the SAME start.
        known_right_source = _skip_expression(_suffix(root, b"(?=\\W)").decode("ascii"), first)
        known_right = re.compile(known_right_source)
        ascii_complete = re.compile(complete_source, re.ASCII)
        ascii_known_right = re.compile(known_right_source, re.ASCII)
    except (RecursionError, re.PatternError, OverflowError) as error:
        raise LegacyRequiredError("native trie compilation requires legacy use") from error
    return CandidateTrie(names, complete, known_right, ascii_complete, ascii_known_right)
