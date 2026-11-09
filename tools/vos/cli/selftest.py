#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify that each registered checker rule fires on a seeded defect.

The meta group checks registry-to-code agreement, and the floors group (`K-46` through
`K-48`) rejects empty readings. This harness tests that each rule detects a targeted
mutation in an isolated working-tree sandbox:

- A rule that reports its mutant is `killed` (live).
- A rule that misses its mutant is `survived` (dead surface).
- A case whose mutation no longer modifies the target file is `unseeded` (stale case).

Verdict types, reporting, and exit codes come from [`vos/seeded.py`](../seeded.py).
`CASES` lives here beside the runner and is exempted from `K-83` so its two quarantine
cases can spell the coupling they test.

Each case runs in a parallel worker sandbox hardlinked against a shared template built
from the working tree (with a `.git` pointer to the template's index and pre-warmed
hash-checked bytecode). Writes unlink before writing so mutations never leak into the
shared template.

    tools/run.py selftest                 # every case
    tools/run.py selftest --rule K-23     # one rule
    tools/run.py selftest --keep          # keep sandboxes for inspection

Exit 0 when every case kills its mutant, the repair path holds, and every registered
rule is covered; 1 otherwise.
"""

import argparse
import gzip
import hashlib
import json
import os
import py_compile
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

from vos import checkregistry, memplan, proofcites, proofheaders, proofs, sharding, timings
from vos import corpus as corpus_mod
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

MID = "·"
SEC = "§"


# =====================================================================================
# Sandbox and mutation helpers
# =====================================================================================


class Sandbox:
    """Isolated view of the working tree for running `tools/check.py`.

    Files are hardlinked to `pristine` unless `fix_ok` is set (which copies non-`model/`
    files so `--fix` can rewrite them in place without mutating the shared template).
    `write` and `delete` unlink targets before modifying them.
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
        """Unlink `rel` and write `text`, returning False if `text` is None or unchanged."""
        if text is None:
            return False
        if text == self.read(rel):
            return False
        self.touched.add(rel)
        target = self.path / rel
        # Unlink before writing so hardlinks into the template are never modified in place.
        target.unlink()
        target.write_text(text, encoding="utf-8", newline="")
        return True

    def delete(self, rel: str) -> bool:
        """Delete `rel`, returning False if it did not exist."""
        target = self.path / rel
        if not target.exists():
            return False
        self.touched.add(rel)
        target.unlink(missing_ok=True)
        return True

    def reset(self) -> None:
        """Restore all touched paths from `pristine`."""
        for rel in self.touched:
            source, target = self.pristine / rel, self.path / rel
            target.unlink(missing_ok=True)
            if source.exists():
                _link_or_copy(source, target)
        self.touched.clear()

    def check(self, fix: bool = False,
              through: str | None = None) -> tuple[int, list[str], list[str]]:
        """Run `tools/check.py` in a subprocess and return `(returncode, lines, failed_rule_ids)`."""
        if fix and not self.fix_ok:
            raise SystemExit("--fix rewrites documents in place, which writes through "
                             "this sandbox's hardlinks into the template; it may only "
                             "run on the repair sandbox, which holds real copies")
        # Validate hash-based pycs on every import and pass -B so mutated sources do
        # not write new bytecode through shared links.
        argv = [sys.executable, "--check-hash-based-pycs", "always", "-B", "-c",
            "import sys; sys.path.insert(0, sys.argv.pop(1)); "
            "import check; raise SystemExit(check.main())",
            str((self.path / CHECKER).parent)] + (["--fix"] if fix else []) + (
            ["--through", through] if bool(through) else [])
        try:
            proc = subprocess.run(argv, cwd=self.path, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace",
                                  timeout=CHECK_TIMEOUT, check=False)
        except subprocess.TimeoutExpired:
            return 1, [OVERRAN], []
        out: list[str] = [*(proc.stdout or "").splitlines(),
                          *(proc.stderr or "").splitlines()]
        failed: list[str] = sorted({m.group(1) for line in out
                                    if (m := re.match(rf"\s*FAIL ({checkregistry.ID_PATTERN}):", line))})
        return proc.returncode, out, failed


def remove_tree(path: Path) -> None:
    """Recursively delete `path`, clearing read-only bits on pack files if needed."""
    def force(func: Callable[[str], object], target: str, _exc: BaseException) -> None:
        Path(target).chmod(stat.S_IWRITE)
        func(target)

    if path.exists():
        shutil.rmtree(path, onexc=force)


def _link_or_copy(src: str | Path, dst: str | Path) -> None:
    """Hardlink `src` to `dst`, falling back to `shutil.copy2` across filesystems."""
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _warm_bytecode(template: Path, jobs: int) -> int:
    """Pre-compile checker modules into `CHECKED_HASH` bytecode caches in `template`."""
    sources = [template / CHECKER, *(template / "tools/vos").rglob("*.py")]

    def compile_one(source: Path) -> bool:
        try:
            cached = py_compile.compile(
                str(source), doraise=True, quiet=2,
                invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)
        except OSError, py_compile.PyCompileError:
            return False
        return cached is not None

    return sum(_across(compile_one, sources, jobs))


def stand_up(template: Path, path: Path, fix_ok: bool = False, *, jobs: int = 1) -> Sandbox:
    """Create a worker sandbox at `path` linked against `template`.

    Writes a `.git` gitdir file pointing to `template/.git` so `git ls-files` uses the
    shared index against the sandbox's working tree. When `fix_ok` is True, files
    outside `model/` are copied rather than hardlinked so `--fix` can rewrite them in
    place safely.
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


# Placeholder file inside each submodule directory so links into `upstream/<name>` resolve.
SUBMODULE_STAND_IN = ".selftest-submodule"


def stamp_gitlinks(into: Path, gitlinks: dict[str, str]) -> None:
    """Replace submodule stand-in blobs in `into`'s Git index with mode-`160000` gitlinks."""
    if not gitlinks:
        return
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
    """Map `work` across `items` using up to `jobs` threads, preserving input order."""
    work_list = list(items)
    if jobs == 1 or len(work_list) < 2:
        return [work(item) for item in work_list]
    with ThreadPoolExecutor(max_workers=min(jobs, len(work_list))) as pool:
        return list(pool.map(work, work_list))


def edit_entry(text: str, ident: str, edit: Callable[[str], str | None]) -> str | None:
    """Apply `edit` to the register entry block for `ident`."""
    start = text.find(f"**{ident}** ")
    if start < 0:
        return None
    end = text.find("\n**R-", start + 1)
    if end < 0:
        end = len(text)
    new = edit(text[start:end])
    return None if new is None else text[:start] + new + text[end:]


def replace_once(text: str, find: str, repl: str, start: int = 0) -> str | None:
    """Replace the first occurrence of `find` at or after `start`, or return None."""
    i = text.find(find, start)
    return None if i < 0 else text[:i] + repl + text[i + len(find):]


def replace_span(text: str, m: re.Match[str], new: str) -> str:
    return text[:m.start()] + new + text[m.end():]


# =====================================================================================
# Template cache
# =====================================================================================
#
# Reuses unchanged files and Git objects from the most recent completed template build.
# A file is hardlinked from the snapshot only when its path, size, mtime, and placement
# kind match the manifest and its mtime precedes `built_ns` by at least `_GRACE_NS`.

_MANIFEST = ".selftest-manifest.json"
_GRACE_NS = 2_000_000_000

type Placement = tuple[int, int, str]     # size, mtime_ns, "copy" | "empty"


def _cache_root(repo: Path) -> Path:
    """Return the per-checkout template cache directory in the system temp dir."""
    digest = hashlib.sha256(str(repo).casefold().encode()).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"verifiedos-selftest-cache-{digest}"


def _newest_snapshot(cache: Path) -> tuple[Path, int, dict[str, list[int | str]],
                                         dict[str, str]] | None:
    """Return `(path, built_ns, files, gitlinks)` for the newest valid snapshot in `cache`."""
    if not cache.is_dir():
        return None
    for path in sorted((p for p in cache.iterdir() if re.fullmatch(r"t\d+", p.name)),
                       key=lambda p: int(p.name[1:]), reverse=True):
        try:
            data = json.loads((path / _MANIFEST).read_text(encoding="utf-8"))
        except OSError, ValueError:
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
    """Hardlink or copy the directory tree `src` into `dst`."""
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
    """Return True if every path in `files` resolves to a blob in `root`'s index and object store."""
    names = list(files)
    if not names:
        return True
    try:
        done = subprocess.run(["git", "cat-file", "--batch-check=%(objecttype)"],
                              input="".join(f":{name}\n" for name in names),
                              cwd=root, capture_output=True, encoding="utf-8",
                              errors="replace", check=False, timeout=60)
    except OSError, subprocess.TimeoutExpired:
        return False
    return done.returncode == 0 and done.stdout.splitlines() == ["blob"] * len(names)


