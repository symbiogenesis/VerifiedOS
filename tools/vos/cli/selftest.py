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

What a verdict is, and the report and the exit code they imply, is
[vos/seeded.py](../seeded.py)'s and is shared with the generated loops; what is here
is the oracle, and it is the one part of a mutation run that cannot be shared. This
oracle's population is **authored** rather than walked out of a source, because its
subject is a registry where a rule and its mutant are two halves of one claim, and its
third verdict is `unseeded` rather than `stillborn`: an authored case can stop
applying to a document that moved under it, which is a finding, where a generated one
regenerates itself and can only fail to compile, which is not. The `CASES` table stays
here for two reasons that are not style. A rule is added by three edits and one of
them is a row of that list, so it belongs beside the run that reads it; and K-83 holds
that nothing in the landing loop names the quarantine, exempting this file by name so
that the two cases seeding that rule can spell the coupling they seed.

Every case runs against a sandbox built from the working tree, so the checker under
test is the one on disk rather than the one at HEAD, and no case can touch the real
repository. The sandbox is a git repository because the checker reads its corpus from
the index. Cases run in parallel across one sandbox per worker, and a sandbox is
hardlinks into one pristine template rather than a copy of it, which together are
what make a whole pass half a minute rather than a coffee break; a case only ever
sees its own sandbox, and a write breaks its link before it lands, so neither the
parallelism nor the sharing changes a verdict.

    tools/run.py selftest                 # every case
    tools/run.py selftest --rule K-23     # one rule, while iterating on it
    tools/run.py selftest --keep          # leave the sandboxes for inspection

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
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from typing import cast

from vos import corpus as corpus_mod
from vos import memplan, proofcites, proofheaders, proofs, sharding, timings
from vos.checks import Context, generated, headers
from vos.checks.ledger import ARTIFACT as PROOF_LEDGER
from vos.coread import LEDGER
from vos.corpus import GITLINK_MODE, MODEL_FACTS, UNREAD_PREFIX, is_model_citation_path
from vos.dialectgen import TABLE as DIALECT_TABLE
from vos.figures import words
from vos.memplan import ARTIFACT as MEMORY_PLAN
from vos.proofcites import DERIVED_BEGIN
from vos.register import REQ_ID_PATTERN, REQ_TOKEN_RE, read_artifacts, read_register
from vos.report import Reporter
from vos.sailbundle import BUNDLE
from vos.seeded import KILLED, SURVIVED, UNSEEDED, Verdict, summarize
from vos.sharding import Shard
from vos.socmap import ARTIFACT as SOC_MAP

CHECKER = "tools/check.py"
RULES = "tools/check-rules.md"
CHECK_TIMEOUT = 300
OVERRAN = f"FAIL: the checker run overran {CHECK_TIMEOUT} s and was killed"

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

    def check(self, fix: bool = False,
              through: str | None = None) -> tuple[int, list[str], list[str]]:
        """The checker's own verdict, as the rule ids it reported, so a case asserts
        against what the run decided rather than against its prose.

        A subprocess and not an in-process call: two cases mutate the checker's own
        source, and only a fresh interpreter reads the mutant rather than the module
        this process already imported. Import the checker in the settled interpreter:
        a mutated lockfile is input to audit, never an environment to install.
        `through` stops the run after the group that decides that rule.
        """
        if fix and not self.fix_ok:
            raise SystemExit("--fix rewrites documents in place, which writes through "
                             "this sandbox's hardlinks into the template; it may only "
                             "run on the repair sandbox, which holds real copies")
        argv = [sys.executable, "-c",
            "import sys; sys.path.insert(0, sys.argv.pop(1)); "
            "import check; raise SystemExit(check.main())",
            str((self.path / CHECKER).parent)] + (["--fix"] if fix else []) + (
            ["--through", through] if through else [])
        # a run is seconds, so an overrun of CHECK_TIMEOUT is a hang (a mutant that
        # sends a pattern into catastrophic backtracking), and it must land as its
        # case's failure rather than as a run that never ends; errors='replace' for the
        # same containment, a mutant being allowed to make the checker's output
        # undecodable
        try:
            proc = subprocess.run(argv, cwd=self.path, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace",
                                  timeout=CHECK_TIMEOUT, check=False)
        except subprocess.TimeoutExpired:
            return 1, [OVERRAN], []
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


def stand_up(template: Path, path: Path, fix_ok: bool = False, *, jobs: int = 1) -> Sandbox:
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

    Directory workers may overlap independent file placements while constructing
    the first sandbox. Callers already constructing several sandboxes concurrently
    retain one worker per sandbox, so the two levels do not multiply their pools.
    """
    remove_tree(path)
    entries: list[tuple[Path, Path, list[str], bool]] = []
    for dirpath, dirnames, filenames in template.walk():
        rel = dirpath.relative_to(template)
        target = path / rel
        target.mkdir(parents=True, exist_ok=True)
        names = filenames
        if not rel.parts:
            dirnames.remove(".git")
            names = [name for name in names if name != _MANIFEST]
        entries.append((dirpath, target, names,
                        not fix_ok or rel.parts[:1] == ("model",)))

    def place(entry: tuple[Path, Path, list[str], bool]) -> None:
        dirpath, target, names, linked = entry
        for name in names:
            if linked:
                _link_or_copy(dirpath / name, target / name)
            else:
                shutil.copy2(dirpath / name, target / name)

    _across(place, entries, jobs)
    (path / ".git").write_text(f"gitdir: {template / '.git'}\n", encoding="utf-8")
    return Sandbox(path, template, fix_ok=fix_ok)


# The file a submodule's directory is stood up around, so that the empty directory
# survives into every sandbox and a link at it resolves against the filesystem.
SUBMODULE_STAND_IN = ".selftest-submodule"


def stamp_gitlinks(into: Path, gitlinks: dict[str, str]) -> None:
    """Put the repository's gitlinks back into the sandbox's own index.

    A sandbox's index is `git add -A` over a tree in which every submodule is a
    directory holding one stand-in file, so what it records at `upstream/<name>` is
    that stand-in and no gitlink at all. That cost nothing while no rule read one.
    K-81 reads the commit each gitlink records, out of the index because that is
    where it is written whether or not the submodule was ever fetched, so a sandbox
    that dropped them would report every pin as owned by nothing and fail its
    baseline, which reports as a red tree rather than as a bad mutant.

    Run on every template, carried index or fresh one, because the two fail the same
    way and a carried index is the older of the two. git rewrites an index through a
    lock and a rename, so this never writes through the hardlink a carried one is.

    What the repository pins is asked of `vos.corpus`, which already splits the
    index's gitlinks out of one listing: a second parse of `ls-files --stage` here
    would be the two-copies-of-one-question defect the tools' own conventions refuse.
    """
    if not gitlinks:
        return
    # The stand-in leaves the index first, because a blob under `upstream/<name>` and
    # a gitlink at it cannot both be entries; and `--cacheinfo` is what states the
    # entry, taking the mode, the object and the path outright rather than asking
    # git to work them out from a working tree where the submodule is an empty
    # directory and not a repository.
    stand_ins = [f"{path}/{SUBMODULE_STAND_IN}" for path in sorted(gitlinks)]
    cacheinfo = [arg for path, oid in sorted(gitlinks.items())
                 for arg in ("--cacheinfo", f"{GITLINK_MODE},{oid},{path}")]
    for args in (["update-index", "--force-remove", "--", *stand_ins],
                 ["update-index", "--add", *cacheinfo]):
        proc = subprocess.run(["git", *args], cwd=into, capture_output=True,
                              text=True, encoding="utf-8", check=False)
        if proc.returncode != 0:
            raise SystemExit("could not put the sandbox index's gitlinks back: "
                             f"git {args[0]}: {proc.stderr.strip()}")


def _across[T, R](work: Callable[[T], R], items: Iterable[T], jobs: int) -> list[R]:
    """One call per item, run at once, answered in the order the items were given.

    Everything handed to this is a subprocess or a tree of a thousand small files, so a
    worker spends nearly all of its time inside a syscall with the interpreter lock
    released: the run is I/O the machine can overlap rather than Python it cannot.
    """
    work_list = list(items)
    if jobs == 1 or len(work_list) < 2:
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


def _newest_snapshot(cache: Path) -> tuple[Path, int, dict[str, list[int | str]],
                                         dict[str, str]] | None:
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
        if not isinstance(data, dict):
            continue
        built, files, gitlinks = data.get("built_ns"), data.get("files"), data.get("gitlinks")
        if (isinstance(built, int) and isinstance(files, dict)
                and isinstance(gitlinks, dict)
                and all(isinstance(path, str) and isinstance(oid, str)
                        for path, oid in gitlinks.items())):
            return (path, built, cast("dict[str, list[int | str]]", files),
                    cast("dict[str, str]", gitlinks))
    return None


def _link_tree(src: Path, dst: Path, jobs: int = 1) -> None:
    """Place directories first, then overlap independent file links within them."""
    def failed(error: OSError) -> None:
        raise error

    entries: list[tuple[Path, Path, list[str]]] = []
    for dirpath, _dirnames, filenames in src.walk(on_error=failed):
        target = dst / dirpath.relative_to(src)
        target.mkdir(parents=True, exist_ok=True)
        entries.append((dirpath, target, filenames))

    def place(entry: tuple[Path, Path, list[str]]) -> None:
        dirpath, target, filenames = entry
        for name in filenames:
            _link_or_copy(dirpath / name, target / name)

    _across(place, entries, jobs)


def _complete_index(root: Path, files: Iterable[str]) -> bool:
    """A carried index must resolve every expected blob in its own object store.

    Git reads object headers in one batch, without rehashing their contents. An
    interrupted cache copy cannot authorize an index shortcut: `add` alone may
    skip an unchanged entry even when the object that entry names is missing.
    """
    names = list(files)
    if not names:
        return True
    try:
        done = subprocess.run(["git", "cat-file", "--batch-check=%(objecttype)"],
                              input="".join(f":{name}\n" for name in names),
                              cwd=root, capture_output=True, encoding="utf-8",
                              errors="replace", check=False, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0 and done.stdout.splitlines() == ["blob"] * len(names)


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
    from its corpus, but the directory itself is stood up and its gitlink is put back
    into the index afterwards. The two serve different readers and both are needed. A
    link at a submodule resolves against the filesystem, and the stand-in file is what
    makes the directory survive, git having no way to track an empty one; the pin rule
    reads the commit each submodule is at out of the index, where `git add -A` over
    that stand-in leaves a blob and no gitlink at all, so `stamp_gitlinks` restores
    what the sandbox's own tree cannot say.

    What comes back is how many files the template holds and how many of those were
    carried from the previous run's snapshot under the cache's rules, stated above it.
    """
    remove_tree(into)
    into.mkdir(parents=True)

    index = corpus_mod.read_index(repo)
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "--full-name",
         "--others", "--exclude-standard"],
        cwd=repo, capture_output=True, text=True, encoding="utf-8", check=False,
        env=corpus_mod._git_environment(repo))
    if proc.returncode != 0:
        raise SystemExit("git ls-files failed in the repository")
    listed = [*index.files, *index.gitlinks, *proc.stdout.splitlines()]

    # the directories first and once each, so that the writes below share nothing and go
    # in together: a thousand small files is the case `_across` is for
    for parent in {(into / rel).parent for rel in listed}:
        parent.mkdir(parents=True, exist_ok=True)

    held = _newest_snapshot(_cache_root(repo))
    snapshot, built_ns, old_files, old_gitlinks = held or (None, 0, {}, {})
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
            (dst / SUBMODULE_STAND_IN).write_text(
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

    # Keep the snapshot's immutable Git objects even when a source changed. An
    # unchanged index can travel with them; otherwise detach it before `add`, so
    # normalization and ignore rules are applied as they are on the cold path.
    # A prior index can otherwise retain CRLF blobs under new text=auto attributes
    # or preserve files excluded by new ignore rules. Rebuilding the object store
    # would also compress every unchanged blob again. A missing or partial store
    # still takes the cold path.
    manifest = {rel: [size, mtime, kind] for rel, (size, mtime, kind) in placed.items()}
    gitlinks = index.gitlinks
    carried_index = False
    if snapshot is not None:
        # a snapshot swept mid-carry surfaces as a link that fails or a walk that
        # yields nothing, and either answers like every other doubt: rebuild
        try:
            _link_tree(snapshot / ".git", into / ".git", jobs)
            carried_index = ((into / ".git" / "index").is_file()
                             and _complete_index(into, old_files))
        except OSError:
            carried_index = False
    if not carried_index:
        remove_tree(into / ".git")
        proc = subprocess.run(["git", "-c", "init.defaultBranch=main", "init", "-q"],
                              cwd=into, capture_output=True, check=False)
        if proc.returncode != 0:
            raise SystemExit("could not build the sandbox index: git init")
    if (not carried_index or manifest != old_files or gitlinks != old_gitlinks
            or carried != sum(1 for _, _, kind in placed.values() if kind == "copy")):
        # Unlink rather than truncate: the old index is still a snapshot's hardlink.
        (into / ".git" / "index").unlink(missing_ok=True)
        proc = subprocess.run(["git", "add", "-A"], cwd=into, capture_output=True, check=False)
        if proc.returncode != 0:
            raise SystemExit("could not build the sandbox index: git add")
    stamp_gitlinks(into, gitlinks)

    # written after the index is built, so no `git add` ever sees it
    (into / _MANIFEST).write_text(
        json.dumps({"built_ns": time.time_ns(), "files": manifest, "gitlinks": gitlinks}),
        encoding="utf-8")
    return copied, carried


# =====================================================================================
# the cases: at least one mutant per rule, each stating the defect it seeds
# =====================================================================================
#
# A case is either a literal substitution or, where the defect is structural, a
# function over the sandbox. Several mutants trip more than one rule, which is expected
# and not a weakness: an id renamed in one artifact is genuinely wrong in every
# artifact that cites it. A case passes when its own rule is among those that reported,
# so collateral findings neither hide a miss nor manufacture a hit.

REGISTER = "docs/requirements-register.md"
SPEC = "docs/spec.md"
CRITIQUE = "docs/background/critique.md"
CROWN = "docs/assurance/crown-jewels.md"
MATRIX = "docs/assurance/coverage-matrix.md"
PROFILE = "docs/hardware/isa-profile.md"
PERF = "docs/performance/performance-estimates.md"
PLAN = "docs/implementation/implementation-checklist.md"
# every landed item's note, and so every findings block, holder citation and landing
# declaration a landed item wrote, lives here from S10b
LOG = "docs/implementation/completion-log.md"
BINDINGS = "docs/assurance/field-bindings.md"
ABSENCE = "docs/hardware/absence-contract.md"
CORPUS_DOC = "docs/assurance/differential-corpus.md"
CONTRACT = "docs/implementation/contracts/freeze-measurement.md"
GEOMETRY = "docs/hardware/block-geometry-constraint.md"
IDL_PROFILE = "docs/languages/idl-profile.md"
THIRD_PARTY = "THIRD-PARTY.md"
DELTA = "docs/hardware/rtl-reparameterization-delta.md"
FINDINGS = "docs/assurance/findings-register.md"
BANK_DSE = "docs/hardware/bank-count-dse-contract.md"
RING_ARTIFACT = "proofs/RingContract.v"
KECCAK_GALLINA = "proofs/Keccak.v"
AESGCM_GALLINA = "proofs/AesGcm.v"
SHA256_GALLINA = "proofs/Sha256.v"
SEAM_WITNESSES = "proofs/SeamWitnesses.v"


# One seeded defect, applied to a sandbox, answering whether it changed anything. A
# mutation that writes nothing is a case that has stopped testing its rule, which is
# why the answer is a bool rather than nothing at all.
type Mutation = Callable[[Sandbox], bool]

# One row of `CASES`: the rule the mutant must provoke, what the mutation is in words,
# and the mutation itself.
type Case = tuple[str, str, Mutation]


@dataclass(frozen=True)
class Seeding:
    """One authored case, named the way a verdict names a generated mutant.

    `vos.seeded.Verdict` is about anything with a `.what`, which for a walked mutant is
    its site and its rewrite. An authored case has no site: it was written rather than
    found, and what identifies it is the rule it is aimed at and the defect it seeds in
    words, both of which its row already carries. Nothing else is added, so the row
    stays the whole of a case and this is a reading of it rather than a second copy.
    """

    rule: str
    description: str

    @property
    def what(self) -> str:
        return f"{self.rule}: {self.description}"


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
                        lambda m: REQ_TOKEN_RE.sub(replacement, m.group()))


