# SPDX-License-Identifier: Apache-2.0
"""Checked Markdown references in live source comments and Python docstrings.

File paths are relative to the source carrying the reference. Fragments select
Markdown headings/anchors or declarations in Python, Gallina and Sail. Python
targets are read with the AST, never imported; Gallina uses the existing source
name reader and Sail uses the compiler bundle with its complete source identity.
This is navigation validation, not proof, compilation or behavioral acceptance.
"""

import ast
import io
import re
import textwrap
import tokenize
from bisect import bisect_right
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, override
from urllib.parse import unquote, urlsplit

from vos import proofcites, prooflex, sailbundle

if TYPE_CHECKING:
    from markdown_it import MarkdownIt

    from vos.corpus import Corpus

SUFFIXES = frozenset({".py", ".v", ".sail", ".c", ".h", ".cc", ".cpp", ".hpp",
                      ".sv", ".svh"})
_HISTORICAL = "docs/implementation/retained-evidence/"
_QUOTES = re.compile(r"(?i)^[rub]*(\"\"\"|'''|\"|')")
_C_TOKEN = re.compile(r'"(?:\\[\s\S]|[^"\\])*"|//(?:\\\r?\n|[^\r\n])*|/\*|\*/')
_C_CHAR = re.compile(r"'(?:\\[^\r\n]|[^'\\\r\n])*'")
_CPP_RAW = r'(?:u8|u|U|L)?R"(?P<raw_delimiter>[^\s()\\]{0,16})\('
_BLOCK_TOKEN = re.compile(r"/\*|\*/")


@dataclass(frozen=True)
class Reference:
    line: int
    target: str


def is_source(rel: str) -> bool:
    """Historical snapshots retain their original links; indexed live kinds grow."""
    return not rel.startswith(_HISTORICAL) and PurePosixPath(rel).suffix in SUFFIXES


def _normal(text: str) -> str:
    """Remove comment margins while retaining physical source line numbers."""
    lines = text.split("\n")
    if not lines:
        return text
    lines[0] = lines[0].lstrip()
    if len(lines) > 1:
        lines[1:] = textwrap.dedent("\n".join(lines[1:])).split("\n")
    return "\n".join(lines)


def _python(text: str) -> Iterator[tuple[int, str]]:
    tree = ast.parse(text)
    docstrings: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if (node.body and isinstance(first := node.body[0], ast.Expr)
                and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str)):
            if first.value.end_lineno is None or first.value.end_col_offset is None:
                raise ValueError("Python docstring has no complete source span")
            docstrings.append(((first.value.lineno, first.value.col_offset),
                               (first.value.end_lineno, first.value.end_col_offset)))
    # A single projected comment document allows reference definitions on adjacent
    # comment lines. Non-comments remain blank, so string fixtures are never read.
    comments = [""] * len(text.split("\n"))
    source_lines = text.split("\n")
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT:
            comments[token.start[0] - 1] = token.string[1:].removeprefix(" ")
        elif token.type == tokenize.STRING:
            # AST columns count UTF-8 bytes; tokenize columns count characters.
            begin = (token.start[0], len(source_lines[token.start[0] - 1][:token.start[1]].encode("utf-8")))
            end = (token.end[0], len(source_lines[token.end[0] - 1][:token.end[1]].encode("utf-8")))
            if not any(first <= begin and end <= last for first, last in docstrings):
                continue
            match = _QUOTES.match(token.string)
            if match:
                quote = match.group(1)
                yield token.start[0], _normal(token.string[match.end():-len(quote)])
    yield 1, "\n".join(comments)


def _c_comments(text: str, *, chars: bool, nested: bool, cpp: bool) -> Iterator[tuple[int, str]]:
    """Locate C-like comments, without treating Sail/SV apostrophes as strings."""
    pattern = re.compile((_CPP_RAW + "|" if cpp else "") + _C_TOKEN.pattern
                         + ("|" + _C_CHAR.pattern if chars else ""))
    depth = start = at = 0
    while token := (_BLOCK_TOKEN if depth else pattern).search(text, at):
        at = token.end()
        value = token.group()
        if depth:
            if value == "/*" and nested:
                depth += 1
            elif value == "*/":
                depth -= 1
                if not depth:
                    yield start, text[start + 2:token.start()]
        elif cpp and (delimiter := token.group("raw_delimiter")) is not None:
            ending = ")" + delimiter + '"'
            end = text.find(ending, at)
            if end < 0:
                raise ValueError("unterminated C++ raw string")
            at = end + len(ending)
        elif value == "/*":
            depth, start = 1, token.start()
        elif value.startswith("//"):
            yield token.start(), value[2:]
    if depth:
        raise ValueError("unterminated block comment")


