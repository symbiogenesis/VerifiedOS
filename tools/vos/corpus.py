# SPDX-License-Identifier: Apache-2.0
"""Every document in the repository, read once.

A fenced block is shown as text, so an anchor inside one is not a bookmark, a link
inside one is not a link, and an id inside one names nothing: the register's own
entry template cites `#r-ss-nnn`, which must not read as a dangling trace. Every
check that reads whole documents reads them through here, so the rule is stated
once and every check inherits it.

Each document keeps its raw text beside its lines, plus a table of line-start
offsets. The checks scan the raw text once with one pattern and resolve a hit back
to its line by binary search, rather than walking every line once per check; the
reports are the same, arrived at in one pass instead of many.
"""

import bisect
import re
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

# The line-anchored patterns here are matched against one line rather than scanned
# across the whole text with `(?m)^`. The two decide the same lines, but a multiline
# scan costs the engine an attempt at every line start of a three-megabyte corpus,
# where a line walk rejects on a substring test first and enters the engine only for
# the few lines that survive it: measured over this corpus each such scan fell from
# about twenty milliseconds to under three, and a run performs several of them.
#
# [^\S\r\n] is \s minus the line breaks, which on a single line is the same class.
FENCE_RE = re.compile(r"[^\S\r\n]*```")
ANCHOR_RE = re.compile(r'<a id="([^"]+)"')
HEADING_RE = re.compile(r"#{1,6}[ \t]+([^\r\n]+)")
NUMBERED_RE = re.compile(r"^§?(\d+(?:\.\d+)*)[.:) ]")

_TAG_RE = re.compile(r"<[^>]+>")
_PUNCT_RE = re.compile(r"[^\w\s-]")
_SPACE_RE = re.compile(r"\s+")


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
        """Every line-anchored match a fence does not display, as its line and its match.

        The line's index comes back with it because the walk already knows it: where a
        caller wants the raw offset instead it is `starts[index]`, and the binary search
        `line_of` would otherwise perform is never paid for at all.

        `lead` is a substring the pattern cannot match without, tested before the
        pattern is. It is redundant with the pattern rather than a further condition, so
        it can only skip lines the pattern would reject anyway; what it buys is that
        nearly every line is rejected by a C substring scan instead of by entering the
        regex engine.
        """
        for i, line in enumerate(self.lines):
            if lead in line and not self.fenced[i] and (m := pattern.match(line)):
                yield i, m


def _read(path: Path, name: str) -> Document:
    try:
        raw = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        # named here because the bare exception names only offsets: the load runs
        # before any rule reports, so the one thing a stopped run can still do is say
        # which tracked document is not the UTF-8 the corpus requires
        raise RuntimeError(f"{name} is not valid UTF-8: {exc}") from exc

    # one split hands back every segment with its terminator's length implied, so
    # the offsets accumulate without touching the text again
    parts = raw.split("\n")
    starts: list[int] = []
    offset = 0
    for part in parts:
        starts.append(offset)
        offset += len(part) + 1

    # a file ending in a newline has no final empty line, which is what every
    # line-oriented reader means by its line count
    body = parts[:-1] if parts and parts[-1] == "" else parts
    lines = [p.removesuffix("\r") for p in body]

    # every fence marker toggles, so the odd-even pairs span the displayed lines,
    # markers included; an unclosed fence displays to the end of the file. The markers
    # are the lines the fence pattern matches, so a walk names them by index and no
    # offset has to be resolved back to a line.
    last = len(lines) - 1
    marks = [i for i, line in enumerate(lines)
             if "```" in line and FENCE_RE.match(line)]

    fenced = [False] * len(lines)
    for k in range(0, len(marks), 2):
        a = marks[k]
        b = min(marks[k + 1] if k + 1 < len(marks) else last, last)
        # a fence is a span of lines, so marking one is a span write
        fenced[a:b + 1] = [True] * (b - a + 1)

    return Document(name=name, raw=raw, lines=lines, starts=starts, fenced=fenced)


PROSE = "docs/spec.md"
PROSE_SECTION_RE = re.compile(r"## (\d+)\.")