def _k14(box: Sandbox) -> bool:
    # the id is read out of the register rather than named here, so the case keeps
    # working when the subsection is re-populated
    register = box.read(REGISTER)
    sub = re.search(r"(?ms)^### 15\.14 .*?(?=^### )", register)
    if not sub:
        return False
    view = box.read(ABSENCE)
    for ident in re.findall(rf"(?m)^\*\*({REQ_ID_PATTERN})\*\* ", sub.group()):
        if ident in view:
            # swapped for another live id, so only the membership is wrong
            return box.write(ABSENCE, view.replace(ident, "R-01-001"))
    return False


def _k26(box: Sandbox) -> bool:
    # An arbitrary stale value must be caught independently of the current inventory.
    return box.write(CRITIQUE, replace_once(
        box.read(CRITIQUE), "\n## ",
        "\nThere are 9999 crown-jewel specifications in view.\n\n## "))



def _k29(box: Sandbox) -> bool:
    text = box.read(PROFILE)
    start = text.find("### 5.1 ")
    if start < 0:
        return False
    m = re.search(r"(?m)^\| `[^\r\n]*R-\d\d-\d+[^\r\n]*", text[start:])
    if not m:
        return False
    row = REQ_TOKEN_RE.sub("the profile", m.group())
    at = start + m.start()
    return box.write(PROFILE, text[:at] + row + text[at + len(m.group()):])


def _k100(box: Sandbox) -> bool:
    """A module renaming the function a row of the lane's fact table points at.

    Every occurrence moves rather than the definition alone, which is what makes this a
    refactor and not a broken file: the module is internally consistent, imports, and
    stops spelling the name a table two directories away names as its consumer. One
    occurrence would leave the call site spelling it and the rule rightly quiet.
    """
    rel = "tools/vos/env.py"
    text = box.read(rel)
    if "_ccache_args" not in text:
        return False
    return box.write(rel, text.replace("_ccache_args", "_ccache_launchers"))


def _k84(box: Sandbox) -> bool:
    """A Tier-B landing that names no rule holding what it created.

    Seeded on the first exit-evidence line rather than written into one item by name,
    so the case survives items landing and being re-ordered around it. The declaration
    is the whole mutation: the four conditions Tier B is admitted on are prose until
    something reads them, and what this asks is whether the fourth one now bites.
    """
    text = box.read(LOG)
    m = re.search(r"(?m)^(?P<ind>[^\S\r\n]*)\* Exit evidence:[^\r\n]*", text)
    if not m:
        return False
    return box.write(LOG, replace_span(
        text, m, f"{m.group()}\n{m.group('ind')}* Landed: Tier B."))


def _k82_entry(box: Sandbox) -> bool:
    """A landed item whose completion-log entry is gone, and whose cell no longer links.

    The heading is deleted whole, so the note beneath it is read as the previous
    entry's, and the plan's cell drops the link it carried, so that the link check does
    not report the dead fragment first and the case decides on K-82's own reading: a
    landed item the log carries no entry for. The item is one whose note carries no
    findings block, so the merge into its neighbour moves no count and the case is
    the totality alone.
    """
    heading = "### M0.5 · Reconcile the baselines\n\n"
    log = box.read(LOG)
    if heading not in log:
        return False
    plan = box.read(PLAN)
    link = " ([note](completion-log.md#m05-reconcile-the-baselines))"
    if link not in plan:
        return False
    return (box.write(LOG, log.replace(heading, "", 1))
            and box.write(PLAN, plan.replace(link, "", 1)))


def _k82_figure(box: Sandbox) -> bool:
    """The register's own size, moved off the figure the entries give.

    Computed from what it finds rather than pinned as a literal, because the figure it
    seeds is one `--fix` rewrites: a literal here would be a derived fact hand-maintained
    in the selftest, and it would go stale on the next item that lands a finding rather
    than on any change to the rule. What the case asks is unchanged, that the repair path
    recognizes the register's size as its own to rewrite.
    """
    text = box.read(FINDINGS)
    m = re.search(r"The plan records (?P<n>\d+) of them", text)
    if not m:
        return False
    return box.write(FINDINGS, replace_span(
        text, m, f"The plan records {int(m.group('n')) - 1} of them"))


# A DECTED width no code reaches, with every figure built on it moved to agree: the
# normative code at about 7 check bits over 4 tag bits, the fallback's implied 6 over 2,
# and the totals, shares, bands and the specification's and bank-count contract's
# copies all consistent with them. The arithmetic holds throughout, so K-69 agrees and
# within K-54 only the distance-6 floor sees that no code of that distance is so short.
_K54_BELOW_FLOOR: list[tuple[str, str, str]] = [
    (REGISTER,
     "under a DECTED code of 8 check bits, the fewest any code of minimum distance 6 over 4 "
     "bits admits, for total metadata of some 22 bits per 256 data bits (8.6%), of which "
     "the tag plane with its own code is 12, some 4.7% of the payload; 128 bits (18 per "
     "128, 14.1%, the tag plane with its code 9 of them at 7.0%)",
     "under a DECTED code of about 7 bits, for total metadata of some 21 bits per 256 data "
     "bits (8.2%), of which the tag plane with its own code is 11, some 4.3% of the "
     "payload; 128 bits (17 per 128, 13.3%, the tag plane with its code 8 of them at 6.3%)"),
    (REGISTER, "about 47–70 MB of SRAM per GB", "about 43–63 MB of SRAM per GB"),
    (REGISTER, "consume 188–560% of a", "consume 172–504% of a"),
    (SPEC, "about 47–70 MB of SRAM per GB", "about 43–63 MB of SRAM per GB"),
    (SPEC, "consume 188–560% of a", "consume 172–504% of a"),
    (SPEC, "12 of the 22 at 256 and 9 of the 18 at 128",
     "11 of the 21 at 256 and 8 of the 17 at 128"),
    (REGISTER, "some 4.7–7.0% of the bulk array", "some 4.3–6.3% of the bulk array"),
    (SPEC, "some 4.7–7.0% of the bulk array", "some 4.3–6.3% of the bulk array"),
    (SPEC, "some 4.7% and 7.0% of the payload", "some 4.3% and 6.3% of the payload"),
    (BANK_DSE, "some 4.7 to 7.0% of the bulk array", "some 4.3 to 6.3% of the bulk array"),
]


def _k54_below_floor(box: Sandbox) -> bool:
    texts: dict[str, str | None] = {}
    for rel, find, repl in _K54_BELOW_FLOOR:
        text = texts[rel] if rel in texts else box.read(rel)
        texts[rel] = None if text is None else replace_once(text, find, repl)
    if any(text is None for text in texts.values()):
        return False
    # every file is written before the verdict is read, so no write is short-circuited
    written = [box.write(rel, text) for rel, text in texts.items()]
    return all(written)


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
    """Remove one source guard, leaving its computed quantity unprotected."""
    rel = "tools/vos/checks/counts.py"
    return _first_match(rel, r"(?m)^    \"sections\": \"the register's normative sections\",\r?\n",
                        lambda _m: "")(box)



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


def _k109(box: Sandbox) -> bool:
    """Change the generated fingerprint without changing authored citations."""
    text = box.read(SEAM_WITNESSES)
    start = text.find(DERIVED_BEGIN)
    if start < 0:
        return False
    found = re.search(r"SHA256: ([0-9a-f]{64})", text[start:])
    if found is None:
        return False
    a, b = start + found.start(1), start + found.end(1)
    changed = ("1" if found.group(1)[0] == "0" else "0") + found.group(1)[1:]
    return box.write(SEAM_WITNESSES, text[:a] + changed + text[b:])


def _k117_switch(box: Sandbox) -> bool:
    """The Rupicola lowering's switch constant renamed wherever it is spelled.

    The driver and its one importer move together, so the lowering still runs and only
    the instrument table's reading of the driver's own literal finds nothing, which is
    to be a finding rather than a row falling out of the set unremarked.
    """
    driver = "tools/bedrock2-lowering/regenerate.py"
    importer = "tools/bedrock2-lowering/hello.py"
    text = box.read(driver)
    renamed = re.sub(r"\bSWITCH\b", "LOWERING_SWITCH", text)
    if renamed == text:
        return False
    return box.write(driver, renamed) and box.write(importer, replace_once(
        box.read(importer), "regenerate.SWITCH", "regenerate.LOWERING_SWITCH"))


def _k117_release(box: Sandbox) -> bool:
    """compare_component.py's release constant renamed wherever it is spelled.

    The comparison still holds its prover to the rig's release under the new name, so
    only the instrument table's reading of the file's own name finds nothing, which is to
    be a finding rather than the row falling back to no stated release unremarked.
    """
    path = "tools/wasm-oracle/compare_component.py"
    text = box.read(path)
    renamed = re.sub(r"\bROCQ_VERSION\b", "PROVER_RELEASE", text)
    return renamed != text and box.write(path, renamed)


def _keep_own_id(entry_line: str) -> str:
    head = re.match(rf"^\*\*{REQ_ID_PATTERN}\*\* ", entry_line)
    if head is None:
        # The caller picked this line out of the register as an entry, so a line that
        # does not open with an id means the mutation no longer applies. Said here
        # rather than as an AttributeError on `None`, which reads as a defect in this
        # tool rather than as the drift it actually is.
        raise SystemExit(f"the entry to mutate does not open with a requirement id: "
                         f"{entry_line[:60]!r}")
    return head.group() + REQ_TOKEN_RE.sub("R-01-001", entry_line[len(head.group()):])