def _publish(template: Path, cache: Path) -> None:
    """Publish `template` as the newest numbered snapshot in `cache` and prune old snapshots."""
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
            pass


def build_template(repo: Path, into: Path, jobs: int) -> tuple[int, int]:
    """Populate `into` from `repo`'s working tree and non-ignored untracked files.

    Files under `model/` that the checker only checks for path existence (outside
    [`MODEL_FACTS`](../corpus.py#MODEL_FACTS) and
    [`is_model_citation_path`](../corpus.py#is_model_citation_path)) are created empty.
    Submodule directories receive `SUBMODULE_STAND_IN` and have their mode-`160000`
    gitlinks restored in the template index via [`stamp_gitlinks`](#stamp_gitlinks).

    Returns `(copied_count, carried_from_cache_count)`.
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

    for parent in {(into / rel).parent for rel in listed}:
        parent.mkdir(parents=True, exist_ok=True)

    held = _newest_snapshot(_cache_root(repo))
    snapshot, built_ns, old_files, old_gitlinks = held or (None, 0, {}, {})
    if snapshot is not None:
        try:
            os.utime(snapshot)
        except OSError:
            snapshot, old_files = None, {}
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
            return 0, 0
        empty = (rel.startswith(UNREAD_PREFIX) and rel not in MODEL_FACTS
                 and not is_model_citation_path(rel))
        kind = "empty" if empty else "copy"
        placed[rel] = (measured.st_size, measured.st_mtime_ns, kind)
        if empty:
            dst.touch()
            return 1, 0
        if (snapshot is not None
                and old_files.get(rel) == [measured.st_size, measured.st_mtime_ns, kind]
                and measured.st_mtime_ns + _GRACE_NS < built_ns):
            try:
                os.link(snapshot / rel, dst)
            except OSError:
                pass
            else:
                return 1, 1
        shutil.copy2(src, dst)
        return 1, 0

    counts = _across(place, listed, jobs)
    copied = sum(one for one, _ in counts)
    carried = sum(one for _, one in counts)

    # Reuse the snapshot's Git objects when available; if any file or gitlink changed,
    # unlink the carried index before running `git add -A`.
    manifest = {rel: [size, mtime, kind] for rel, (size, mtime, kind) in placed.items()}
    gitlinks = index.gitlinks
    carried_index = False
    if snapshot is not None:
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
        (into / ".git" / "index").unlink(missing_ok=True)
        proc = subprocess.run(["git", "add", "-A"], cwd=into, capture_output=True, check=False)
        if proc.returncode != 0:
            raise SystemExit("could not build the sandbox index: git add")
    stamp_gitlinks(into, gitlinks)

    (into / _MANIFEST).write_text(
        json.dumps({"built_ns": time.time_ns(), "files": manifest, "gitlinks": gitlinks}),
        encoding="utf-8")
    return copied, carried


# =====================================================================================
# Mutation cases
# =====================================================================================

REGISTER = "docs/requirements-register.md"
SPEC = "docs/spec.md"
CRITIQUE = "docs/background/critique.md"
CROWN = "docs/assurance/crown-jewels.md"
MATRIX = "docs/assurance/coverage-matrix.md"
PROFILE = "docs/hardware/isa-profile.md"
PERF = "docs/performance/performance-estimates.md"
PLAN = "PLAN.md"
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

type Mutation = Callable[[Sandbox], bool]
type Case = tuple[str, str, Mutation]


@dataclass(frozen=True)
class Seeding:
    """Identifier and description of an authored selftest case for [`vos.seeded.Verdict`](../seeded.py#Verdict)."""

    rule: str
    description: str

    @property
    def what(self) -> str:
        return f"{self.rule}: {self.description}"


def _literal(rel: str, find: str, repl: str) -> Mutation:
    def apply(box: Sandbox) -> bool:
        return box.write(rel, replace_once(box.read(rel), find, repl))
    return apply


def _k103(box: Sandbox) -> bool:
    """Transpose an authored requirement citation outside the derived header region."""
    text = box.read(SEAM_WITNESSES)
    region = proofcites.derived(text)
    if region.faults:
        return False
    for match in REQ_TOKEN_RE.finditer(text):
        if match.group() == "R-05-166" and not any(
                start <= match.start() < end for start, end in region.spans):
            return box.write(SEAM_WITNESSES, replace_span(text, match, "R-05-616"))
    return False


def _k114_compressed_premise(box: Sandbox) -> bool:
    """Append an unlisted premise inside retained gzip evidence."""
    rel = ("docs/implementation/retained-evidence/q39/pending-audits-20261012/"
           "raw/standard-source/progress.json.gz")
    target = box.path / rel
    raw = gzip.decompress(target.read_bytes())
    box.touched.add(rel)
    target.unlink()
    target.write_bytes(gzip.compress(raw + b"\nCorrectness rests on HACL* and F*/Z3.\n", mtime=0))
    return True


def _entry(ident: str, edit: Callable[[str], str | None]) -> Mutation:
    def apply(box: Sandbox) -> bool:
        return box.write(REGISTER, edit_entry(box.read(REGISTER), ident, edit))
    return apply


def _first_match(rel: str, pattern: str, rewrite: Callable[[re.Match[str]], str],
                 flags: int = re.MULTILINE) -> Mutation:
    """Rewrite the first match of `pattern` in `rel`."""
    def apply(box: Sandbox) -> bool:
        text = box.read(rel)
        m = re.search(pattern, text, flags)
        if not m:
            return False
        return box.write(rel, replace_span(text, m, rewrite(m)))
    return apply


def _renumber(rel: str, pattern: str, group: int, value: str) -> Mutation:
    """Overwrite group `group` of the first match of `pattern` in `rel`."""
    def apply(box: Sandbox) -> bool:
        text = box.read(rel)
        m = re.search(pattern, text, re.MULTILINE)
        if not m:
            return False
        return box.write(rel, text[:m.start(group)] + value + text[m.end(group):])
    return apply


def _seed_paragraph(sentence: str) -> Mutation:
    """Insert `sentence` as an unfenced paragraph before the first `## ` heading in `CRITIQUE`."""
    return _literal(CRITIQUE, "\n## ", f"\n{sentence}\n\n## ")


def _strip_requirements(rel: str, pattern: str,
                        replacement: str = "the register") -> Mutation:
    return _first_match(rel, pattern,
                        lambda m: REQ_TOKEN_RE.sub(replacement, m.group()))


def _k14(box: Sandbox) -> bool:
    register = box.read(REGISTER)
    sub = re.search(r"(?ms)^### 15\.14 .*?(?=^### )", register)
    if not sub:
        return False
    view = box.read(ABSENCE)
    for ident in re.findall(rf"(?m)^\*\*({REQ_ID_PATTERN})\*\* ", sub.group()):
        if ident in view:
            return box.write(ABSENCE, view.replace(ident, "R-01-001"))
    return False


def _k26(box: Sandbox) -> bool:
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
    """Rename `_ccache_args` across `tools/vos/env.py` so the lane fact table points at a missing consumer."""
    rel = "tools/vos/env.py"
    text = box.read(rel)
    if "_ccache_args" not in text:
        return False
    return box.write(rel, text.replace("_ccache_args", "_ccache_launchers"))


def _k84_unregistered_holder(box: Sandbox) -> bool:
    """Change an unfenced bold holder citation in `LOG` to unallocated `K-64`."""
    text = box.read(LOG)
    doc = corpus_mod.from_text(text, LOG)
    for holder in re.finditer(rf"\*\*({checkregistry.ID_PATTERN})\*\*", text):
        if not doc.is_fenced(holder.start()) and holder.group(1) != "K-64":
            return box.write(LOG, text[:holder.start(1)] + "K-64" + text[holder.end(1):])
    return False


def _k84_retired_holder(box: Sandbox) -> bool:
    """Change a current unfenced holder citation in `PLAN` to retired `K-102`."""
    text = box.read(PLAN)
    doc = corpus_mod.from_text(text, PLAN)
    for holder in re.finditer(rf"\*\*({checkregistry.ID_PATTERN})\*\*", text):
        if not doc.is_fenced(holder.start()) and holder.group(1) != "K-102":
            return box.write(PLAN, text[:holder.start(1)] + "K-102" + text[holder.end(1):])
    return False


def _k84(box: Sandbox) -> bool:
    """Remove the holders from an unfenced Tier-B landing declaration in `LOG`."""
    text = box.read(LOG)
    doc = corpus_mod.from_text(text, LOG)
    declarations = re.finditer(
        r"(?m)^(?P<lead>[^\S\r\n]*(?:\*+ )?Landed: Tier B)\b(?P<rest>[^\r\n]*)", text)
    for declaration in declarations:
        if (not doc.is_fenced(declaration.start())
                and re.search(rf"\*\*{checkregistry.ID_PATTERN}\*\*", declaration.group("rest"))):
            return box.write(LOG, replace_span(text, declaration, declaration.group("lead") + "."))
    return False


def _k82_entry(box: Sandbox) -> bool:
    """Delete a landed item's completion-log heading and its link in `PLAN.md`."""
    heading = "### M0.5 · Reconcile the baselines\n\n"
    log = box.read(LOG)
    if heading not in log:
        return False
    plan = box.read(PLAN)
    link = " ([note](docs/implementation/completion-log.md#m05-reconcile-the-baselines))"
    if link not in plan:
        return False
    return (box.write(LOG, log.replace(heading, "", 1))
            and box.write(PLAN, plan.replace(link, "", 1)))


def _k82_figure(box: Sandbox) -> bool:
    """Decrement the findings count in `FINDINGS` so `--fix` repairs it."""
    text = box.read(FINDINGS)
    m = re.search(r"The plan records (?P<n>\d+) of them", text)
    if not m:
        return False
    return box.write(FINDINGS, replace_span(
        text, m, f"The plan records {int(m.group('n')) - 1} of them"))


# Lower the DECTED check-bit width below the distance-6 floor while keeping all derived
# percentages and SRAM bands internally consistent so K-54's coding-theory floor fires.
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
    """Remove one source guard in `tools/vos/checks/counts.py`."""
    rel = "tools/vos/checks/counts.py"
    return _first_match(rel, r"(?m)^    \"sections\": \"the register's normative sections\",\r?\n",
                        lambda _m: "")(box)


def _k49(box: Sandbox) -> bool:
    return box.delete(ABSENCE)


def _k61(box: Sandbox) -> bool:
    """Corrupt one recorded prose digest in `LEDGER`."""
    text = box.read(LEDGER)
    m = re.search(r'^(  "R-01-001": \[")([0-9a-f]{12})', text, re.MULTILINE)
    if not m:
        return False
    return box.write(LEDGER, text[:m.start(2)] + "0" * 12 + text[m.end(2):])


def _k109(box: Sandbox) -> bool:
    """Flip one hex digit of the generated header fingerprint in `SEAM_WITNESSES`."""
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
    """Rename `SWITCH` across `regenerate.py` and `hello.py` so the instrument reader misses it."""
    driver = "tools/bedrock2-lowering/regenerate.py"
    importer = "tools/bedrock2-lowering/hello.py"
    text = box.read(driver)
    renamed = re.sub(r"\bSWITCH\b", "LOWERING_SWITCH", text)
    if renamed == text:
        return False
    return box.write(driver, renamed) and box.write(importer, replace_once(
        box.read(importer), "regenerate.SWITCH", "regenerate.LOWERING_SWITCH"))


def _k117_release(box: Sandbox) -> bool:
    """Rename `ROCQ_VERSION` in `compare_component.py` so the instrument reader misses it."""
    path = "tools/wasm-oracle/compare_component.py"
    text = box.read(path)
    renamed = re.sub(r"\bROCQ_VERSION\b", "PROVER_RELEASE", text)
    return renamed != text and box.write(path, renamed)


def _keep_own_id(entry_line: str) -> str:
    head = re.match(rf"^\*\*{REQ_ID_PATTERN}\*\* ", entry_line)
    if head is None:
        raise SystemExit(f"the entry to mutate does not open with a requirement id: "
                         f"{entry_line[:60]!r}")
    return head.group() + REQ_TOKEN_RE.sub("R-01-001", entry_line[len(head.group()):])


CASES: list[Case] = [
    ("K-00", "a registered rule with its registry row retitled out of the table",
     _literal(RULES, "| K-41 | glyphs", "| K-xx | glyphs")),

    ("K-00", "two authored metadata records claiming the same permanent ID",
     _literal(checkregistry.SOURCE, '"id": "K-01"', '"id": "K-00"')),

    ("K-00", "a rule assigned a reach class the registry does not carry",
     _literal(checkregistry.SOURCE, '"reach": "total"', '"reach": "marker"')),

    ("K-00", "a metadata group with no executable callback",
     _literal(checkregistry.SOURCE, '"group": "traces"', '"group": "missing"')),

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

    ("K-12", "a source comment linking to a file the repository does not carry",
     _literal("tools/vos/checks/links.py", "# SPDX-License-Identifier: Apache-2.0",
              "# SPDX-License-Identifier: Apache-2.0\n"
              "# [missing source](missing-reference.py)")),

    ("K-12", "a source comment linking to a renamed Python declaration",
     _literal("tools/vos/checks/links.py", "# SPDX-License-Identifier: Apache-2.0",
              "# SPDX-License-Identifier: Apache-2.0\n"
              "# [renamed declaration](links.py#missing_declaration)")),

    ("K-12", "a source comment linking to a renamed Gallina declaration",
     _literal("tools/vos/checks/links.py", "# SPDX-License-Identifier: Apache-2.0",
              "# SPDX-License-Identifier: Apache-2.0\n"
              "# [renamed declaration](../../../proofs/KernelInstance.v#missing_declaration)")),

    ("K-12", "a source comment linking to a renamed Sail declaration",
     _literal("tools/vos/checks/links.py", "# SPDX-License-Identifier: Apache-2.0",
              "# SPDX-License-Identifier: Apache-2.0\n"
              "# [renamed declaration](../../../model/model/core/cap_format.sail#missing_declaration)")),

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

    # Keep the entry's own ID and replace its cited IDs so the seam composes un-conferred refusals.
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

    # Narrow the range symmetrically around the midpoint so K-35 stays quiet and K-86 fires.
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

    ("K-37", "a committed total its explicit dispositions do not give",
     _renumber(PLAN, r"(?m)^\| Committed remaining h \| ([\d.,]+) \|", 1, "999")),

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

    ("K-96", "a leaf assigned to two work dispositions",
     _literal("docs/implementation/work-order.json", '"Q3b"', '"M7.1a"')),

    ("K-96", "a work owner with an unclassified priced leaf",
     _first_match("docs/implementation/work-order.json", r'(?m)^      "Q3b",\n', lambda _m: "")),

    ("K-96", "a stale generated authoring verdict",
     _literal(PLAN, "available for authoring", "ready without its inputs")),

    ("K-96", "a calibration ratio the record's estimates and the actuals do not give",
     _renumber(PLAN, r"(?m)^\| M0\.8d \| X-authored \| ([\d.,]+) \|", 1, "999")),

    ("K-96", "a missing calibration result marker",
     _literal(PLAN, "<!-- calibration-results:start -->", "<!-- calibration-results:missing -->")),

    ("K-96", "a duplicated calibration result row",
     _first_match(PLAN, r"(?m)^\| attended \| I \|[^\r\n]*",
                  lambda m: m.group() + "\n" + m.group())),

    ("K-96", "a malformed calibration result cell",
     _renumber(PLAN, r"(?m)^\| attended \| I \| (\d+) \|", 1, "unknown")),

    ("K-96", "a stale calibration result count",
     _renumber(PLAN, r"(?m)^\| attended \| I \| (\d+) \|", 1, "9999")),

    ("K-96", "a completed attended item the calibration record no longer carries",
     _first_match(PLAN, r"(?m)^\| S1 \| I \| [\d.,]+ \|[^\r\n]*\r?\n", lambda _m: "")),

    ("K-96", "an agent-parallel ratio the second record's estimates do not give",
     _renumber(PLAN, r"(?m)^\| M6\.0b \| X-authored \| ([\d.,]+) \|", 1, "999")),

    ("K-96", "a retained estimate presented as a calibration measurement",
     _literal(PLAN, "| M1.2b | n/a | n/a |", "| M1.2b | X-authored | 6 |")),

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

    ("K-52", "a markable file whose license mark has gone",
     _literal("tools/vos/checks/marks.py", "# SPDX-License-Identifier: Apache-2.0\n", "")),
    ("K-52", "an authored OCaml template whose license mark has gone",
     _literal("proofs/campaigns/mlkem_driver.ml.in", "(* SPDX-License-Identifier: Apache-2.0 *)\n", "")),
    ("K-52", "the authored native OCaml producer whose license mark has gone",
     _literal("tools/rocq-census/vos_rocq_census.ml", "(* SPDX-License-Identifier: Apache-2.0 *)\n", "")),
    ("K-52", "an authored Gallina template whose license mark has gone",
     _literal("proofs/campaigns/mlkem_extract.v.in", "(* SPDX-License-Identifier: Apache-2.0 *)\n", "")),
    ("K-52", "an authored CMake overlay whose license mark has gone",
     _literal("tools/sail-modular/overlay.cmake", "# SPDX-License-Identifier: Apache-2.0\n", "")),
    ("K-52", "an authored Sail project fixture whose license mark has gone",
     _literal("tools/sail-lsp/fixtures/qualification.sail_project", "// SPDX-License-Identifier: Apache-2.0\n", "")),
    ("K-52", "an authored Lustre node whose license mark has gone",
     _literal("supervisor/route/start_restart.lus", "-- SPDX-License-Identifier: Apache-2.0\n", "")),

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
    ("K-53", "the authored native OCaml language whose ruling has gone",
     _literal("tools/vos/checks/marks.py", '    ".ml": ("(* ", " *)"),\n', "")),
    ("K-53", "an upstream patch whose byte-preserving ruling has gone",
     _literal("tools/vos/checks/marks.py",
              '    ".patch": "a unified diff must preserve upstream context and hunk bytes",\n', "")),

    ("K-54", "the tag granule moved out from under every figure derived from it",
     _renumber(REGISTER, r"one validity tag per \*\*(\d+)-bit\*\* granule", 1, "128")),

    ("K-54", "a DECTED width below the distance-6 floor under consistent figures",
     _k54_below_floor),

    ("K-54", "an upper band end the fallback codeword does not give",
     _literal(REGISTER, "about 47–70 MB of SRAM per GB", "about 47–71 MB of SRAM per GB")),

    ("K-54", "a ladder rung extended Hamming, the tags and the linear floor do not give",
     _literal(REGISTER, "full ladder is 21.9 / 14.1 / 8.6 / 5.5%",
              "full ladder is 21.9 / 14.1 / 8.6 / 5.3%")),

    ("K-55", "an artifact that no longer books the per-class bank count as open",
     _literal(REGISTER, "the per-class bank count is in R-15-014a's frozen parameter set",
              "the per-class bank count is frozen")),

    ("K-56", "a region class the two latency-class lists no longer place",
     _first_match(REGISTER, r"(?m)^· Accept: the first class carries[^\r\n]*",
                  lambda m: m.group().replace("recovery workspaces, ", ""))),

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

    ("K-57", "a composition that writes a welded block size the model does not",
     _literal("model/config/verifiedos.json",
              '"cache_block_size_exp": 6', '"cache_block_size_exp": 5')),

    ("K-57", "a stated block ceiling the destination register's width does not give",
     _literal(REGISTER, "the block at most **512 bytes**",
              "the block at most **256 bytes**")),

    ("K-60", "a class whose vector geometry the composition and the documents no "
             "longer agree on",
     _literal("model/config/verifiedos.json", '"vlen_exp": 12', '"vlen_exp": 13')),

    ("K-61", "a pair the ledger records as read at contents it no longer holds", _k61),

    ("K-62", "a normative section of the prose that the register no longer extracts",
     _literal(REGISTER, "## §18", "## §20")),

    ("K-63", "a model file citing a requirement the register does not declare",
     _literal("model/model/core/timing.sail", "R-15-095", "R-15-995")),

    ("K-65", "a second shipped configuration that composes the same core as the first",
     _literal("model/config/verifiedos-v.json", '"hartid": 6', '"hartid": 0')),

    # Mutate `Ext_Zvl32b` in the generated Sail bundle so `K-78` fires without `K-88`.
    ("K-78", "a minimum-vector-length rung a vectorless composition now reaches",
     _literal(BUNDLE,
              '"id":"Ext_Zvl32b"},"body":{"contents":"sizeof(vlen_exp) >= 5"',
              '"id":"Ext_Zvl32b"},"body":{"contents":"sizeof(vlen_exp) >= 3"')),

    ("K-87", "an excluded-by-name extension a shipped configuration switches back on",
     _literal("model/config/verifiedos.json",
              '"Zbc": { "supported": false }',
              '"Zbc": { "supported": true }')),

    ("K-66", "a form the profile excludes and the model still decodes",
     _literal(PROFILE, "Sail: `AMOCAS`", "Sail: `AMO`")),

    ("K-68", "a co-stated fact one of its sites no longer states",
     _entry("R-14-007", lambda entry: entry.replace(
         "capabilities beyond pure compute", "capabilities beyond pure computation"))),

    ("K-46", "an owned enumeration whose lead-in moved out of the reader's reach",
     _literal(REGISTER, "obligations are exactly:", "obligations are precisely:")),

    ("K-69", "a restated owned figure drifted from the entry that fixes it",
     _literal(SPEC, "target ≤10k lines", "target ≤12k lines")),

    ("K-70", "a delta item of the closed freeze delta that its instrument does not "
             "account for",
     _literal(CONTRACT, "| (v) the capability indexed",
              "| the capability indexed")),

    ("K-60", "a VLEN token naming a geometry no composed class carries",
     _literal(SPEC, "VLEN=4096", "VLEN=2048")),

    ("K-71", "a manifest declaring a commit-trace schema the document does not state",
     _first_match("corpus/manifest.json", r'"trace_schema": (\d+)',
                  lambda m: f'"trace_schema": {int(m.group(1)) + 1}')),

    ("K-72", "a hand-written corpus word standing on a ground the encoder contradicts",
     _literal(CORPUS_DOC, "| the word is what the reader must see | `csrrw",
              "| the encoder cannot express it | `csrrw")),

    ("K-73", "a freshness conferral naming a state the enumeration does not carry",
     _first_match(REGISTER, f"(?m)^{MID} RoT-fresh: (.+?) \\(R-10-013\\)",
                  lambda m: m.group().replace(m.group(1), "a state of its own"))),

    ("K-74", "a residual cell whose citation of the section booking it has gone",
     _literal(MATRIX, "R-08-006, R-15-208, R-17-037", "R-08-006, R-15-208")),

    ("K-95", "a coverage cell whose standing differs from the inventory",
     _first_match(MATRIX,
                  r"(?m)^\| `B-\d\d` \| `P-\d` \|[^\r\n]*\| (authored|partial|not authored) \|$",
                  lambda m: m.group().replace(f"| {m[1]} |",
                      "| not authored |" if m[1] == "authored" else "| authored |"))),

    ("K-76", "a synthesis parameter the provenance record binds set to another value",
     _literal("rtl/vos_c_class_config_pkg.sv", "BHTEntries: unsigned'(0),",
              "BHTEntries: unsigned'(1),")),

    ("K-118", "a workflow action at a commit its reviewed row does not state",
     _first_match(".github/workflows/host-gates.yml",
                  r"(?m)^(\s*- uses: [^@\s]+@[0-9a-f]{39})([0-9a-f])",
                  lambda m: m[1] + ("1" if m[2] == "0" else "0"))),
    ("K-118", "a nested composite action at an unreviewed commit",
     _first_match(".github/actions/setup-target-sail/action.yml",
                  r"(?m)^([ \t]+uses: [^@\s]+@[0-9a-f]{39})([0-9a-f])",
                  lambda m: m[1] + ("1" if m[2] == "0" else "0"))),
    ("K-118", "a local composite action whose metadata is absent",
     _literal(".github/workflows/boot-crypto-target.yml",
              "uses: ./.target-ci/.github/actions/setup-target-sail",
              "uses: ./.target-ci/.github/actions/missing-target-sail")),
    ("K-118", "a local composite fetched from a foreign repository",
     _literal(".github/workflows/boot-crypto-target.yml",
              "          path: .target-ci\n",
              "          repository: example/unreviewed\n          path: .target-ci\n")),
    ("K-118", "a workflow action referenced by a tag that can move",
     _first_match(".github/workflows/host-gates.yml",
                  r"(?m)^(\s*- uses: [^@\s]+)@[0-9a-f]{40} # (v\d+)\.\d+\.\d+$",
                  lambda m: f"{m[1]}@{m[2]}")),
    ("K-118", "a workflow action with invalid continuation after its pinned source-line comment",
     _first_match(".github/workflows/host-gates.yml",
                  r"(?m)^([ \t]*)- uses: [^@\s]+@[0-9a-f]{40} # v\d+\.\d+\.\d+\n",
                  lambda m: f"{m[0]}{m[1]}    continuation\n")),
    ("K-118", "a workflow action stated in a shape the reading does not parse",
     _first_match(".github/workflows/host-gates.yml",
                  r"(?m)^(\s*- )uses:( [^@\s]+@[0-9a-f]{40} # v\d+\.\d+\.\d+)$",
                  lambda m: f'{m[1]}"uses":{m[2]}')),
    ("K-118", "a workflow action stated as an explicit key with a trailing comment",
     _first_match(".github/workflows/host-gates.yml",
                  r"(?m)^([ \t]*)- uses:( [^@\s]+@[0-9a-f]{40} # v\d+\.\d+\.\d+)$",
                  lambda m: f"{m[1]}- ? uses # the action\n{m[1]}  :{m[2]}")),
    ("K-118", "a workflow action stated as a flow mapping's unspaced explicit key",
     _first_match(".github/workflows/host-gates.yml",
                  r"(?m)^([ \t]*)- uses: ([^@\s]+@[0-9a-f]{40})( # v\d+\.\d+\.\d+)$",
                  lambda m: f"{m[1]}- {{?uses: {m[2]}}}{m[3]}\n{m[0]}")),
    ("K-118", "a workflow action stated after a quoted scalar's line opening with #",
     _first_match(".github/workflows/host-gates.yml",
                  r"(?m)^([ \t]*)- uses: ([^@\s]+@[0-9a-f]{40})( # v\d+\.\d+\.\d+)$",
                  lambda m: f'{m[1]}- {{name: "the action\n{m[1]}  # pinned", '
                            f"uses: {m[2]}}}{m[3]}\n{m[0]}")),
    ("K-118", "an action row that names no action a workflow runs",
     _literal(THIRD_PARTY, "| actions/download-artifact |", "| actions/download-artifacts |")),
    ("K-118", "an action row linking its licence at a commit other than the one it reviewed",
     _first_match(THIRD_PARTY, r"(github\.com/actions/checkout/blob/[0-9a-f]{39})([0-9a-f])",
                  lambda m: m[1] + ("1" if m[2] == "0" else "0"))),
    ("K-116", "a width-transform registry naming a commit the imported core's gitlink "
              "does not carry",
     _first_match("tools/rtl-width-transforms.json", r'^(  "pin": ")([0-9a-f])',
                  lambda m: m[1] + ("1" if m[2] != "1" else "2"))),

    ("K-118", "an elaborator source release its licence review does not state",
     _first_match("tools/vos/cli/rtl.py", r'^(VERILATOR_PIN = ")([^"\r\n]*)"',
                  lambda m: f'{m[1]}{m[2]}.1"')),
    ("K-118", "a hand-edited generated development-tool view",
     _first_match(THIRD_PARTY, r"filelock `(\d[^`]*)`", lambda m: f"filelock `{m[1]}.1`")),
    ("K-118", "an unsupported authored development-tool review schema",
     _literal("tools/development-tools.json", '"schema": 2', '"schema": 3')),
    ("K-118", "an authored review identity missing from the template",
     _first_match("tools/development-tools.json", r'"id": "([^"]+)"',
                  lambda m: f'"id": "{m[1]}_missing"')),
    ("K-118", "a locked Python release its development-tool row does not state",
     _first_match("tools/uv.lock", r'name = "filelock"\r?\nversion = "([^"]+)"',
                  lambda m: m.group().replace(f'"{m[1]}"', f'"{m[1]}.1"'))),
    ("K-118", "an opam snapshot release its development-tool row does not state",
     _first_match("tools/opam/sail.lock", r'"zarith\.([^"]+)"',
                  lambda m: f'"zarith.{m[1]}.1"')),
    ("K-118", "a contained compiler prover release its development-tool row does not state",
     _first_match("tools/opam/contained-compiler.lock", r'"rocq-core\.([^"]+)"',
                  lambda m: f'"rocq-core.{m[1]}.1"')),
    ("K-118", "a contained compiler OCaml release its development-tool row does not state",
     _first_match("tools/opam/contained-compiler.lock",
                  r'(?s)(installed:\s*\[.*?"ocaml-base-compiler\.)([^"]+)"',
                  lambda m: f'{m[1]}{m[2]}.1"')),
    ("K-118", "a contained compiler Menhir runtime release its development-tool row does not state",
     _first_match("tools/opam/contained-compiler.lock", r'"menhirLib\.([^"]+)"',
                  lambda m: f'"menhirLib.{m[1]}.1"')),
    ("K-118", "a CertiRocq snapshot release its development-tool row does not state",
     _first_match("tools/opam/certirocq.lock", r'"yojson\.([^"]+)"',
                  lambda m: f'"yojson.{m[1]}.1"')),
    ("K-118", "an opam snapshot's pinned commit its development-tool row does not state",
     _first_match("tools/opam/quickchick.lock", r"(QuickChick\.git#)([0-9a-f])",
                  lambda m: m[1] + ("1" if m[2] != "1" else "2"))),
    ("K-118", "a hook release the model's hook configuration pins and its row does not state",
     _first_match("model/.pre-commit-config.yaml", r"# frozen: v(\d\S*)",
                  lambda m: f"# frozen: v{m[1]}.1")),
    ("K-118", "a hook commit the model's hook configuration pins and its row does not state",
     _first_match("model/.pre-commit-config.yaml", r"^([ \t]+rev: \"?)([0-9a-f])",
                  lambda m: m[1] + ("1" if m[2] != "1" else "2"))),
    ("K-118", "a hook repository's rev a line inside a hook's block scalar stands in for",
     _first_match("model/.pre-commit-config.yaml",
                  r'^([ \t]+)rev: "?([0-9a-f]{40})"? # frozen: (\S+)\n'
                  r"(\1hooks:\n([ \t]+)- id: \S+\n)",
                  lambda m: (f"{m[1]}rev: {m[3]} # the tag\n{m[4]}{m[5]}  description: |\n"
                             f"{m[5]}    rev: {m[2]} # frozen: {m[3]}\n"))),
    ("K-118", "a hook repository anchored on a line a no-break space opens and aliased in",
     _first_match("model/.pre-commit-config.yaml", r"^(repos:\n.*)\Z",
                  lambda m: ("ci:\n  \u00a0#x: &unreviewed {repo: https://github.com/example/"
                             f"unreviewed-hooks, rev: {'d' * 40}, hooks: [{{id: unreviewed}}]}}\n"
                             f"{m[1]}  - *unreviewed\n"),
                  flags=re.MULTILINE | re.DOTALL)),
    ("K-118", "a hook repository stated after a quoted scalar's line opening with #",
     _first_match("model/.pre-commit-config.yaml", r"\Z",
                  lambda _: '  - {hooks: [{id: unreviewed, name: "the unreviewed hook\n'
                            '    # reviewed"}], repo: https://github.com/example/'
                            f"unreviewed-hooks, rev: {'d' * 40}}}\n")),
    ("K-118", "a hook repository stated as a flow mapping of unspaced explicit keys",
     _first_match("model/.pre-commit-config.yaml", r"\Z",
                  lambda _: "  - {?repo: https://github.com/example/unreviewed-hooks, "
                            f"?rev: {'d' * 40}, ?hooks: [{{?id: unreviewed}}]}}\n")),
    ("K-118", "a hook repository whose keys follow a byte-order mark opening their lines",
     _first_match("model/.pre-commit-config.yaml", r"\Z",
                  lambda _: "  - {hooks: [{id: unreviewed}],\n"
                            "\ufeffrepo: https://github.com/example/unreviewed-hooks,\n"
                            f"\ufeffrev: {'d' * 40}}}\n")),
    ("K-118", "a hook repository's rev a merge key supplies from a meta entry's mapping",
     _first_match("model/.pre-commit-config.yaml",
                  r"^(repos:\n)(  - repo: \S+\n)([ \t]+)(rev: .*\n)",
                  lambda m: (f"{m[1]}  - repo: meta\n{m[3]}x: &moved {{\n{m[3]}rev: {'d' * 40}\n"
                             f"{m[3]}}}\n{m[3]}hooks: [{{id: check-useless-excludes}}]\n{m[2]}"
                             f"{m[3]}<<: *moved\n{m[3]}x: [\n{m[3]}{m[4]}{m[3]}]\n"))),
    ("K-118", "a hook repository's second rev after a line separator",
     _first_match("model/.pre-commit-config.yaml",
                  r'^([ \t]+)rev: "?([0-9a-f]{39})([0-9a-f])"?.*?(?=\n[ \t]*- repo:)',
                  lambda m: f"{m[0]}\u2028{m[1]}rev: {m[2]}{'1' if m[3] == '0' else '0'}",
                  flags=re.MULTILINE | re.DOTALL)),
    ("K-118", "a hook repository the model's hook configuration runs and no row reviews",
     _first_match("model/.pre-commit-config.yaml", r"\Z",
                  lambda _: "  - repo: https://github.com/example/unreviewed-hooks\n"
                            f"    rev: {'d' * 40} # frozen: v1.0.0\n"
                            "    hooks:\n      - id: unreviewed\n")),
    ("K-118", "a hook build backend the pip constraints pin and its row does not state",
     _first_match("tools/ci/model-hooks-build-constraints.txt", r"^(setuptools==)([^\s\\]+)",
                  lambda m: f"{m[1]}{m[2]}.1")),
    ("K-118", "a hook dependency the pip constraints pin and no row reads",
     _first_match("tools/ci/model-hooks-constraints.txt", r"\Z",
                  lambda _: "unreviewed-dependency==1.0.0\n")),
    ("K-118", "a hook dependency pin a continued marker leaves applying nowhere",
     _first_match("tools/ci/model-hooks-constraints.txt",
                  r"^([A-Za-z0-9._-]+==[^\s\\]+(?: \\\n[ \t]+--hash=sha256:[0-9a-f]{64})*)\n",
                  lambda m: f"{m[1]} \\\n    ; sys_platform == \"never\"\n")),

    ("K-80", "a component's licence text named at a path the repository does not carry",
     _literal(THIRD_PARTY, "`model/dependencies/elfio/LICENSE.txt`",
              "`model/dependencies/elfio/LICENCE.txt`")),

    ("K-83", "a landing-loop tool that imports the quarantined instruments",
     _literal("tools/vos/cli/blast.py", "from vos.corpus import find_root",
              "from quarantine import freeze\nfrom vos.corpus import find_root")),

    ("K-83", "a landing-loop tool that puts the quarantine on its own path",
     _literal("tools/run.py",
              'sys.path.insert(0, str(Path(__file__).resolve().parent))',
              'sys.path.insert(0, str(Path(__file__).resolve().parent / "quarantine"))')),

    ("K-79", "a capability-format width the authored package and the model no longer "
             "agree on",
     _literal("rtl/vos_cheri_pkg.sv",
              "localparam int unsigned CapAddrWidth = 36;",
              "localparam int unsigned CapAddrWidth = 32;")),

    ("K-81", "an upstream pin restated as a commit the record does not record",
     _literal(DELTA, "| `0c7b3adf` | 2026-09-24 |", "| `0c7b3ade` | 2026-09-24 |")),
    ("K-81", "a historical modular receipt gitlink changed outside its exact scoped edition",
     _literal("docs/assurance/sail-assistance-evidence/modular.json",
              "gitlink:24c6e2d8531e6a6d0a9e29bde2a109484099aec9",
              "gitlink:0000000000000000000000000000000000000000")),
    ("K-81", "a scoped libclang license reading changed without its recorded edition",
     _literal("THIRD-PARTY.md", "2078da43e25a4623cab2d0d60decddf709aaea28",
              "0000000000000000000000000000000000000000")),
    ("K-81", "a copied model transplant edition changed outside its exact retained-source residue",
     _literal("docs/implementation/retained-evidence/close3-q35p-20261013/bindings.sail.txt",
              "bb07488d", "bb07488e")),
    ("K-81", "a copied tag-outcome reproducer edition changed outside its exact retained-source residue",
     _literal("docs/implementation/retained-evidence/q35p-tag-outcomes-20261023/bindings.sail.txt",
              "bb07488d", "bb07488e")),
    ("K-81", "a watched PR workflow identifier changed outside its exact scoped capture",
     _literal("docs/implementation/upstream-prs.md",
              "actions/runs/33583780921): **success**",
              "actions/runs/33583780922): **success**")),
    ("K-81", "a declared workflow identifier used as a source pin outside its tracker scope",
     _literal("docs/implementation/fiat-crypto-emission.md",
              "1e721c6f18c43b90922e7bc57fd64848e5cff2be", "33583780870")),

    ("K-84", "a landing naming a holder the rule registry does not carry",
     _k84_unregistered_holder),

    ("K-84", "a Tier-B landing naming no rule holding what it created", _k84),

    ("K-84", "a current claim relying on a retired rule",
     _k84_retired_holder),

    ("K-82", "a completion note whose declared count is not the number of findings "
             "beneath it",
     _literal(LOG, "  * Six findings.\n    * **The discharge needed no mechanism",
              "  * Seven findings.\n    * **The discharge needed no mechanism")),

    ("K-82", "a landed item the completion log carries no entry for", _k82_entry),

    ("K-82", "a register entry raised at an item the plan does not carry",
     _literal(FINDINGS, "· Raised: I11", "· Raised: I12")),

    ("K-113", "a landed item keeping a note line under its summary",
     _literal(PLAN, "is M0.8c's to close. ([note](docs/implementation/completion-log.md#s1-discharge-the-owed-"
                    "register-acts))\n",
              "is M0.8c's to close. ([note](docs/implementation/completion-log.md#s1-discharge-the-owed-"
              "register-acts))\n    * Exit evidence left behind by the move.\n")),

    ("K-113", "a landed item's summary linking another item's entry",
     _literal(PLAN, "([note](docs/implementation/completion-log.md#s2-adopt-the-two-tier-landing-rule-and-"
                    "hold-it-by-rule))",
              "([note](docs/implementation/completion-log.md#s1-discharge-the-owed-register-acts))")),

    ("K-85", "an elision table naming a record kind the meeting table also carries",
     _literal(CORPUS_DOC,
              "| `T` | `rvfi_trap` is a boolean where the record carries the cause |",
              "| `X` | `rvfi_trap` is a boolean where the record carries the cause |")),

    ("K-85", "a projection that has stopped emitting a record the meeting table claims",
     _literal("tools/vos/rvfi.py",
              '("W", packet.mem_wmask, packet.mem_wdata)',
              '("R", packet.mem_wmask, packet.mem_wdata)')),

    ("K-88", "a generated artifact edited by hand, one token off the bytes its "
             "generator wrote",
     _literal(BUNDLE, '"embedding":"plain"', '"embedding":"plane"')),

    ("K-88", "a project source omitted from Sail's bundle MD5 map changes",
     _literal("model/model/extensions/B/zbc_insts.sail",
              "function clause currentlyEnabled(Ext_Zbc) = hartSupports(Ext_Zbc)",
              "function clause currentlyEnabled(Ext_Zbc) = hartSupports(Ext_Zbkc)")),

    ("K-88", "a host-lane generated artifact one token off what its generator writes",
     _literal(DIALECT_TABLE, '"ctor": "RTYPE"', '"ctor": "RTYPEX"')),

    ("K-88", "a second host row's generated artifact granting a permission its "
             "composition withholds",
     _literal(SOC_MAP,
              "io: 1'b1, executable: 1'b0, readable: 1'b1, writable: 1'b0",
              "io: 1'b1, executable: 1'b1, readable: 1'b1, writable: 1'b0")),
    ("K-88", "a third host row's generated artifact declaring a fetch constant its "
             "proof file does not",
     _literal(MEMORY_PLAN, '"second_fetch": 15', '"second_fetch": 16')),
    ("K-88", "the calibration view accepts a populated manifest its schema does not",
     _literal("docs/hardware/calibration-manifest.md",
              "This unpopulated schema", "This populated schema")),
    ("K-88", "a generated vector bit-count corpus instruction drifts from its oracle",
     _literal("corpus/vector-bitcount.s", "vclz.v", "vctz.v")),
    ("K-88", "a generated vector bit-count Sail instruction drifts from its oracle",
     _literal("model/model/unit_tests/test_vector_bitcount.sail", "VCLZ_V", "VCTZ_V")),
    ("K-88", "a generated block-authority instruction drifts from its owners",
     _literal("corpus/block-authority.s", "cmove", "cgettag")),
    ("K-88", "the generated command lane reference disagrees with its metadata",
     _literal("tools/generated/command-lanes.md", "Operational handlers", "Invented handlers")),
    ("K-88", "the generated research evidence view drifts from its owner",
     _literal("docs/background/math-evidence.md", "# ", "## ")),
    ("K-88", "the retained finite matrix replay count changes",
     _literal("docs/background/rank48-replay.json", '"linear_operations": 204', '"linear_operations": 205')),
    ("K-88", "a generated production manifest promotes unresolved evidence",
     _literal("tools/composer/generated/manifest.json", '"production_admission":false',
              '"production_admission":true')),
    ("K-88", "the production composition substitutes a package identity",
     _literal("tools/composer/m8a-composition.json", '"package_id": "storage"',
              '"package_id": "crypto-core"')),
    ("K-88", "a composer package source view drops a shared dependency",
     _literal("tools/composer/packages/composer.json", '"tools/vos/jsonutil.py"',
              '"tools/vos/omitted-jsonutil.py"')),
    ("K-88", "an admission package source view drops a shared dependency",
     _literal("tools/composer/packages/admission.json", '"tools/vos/jsonutil.py"',
              '"tools/vos/omitted-jsonutil.py"')),
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
    ("K-88", "a signature adapter inverted after its staged streams were compiled",
     _literal("firmware/crypto/signature_target.c",
              "  return accepted ? 0 : 1;", "  return accepted ? 1 : 0;")),
    ("K-88", "a chain entropy refusal inverted after its historical streams were compiled",
     _literal("firmware/chain/rom.c", "  if (!entropy) {", "  if (entropy) {")),
    ("K-88", "a Fiat inclusion header changed after the recorded emission",
     _literal("tools/generated/fiat-crypto/25519_32.h",
              "static void fiat_25519_carry_mul", "static void fiat_25519_carry_mul_changed")),
    ("K-88", "the second Fiat field header changed after emission",
     _literal("tools/generated/fiat-crypto/p256_32.h",
              "static void fiat_p256_mul(", "static void fiat_p256_mul_changed(")),
    ("K-88", "the Fiat receipt no longer enumerates its source archives",
     _literal("tools/generated/fiat-crypto/manifest.json", '"sources": [', '"lost_sources": [')),
    ("K-88", "the Fiat receipt omits its locked generator build environment",
     _literal("tools/generated/fiat-crypto/manifest.json",
              '"build_environment": {', '"lost_build_environment": {')),
    ("K-88", "the Fiat receipt names a prover outside the locked build environment",
     _literal("tools/generated/fiat-crypto/manifest.json",
              '"prover": "9.3.0"', '"prover": "9.2.0"')),
    ("K-88", "the Fiat wrapper changed without regenerating its emission",
     _literal("tools/fiat_crypto_emit.py", "Inclusion wrapper added by VerifiedOS",
              "Inclusion wrapper revised by VerifiedOS")),
    ("K-88", "a device-register package recording an owner commit the Mocha gitlink "
             "does not carry",
     _first_match("rtl/vos_device_regs_pkg.sv",
                  r"^(// UART owner revision: upstream/mocha at )([0-9a-f])",
                  lambda m: m[1] + ("1" if m[2] != "1" else "2"))),
    ("K-88", "a block-contract register offset moved without regenerating the "
             "device-register package",
     _literal("interfaces/block-device-contract.md", "| `0x38` | `ACK` |",
              "| `0x40` | `ACK` |")),
    ("K-88", "the device-register generator's header changed without regenerating "
             "the package",
     _literal("tools/vos/device_regs.py",
              "from the owners below; rtl devicescheck checks it.",
              "from the owners below.")),
    ("K-94", "a devicetree node stating a neighbouring window instead of its own",
     _literal("model/model/postlude/device_tree.sail",
              "generate_dts_reg(plat_uart_base, plat_uart_size)",
              "generate_dts_reg(plat_blkdev_base, plat_uart_size)")),
    ("K-91", "a known answer one byte off in the Gallina transcription of FIPS 202",
     _literal(KECCAK_GALLINA, "0x17 :: 0x86 :: 0xA7 :: 0xB9", "0x17 :: 0x86 :: 0xA7 :: 0xBA")),

    ("K-107", "a published S-box byte off by one in the Gallina derivation of FIPS 197",
     _literal(AESGCM_GALLINA, "0x63 :: 0x7C :: 0x77 :: 0x7B", "0x63 :: 0x7C :: 0x77 :: 0x7A")),

    ("K-107", "a SHA-256 sigma rotation amount the model and the reference now spell apart",
     _literal(SHA256_GALLINA, "7 :: 18 :: 17 :: 19 :: nil", "7 :: 18 :: 17 :: 20 :: nil")),

    ("K-89", "a generated interface artifact whose width rule was narrowed by hand",
     _literal(RING_ARTIFACT,
              "if Nat.leb cases 256 then 1 else if Nat.leb cases 65536 then 2 else 4.",
              "if Nat.leb cases 255 then 1 else if Nat.leb cases 65536 then 2 else 4.")),

    ("K-99", "a wire-format row that stopped carrying a member the emitter encodes",
     _literal(IDL_PROFILE,
              "plus offset, length, direction, and declared content type",
              "plus offset, length, and declared content type")),

    ("K-99", "a width ladder whose stated ceiling is not the top rung it states",
     _literal(IDL_PROFILE, "its four-byte ceiling", "its two-byte ceiling")),

    ("K-100", "a lane fact naming a consumer the module it points at has renamed",
     _k100),

    ("K-101", "a device region the configuration template declares executable",
     _literal("model/config/config.json.in",
              '"executable": false', '"executable": true')),

    ("K-103", "a proof artifact citing a requirement id with two digits transposed",
     _k103),

    ("K-104", "a generated capability exception code changed in the RTL adapter",
     _literal("rtl/vos_cva6_cheri_pkg.sv", "CAP_EXCEPTION = 28;", "CAP_EXCEPTION = 29;")),

    ("K-108", "a derived region opened in a proof artifact and never closed",
     _literal(SEAM_WITNESSES, "   SeamWitnesses.v\n",
              f"   SeamWitnesses.v\n\n   {DERIVED_BEGIN}\n")),
    ("K-109", "a generated proof header changing its owner's fingerprint", _k109),
    ("K-110", "the shared agent instructions deleted from the tracked source",
     lambda box: box.delete("AGENTS.md")),
    ("K-114", "a declared proof campaign resting a result on libcrux's F* proof",
     _literal("proofs/campaigns/mldsa-reference.md",
              "carries no authorization for deterministic production signing.",
              "carries no authorization for deterministic production signing. Its "
              "signing path's functional correctness rests on libcrux's verified "
              "ML-DSA, whose F\\* proof this campaign takes as its premise.")),
    ("K-114", "a license-reference section acquiring an unlisted proof premise",
     _first_match(THIRD_PARTY, r"(?m)^\*\*Cryptography references\.\*\*[^\n]*",
                  lambda m: f"{m[0]}\nThe implementation's acceptance relies on HACL*'s proof.")),
    ("K-114", "a retained compressed record resting a result on an unlisted interim",
     _k114_compressed_premise),
    ("K-117", "a proof source the Wasm oracle compiles rewritten into Rocq 9.3's "
              "`if … is`",
     _literal("proofs/EndpointIPC.v", "  match l with nil => d | cons x _ => x end.",
              "  if l is cons x _ then x else d.")),
    ("K-117", "the Rupicola lowering's switch constant renamed out from under the "
              "instrument table", _k117_switch),
    ("K-117", "compare_component.py's release constant renamed out from under the "
              "instrument table", _k117_release),
    ("K-117", "the kernel's vector harness moved to the CertiRocq switch under a row "
              "stating the gate's",
     _literal("tools/vos/cli/kernel.py", "found = gallina.prover(gallina.VECTOR_SWITCH)",
              "found = gallina.prover(gallina.ORACLE_SWITCH)")),
    ("K-105", "a discharge annotation claiming an entry above a term rather than a "
              "statement",
     _literal(SEAM_WITNESSES, "Definition refutes_seam_ni_timing",
              "(*| discharges: R-05-160 |*)\nDefinition refutes_seam_ni_timing")),

    ("K-106", "a generated ledger row hand-promoted from cited to claimed",
     _literal(PROOF_LEDGER, "| n/a | cited |", "| n/a | claimed |")),
]

# Rules explicitly exempted from having a case in `CASES`.
UNSEEDABLE: dict[str, str] = {}


def _case_mutation(rule: str) -> Mutation:
    """Return the first `CASES` mutation for `rule`."""
    for ident, _, apply in CASES:
        if ident == rule:
            return apply
    raise SystemExit(f"no case to reuse as {rule}'s repair seed")


# Every rule with a `--fix` branch, mapped to `(expected_fixed_line_substring, seed_mutation)`.
# Rules whose primary `CASES` entry mutates an upstream owner (such as K-54's granule
# owner or K-57's register bound) use a derived-artifact seed here so `--fix` restores
# the pristine tree in one pass without dirtying co-read pairs.
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
    "K-95": ("standing", _case_mutation("K-95")),
    "K-82": ("findings the plan records", _k82_figure),
    "K-88": ("restored from the index", _case_mutation("K-88")),
    "K-106": ("ledger row", _case_mutation("K-106")),
    "K-109": ("generated requirement header", _case_mutation("K-109")),
    "K-104": ("generated capability exceptions", _case_mutation("K-104")),
}


