#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Hold the checker against the one property its own meta group cannot decide: that
each rule it carries actually fires.

The checker closes a great deal on itself. The meta group holds the rule registry and
the code in agreement in both directions, and the floors group (K-46 through K-48)
catches the reading that has emptied. What none of them reaches is the rule that still
reads a populated set and has stopped deciding anything about it: a pattern that
narrowed without emptying, an anchor that now matches a neighbouring construct, a
branch made unreachable by an edit elsewhere. tools/check-rules.md names that residue
in "What a passing run does not decide" and leaves it to a person. This closes the
part of it a machine can have: for each rule, one document mutated so that the rule
must report, and a run that says whether it did.

The method is mutation testing and its guarantee is exactly the usual one. A rule that
survives its mutant is dead surface, reported here. A rule that kills its mutant is
live, which is not the same as correct: whether it decides the *right* property is
still the registry's claim and a person's to audit. Nothing here re-states what a rule
means. It states only that the rule bites.

Every case runs against a sandbox built from the working tree, so the checker under
test is the one on disk rather than the one at HEAD, and no case can touch the real
repository. The sandbox is a git repository because the checker reads its corpus from
the index. Cases run in parallel across one sandbox per worker, and a sandbox is
hardlinks into one pristine template rather than a copy of it, which together are
what make a whole pass half a minute rather than a coffee break; a case only ever
sees its own sandbox, and a write breaks its link before it lands, so neither the
parallelism nor the sharing changes a verdict.

    tools/check-selftest.py                 # every case
    tools/check-selftest.py --rule K-23     # one rule, while iterating on it
    tools/check-selftest.py --keep          # leave the sandboxes for inspection

Exit 0 when every case kills its mutant and every registered rule is accounted for,
1 otherwise.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from queue import Queue
from typing import cast

# The tools import `vos` without being installed, so each puts its own directory on
# the path first. Every import below this line is deliberately not at the top.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vos import corpus as corpus_mod
from vos.coread import LEDGER
from vos.corpus import MODEL_FACTS, UNREAD_PREFIX, is_model_citation_path
from vos.figures import words

CHECKER = "tools/check.py"
RULES = "tools/check-rules.md"

# the two characters the documents' own shapes are written in, named so that a case
# composing a pattern around one never has to spell it inside a regex
MID = "·"      # the bullet the register opens each property line with
SEC = "§"      # the section sign a trace and a cross-reference display


# =====================================================================================
# the sandbox, and the helpers a case edits it through
# =====================================================================================