# the tree the corpus excludes by name, stated once so that the selftest's sandbox and
# the exclusion itself cannot stop agreeing
UNREAD_PREFIX = "model/"

# The carve-out inside that exclusion, and the reason it has to live beside it. A few
# model files carry a fact a document restates, and a rule holding the two together has
# to read both; the selftest's sandbox stands the rest of the tree up as empty files to
# save copying what no rule opens, so a path a rule reads and this list omits passes on
# the host and fails every sandbox's baseline, which reports as a red tree rather than
# as a bad mutant. One list, read by the sandbox and by the parses alike.
MODEL_FACTS = (
    "model/model/core/cap_format.sail",
    "model/model/core/timing.sail",
    "model/model/unit_tests/test_cheri_insts.sail",
    "model/config/verifiedos.json",
    "model/config/verifiedos-v.json",
    "model/config/config.json.in",
)

# The second window into the same tree, declared separately because it is narrow for
# no reason at all and the list above is narrow for a good one.
#
# `MODEL_FACTS` is a *value* window: a rule reading a number out of the model should
# name the file it reads, and adding one is a decision somebody makes on purpose. The
# citation check is not that kind of rule. What it holds is hygiene over a construct
# that occurs wherever the curated model argues from the register, which is most of the
# tree, so a window sized for the other purpose leaves its claim mostly untrue: aimed
# at the files above it reaches under a quarter of the citations the model makes, and
# the sentence *the model's own citations reach no rule* stays true of the rest. The
# citations are counted on every run and the live figure is K-63's `ok` line's to state,
# never this comment's.
#
# The reach is by kind rather than by name for the same reason: a list of seventy-odd
# files would be a membership nobody maintains, and the day a new Sail file cites a
# requirement is the day it should be checked rather than the day somebody remembers.
# The cost is the selftest's sandbox copying these instead of standing them up empty,
# which is a few hundred files and about a megabyte.
#
# The kinds are not only Sail. The emulator harness and the test build files argue from
# the register too, and those arguments are this repository's rather than upstream's:
# upstream has no reason to cite an id in this numbering, so a requirement named in a
# `.cpp` under `c_emulator/` is a curation decision exactly as one in a `.sail` is. A
# window that admitted only Sail left nine of them unread, which is the same defect one
# scale down.
MODEL_CITATION_SUFFIXES = (".sail", ".json", ".in", ".cpp", ".hpp", ".c", ".h",
                           ".cmake")
MODEL_CITATION_NAMES = ("CMakeLists.txt",)


def is_model_citation_path(rel: str) -> bool:
    """Whether a tracked path is one the citation check reads.

    `dependencies/` is excluded because it is somebody else's code vendored whole: a
    requirement id appearing there would be a coincidence of digits rather than a
    citation, and holding an upstream to this repository's register is not a claim
    anyone should make. It carries none today, so the exclusion is a statement about
    what the window means rather than a filter doing work.
    """
    return (rel.startswith(UNREAD_PREFIX)
            and not rel.startswith(UNREAD_PREFIX + "dependencies/")
            and (rel.endswith(MODEL_CITATION_SUFFIXES)
                 or rel.rsplit("/", 1)[-1] in MODEL_CITATION_NAMES))

# an index entry's mode, which is what tells a submodule from a file
GITLINK_MODE = "160000"


