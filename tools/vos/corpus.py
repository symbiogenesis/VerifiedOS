# SPDX-License-Identifier: Apache-2.0
"""Load the tracked Markdown document corpus, Git index membership, and gitlink pins.

Each [`Document`](#Document) stores its raw text, lines, line-start offsets, CommonMark
code-block mask (`fenced`), headings, and link targets (`slug(heading)` and `<a id="...">`
anchors outside code blocks).
"""

import bisect
import gzip
import os
import re
import subprocess
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from vos import proofenv

if TYPE_CHECKING:
    from markdown_it import MarkdownIt

# Retained text may have a lossless compressed representation. Scanners read its
# original bytes so a storage change does not hide a citation or encoding defect.
COMPRESSED_EVIDENCE = "docs/implementation/retained-evidence/"


def gzip_contents(blob: bytes) -> bytes:
    """Require a gzip member rather than accepting empty or plaintext evidence."""
    if not blob.startswith(b"\x1f\x8b"):
        raise ValueError("missing gzip header")
    return gzip.decompress(blob)


def scan_bytes(root: Path, rel: str) -> bytes:
    """Read one indexed surface, expanding retained gzip evidence losslessly."""
    blob = (root / rel).read_bytes()
    if rel.startswith(COMPRESSED_EVIDENCE) and rel.endswith(".gz"):
        return gzip_contents(blob)
    return blob

# Semantic readers retain their prescribed line forms. General Markdown structure
# comes from the shared CommonMark parser, without serializing its tokens to disk.
ANCHOR_RE = re.compile(r'<a id="([^"]+)"')
HEADING_RE = re.compile(r"#{1,6}[ \t]+([^\r\n]+)")

_TAG_RE = re.compile(r"<[^>]+>")
_PUNCT_RE = re.compile(r"[^\w\s-]")
_SPACE_RE = re.compile(r"\s+")


@cache
def _markdown() -> MarkdownIt:
    # The launcher imports corpus to find its root before entering the locked
    # environment. Resolve third-party parser code only when a document is read.
    from markdown_it import MarkdownIt  # noqa: PLC0415

    # Structural readers need block maps and the unexpanded inline token's
    # content, never its children. Keep the same block grammar and normalization;
    # omitting inline expansion avoids parsing every document's links twice.
    return MarkdownIt("commonmark", {"html": True}).enable("table").disable("inline")


def _syntax(lines: list[str]) -> tuple[list[bool], list[tuple[int, str]]]:
    """Read code regions and headings from maintained token source maps."""
    fenced = [False] * len(lines)
    headings: list[tuple[int, str]] = []
    tokens = _markdown().parse("\n".join(line.removesuffix("\r") for line in lines))
    for index, token in enumerate(tokens):
        if token.type not in {"fence", "code_block", "heading_open"}:
            continue
        if token.map is None:
            raise ValueError(f"Markdown {token.type} token has no source map")
        start, end = token.map
        if not 0 <= start < end <= len(lines):
            raise ValueError(f"Markdown {token.type} token has an invalid source map")
        if token.type in {"fence", "code_block"}:
            fenced[start:end] = [True] * (end - start)
        else:
            if index + 1 == len(tokens) or tokens[index + 1].type != "inline":
                raise ValueError("Markdown heading has no inline content token")
            headings.append((start, tokens[index + 1].content))
    return fenced, headings


def fence_lines(lines: list[str]) -> list[bool]:
    """Mask fenced, container and indented code, retaining the historical API name."""
    return _syntax(lines)[0]


def slug(heading: str) -> str:
    """A heading's fragment id: tags and backticks vanish, punctuation vanishes,
    spaces hyphenate. Markdown makes no distinction between a slug and a declared
    bookmark, so a link may name either."""
    text = _TAG_RE.sub("", heading).replace("`", "").strip().lower()
    return _SPACE_RE.sub("-", _PUNCT_RE.sub("", text))