CASES: list[Case] = [
    ("K-00", "a registered rule with its registry row retitled out of the table",
     _literal(RULES, "| K-41 | glyphs", "| K-xx | glyphs")),

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
                  rf"(?m)^\*\*{REQ_ID_PATTERN}\*\* [^\r\n]*Fail-closed seam \*\*[^\r\n]*",
                  lambda m: _keep_own_id(m.group()))),

    ("K-22", "a freshness conferral that stops naming the enumeration collecting it",
     _first_match(REGISTER, f"(?m)^{MID} RoT-fresh:[^\r\n]*R-10-013[^\r\n]*",
                  lambda m: re.sub(r"R-10-013[a-z]*", "the enumeration", m.group()))),

    ("K-23", "an entry speaking the vocabulary of refusal and standing in no column",
     _entry("R-01-001", lambda b: re.sub(
         r"(?m)^(\*\*R-01-001\*\*[^\r\n]*)",
         r"\1 The unit refuses rather than degrades.", b))),

    ("K-24", "an asserted count the artifact no longer gives",
     _renumber(REGISTER, r"[\w-]+(?= requirements confer a refusal)", 0, "ninety-nine")),

    ("K-24", "a multiline prerequisite list loses one enumeration marker",
     _literal(SPEC, "- (3) A **WCET cost-annotation pass", "- A **WCET cost-annotation pass")),

    ("K-24", "the admission-test lead-in states the wrong count",
     _literal(SPEC, "satisfies all five parts", "satisfies all six parts")),

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

    ("K-111", "a Wasm penalty not derived from its workload assumptions",
     _literal(PERF, "| Broad coverage | −80% to −90% |",
              "| Broad coverage | −1% to −90% |")),

    ("K-112", "a scalar Wasm headline not derived from its incremental target",
     _literal(PERF, "| Wasm scalar execution, unchanged Core 3.0 modules (conditional target) | **−45%",
              "| Wasm scalar execution, unchanged Core 3.0 modules (conditional target) | **−1%")),

    ("K-34", "a checklist item whose estimate cell the document cannot read",
     _first_match(PLAN,
                  rf"(?m)^\* \[x\] \*\*[^*]+\*\* {MID} [\d.,]+ h actual",
                  lambda m: re.sub(rf" {MID} [\d.,]+ h actual",
                                   " (about half a day)", m.group()))),

    ("K-34", "an open item's cell carrying no authority class",
     _first_match(PLAN,
                  rf"(?m)^\* \[ \] \*\*[^*]+\*\* {MID} [\d.,]+ h, range [\d.,]+–[\d.,]+ "
                  rf"{MID} [IX](?= {MID}|$)",
                  lambda m: re.sub(rf" {MID} [IX]$", "", m.group()))),

    ("K-35", "an open midpoint that is not the mean of its own range",
     _renumber(PLAN, rf"(?m)^\* \[ \] \*\*[^*]+\*\* {MID} ([\d.,]+)(?= h, range )",
               1, "999")),

    ("K-34", "a retained completion estimate attached to an open checkbox",
     _first_match(PLAN,
                  r"(?m)^\s*\* \[x\] \*\*[^*]+\*\* · [\d.,]+ h retained estimate, actual n/a",
                  lambda m: m.group().replace("[x]", "[ ]", 1))),

    # the range is narrowed about its own stated midpoint rather than at one end, so the
    # mean still holds and K-35 stays quiet: the seeded defect is the span alone, which is
    # what makes this case evidence that K-86 reads the width and not the arithmetic.
    ("K-86", "an open class-X range narrowed to under a factor of two",
     _first_match(PLAN,
                  rf"(?m)^\* \[ \] \*\*[^*]+\*\* {MID} ([\d.,]+) h, range [\d.,]+–[\d.,]+ "
                  rf"{MID} X(?= {MID}|$)",
                  lambda m: re.sub(
                      r"range [\d.,]+–[\d.,]+",
                      f"range {float(m.group(1).replace(',', '')) - 0.5:g}–"
                      f"{float(m.group(1).replace(',', '')) + 0.5:g}",
                      m.group()))),

    ("K-36", "a subtotal that no longer sums the items beneath it",
     _renumber(PLAN, r"(?m)^\*\*[^*]+ subtotal:\*\* ([\d.,]+)(?= h )", 1, "999")),

    ("K-36", "a legacy percentage reintroduced into an item cell",
     _first_match(PLAN, r"(?m)^\* \[x\] \*\*[^*]+\*\* · [\d.,]+ h actual",
                  lambda m: m.group() + " · 99.9%")),

    ("K-37", "a restated grand total the items do not give",
     _renumber(PLAN, r"(?m)^\| Total estimate midpoint h \| ([\d.,]+) \|", 1, "999")),

    ("K-37", "a restated class sum the open items of that class do not give",
     _renumber(PLAN, r"(?m)^\| Open class I h \| ([\d.,]+) \|", 1, "999")),

    ("K-37", "a gate figure its explicit leaves do not give",
     _renumber(PLAN, r"(?m)^\| Committed M8a open h \| ([\d.,]+) \|", 1, "999")),

    # Move the range alone: the midpoint still agrees with its source cells.
    ("K-37", "a committed gate range its explicit leaves do not give",
     _renumber(PLAN, r"(?m)^\| Committed M8a open range h \| ([\d.,]+)–",
               1, "999")),

    ("K-37", "a missing estimate summary marker",
     _literal(PLAN, "<!-- estimate-summary:start -->", "<!-- estimate-summary:missing -->")),

    ("K-37", "a duplicated estimate summary row",
     _first_match(PLAN, r"(?m)^\| Open class I h \|[^\r\n]*",
                  lambda m: m.group() + "\n" + m.group())),

    ("K-37", "a malformed estimate summary value",
     _renumber(PLAN, r"(?m)^\| Total estimate midpoint h \| ([\d.,]+) \|", 1, "unknown")),

    # one recorded estimate is moved in the pool the calibrated total rests on, so the
    # ratio every open class-X cell is priced against moves with it while every actual
    # stays in its cell; K-37 reports the calibrated total beside this, and what the case
    # asks is that the ratio itself is a quotient over the record rather than a figure
    # read out of the sentence stating it
    ("K-96", "a leaf assigned to two work dispositions",
     _literal("docs/implementation/work-order.json", '"Q3b"', '"M7.1a"')),

    ("K-96", "a work owner with an unclassified priced leaf",
     _first_match("docs/implementation/work-order.json", r'(?m)^      "Q3b",\n', lambda _m: "")),

    ("K-96", "a stale generated authoring verdict",
     _literal(PLAN, "available for authoring", "ready without its inputs")),

    ("K-96", "a calibration ratio the record's estimates and the actuals do not give",
     _renumber(PLAN, r"(?m)^\| M0\.8d \| X-authored \| ([\d.,]+) \|", 1, "999")),

    # The generated result site must remain uniquely shaped and numerically derived.
    ("K-96", "a missing calibration result marker",
     _literal(PLAN, "<!-- calibration-results:start -->", "<!-- calibration-results:missing -->")),

    ("K-96", "a duplicated calibration result row",
     _first_match(PLAN, r"(?m)^\| attended \| I \|[^\r\n]*",
                  lambda m: m.group() + "\n" + m.group())),

    ("K-96", "a malformed calibration result cell",
     _renumber(PLAN, r"(?m)^\| attended \| I \| (\d+) \|", 1, "unknown")),

    ("K-96", "a stale calibration result count",
     _renumber(PLAN, r"(?m)^\| attended \| I \| (\d+) \|", 1, "9999")),

    # Removing a source row must fail totality, not silently shrink the fit.
    ("K-96", "a completed attended item the calibration record no longer carries",
     _first_match(PLAN, r"(?m)^\| S1 \| I \| [\d.,]+ \|[^\r\n]*\r?\n", lambda _m: "")),

    # Moving the parallel record changes only its own fit; every actual stays put.
    ("K-96", "an agent-parallel ratio the second record's estimates do not give",
     _renumber(PLAN, r"(?m)^\| M6\.0b \| X-authored \| ([\d.,]+) \|", 1, "999")),

    ("K-96", "a retained estimate presented as a calibration measurement",
     _literal(PLAN, "| M1.2b | n/a | n/a |", "| M1.2b | X-authored | 6 |")),

    ("K-38", "a table row of the wrong width",
     _literal(MATRIX, "| `B-01` | `P-1` |", "| seeded | `B-01` | `P-1` |")),

    ("K-39", "a run of table rows carrying no header rule",
     _seed_paragraph("| a stray row | pasted on its own |")),

    ("K-41", "UTF-8 read as a single-byte encoding",
     _seed_paragraph("The caf" + chr(0x00C3) + chr(0x00A9) + " problem.")),

    ("K-42", "a bindings row disagreeing with the apex record",
     _literal(BINDINGS, "| `spatial_safety` |", "| `spatial_safetyx` |")),

    ("K-43", "a consumer cell that no longer restates the statement", _k43),

    ("K-44", "an instantiation cell in no readable form",
     _literal(BINDINGS, "| none yet |", "| soon |")),

    ("K-45", "a disposition left standing over a requirement that was retired",
     _literal(REGISTER, "**R-03-003** ", "**R-03-903** ")),

    ("K-46", "a computed quantity with no declared owner guard", _k46),

    ("K-47", "an enumeration whose reading has moved off the heading it read",
     _literal(PROFILE, "### 5.1 ", "### 5.9 ")),

    ("K-48", "a view drawing its members from a subsection the register no longer carries",
     _literal("tools/vos/checks/views.py", '"15.14"', '"15.94"')),

    ("K-49", "a view the register obliges and the repository does not carry", _k49),

    ("K-50", "a corpus member the manifest lists and the document does not describe",
     _literal(CORPUS_DOC, "(../../corpus/cap-trap.s)", "(../../corpus/cap-trap-moved.s)")),

    ("K-51", "a corpus member whose program no longer assembles",
     _literal("corpus/cap-trap.s", "cmove   c8, c1", "cmove   c8, c1, c2")),

    # The mark is stripped rather than mangled, because an absent mark is the failure
    # this rule exists for: a new file lands unmarked and reads exactly like a marked
    # one. The target is the checker's own module, so the case cannot be satisfied by
    # a file the repository might stop carrying.
    ("K-52", "a markable file whose license mark has gone",
     _literal("tools/vos/checks/marks.py", "# SPDX-License-Identifier: Apache-2.0\n", "")),
    ("K-52", "an authored OCaml template whose license mark has gone",
     _literal("proofs/campaigns/mlkem_driver.ml.in", "(* SPDX-License-Identifier: Apache-2.0 *)\n", "")),
    ("K-52", "an authored Gallina template whose license mark has gone",
     _literal("proofs/campaigns/mlkem_extract.v.in", "(* SPDX-License-Identifier: Apache-2.0 *)\n", "")),
    ("K-52", "an authored CMake overlay whose license mark has gone",
     _literal("tools/sail-modular/overlay.cmake", "# SPDX-License-Identifier: Apache-2.0\n", "")),
    ("K-52", "an authored Sail project fixture whose license mark has gone",
     _literal("tools/sail-lsp/fixtures/qualification.sail_project", "// SPDX-License-Identifier: Apache-2.0\n", "")),
    ("K-52", "an authored Lustre node whose license mark has gone",
     _literal("supervisor/route/start_restart.lus", "-- SPDX-License-Identifier: Apache-2.0\n", "")),

    # A new file of an unknown kind cannot be seeded, because the corpus is the git
    # index and an untracked file is not in it. Withdrawing a kind's ruling puts an
    # existing file into exactly the state a new kind would arrive in, which is the
    # state the rule exists to report.
    ("K-53", "a tracked file whose kind the tool no longer rules on",
     _literal("tools/vos/checks/marks.py",
              '    ".json": "JSON admits no comment, so a mark would make the file '
              'unparseable",\n', "")),
    ("K-53", "a generated lockfile whose metadata ruling has gone",
     _literal("tools/vos/checks/marks.py",
              '    ".lock": "resolver-generated dependency metadata rather than authored '
              'content",\n', "")),
    ("K-53", "an authored template language whose explicit ruling has gone",
     _literal("tools/vos/checks/marks.py", '    ".ml.in": ("(* ", " *)"),\n', "")),
    ("K-53", "an upstream patch whose byte-preserving ruling has gone",
     _literal("tools/vos/checks/marks.py",
              '    ".patch": "a unified diff must preserve upstream context and hunk bytes",\n', "")),

    # The owner is moved rather than one of the eleven figures, because a figure edited
    # alone is the easy half: what the rule is for is the granule changing under all of
    # them at once, which is the edit nobody would think to propagate by hand. The
    # repair lane seeds K-54 a defect of its own instead of this one; REPAIRABLE says
    # why a moved owner cannot ride it.
    ("K-54", "the tag granule moved out from under every figure derived from it",
     _renumber(REGISTER, r"one validity tag per \*\*(\d+)-bit\*\* granule", 1, "128")),

    # The granule case moves every figure at once and so cannot tell a rule holding the
    # figures against each other from one holding them against coding theory. This one
    # can: the width falls below the floor with everything built on it moved to agree,
    # so a rule narrowed to consistency passes it.
    ("K-54", "a DECTED width below the distance-6 floor under consistent figures",
     _k54_below_floor),

    # One end of one band, moved alone: the fallback codeword's arithmetic is what fixes
    # it, and the low-end holds beside it cannot see it move.
    ("K-54", "an upper band end the fallback codeword does not give",
     _literal(REGISTER, "about 47–70 MB of SRAM per GB", "about 47–71 MB of SRAM per GB")),

    # A rung of the ladder the width is chosen from, moved alone: every codeword figure
    # still agrees, and only pricing the ladder at its floor sees the rung is wrong.
    ("K-54", "a ladder rung extended Hamming, the tags and the linear floor do not give",
     _literal(REGISTER, "full ladder is 21.9 / 14.1 / 8.6 / 5.5%",
              "full ladder is 21.9 / 14.1 / 8.6 / 5.3%")),

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

    ("K-56", "hot guest data moved into the bulk class",
     _first_match(REGISTER, r"(?m)^· Accept: the first class carries[^\r\n]*",
                  lambda m: m.group().replace("bounded hot guest data, ", "").replace(
                      "the second carries bulk by volume,",
                      "the second carries bulk by volume, bounded hot guest data,"))),

    ("K-56", "guest placement loses its fixed class and grant constraint",
     _literal(REGISTER,
              "every extent and pool draw keeps its composition-fixed memory class, "
              "bank grants and timing charge, with no runtime relocation or automatic tiering",
              "guest data may move freely between classes")),

    ("K-56", "bulk guest backing loses its governing placement",
     _literal(REGISTER,
              "Bulk arena backing uses the **second class** by default",
              "Bulk arena backing uses an unspecified class")),

    # One of the transcriptions is moved and the rest are left, which is the shape a
    # real drift takes: an exponent edited in the composition that the model's own
    # assertion would catch only once something executed.
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

    # The *model* is edited rather than a configuration, which is the half of this rule
    # nothing else can see. A geometry moved in a shipped file is K-65's finding too and
    # would seed a case that passes on somebody else's report; a rung re-based in the
    # extension registry moves which vector extensions a vector length names, and no
    # other rule reads that ladder at all. `Zvl32b` is the lowest rung and so the one
    # that decides every rung above it, and the substitution puts its threshold under
    # the floor of `vlen_exp`'s own constraint, which makes it true at every geometry
    # this model can be built at and therefore true of the vectorless composition.
    #
    # The seed is in the *generated bundle* rather than in `extensions.sail`, because
    # that is where this rule reads the ladder since S15: editing the Sail alone leaves
    # the rung this rule sees untouched and reports as K-88's stale artifact instead,
    # which is the correct verdict about that tree and no test of this rule. The anchor
    # carries the clause's own pattern id as well as its body, because a body of
    # `sizeof(vlen_exp) >= 5` is written at more than one rung and `replace_once` would
    # take whichever came first.
    ("K-78", "a minimum-vector-length rung a vectorless composition now reaches",
     _literal(BUNDLE,
              '"id":"Ext_Zvl32b"},"body":{"contents":"sizeof(vlen_exp) >= 5"',
              '"id":"Ext_Zvl32b"},"body":{"contents":"sizeof(vlen_exp) >= 3"')),

    # The *configuration* is edited rather than the profile or the model, because that
    # is the direction this defect arrives from and the reason the rule exists: the
    # exclusion is a setting, so switching it back on is one key in one file that no
    # review gate reads, where an edit to either of the other two artifacts is an act
    # somebody takes deliberately.
    ("K-87", "an excluded-by-name extension a shipped configuration switches back on",
     _literal("model/config/verifiedos.json",
              '"Zbc": { "supported": false }',
              '"Zbc": { "supported": true }')),

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

    ("K-67", "a resolved checker pin drifted from the manifest",
     _literal("tools/uv.lock", 'name = "ruff"\nversion = "0.16.9"',
              'name = "ruff"\nversion = "0.16.8"')),

    # One site of a fact two pairs state is reworded while its siblings stand, which
    # is the drift K-61 cannot see: the edited pair blesses on its own two sides and
    # the other pair's copy stays green. K-61 fires on the edited entry too, which is
    # expected collateral; the case passes only on K-68's own report.
    ("K-68", "a co-stated fact one of its sites no longer states",
     _entry("R-14-007", lambda entry: entry.replace(
         "capabilities beyond pure compute", "capabilities beyond pure computation"))),

    # An owned enumeration's lead-in moves with the list untouched: the reader
    # returns zero, and the guard must report the moved owner even without prose claims.
    ("K-46", "an owned enumeration whose lead-in moved out of the reader's reach",
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
    # The standing column is the one column of the matrix no hand writes: the
    # inventory's status lifted over the rows a cell's requirements constrain. A cell
    # assigned another standing by hand is the defect. Other rules read it as sound:
    # the mode still places,
    # the citations still resolve, the row is still its header's width. The cell is
    # found by its standing rather than named, and changes any valid standing so the
    # case survives the last not-authored or partial cell being implemented.
    ("K-95", "a coverage cell whose standing differs from the inventory",
     _first_match(MATRIX,
                  r"(?m)^\| `B-\d\d` \| `P-\d` \|[^\r\n]*\| (authored|partial|not authored) \|$",
                  lambda m: m.group().replace(f"| {m[1]} |",
                      "| not authored |" if m[1] == "authored" else "| authored |"))),

    # The settings express one target in different dialects. Narrative references
    # may omit the version; executable configuration must still agree.
    ("K-75", "a checker settings file at an interpreter floor the other does not fix",
     _literal("tools/ruff.toml", 'target-version = "py314"',
              'target-version = "py313"')),
    # The floor the gate actually runs on, which is the copy that decides whether a
    # green run says anything: a workflow an interpreter below the floor would admit
    # constructs the tools are written to refuse.
    ("K-75", "a host workflow interpreter below the floor ty.toml fixes",
     _literal(".github/workflows/host-gates.yml", 'python-version: "3.14"',
              'python-version: "3.13"')),
    ("K-75", "a guest workflow interpreter below the floor ty.toml fixes",
     _literal(".github/workflows/guest-gates.yml", 'python-version: "3.14"',
              'python-version: "3.13"')),
    # The campaign installs the interpreter in each of its jobs, so the second job's
    # copy is seeded too: a rule reading only the first site in a file passes it.
    ("K-75", "a campaign workflow's first interpreter below the floor ty.toml fixes",
     _literal(".github/workflows/boot-crypto-target.yml", 'python-version: "3.14"',
              'python-version: "3.13"')),
    ("K-75", "a campaign workflow's later interpreter below the floor ty.toml fixes",
     _first_match(".github/workflows/boot-crypto-target.yml",
                  r'(python-version: "3\.14".*)python-version: "3\.14"',
                  lambda m: m[1] + 'python-version: "3.13"', flags=re.DOTALL)),
    # The instrument switch route installs the interpreter in each of its five jobs, so
    # each job's copy is seeded on its own, found within that job's block.
    *(("K-75", f"the instrument switch route's {job} job interpreter below the floor "
       "ty.toml fixes",
       _first_match(".github/workflows/instrument-switches.yml",
                    rf'(^  {job}:\n(?:(?!^  [\w-]+:\n).)*?)python-version: "3\.14"',
                    lambda m: m[1] + 'python-version: "3.13"', flags=re.MULTILINE | re.DOTALL))
      for job in ("plan", "build", "import", "seed", "join")),
    ("K-75", "a project admitting an interpreter below the typing target",
     _literal("tools/pyproject.toml", 'requires-python = ">=3.14,<3.15"',
              'requires-python = ">=3.13,<3.15"')),

    # The configuration is moved rather than the record, because that is the direction
    # no reader of one file can see: the record goes on naming the parameter that takes
    # the predictor and the build it names has stopped taking it, which is a claim that
    # a structure is absent standing over an elaboration that instantiates it. Moving
    # the record instead would be the easy half and would read as an ordinary edit.
    ("K-76", "a synthesis parameter the provenance record binds set to another value",
     _literal("rtl/vos_c_class_config_pkg.sv", "BHTEntries: unsigned'(0),",
              "BHTEntries: unsigned'(1),")),

    # The reviewed license row must still match the elaborator's enforced pin;
    # secondary prose refers to this row without copying its version.
    ("K-97", "an elaborator pin the record states and the lane's own constant refuses",
     _literal(THIRD_PARTY, "pinned at **5.052**", "pinned at **5.036**")),

    # A workflow's action moves to a commit its row never reviewed, which is what a
    # bump without a licence read leaves. The first pinned line is found by its shape
    # and its last digit changed, so the case survives every reviewed bump.
    ("K-115", "a workflow action at a commit its reviewed row does not state",
     _first_match(".github/workflows/host-gates.yml",
                  r"(?m)^(\s*- uses: [^@\s]+@[0-9a-f]{39})([0-9a-f])",
                  lambda m: m[1] + ("1" if m[2] == "0" else "0"))),
    # The same line returned to a movable tag: the row still states a reviewed commit,
    # and nothing fixes the code the tag names on the next run.
    ("K-115", "a workflow action referenced by a tag that can move",
     _first_match(".github/workflows/host-gates.yml",
                  r"(?m)^(\s*- uses: [^@\s]+)@[0-9a-f]{40} # (v\d+)\.\d+\.\d+$",
                  lambda m: f"{m[1]}@{m[2]}")),
    # The same line under a quoted key, which GitHub runs exactly as the bare one and the
    # block reading does not take: the action is run elsewhere too, so only the census of
    # `uses` keys stops the rule reporting agreement about a line it never read.
    ("K-115", "a workflow action stated in a shape the reading does not parse",
     _first_match(".github/workflows/host-gates.yml",
                  r"(?m)^(\s*- )uses:( [^@\s]+@[0-9a-f]{40} # v\d+\.\d+\.\d+)$",
                  lambda m: f'{m[1]}"uses":{m[2]}')),
    # The same line as an explicit key carrying a comment, the key on one line and the
    # reference on the next: YAML reads the step unchanged, and only a census counting
    # every explicit-key indicator, whatever follows it, sees the reference at all.
    ("K-115", "a workflow action stated as an explicit key with a trailing comment",
     _first_match(".github/workflows/host-gates.yml",
                  r"(?m)^([ \t]*)- uses:( [^@\s]+@[0-9a-f]{40} # v\d+\.\d+\.\d+)$",
                  lambda m: f"{m[1]}- ? uses # the action\n{m[1]}  :{m[2]}")),
    # A step before that line runs the same action from a flow mapping whose explicit key
    # stands flush against its `?`: PyYAML reads every `?` inside a flow collection as a
    # key's indicator, so the workflow gains a step that runs the action, and only a
    # census counting a flow `?` whatever follows it sees the step. The step is added
    # rather than the line rewritten, a flow mapping being unable to take the `with:`
    # block under that line, and a workflow YAML refuses would test nothing.
    ("K-115", "a workflow action stated as a flow mapping's unspaced explicit key",
     _first_match(".github/workflows/host-gates.yml",
                  r"(?m)^([ \t]*)- uses: ([^@\s]+@[0-9a-f]{40})( # v\d+\.\d+\.\d+)$",
                  lambda m: f"{m[1]}- {{?uses: {m[2]}}}{m[3]}\n{m[0]}")),
    # A step before that line runs the same action from a flow mapping whose `uses` key
    # follows a quoted name continued onto a line opening with `#`: that line is the
    # scalar's text rather than a comment, so the workflow gains a step that runs the
    # action, and only a census reading every line, a comment's included, counts the key.
    ("K-115", "a workflow action stated after a quoted scalar's line opening with #",
     _first_match(".github/workflows/host-gates.yml",
                  r"(?m)^([ \t]*)- uses: ([^@\s]+@[0-9a-f]{40})( # v\d+\.\d+\.\d+)$",
                  lambda m: f'{m[1]}- {{name: "the action\n{m[1]}  # pinned", '
                            f"uses: {m[2]}}}{m[3]}\n{m[0]}")),
    # The record's side: a row renamed away from the action it reviews leaves both a
    # workflow running code with no row and a row reviewing code nothing runs.
    ("K-115", "an action row that names no action a workflow runs",
     _literal(THIRD_PARTY, "| actions/download-artifact |", "| actions/download-artifacts |")),
    # A row's licence link moved off the commit the row reviewed, its last digit changed
    # so the case survives every reviewed bump: the reviewed revision and every workflow
    # still agree, and only a rule holding the link to that revision sees the terms
    # linked at another edition.
    ("K-115", "an action row linking its licence at a commit other than the one it reviewed",
     _first_match(THIRD_PARTY, r"(github\.com/actions/checkout/blob/[0-9a-f]{39})([0-9a-f])",
                  lambda m: m[1] + ("1" if m[2] == "0" else "0"))),
    # The same row gaining a second link to its licence on GitHub's raw-content host,
    # which serves the same file, at a commit its last digit moved off the reviewed one.
    # The row still links its terms at the reviewed commit, so only a reading taking the
    # raw host holds the second link.
    ("K-115", "an action row linking its licence through another host at another commit",
     _first_match(THIRD_PARTY, r"(https://github\.com/(actions/checkout)/blob/"
                               r"([0-9a-f]{39})([0-9a-f])/LICENSE)\)",
                  lambda m: f"{m[1]}) and [a copy](https://raw.githubusercontent.com/{m[2]}/"
                            f"{m[3]}{'1' if m[4] == '0' else '0'}/LICENSE)")),
    # The same row gaining a link to its action's tree at a branch, no path following the
    # branch. The reviewed link still agrees, so only a reading that ends the revision at
    # the link's end, and not only at a following `/`, holds the branch.
    ("K-115", "an action row linking its action's tree at a branch",
     _first_match(THIRD_PARTY, r"(\[MIT LICENSE\]\(https://github\.com/(actions/checkout)/"
                               r"blob/[0-9a-f]{40}/LICENSE\))",
                  lambda m: f"{m[1]} in [its tree](https://github.com/{m[2]}/tree/main)")),
    # The same row gaining a link to its action's tree at the reviewed commit followed by
    # `_` in its Markdown destination, which GFM keeps, so the link names a ref other
    # than the commit, one a branch may carry. The reviewed link still agrees, so only a
    # reading that runs a destination's revision to the bracket closing it, rather than
    # stripping trailing punctuation from it as from a bare link, holds the other ref.
    ("K-115", "an action row linking its action's tree at the reviewed commit plus `_`",
     _first_match(THIRD_PARTY, r"(\[MIT LICENSE\]\(https://github\.com/(actions/checkout)/"
                               r"blob/([0-9a-f]{40})/LICENSE\))",
                  lambda m: f"{m[1]} in [its tree](https://github.com/{m[2]}/tree/{m[3]}_)")),
    # The row's licence link narrowed to its action's tree at the reviewed commit, no path
    # following the commit: the link still names the reviewed revision and every
    # workflow agrees, so only a reading that tells a view naming a file from one naming
    # none sees a row that no longer links its terms.
    ("K-115", "an action row linking its action's tree at the reviewed commit and no file",
     _first_match(THIRD_PARTY, r"\[MIT LICENSE\]\(https://github\.com/(actions/checkout)/"
                               r"blob/([0-9a-f]{40})/LICENSE\)",
                  lambda m: f"[MIT LICENSE](https://github.com/{m[1]}/tree/{m[2]})")),
    # The row's licence link dropped, its text kept: the row still states its reviewed
    # revision and every workflow agrees with it, and only a rule requiring the link
    # sees a row that no longer says where its terms were read.
    ("K-115", "an action row linking no licence of its action",
     _first_match(THIRD_PARTY, r"\[(MIT LICENSE)\]\(https://github\.com/actions/checkout/"
                               r"blob/[0-9a-f]{40}/LICENSE\)",
                  lambda m: m[1])),
    # A gitlink moved with an artifact derived through it left behind, seeded as the
    # recorded commit's first digit changed so the index, the licence record and every
    # restating sentence still agree. The registry's line names no upstream, so K-81
    # cannot see it and only this rule holds it. The case anchors on the line's own
    # words rather than on the pinned id, so a pin advance does not unseed it.
    ("K-116", "a width-transform registry naming a commit the imported core's gitlink "
              "does not carry",
     _first_match("tools/rtl-width-transforms.json", r'^(  "pin": ")([0-9a-f])',
                  lambda m: m[1] + ("1" if m[2] != "1" else "2"))),

    # A development-tool row moved to a release its lock does not fix, the drift a row
    # edited without its owner leaves: the release is extended rather than spelled, so
    # the case survives every reviewed bump.
    ("K-118", "a development-tool row stating a release its lock does not fix",
     _first_match(THIRD_PARTY, r"filelock `(\d[^`]*)`", lambda m: f"filelock `{m[1]}.1`")),
    # The other direction, which no reader of the record can see: the lock moves and
    # the row it owns stays, a bump without a licence read.
    ("K-118", "a locked Python release its development-tool row does not state",
     _first_match("tools/uv.lock", r'name = "filelock"\r?\nversion = "([^"]+)"',
                  lambda m: m.group().replace(f'"{m[1]}"', f'"{m[1]}.1"'))),
    # The same direction through an opam snapshot, a different owner reader: one
    # switch's Zarith moves while the row says every switch carries one release.
    ("K-118", "an opam snapshot release its development-tool row does not state",
     _first_match("tools/opam/sail.lock", r'"zarith\.([^"]+)"',
                  lambda m: f'"zarith.{m[1]}.1"')),
    # Both directions through the CertiRocq snapshot's rows, which read each package's
    # backticked release by its name: an OCaml library moves in the lock while its row
    # stays, and the row's release moves while the lock stays.
    ("K-118", "a CertiRocq snapshot release its development-tool row does not state",
     _first_match("tools/opam/certirocq.lock", r'"yojson\.([^"]+)"',
                  lambda m: f'"yojson.{m[1]}.1"')),
    ("K-118", "a CertiRocq snapshot row stating a release its lock does not fix",
     _first_match(THIRD_PARTY, r"yojson `(\d[^`]*)`", lambda m: f"yojson `{m[1]}.1`")),
    # A licence reading's tag list gains a tag in a form the list's reading cannot take:
    # every other tag still agrees with the switches, so only a list read item by item,
    # with an unreadable item a finding, keeps the row from passing over it unread.
    ("K-118", "a development-tool tag list naming a tag its reading cannot take",
     _first_match(THIRD_PARTY, r"byte-identical at the `", lambda m: f"{m[0]}rocq-9.0.0`, `")),
    # A workflow analyzer's licence link moved to a tag the lock does not install while
    # its bold release stays: the release the terms were read at and the link to them
    # now disagree, and only a site reading the tag holds the link at all.
    ("K-118", "a workflow analyzer's licence tag its lock does not install",
     _first_match(THIRD_PARTY, r"(zizmorcore/zizmor/blob/v)(\d[^/]*)(/LICENSE)",
                  lambda m: f"{m[1]}{m[2]}.1{m[3]}")),
    # A held row gains a release in an opam identifier's spelling, which no site reads:
    # only a census reading a release after its package name's dot sees it at all.
    ("K-118", "a development-tool row stating an opam identifier's release no site reads",
     _first_match(THIRD_PARTY, r"(Gallina input generator in a dedicated switch), built",
                  lambda m: f"{m[1]} beside `coq-simple-io.1.10.0`, built")),
    # The same row gains a release after an opam name ending in digits: a census taking
    # every numeral whose dot follows a digit for the tail of the numeral before it
    # leaves that release unread.
    ("K-118", "a development-tool row stating a release after a name ending in digits",
     _first_match(THIRD_PARTY, r"(Gallina input generator in a dedicated switch), built",
                  lambda m: f"{m[1]} beside `base64.3.5.1`, built")),
    # The same row gains a release after a name whose last letter, a `v`, follows a digit:
    # a census taking every `v` after a non-letter for a tag's prefix, and not only one
    # after a hyphen or `+`, leaves that release unread.
    ("K-118", "a development-tool row stating a release after a letter following digits",
     _first_match(THIRD_PARTY, r"(Gallina input generator in a dedicated switch), built",
                  lambda m: f"{m[1]} beside `x86v3.5.1`, built")),
    # The same direction through a snapshot's commit pin, another owner reader: the
    # QuickChick snapshot's pinned commit moves while the row names the one its licence
    # was read at. The commit's first digit changes, so a moved pin leaves it seeded.
    ("K-118", "an opam snapshot's pinned commit its development-tool row does not state",
     _first_match("tools/opam/quickchick.lock", r"(QuickChick\.git#)([0-9a-f])",
                  lambda m: m[1] + ("1" if m[2] != "1" else "2"))),
    # A declared row nothing here owns gains a second release in its licence link text,
    # so the row no longer says which release its terms were read at.
    ("K-118", "a declared development-tool row stating two releases",
     _first_match(THIRD_PARTY, r"\[v(\d[^ \]]*)( LICENSE\]\(https://github\.com/cli/cli/)",
                  lambda m: f"[v{m[1]}.1{m[2]}")),
    # The same direction through the model's hook configuration, whose rev pins a
    # commit and whose `# frozen:` comment names the tag that commit was read at: each
    # half moves alone while the hook's row stays, the release extended rather than
    # spelled and the commit's first digit changed, so a reviewed bump leaves both seeded.
    ("K-118", "a hook release the model's hook configuration pins and its row does not state",
     _first_match("model/.pre-commit-config.yaml", r"# frozen: v(\d\S*)",
                  lambda m: f"# frozen: v{m[1]}.1")),
    ("K-118", "a hook commit the model's hook configuration pins and its row does not state",
     _first_match("model/.pre-commit-config.yaml", r"^([ \t]+rev: \"?)([0-9a-f])",
                  lambda m: m[1] + ("1" if m[2] != "1" else "2"))),
    # The first entry's rev moved to its tag under a comment other than `# frozen:`, and
    # its reviewed rev line written into a hook's block-scalar description: YAML reads
    # the entry's rev as the tag and the line as the description's text, so only a
    # reading that takes the rev key at the column of the entry's `repo` key, in the one
    # shape it reads, sees the entry run a revision its row did not review.
    ("K-118", "a hook repository's rev a line inside a hook's block scalar stands in for",
     _first_match("model/.pre-commit-config.yaml",
                  r'^([ \t]+)rev: "?([0-9a-f]{40})"? # frozen: (\S+)\n'
                  r"(\1hooks:\n([ \t]+)- id: \S+\n)",
                  lambda m: (f"{m[1]}rev: {m[3]} # the tag\n{m[4]}{m[5]}  description: |\n"
                             f"{m[5]}    rev: {m[2]} # frozen: {m[3]}\n"))),
    # A repository entry anchored under the `ci` mapping pre-commit loads unchecked, on a
    # line whose `#` follows a no-break space, and aliased into `repos`: YAML's blanks are
    # the space and the tab alone, so that line is a key rather than a comment, and only
    # a census skipping no other line as one sees the entry pre-commit would run.
    ("K-118", "a hook repository anchored on a line a no-break space opens and aliased in",
     _first_match("model/.pre-commit-config.yaml", r"^(repos:\n.*)\Z",
                  lambda m: ("ci:\n  \u00a0#x: &unreviewed {repo: https://github.com/example/"
                             f"unreviewed-hooks, rev: {'d' * 40}, hooks: [{{id: unreviewed}}]}}\n"
                             f"{m[1]}  - *unreviewed\n"),
                  flags=re.MULTILINE | re.DOTALL)),
    # A hook repository appended as a flow mapping whose keys follow its hook's quoted
    # name continued onto a line opening with `#`: that line is the name's text and then
    # the entry's keys rather than a comment, so pre-commit runs the entry, and only a
    # census reading every line, a comment's included, sees it.
    ("K-118", "a hook repository stated after a quoted scalar's line opening with #",
     _first_match("model/.pre-commit-config.yaml", r"\Z",
                  lambda _: '  - {hooks: [{id: unreviewed, name: "the unreviewed hook\n'
                            '    # reviewed"}], repo: https://github.com/example/'
                            f"unreviewed-hooks, rev: {'d' * 40}}}\n")),
    # A hook repository appended as a flow mapping whose every key stands flush against
    # its explicit-key `?`: PyYAML and libyaml read every `?` inside a flow collection as
    # a key's indicator, so pre-commit runs the entry, and only a census counting a flow
    # `?` whatever follows it, as K-115's does, sees it.
    ("K-118", "a hook repository stated as a flow mapping of unspaced explicit keys",
     _first_match("model/.pre-commit-config.yaml", r"\Z",
                  lambda _: "  - {?repo: https://github.com/example/unreviewed-hooks, "
                            f"?rev: {'d' * 40}, ?hooks: [{{?id: unreviewed}}]}}\n")),
    # A hook repository appended as a flow mapping whose `repo` and `rev` keys each open
    # their line flush against a byte-order mark: libyaml, whose loader pre-commit takes,
    # skips a U+FEFF opening any line, so pre-commit runs the entry, and only a census
    # reading a key after one as after a blank sees it.
    ("K-118", "a hook repository whose keys follow a byte-order mark opening their lines",
     _first_match("model/.pre-commit-config.yaml", r"\Z",
                  lambda _: "  - {hooks: [{id: unreviewed}],\n"
                            "\ufeffrepo: https://github.com/example/unreviewed-hooks,\n"
                            f"\ufeffrev: {'d' * 40}}}\n")),
    # The first entry's reviewed rev line moved inside a flow sequence, where it stands
    # at the entry's key column and is no key of the entry, and a merge key supplying the
    # rev YAML loads from a mapping anchored inside a `meta` entry put before it, whose
    # lines no reading holds: pre-commit runs the moved rev, and only a census reporting
    # every merge key sees the entry run a revision its row did not review.
    ("K-118", "a hook repository's rev a merge key supplies from a meta entry's mapping",
     _first_match("model/.pre-commit-config.yaml",
                  r"^(repos:\n)(  - repo: \S+\n)([ \t]+)(rev: .*\n)",
                  lambda m: (f"{m[1]}  - repo: meta\n{m[3]}x: &moved {{\n{m[3]}rev: {'d' * 40}\n"
                             f"{m[3]}}}\n{m[3]}hooks: [{{id: check-useless-excludes}}]\n{m[2]}"
                             f"{m[3]}<<: *moved\n{m[3]}x: [\n{m[3]}{m[4]}{m[3]}]\n"))),
    # The first entry stating a second rev, its commit's last digit changed, after a line
    # separator closing the entry's last line: YAML breaks the line there and keeps the
    # last rev, so only a reading splitting the file where YAML does sees two revs.
    ("K-118", "a hook repository's second rev after a line separator",
     _first_match("model/.pre-commit-config.yaml",
                  r'^([ \t]+)rev: "?([0-9a-f]{39})([0-9a-f])"?.*?(?=\n[ \t]*- repo:)',
                  lambda m: f"{m[0]}\u2028{m[1]}rev: {m[2]}{'1' if m[3] == '0' else '0'}",
                  flags=re.MULTILINE | re.DOTALL)),
    # A hook repository appended with no row, pinned as `autoupdate --freeze` writes a
    # reviewed one: every row still agrees with its own entry, so only a census of every
    # entry the configuration carries sees code pre-commit runs whose terms nobody read.
    # Its commit is spelled in letters, which YAML 1.1 reads as the string pre-commit's
    # schema requires, where forty zeros would load as the octal integer 0 it refuses.
    ("K-118", "a hook repository the model's hook configuration runs and no row reviews",
     _first_match("model/.pre-commit-config.yaml", r"\Z",
                  lambda _: "  - repo: https://github.com/example/unreviewed-hooks\n"
                            f"    rev: {'d' * 40} # frozen: v1.0.0\n"
                            "    hooks:\n      - id: unreviewed\n")),
    # The build constraints move setuptools, every hook package's build backend, while
    # its development-tools row stays: the release is extended rather than spelled, so a
    # reviewed bump leaves the case seeded, and only a reading of the pip constraint
    # files the model's hook step installs from sees a backend whose terms nobody read.
    ("K-118", "a hook build backend the pip constraints pin and its row does not state",
     _first_match("tools/ci/model-hooks-build-constraints.txt", r"^(setuptools==)([^\s\\]+)",
                  lambda m: f"{m[1]}{m[2]}.1")),
    # A pin appended for a package no row reads, as a dependency a hook gained would be
    # pinned: every row still agrees with the pins it reads, so only a census of every
    # pin the constraint files carry sees a release pip installs whose terms nobody read.
    ("K-118", "a hook dependency the pip constraints pin and no row reads",
     _first_match("tools/ci/model-hooks-constraints.txt", r"\Z",
                  lambda _: "unreviewed-dependency==1.0.0\n")),
    # The first pin continued onto a line carrying a marker no platform meets: pip joins
    # a line ending in `\` with the next, so the pin applies nowhere and pip installs
    # whatever release the hook asks for, while the pin's own line still reads as the
    # release its row states. Only a reading joining the lines as pip joins them sees it.
    ("K-118", "a hook dependency pin a continued marker leaves applying nowhere",
     _first_match("tools/ci/model-hooks-constraints.txt", r"^([A-Za-z0-9._-]+==[^\s\\]+)\n",
                  lambda m: f"{m[1]} \\\n    ; sys_platform == \"never\"\n")),

    # A one-letter respelling of a licence file's name, inside the backticks that make
    # the cell a path rather than a link. That is the whole point of the case: the row
    # still renders, the table is still the width its header declares, no id and no
    # count moves, and K-12 cannot see it because there is no link here to follow. The
    # component goes on being listed as redistributed here while the terms it is
    # redistributed under are named at a file the index does not carry.
    ("K-80", "a component's licence text named at a path the repository does not carry",
     _literal(THIRD_PARTY, "`model/dependencies/elfio/LICENSE.txt`",
              "`model/dependencies/elfio/LICENCE.txt`")),
    # A landing-loop tool is given an import of the quarantine, which is the whole of
    # what the move would otherwise not have prevented: the directory is an ordinary
    # package on `tools/`, so the statement resolves and the coupling is back with every
    # other gate still green. The seeded file is one no other tool imports, so the
    # sandbox's own checker run is unaffected and the case decides about K-83 alone; the
    # statement is written here inside a string on one line, which is why the rule is
    # anchored at a line start and this file is not a site of its own. The anchor is the
    # one import that tool cannot lose rather than the first line of its import block,
    # because a tool gaining a module rewrites that line and the case would then seed
    # nothing, which is a finding about the case and not about the rule.
    ("K-83", "a landing-loop tool that imports the quarantined instruments",
     _literal("tools/vos/cli/blast.py", "from vos.corpus import find_root",
              "from quarantine import freeze\nfrom vos.corpus import find_root")),

    # One rule gets one case, and this rule gets two, because it holds two ways in and
    # the case above reaches only one: with the path half deleted the mutant above is
    # still killed, so a rule narrowed to imports would pass its own selftest while a
    # landing-loop tool went on launching a quarantined entry point by path. The seed is
    # a tool putting the quarantine on its own import path, which is how the coupling
    # arrives for a program whose hyphenated name no import statement can spell.
    ("K-83", "a landing-loop tool that puts the quarantine on its own path",
     _literal("tools/run.py",
              'sys.path.insert(0, str(Path(__file__).resolve().parent))',
              'sys.path.insert(0, str(Path(__file__).resolve().parent / "quarantine"))')),

    # The transcription is moved and the definition is left, which is the direction the
    # defect arrives from: the model is the definition and nothing edits it to follow a
    # SystemVerilog package. The address width is the one to move because it is the
    # parameter with the most restatements, so a real drift in it would leave four other
    # sites still agreeing with each other and only this rule reading the fifth against
    # the model. K-57 opens that file too, for the welded block size, and this moves a
    # different localparam, so the case passes on K-79's own report.
    ("K-79", "a capability-format width the authored package and the model no longer "
             "agree on",
     _literal("rtl/vos_cheri_pkg.sv",
              "localparam int unsigned CapAddrWidth = 36;",
              "localparam int unsigned CapAddrWidth = 32;")),
    # A restating site rather than the record's row, which is the direction the rule
    # is built around: the licence record and the gitlink go on agreeing, so the
    # first hop stays green and only the second can see it. Moving the row instead
    # would fire the first hop and prove nothing about the second. The digit changed
    # is the last of the delta's provenance cell, so the mutant is a transcription
    # slip and not a pin that has moved, and no other rule opens that cell: the case
    # passes on K-81's own report with no collateral.
    ("K-81", "an upstream pin restated as a commit the record does not record",
     _literal(DELTA, "| `0c7b3adf` | 2026-09-24 |", "| `0c7b3ade` | 2026-09-24 |")),
    ("K-81", "a historical modular receipt gitlink changed outside its exact scoped edition",
     _literal("docs/assurance/sail-assistance-evidence/modular.json",
              "gitlink:24c6e2d8531e6a6d0a9e29bde2a109484099aec9",
              "gitlink:0000000000000000000000000000000000000000")),
    ("K-81", "a scoped libclang license reading changed without its recorded edition",
     _literal("THIRD-PARTY.md", "2078da43e25a4623cab2d0d60decddf709aaea28",
              "0000000000000000000000000000000000000000")),

    # One holder citation moved onto the id the numbering is missing, which is the
    # defect in the shape it actually arrives in rather than an invented one: the plan
    # already reports a gap at that id, so a hand reaching for the next free number
    # writes exactly this. The citation moved is the capability format's, and no other
    # rule reads a K- id in this document, so the case passes on K-84's own report.
    ("K-84", "a landing naming a holder the rule registry does not carry",
     _literal(LOG, "**K-79**", "**K-64**")),

    # The other half, and the case above does not reach it: with the declaration loop
    # deleted that mutant is still killed, so a rule narrowed to its citations would
    # pass its own selftest. A Tier-B landing naming nothing is what the fourth of the
    # four conditions exists to refuse, and it is the state the rule was written for.
    ("K-84", "a Tier-B landing naming no rule holding what it created", _k84),

    ("K-84", "a current claim relying on a retired rule",
     _literal(PLAN, "K-86 checks this span floor", "**K-102** checks this span floor")),

    # A class list that stopped growing, which is the direction the defect arrives from:
    # a rule is registered and the list that should name it is left as it was. The id
    # dropped is the head of the total class's list, a rule no other case moves, so the
    # registry and the code go on agreeing and only this rule reads the list at all.
    ("K-119", "a registered rule dropped from its reach class's list",
     _literal(RULES, "That is what K-00, K-38,", "That is what K-38,")),

    # The other direction, which the case above does not reach: with the two-class
    # finding deleted that mutant is still killed, so a rule narrowed to unplaced rules
    # would pass its own selftest while a rule named under two classes left its reach
    # undecidable from the page. The same rule is written into the name class's list
    # as well, so every id still resolves and only the exactly-one reading can see it.
    ("K-119", "a registered rule named under a second reach class",
     _literal(RULES, "which is what K-01 through K-17,",
              "which is what K-00, K-01 through K-17,")),

    # A fifth class opened in other words than the four use. It carries no membership
    # sentence, so an opener read only as `found by` or `a` before the bold name passes
    # it over and the text sits unnoticed inside the pattern class's region.
    ("K-119", "a fifth reach class opened in words the four do not use",
     _literal(RULES, "Where the set is **total**,",
              "Where the set is located by **marker**, nothing is read. "
              "Where the set is **total**,")),

    # The lead with no class in bold before a full stop or the line's end, which opens
    # nothing and is otherwise read as part of the class before it.
    ("K-119", "a 'Where the set is' sentence naming no class",
     _literal(RULES, "Where the set is **total**,",
              "Where the set is located by a marker, nothing is read. "
              "Where the set is **total**,")),

    # The same fifth class opened mid-sentence, its lead in lower case. It carries no
    # membership sentence either, so a lead read in one letter case alone passes it over
    # as part of the pattern class's text.
    ("K-119", "a fifth reach class opened mid-sentence in lower case",
     _literal(RULES, "Where the set is **total**,",
              "Past them, where the set is located by **marker**, nothing is read. "
              "Where the set is **total**,")),

    # The same fifth class with its lead set in underscore italics, which opens nothing.
    # A lead found only at a word boundary does not see it, the underscore counting as a
    # word character, so the text sits unnoticed inside the pattern class's region.
    ("K-119", "a fifth reach class whose lead is set in underscore italics",
     _literal(RULES, "Where the set is **total**,",
              "_Where the set is_ located by **marker**, nothing is read. "
              "Where the set is **total**,")),

    # The same again with its lead wrapped across a line, which opens nothing either. A
    # lead found only with single spaces between its words does not see it.
    ("K-119", "a fifth reach class whose lead is wrapped across a line",
     _literal(RULES, "Where the set is **total**,",
              "Where the set\nis located by **marker**, nothing is read. "
              "Where the set is **total**,")),

    # The total class's name with a stray `*` past its closing pair, outside the form
    # the page states. An opener holding only the other three sides of the two pairs
    # reads it as the total class as before, so the section reads as agreeing with the
    # registry while its lead stands in a form the rule says it does not take.
    ("K-119", "a reach class whose bold name is trailed by a third '*'",
     _literal(RULES, "Where the set is **total**,", "Where the set is **total***,")),

    # A membership sentence ahead of the first class, which no class's region reaches.
    # The rule it names is still placed once by its own class, so the section reads as
    # agreeing with the registry and only a reading of the stretch before the first
    # class sees a class introduced there in other words.
    ("K-119", "a membership sentence ahead of the first reach class",
     _literal(RULES, "and there are four answers.",
              "and there are four answers, which is what K-26 are.")),

    # The same sentence with `that` in lower case, written mid-sentence. A membership
    # sentence read in one capitalization of each word alone passes it over, so the
    # section reads as agreeing with the registry just as above.
    ("K-119", "a lower-case 'that is what' membership sentence ahead of the first class",
     _literal(RULES, "and there are four answers.",
              "and there are four answers; that is what K-26 are.")),

    # A membership sentence between a class's lead and its bold name. The class still
    # opens, so a region read from past the name alone passes over the sentence and the
    # rule it names stays placed once by its own class, the section reading as agreeing
    # with the registry while the total class names a second list.
    ("K-119", "a membership sentence between a class's lead and its name",
     _literal(RULES, "Where the set is **total**,",
              "Where the set is made of rules which is what K-26 are, and **total**,")),

    # A membership sentence set in underscore italics ahead of the first class. A reading
    # that takes the strict form alone passes it over, the underscore standing where its
    # word boundary should, so the section reads as agreeing with the registry while it
    # names a list no class reads.
    ("K-119", "a membership sentence in underscore italics ahead of the first class",
     _literal(RULES, "and there are four answers.",
              "and there are four answers, _which is what K-26 are_.")),

    # A membership sentence ahead of the first class again, its first id struck through,
    # the registry's own markup for an id. A finder crossing only whitespace, emphasis, a
    # backtick or a bracket on the way to the id passes it over, so the section reads as
    # agreeing with the registry while it names a list no class reads.
    ("K-119", "a membership sentence whose first id is struck through",
     _literal(RULES, "and there are four answers.",
              "and there are four answers, which is what ~~K-26~~ are.")),

    # The same inside the pattern class's region, its list in a code span. The class
    # still reads its own sentence, so a reading that takes the strict form alone finds
    # exactly one there and passes this second list over.
    ("K-119", "a membership sentence listing its rule in a code span",
     _literal(RULES, "Where the set is **total**,",
              "The marker rules, which is what `K-26` are, come next. "
              "Where the set is **total**,")),

    # Seeded on the plan's side, which is the direction the defect arrives from: a
    # completion note is edited far more often than the index over it. The word alone
    # moves and its bullets stay, which is exactly what a finding added to a note
    # without the count following it looks like, and it is why the block's size is
    # counted from the bullets rather than read off the word. Nothing else opens this
    # bullet: it carries no figure, no id, no citation and no table cell, so the case
    # passes on K-82's own report with no collateral.
    ("K-82", "a completion note whose declared count is not the number of findings "
             "beneath it",
     _literal(LOG, "  * Six findings.\n    * **The discharge needed no mechanism",
              "  * Seven findings.\n    * **The discharge needed no mechanism")),

    # The third side of the relation, which neither case above reaches: the notes live
    # in the completion log from S10b and K-82 holds that log's entries total against
    # the plan's landed items. A landed item whose entry is gone is what a landing that
    # forgot its note, or a move that lost one, looks like, and no other rule sees it
    # once the cell's link goes with the heading.
    ("K-82", "a landed item the completion log carries no entry for", _k82_entry),

    # One rule gets one case, and this rule gets two, because the pairing fails from
    # two sides and neither case reaches the other: with the resolution half deleted
    # the mutant above is still killed, so a rule narrowed to the count word would
    # pass its own selftest. The raising item is respelled to one the plan does not
    # carry, which is what a split or a strike leaves behind, and it fires both
    # readings at once, the item resolving against nothing and its note's one counted
    # finding losing the entry that indexed it.
    ("K-82", "a register entry raised at an item the plan does not carry",
     _literal(FINDINGS, "· Raised: I11", "· Raised: I12")),

    # The plan's side of the move K-82 holds from the log's: a landed item keeps one
    # summary line and its link, so a line of the note left standing under it is the
    # defect. Two cases, because the shape and the link fail apart: the first nests a
    # note line under the summary, and the second points a summary at another item's
    # entry, which K-12 still resolves and only this rule reads.
    ("K-113", "a landed item keeping a note line under its summary",
     _literal(PLAN, "is M0.8c's to close. ([note](completion-log.md#s1-discharge-the-owed-"
                    "register-acts))\n",
              "is M0.8c's to close. ([note](completion-log.md#s1-discharge-the-owed-"
              "register-acts))\n    * Exit evidence left behind by the move.\n")),

    ("K-113", "a landed item's summary linking another item's entry",
     _literal(PLAN, "([note](completion-log.md#s2-adopt-the-two-tier-landing-rule-and-"
                    "hold-it-by-rule))",
              "([note](completion-log.md#s1-discharge-the-owed-register-acts))")),

    # The elision table is made to claim a kind the packet meets, which fires three of
    # the rule's readings at once: the moved kind is now in both §9 tables, the kind it
    # displaced is in neither, and the elision table no longer names the set the packet
    # view actually drops. The anchor carries the whole row rather than its first cell,
    # and that is the case rather than a style: §4's schema table writes the same first
    # cell, it comes first in the document, and `replace_once` takes the first
    # occurrence, so a short anchor would seed the schema instead of the elision table.
    ("K-85", "an elision table naming a record kind the meeting table also carries",
     _literal(CORPUS_DOC,
              "| `T` | `rvfi_trap` is a boolean where the record carries the cause |",
              "| `X` | `rvfi_trap` is a boolean where the record carries the cause |")),

    # One rule gets one case, and this rule gets two, because the split is written on
    # both sides and the case above reaches only the document's: with the code half
    # deleted that mutant is still killed, so a rule narrowed to holding the two tables
    # against each other would pass its own selftest while the projection an executor is
    # compared through stopped emitting a record §9.2 goes on describing one for one.
    # The seed is a copy-paste slip in the projection's own pair of effect kinds, which
    # leaves the module importable and every other rule silent, so the case passes on
    # K-85's own report.
    ("K-85", "a projection that has stopped emitting a record the meeting table claims",
     _literal("tools/vos/rvfi.py",
              '("W", packet.mem_wmask, packet.mem_wdata)',
              '("R", packet.mem_wmask, packet.mem_wdata)')),

    # The whole of the defect and nothing else: one token of a generated artifact
    # edited by hand. The anchor is the bundle's own `embedding` field rather than
    # anything it describes, and that is the case rather than tidiness. Every other
    # token in the file is a fact some rule downstream reads, so seeding one would fire
    # that rule as well and leave this case passing on a mutant about the capability
    # format; this field is read by the bundle's own reader and by nothing else, so what
    # is being asked is exactly *does anything notice a generated file that was
    # edited*. It is also the seed the repair lane takes: the working tree moves off the
    # staged blob while the staged blob is still the model's, which is the one state in
    # which --fix may write the bytes back.
    ("K-88", "a generated artifact edited by hand, one token off the bytes its "
             "generator wrote",
     _literal(BUNDLE, '"embedding":"plain"', '"embedding":"plane"')),

    # A second case for K-88, because the rule's two lanes are two readings and a case
    # seeded at one proves nothing about the other. The case above moves a *guest* row's
    # artifact off the blob the index holds, which is the whole of what a lane with no
    # emitter can decide. This one moves a *host* row's artifact off what its generator
    # would write now, which is the stronger claim and the one the host lane exists to
    # make: the generator runs at the gate, so the comparison is against the bytes
    # rather than against the last commit of them.
    #
    # The constructor name is the anchor for the reason `embedding` is the other one:
    # `dialect.py` reads a row's word, its mask and its slots and never its constructor,
    # so seeding it changes what this rule decides and what no other rule reads.
    ("K-88", "a host-lane generated artifact one token off what its generator writes",
     _literal(DIALECT_TABLE, '"ctor": "RTYPE"', '"ctor": "RTYPEX"')),

    # A third case for K-88, and what it adds is not a reading: it is that the *second*
    # host row is live. The reading is the one above, so by the rule this file otherwise
    # keeps, one case per reading, this case would not be written. It is written because
    # what makes a row decide anything is the table rather than the code over it, and a
    # row nothing ever seeds is a row that can be misconfigured and still report green
    # at every run, which is the shape this repository names a check that decides
    # nothing. Registry coverage cannot see it either, being by rule.
    #
    # The seed is the ROM region's `executable` bit, hand-written into the generated map
    # against the composition that owns it: a map granting a permission its composition
    # withholds is the defect a generated artifact held against its last commit rather
    # than against its generator would carry, and this row's whole point is that it is
    # held against the generator. The anchor is the whole PMA quadruple because
    # `executable: 1'b0` is written at two regions and the leading one is the ROM's only
    # by the composition's order.
    ("K-88", "a second host row's generated artifact granting a permission its "
             "composition withholds",
     _literal(SOC_MAP,
              "io: 1'b1, executable: 1'b0, readable: 1'b1, writable: 1'b0",
              "io: 1'b1, executable: 1'b1, readable: 1'b1, writable: 1'b0")),
    # A fourth case for K-88, for the third host row and for the reason the third case
    # states: a row nothing seeds is a row that can be misconfigured and report green.
    # The seed is the second class's fetch constant in the memory plan's export, moved
    # one unit off what the proof file declares, which is the plan's own over-margin
    # variant written into the generated artifact by hand: a placement search reading
    # it would price every second-class region one unit dearer than the proof gate
    # admits, and every other rule reads nothing out of this file.
    ("K-88", "a third host row's generated artifact declaring a fetch constant its "
             "proof file does not",
     _literal(MEMORY_PLAN, '"second_fetch": 15', '"second_fetch": 16')),
    ("K-88", "the calibration view accepts a populated manifest its schema does not",
     _literal("docs/hardware/calibration-manifest.md",
              "This unpopulated schema", "This populated schema")),
    ("K-88", "a supervisor acknowledgment field aliases the publication sequence",
     _literal("supervisor/include/vos_context_layout.h",
              "#define VOS_CTX_ACK_STATUS 1U", "#define VOS_CTX_ACK_STATUS 0U")),
    ("K-88", "a calibration field class outside the declared vocabulary",
     _literal("interfaces/calibration-schema.json",
              '"id": "sensor-trim"', '"id": "authority-trim"')),
    ("K-88", "the wire-format view claiming a descriptor the inventory lacks",
     _literal("docs/assurance/wire-format-inventory.md",
              "Every Narcissus descriptor is absent", "Every Narcissus descriptor is present")),
    ("K-88", "the wire-format inventory silently promoting an absent descriptor",
     _literal("interfaces/wire-formats.json",
              '"descriptor": "absent"', '"descriptor": "present"')),
    ("K-88", "a generated device-register accessor shifts another field",
     _literal("proofs/DeviceRegisters.v",
              "N.shiftr word 32", "N.shiftr word 31")),
    ("K-88", "the device-register RTL constants disagree with their declaration",
     _literal("rtl/generated/device_registers_pkg.sv",
              "TRNG_HEALTH_COMPLETE_SHIFT = 32", "TRNG_HEALTH_COMPLETE_SHIFT = 31")),
    ("K-88", "a generated pool trace grants wider authority than its producer",
     _literal("proofs/ElasticPoolCampaign.v",
              "Grant 1 0 64 (chunk_cap 64 16)", "Grant 1 0 64 (chunk_cap 64 32)")),
    # The staged signature streams' own bytes are untouched here: the source they were
    # compiled from changes, which only the manifest's recorded source digests can see.
    ("K-88", "a signature adapter inverted after its staged streams were compiled",
     _literal("firmware/crypto/signature_target.c",
              "  return accepted ? 0 : 1;", "  return accepted ? 1 : 0;")),
    ("K-88", "a Fiat inclusion header changed after the recorded emission",
     _literal("tools/generated/fiat-crypto/25519_32.h",
              "static void fiat_25519_carry_mul", "static void fiat_25519_carry_mul_changed")),
    ("K-88", "the second Fiat field header changed after emission",
     _literal("tools/generated/fiat-crypto/p256_32.h",
              "static void fiat_p256_mul(", "static void fiat_p256_mul_changed(")),
    ("K-88", "the Fiat receipt no longer enumerates its source archives",
     _literal("tools/generated/fiat-crypto/manifest.json", '"sources": [', '"lost_sources": [')),
    ("K-88", "the Fiat wrapper changed without regenerating its emission",
     _literal("tools/fiat_crypto_emit.py", "Inclusion wrapper added by VerifiedOS",
              "Inclusion wrapper revised by VerifiedOS")),
    # The device-register package's guest row, seeded at its recorded owner commit with
    # the first digit changed, so the index, the licence record and every restating
    # sentence still agree. The row keeps the header out of K-81's window, so no other
    # rule reads the stamp. Sandboxes share one index, so the seed also moves the working
    # tree off the staged blob; the row's unit case isolates the gitlink comparison. The
    # anchor is the line's own words, so a pin advance does not unseed it.
    ("K-88", "a device-register package recording an owner commit the Mocha gitlink "
             "does not carry",
     _first_match("rtl/vos_device_regs_pkg.sv",
                  r"^(// UART owner revision: upstream/mocha at )([0-9a-f])",
                  lambda m: m[1] + ("1" if m[2] != "1" else "2"))),
    # The same row's block half, seeded at its owner rather than at the package: the
    # contract's ACK offset moves and the package still agrees with its index and its
    # gitlink, so only the host's rendering of the package from its block owners can
    # see it.
    ("K-88", "a block-contract register offset moved without regenerating the "
             "device-register package",
     _literal("interfaces/block-device-contract.md", "| `0x38` | `ACK` |",
              "| `0x40` | `ACK` |")),
    # The same row's bytes outside every constant, seeded at the generator: its header
    # comment changes while the package still agrees with its index, its gitlink and its
    # block owners, so only the host's rendering of the whole package can see it.
    ("K-88", "the device-register generator's header changed without regenerating "
             "the package",
     _literal("tools/vos/device_regs.py",
              "from the owners below; rtl devicescheck checks it.",
              "from the owners below.")),
    # The *emitter* is edited rather than a configuration, because that is the direction
    # this defect arrives from: a window is declared once and a node for it is written
    # once, and what goes wrong afterwards is the node, either never written or written
    # about the wrong window. Both of the live findings this rule opened on were of the
    # first kind, an aperture with a validator clause and no node at all; the seed is
    # the second kind because it is the one a reader cannot see, the tree still carrying
    # a node per device and one of them naming a neighbour's address.
    #
    # Seeding a *configuration* instead would put the defect in the file K-65 already
    # reads, so the case would pass on somebody else's report; seeding the validator
    # would seed the half the composition-time run already refuses out loud.
    ("K-94", "a devicetree node stating a neighbouring window instead of its own",
     _literal("model/model/postlude/device_tree.sail",
              "generate_dts_reg(plat_uart_base, plat_uart_size)",
              "generate_dts_reg(plat_blkdev_base, plat_uart_size)")),
    # The other generated artifact, and the seed is in its *boilerplate* rather than in
    # a declared constant or a register token. Every constant the file carries is a
    # value the declaration fixes and every enumeration member is the register's, so an
    # anchor on either would rot the day a composition is re-priced or an entry gains a
    # member, which is work that never touched this rule. The width rule is the one
    # block the emitter writes identically whatever its owners say, it is what IDL-023
    # fixes, and narrowing it is the silent defect: a generated file whose one
    # admissible length form has quietly become two still compiles, still passes the
    # proof gate, and is no longer what its generator writes.
    # The *Gallina* side is seeded rather than the Sail one, because that is the side
    # this repository authored second and the side whose gate says least about the pair:
    # a byte moved here still compiles, still proves its own `Example` against itself,
    # and still passes every proof gate, where the Sail literal at least sits beside a
    # harness a model build runs. One byte of one lane, so what the case exercises is the
    # lane-by-lane comparison rather than a length or a parse.
    ("K-91", "a known answer one byte off in the Gallina transcription of FIPS 202",
     _literal(KECCAK_GALLINA, "0x17 :: 0x86 :: 0xA7 :: 0xB9", "0x17 :: 0x86 :: 0xA7 :: 0xBA")),

    # Two cases rather than one, because the rule reads two shapes on each side and
    # neither defect reaches the other's. The S-box seed moves a byte of a Gallina
    # `Example` against a Sail vector literal, which is the shape K-91 already has one
    # object over; the sigma seed moves a member of a Gallina `Definition`'s list against
    # four model functions read in that list's own grouping, taking only the amounts the
    # model spells as rotations rather than as shifts.
    # Both seeds are on the *Gallina* side, and neither is a defect nothing else could
    # see: each breaks the `Example` that states it and the Coq gate would refuse it. What
    # makes them cases for this rule is that no gate which would refuse them runs on the
    # host lane, which is the lane this rule is for and the only one CI has. Seeding the
    # model's side instead would put the write under the `-text` tree, where the whole
    # point of a one-token mutation is lost to a line-ending sweep.
    ("K-107", "a published S-box byte off by one in the Gallina derivation of FIPS 197",
     _literal(AESGCM_GALLINA, "0x63 :: 0x7C :: 0x77 :: 0x7B", "0x63 :: 0x7C :: 0x77 :: 0x7A")),

    ("K-107", "a SHA-256 sigma rotation amount the model and the reference now spell apart",
     _literal(SHA256_GALLINA, "7 :: 18 :: 17 :: 19 :: nil", "7 :: 18 :: 17 :: 20 :: nil")),

    ("K-89", "a generated interface artifact whose width rule was narrowed by hand",
     _literal(RING_ARTIFACT,
              "if Nat.leb cases 256 then 1 else if Nat.leb cases 65536 then 2 else 4.",
              "if Nat.leb cases 255 then 1 else if Nat.leb cases 65536 then 2 else 4.")),

    # The same file from the other side, and the seed is in the *profile* rather than in
    # the artifact, because that is the whole of what separates this rule from the one
    # above: K-89 re-emits and compares bytes, so it is satisfied by an artifact that
    # agrees with the declaration and the register whatever §4.2 has come to say. One
    # member leaves the row that places it, the encoder goes on spending a declared width
    # on it, and the row still renders, keeps its width, cites the same requirement and
    # moves no count, so no table, link, citation or count rule reads the edit.
    ("K-99", "a wire-format row that stopped carrying a member the emitter encodes",
     _literal(IDL_PROFILE,
              "plus offset, length, direction, and declared content type",
              "plus offset, length, and declared content type")),

    # One rule gets one case and this one gets two, because the reading above is a
    # membership and the reading here is the recomputation: with the ladder half deleted
    # the case above is still killed, so a rule narrowed to the pairings would pass its
    # own selftest while the width rule the emitter writes as a literal drifted from the
    # entry that fixes it. The seed moves the *criterion's* restatement of the ceiling and
    # leaves the two statements of the rungs standing, which is the drift that reads as
    # an editorial change: the entry goes on stating one ladder, and it now names a top
    # rung its own rungs do not reach.
    ("K-99", "a width ladder whose stated ceiling is not the top rung it states",
     _literal(IDL_PROFILE, "its four-byte ceiling", "its two-byte ceiling")),

    # The lane's fact table names a function of `env.py` as what wants ccache, and the
    # seed renames that function where it is defined. That is the direction the drift
    # arrives from and the reason it is silent: nobody edits a table of facts to follow a
    # refactor of the module it points at, the rename is local, every caller moves with
    # it, both type checkers stay clean, and the row goes on naming a consumer this tree
    # no longer has. The provisioner is not seeded, being imported here rather than read
    # off the sandbox, which is what makes the artifact side the one a case can move.
    ("K-100", "a lane fact naming a consumer the module it points at has renamed",
     _k100),

    # The *template* is seeded rather than a shipped composition, and it is the only seed
    # that isolates this reading. `memory.regions` is in neither non-primary file's
    # declared divergence set and a list is compared whole, so an `executable` flipped in
    # any of the three is K-65's finding as well; flipped in the primary it is K-88's too,
    # the SoC map package being generated from that file's regions. The template is read
    # by this rule and, for another key entirely, by K-57, so a device region made
    # executable there is a defect exactly one rule reads.
    #
    # It is also the direction the defect arrives from, which is why the rule takes the
    # template in at all: it is what every generated test-matrix configuration is
    # configured from and the copy no `*.json` reading and no dialect loader reaches, so
    # an attribute changed here reaches a built emulator through a file nothing else
    # opens. The first `"executable": false` in it is the ROM region's, which is typed
    # IOMemory, so the literal is unambiguous and the substitution declares a device
    # endpoint fetchable.
    ("K-101", "a device region the configuration template declares executable",
     _literal("model/config/config.json.in",
              '"executable": false', '"executable": true')),

    # A transposition rather than an invented id, because that is the shape the defect
    # actually takes: a header sentence is written from memory about an entry that turns
    # out to be numbered something else, and the result renders as a citation, compiles,
    # and passes the assumption gate. `proofs/` carries no Markdown, so no other rule
    # reads the edit at all: K-11 resolves ids in documents and K-63 reads `model/` by
    # kind, which is what makes this one rule's finding and nobody else's. The seed is in
    # a header comment because that is where the artifacts argue from the register, and
    # it moves no count, no link and no anchor.
    ("K-103", "a proof artifact citing a requirement id with two digits transposed",
     _literal(SEAM_WITNESSES, "the R-05-165 / R-05-166 discipline",
              "the R-05-165 / R-05-616 discipline")),

    # The adapter's generated exception code is edited without moving its Sail owner.
    # This reaches generation rather than the capability-format rule's width surface.
    ("K-104", "a generated capability exception code changed in the RTL adapter",
     _literal("rtl/vos_cva6_cheri_pkg.sv", "CAP_EXCEPTION = 28;", "CAP_EXCEPTION = 29;")),

    # An extra BEGIN inside the header makes the exclusion unbalanced. Read the marker
    # from its owner so a respelling cannot turn the case into an unrelated parse fault.
    ("K-108", "a derived region opened in a proof artifact and never closed",
     _literal(SEAM_WITNESSES, "   SeamWitnesses.v\n",
              f"   SeamWitnesses.v\n\n   {DERIVED_BEGIN}\n")),
    ("K-109", "a generated proof header changing its owner's fingerprint", _k109),
    ("K-110", "the shared agent instructions deleted from the tracked source",
     lambda box: box.delete("AGENTS.md")),
    # A validation record resting a result on an interim's verdict, which is the consumer
    # R-05-022 enters when it is admitted and a hand-kept list forgets. The campaign is
    # an anchor the rule already declares no premise, for its two lines saying no libcrux
    # or HACL* body is copied and the comparison runs against OpenSSL, and the sentence
    # lands on a line no declared fragment names: a rule that classified by anchor
    # rather than by line would pass it. The
    # names are escaped as the prose writes them, so no Markdown or link rule reads the
    # edit and the verdict is K-114's alone.
    ("K-114", "a declared proof campaign resting a result on libcrux's F* proof",
     _literal("proofs/campaigns/mldsa-reference.md",
              "carries no authorization for deterministic production signing.",
              "carries no authorization for deterministic production signing. Its "
              "signing path's functional correctness rests on libcrux's verified "
              "ML-DSA, whose F\\* proof this campaign takes as its premise.")),
    # The rewrite a modernizing lane makes: a two-branch match in a proof source turned
    # into Rocq 9.3's `if … is`, which the gate accepts and the Wasm oracle's Rocq 9.1.1
    # cannot parse. EndpointIPC.v is the source that stays compiled at an older release
    # whichever other instruments move, so the case outlives them.
    ("K-117", "a proof source the Wasm oracle compiles rewritten into Rocq 9.3's "
              "`if … is`",
     _literal("proofs/EndpointIPC.v", "  match l with nil => d | cons x _ => x end.",
              "  if l is cons x _ then x else d.")),
    ("K-117", "the Rupicola lowering's switch constant renamed out from under the "
              "instrument table", _k117_switch),
    ("K-117", "compare_component.py's release constant renamed out from under the "
              "instrument table", _k117_release),
    # An instrument moved to an older switch while its row still states the gate's: the
    # kernel's vectors asked of the CertiRocq switch at Rocq 9.1.1. Nothing its harness
    # compiles writes a 9.3 form today, so only the reading of what kernel.py asks for
    # can see that the set no longer follows the instrument.
    ("K-117", "the kernel's vector harness moved to the CertiRocq switch under a row "
              "stating the gate's",
     _literal("tools/vos/cli/kernel.py", "found = gallina.prover(gallina.VECTOR_SWITCH)",
              "found = gallina.prover(gallina.ORACLE_SWITCH)")),
    # A discharge annotation above a `Definition`, which is the one of this rule's four
    # refusals that renders perfectly and reads as correct: the annotation parses, its id
    # is live, and what it claims is that a *term* answers an obligation. The other three
    # read as typos to anyone who looks at the line, and this one does not, so it is the
    # case worth having.
    #
    # The id it claims is one the file already cites, and that is what isolates the rule.
    # An annotation is ordinary text in the artifact, so its ids reach K-103's citation
    # scan and the ledger's cited set alike: an id the file does not already carry would
    # add a ledger row and fire K-106 as well, and a dead one would fire K-103. Reusing a
    # live id the header already argues from moves exactly one rule's verdict.
    ("K-105", "a discharge annotation claiming an entry above a term rather than a "
              "statement",
     _literal(SEAM_WITNESSES, "Definition refutes_seam_ni_timing",
              "(*| discharges: R-05-160 |*)\nDefinition refutes_seam_ni_timing")),

    # The generated ledger promoted by hand: one row's claim column moved from `cited` to
    # `claimed` with no annotation anywhere to back it. That is the direction this defect
    # arrives from, a burn-down being a table somebody wants to tick off, and the claim
    # column is the only cell whose edit still renders as a true-looking row, the other
    # three being join keys. Nothing else in the tool reads this file, so the verdict is
    # one rule's. It is also the repair lane's seed for the same rule.
    ("K-106", "a generated ledger row hand-promoted from cited to claimed",
     _literal(PROOF_LEDGER, "| n/a | cited |", "| n/a | claimed |")),
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
# purpose. Seven seeds are the rules' own case mutants, each an arithmetic figure whose
# repair writes the pristine bytes back. Two rules cannot ride their own case. K-54's
# moves the granule owner, and repairing from a moved owner rewrites every derived
# figure to the new granule and dirties co-read pairs no --fix may bless, so the
# after-check could never pass. K-57's two both seed a site that is *not* repaired, one
# under a `-text` tree and one the register's own normative statement, so neither would
# reach a `fixed:` line. Each takes a seed here instead, moving one derived figure in
# the exact document bytes a case would anchor on, and the repair restores the tree it
# found.
REPAIRABLE: dict[str, tuple[str, Mutation]] = {
    "K-24": ("fc-conferrals", _case_mutation("K-24")),
    "K-28": (f"Coverage {SEC}", _case_mutation("K-28")),
    "K-32": ("product:", _case_mutation("K-32")),
    "K-36": (" subtotal:", _case_mutation("K-36")),
    "K-37": ("estimate summary", _case_mutation("K-37")),
    "K-96": ("calibration results", _renumber(
        PLAN, r"(?m)^\| attended \| I \| (\d+) \|", 1, "9999")),
    "K-54": ("the tag plane's", _literal(
        REGISTER, "granule is 15.6 MB per GB of data",
        "granule is 99.9 MB per GB of data")),
    "K-57": ("the block's candidate set", _literal(
        GEOMETRY, "**the block is 32, 64, 128, 256, or 512 bytes**",
        "**the block is 32, 64, 128, or 256 bytes**")),
    "K-69": ("kernel-line-budget", _case_mutation("K-69")),
    # A standing rather than a figure, and it rides its own case: the repair writes the
    # inventory's class back over the cell a hand promoted.
    "K-95": ("standing", _case_mutation("K-95")),
    # A third that cannot ride its own case, and for the plainest reason: neither of
    # K-82's cases is an arithmetic figure. One moves a count word in the plan and the
    # other an item id in the register, and repairing either would mean writing a
    # finding or a note, so neither reaches a `fixed:` line. The seed instead moves the
    # one figure the rule does rewrite, the register's own size, in the sentence that
    # states it beside the item count, and it computes that figure rather than pinning
    # it: the number moves whenever an item lands a finding, so a literal would go stale
    # on work that never touched the rule.
    "K-82": ("findings the plan records", _k82_figure),
    # The one repair here that is not a figure at all. K-88's own case is already the
    # state its repair is for, a working tree one token off a staged blob that is still
    # the model's, so it rides it: what is proved is that --fix writes a whole generated
    # file back from the index rather than that it recomputes an arithmetic.
    "K-88": ("restored from the index", _case_mutation("K-88")),
    # The second that is not a figure, and it rides its own case for the reason K-88's
    # does: a hand-promoted ledger row is already the state its repair is for, and what
    # the lane proves is that --fix writes the whole artifact from its generator rather
    # than that it recomputes an arithmetic in place.
    "K-106": ("ledger row", _case_mutation("K-106")),
    "K-109": ("generated requirement header", _case_mutation("K-109")),
    "K-104": ("generated capability exceptions", _case_mutation("K-104")),
}


# =====================================================================================
# run
# =====================================================================================


def _select_cases(rule: str | None, shard: Shard | None,
                  repair_only: bool = False) -> list[Case]:
    if repair_only:
        if rule is not None or shard is not None:
            raise ValueError("--repair-only cannot be combined with --rule or --shard")
        return []
    if shard is not None:
        if rule is not None:
            raise ValueError("--rule cannot be combined with --shard")
        return shard.select(CASES)
    selected = [c for c in CASES if rule is None or c[0] == rule]
    if not selected:
        raise ValueError(f"no case for rule '{rule}'")
    return selected


def _needs_repair(selected: list[Case], shard: Shard | None,
                  repair_only: bool = False) -> bool:
    # The repair exercises all repairable rules together, so no partition of the cases
    # runs it, whichever of them it holds: --repair-only runs it instead, and the
    # shards of one count and that run together are the unsharded run.
    if repair_only:
        return True
    if shard is not None:
        return False
    return any(rule in REPAIRABLE for rule, _, _ in selected)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed each checker rule a defect it must report.")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--rule", help="run one rule's case only")
    selection.add_argument("--shard", type=sharding.parse, metavar="INDEX/TOTAL",
                           help="run a disjoint partition of cases, without the repair path, "
                                "which --repair-only runs")
    selection.add_argument("--repair-only", action="store_true",
                           help="run the repair path beside the unmutated baseline, and no case")
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
    try:
        selected = _select_cases(args.rule, args.shard, args.repair_only)
    except ValueError as err:
        parser.error(str(err))
    if args.shard is not None:
        print(f"shard {args.shard}: {len(selected)} of {len(CASES)} cases; "
              "every shard and --repair-only must pass")
    if args.repair_only:
        print(f"repair path only: 0 of {len(CASES)} cases")
    # Phase and case seconds for the gate's summary, never printed; claimed before any
    # child starts, so no checker run inherits the file.
    record, clock = timings.claim(), timings.Clock()

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
    jobs = max(1, min(args.jobs, len(selected)))
    # Placement overlaps file writes rather than checker runs, so a run selecting no
    # case, the repair path's alone, still places its template and first sandbox
    # across --jobs workers.
    width = jobs if selected else max(1, args.jobs)

    # One sandbox per worker, and one more the repair path keeps to itself so that its
    # five runs go beside the cases rather than after them. Where the lane never runs,
    # under a shard or when no selected rule carries a --fix branch, the extra sandbox
    # is stood up cheap, as links, and joins the case queue instead of holding real
    # copies for nothing.
    repairable = _needs_repair(selected, args.shard, args.repair_only)
    made: list[Sandbox] = []
    print(f"building {jobs + 1} sandbox(es) at {sandbox}")
    template = sandbox / "template"
    with clock.timing("phase", "template"):
        copied, carried = build_template(repo, template, width)
    print(f"placed {copied} file(s), {carried} carried from the previous run, "
          "indexed as the baseline")
    print()

    try:
        # The baseline needs one sandbox and nothing else, so only the first is stood
        # up before it, using the available setup workers across its directories.
        # The rest land while the baseline runs, one worker per sandbox, each joining
        # the queue as it does, and the case wave draws them out as they arrive.
        with clock.timing("phase", "first sandbox"):
            made.append(stand_up(template, sandbox / "w0", jobs=width))
        boxes: Queue[Sandbox] = Queue()
        with ThreadPoolExecutor(max_workers=jobs) as setup:
            def later(i: int) -> Sandbox:
                box = stand_up(template, sandbox / f"w{i}", fix_ok=repairable and i == jobs)
                made.append(box)
                if not box.fix_ok:
                    boxes.put(box)
                return box

            standing = [setup.submit(later, i) for i in range(1, jobs + 1)]
            code = _run(selected, made[0], boxes, standing[-1], jobs, repairable, clock,
                        sharded=args.shard is not None, repair_only=args.repair_only)
            for future in standing:
                future.result()   # a sandbox that failed to stand up is loud, not lost
        return code
    finally:
        started = time.perf_counter()
        if args.keep:
            print(f"sandboxes kept at {sandbox}")
        else:
            # the template leaves for the cache before the estate is deleted, and the
            # estate is deleted the way it was built, the parent last
            _publish(template, _cache_root(repo))
            _across(remove_tree, [box.path for box in made], jobs + 1)
            remove_tree(sandbox)
        clock.add("phase", "teardown", time.perf_counter() - started)
        timings.write(record, clock.units())