class Sandbox:
    """One disposable view of the working tree, and the checker that runs against it.

    Its files are hardlinks into the pristine template beside it rather than copies,
    which buys two things at once: standing one up is a metadata pass over the tree,
    and the on-access virus scan a fresh copy of the corpus pays on its first read,
    several seconds of it per sandbox, is paid once for the template and shared,
    because a link is the same file object and carries the same verdict. The price is
    one invariant: nothing writes through a link in place. Every write here unlinks
    first, so the edit lands in a new file and the template keeps the original bytes.
    The checker's own --fix is the one writer these methods cannot reach, so `check`
    refuses fix=True unless the sandbox was stood up fix-safe, holding real copies of
    every file --fix could rewrite.
    """

    def __init__(self, path: Path, pristine: Path, fix_ok: bool = False) -> None:
        self.path = path
        self.pristine = pristine
        self.fix_ok = fix_ok
        self.touched: set[str] = set()

    def read(self, rel: str) -> str:
        with (self.path / rel).open(encoding="utf-8", newline="") as f:
            return f.read()

    def write(self, rel: str, text: str | None) -> bool:
        """Write, and say whether anything was written.

        A mutation that produced no change is a case that has stopped testing its rule,
        and it must be told apart from a rule that read a defect and said nothing: a
        null edit is refused rather than written, so a pattern that stopped matching
        cannot blank the document it was aimed at.
        """
        if text is None:
            return False
        if text == self.read(rel):
            return False
        self.touched.add(rel)
        target = self.path / rel
        # unlinked before written: the file is a hardlink, and a write through it in
        # place would edit the template under every other sandbox
        target.unlink()
        target.write_text(text, encoding="utf-8", newline="")
        return True

    def delete(self, rel: str) -> bool:
        """Delete, and say whether anything was deleted.

        A file already absent is the same drift a null edit is: the case has stopped
        seeding its rule, and that is reported as unseeded rather than raised as a
        worker's crash.
        """
        target = self.path / rel
        if not target.exists():
            return False
        self.touched.add(rel)
        target.unlink(missing_ok=True)
        return True

    def reset(self) -> None:
        """A case is undone rather than compensated for, and only where it wrote.

        Every edit is recorded as it is made, so undoing one is re-linking the
        pristine file over it: an unlink and a hardlink, whatever the size of the
        document the case rewrote. `git checkout -- .` would restore the same bytes,
        but it stats the whole tree on every case, which over sixty cases is most of
        a run spent re-checking a thousand files to undo an edit to one.
        """
        for rel in self.touched:
            source, target = self.pristine / rel, self.path / rel
            target.unlink(missing_ok=True)
            if source.exists():
                _link_or_copy(source, target)
        self.touched.clear()

    def check(self, fix: bool = False) -> tuple[int, list[str], list[str]]:
        """The checker's own verdict, as the rule ids it reported, so a case asserts
        against what the run decided rather than against its prose.

        A subprocess and not an in-process call: two cases mutate the checker's own
        source, and only a fresh interpreter reads the mutant rather than the module
        this process already imported.
        """
        if fix and not self.fix_ok:
            raise SystemExit("--fix rewrites documents in place, which writes through "
                             "this sandbox's hardlinks into the template; it may only "
                             "run on the repair sandbox, which holds real copies")
        argv = [sys.executable, str(self.path / CHECKER)] + (["--fix"] if fix else [])
        # a run is ~1 s, so an overrun this size is a hang (a mutant that sends a
        # pattern into catastrophic backtracking), and it must land as its case's
        # failure rather than as a run that never ends; errors='replace' for the same
        # containment, a mutant being allowed to make the checker's output undecodable
        timeout = 300
        try:
            proc = subprocess.run(argv, cwd=self.path, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace",
                                  timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            return 1, [f"FAIL: the checker run overran {timeout} s and was killed"], []
        out: list[str] = [*(proc.stdout or "").splitlines(),
                          *(proc.stderr or "").splitlines()]
        failed: list[str] = sorted({m.group(1) for line in out
                                    if (m := re.match(r"\s*FAIL (K-\d{2,3})", line))})
        return proc.returncode, out, failed


def remove_tree(path: Path) -> None:
    """Delete a sandbox, read-only files included.

    git marks its pack files read-only, and on Windows that is enough to make an
    ordinary recursive delete fail halfway through, leaving a sandbox nobody asked to
    keep and a run that cannot start next time.
    """
    def force(func: Callable[[str], object], target: str, _exc: BaseException) -> None:
        Path(target).chmod(stat.S_IWRITE)
        func(target)

    if path.exists():
        shutil.rmtree(path, onexc=force)


def _link_or_copy(src: str | Path, dst: str | Path) -> None:
    """A hardlink where the filesystem grants one, a copy where it does not, and the
    same contract either way: the destination is a fresh directory entry, so an
    unlink-first write never reaches the source."""
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def stand_up(template: Path, path: Path, fix_ok: bool = False) -> Sandbox:
    """One sandbox, as hardlinks into the template.

    Its .git is one pointer file naming the template's rather than a linked tree.
    Everything the checker asks git is `ls-files`, a read of the shared index, and a
    third of the template's files are the object store `git add` wrote beside it, so
    the pointer spares every sandbox linking, and later unlinking, a store nothing
    reads. git resolves the pointer's worktree to the directory holding it, which is
    what keeps each sandbox's checker reading its own mutated tree against the one
    shared index.

    A fix-safe sandbox is the exception the repair path needs: the checker's --fix
    rewrites documents in place through whatever name it opens, which a hardlink
    would relay straight into the template under every running case. What --fix can
    name is the document corpus, so everything outside model/ is a real copy there,
    a boundary that contains that corpus with room to spare while keeping the
    copying, and the scan a fresh copy costs on first read, to the hundred-odd files
    outside that tree.
    """
    remove_tree(path)
    for dirpath, dirnames, filenames in template.walk():
        rel = dirpath.relative_to(template)
        target = path / rel
        target.mkdir(parents=True, exist_ok=True)
        names = filenames
        if not rel.parts:
            dirnames.remove(".git")
            names = [name for name in names if name != _MANIFEST]
        linked = not fix_ok or rel.parts[:1] == ("model",)
        for name in names:
            if linked:
                _link_or_copy(dirpath / name, target / name)
            else:
                shutil.copy2(dirpath / name, target / name)
    (path / ".git").write_text(f"gitdir: {template / '.git'}\n", encoding="utf-8")
    return Sandbox(path, template, fix_ok=fix_ok)


def _across[T, R](work: Callable[[T], R], items: Iterable[T], jobs: int) -> list[R]:
    """One call per item, run at once, answered in the order the items were given.

    Everything handed to this is a subprocess or a tree of a thousand small files, so a
    worker spends nearly all of its time inside a syscall with the interpreter lock
    released: the run is I/O the machine can overlap rather than Python it cannot.
    """
    work_list = list(items)
    if len(work_list) < 2:
        return [work(item) for item in work_list]
    with ThreadPoolExecutor(max_workers=min(jobs, len(work_list))) as pool:
        return list(pool.map(work, work_list))


def edit_entry(text: str, ident: str, edit: Callable[[str], str | None]) -> str | None:
    """A register entry is its normative line plus the property lines under it, ending
    where the next entry begins. Several cases need surgery inside exactly one entry
    and must not reach the next, so the span is computed once here."""
    start = text.find(f"**{ident}** ")
    if start < 0:
        return None
    end = text.find("\n**R-", start + 1)
    if end < 0:
        end = len(text)
    new = edit(text[start:end])
    return None if new is None else text[:start] + new + text[end:]


def replace_once(text: str, find: str, repl: str, start: int = 0) -> str | None:
    """Replace one literal, at or after an offset. The offset is how a case skips the
    register's entry template, which is fenced prose carrying every property line's
    shape and is not an entry at all."""
    i = text.find(find, start)
    return None if i < 0 else text[:i] + repl + text[i + len(find):]


def replace_span(text: str, m: re.Match[str], new: str) -> str:
    return text[:m.start()] + new + text[m.end():]


# =====================================================================================
# the template cache: the previous run's template, reused file by file
# =====================================================================================
#
# Building the template is copying nine hundred files under the on-access scanner,
# which costs more than every case that then runs against it. Almost none of those
# files changed since the last run, so the newest published template is kept between
# runs and each unchanged file is hardlinked forward instead of copied. What decides
# "unchanged" is deliberately conservative, because a stale-but-believed-current
# template would run every mutant against the wrong tree and nothing above the
# selftest exists to catch that: a file is carried only when its path, size, mtime and
# treatment all match the manifest the previous build wrote, and a file whose mtime
# falls within the grace of that manifest's own write is re-copied however it
# compares, which is the racily-clean rule git's index keeps and it closes the race
# of a file rewritten between being measured and being copied. Every other doubt
# answers "copy from the repository": a manifest that does not parse, a snapshot
# whose file cannot be linked, a treatment the current declarations changed.
#
# Snapshots are immutable and numbered, and a run publishes by renaming its own
# template into the cache after every case is done, so a run that dies publishes
# nothing and concurrent runs race only over the next number. A run touches the
# snapshot it links out of as it picks it, so a concurrent publisher's sweep spares
# any tree a build could still be reading, and an index carry the sweep interrupts
# anyway answers the way every other doubt does, by rebuilding from scratch. The
# manifest lives inside the snapshot it describes and is written after `git add`,
# so no sandbox index ever carries it.

_MANIFEST = ".selftest-manifest.json"
_GRACE_NS = 2_000_000_000

# how each listed path was placed: a byte copy of the repository's file, or an empty
# stand-in whose content owes nothing to the source
type Placement = tuple[int, int, str]     # size, mtime_ns, "copy" | "empty"


def _cache_root(repo: Path) -> Path:
    """Where this checkout's templates survive between runs, keyed by the checkout's
    own path so that worktrees of one repository never share a cache."""
    digest = hashlib.sha256(str(repo).casefold().encode()).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"verifiedos-selftest-cache-{digest}"


def _newest_snapshot(cache: Path) -> tuple[Path, int, dict[str, list[int | str]]] | None:
    """The highest-numbered snapshot carrying a readable manifest, as its path, the
    manifest's own write time, and what it says each file was placed from."""
    if not cache.is_dir():
        return None
    for path in sorted((p for p in cache.iterdir() if re.fullmatch(r"t\d+", p.name)),
                       key=lambda p: int(p.name[1:]), reverse=True):
        try:
            data = json.loads((path / _MANIFEST).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        built, files = data.get("built_ns"), data.get("files")
        if isinstance(built, int) and isinstance(files, dict):
            return path, built, cast("dict[str, list[int | str]]", files)
    return None


def _link_tree(src: Path, dst: Path) -> None:
    for dirpath, _dirnames, filenames in src.walk():
        target = dst / dirpath.relative_to(src)
        target.mkdir(parents=True, exist_ok=True)
        for name in filenames:
            _link_or_copy(dirpath / name, target / name)


def _publish(template: Path, cache: Path) -> None:
    """The run's template becomes the next run's source, atomically and last.

    A rename rather than a copy, after every case is done: a sandbox's hardlinks do
    not care what the shared file's directory entry is called, and a run that died
    before reaching here has published nothing, leaving the previous snapshot
    standing. Losing the race for a number is retried at the next one, and any other
    refusal is abandoned rather than fought: the cache is a saving, never a claim.
    Snapshots below the newest are removed once their last pick is comfortably old:
    the age test reads the mtime `build_template` bumps as it picks, a snapshot is
    read only during the build that picked it, and ten minutes bounds that build by
    two orders of magnitude.
    """
    if not template.is_dir():
        return
    cache.mkdir(parents=True, exist_ok=True)
    taken = max((int(p.name[1:]) for p in cache.iterdir()
                 if re.fullmatch(r"t\d+", p.name)), default=0)
    published = 0
    for n in range(taken + 1, taken + 20):
        try:
            template.rename(cache / f"t{n}")
        except FileExistsError:
            continue
        except OSError:
            return
        published = n
        break
    if not published:
        return
    for p in cache.iterdir():
        if not (re.fullmatch(r"t\d+", p.name) and int(p.name[1:]) < published):
            continue
        try:
            if time.time() - p.stat().st_mtime > 600:
                remove_tree(p)
        except OSError:
            pass                        # a concurrent run is sweeping the same snapshot


def build_template(repo: Path, into: Path, jobs: int) -> tuple[int, int]:
    """The working tree, not HEAD and not the index: the checker under test is the one
    being edited, and so is every document it reads. Untracked files are copied for the
    same reason. A document or a tool written but not yet staged is exactly the thing
    most likely to be wrong, and a sandbox that omitted it would fail on the links
    pointing at it rather than test it. Ignored files stay out, `.gitignore` deciding
    that the same way it does everywhere else.

    One directory is stood up rather than copied. `model/` is most of the repository's
    tracked files and the checker reads almost none of them: it excludes the whole
    directory from its *document* corpus by name, as vendored upstream prose answering
    to another repository's house style. What it does read of the rest is whether those
    paths *exist*, because a link into the curated tree must resolve. So each is created
    empty, and the saving is most of the cost of the template every sandbox then links
    against, which is otherwise 95% files no rule opens.

    There are two exceptions and they are named rather than guessed at, in
    `vos.corpus` beside the exclusion they carve out of. `MODEL_FACTS` is a handful of
    model files carrying a fact a document restates, the welded block size being the
    one that forced it, and a rule holding the two together has to read both.
    `is_model_citation_path` is the wider one: the requirement citations the model
    makes occur in most of its Sail, so the rule holding them against the register
    reaches by kind rather than by name and this copies that kind instead of touching
    it. Either way a rule reading a model path neither admits would pass on the host
    and fail every sandbox's baseline, which reports as a red tree rather than as a bad
    mutant, so the declarations are the one place that can go wrong and they go wrong
    loudly.

    A submodule's contents are not copied, because the checker excludes upstream prose
    from its corpus, but the directory itself is stood up: a link at a submodule is
    resolved against the filesystem here, where the sandbox's own index carries no
    gitlink to resolve it against instead. The placeholder is what makes the directory
    survive the clean between cases, git having no way to track an empty one.

    What comes back is how many files the template holds and how many of those were
    carried from the previous run's snapshot under the cache's rules, stated above it.
    """
    remove_tree(into)
    into.mkdir(parents=True)

    listed: list[str] = []
    for extra in ([], ["--others", "--exclude-standard"]):
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "--full-name", *extra],
            cwd=repo, capture_output=True, text=True, encoding="utf-8", check=False)
        if proc.returncode != 0:
            raise SystemExit("git ls-files failed in the repository")
        listed += proc.stdout.splitlines()

    # the directories first and once each, so that the writes below share nothing and go
    # in together: a thousand small files is the case `_across` is for
    for parent in {(into / rel).parent for rel in listed}:
        parent.mkdir(parents=True, exist_ok=True)

    held = _newest_snapshot(_cache_root(repo))
    snapshot, built_ns, old_files = held or (None, 0, {})
    if snapshot is not None:
        # the pick is marked on the snapshot itself, which is what `_publish`'s sweep
        # ages: a tree some build is still linking out of always reads as just used
        try:
            os.utime(snapshot)
        except OSError:
            snapshot, old_files = None, {}    # gone under the pick: the repository decides
    placed: dict[str, Placement] = {}

    def place(rel: str) -> tuple[int, int]:
        src, dst = repo / rel, into / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            (dst / ".selftest-submodule").write_text(
                f"a stand-in for the {rel} submodule, so links at it resolve\n",
                encoding="utf-8")
            return 0, 0
        try:
            measured = src.stat()
        except OSError:
            return 0, 0        # listed but gone: a deletion not yet staged, dropped here
        empty = (rel.startswith(UNREAD_PREFIX) and rel not in MODEL_FACTS
                 and not is_model_citation_path(rel))
        kind = "empty" if empty else "copy"
        placed[rel] = (measured.st_size, measured.st_mtime_ns, kind)
        if empty:
            # a stand-in owes nothing to the source's bytes, so writing it fresh is
            # the same act carrying it forward would be
            dst.touch()
            return 1, 0
        if (snapshot is not None
                and old_files.get(rel) == [measured.st_size, measured.st_mtime_ns, kind]
                and measured.st_mtime_ns + _GRACE_NS < built_ns):
            try:
                os.link(snapshot / rel, dst)
            except OSError:
                pass                    # the snapshot moved: the repository decides
            else:
                return 1, 1
        shutil.copy2(src, dst)
        return 1, 0

    counts = _across(place, listed, jobs)
    copied = sum(one for one, _ in counts)
    carried = sum(one for _, one in counts)

    # The index, and no commit on top of it. `ls-files --stage` is the whole of what the
    # checker asks git and `add` is what answers it, so a commit would be a third of a
    # second per run spent writing a HEAD that nothing here ever reads: a case is undone
    # from the pristine tree beside it rather than out of git. When every copied file
    # was carried and the manifests agree entry for entry, the snapshot's index already
    # describes this exact tree, empty stand-ins included, and is carried the same way;
    # any file this run copied afresh means the index is rebuilt from scratch.
    manifest = {rel: [size, mtime, kind] for rel, (size, mtime, kind) in placed.items()}
    carried_index = False
    if (snapshot is not None and manifest == old_files
            and carried == sum(1 for _, _, kind in placed.values() if kind == "copy")):
        # a snapshot swept mid-carry surfaces as a link that fails or a walk that
        # yields nothing, and either answers like every other doubt: rebuild
        try:
            _link_tree(snapshot / ".git", into / ".git")
            carried_index = (into / ".git" / "index").is_file()
        except OSError:
            carried_index = False
    if not carried_index:
        remove_tree(into / ".git")
        for args in (["-c", "init.defaultBranch=main", "init", "-q"], ["add", "-A"]):
            proc = subprocess.run(["git", *args], cwd=into, capture_output=True, check=False)
            if proc.returncode != 0:
                raise SystemExit(f"could not build the sandbox index: git {args[0]}")

    # written after the index is built, so no `git add` ever sees it
    (into / _MANIFEST).write_text(
        json.dumps({"built_ns": time.time_ns(), "files": manifest}),
        encoding="utf-8")
    return copied, carried