@dataclass
class Document:
    name: str
    raw: str
    lines: list[str]
    starts: list[int]
    fenced: list[bool]
    targets: set[str] = field(default_factory=set)
    headings: list[tuple[int, str]] = field(default_factory=list)

    def line_of(self, offset: int) -> int:
        """The 0-based line containing a raw-text offset."""
        return bisect.bisect_right(self.starts, offset) - 1

    def at(self, offset: int) -> int:
        """The 1-based line, for a finding a person has to go and visit."""
        return self.line_of(offset) + 1

    def is_fenced(self, offset: int) -> bool:
        return self.fenced[self.line_of(offset)]

    def unfenced(self, lead: str,
                 pattern: re.Pattern[str]) -> Iterator[tuple[int, re.Match[str]]]:
        """Yield `(0_based_line_index, match)` for unfenced lines containing `lead` and matching `pattern`."""
        for i, line in enumerate(self.lines):
            if lead in line and not self.fenced[i] and (m := pattern.match(line)):
                yield i, m


def _read(path: Path, name: str) -> Document:
    try:
        raw = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"{name} is not valid UTF-8: {exc}") from exc

    return from_text(raw, name)


def from_text(raw: str, name: str) -> Document:
    """Parse decoded UTF-8 `raw` text into a [`Document`](#Document)."""
    parts = raw.split("\n")
    starts: list[int] = []
    offset = 0
    for part in parts:
        starts.append(offset)
        offset += len(part) + 1

    body = parts[:-1] if parts and parts[-1] == "" else parts
    lines = [p.removesuffix("\r") for p in body]

    try:
        fenced, headings = _syntax(lines)
    except ValueError as exc:
        raise RuntimeError(f"{name}: {exc}") from exc
    return Document(name=name, raw=raw, lines=lines, starts=starts, fenced=fenced,
                    headings=headings)


PROSE = "docs/spec.md"
PROSE_SECTION_RE = re.compile(r"## (\d+)\.")

# Shared by the corpus exclusion and the selftest's sandbox.
UNREAD_PREFIX = "model/"

# Model files whose values are checked against documentation (copied into the selftest sandbox).
MODEL_FACTS = (
    "model/model/riscv.sail_project",
    "model/model/core/cap_format.sail",
    "model/model/core/cap_common.sail",
    "model/model/core/xlen.sail",
    "model/model/core/timing.sail",
    "model/model/core/extensions.sail",
    "model/model/core/platform_config.sail",
    "model/model/postlude/device_tree.sail",
    "model/model/postlude/validate_config.sail",
    "model/model/unit_tests/test_cheri_insts.sail",
    "model/config/verifiedos.json",
    "model/config/verifiedos-v.json",
    "model/config/verifiedos-rot.json",
    "model/config/config.json.in",
    "model/.pre-commit-config.yaml",
)

# Model file extensions and filenames scanned by K-63 (`counts_model.py`).
MODEL_CITATION_SUFFIXES = (".sail", ".json", ".in", ".cpp", ".hpp", ".c", ".h",
                           ".cmake")
MODEL_CITATION_NAMES = ("CMakeLists.txt",)


def is_model_citation_path(rel: str) -> bool:
    """Return True if `rel` is a tracked `model/` file (outside `model/dependencies/`) scanned by `K-63`."""
    return (rel.startswith(UNREAD_PREFIX)
            and not rel.startswith(UNREAD_PREFIX + "dependencies/")
            and (rel.endswith(MODEL_CITATION_SUFFIXES)
                 or rel.rsplit("/", 1)[-1] in MODEL_CITATION_NAMES))

GITLINK_MODE = "160000"


