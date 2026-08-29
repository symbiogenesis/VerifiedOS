# SPDX-License-Identifier: Apache-2.0
"""The `coread` command end to end, in a sandbox checkout small enough to derive by hand.

Blessing is a judgment, so every mutating case here runs against a fixture tree and
never the live ledger. What is held: list mode is a worklist that exits 0 with pairs
pending, `--show` prints the two sides for one pair, several, or with `--all` every
pending pair in one read, `--where` names both sides' file:line sites so an editor
opens at the pair, `--bless` reaches a green list, a re-bless
of a current pair leaves the ledger's bytes and mtime alone (the write-path
fixpoint), `--bless --all` with nothing pending writes nothing, a stale row left by
a retired requirement is rebuilt away and the purge is reported even when nothing is
pending, a moved pair is owed a reading and one bless settles it, and each
flag-combination refusal exits nonzero with its own message rather than silently
dropping one act.

The subprocess runs a copy of the live sources materialized into the sandbox,
because the tool derives its root from its own file and the fixture must be that
root; the copy is read from the live tree at run time, so it is this checkout's
code that is tested.
"""

import json
import subprocess
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from tests.harness import TOOLS, Case, ensure, sandbox_tree

# The live sources the sandbox copy of the tool runs on, relative to the root.
_SOURCES = ("tools/run.py", "tools/vos/cli/__init__.py", "tools/vos/cli/coread.py",
            "tools/vos/__init__.py", "tools/vos/coread.py",
            "tools/vos/corpus.py", "tools/vos/register.py")

# Three entries in the register's own shape: body line, criterion, conferral on the
# third, trace. The parse anchors on these spellings, so the fixture keeps them.
_REGISTER = """\
# Requirements register (fixture)

## §1 Fixture obligations

**R-01-001** MUST hold the first fixture obligation.
· Accept: the first criterion is measured.
· Trace: [spec 1](spec.md#r-01-001)

**R-01-002** MUST hold the second fixture obligation.
· Accept: the second criterion is measured.
· Trace: [spec 1](spec.md#r-01-002)

**R-01-003** MUST NOT drop the third fixture obligation.
· Accept: the third criterion is measured.
· Fail-closed: refusal is the third obligation's failure mode.
· Trace: [spec 1](spec.md#r-01-003)
"""

# One bookmark per entry, each owning its own paragraph, so every pair's prose side
# is one derivable span.
_SPEC = """\
# Design (fixture)

## 1. The fixture claims

The first claim's prose stands here. <a id="r-01-001"></a>
It continues on a second line the same span owns.

The second claim's prose stands here. <a id="r-01-002"></a>

The third claim's prose stands here. <a id="r-01-003"></a>
"""


def _fixture() -> dict[str, str]:
    root = TOOLS.parent
    files = {rel: (root / rel).read_text(encoding="utf-8") for rel in _SOURCES}
    files["docs/requirements-register.md"] = _REGISTER
    files["docs/spec.md"] = _SPEC
    return files


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(root / "tools" / "run.py"), "coread", *args],
        capture_output=True, encoding="utf-8", errors="replace", check=False,
        timeout=120)


@dataclass
class _Flow:
    stack: ExitStack | None = None
    root: Path | None = None


_FLOW = _Flow()


def _root() -> Path:
    if _FLOW.root is None:
        raise AssertionError("the sandbox setup case did not run or did not survive")
    return _FLOW.root


def _ledger(root: Path) -> Path:
    return root / "tools" / "co-read.json"


def _list_pending() -> None:
    stack = ExitStack()
    _FLOW.stack = stack
    _FLOW.root = stack.enter_context(sandbox_tree(_fixture()))

    done = _run(_root())
    ensure(done.returncode == 0,
           f"list mode is a worklist and exits 0 with pairs pending, got "
           f"{done.returncode}: {done.stderr!r}")
    ensure("3 pair(s) owed a reading:" in done.stdout,
           f"three never-recorded pairs are owed, got {done.stdout!r}")
    for ident in ("R-01-001", "R-01-002", "R-01-003"):
        ensure(f"{ident:<12} never recorded" in done.stdout,
               f"{ident} must be listed as never recorded, got {done.stdout!r}")
    ensure(not _ledger(_root()).exists(), "listing must not create the ledger")


def _show_pair() -> None:
    done = _run(_root(), "--show", "R-01-001")
    ensure(done.returncode == 0, f"--show on a live pair exits 0, got {done.returncode}")
    ensure("=== R-01-001 ===" in done.stdout
           and "--- the prose it cites (never recorded) ---" in done.stdout
           and "The first claim's prose stands here." in done.stdout
           and "It continues on a second line the same span owns." in done.stdout
           and "--- the entry (never recorded) ---" in done.stdout
           and "**R-01-001** MUST hold the first fixture obligation." in done.stdout
           and "· Accept: the first criterion is measured." in done.stdout,
           f"--show must print both sides against each other, got {done.stdout!r}")
    ensure("R-01-002" not in done.stdout,
           f"--show prints one pair, not the register, got {done.stdout!r}")