# =====================================================================================
# the cases: one mutant per rule, each stating the defect it seeds
# =====================================================================================
#
# A case is either a literal substitution or, where the defect is structural, a
# function over the sandbox. Several mutants trip more than one rule, which is expected
# and not a weakness: an id renamed in one artifact is genuinely wrong in every
# artifact that cites it. A case passes when its own rule is among those that reported,
# so collateral findings neither hide a miss nor manufacture a hit.

REGISTER = "docs/requirements-register.md"
SPEC = "docs/spec.md"
CRITIQUE = "docs/critique.md"
CROWN = "docs/crown-jewels.md"
MATRIX = "docs/coverage-matrix.md"
PROFILE = "docs/isa-profile.md"
PERF = "docs/performance-estimates.md"
PLAN = "docs/implementation-checklist.md"
BINDINGS = "docs/field-bindings.md"
ABSENCE = "docs/absence-contract.md"
CORPUS_DOC = "docs/differential-corpus.md"
CONTRACT = "docs/freeze-measurement-contract.md"
GEOMETRY = "docs/block-geometry-constraint.md"
THIRD_PARTY = "THIRD-PARTY.md"


# One seeded defect, applied to a sandbox, answering whether it changed anything. A
# mutation that writes nothing is a case that has stopped testing its rule, which is
# why the answer is a bool rather than nothing at all.
type Mutation = Callable[[Sandbox], bool]

# One row of `CASES`: the rule the mutant must provoke, what the mutation is in words,
# and the mutation itself.
type Case = tuple[str, str, Mutation]


def _literal(rel: str, find: str, repl: str) -> Mutation:
    def apply(box: Sandbox) -> bool:
        return box.write(rel, replace_once(box.read(rel), find, repl))
    return apply


def _entry(ident: str, edit: Callable[[str], str | None]) -> Mutation:
    def apply(box: Sandbox) -> bool:
        return box.write(REGISTER, edit_entry(box.read(REGISTER), ident, edit))
    return apply


def _first_match(rel: str, pattern: str, rewrite: Callable[[re.Match[str]], str],
                 flags: int = re.MULTILINE) -> Mutation:
    """Rewrite the first match of a pattern, or refuse if it no longer matches."""
    def apply(box: Sandbox) -> bool:
        text = box.read(rel)
        m = re.search(pattern, text, flags)
        if not m:
            return False
        return box.write(rel, replace_span(text, m, rewrite(m)))
    return apply


def _renumber(rel: str, pattern: str, group: int, value: str) -> Mutation:
    """Overwrite one numbered group of the first match, leaving the rest of the line."""
    def apply(box: Sandbox) -> bool:
        text = box.read(rel)
        m = re.search(pattern, text, re.MULTILINE)
        if not m:
            return False
        return box.write(rel, text[:m.start(group)] + value + text[m.end(group):])
    return apply


def _seed_paragraph(sentence: str) -> Mutation:
    """Drop a sentence into the gap before a heading, where the checker reads it as
    ordinary prose."""
    return _literal(CRITIQUE, "\n## ", f"\n{sentence}\n\n## ")


def _strip_requirements(rel: str, pattern: str,
                        replacement: str = "the register") -> Mutation:
    return _first_match(rel, pattern,
                        lambda m: re.sub(r"R-\d\d-\d+[a-z]?", replacement, m.group()))


def _k14(box: Sandbox) -> bool:
    # the id is read out of the register rather than named here, so the case keeps
    # working when the subsection is re-populated
    register = box.read(REGISTER)
    sub = re.search(r"(?ms)^### 15\.14 .*?(?=^### )", register)
    if not sub:
        return False
    view = box.read(ABSENCE)
    for ident in re.findall(r"(?m)^\*\*(R-\d\d-\d+[a-z]?)\*\* ", sub.group()):
        if ident in view:
            # swapped for another live id, so only the membership is wrong
            return box.write(ABSENCE, view.replace(ident, "R-01-001"))
    return False