class Corpus:
    """The tracked Markdown of the repository, and what a link may name in it."""

    def __init__(self, root: Path, docs: list[Document], gitlinks: dict[str, str],
                 tracked: list[str], indexed: set[str] | None = None) -> None:
        self.root = root
        self.docs = docs
        self.by_name = {d.name: d for d in docs}
        # Submodule path -> indexed commit. Link checks use path membership;
        # pin checks use the commit without another Git invocation.
        self.gitlinks = gitlinks
        # Tracked files present in the working tree, including non-Markdown and
        # model files. Each whole-tree check defines its own exclusions.
        self.tracked = tracked
        # Stage-zero files, including working-tree deletions. Rules asking whether
        # the index carries a file need its membership, not a subprocess reading
        # its entire blob. Conflicted entries have no stage zero; gitlinks point at
        # commits rather than blobs. Neither can supply an indexed file.
        self.indexed = frozenset(tracked if indexed is None else indexed)

        # Semantic citations use each file's own heading and bookmark targets.
        for d in docs:
            for _, heading in d.headings:
                d.targets.add(slug(heading))

        # Every bookmark: where it is declared, how often, and the prose §n it sits in.
        # A bookmark may be cited more than once from the prose only by taking a -2/-3
        # suffix; the base id it belongs to is what the trace check resolves against.
        # Ids are per-file, so two documents may carry the same one; within a file a
        # repeat is a fault, and the link check needs the whole set, not the prose's.
        self.anchor_count: dict[str, int] = {}   # prose bookmark -> how often declared
        self.anchor_sec: dict[str, str | None] = {}  # prose bookmark -> the §n it sits in
        self.buried: list[str] = []              # anchors code displays instead of declaring
        self.declared_twice: list[str] = []
        for d in docs:
            self._read_anchors(d)

    def _read_anchors(self, d: Document) -> None:
        prose = d.name == PROSE
        head_offsets: list[int] = []
        head_secs: list[str] = []
        if prose:
            for i, m in d.unfenced("## ", PROSE_SECTION_RE):
                head_offsets.append(d.starts[i])
                head_secs.append(m.group(1))

        here: dict[str, int] = {}
        for m in ANCHOR_RE.finditer(d.raw):
            i = d.line_of(m.start())
            ident = m.group(1)
            if d.fenced[i]:
                self.buried.append(
                    f"{d.name}:{i + 1} buries #{ident} in a code block, "
                    "where it is text and not a bookmark"
                )
                continue
            d.targets.add(ident)
            here[ident] = here.get(ident, 0) + 1
            if here[ident] == 2:
                self.declared_twice.append(
                    f"{d.name} declares #{ident} more than once; "
                    "a link to it resolves to whichever comes first"
                )
            if prose:
                self.anchor_count[ident] = self.anchor_count.get(ident, 0) + 1
                if ident not in self.anchor_sec:
                    j = bisect.bisect_right(head_offsets, m.start()) - 1
                    self.anchor_sec[ident] = head_secs[j] if j >= 0 else None

    def get(self, name: str) -> Document | None:
        return self.by_name.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self.by_name


def _git_environment(root: Path) -> dict[str, str] | None:
    """Return `os.environ` overlaid with [`proofenv.git_env`](proofenv.py#git_env) for linked worktrees in WSL, or `None`."""
    overlay = proofenv.git_env(root)
    return {**os.environ, **overlay} if overlay else None


def _git(root: Path, *args: str) -> list[str]:
    """Run `git *args` with NUL-delimited output (`-z`) and return the split entries."""
    proc = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, check=False,
        env=_git_environment(root),
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return proc.stdout.decode("utf-8").split("\0")[:-1]


def staged_bytes(root: Path, path: str) -> bytes | None:
    """Return the stage-0 index blob bytes for `path`, or `None` if not staged."""
    proc = subprocess.run(["git", "cat-file", "blob", f":{path}"],
                          cwd=root, capture_output=True, check=False,
                          env=_git_environment(root))
    return proc.stdout if proc.returncode == 0 else None


def staged_blobs(root: Path, paths: Iterable[str]) -> dict[str, bytes | None]:
    """Read a batch of stage-zero blobs in one process, without retaining a cache.

    Git's `cat-file --batch -Z` frames headers with NUL and contents by byte size.
    Splitting the entire output on a delimiter would corrupt binary blobs. Explicit
    stage zero also prevents an absent/conflicted path from resolving through HEAD.
    Older Git versions without `-Z`, or another batch failure, retain the individual
    reader's per-path decisions rather than turning every requested file into a miss.
    """
    requests = {path: f":0:{path}".encode() for path in paths}
    if not requests:
        return {}
    if any(b"\0" in request for request in requests.values()):
        raise ValueError("an indexed path cannot contain NUL")
    proc = subprocess.run(
        ["git", "cat-file", "--batch", "-Z"], cwd=root,
        input=b"".join(request + b"\0" for request in requests.values()),
        capture_output=True, check=False, env=_git_environment(root))
    if proc.returncode != 0:
        return {path: staged_bytes(root, path) for path in requests}
    return _batch_blobs(proc.stdout, requests)