def prose(rel: str, text: str) -> Iterator[tuple[int, str]]:
    """Comment/docstring blocks as their one-based start line and Markdown text."""
    suffix = PurePosixPath(rel).suffix
    if suffix == ".py":
        yield from _python(text)
        return
    if suffix == ".v":
        regions = []
        for part in prooflex.regions(text, strings_in_comments=True):
            if not part.closed:
                raise ValueError("unclosed string/comment or unmatched comment ending")
            if part.kind == "comment":
                regions.append((part.start, text[part.start + 2:part.end - 2]))
    else:
        regions = list(_c_comments(text, chars=suffix not in {".sail", ".sv", ".svh"},
                                   nested=suffix == ".sail", cpp=suffix in {".cc", ".cpp", ".hpp"}))
    projected = [""] * len(text.split("\n"))
    starts = [0, *(match.end() for match in re.finditer("\n", text))]
    for start, body in regions:
        line = bisect_right(starts, start) - 1
        for offset, value in enumerate(_normal(body).split("\n")):
            # Conventional block-comment '*' margins have no Markdown meaning.
            marginless = re.sub(r"^[ \t]*\* ?", "", value)
            separator = " " if projected[line + offset] else ""
            projected[line + offset] += separator + marginless
    yield 1, "\n".join(projected)


@cache
def _markdown() -> MarkdownIt:
    from markdown_it import MarkdownIt  # noqa: PLC0415

    class LinkParser(MarkdownIt):
        @override
        def validateLink(self, url: str) -> bool:
            # Validation reads destinations, never renders or opens them. Keep
            # file: destinations visible so local-path policy can refuse them.
            return True

    return LinkParser("commonmark")


def references(rel: str, text: str) -> Iterator[Reference]:
    """Use CommonMark links, including reference-style links and excluding code."""
    for start, block in prose(rel, text):
        lines = block.split("\n")
        for token in _markdown().parse(block):
            if token.type != "inline" or token.children is None or token.map is None:
                continue
            cursor = token.map[0]
            for child in token.children:
                if child.type not in {"link_open", "image"}:
                    continue
                target = child.attrGet("href" if child.type == "link_open" else "src")
                if target is None:
                    continue
                if not isinstance(target, str):
                    raise TypeError("Markdown link destination is not text")
                # Inline tokens have block source maps. Locate an explicit URL
                # within that block when available; reference-style links retain
                # the referring block's first line rather than the definition's.
                line = next((n for n in range(cursor, token.map[1]) if target in lines[n]), cursor)
                cursor = line
                yield Reference(start + line, target)


def _local(source: str, target: str) -> tuple[str, str] | None:
    parsed = urlsplit(target)
    if re.match(r"^[A-Za-z]:", target):
        raise ValueError("local references cannot use a Windows drive path")
    if (parsed.scheme and parsed.scheme != "file") or parsed.netloc:
        return None
    path, fragment = unquote(parsed.path), unquote(parsed.fragment)
    if (parsed.scheme or parsed.query or "\\" in path or "\0" in path
            or any(ord(char) < 32 for char in path + fragment) or path.startswith("/")):
        raise ValueError("local references require a relative file path without a query")
    if not path:
        return source, fragment
    parts = list(PurePosixPath(source).parent.parts)
    for part in path.split("/"):
        if part == "..":
            if not parts:
                raise ValueError("local reference escapes the repository")
            parts.pop()
        elif part not in {"", "."}:
            if ":" in part:
                raise ValueError("local reference contains an unsafe path component")
            parts.append(part)
    return "/".join(parts), fragment


def _safe(root: Path, rel: str) -> Path:
    path = root
    for part in PurePosixPath(rel).parts:
        path /= part
        if path.is_symlink() or path.is_junction():
            raise ValueError(f"{rel}: symbolic links and junctions are not reference targets")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"{rel}: reference escapes the repository")
    return path