def _k26(box: Sandbox) -> bool:
    # the form has to be one the tool actually counts, so it is read out of the
    # inventory rather than invented
    n = len(re.findall(r"(?m)^\| \d+ \|", box.read(CROWN)))
    return box.write(CRITIQUE, replace_once(
        box.read(CRITIQUE), "\n## ",
        f"\nThere are {words(n)} crown-jewel specifications in view.\n\n## "))


def _k29(box: Sandbox) -> bool:
    text = box.read(PROFILE)
    start = text.find("### 5.1 ")
    if start < 0:
        return False
    m = re.search(r"(?m)^\| `[^\r\n]*R-\d\d-\d+[^\r\n]*", text[start:])
    if not m:
        return False
    row = re.sub(r"R-\d\d-\d+[a-z]?", "the profile", m.group())
    at = start + m.start()
    return box.write(PROFILE, text[:at] + row + text[at + len(m.group()):])


def _k30(box: Sandbox) -> bool:
    text = box.read(PERF)
    m = re.search(r"(?m)^\|[^\r\n]*In-order issue[^\r\n]*", text)
    if not m:
        return False
    cells = m.group().split("|")
    return box.write(PERF, replace_span(
        text, m, m.group().replace(cells[4], " roughly a third off ")))


def _k43(box: Sandbox) -> bool:
    text = box.read(BINDINGS)
    m = re.search(r"(?m)^\| `\w+` \| `(?P<c>[^`]+)`", text)
    if not m:
        return False
    return box.write(BINDINGS,
                     text[:m.start("c")] + "nothing_at_all" + text[m.end("c"):])


def _k46(box: Sandbox) -> bool:
    """Comment out one registered claim, so a computed quantity is held by nothing."""
    rel = "tools/vos/checks/counts.py"
    text = box.read(rel)
    m = re.search(r'(?m)^(\s*)\("README\.md", "absences",', text)
    if not m:
        return False
    return box.write(rel, text[:m.start()] + m.group(1) + "# (" + text[m.end():])


def _k49(box: Sandbox) -> bool:
    return box.delete(ABSENCE)


def _k61(box: Sandbox) -> bool:
    """Move one recorded prose digest, so a pair the ledger calls read no longer is.

    The ledger's own bytes are moved rather than a document's. A digest is a function
    of the prose, so a case naming one as a literal would rot the next time that
    paragraph was edited; anchoring on the row's shape instead keeps the case true
    whatever the documents hold, and exercises the comparison rather than only the
    membership half a renamed row would reach.
    """
    text = box.read(LEDGER)
    m = re.search(r'^(  "R-01-001": \[")([0-9a-f]{12})', text, re.MULTILINE)
    if not m:
        return False
    return box.write(LEDGER, text[:m.start(2)] + "0" * 12 + text[m.end(2):])


def _keep_own_id(entry_line: str) -> str:
    head = re.match(r"^\*\*R-\d\d-\d+[a-z]?\*\* ", entry_line)
    if head is None:
        # The caller picked this line out of the register as an entry, so a line that
        # does not open with an id means the mutation no longer applies. Said here
        # rather than as an AttributeError on `None`, which reads as a defect in this
        # tool rather than as the drift it actually is.
        raise SystemExit(f"the entry to mutate does not open with a requirement id: "
                         f"{entry_line[:60]!r}")
    return head.group() + re.sub(r"R-\d\d-\d+[a-z]?", "R-01-001",
                                 entry_line[len(head.group()):])