def _verdict(case: Case, box: Sandbox) -> Verdict:
    """One case, run against a sandbox of its own: the whole of this oracle.

    A case passes when its own rule is among those the checker reported, so the kill
    states which rules fired rather than only that one did: a mutant that trips its
    neighbours as well is expected, and a reader who cannot see which ones cannot tell
    that from a mutant that tripped only a neighbour.

    The run stops after the group that decides the case's rule. A group reads only
    what earlier groups computed, so that verdict is the whole run's, and a kill names
    the rules that fired up to it. A survivor is run again whole, so its report names
    every rule that fired and every exit a full run gives; a hang is not run twice.
    """
    rule, what, apply = case
    seeded = Seeding(rule, what)
    if not apply(box):
        return Verdict(seeded, UNSEEDED,
                       "the mutant will not apply; the document it seeds has moved")
    code, out, failed = box.check(through=rule)
    if rule not in failed and out != [OVERRAN]:
        code, _, failed = box.check()
    if rule in failed:
        return Verdict(seeded, KILLED, f"the checker reported {', '.join(failed)}")
    # a run that reported nothing and a run that died before reporting look the same
    # from the rule's side and are repaired differently, so the exit code is stated
    how = (f"other rules fired: {', '.join(failed)}" if failed
           else "the run was green" if code == 0
           else f"the run exited {code} with no finding, so the checker did not "
                "survive the mutant either")
    return Verdict(seeded, SURVIVED, how)