# =====================================================================================
# Execution
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
    if repair_only:
        return True
    if shard is not None:
        return False
    return any(rule in REPAIRABLE for rule, _, _ in selected)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        suggest_on_error=True, description="Seed each checker rule a defect it must report.")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--rule", help="run one rule's case only")
    selection.add_argument("--shard", type=sharding.parse, metavar="INDEX/TOTAL",
                           help="run a disjoint partition of cases, without the repair path, "
                                "which --repair-only runs")
    selection.add_argument("--repair-only", action="store_true",
                           help="run the repair path beside the unmutated baseline, and no case")
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
    record = timings.claim()
    clock = timings.Clock(snapshot=record)

    sandbox = args.sandbox or Path(tempfile.mkdtemp(prefix="verifiedos-selftest-"))

    repo = corpus_mod.find_root()
    case_jobs = min(max(1, args.jobs), len(selected))
    jobs = max(1, case_jobs)
    width = jobs if selected else max(1, args.jobs)

    repairable = _needs_repair(selected, args.shard, args.repair_only)
    made: list[Sandbox] = []
    print(f"building {case_jobs + int(repairable)} sandbox(es) at {sandbox}")
    template = sandbox / "template"
    with clock.timing("phase", "template"):
        copied, carried = build_template(repo, template, width)
    print(f"placed {copied} file(s), {carried} carried from the previous run, "
          "indexed as the baseline")
    print()

    try:
        with clock.timing("phase", "checked bytecode"):
            _warm_bytecode(template, width)
        baseline = Sandbox(template, template)
        boxes: Queue[Sandbox | BaseException] = Queue()
        with ThreadPoolExecutor(max_workers=jobs) as setup:
            def later(i: int, *, fix_ok: bool = False) -> Sandbox:
                try:
                    with clock.timing("phase", f"sandbox w{i}"):
                        box = stand_up(template, sandbox / f"w{i}", fix_ok=fix_ok,
                                       jobs=width if not selected else 1)
                except BaseException as err:
                    if not fix_ok:
                        boxes.put(err)
                    raise
                made.append(box)
                if not box.fix_ok:
                    boxes.put(box)
                return box

            standing = [setup.submit(later, i) for i in range(case_jobs)]
            repair_ready = (setup.submit(later, case_jobs, fix_ok=True)
                            if repairable else None)
            if repair_ready is not None:
                standing.append(repair_ready)
            code = _run(selected, baseline, boxes, repair_ready, jobs, repairable, clock,
                        sharded=args.shard is not None, repair_only=args.repair_only)
            for future in standing:
                future.result()
        return code
    finally:
        started = time.perf_counter()
        if args.keep:
            print(f"sandboxes kept at {sandbox}")
        else:
            _publish(template, _cache_root(repo))
            _across(remove_tree, [box.path for box in made], jobs + 1)
            remove_tree(sandbox)
        clock.add("phase", "teardown", time.perf_counter() - started, started)
        timings.write(record, clock.units())