CASES: list[Case] = [
    ("K-00", "a registered rule with its registry row retitled out of the table",
     _literal(RULES, "| K-40 | glyphs", "| K-xx | glyphs")),

    ("K-01", "a trace's derived bookmark renamed in the prose",
     _literal(SPEC, '<a id="r-01-001">', '<a id="moved-away">')),

    ("K-02", "a trace writing out the citation its own id derives",
     _entry("R-01-001", lambda b: b.replace(
         f"{MID} Trace: CJ-T", f"{MID} Trace: [{SEC}1](spec.md#r-01-001)"))),

    ("K-03", "one bookmark declared twice in the same document",
     _literal(SPEC, '<a id="r-01-002"></a>', '<a id="r-01-002"></a><a id="r-01-002"></a>')),

    ("K-04", "a bookmark buried in a fenced block, where it is text",
     lambda box: box.write(CRITIQUE, box.read(CRITIQUE)
                           + '\n```\n<a id="seeded-in-a-fence"></a>\n```\n')),

    ("K-05", "a requirement whose trace line stops being one",
     _entry("R-01-001", lambda b: b.replace(f"{MID} Trace:", f"{MID} Traced:"))),

    ("K-06", "a requirement left with nothing to decide it",
     _entry("R-01-001", lambda b: b.replace(f"{MID} Accept:", f"{MID} Accepts:"))),

    ("K-07", "a criterion stated below the trace that must follow it",
     _entry("R-01-001", lambda b: re.sub(
         f"({MID} Trace: [^\r\n]*)",
         f"\\1\n{MID} Accept: a criterion stated after the trace", b))),

    ("K-08", "a prose bookmark naming a requirement the register never declared",
     _literal(SPEC, '<a id="r-01-001">', '<a id="r-01-901">')),

    ("K-09", "a written-out trace displaying a section its bookmark does not sit in",
     _entry("R-01-001", lambda b: b.replace(
         f"{MID} Trace: CJ-T",
         f"{MID} Trace: [{SEC}9](spec.md#r-01-001); and the crown jewel"))),

    ("K-10", "one requirement id declared by two entries",
     _literal(REGISTER, "**R-01-002** ", "**R-01-001** ")),

    ("K-11", "a requirement id that names nothing",
     _seed_paragraph("The R-99-999 obligation applies here.")),

    ("K-12", "a link pointing at a file the repository does not carry",
     _literal("README.md", "](docs/", "](docs/not-a-")),

    ("K-13", "a section number no heading carries",
     _seed_paragraph(f"This is settled at {SEC}99.7.")),

    ("K-14", "a bearing requirement its view stops carrying", _k14),

    ("K-15", "a matrix cell moved off its own pair, leaving a gap and a duplicate",
     _literal(MATRIX, "| `B-01` | `P-1` |", "| `B-02` | `P-1` |")),

    ("K-16", "a matrix cell resting on no requirement",
     _strip_requirements(MATRIX, r"(?m)^\| `B-\d\d` \| `P-\d` \|[^\r\n]*")),

    ("K-17", "a CJ- target the inventory does not account for",
     _literal(REGISTER, "| `CJ-SAIL` |", "| `CJ-SAILX` |")),

    ("K-18", "an inventory row no requirement confers the status on",
     _strip_requirements(CROWN, r"(?m)^\| \d+ \|[^\r\n]*", "R-01-001")),

    ("K-19", "the crown-jewel status asserted in a criterion and on no entry line",
     _entry("R-01-001", lambda b: b.replace(
         f"{MID} Accept:",
         f"{MID} Accept: the crown-jewel spec it names is authored, and"))),

    ("K-20", "a conferred refusal no seam collects",
     _entry("R-01-001", lambda b: b.replace(
         f"{MID} Trace:",
         f"{MID} Fail-closed: the seeded refusal stops the unit, and the stop costs a "
         f"restart\n{MID} Trace:"))),

    # the entry's own id is left alone and every id it cites is swapped, so the seam
    # composes refusals no requirement confers while still being the entry it was
    ("K-21", "a seam composing a refusal no requirement confers",
     _first_match(REGISTER,
                  r"(?m)^\*\*R-\d\d-\d+[a-z]?\*\* [^\r\n]*Fail-closed seam \*\*[^\r\n]*",
                  lambda m: _keep_own_id(m.group()))),

    ("K-22", "a freshness conferral that stops naming the enumeration collecting it",
     _first_match(REGISTER, f"(?m)^{MID} RoT-fresh:[^\r\n]*R-10-013[^\r\n]*",
                  lambda m: re.sub(r"R-10-013[a-z]?", "the enumeration", m.group()))),

    ("K-23", "an entry speaking the vocabulary of refusal and standing in no column",
     _entry("R-01-001", lambda b: re.sub(
         r"(?m)^(\*\*R-01-001\*\*[^\r\n]*)",
         r"\1 The unit refuses rather than degrades.", b))),

    ("K-24", "an asserted count the artifact no longer gives",
     _renumber(CROWN, r"\d+(?= coarse targets)", 0, "99")),

    ("K-25", "an inventory status spelled outside the three declared classes",
     _first_match(
         CROWN,
         r"(?m)^\| \d+ \|[^\r\n]*\| (not authored|partial[^|]*|[^|]*authored[^|]*) \|[^\r\n]*",
         lambda m: re.sub(r"\| [^|]+ \|(\s*)$", r"| in progress |\1", m.group()))),

    ("K-26", "a counted figure restated where no claim holds it", _k26),

    ("K-27", "a Coverage row naming a section the register does not carry",
     _literal(REGISTER, f"| **{SEC}5 ", f"| **{SEC}55 ")),

    ("K-28", "a Coverage row whose count the register does not give",
     _renumber(REGISTER,
               rf"(?m)^\| \*\*{SEC}\d+ [^|]*\| \*\*extracted\*\* \| \*\*(\d+)\*\* \|",
               1, "999")),

    ("K-29", "a CSR row resting on no requirement", _k29),

    ("K-30", "an estimate figure stated outside the column shape", _k30),

    ("K-31", "a dominant term whose big-table row is retitled out from under it",
     _literal(PERF, "In-order issue, no speculation/OoO",
              "In-order issue, no speculation or OoO")),

    ("K-32", "a compounded product the rows beneath it do not give",
     _literal(PERF, "| Better | " + chr(0x2212) + "42% |",
              "| Better | " + chr(0x2212) + "11% |")),

    ("K-33", "a credit the band and the product do not support",
     _literal(PERF, "| 3 points conservative |", "| 9 points conservative |")),

    ("K-34", "a checklist item whose estimate cell the document cannot read",
     _first_match(PLAN,
                  rf"(?m)^\* \[x\] \*\*[^*]+\*\* {MID} [\d.,]+ h actual {MID} [\d.]+%",
                  lambda m: re.sub(rf" {MID} [\d.,]+ h actual {MID} [\d.]+%",
                                   " (about half a day)", m.group()))),

    ("K-35", "an open midpoint that is not the mean of its own range",
     _renumber(PLAN, rf"(?m)^\* \[ \] \*\*[^*]+\*\* {MID} ([\d.,]+)(?= h, range )",
               1, "999")),

    ("K-36", "a subtotal that no longer sums the items beneath it",
     _renumber(PLAN, r"(?m)^\*\*[^*]+ subtotal:\*\* ([\d.,]+)(?= h )", 1, "999")),

    ("K-37", "a restated grand total the items do not give",
     _renumber(PLAN, r"(?m)^\* Total estimate: ([\d.,]+)(?= h midpoint)", 1, "999")),

    ("K-38", "a table row of the wrong width",
     _literal(MATRIX, "| `B-01` | `P-1` |", "| seeded | `B-01` | `P-1` |")),

    ("K-39", "a run of table rows carrying no header rule",
     _seed_paragraph("| a stray row | pasted on its own |")),

    ("K-40", "an em-dash, which the house style forbids",
     _seed_paragraph("A clause " + chr(0x2014) + " and its aside.")),

    ("K-41", "UTF-8 read as a single-byte encoding",
     _seed_paragraph("The caf" + chr(0x00C3) + chr(0x00A9) + " problem.")),

    ("K-42", "a bindings row disagreeing with the apex record",
     _literal(BINDINGS, "| `spatial_safety` |", "| `spatial_safetyx` |")),

    ("K-43", "a consumer cell that no longer restates the statement", _k43),

    ("K-44", "an instantiation cell in no readable form",
     _literal(BINDINGS, "| none yet |", "| soon |")),

    ("K-45", "a disposition left standing over a requirement that was retired",
     _literal(REGISTER, "**R-03-003** ", "**R-03-903** ")),

    ("K-46", "a computed quantity with no claim to notice it going to zero", _k46),

    ("K-47", "an enumeration whose reading has moved off the heading it read",
     _literal(PROFILE, "### 5.1 ", "### 5.9 ")),

    ("K-48", "a view drawing its members from a subsection the register no longer carries",
     _literal("tools/vos/checks/views.py", '"15.14"', '"15.94"')),

    ("K-49", "a view the register obliges and the repository does not carry", _k49),

    ("K-50", "a corpus member the manifest lists and the document does not describe",
     _literal(CORPUS_DOC, "(../corpus/cap-trap.s)", "(../corpus/cap-trap-moved.s)")),

    ("K-51", "a corpus member whose program no longer assembles",
     _literal("corpus/cap-trap.s", "cmove   c8, c1", "cmove   c8, c1, c2")),

    # The mark is stripped rather than mangled, because an absent mark is the failure
    # this rule exists for: a new file lands unmarked and reads exactly like a marked
    # one. The target is the checker's own module, so the case cannot be satisfied by
    # a file the repository might stop carrying.
    ("K-52", "a markable file whose license mark has gone",
     _literal("tools/vos/checks/marks.py", "# SPDX-License-Identifier: Apache-2.0\n", "")),

    # A new file of an unknown kind cannot be seeded, because the corpus is the git
    # index and an untracked file is not in it. Withdrawing a kind's ruling puts an
    # existing file into exactly the state a new kind would arrive in, which is the
    # state the rule exists to report.
    ("K-53", "a tracked file whose kind the tool no longer rules on",
     _literal("tools/vos/checks/marks.py",
              '    ".json": "JSON admits no comment, so a mark would make the file '
              'unparseable",\n', "")),

    # The owner is moved rather than one of the eleven figures, because a figure edited
    # alone is the easy half: what the rule is for is the granule changing under all of
    # them at once, which is the edit nobody would think to propagate by hand. The
    # repair lane seeds K-54 a defect of its own instead of this one; REPAIRABLE says
    # why a moved owner cannot ride it.
    ("K-54", "the tag granule moved out from under every figure derived from it",
     _renumber(REGISTER, r"one validity tag per \*\*(\d+)-bit\*\* granule", 1, "128")),

    # The booking half rather than the capacity half: an owner that stops stating its
    # figure is the ordinary floor, where an artifact that stops booking the bank count
    # as open is the reading whose moving changes what the rule should be doing.
    ("K-55", "an artifact that no longer books the per-class bank count as open",
     _literal(REGISTER, "the per-class bank count is in R-15-014a's frozen parameter set",
              "the per-class bank count is frozen")),

    # Dropped from one list and not added to the other, which is what a region class
    # being reworded actually looks like: it is on neither side and every remaining
    # term still checks out.
    ("K-56", "a region class the two latency-class lists no longer place",
     _first_match(REGISTER, r"(?m)^· Accept: the first class carries[^\r\n]*",
                  lambda m: m.group().replace("recovery workspaces, ", ""))),

    # The charge gains a term and the placement is left alone, which is the direction
    # this arm exists for and the one the other case cannot reach: every term already
    # in the lists still checks out, the two lists still partition, and what is wrong
    # is that a byte somebody now pays for is on neither class. A ring is chosen
    # because the nearest existing term is a substring of it, so a rule matching
    # loosely would place the new term by accident and pass.
    ("K-56", "a physical byte the composition is charged and neither class carries",
     _literal(REGISTER, "quarantine entries, interpreter object arenas",
              "quarantine entries, telemetry rings, interpreter object arenas")),

    # One of the four transcriptions is moved and the other three are left, which is
    # the shape a real drift takes: an exponent edited in the composition that the
    # model's own assertion would catch only once something executed.
    ("K-57", "a composition that writes a welded block size the model does not",
     _literal("model/config/verifiedos.json",
              '"cache_block_size_exp": 6', '"cache_block_size_exp": 5')),

    # The entry's ceiling rather than one of the transcriptions, because it is the one
    # normative statement of the bound and the one site whose moving leaves every other
    # still agreeing with every other. A halved ceiling also leaves the declared block
    # inside the set it admits, so what has to catch it is the arithmetic against the
    # granule and the destination width and not the membership test beside it.
    ("K-57", "a stated block ceiling the destination register's width does not give",
     _literal(REGISTER, "the block at most **512 bytes**",
              "the block at most **256 bytes**")),

    # The bank grant is moved in the composition and left in the contract, which is the
    # direction a real edit takes: the emulator needs a number, so the configuration is
    # where somebody changes one, and the contract is the copy that goes stale.
    ("K-58", "a bank grant the contract and the composition no longer agree on",
     _literal("model/config/verifiedos.json", '"banks": 4096', '"banks": 2048')),

    # The citing document is edited rather than the cited one, because that is the
    # cheaper half of the same defect and the harder one to see: the name here is the
    # entry's own former title, so the sentence reads exactly as it did before the
    # other document merged that entry into a larger one.
    ("K-59", "an entry named in another document under a title it no longer carries",
     _literal(SPEC, "the second-die entry in [Evaluated",
              "the bonded-die-stacking entry in [Evaluated")),

    # The composition is moved and the three prose tables are left, which is the
    # direction a real edit takes for the reason K-58's does: a vector length is
    # something somebody changes where the model reads it, and the documents saying
    # what a class is are the copies that go stale. The V row is the one mutated
    # because its exponent is the only one written once in the file, the C class's
    # being the geometry `extensions.V` is built at and so written twice on purpose.
    ("K-60", "a class whose vector geometry the composition and the documents no "
             "longer agree on",
     _literal("model/config/verifiedos.json", '"vlen_exp": 12', '"vlen_exp": 13')),

    ("K-61", "a pair the ledger records as read at contents it no longer holds", _k61),

    # The register's own heading is renumbered rather than a section added to the prose.
    # A new prose heading would also cut short the span above it and so report K-61,
    # where a case is for one rule biting; and the rename is the defect in its purest
    # form, because renumbering moves no count at all: `len(reg.per_section)` is
    # eighteen before and after, so the figure the counts group holds stays right while
    # the extraction it is supposed to stand for has gone.
    ("K-62", "a normative section of the prose that the register no longer extracts",
     _literal(REGISTER, "## §18", "## §20")),

    # A digit is changed inside a citation the model argues from, which is the defect
    # in the form it actually arrives in: nobody invents a requirement id, they
    # mistype one or carry one across from an upstream that numbered things its own
    # way. The site is the timing table's own governing citation, so the mutation is
    # a sentence that still reads as a citation and names nothing.
    ("K-63", "a model file citing a requirement the register does not declare",
     _literal("model/model/core/timing.sail", "R-15-095", "R-15-995")),

    # The composed hart of the V-class configuration is moved back to the C-class one,
    # which is the *quiet* half of the rule rather than the loud half. A key that
    # drifted makes the second file a different machine and shows up as a diff nobody
    # can miss; a declared divergence that stopped diverging leaves two files that
    # validate, run, and agree, with the second one no longer a second core at all. The
    # platform key is the first `"hartid": 6` in the file, ahead of the roster entry
    # naming the same identity, which is why the literal is unambiguous.
    ("K-65", "a second shipped configuration that composes the same core as the first",
     _literal("model/config/verifiedos-v.json", '"hartid": 6', '"hartid": 0')),

    # The *profile* is edited rather than the model, which is the direction this defect
    # actually arrives from: an amendment excludes a form and the model goes on
    # implementing it, which is exactly what R-15-039b did. Mutating the model instead
    # would seed the mirror defect and would have to pick a file two other lanes are
    # curating; the exclusion row is permanent, so the anchor cannot rot.
    #
    # The *marker* is what the substitution moves, because that is the half of the rule
    # a break would leave silent. The fragment path was seeded here as
    # "`vle<eew>ff.v`" -> "`cincoffset`", a name spelled by an assembly clause and
    # carried by the encoder table at once; it is written down rather than kept because
    # one rule gets one case, and the membership path is the one whose reading is new.
    # `AMO` is the substituted constructor because the model decodes it in the clause
    # next to the deleted one, so the case fires on a name that is certainly there and
    # will not rot into an unseeded pass.
    ("K-66", "a form the profile excludes and the model still decodes",
     _literal(PROFILE, "Sail: `AMOCAS`", "Sail: `AMO`")),

    # One install line is moved and the checker-table rows are left, which is the shape
    # the defect takes: a pin bumped where it is enforced or where it is read first,
    # with the other copies going stale behind it.
    ("K-67", "a README pin drifted from the version typecheck.py fixes",
     _literal("tools/README.md", "uv tool install ty==0.0.74",
              "uv tool install ty==0.0.73")),

    # One site of a fact two pairs state is reworded while its siblings stand, which
    # is the drift K-61 cannot see: the edited pair blesses on its own two sides and
    # the other pair's copy stays green. K-61 fires on the edited entry too, which is
    # expected collateral; the case passes only on K-68's own report.
    ("K-68", "a co-stated fact one of its sites no longer states",
     _entry("R-14-007", lambda entry: entry.replace(
         "capabilities beyond pure compute", "capabilities beyond pure computation"))),

    # An owned enumeration's lead-in moves with the list untouched: the reader
    # returns zero, and the guard must report the moved owner rather than resolve
    # the claims, whose --fix would rewrite every restating count-word to "zero"
    # across three documents and leave the next run green.
    ("K-24", "an owned enumeration whose lead-in moved out of the reader's reach",
     _literal(REGISTER, "obligations are exactly:", "obligations are precisely:")),

    # A restated figure drifts from the entry that fixes it: the kernel budget's spec
    # restatement moves while R-07-001 stands, the drift K-69's --fix rewrites back
    # from the owner.
    ("K-69", "a restated owned figure drifted from the entry that fixes it",
     _literal(SPEC, "target ≤10k lines", "target ≤12k lines")),

    # The marker is stripped from one §1 row and the row is otherwise left alone, which
    # is the state the real defect leaves behind: a delta item the register enumerates
    # and the instrument accounts for nowhere. The row keeps its width, its governing
    # citation and its decision, so no table, view or citation rule reads the edit and
    # K-70 is the one rule that can. It seeds no `FD-`, `FM-` or `G-` count, those being
    # restated in a document this case may not repair.
    ("K-70", "a delta item of the closed freeze delta that its instrument does not "
             "account for",
     _literal(CONTRACT, "| (v) the capability indexed",
              "| the capability indexed")),

    # The second reach of K-60: a free-prose VLEN token names a geometry no composed
    # class carries. The first spec token the seed happens to hit may sit in the
    # class table itself, in which case the table half fires instead; either half's
    # report is K-60's own.
    ("K-60", "a VLEN token naming a geometry no composed class carries",
     _literal(SPEC, "VLEN=4096", "VLEN=2048")),

    # The manifest is bumped and the document's §4 heading is left, which is the shape
    # the defect takes: the record grammar advances where an executor is checked
    # against it, and the prose describing the grammar stands still. The seed is an
    # increment of whatever the manifest declares rather than a literal, so the day
    # the schema legitimately advances is not the day this case stops applying.
    ("K-71", "a manifest declaring a commit-trace schema the document does not state",
     _first_match("corpus/manifest.json", r'"trace_schema": (\d+)',
                  lambda m: f'"trace_schema": {int(m.group(1)) + 1}')),

    # The ground rather than the membership, because the ground is the half that
    # expires in silence: the seed moves one word onto *cannot express it*, which
    # the encoder contradicts by building it from the reading beside it. That is
    # the shape the real defect takes, a row standing on a ground that stopped
    # being true the day a table row landed, and the member goes on writing the
    # word because nothing else reads a `.word` to notice.
    ("K-72", "a hand-written corpus word standing on a ground the encoder contradicts",
     _literal(CORPUS_DOC, "| the word is what the reader must see | `csrrw",
              "| the encoder cannot express it | `csrrw")),

    # The state and not the citation, which is K-22's half and stays intact: the seeded
    # line goes on naming the entry that collects it and stops naming a state that entry
    # carries, which is the member admitted without the budget sentence being reopened.
    # Read from the register rather than spelled here, so the case survives a reworded
    # state, and both directions fire on it at once, the conferral standing outside the
    # enumeration and the state it left standing under no conferral.
    ("K-73", "a freshness conferral naming a state the enumeration does not carry",
     _first_match(REGISTER, f"(?m)^{MID} RoT-fresh: (.+?) \\(R-10-013\\)",
                  lambda m: m.group().replace(m.group(1), "a state of its own"))),
    # The §17 citation is dropped from a residual cell and the mode is left standing,
    # which is the state the real defect leaves behind: a cell reporting that §17 books
    # its remainder, over requirements that discharge the pair instead. The cell keeps
    # two citations, so it still rests on a requirement and K-16 reads it as sound; the
    # ids it keeps resolve, so the names group reads it as sound; and its pair is
    # untouched, so K-15 never looks. K-74 is the one rule that can.
    ("K-74", "a residual cell whose citation of the section booking it has gone",
     _literal(MATRIX, "R-08-006, R-15-208, R-17-037", "R-08-006, R-15-208")),

    # One of the two settings rather than one of the five sentences, because the pair of
    # settings is where the figure is hardest to see moving: `py314` and `3.14` are one
    # floor in two dialects, so a bump taken in one of them looks like an edit to a
    # different quantity, and the prose that restates the floor goes on agreeing with
    # the half that did not move.
    ("K-75", "a checker settings file at an interpreter floor the other does not fix",
     _literal("tools/ruff.toml", 'target-version = "py314"',
              'target-version = "py313"')),

    # The configuration is moved rather than the record, because that is the direction
    # no reader of one file can see: the record goes on naming the parameter that takes
    # the predictor and the build it names has stopped taking it, which is a claim that
    # a structure is absent standing over an elaboration that instantiates it. Moving
    # the record instead would be the easy half and would read as an ordinary edit.
    ("K-76", "a synthesis parameter the provenance record binds set to another value",
     _literal("rtl/vos_c_class_config_pkg.sv", "BHTEntries: unsigned'(0),",
              "BHTEntries: unsigned'(1),")),

    # A one-letter respelling of a licence file's name, inside the backticks that make
    # the cell a path rather than a link. That is the whole point of the case: the row
    # still renders, the table is still the width its header declares, no id and no
    # count moves, and K-12 cannot see it because there is no link here to follow. The
    # component goes on being listed as redistributed here while the terms it is
    # redistributed under are named at a file the index does not carry.
    ("K-80", "a component's licence text named at a path the repository does not carry",
     _literal(THIRD_PARTY, "`model/dependencies/elfio/LICENSE.txt`",
              "`model/dependencies/elfio/LICENCE.txt`")),
]