def python_names(text: str) -> set[str]:
    """Lexical qualified declarations; importing a target is never necessary."""
    names: set[str] = set()

    def bindings(target: ast.expr) -> Iterator[str]:
        if isinstance(target, ast.Name):
            yield target.id
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                yield from bindings(element)
        elif isinstance(target, ast.Starred):
            yield from bindings(target.value)

    def visit(nodes: list[ast.stmt], prefix: str) -> None:
        for node in nodes:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + node.name
                names.add(name)
                visit(node.body, name + ".")
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    names.update(prefix + name for name in bindings(target))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.add(prefix + node.target.id)
            elif isinstance(node, ast.TypeAlias):
                names.add(prefix + node.name.id)
            else:
                # Conditional declarations retain their lexical owner. Local
                # imports are references, not declarations defined by this file.
                for _field, value in ast.iter_fields(node):
                    if isinstance(value, list) and value and all(isinstance(n, ast.stmt) for n in value):
                        visit(value, prefix)

    visit(ast.parse(text).body, "")
    return names


def findings(root: Path, corpus: Corpus) -> list[str]:
    """Validate every indexed live source reference; failures never rewrite prose."""
    faults: list[str] = []
    texts: dict[str, str] = {}
    symbols: dict[str, set[str]] = {}
    sail: dict[str, set[str]] | None = None

    def read(rel: str) -> str:
        if rel not in texts:
            texts[rel] = _safe(root, rel).read_bytes().decode("utf-8")
        return texts[rel]

    def declarations(rel: str) -> set[str]:
        nonlocal sail
        suffix = PurePosixPath(rel).suffix
        if suffix == ".sail":
            if sail is None:
                if not {sailbundle.BUNDLE, sailbundle.SOURCE_IDENTITY} <= corpus.indexed:
                    raise ValueError("Sail bundle and source identity must be indexed")
                raw = _safe(root, sailbundle.BUNDLE).read_bytes()
                owners = sailbundle.read_source_identity(root, raw)
                sail = {owner: set[str]() for owner in owners}
                for declaration in sailbundle.parse(raw).declarations():
                    file = declaration.source.file
                    owner = f"{sailbundle.SOURCE_ROOT}/{file}"
                    if file is not None and owner in sail:
                        sail[owner].add(declaration.name)
            if rel not in sail:
                raise ValueError(f"{rel}: not a recorded local Sail source owner")
            return sail[rel]
        if rel not in symbols:
            if suffix == ".py":
                symbols[rel] = python_names(read(rel))
            elif suffix == ".v":
                symbols[rel] = set(proofcites.names(read(rel)))
            elif suffix == ".md":
                doc = corpus.get(rel)
                if doc is None:
                    raise ValueError(f"{rel}: not an indexed Markdown document in the corpus")
                symbols[rel] = doc.targets
            else:
                raise ValueError(f"{rel}: fragments are unsupported for this target kind")
        return symbols[rel]

    def validate(source: str, ref: Reference) -> None:
        resolved = _local(source, ref.target)
        if resolved is None:
            return
        target, fragment = resolved
        if target in corpus.gitlinks and not fragment:
            return
        if target not in corpus.indexed:
            prefix = target + "/" if target else ""
            if any(rel.startswith(prefix) for rel in corpus.indexed):
                if fragment:
                    raise ValueError(f"{target}: directory references cannot select a fragment")
                if not _safe(root, target).is_dir():
                    raise ValueError(f"{target}: indexed directory is missing from the working tree")
                return
            raise ValueError(f"{target}: target is not an indexed file (paths are case-sensitive)")
        if not _safe(root, target).is_file():
            raise ValueError(f"{target}: indexed target is missing from the working tree")
        if fragment and fragment not in declarations(target):
            raise ValueError(f"{target}: no heading, anchor or supported declaration #{fragment}")

    sources = sorted(rel for rel in corpus.indexed if is_source(rel))
    if not sources:
        return ["the index carries no live source file for comment-reference validation"]
    for source in sources:
        try:
            text = read(source)
            # A CommonMark local link or reference definition contains a closing
            # label followed by a destination, label or colon. Skip unrelated
            # source before paying for AST/tokenization and comment projection.
            if not re.search(r"\][ \t\r\n]*(?:\(|\[|:)", text):
                continue
            refs = list(references(source, text))
        except (OSError, UnicodeError, ValueError, TypeError, SyntaxError, tokenize.TokenError) as exc:
            faults.append(f"{source}: cannot read source references: {exc}")
            continue
        for ref in refs:
            try:
                validate(source, ref)
            except (OSError, UnicodeError, ValueError, SyntaxError, sailbundle.BundleError) as exc:
                faults.append(f"{source}:{ref.line} {ref.target}: {exc}")
    return faults