def _run(selected: list[Case], first: Sandbox, boxes: Queue[Sandbox],
         repair_ready: Future[Sandbox], jobs: int, repairable: bool | None = None,
         clock: timings.Clock | None = None, *, sharded: bool = False,
         repair_only: bool = False) -> int:
    if repair_only and (selected or repairable is False):
        raise ValueError("--repair-only runs the repair path and no case")
    measured = clock or timings.Clock()

    def one(case: Case) -> Verdict:
        box = boxes.get()
        started = time.perf_counter()
        try:
            return _verdict(case, box)
        finally:
            box.reset()
            boxes.put(box)
            measured.add("case", f"{case[0]}: {case[1]}", time.perf_counter() - started)

    def timed_repair() -> tuple[list[str], list[str]]:
        with measured.timing("phase", "repair path"):
            return _repair_path(repair_ready)

    # The repair path is five more whole runs of the checker in sequence, the longest
    # chain a run holds, and depends on nothing the baseline or a case does, so it
    # starts first, beside both, on the sandbox held back for it, and reports where it
    # has always reported: after the cases. Under --rule it runs only when a selected
    # rule carries a --fix branch, because for any other rule it is most of the
    # iteration path's cost and proves nothing about the rule being iterated on. No
    # shard runs it; --repair-only runs it beside the baseline alone.
    if repairable is None:
        repairable = repair_only or any(rule in REPAIRABLE for rule, _, _ in selected)
    with ThreadPoolExecutor(max_workers=jobs + 1) as pool:
        repairing = pool.submit(timed_repair) if repairable else None

        # Nothing below means anything against a sandbox that was already failing: a
        # mutant would be reported killed by whatever was broken before it was
        # introduced. That verdict discards the repair path's report, and leaving the
        # pool still waits for it, so no checker is running when the estate is removed.
        with measured.timing("phase", "baseline"):
            code, out, _ = first.check()
        if code != 0:
            print("FAIL: the unmutated sandbox does not pass, so no case can decide anything:")
            showing = False
            for line in out:
                if line.lstrip().startswith("FAIL"):
                    showing = True
                elif not line.startswith("       "):
                    showing = False
                if showing:
                    print(f"  {line}")
            return 1
        print("ok: the unmutated sandbox passes, so every finding below is the mutant")
        print()
        boxes.put(first)

        with measured.timing("phase", "cases"):
            verdicts = list(pool.map(one, selected))
        repair: list[str] = []
        repair_out = ["--- the repair path ---",
                      "  skipped: this selection does not own the repair path"]
        if repairing is not None:
            repair, repair_out = repairing.result()

    # The cases' whole report and their own exit code, on the shape every mutation loop
    # here shares. Two things stay this tool's, because neither is about a mutant: the
    # repair path, which decides about --fix, and the registry coverage, which decides
    # about the rule registry and reads `CASES` rather than the run. Their findings are
    # OR'd in below, which is what the hand-rolled tally did. --repair-only selects no
    # case, so it has no population to report; any other run summarizes its cases, and
    # summarize refuses an empty population as a vacuous pass.
    report: list[str] = []
    cases_code = 0 if repair_only else summarize(report, verdicts, RULES, "checker")
    print(f"--- the mutation cases ---\n  skipped: --repair-only selects none of "
          f"{len(CASES)} case(s)" if repair_only else "\n".join(report))
    print()

    print("\n".join(repair_out))
    print()
    gaps = _registry_coverage(first)
    print()

    beside = len(repair) + len(gaps)
    if cases_code or beside:
        if beside:
            print(f"{beside} further finding(s) beside the cases, above.")
        return 1
    held = ("the repair path holds" if repairable
            else "the repair path is left to --repair-only" if sharded
            else "the repair path had nothing to prove")
    if repair_only:
        print(f"{held} and the registry is covered; --repair-only selects no case, so this "
              "run decides no mutant.")
        return 0
    print(f"every one of {len(verdicts)} rule(s) killed its mutant, {held}, "
          "and the registry is covered.")
    if len(verdicts) < len(CASES):
        # A narrowed run says what it did not decide, and it has to say it here. The
        # coverage check above reads `CASES` rather than the run, so it reports the
        # registry covered however few cases ran, and a green exit under --rule is a
        # green exit about those cases alone.
        print(f"{len(CASES) - len(verdicts)} case(s) were not selected and decided "
              "nothing, so this run is about the selected case(s) alone.")
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