def _verdict(case: Case, box: Sandbox) -> Verdict:
    """Apply `case` to `box`, run `box.check`, and return its `Verdict`."""
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
    how = (f"other rules fired: {', '.join(failed)}" if failed
           else "the run was green" if code == 0
           else f"the run exited {code} with no finding, so the checker did not "
                "survive the mutant either")
    return Verdict(seeded, SURVIVED, how)


def _run(selected: list[Case], baseline: Sandbox, boxes: Queue[Sandbox | BaseException],
         repair_ready: Future[Sandbox] | None, jobs: int, repairable: bool | None = None,
         clock: timings.Clock | None = None, *, sharded: bool = False,
         repair_only: bool = False) -> int:
    if repair_only and (selected or repairable is False):
        raise ValueError("--repair-only runs the repair path and no case")
    measured = clock or timings.Clock()

    def one(case: Case) -> Verdict:
        box = boxes.get()
        if isinstance(box, BaseException):
            boxes.put(box)
            raise box
        with measured.timing("case", f"{case[0]}: {case[1]}"):
            try:
                return _verdict(case, box)
            finally:
                box.reset()
                boxes.put(box)

    def timed_repair() -> tuple[list[str], list[str]]:
        if repair_ready is None:
            raise ValueError("the repair path needs its private sandbox")
        with measured.timing("phase", "repair path"):
            return _repair_path(repair_ready)

    if repairable is None:
        repairable = repair_only or any(rule in REPAIRABLE for rule, _, _ in selected)
    with ThreadPoolExecutor(max_workers=jobs + 1) as pool:
        repairing = pool.submit(timed_repair) if repairable else None

        with measured.timing("phase", "baseline"):
            code, out, _ = baseline.check()
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
        with measured.timing("phase", "cases"):
            verdicts = list(pool.map(one, selected))
        repair: list[str] = []
        repair_out = ["--- the repair path ---",
                      "  skipped: this selection does not own the repair path"]
        if repairing is not None:
            repair, repair_out = repairing.result()

    report: list[str] = []
    cases_code = 0 if repair_only else summarize(report, verdicts, RULES, "checker")
    print(f"--- the mutation cases ---\n  skipped: --repair-only selects none of "
          f"{len(CASES)} case(s)" if repair_only else "\n".join(report))
    print()

    print("\n".join(repair_out))
    print()
    gaps = _registry_coverage(baseline)
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
        print(f"{len(CASES) - len(verdicts)} case(s) were not selected and decided "
              "nothing, so this run is about the selected case(s) alone.")
    return 0