# A rule with no case is not a defect, but it must be a decision.
UNSEEDABLE: dict[str, str] = {}


def _case_mutation(rule: str) -> Mutation:
    """A rule's own case mutant, reused as its repair seed."""
    for ident, _, apply in CASES:
        if ident == rule:
            return apply
    raise SystemExit(f"no case to reuse as {rule}'s repair seed")


# Every rule with a --fix branch: the substring its rewrite's `fixed:` line must carry,
# and the defect the repair lane seeds. The repair path is never exercised by a
# green tree, so a branch missing here ships untested unless something breaks it on
# purpose. Six seeds are the rules' own case mutants, each an arithmetic figure whose
# repair writes the pristine bytes back. Two rules cannot ride their own case. K-54's
# moves the granule owner, and repairing from a moved owner rewrites every derived
# figure to the new granule and dirties co-read pairs no --fix may bless, so the
# after-check could never pass. K-57's two both seed a site that is *not* repaired, one
# under a `-text` tree and one the register's own normative statement, so neither would
# reach a `fixed:` line. Each takes a seed here instead, moving one derived figure in
# the exact document bytes a case would anchor on, and the repair restores the tree it
# found.
REPAIRABLE: dict[str, tuple[str, Mutation]] = {
    "K-24": ("cj-targets", _case_mutation("K-24")),
    "K-28": (f"Coverage {SEC}", _case_mutation("K-28")),
    "K-32": ("product:", _case_mutation("K-32")),
    "K-36": (" subtotal:", _case_mutation("K-36")),
    "K-37": ("the total estimate", _case_mutation("K-37")),
    "K-54": ("the tag plane's", _literal(
        REGISTER, "granule is 15.6 MB per GB of data",
        "granule is 99.9 MB per GB of data")),
    "K-57": ("the block-size ceiling", _literal(
        GEOMETRY, "that is a ceiling of **512 bytes**",
        "that is a ceiling of **256 bytes**")),
    "K-69": ("kernel-line-budget", _case_mutation("K-69")),
}