def _header_require(condition: bool, message: str) -> None:
    """A failed corpus assertion is a selftest finding, including under python -O."""
    if not condition:
        raise ValueError(message)


def _header_context(root: Path, *, fix: bool = False) -> Context:
    corpus = corpus_mod.load(root)
    return Context(root=root, corpus=corpus, reg=read_register(corpus),
                   art=read_artifacts(corpus), rep=Reporter(), fix=fix)


def _stale_header_manifest(text: str, rel: str) -> str:
    region = proofcites.derived(text)
    _header_require(not region.faults and len(region.spans) == 1,
                    f"{rel}: the corpus proof does not have one safe manifest: {region.faults}")
    start, stop = region.spans[0]
    prefix, marker, digest = text[start:stop].partition("SHA256: ")
    _header_require(bool(marker) and bool(digest) and digest[0] in "0123456789abcdef",
                    f"{rel}: cannot seed a stale manifest without its fingerprint")
    first = "1" if digest[0] == "0" else "0"
    return text[:start] + prefix + marker + first + digest[1:] + text[stop:]


def _proof_header_repair(box: Sandbox) -> int:
    # The index decides membership; fixture size and proof names follow the corpus.
    # Private copies include the generated ring, which repair must leave untouched.
    root = box.path
    source_corpus = corpus_mod.load(root)
    rels = sorted(rel for rel in source_corpus.tracked if proofcites.is_source(rel))
    authored = set(rels) - proofheaders.EXCLUDED
    _header_require(bool(authored), "an empty proof corpus cannot witness header preservation")
    original = {rel: (root / rel).read_bytes()
                for rel in [REGISTER, *rels, memplan.ARTIFACT]}
    # reset() can relink even a fix-safe lane into its template. Detach the whole
    # subject before calling the repair planner, so an early-write defect cannot
    # change the pristine corpus or another worker's inputs.
    for rel, data in original.items():
        box.touched.add(rel)
        target = root / rel
        target.unlink()
        target.write_bytes(data)
    files = {rel: data.decode("utf-8") for rel, data in original.items()}
    identities = {rel: (set(proofcites.ids(files[rel])), proofs.sentences(files[rel]))
                  for rel in rels}
    row = next(row for row in generated.GENERATED if row.path == memplan.ARTIFACT)

    baseline = _header_context(root)
    changed, faults = proofheaders.plan(root, baseline.reg, rels)
    _header_require(not changed and not faults,
                    f"the indexed proof corpus needs repair before mutation: "
                    f"{sorted(changed)}, {faults}")
    _header_require(not generated._host_row(baseline, row, None).findings,
                    "the original memory-plan export disagrees with its proof")
    for rel in sorted(authored):
        seeded = _stale_header_manifest(files[rel], rel)
        _header_require(seeded != files[rel], f"{rel}: no stale fingerprint was seeded")
        _header_require((set(proofcites.ids(seeded)), proofs.sentences(seeded)) == identities[rel],
                        f"{rel}: the seed changed authored citations or Gallina sentences")
        box.write(rel, seeded)

    before = _header_context(root)
    headers.run(before)
    _header_require(before.rep.findings == len(authored),
                    f"each stale proof needs its own finding: {before.rep.out}")
    _header_require(all(any(f"{rel}: generated requirement header is stale" in line
                            for line in before.rep.out) for rel in authored),
                    f"a stale proof was absent from the findings: {before.rep.out}")

    seeded_bytes = {rel: (root / rel).read_bytes() for rel in original}
    repair = _header_context(root, fix=True)
    generated._host_row(repair, row, None)
    headers.run(repair)
    _header_require(repair.rep.findings == 0,
                    f"the corpus repair refused a stale proof: {repair.rep.out}")
    _header_require(set(repair.fixed) == authored | {memplan.ARTIFACT},
                    f"the repair omitted a proof or crossed ownership: {sorted(repair.fixed)}")
    _header_require(all((root / rel).read_bytes() == data for rel, data in seeded_bytes.items()),
                    "repair planning published bytes before the checker flush")
    for rel, text in repair.fixed.items():
        if rel in authored:
            _header_require((set(proofcites.ids(text)), proofs.sentences(text)) == identities[rel],
                            f"{rel}: repair changed authored citations or Gallina sentences")
        box.write(rel, text)

    _header_require(all((root / rel).read_bytes() == data for rel, data in original.items()),
                    "repair failed to restore exact corpus bytes or changed an excluded owner")
    exported = json.loads((root / memplan.ARTIFACT).read_text(encoding="utf-8"))
    source_md5 = hashlib.md5((root / memplan.SOURCE).read_bytes(),
                            usedforsecurity=False).hexdigest()
    _header_require(exported["header"]["source_md5"] == source_md5,
                    "the dependent export does not bind the repaired source bytes")
    for fix in (False, True):
        after = _header_context(root, fix=fix)
        reading = generated._host_row(after, row, None)
        headers.run(after)
        _header_require(not reading.findings and after.rep.findings == 0,
                        f"the corpus did not converge after one repair: "
                        f"{reading.findings}, {after.rep.out}")
        _header_require(not after.fixed,
                        f"the converged corpus queued another repair: {sorted(after.fixed)}")
    return len(authored)


def _proof_header_repair_path(box: Sandbox) -> tuple[list[str], list[str]]:
    """Exercise the indexed proof corpus once inside the repair lane."""
    out = ["--- the proof-header corpus repair ---"]
    try:
        count = _proof_header_repair(box)
    except (OSError, ValueError, KeyError, RuntimeError) as err:
        problem = f"proof-header corpus: {err}"
        return [problem], [*out, f"  {problem}"]
    finally:
        box.reset()
    return [], [*out, f"  ok: {count} stale manifests detected and repaired; authored "
                "bytes preserved, generated owners untouched, dependent export "
                "current, and the second repair queues nothing"]


def _repair_path(ready: Future[Sandbox]) -> tuple[list[str], list[str]]:
    """--fix rewrites the asserted counts, the Coverage rows, the compounded products,
    the checklist's cells and totals, and the tag-plane figures from their artifacts,
    and on a repository that already agrees it rewrites nothing, so those branches ship
    untested unless something breaks them on purpose. One seed per rule in REPAIRABLE,
    all of them at once, each repair asserted by its own `fixed:` line, and the lane is
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
    if not problems:
        header_problems, header_out = _proof_header_repair_path(box)
        problems.extend(header_problems)
        out.extend(header_out)
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