def _batch_blobs(output: bytes, requests: dict[str, bytes]) -> dict[str, bytes | None]:
    """Decode Git's byte-framed response, refusing incomplete or extra records."""
    found: dict[str, bytes | None] = {}
    cursor = 0
    for path, request in requests.items():
        end = output.find(b"\0", cursor)
        if end < 0:
            raise RuntimeError(f"git cat-file returned no complete header for {path}")
        header = output[cursor:end]
        cursor = end + 1
        if header == request + b" missing" or header.endswith(b" submodule"):
            found[path] = None
            continue
        fields = header.split()
        if len(fields) != 3 or not fields[2].isdigit():
            raise RuntimeError(f"git cat-file returned an invalid header for {path}")
        end = cursor + int(fields[2])
        if output[end:end + 1] != b"\0":
            raise RuntimeError(f"git cat-file returned incomplete contents for {path}")
        found[path] = output[cursor:end] if fields[1] == b"blob" else None
        cursor = end + 1
    if cursor != len(output):
        raise RuntimeError("git cat-file returned unrequested contents")
    return found


def find_root(start: Path | None = None) -> Path:
    """Find the repository root above `start` (or this module's path) containing `.git` and `docs/requirements-register.md`."""
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".git").exists() and (candidate / "docs" / "requirements-register.md").exists():
            return candidate
    raise SystemExit(
        f"no repository root above '{here}': expected a .git and docs/requirements-register.md"
    )


@dataclass(frozen=True)
class Index:
    """The index's file membership and pins, without reading the working tree.

    `files` includes deleted and unmerged paths, once each in Git's order.
    `indexed` is narrower: only stage-zero files can supply an indexed blob.
    """

    files: tuple[str, ...]
    gitlinks: dict[str, str]
    indexed: frozenset[str]


def read_index(root: Path) -> Index:
    """Read file membership, stage-zero membership and gitlinks in one Git call."""
    files: list[str] = []
    gitlinks: dict[str, str] = {}
    indexed: set[str] = set()
    seen: set[str] = set()
    for entry in _git(root, "ls-files", "--stage", "--full-name", "-z"):
        staged, _, path = entry.partition("\t")
        mode, oid, stage = staged.split()
        if stage == "0" and mode != GITLINK_MODE:
            indexed.add(path)
        if path in seen:
            continue
        seen.add(path)
        if mode == GITLINK_MODE:
            gitlinks[path] = oid
        else:
            files.append(path)
    return Index(tuple(files), gitlinks, frozenset(indexed))


def load(root: Path) -> Corpus:
    """Load the tracked Markdown corpus (excluding `model/`), tracked file paths, and gitlink pins.

    Tracked files deleted from the working tree remain in `indexed` but are omitted
    from `tracked` and `docs` so each consuming rule reports their absence cleanly.
    """
    # Read file membership, gitlink paths and pinned commits in one listing.
    # Gitlinks resolve for link and pin checks even when submodules are uninitialized.
    index = read_index(root)
    names: list[str] = []
    tracked: list[str] = []
    for path in index.files:
        if not (root / path).is_file():
            continue
        tracked.append(path)
        if path.endswith(".md") and not path.startswith(UNREAD_PREFIX):
            names.append(path)

    docs = []
    for n in sorted(names):
        try:
            docs.append(_read(root / n, n))
        except FileNotFoundError:
            # Treat deletion after listing like any missing file: let each rule
            # report its absence rather than aborting the corpus load.
            continue
    return Corpus(root, docs, index.gitlinks, sorted(tracked), set(index.indexed))