def _show_several() -> None:
    done = _run(_root(), "--show", "R-01-001", "R-01-003")
    ensure(done.returncode == 0, f"--show on two live pairs exits 0, got {done.returncode}")
    ensure("=== R-01-001 ===" in done.stdout and "=== R-01-003 ===" in done.stdout
           and "R-01-002" not in done.stdout,
           f"--show prints the named pairs and no other, got {done.stdout!r}")
    ensure("record the readings with `python tools/run.py coread --bless "
           "R-01-001 R-01-003`." in done.stdout,
           f"several pairs end in one bless hint naming them all, got {done.stdout!r}")


def _show_all_pending() -> None:
    done = _run(_root(), "--show", "--all")
    ensure(done.returncode == 0, f"--show --all exits 0, got {done.returncode}")
    for ident in ("R-01-001", "R-01-002", "R-01-003"):
        ensure(f"=== {ident} ===" in done.stdout,
               f"--show --all covers every pending pair, {ident} missing: {done.stdout!r}")


def _where_pair() -> None:
    done = _run(_root(), "--where", "R-01-002")
    ensure(done.returncode == 0, f"--where on a live pair exits 0, got {done.returncode}")
    ensure("R-01-002:" in done.stdout
           and "docs/spec.md:8  #r-01-002" in done.stdout
           and "docs/requirements-register.md:9" in done.stdout,
           f"--where names both sides' file:line sites, got {done.stdout!r}")
    ensure("r-01-001" not in done.stdout and "r-01-003" not in done.stdout,
           f"--where prints one pair's sites, not the register's, got {done.stdout!r}")


def _bless_one_then_all() -> None:
    done = _run(_root(), "--bless", "R-01-001")
    ensure(done.returncode == 0
           and "recorded 1 co-read(s); the ledger now holds 1 of 3 pairs." in done.stdout,
           f"one bless records one pair, got {done.returncode}: {done.stdout!r}")

    listed = _run(_root())
    ensure(listed.returncode == 0 and "2 pair(s) owed a reading:" in listed.stdout
           and "R-01-001" not in listed.stdout,
           f"a blessed pair leaves the worklist, got {listed.stdout!r}")

    done = _run(_root(), "--bless", "--all")
    ensure(done.returncode == 0
           and "recorded 2 co-read(s); the ledger now holds 3 of 3 pairs." in done.stdout,
           f"--all records the pending remainder, got {done.returncode}: {done.stdout!r}")

    listed = _run(_root())
    ensure(listed.returncode == 0
           and "every one of the 3 pairs was last read as it now stands." in listed.stdout,
           f"a fully blessed ledger lists green, got {listed.stdout!r}")

    rows = json.loads(_ledger(_root()).read_text(encoding="utf-8"))
    ensure(list(rows) == ["R-01-001", "R-01-002", "R-01-003"],
           f"the ledger is rebuilt in register order, got {list(rows)!r}")
    ensure(all(len(pair) == 2 and all(len(d) == 12 for d in pair)
               for pair in rows.values()),
           f"every row is two 12-hex digests, got {rows!r}")


def _show_all_with_nothing_pending() -> None:
    done = _run(_root(), "--show", "--all")
    ensure(done.returncode == 0
           and "nothing pending; the ledger already stands as the pairs do." in done.stdout,
           f"--show --all with nothing pending says so, got {done.returncode}: "
           f"{done.stdout!r}")


def _rebless_is_a_fixpoint() -> None:
    ledger = _ledger(_root())
    before = ledger.read_bytes()
    stamp = ledger.stat().st_mtime_ns

    done = _run(_root(), "--bless", "R-01-001")
    ensure(done.returncode == 0, f"a re-bless exits 0, got {done.returncode}")
    ensure(ledger.read_bytes() == before,
           "a re-bless of a current pair must land on byte-identical ledger content")
    ensure(ledger.stat().st_mtime_ns == stamp,
           "a write that would change nothing is skipped, so the mtime stands")


def _bless_all_with_nothing_pending() -> None:
    ledger = _ledger(_root())
    before = ledger.read_bytes()
    stamp = ledger.stat().st_mtime_ns

    done = _run(_root(), "--bless", "--all")
    ensure(done.returncode == 0
           and "nothing pending; the ledger already stands as the pairs do." in done.stdout,
           f"--all with nothing pending says so, got {done.returncode}: {done.stdout!r}")
    ensure(ledger.read_bytes() == before and ledger.stat().st_mtime_ns == stamp,
           "--all with nothing pending must write nothing")