class Corpus:
    """The tracked Markdown of the repository, and what a link may name in it."""

    def __init__(self, root: Path, docs: list[Document], gitlinks: set[str],
                 tracked: list[str]) -> None:
        self.root = root
        self.docs = docs
        self.by_name = {d.name: d for d in docs}
        self.gitlinks = gitlinks
        # Every tracked path that is a file rather than a gitlink, Markdown and not,
        # model/ and not. Only the marks group reads it, and it reads the whole tree
        # on purpose: its question is what kind each file is, so the exclusions the
        # document groups apply by construction are that group's to state and refuse.
        self.tracked = tracked

        # A fragment resolves to a bookmark or to a heading's slug, and Markdown makes
        # no distinction between them, so this is one set per file. The numbering is
        # shared across documents (§5.2 is the register's subsection and the profile's
        # CSR section), so the numbered headings are one set for the repository.
        self.numbered: set[str] = set()
        for d in docs:
            for _, m in d.unfenced("#", HEADING_RE):
                heading = m.group(1)
                d.targets.add(slug(heading))
                num = NUMBERED_RE.match(heading)
                if num:
                    self.numbered.add(num.group(1))

        # Every bookmark: where it is declared, how often, and the prose §n it sits in.
        # A bookmark may be cited more than once from the prose only by taking a -2/-3
        # suffix; the base id it belongs to is what the trace check resolves against.
        # Ids are per-file, so two documents may carry the same one; within a file a
        # repeat is a fault, and the link check needs the whole set, not the prose's.
        self.anchor_count: dict[str, int] = {}   # prose bookmark -> how often declared
        self.anchor_sec: dict[str, str | None] = {}  # prose bookmark -> the §n it sits in
        self.buried: list[str] = []              # anchors a fence displays instead of declaring
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
                    f"{d.name}:{i + 1} buries #{ident} in a fenced block, "
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


def _git(root: Path, *args: str) -> list[str]:
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=root, capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.splitlines()


def find_root(start: Path | None = None) -> Path:
    """The repository root, found from a path rather than from the caller's cwd.

    Every path the tools name is repository-relative, so a run from anywhere else
    would read a different tree and report on it confidently. Deriving the root from
    the tool's own location removes the question: there is no wrong directory to run
    from, which is one whole class of user error deleted rather than diagnosed.
    """
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".git").exists() and (candidate / "docs" / "requirements-register.md").exists():
            return candidate
    raise SystemExit(
        f"no repository root above '{here}': expected a .git and docs/requirements-register.md"
    )


def load(root: Path) -> Corpus:
    """Every tracked Markdown document, plus the gitlinks a link may point at.

    The corpus is what the repository tracks, which git already knows: `ls-files`
    skips ignored files and build output without this tool maintaining a list of
    them, and a submodule is one gitlink entry rather than its contents, so upstream
    prose stays out by construction rather than by a .gitmodules parse. What git
    cannot see is that model/ is that same upstream prose vendored rather than
    pinned, the curated tree M0.6a stands up from the sail-riscv blobs: tracked here,
    answering to its own repository's house style, and so the one exclusion left to
    state.

    The index lists what is tracked, which is not quite what is readable: a document
    deleted from the working tree is still an index entry until the deletion is
    staged. Such a file is dropped from the corpus rather than read, because that is
    what makes its absence *reportable*. Every rule that names it then fails on its
    own terms, the view check finding the artifact gone and the link check finding
    the pointers at it dead, which is a finding a person can act on; reading it
    instead would abort the run on an IO error before any rule decided anything.
    """
    # One listing answers both questions the corpus asks of the index, because both are
    # answered by an entry's mode. A link at a submodule points at something the
    # repository carries as a gitlink rather than as a directory, and whether that
    # gitlink is checked out is the reader's business and not the pointer's. So a
    # submodule path resolves whether or not its contents are on disk: a shallow clone,
    # or a checkout that skipped submodules, is not a repository whose cross-references
    # have gone stale.
    names: list[str] = []
    gitlinks: set[str] = set()
    tracked: list[str] = []
    seen: set[str] = set()
    for entry in _git(root, "ls-files", "--stage", "--full-name"):
        staged, _, path = entry.partition("\t")     # `<mode> <object> <stage>\t<path>`
        if staged.startswith(GITLINK_MODE):
            gitlinks.add(path)
            continue
        # a merge conflict lists an unmerged path once per stage, and one path read
        # as two documents would report every anchor it declares as declared twice
        if path in seen:
            continue
        seen.add(path)
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
            # deleted between the listing and the read, by a peer session sharing the
            # checkout: dropped exactly as a deletion that landed before the listing
            # is, so its absence stays reportable on every rule's own terms
            continue
    return Corpus(root, docs, gitlinks, sorted(tracked))
