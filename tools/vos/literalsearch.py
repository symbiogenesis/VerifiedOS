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


def expression(root: Node, terminal: bytes, *, left_name_boundary: bool = False) -> bytes:
    if not left_name_boundary:
        return _suffix(root, terminal)
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


@dataclass(frozen=True)
class CandidateTrie:
    names: tuple[str, ...]
    complete: re.Pattern[str]
    known_right: re.Pattern[str]

    def present(self, text: str, *, first: bool, final: bool) -> bool:
        """One native search with all window-edge constraints inside its scope."""
        low = _lowered(text)
        pattern = self.complete if final else self.known_right
        # Offset zero has no known preceding character in an interior window.
        # Starting at one also preserves overlapping alternatives at later starts.
        return pattern.search(low, 0 if first else 1) is not None

    def lines(self, text: str, *, lowered: str | None = None) -> Iterator[tuple[int, int, int]]:
        """Whole name-bearing source lines with unchanged indices and offsets.

        The input starts at a real line boundary and ends at a real line boundary
        or source EOF. The streaming caller must buffer incomplete source lines.
        """
        low = _lowered(text) if lowered is None else lowered
        if len(low) != len(text):
            raise LegacyRequiredError("lowercase changes source offsets")
        match = self.complete.search(low)
        cursor = index = 0
        while match is not None:
            start = text.rfind("\n", 0, match.start()) + 1
            end = text.find("\n", match.end())
            index += text.count("\n", cursor, start)
            yield index, start, end if end >= 0 else len(text)
            if end < 0:
                break
            cursor = start
            # Every match on this line is covered by retaining the whole line;
            # attribution and every id remain the legacy parser's decisions.
            match = self.complete.search(low, end + 1)


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
                or name != name.lower() or "\n" in name or "\r" in name):
            raise LegacyRequiredError("literal needs the complete legacy reader")
        total += len(name)
        if total > MAX_CHARACTERS:
            raise LegacyRequiredError("excessive aggregate literal size")
    root = build(tuple(name.encode("ascii") for name in names))
    try:
        complete = re.compile(expression(root, b"(?!\\w)", left_name_boundary=True).decode("ascii"))
        # Keeping this constraint at each terminal allows a failed longer EOF
        # alternative to fall back to a valid shorter literal at the SAME start.
        known_right = re.compile(expression(root, b"(?=\\W)", left_name_boundary=True).decode("ascii"))
    except (RecursionError, re.PatternError, OverflowError) as error:
        raise LegacyRequiredError("native trie compilation requires legacy use") from error
    return CandidateTrie(names, complete, known_right)


@dataclass(frozen=True)
class ByteTrie:
    literals: tuple[bytes, ...]
    pattern: re.Pattern[bytes] | None

    def present(self, window: bytes) -> bool:
        # An empty population has the same result as any() over no needles.
        return self.pattern.search(window) is not None if self.pattern is not None else False


def compile_literals(literals: tuple[bytes, ...]) -> ByteTrie:
    """Compile exact bytes, or require the unchanged any(needle in window) scan."""
    if type(literals) is not tuple or len(literals) > MAX_NAMES:
        raise LegacyRequiredError("excessive literal population")
    if not literals:
        return ByteTrie(literals, None)
    total = 0
    for literal in literals:
        if type(literal) is not bytes or not literal or len(literal) > MAX_NAME_LENGTH:
            raise LegacyRequiredError("empty, excessive or unsupported byte literal")
        total += len(literal)
        if total > MAX_CHARACTERS:
            raise LegacyRequiredError("excessive aggregate literal size")
    root = build(literals)
    try:
        pattern = re.compile(expression(root, b""))
    except (RecursionError, re.PatternError, OverflowError) as error:
        raise LegacyRequiredError("native byte trie compilation requires legacy use") from error
    return ByteTrie(literals, pattern)


@dataclass(frozen=True)
class ByteCandidates:
    sensitive: ByteTrie
    folded: ByteTrie
    overlap: int

    def present(self, window: bytes) -> bool:
        # Keep bytes.lower(), not Unicode folding, and never normalize literals.
        return (self.sensitive.present(window)
                or (self.folded.pattern is not None and self.folded.present(window.lower())))


def compile_bytes(sensitive: tuple[bytes, ...], folded: tuple[bytes, ...]) -> ByteCandidates:
    return ByteCandidates(compile_literals(sensitive), compile_literals(folded),
                          max((len(literal) for literal in (*sensitive, *folded)), default=1) - 1)