def _copied_bytes(box: Sandbox) -> dict[str, bytes]:
    """Return `{rel: bytes}` for every non-`model/`, non-`.git/` file in `box`."""
    held: dict[str, bytes] = {}
    for dirpath, dirnames, filenames in box.path.walk():
        if dirpath == box.path:
            dirnames[:] = [d for d in dirnames if d not in (".git", "model")]
        if "__pycache__" in dirnames:
            dirnames.remove("__pycache__")
        for name in filenames:
            held[str((dirpath / name).relative_to(box.path))] = (dirpath / name).read_bytes()
    return held


def _bytes_moved(before: dict[str, bytes], after: dict[str, bytes]) -> list[str]:
    """Return sorted relative paths whose bytes differ between `before` and `after`."""
    differing = {rel for rel in before.keys() & after.keys() if before[rel] != after[rel]}
    return sorted((before.keys() ^ after.keys()) | differing)


def _header_require(condition: bool, message: str) -> None:
    """Raise `ValueError(message)` when `condition` is False."""
    if not condition:
        raise ValueError(message)


def _header_context(root: Path, *, fix: bool = False, snapshot: Context | None = None) -> Context:
    """Construct a fresh `Context` for `root`, optionally sharing `snapshot`'s loaded corpus."""
    if snapshot is None:
        corpus = corpus_mod.load(root)
        reg, art = read_register(corpus), read_artifacts(corpus)
    else:
        if snapshot.root != root:
            raise ValueError("proof-header snapshot belongs to a different root")
        corpus, reg, art = snapshot.corpus, snapshot.reg, snapshot.art
    return Context(root=root, corpus=corpus, reg=reg, art=art, rep=Reporter(), fix=fix)


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
    root = box.path
    baseline = _header_context(root)
    source_corpus = baseline.corpus
    rels = sorted(rel for rel in source_corpus.tracked if proofcites.is_source(rel))
    authored = set(rels) - proofheaders.EXCLUDED
    _header_require(bool(authored), "an empty proof corpus cannot witness header preservation")
    original = {rel: (root / rel).read_bytes()
                for rel in [REGISTER, *rels, memplan.ARTIFACT]}
    # Detach all subject files from template hardlinks before calling the repair planner.
    for rel, data in original.items():
        box.touched.add(rel)
        target = root / rel
        target.unlink()
        target.write_bytes(data)
    files = {rel: data.decode("utf-8") for rel, data in original.items()}
    identities = {rel: (set(proofcites.ids(files[rel])), proofs.sentences(files[rel]))
                  for rel in rels}
    row = next(row for row in generated.GENERATED if row.path == memplan.ARTIFACT)

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
    repaired_snapshot = _header_context(root)
    for fix in (False, True):
        after = _header_context(root, fix=fix, snapshot=repaired_snapshot)
        reading = generated._host_row(after, row, None)
        headers.run(after)
        _header_require(not reading.findings and after.rep.findings == 0,
                        f"the corpus did not converge after one repair: "
                        f"{reading.findings}, {after.rep.out}")
        _header_require(not after.fixed,
                        f"the converged corpus queued another repair: {sorted(after.fixed)}")
        _header_require(all((root / rel).read_bytes() == data for rel, data in original.items()),
                        "the converged checks changed the repaired snapshot's source bytes")
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
    """Verify `--fix` idempotence on the pristine tree, repair of all `REPAIRABLE` seeds,
    and post-repair idempotence."""
    box = ready.result()
    box.reset()
    problems: list[str] = []

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
    """Verify bidirectional coverage between the rule registry and `CASES` / `UNSEEDABLE`."""
    print("--- coverage of the registry ---")
    registered = sorted(checkregistry.read(box.path).identifiers)
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