# =====================================================================================
# run
# =====================================================================================


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed each checker rule a defect it must report.")
    parser.add_argument("--rule", help="run one rule's case only")
    # Eight, measured rather than assumed: a worker is a whole checker subprocess with
    # a git child under it, so extra workers past eight pay more in contention than
    # their extra sandboxes save even below the core count. Over full passes on a
    # twelve-core machine, eight workers ran 24.9 s where twelve ran 26.7 s and
    # sixteen 29.7 s.
    parser.add_argument("--jobs", type=int, default=min(8, os.process_cpu_count() or 2),
                        help="how many sandboxes run cases at once")
    parser.add_argument("--sandbox", type=Path, default=None,
                        help="where the sandboxes are built "
                             "(default: a private directory for this run)")
    parser.add_argument("--keep", action="store_true",
                        help="leave the sandboxes on disk for inspection")
    args = parser.parse_args(argv)

    # A private directory per run rather than one path every run reuses. What survives
    # between runs is the template cache, carried file by file under its own rules, so
    # a shared estate would buy nothing that the cache does not already keep and would
    # cost correctness: two runs at once rebuild each other's tree underneath the cases
    # reading it, and neither verdict is about its mutant afterwards. The failure is also
    # not self-clearing on Windows, where the losing run's checker subprocesses outlive
    # their parent holding `template/.git` open, so every later run fails standing up
    # rather than in a case. Passing --sandbox names a directory instead, which is how a
    # kept run gets a path chosen in advance.
    sandbox = args.sandbox or Path(tempfile.mkdtemp(prefix="verifiedos-selftest-"))

    repo = corpus_mod.find_root()
    selected = [c for c in CASES if not args.rule or c[0] == args.rule]
    if args.rule and not selected:
        raise SystemExit(f"no case for rule '{args.rule}'")
    jobs = max(1, min(args.jobs, len(selected)))

    # One sandbox per worker, and one more the repair path keeps to itself so that its
    # five runs go beside the cases rather than after them. When no selected rule
    # carries a --fix branch the lane never runs, so the extra sandbox is stood up
    # cheap, as links, and joins the case queue instead of holding real copies for
    # nothing.
    repairable = any(rule in REPAIRABLE for rule, _, _ in selected)
    made: list[Sandbox] = []
    print(f"building {jobs + 1} sandbox(es) at {sandbox}")
    template = sandbox / "template"
    copied, carried = build_template(repo, template, jobs)
    print(f"placed {copied} file(s), {carried} carried from the previous run, "
          "indexed as the baseline")
    print()

    try:
        # The baseline needs one sandbox and nothing else, so only the first is stood
        # up before it: the rest land while the baseline runs, each joining the queue
        # as it does, and the case wave draws them out as they arrive.
        made.append(stand_up(template, sandbox / "w0"))
        boxes: Queue[Sandbox] = Queue()
        with ThreadPoolExecutor(max_workers=jobs) as setup:
            def later(i: int) -> Sandbox:
                box = stand_up(template, sandbox / f"w{i}", fix_ok=repairable and i == jobs)
                made.append(box)
                if not box.fix_ok:
                    boxes.put(box)
                return box

            standing = [setup.submit(later, i) for i in range(1, jobs + 1)]
            code = _run(selected, made[0], boxes, standing[-1], jobs)
            for future in standing:
                future.result()   # a sandbox that failed to stand up is loud, not lost
        return code
    finally:
        if args.keep:
            print(f"sandboxes kept at {sandbox}")
        else:
            # the template leaves for the cache before the estate is deleted, and the
            # estate is deleted the way it was built, the parent last
            _publish(template, _cache_root(repo))
            _across(remove_tree, [box.path for box in made], jobs + 1)
            remove_tree(sandbox)