def _stale_row_purged() -> None:
    # A retired requirement's row, injected as a strike would leave it: every pair
    # blessed, nothing pending, and K-61 red on the row alone. `--bless --all` is the
    # one command that purges it, so it must rebuild here rather than answer
    # "nothing pending".
    ledger = _ledger(_root())
    text = ledger.read_text(encoding="utf-8")
    ledger.write_text(
        text.replace('\n}', ',\n  "R-99-999": ["aaaaaaaaaaaa", "bbbbbbbbbbbb"]\n}'),
        encoding="utf-8", newline="")

    listed = _run(_root())
    ensure("1 ledger row(s) naming no live requirement: R-99-999" in listed.stdout,
           f"the stale row must be listed before the purge, got {listed.stdout!r}")

    done = _run(_root(), "--bless", "--all")
    ensure(done.returncode == 0
           and "recorded 0 co-read(s); the ledger now holds 3 of 3 pairs." in done.stdout
           and "purged 1 stale row(s) naming no live requirement: R-99-999" in done.stdout,
           f"a stale row alone still wants the rebuild, got {done.returncode}: "
           f"{done.stdout!r}")
    ensure("R-99-999" not in ledger.read_text(encoding="utf-8"),
           "the purged row must be gone from the ledger")

    listed = _run(_root())
    ensure("every one of the 3 pairs was last read as it now stands." in listed.stdout,
           f"the purge must end green, got {listed.stdout!r}")


def _moved_pair_owed_then_settled() -> None:
    # A prose edit under one bookmark dirties exactly that pair, and one bless
    # settles it: the fixpoint from a dirty state, not merely from green.
    spec = _root() / "docs" / "spec.md"
    text = spec.read_text(encoding="utf-8")
    spec.write_text(
        text.replace("The second claim's prose stands here.",
                     "The second claim's prose stands here, reworded."),
        encoding="utf-8", newline="")

    listed = _run(_root())
    ensure(listed.returncode == 0 and "1 pair(s) owed a reading:" in listed.stdout
           and f"{'R-01-002':<12} prose changed" in listed.stdout,
           f"the reworded span dirties its own pair alone, got {listed.stdout!r}")

    shown = _run(_root(), "--show", "R-01-002")
    ensure("(CHANGED since the last reading)" in shown.stdout
           and "(unchanged)" in shown.stdout,
           f"--show must say which side moved, got {shown.stdout!r}")

    done = _run(_root(), "--bless", "R-01-002")
    ensure(done.returncode == 0, f"blessing the moved pair exits 0, got {done.returncode}")
    listed = _run(_root())
    ensure("every one of the 3 pairs was last read as it now stands." in listed.stdout,
           f"one bless settles the moved pair, got {listed.stdout!r}")


def _refusals() -> None:
    # Each flag names a different act, so every combination that would drop one
    # silently is refused by name instead.
    for args, message in (
        (("--show", "R-01-001", "--bless", "R-01-002"),
         "--show and --bless are different acts: run one, then the other"),
        (("--where", "R-01-001", "--bless", "R-01-002"),
         "--where and --bless are different acts: run one, then the other"),
        (("--show", "R-01-001", "--where", "R-01-002"),
         "--show and --where are different acts: run one, then the other"),
        (("--all",), "--all covers pending pairs and needs --show or --bless"),
        (("--where", "R-01-001", "--all"),
         "--all covers pending pairs and needs --show or --bless"),
        (("--bless", "R-01-001", "--all"), "--bless takes explicit ids or --all, not both"),
        (("--show", "R-01-001", "--all"), "--show takes explicit ids or --all, not both"),
        (("--bless",), "--bless needs an id, or --all to record every pending pair"),
        (("--show", ""), "--show needs a requirement id"),
        (("--where", ""), "--where needs a requirement id"),
        (("--bless", "R-77-777"), "no requirement in the register: R-77-777"),
        (("--show", "R-77-777"), "no requirement 'R-77-777' in the register"),
        (("--where", "R-77-777"), "no requirement 'R-77-777' in the register"),
    ):
        done = _run(_root(), *args)
        ensure(done.returncode != 0 and message in done.stderr,
               f"co-read.py {' '.join(args)!r} must refuse with {message!r}, got "
               f"{done.returncode}: {done.stderr!r}")


def _teardown() -> None:
    if _FLOW.stack is not None:
        _FLOW.stack.close()
        _FLOW.stack = None
        _FLOW.root = None


def cases() -> list[Case]:
    # the first case stands the shared sandbox up and the last takes it down; the
    # cases between run in order and each leaves the state the next one starts from
    return [
        Case("list-pending", _list_pending, lane="host"),
        Case("show-pair", _show_pair, lane="host"),
        Case("show-several", _show_several, lane="host"),
        Case("show-all-pending", _show_all_pending, lane="host"),
        Case("where-pair", _where_pair, lane="host"),
        Case("bless-one-then-all", _bless_one_then_all, lane="host"),
        Case("show-all-with-nothing-pending", _show_all_with_nothing_pending, lane="host"),
        Case("rebless-is-a-fixpoint", _rebless_is_a_fixpoint, lane="host"),
        Case("bless-all-with-nothing-pending", _bless_all_with_nothing_pending, lane="host"),
        Case("stale-row-purged", _stale_row_purged, lane="host"),
        Case("moved-pair-owed-then-settled", _moved_pair_owed_then_settled, lane="host"),
        Case("refusals", _refusals, lane="host"),
        Case("teardown", _teardown, lane="host"),
    ]