def _run(selected: list[Case], first: Sandbox, boxes: Queue[Sandbox],
         repair_ready: Future[Sandbox], jobs: int) -> int:
    # Nothing below means anything against a sandbox that was already failing: a mutant
    # would be reported killed by whatever was broken before it was introduced.
    code, out, _ = first.check()
    if code != 0:
        print("FAIL: the unmutated sandbox does not pass, so no case can decide anything:")
        for line in out:
            if line.lstrip().startswith("FAIL"):
                print(f"  {line}")
        return 1
    print("ok: the unmutated sandbox passes, so every finding below is the mutant")
    print()
    boxes.put(first)

    def one(case: Case) -> tuple[str, str, str, str | None]:
        rule, what, apply = case
        box = boxes.get()
        try:
            if not apply(box):
                return rule, what, "unseeded", None
            code, _, failed = box.check()
            if rule in failed:
                return rule, what, "killed", None
            # a run that reported nothing and a run that died before reporting look the
            # same from the rule's side and are repaired differently, so the exit code
            # is stated
            how = (f"other rules fired: {', '.join(failed)}" if failed
                   else "the run was green" if code == 0
                   else f"the run exited {code} with no finding, so the checker did not "
                        "survive the mutant either")
            return rule, what, "survived", how
        finally:
            box.reset()
            boxes.put(box)

    # The repair path is five more whole runs of the checker and depends on nothing a
    # case does, so it goes in beside them on the sandbox held back for it, and reports
    # where it has always reported: after the cases. Under --rule it runs only when a
    # selected rule carries a --fix branch, because for any other rule it is most of
    # the iteration path's cost and proves nothing about the rule being iterated on.
    repairable = any(rule in REPAIRABLE for rule, _, _ in selected)
    with ThreadPoolExecutor(max_workers=jobs + 1) as pool:
        repairing = pool.submit(_repair_path, repair_ready) if repairable else None
        results = list(pool.map(one, selected))
        repair: list[str] = []
        repair_out = ["--- the repair path ---",
                      "  skipped: no selected rule carries a --fix branch"]
        if repairing is not None:
            repair, repair_out = repairing.result()

    survived, unseeded, ran = [], [], 0
    for rule, what, verdict, how in results:
        if verdict == "unseeded":
            # a mutation that would not apply is the sharper finding of the two: the
            # document it was written against has moved, so the case has stopped testing
            # anything and would report the rule live for as long as nobody looked
            unseeded.append(f"{rule}: the mutant will not apply; the document it seeds has moved")
            print(f"{rule:<6} UNSEEDED  {what}")
            continue
        ran += 1
        if verdict == "killed":
            print(f"{rule:<6} killed    {what}")
        else:
            survived.append(f"{rule}: the mutant survived; the rule read the defect and "
                            f"reported nothing ({how})")
            print(f"{rule:<6} SURVIVED  {what}")
    print()

    print("\n".join(repair_out))
    print()
    gaps = _registry_coverage(first)
    print()

    findings = len(survived) + len(unseeded) + len(repair) + len(gaps)
    if findings:
        for line in survived + unseeded:
            print(line)
        print(f"{findings} finding(s); {ran} of {len(selected)} case(s) ran.")
        return 1
    held = ("the repair path holds" if repairable
            else "the repair path had nothing to prove")
    print(f"every one of {ran} rule(s) killed its mutant, {held}, "
          "and the registry is covered.")
    return 0


def _copied_bytes(box: Sandbox) -> dict[str, bytes]:
    """Every real-copied file in the fix-safe sandbox, as its bytes.

    The walk skips `model/`, the one tree `stand_up` links there rather than copies,
    and any `.git/` directory; the sandbox's own `.git` is a pointer file, so its
    bytes ride along, written once at standup and never by --fix. The rest is the
    whole surface --fix can reach, so holding its bytes before and after a run turns
    "rewrote nothing" from a report into a measurement.
    """
    held: dict[str, bytes] = {}
    for dirpath, dirnames, filenames in box.path.walk():
        if dirpath == box.path:
            dirnames[:] = [d for d in dirnames if d not in (".git", "model")]
        if "__pycache__" in dirnames:
            # the interpreter's leavings from the checker runs themselves: ignored by
            # git, written on import, and no part of the surface --fix can reach
            dirnames.remove("__pycache__")
        for name in filenames:
            held[str((dirpath / name).relative_to(box.path))] = (dirpath / name).read_bytes()
    return held


def _bytes_moved(before: dict[str, bytes], after: dict[str, bytes]) -> list[str]:
    """The files two snapshots disagree on, appearances and losses included."""
    differing = {rel for rel in before.keys() & after.keys() if before[rel] != after[rel]}
    return sorted((before.keys() ^ after.keys()) | differing)


def _repair_path(ready: Future[Sandbox]) -> tuple[list[str], list[str]]:
    """--fix rewrites the asserted counts, the Coverage rows, the compounded products,
    the checklist's cells and totals, and the tag-plane figures from their artifacts,
    and on a repository that already agrees it rewrites nothing, so those branches ship
    untested unless something breaks them on purpose. One seed per rule in REPAIRABLE,
    all seven at once, each repair asserted by its own `fixed:` line, and the lane is
    bracketed by two fixpoint proofs: --fix on the pristine tree exits clean, rewrites
    nothing, and moves no byte; and once the seeded defects are repaired and the
    checker passes, a second --fix again rewrites nothing and moves no byte.

    Its problems and its report are handed back rather than printed, because this runs
    beside the cases and the report reads after them; its sandbox is the fix-safe one,
    waited for here because it is the last to stand up.
    """
    box = ready.result()
    box.reset()
    problems: list[str] = []

    # the tracked tree is itself required to stand at the --fix fixpoint, so this run
    # comes first, before any seed lands
    pristine = _copied_bytes(box)
    idle_code, idle_out, _ = box.check(fix=True)
    if idle_code != 0:
        problems.append("--fix on the pristine tree did not exit clean")
    problems += [f"--fix on the pristine tree rewrote: {line}"
                 for line in idle_out if line.startswith("fixed:")]
    problems += [f"--fix on the pristine tree moved bytes in {rel}"
                 for rel in _bytes_moved(pristine, _copied_bytes(box))]

    for rule, (_, seed) in REPAIRABLE.items():
        if not seed(box):
            problems.append(f"{rule}: its repair seed no longer applies; the document "
                            "it edits has moved")

    before_code, _, before_failed = box.check()
    if before_code == 0:
        problems.append(f"the {words(len(REPAIRABLE))} seeded figures did not fail the "
                        "checker, so the repair proves nothing")
    else:
        problems += [f"{rule}: its seeded figure did not fail its own rule"
                     for rule in REPAIRABLE if rule not in before_failed]

    _, fix_out, _ = box.check(fix=True)
    rewrites = [line for line in fix_out if line.startswith("fixed:")]
    for rule, (marker, _) in REPAIRABLE.items():
        if not any(marker in line for line in rewrites):
            problems.append(f"{rule}: no 'fixed:' line carries {marker!r}, so --fix "
                            "did not recognize its seeded figure")

    after_code, after_out, _ = box.check()
    if after_code != 0:
        problems.append("--fix left findings standing:")
        problems += [f"    {line}" for line in after_out
                     if line.lstrip().startswith("FAIL")]

    # fix-after-fix is a no-op: the repaired tree stands at the same fixpoint the
    # pristine one did
    repaired = _copied_bytes(box)
    again_code, again_out, _ = box.check(fix=True)
    if again_code != 0:
        problems.append("the second --fix did not exit clean")
    problems += [f"the second --fix rewrote again: {line}"
                 for line in again_out if line.startswith("fixed:")]
    problems += [f"the second --fix moved bytes in {rel}"
                 for rel in _bytes_moved(repaired, _copied_bytes(box))]
    box.reset()

    out = ["--- the repair path ---"]
    if problems:
        out += [f"  {line}" for line in problems]
    else:
        out.append(f"  ok: --fix on the pristine tree rewrote nothing and moved no "
                   f"byte, {words(len(REPAIRABLE))} seeded figures failed the checker, "
                   f"--fix rewrote {len(rewrites)} and the tree then passes, and a "
                   f"second --fix rewrote nothing and moved no byte")
    return problems, out


def _registry_coverage(box: Sandbox) -> list[str]:
    """The registry is the enumeration of the tool's reach; this is the enumeration of
    what is held about that reach, and the two are checked against each other for the
    same reason the meta group checks the registry against the code."""
    print("--- coverage of the registry ---")
    registered = re.findall(r"(?m)^\| (K-\d{2,3}) \|", box.read(RULES))
    covered = {rule for rule, _, _ in CASES}
    gaps = [f"{r} is registered, has no case here, and is not declared unseedable"
            for r in registered if r not in covered and r not in UNSEEDABLE]
    gaps += [f"{r} has a case here and no registry row"
             for r in sorted(covered) if r not in registered]
    if gaps:
        for line in gaps:
            print(f"  {line}")
    else:
        print(f"  ok: all {len(registered)} registered rules carry a case")
    return gaps


if __name__ == "__main__":
    sys.exit(main())
