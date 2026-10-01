# SPDX-License-Identifier: Apache-2.0
"""The provisioner, and idempotence held rather than claimed.

`run.py provision` states the lane as a table of facts, and the property that matters
about it is that a run against a machine already satisfying the table plans nothing and
changes nothing. That property is about the mapping from what a probe saw to what would
be run, so it is held over **injected** tables whose probes answer what a case chose,
never over the live machine: a table read off this box says only that this box is
provisioned, which is the acceptance evidence and not a test.

What the live table is held to is the shape every row owes, that each names the loop
wanting it and the artifact owning it and that no two rows share a name, because a row
is only worth having if a reader can act on its finding.

The one case that runs the command is the guest's, doubled and bracketed by
`git status --porcelain` in [test_entrypoints.py](test_entrypoints.py)'s shape: a
`--check` run is read-only or it is lying, and a probe that quietly wrote would be
exactly the defect this tool exists not to be.
"""

import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from tests.test_opam_client import opam_root
from vos import cli, env, opam_client
from vos.cli import provision, rtl, typecheck
from vos.report import Reporter

_ROOT = TOOLS.parent


def _answer(present: bool, saw: str) -> provision.Found:
    """A probe that says what a case chose, so a table describes a hypothetical
    machine rather than this one."""
    return provision.Found(present, saw)


def _fact(name: str, *, present: bool, install: tuple[tuple[str, ...], ...] = (),
          group: str = provision.GATE) -> provision.Fact:
    return provision.Fact(
        name=name, group=group, needs=f"the loop that wants {name}",
        owner=f"the artifact that fixes {name}",
        probe=lambda: _answer(present, f"{name} as this case chose it"),
        install=install)


_HERE = (("do", "the", "install"),)


def _satisfied_plans_nothing() -> None:
    """Idempotence, stated as the property it is: a satisfied probe yields no work."""
    table = (_fact("first", present=True, install=_HERE),
             _fact("second", present=True, install=_HERE, group=provision.TOOLCHAIN))
    results = provision.take(table)
    ensure(provision.plan(results) == [],
           f"every fact present must plan nothing, planned {provision.plan(results)!r}")
    report = provision.run(table)
    ensure(report.findings == 0, f"a satisfied table is clean, got {report.findings}")


def _absent_plans_its_own_command() -> None:
    table = (_fact("here", present=True, install=_HERE),
             _fact("gone", present=False, install=_HERE))
    planned = provision.plan(provision.take(table))
    ensure([fact.name for fact, _ in planned] == ["gone"],
           f"only the absent fact is planned, planned {[f.name for f, _ in planned]}")
    ensure([commands for _, commands in planned] == [_HERE],
           f"a planned fact contributes exactly its own argv, got {planned!r}")


def _absent_without_a_command_reports_only() -> None:
    """A row this tree states no command for is a finding and not a repair.

    The two halves are held apart on purpose. An empty plan because everything is
    satisfied and an empty plan because nothing may be done are the same list and
    opposite verdicts, so the verdict is what tells them apart.
    """
    table = (_fact("unownable", present=False),)
    ensure(provision.plan(provision.take(table)) == [],
           "a fact with no stated command plans nothing")
    report = provision.run(table)
    ensure(report.findings == 1, f"and still fails the run, got {report.findings}")
    said = "\n".join(report.out)
    ensure("plans nothing" in said,
           f"and says why there is nothing to run, said {said!r}")


def _verdict_is_the_exit_code() -> None:
    """The conventions fix 0 clean and 1 a finding, and this is that mapping."""
    clean = provision.run((_fact("here", present=True),))
    ensure(clean.findings == 0, "a clean run finds nothing")
    red = provision.run((_fact("here", present=True), _fact("gone", present=False)))
    ensure(red.findings == 1, f"one absent fact is one finding, got {red.findings}")
    both = provision.run((_fact("a", present=False), _fact("b", present=False)))
    ensure(both.findings == 2, f"two absent facts are two, got {both.findings}")


def _report_is_deterministic() -> None:
    """The probes run concurrently and the report does not: a person reading a run
    twice must read one report, and the order two subprocesses finished in is not a
    property of the machine being described."""
    table = tuple(_fact(f"row-{n}", present=n % 3 != 0, install=_HERE)
                  for n in range(12))
    first = provision.run(table).out
    second = provision.run(table).out
    ensure(first == second, "two runs of one table must print one report")
    names = [line.split(":")[0].removeprefix("ok ").removeprefix("FAIL ").strip()
             for line in first if line.startswith(("ok ", "FAIL "))]
    ensure(names == [fact.name for fact in table],
           f"and in the table's own order, got {names}")


def _only_narrows_and_says_what_it_skipped() -> None:
    """A narrowed run says what it did not decide, which is S13b's rule for `--rule`
    read one instrument over: a gate exiting 0 over a subset while leaving rows
    unprobed would be a gate that lies about its own reach."""
    table = (_fact("gated", present=False, group=provision.GATE),
             _fact("chained", present=False, group=provision.TOOLCHAIN))
    report = provision.run(table, group=provision.GATE)
    said = "\n".join(report.out)
    ensure(report.findings == 1,
           f"the narrowed run decides its own group alone, got {report.findings}")
    ensure("chained" in said and "did not run" in said,
           f"and names the rows it did not decide about, said {said!r}")


def _every_row_is_actionable() -> None:
    """The live table's own shape. A finding a reader cannot act on is not worth
    printing, so every row names the loop that wants the fact and the artifact that
    fixes it, and no two rows share the name a finding is filed under."""
    names = [fact.name for fact in provision.FACTS]
    ensure(len(names) == len(set(names)), f"row names must be unique, got {names}")
    ensure(bool(provision.FACTS), "an empty table would report nothing about anything")
    for fact in provision.FACTS:
        ensure(bool(fact.needs), f"{fact.name} names no loop that wants it")
        ensure(bool(fact.owner), f"{fact.name} names no artifact that fixes it")
        ensure(fact.group in provision.GROUPS,
               f"{fact.name} is in group {fact.group!r}, which --only cannot ask for")


def _versions_are_read_and_not_typed() -> None:
    """The whole point of the table: a pin appears in a row because it was imported.

    Held by the value rather than by inspection, each of these being the constant its
    own owner fixes. A row that had been hand-typed would pass today and drift on the
    first bump, which is the defect this repository exists to catch.
    """
    said = "\n".join(fact.owner + " " + fact.needs + " " +
                     " ".join(" ".join(step) for step in fact.install)
                     for fact in provision.FACTS)
    for pin in (typecheck.TY_VERSION, typecheck.RUFF_VERSION, env.SAIL_VERSION,
                env.Z3_VERSION, env.ROCQ_VERSION, rtl.VERILATOR_PIN):
        ensure(pin in said, f"the table no longer carries {pin}, so a row stopped "
                            "reading the constant that fixes it")


def _number_reads_the_banners() -> None:
    """The three shapes a version arrives in here, and the one that decides the
    pattern: `Z3 version 5.1.0` opens with a digit inside the tool's own name."""
    ensure(provision._number("Z3 version 5.1.0 - 64 bit") == "5.1.0",
           "a digit in the tool's name must not be read as its version")
    ensure(provision._number("Verilator 5.032 2025-01-01 rev (Debian 5.032-1)")
           == "5.032", "the first dotted number is the version")
    ensure(provision._number("0.9.1+9.1") == "0.9.1",
           "opam's build suffix is not part of the version")
    ensure(provision._number("no version here") == "",
           "a banner with no dotted number yields none rather than a fragment")


def _probes_answer_no_question() -> None:
    """A probe's subprocess reads no standard input and inherits no answer from the
    caller's environment, so a question opam asks before an upgrade it would write is
    declined rather than left to the caller's terminal or settings; the rest of the
    environment, the root a probe reads among it, is passed on."""
    answers = {"OPAMYES": "1", "OPAMCONFIRMLEVEL": "unsafe-yes", "OPAMROOT": "/elsewhere"}
    with (patch.dict(os.environ, answers),
          patch.object(provision.subprocess, "run",
                       return_value=subprocess.CompletedProcess(["opam"], 0, "2.6.0\n")) as run):
        ensure(provision._say(("opam", "switch", "list", "--short")) == "2.6.0",
               "the probe still reads the command's standard output")
    passed = run.call_args.kwargs.get("env") or {}
    ensure(run.call_args.kwargs.get("stdin") is subprocess.DEVNULL,
           f"the probe's standard input is closed: {run.call_args}")
    ensure(not {key.upper() for key in passed} & set(env.OPAM_ANSWERS)
           and passed.get("OPAMROOT") == "/elsewhere",
           f"the probe passes on no answer and keeps the root: {sorted(passed)}")


def _opam_probe_preserves_build_suffix() -> None:
    with (tempfile.TemporaryDirectory(prefix="vos-test-") as td,
          patch.object(provision.env, "opam_root", return_value=Path(td) / "absent"),
          patch.object(provision, "switches", return_value={"oracle"}),
          patch.object(provision, "_installed", return_value="0.9.1+9.1")):
        ensure(provision._switch_at("oracle", "rocq-certirocq", "0.9.1+9.1").present,
               "an exact opam version including its Rocq suffix must satisfy the pin")
        ensure(not provision._switch_at("oracle", "rocq-certirocq", "0.9.1+9.2").present,
               "the same release built for another Rocq version must be rejected")


def _opam_root_fixture(root: Path) -> None:
    """A root in opam's own layout: one repository unpacked, the other tarred."""
    (root / "config").write_text('opam-version: "2.0"\nopam-root-version: "2.2"\n',
                                 encoding="utf-8")
    repo = root / "repo"
    (repo / "default").mkdir(parents=True)
    (repo / "repos-config").write_text(
        'opam-version: "2.0"\nrepositories: [\n  "default" {"https://opam.ocaml.org"}\n'
        '  "rocq-released" {"https://rocq-prover.org/opam/released"}\n]\n', encoding="utf-8")
    (repo / "default" / "repo").write_text('opam-version: "2.0"\nstamp: "44871cd5"\n',
                                           encoding="utf-8")
    payload = b'opam-version: "2.0"\nstamp: "2026-09-29 06:07"\n'
    with tarfile.open(repo / "rocq-released.tar.gz", "w:gz") as archive:
        member = tarfile.TarInfo("rocq-released/repo")
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))


def _opam_probe(root: Path, where: str | None, version: str = "") -> provision.Found:
    """The opam row's probe on a machine the case describes: a client at `where`
    answering `version`, over the root at `root`."""
    with (patch.object(provision, "shutil", SimpleNamespace(which=lambda name: where)),
          patch.object(provision, "env", SimpleNamespace(opam_root=lambda: root)),
          patch.object(provision, "_say", return_value=version)):
        return provision._opam_client()


def _opam_probe_holds_the_reviewed_client() -> None:
    """The client on PATH is held to the reviewed release, and the report says what a
    reader needs to act on a mismatch: where the client and its root are, the root's
    format, and each repository's URL and metadata stamp. A client at another release
    is not repairable: moving a developer's root to another client is a recorded step."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        _opam_root_fixture(root)
        for version, present in (("2.5.0", False), (opam_client.OPAM_VERSION, True)):
            found = _opam_probe(root, "/usr/bin/opam", version)
            ensure(found.present is present, f"opam {version} must read present={present}")
            for fragment in (f"opam {version} at /usr/bin/opam", "format 2.2",
                             "default https://opam.ocaml.org at stamp 44871cd5",
                             "rocq-released https://rocq-prover.org/opam/released at stamp "
                             "2026-09-29 06:07"):
                ensure(fragment in found.saw, f"the report must say {fragment!r}: {found.saw}")
            ensure(present or (f"the reviewed client is {opam_client.OPAM_VERSION}" in found.saw
                               and f"from 2.2 to {opam_client.OPAM_ROOT_FORMAT} one way"
                               in found.saw),
                   f"a mismatch names the reviewed client and the cost of moving: {found.saw}")
        # The cost is stated only where there is one: a root already in the reviewed
        # client's format is not rewritten by moving to it, and a newer one is a gap of
        # the root's own, which the reviewed client refuses to write to.
        for fmt, clause in ((opam_client.OPAM_ROOT_FORMAT, ""),
                            ("99.0", "the root is in format 99.0, newer than the reviewed "
                                     f"client's {opam_client.OPAM_ROOT_FORMAT}")):
            (root / "config").write_text(f'opam-root-version: "{fmt}"\n', encoding="utf-8")
            found = _opam_probe(root, "/usr/bin/opam", "2.5.0")
            ensure(not found.present and f"format {fmt};" in found.saw
                   and "one way" not in found.saw and clause in found.saw,
                   f"a root of format {fmt} is reported without an upgrade: {found.saw}")
            ensure(not found.repairable, "a client at another release is never replaced")
        found = _opam_probe(Path(td) / "absent", None)
        ensure(not found.present and found.repairable and "no opam on PATH" in found.saw
               and f"no opam root at {Path(td) / 'absent'}" in found.saw,
               f"an absent client and root are reported as absent and installable: {found.saw}")
    row = next(fact for fact in provision.FACTS if fact.name == "opam")
    ensure(row.probe is provision._opam_client
           and row.install == (tuple(cli.entry("provision", "--install-opam")),)
           and "tools/vos/opam_client.py" in row.owner,
           "the opam row probes the reviewed client, names its owner and installs it "
           "by provision's own command")


def _opam_probe_holds_the_root() -> None:
    """The row holds only where a root stands complete: stating a format no newer than
    the reviewed client's and carrying each owned repository at its URL with its stamp
    read. An absent root is repairable, since the command creates one, and so is one in
    the shape the root-creation route leaves after its leading steps, which running it
    again completes; any other standing root it would leave incomplete is reported, never planned,
    whether or not a client is on PATH, and so is one in a format the reviewed client
    refuses to write to."""
    (default, url), *others = opam_client.OPAM_REPOSITORIES
    reviewed = opam_client.OPAM_VERSION
    missing = ", ".join(f"{name} {address}" for name, address in others)
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        absent = Path(td) / "absent"
        found = _opam_probe(absent, "/usr/bin/opam", reviewed)
        ensure(not found.present and found.repairable
               and f"no opam root at {absent}" in found.saw,
               f"the reviewed client with no root is absent and repairable: {found.saw}")
        partial = Path(td) / "partial"
        opam_root(partial, "flat", configured=((default, url),))
        for where, version in (("/usr/bin/opam", reviewed), (None, "")):
            found = _opam_probe(partial, where, version)
            ensure(not found.present and found.repairable
                   and f"the root lacks {missing}, in the shape the root-creation route "
                       "leaves after its leading steps, which that route's remaining "
                       "steps complete" in found.saw,
                   f"a root in the shape the route leaves after its leading steps is "
                   f"repairable, with the client at {where}: {found.saw}")
        # An addition stopped during its fetch leaves its repository configured and
        # unread, which running that addition again fetches.
        stopped = Path(td) / "stopped"
        opam_root(stopped, "flat", stamps={default: "s"})
        unread = ", ".join(name for name, _ in others)
        for where, version in (("/usr/bin/opam", reviewed), (None, "")):
            found = _opam_probe(stopped, where, version)
            ensure(not found.present and found.repairable
                   and f"the root records no metadata stamp for {unread}, in the shape the "
                       "root-creation route leaves after its leading steps" in found.saw,
                   f"a root whose addition stopped during its fetch is repairable, with "
                   f"the client at {where}: {found.saw}")
        unformatted = Path(td) / "unformatted"
        opam_root(unformatted, "flat")
        (unformatted / "config").write_text('opam-version: "2.0"\n', encoding="utf-8")
        older = Path(td) / "older"
        opam_root(older, "nested", configured=((default, url),))
        lacking = Path(td) / "lacking"
        opam_root(lacking, "flat", configured=tuple(others))
        newer = Path(td) / "newer"
        opam_root(newer, "flat")
        (newer / "config").write_text('opam-root-version: "99.0"\n', encoding="utf-8")
        unstamped = Path(td) / "unstamped"
        opam_root(unstamped, "flat", stamps={name: "s" for name, _ in others})
        for incomplete, fragment in (
                (unformatted, "the root states no format"),
                (older, f"the root lacks {missing}"),
                (lacking, f"the root lacks {default} {url}"),
                (newer, "the root is in format 99.0, newer than the reviewed client's "
                        f"{opam_client.OPAM_ROOT_FORMAT}, which refuses to write to it"),
                (unstamped, f"the root records no metadata stamp for {default}")):
            for where, version in (("/usr/bin/opam", reviewed), (None, "")):
                found = _opam_probe(incomplete, where, version)
                ensure(not found.present and not found.repairable and fragment in found.saw
                       and "a standing root is left as it is unless it is in the shape "
                           "the root-creation route leaves after its leading steps"
                       in found.saw,
                       f"an incomplete root is reported and never planned, with the client "
                       f"at {where}: {found.saw}")
        complete = Path(td) / "complete"
        opam_root(complete, "flat")
        found = _opam_probe(complete, None)
        ensure(not found.present and found.repairable and "one way" not in found.saw,
               f"a complete root in the reviewed format needs only the client: {found.saw}")
        # Installing the reviewed client over a complete root in an older format
        # rewrites that root one way, which is a recorded step rather than a repair.
        older_complete = Path(td) / "older-complete"
        opam_root(older_complete, "nested")
        found = _opam_probe(older_complete, None)
        ensure(not found.present and not found.repairable
               and f"from 2.2 to {opam_client.OPAM_ROOT_FORMAT} one way, a deliberate, "
                   "recorded step rather than a repair" in found.saw,
               f"no client over a complete older root is reported, never planned: {found.saw}")
        # The reviewed client over a complete root holds the row, and over an older one
        # the report says that client rewrites it one way at its first write.
        rewrite = (f"that client rewrites this root from format 2.2 to "
                   f"{opam_client.OPAM_ROOT_FORMAT} one way at its first write")
        for held, rewritten in ((complete, False), (older_complete, True)):
            found = _opam_probe(held, "/usr/bin/opam", reviewed)
            ensure(found.present and (rewrite in found.saw) is rewritten
                   and ("one way" in found.saw) is rewritten,
                   f"the reviewed client over a complete {held.name} root holds: {found.saw}")


def _opam_row_plans_only_what_is_absent() -> None:
    """The opam row's command runs where a client or a root is absent, or the root is
    in the shape the root-creation route leaves after its leading steps, and nothing
    that stands is other than the lane's: a client at another release, no client over
    a complete root in an older format, and any other incomplete root are findings the
    run reports and plans nothing for."""
    reviewed = opam_client.OPAM_VERSION
    row = next(fact for fact in provision.FACTS if fact.name == "opam")
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        complete, partial = Path(td) / "complete", Path(td) / "partial"
        older, newer = Path(td) / "older", Path(td) / "newer"
        older_complete = Path(td) / "older-complete"
        opam_root(complete, "flat")
        opam_root(older_complete, "nested")
        opam_root(partial, "flat", configured=opam_client.OPAM_REPOSITORIES[:1])
        opam_root(older, "nested", configured=opam_client.OPAM_REPOSITORIES[:1])
        opam_root(newer, "flat")
        (newer / "config").write_text('opam-root-version: "99.0"\n', encoding="utf-8")
        for where, version, root, planned in (
                (None, "", Path(td) / "absent", True), (None, "", complete, True),
                (None, "", older_complete, False),
                ("/usr/bin/opam", reviewed, Path(td) / "absent", True),
                ("/usr/bin/opam", "2.5.0", Path(td) / "absent", False),
                ("/usr/bin/opam", "2.5.0", complete, False),
                ("/usr/bin/opam", reviewed, partial, True), (None, "", partial, True),
                ("/usr/bin/opam", "2.5.0", partial, False),
                ("/usr/bin/opam", reviewed, older, False), (None, "", older, False),
                ("/usr/bin/opam", reviewed, newer, False), (None, "", newer, False)):
            with (patch.object(provision, "shutil", SimpleNamespace(which=lambda name, at=where: at)),
                  patch.object(provision.env, "opam_root", return_value=root),
                  patch.object(provision, "_say", return_value=version)):
                results = provision.take((row,))
                report = provision.run((row,))
            case = f"opam {version or 'absent'} at {where} over {root.name}"
            ensure(bool(provision.plan(results)) is planned,
                   f"with {case}, the row plans {provision.plan(results)}")
            said = "\n".join(report.out)
            ensure(report.findings == 1 and ("--install-opam" in said)
                   and (planned or "does not run over what is there" in said),
                   f"with {case}, the report names the command: {said}")


def _switch_rows_wait_on_an_older_root() -> None:
    """An absent switch is planned over no root or one in the reviewed client's format,
    with the reviewed client or no client on PATH, since the opam row installs the
    reviewed one in the same pass; never over a root in an older format, which the
    reviewed client rewrites one way at its first write, nor while a client at another
    release is on PATH, which would build it as a client this tree has not reviewed. A
    switch already there still reads present."""
    row = next(fact for fact in provision.FACTS if fact.name == "the Sail switch")
    reviewed = ("/usr/bin/opam", opam_client.OPAM_VERSION)
    other: tuple[str | None, str] = ("/usr/bin/opam", "2.5.0")
    nothing: tuple[str | None, str] = (None, "")
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        absent = Path(td) / "absent"
        current, older = Path(td) / "current", Path(td) / "older"
        opam_root(current, "flat")
        opam_root(older, "nested")
        for root, carried, client, present, planned in (
                (absent, (), nothing, False, True), (absent, (), reviewed, False, True),
                (absent, (), other, False, False), (current, (), nothing, False, True),
                (current, (), reviewed, False, True), (current, (), other, False, False),
                (older, (), reviewed, False, False), (older, (), nothing, False, False),
                (older, (env.SAIL_SWITCH,), reviewed, True, False),
                (current, (env.SAIL_SWITCH,), reviewed, True, False),
                (current, (env.SAIL_SWITCH,), other, True, False)):
            with (patch.object(provision.env, "opam_root", return_value=root),
                  patch.object(provision, "switches", return_value=carried),
                  patch.object(provision, "_client", return_value=client),
                  patch.object(provision, "_installed", return_value=env.SAIL_VERSION)):
                results = provision.take((row,))
                report = provision.run((row,))
            found = results[0][1]
            case = f"with the switches {carried} and the client {client} over the {root.name} root"
            ensure(found.present is present and bool(provision.plan(results)) is planned,
                   f"{case}, the row reads {found} and plans {provision.plan(results)}")
            said = "\n".join(report.out)
            older_clause = (f"rewrites the opam root at {older} from format 2.2 to "
                            f"{opam_client.OPAM_ROOT_FORMAT} one way at its first write")
            other_clause = ("opam 2.5.0 at /usr/bin/opam would build it, and the reviewed "
                            f"client is {opam_client.OPAM_VERSION}, so no switch is planned")
            ensure((older_clause in said) is (root == older and not present)
                   and (other_clause in said) is (client == other and not present)
                   and (present or planned or "does not run over what is there" in said),
                   f"{case}, the report names the rewrite or the client only where it holds "
                   f"back a recipe: {said}")


def _unread_switch_is_not_absent() -> None:
    """Over a root in an older format, a switch the root's own config lists is reported
    as unread rather than absent, and still planned nothing, naming who listed nothing:
    no client on PATH; the reviewed client, which lists no switch without the upgrade it
    must write first over a root whose repository archive is nested, and declines it; or
    any other empty listing, another client's or the reviewed client's over a root it
    upgrades in memory, with the client and the root's format. Where the config lists
    the switch not, or the root is in the reviewed format, opam's empty listing is read
    as it stands."""
    row = next(fact for fact in provision.FACTS if fact.name == "the Sail switch")
    switch = env.SAIL_SWITCH
    listed = f'installed-switches: ["default" "{switch}"]\n'
    reviewed: tuple[str | None, str] = ("/usr/bin/opam", opam_client.OPAM_VERSION)
    other: tuple[str | None, str] = ("/usr/bin/opam", "2.5.0")
    nothing: tuple[str | None, str] = (None, "")
    declined = ("opam listed no switches without upgrading the root, whose config lists "
                f"the {switch} switch")
    absent = f"opam has no {switch} switch"
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        roots: dict[str, Path] = {}
        for name, layout, config in (("older-listing", "nested", listed),
                                     ("older-unpacked", "unpacked", listed),
                                     ("older-unlisted", "nested", ""),
                                     ("current-listing", "flat", listed)):
            roots[name] = Path(td) / name
            opam_root(roots[name], layout)
            with (roots[name] / "config").open("a", encoding="utf-8", newline="") as stream:
                stream.write(config)
        for name, client, said in (
                ("older-listing", reviewed, declined),
                ("older-listing", nothing, "no opam on PATH lists switches; the root's "
                                           f"config lists the {switch} switch"),
                ("older-listing", other, "opam 2.5.0 listed no switches over this root in "
                                         f"format 2.2, whose config lists the {switch} "
                                         "switch"),
                ("older-unpacked", reviewed, f"opam {opam_client.OPAM_VERSION} listed no "
                                             "switches over this root in format 2.2, whose "
                                             f"config lists the {switch} switch"),
                ("older-unlisted", reviewed, absent), ("older-unlisted", nothing, absent),
                ("current-listing", reviewed, absent)):
            with (patch.object(provision.env, "opam_root", return_value=roots[name]),
                  patch.object(provision, "switches", return_value=()),
                  patch.object(provision, "_client", return_value=client)):
                results = provision.take((row,))
            found = results[0][1]
            older = name.startswith("older")
            ensure(not found.present and found.saw.startswith(said + (";" if older else ""))
                   and (declined in found.saw) is (said == declined)
                   and (not found.repairable) is older,
                   f"over the {name} root with the client {client} the row reads {found}")


def _hard_upgrade_is_read_from_the_root() -> None:
    """Whether the reviewed client must write an older root's upgrade before it reads it
    is read as opam 2.6.0 decides it: from the root's format alone below 2.0~beta5 and
    at 2.1~alpha and 2.1~alpha2, and below 2.6~alpha where the first regular file of a
    configured repository's archive, read in name order, is neither `repo` nor under
    `packages/`; an archive the client fails on first stops the reading undecided, and
    another reviewed release claims nothing until its own source is read."""
    regular, folder, link = tarfile.REGTYPE, tarfile.DIRTYPE, tarfile.SYMTYPE

    def root_at(at: Path, fmt: str,
                archives: dict[str, tuple[tuple[str, bytes], ...] | None]) -> Path:
        """A root in format `fmt` configuring each of `archives`' repositories, each
        archive's members in order, or no archive where it maps to None."""
        (at / "repo").mkdir(parents=True)
        (at / "config").write_text(f'opam-version: "2.0"\nopam-root-version: "{fmt}"\n',
                                   encoding="utf-8")
        listing = "".join(f'  "{name}" {{"https://example.invalid/{name}"}}\n'
                          for name in archives)
        (at / "repo" / "repos-config").write_text(
            f'opam-version: "2.0"\nrepositories: [\n{listing}]\n', encoding="utf-8")
        for name, members in archives.items():
            if members is None:
                continue
            with tarfile.open(at / "repo" / f"{name}.tar.gz", "w:gz") as archive:
                for member_name, kind in members:
                    member = tarfile.TarInfo(member_name)
                    member.type = kind
                    data = b"x" if kind == regular else b""
                    member.size = len(data)
                    if kind == link:
                        member.linkname = "elsewhere"
                    archive.addfile(member, io.BytesIO(data))
        return at

    nested = (("default/", folder), ("default/repo", regular))
    flat = (("packages/", folder), ("packages/p/p.1/opam", regular), ("repo", regular))
    cases: tuple[tuple[str, str, dict[str, tuple[tuple[str, bytes], ...] | None], bool],
                 ...] = (
        ("older than 2.0~beta5", "2.0~beta", {"default": None}, True),
        ("an early 2.1 prerelease", "2.1~alpha2", {"default": None}, True),
        ("the 2.1 release candidate", "2.1~rc", {"default": None}, False),
        ("a nested archive", "2.2", {"default": nested}, True),
        ("unpacked repositories", "2.2", {"default": None}, False),
        ("a flat archive", "2.2", {"default": flat}, False),
        ("a nested archive at 2.6~alpha", "2.6~alpha", {"default": nested}, False),
        ("a nested archive in the reviewed format", opam_client.OPAM_ROOT_FORMAT,
         {"default": nested}, False),
        ("a dotted flat name", "2.2", {"default": (("./repo", regular),)}, False),
        ("a dotted package name", "2.2", {"default": (("./packages/p/opam", regular),)},
         False),
        ("a regular file named packages", "2.2", {"default": (("packages", regular),)},
         True),
        ("a name ending in a slash", "2.2",
         {"default": (("default/x/", regular), ("repo", regular))}, False),
        ("a link first", "2.2", {"default": (("x", link), ("default/repo", regular))},
         False),
        ("a climbing name first", "2.2", {"default": (("../repo", regular),)}, False),
        ("an archive with no regular file", "2.2", {"default": (("default/", folder),)},
         False),
        ("a flat archive, then a nested one", "2.2", {"a": flat, "b": nested}, True),
        ("a link-led archive, then a nested one", "2.2",
         {"a": (("x", link),), "b": nested}, False))
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        for index, (what, fmt, archives, hard) in enumerate(cases):
            root = root_at(Path(td) / str(index), fmt, archives)
            ensure(provision._upgrades_to_read(root) is hard,
                   f"a root in format {fmt} with {what} reads hard={hard}")
        corrupt = root_at(Path(td) / "corrupt", "2.2", {"a": None, "b": nested})
        (corrupt / "repo" / "a.tar.gz").write_bytes(b"not an archive")
        ensure(not provision._upgrades_to_read(corrupt),
               "an archive the client cannot read stops the reading undecided")
        nested_root = root_at(Path(td) / "release", "2.2", {"default": nested})
        with patch.object(provision.opam_client, "OPAM_VERSION", "2.6.1"):
            ensure(not provision._upgrades_to_read(nested_root),
                   "another reviewed release claims no hard upgrade until its source is "
                   "read")


def _client_is_asked_once_per_run() -> None:
    """One run asks the opam client its release once, and the opam row and every switch
    row read that one answer, a client at another release holding back each of their
    commands; the next run asks again, and so does a probe taken outside a run."""
    names = ("opam", "the Sail switch", "the prover switch", "the QuickChick switch")
    rows = tuple(fact for fact in provision.FACTS if fact.name in names)
    version = ("opam", "--version")
    asked: list[tuple[str, ...]] = []

    def say(argv: tuple[str, ...]) -> str:
        asked.append(tuple(argv))
        return "2.5.0" if tuple(argv) == version else ""

    with (tempfile.TemporaryDirectory(prefix="vos-test-") as td,
          patch.object(provision, "shutil", SimpleNamespace(which=lambda name: "/usr/bin/opam")),
          patch.object(provision.env, "opam_root", return_value=Path(td) / "absent"),
          patch.object(provision, "_say", side_effect=say)):
        results = provision.take(rows)
        once = asked.count(version)
        provision.take(rows)
        again = asked.count(version)
        outside = provision._client()
    ensure(len(rows) == len(names) and once == 1 and again == 2,
           f"each run asks the client once for {len(rows)} rows: {once} then {again}")
    ensure(all(not found.present and not found.repairable for _, found in results)
           and not provision.plan(results),
           f"a client at another release holds back every row's command: {results}")
    ensure(outside == ("/usr/bin/opam", "2.5.0") and asked.count(version) == 3,
           f"a probe outside a run asks afresh: {outside} after {asked.count(version)}")


def _prerelease_client_is_not_reviewed() -> None:
    """The client's release is read exactly, its first word, so a prerelease or a
    development build of the reviewed release is another client: the opam row and every
    switch row are held back with the release they read named, and `--install-opam`
    refuses to install over it."""
    reviewed = opam_client.OPAM_VERSION
    ensure(provision._release(f"{reviewed}~beta1\n") == f"{reviewed}~beta1"
           and provision._release("") == "",
           "the release is the client's first word, suffix and all")
    names = ("opam", "the Sail switch", "the prover switch", "the QuickChick switch")
    rows = tuple(fact for fact in provision.FACTS if fact.name in names)
    for release in (f"{reviewed}~beta1", f"{reviewed}~alpha1", f"{reviewed}+dev"):

        def say(argv: tuple[str, ...], release: str = release) -> str:
            return f"{release}\n" if tuple(argv) == ("opam", "--version") else ""

        with (tempfile.TemporaryDirectory(prefix="vos-test-") as td,
              patch.object(provision, "shutil",
                           SimpleNamespace(which=lambda name: "/usr/bin/opam")),
              patch.object(provision.env, "opam_root", return_value=Path(td) / "absent"),
              patch.object(provision, "_say", side_effect=say),
              patch.object(provision, "_dpkg", side_effect=_dpkg_reports()),
              patch.object(provision.opam_client, "install") as installer,
              patch.object(provision.subprocess, "run") as launched):
            results = provision.take(rows)
            said = "\n".join(provision.run(rows).out)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as refused:
                code = provision.install_opam(Path(td) / "bin" / "opam")
        client = f"opam {release} at /usr/bin/opam"
        ensure(len(results) == len(names)
               and all(not found.present and not found.repairable and client in found.saw
                       for _, found in results)
               and not provision.plan(results) and said.count(client) == len(names),
               f"opam {release} holds back every row and is named in each: {results}")
        ensure(code == 1 and f"opam {release} is already on PATH" in refused.getvalue()
               and not installer.called and not launched.called,
               f"--install-opam refuses opam {release}: {refused.getvalue()}")


def _dpkg_reports(*absent: str) -> Callable[[str], provision.Found]:
    """dpkg's answer on a machine the case describes: every package installed but
    those in `absent`."""
    return lambda package: provision.Found(
        package not in absent,
        f"dpkg knows no {package}" if package in absent else "install ok installed 1.0")


def _root_prerequisites_precede_the_opam_row() -> None:
    """Each package the root-creation route needs is a row of its own ahead of the opam
    row, probed by dpkg and installed by apt, so `--apply` installs it before the opam
    row's command runs `opam init`, and names that root creation as what wants it."""
    names = [fact.name for fact in provision.FACTS]
    opam_at = names.index("opam")
    for package in opam_client.ROOT_PREREQUISITES:
        ensure(package in names[:opam_at],
               f"{package} is a row ahead of the opam row: {names}")
        row = provision.FACTS[names.index(package)]
        probe = row.probe
        ensure(isinstance(probe, partial) and probe.func is provision._dpkg
               and probe.args == (package,),
               f"the {package} row asks dpkg for {package}: {probe}")
        ensure(row.install == ((*provision.APT, package),)
               and "root creation" in row.needs
               and "tools/vos/opam_client.py's ROOT_PREREQUISITES" in row.owner,
               f"the {package} row installs it by apt, for the opam row's root creation, "
               f"and names its owner: {row}")


def _install_opam_refuses_without_root_prerequisites() -> None:
    """Where the command would create a root and a package `opam init` needs is absent,
    it refuses naming each such package, before it installs a client or runs opam; a
    root that already stands needs none of them."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        target, root = Path(td) / "bin" / "opam", Path(td) / "opam"
        first, *_, last = opam_client.ROOT_PREREQUISITES
        with (patch.object(provision, "shutil", SimpleNamespace(which=lambda name: None)),
              patch.object(provision, "env", SimpleNamespace(opam_root=lambda: root)),
              patch.object(provision, "_dpkg", side_effect=_dpkg_reports(first, last)),
              patch.object(provision.opam_client, "install") as installer,
              patch.object(provision.subprocess, "run") as launched,
              redirect_stderr(io.StringIO()) as said):
            ensure(provision.install_opam(target) == 1
                   and f"without {first}, {last}," in said.getvalue()
                   and not installer.called and not launched.called,
                   f"absent root prerequisites stop the command first: {said.getvalue()}")
        opam_root(root, "flat")
        with (patch.object(provision, "shutil",
                           SimpleNamespace(which=lambda name: "/usr/bin/opam")),
              patch.object(provision, "env", SimpleNamespace(opam_root=lambda: root)),
              patch.object(provision, "_say", return_value=opam_client.OPAM_VERSION),
              patch.object(provision, "_dpkg", side_effect=_dpkg_reports(first, last)),
              patch.object(provision.subprocess, "run") as launched,
              redirect_stdout(io.StringIO()) as out):
            ensure(provision.install_opam(target) == 0 and not launched.called
                   and "already stands complete" in out.getvalue(),
                   f"a complete root needs no root prerequisite: {out.getvalue()}")


def _install_opam_installs_only_what_is_absent() -> None:
    """`--install-opam` installs the client through the owner's route where none is on
    PATH and creates a root by the owner's route where none stands, never over what
    stands: a client at another release, or a root the row reads as incomplete."""
    with (tempfile.TemporaryDirectory(prefix="vos-test-") as td,
          patch.object(provision, "_dpkg", side_effect=_dpkg_reports())):
        target = Path(td) / "bin" / "opam"
        root = Path(td) / "opam"
        selected: list[str | None] = [None]
        steps: list[str] = []

        def install(destination: Path, machine: str) -> None:
            steps.append(f"install {destination} {machine}")
            selected[0] = str(destination)

        def run(argv: list[str], *, check: bool,
                env: dict[str, str]) -> subprocess.CompletedProcess[str]:
            del check
            steps.append(f"{' '.join(argv)} in {env['OPAMROOT']}")
            if tuple(argv) == opam_client.CREATE_ROOT[-1]:
                opam_root(root, "flat")
            return subprocess.CompletedProcess(argv, 0)

        # PATH searches the destination's directory, spelled with a trailing separator
        # behind another entry and an empty one.
        searched = {"PATH": os.pathsep.join((str(Path(td) / "first"), "",
                                             f"{target.parent}{os.sep}"))}
        with (patch.dict(os.environ, searched),
              patch.object(provision, "shutil",
                           SimpleNamespace(which=lambda name: selected[0])),
              patch.object(provision, "env", SimpleNamespace(opam_root=lambda: root)),
              patch.object(provision, "_say", return_value=opam_client.OPAM_VERSION),
              patch.object(provision.opam_client, "install", side_effect=install),
              patch.object(provision.subprocess, "run", side_effect=run),
              patch.object(provision.platform, "machine", return_value="x86_64"),
              redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO())):
            ensure(provision.install_opam(target) == 0
                   and steps == [f"install {target} x86_64",
                                 *(f"{' '.join(argv)} in {root}"
                                   for argv in opam_client.CREATE_ROOT)],
                   f"an absent client and root are installed by the owner's routes: {steps}")
            ensure(f"created the opam root at {root} in format "
                   f"{opam_client.OPAM_ROOT_FORMAT}" in out.getvalue(),
                   f"the created root is held to the reviewed format: {out.getvalue()}")
            steps.clear()
            ensure(provision.install_opam(target) == 0 and not steps,
                   f"the reviewed client over a complete root is left alone: {steps}")
        # Each refusal leaves what stands exactly as it was.
        with (patch.object(provision, "shutil",
                           SimpleNamespace(which=lambda name: "/usr/bin/opam")),
              patch.object(provision, "env", SimpleNamespace(opam_root=lambda: root)),
              patch.object(provision, "_say", return_value="2.5.0"),
              patch.object(provision.opam_client, "install") as installer,
              patch.object(provision.subprocess, "run") as launched,
              redirect_stderr(io.StringIO()) as said):
            ensure(provision.install_opam(target) == 1 and "already on PATH" in said.getvalue()
                   and not installer.called and not launched.called,
                   f"a client at another release is never replaced: {said.getvalue()}")
        # A root lacking the repository `opam init` fetches is not in the shape the
        # route leaves after its leading steps, so the route's remaining steps would not
        # complete it.
        partial = Path(td) / "partial"
        opam_root(partial, "flat", configured=opam_client.OPAM_REPOSITORIES[1:])
        before = (partial / "repo" / "repos-config").read_bytes()
        with (patch.object(provision, "shutil",
                           SimpleNamespace(which=lambda name: "/usr/bin/opam")),
              patch.object(provision, "env", SimpleNamespace(opam_root=lambda: partial)),
              patch.object(provision, "_say", return_value=opam_client.OPAM_VERSION),
              patch.object(provision.subprocess, "run") as launched,
              redirect_stderr(io.StringIO()) as said):
            ensure(provision.install_opam(target) == 1 and "left as it is" in said.getvalue()
                   and "lacks" in said.getvalue() and not launched.called
                   and (partial / "repo" / "repos-config").read_bytes() == before,
                   f"an incomplete root is reported and left as it is: {said.getvalue()}")
        # With no client, a root the row reads as incomplete is refused before the
        # client is installed, which would otherwise leave a client and a failure.
        older, newer = Path(td) / "older", Path(td) / "newer"
        opam_root(older, "nested", configured=opam_client.OPAM_REPOSITORIES[:1])
        opam_root(newer, "flat")
        (newer / "config").write_text('opam-root-version: "99.0"\n', encoding="utf-8")
        for incomplete in (older, newer):
            with (patch.object(provision, "shutil", SimpleNamespace(which=lambda name: None)),
                  patch.object(provision, "env",
                               SimpleNamespace(opam_root=lambda at=incomplete: at)),
                  patch.object(provision.opam_client, "install") as installer,
                  patch.object(provision.subprocess, "run") as launched,
                  redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as said):
                ensure(provision.install_opam(target) == 1
                       and "left as it is" in said.getvalue()
                       and not installer.called and not launched.called,
                       f"no client over the incomplete root {incomplete.name} installs "
                       f"nothing: {said.getvalue()}")
        # With no client, a complete root in an older format is refused before the
        # client is installed, because the reviewed client would rewrite it one way;
        # the reviewed client already on PATH over it leaves it as it is.
        older_complete = Path(td) / "older-complete"
        opam_root(older_complete, "nested")
        before = (older_complete / "config").read_bytes()
        with (patch.dict(os.environ, searched),
              patch.object(provision, "shutil", SimpleNamespace(which=lambda name: None)),
              patch.object(provision, "env", SimpleNamespace(opam_root=lambda: older_complete)),
              patch.object(provision.opam_client, "install") as installer,
              patch.object(provision.subprocess, "run") as launched,
              redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as said):
            ensure(provision.install_opam(target) == 1
                   and f"is in format 2.2, which the reviewed client "
                       f"{opam_client.OPAM_VERSION} rewrites to "
                       f"{opam_client.OPAM_ROOT_FORMAT} one way" in said.getvalue()
                   and "deliberate, recorded step" in said.getvalue()
                   and not installer.called and not launched.called
                   and (older_complete / "config").read_bytes() == before,
                   f"no client over a complete older root installs nothing: {said.getvalue()}")
        with (patch.object(provision, "shutil",
                           SimpleNamespace(which=lambda name: "/usr/bin/opam")),
              patch.object(provision, "env", SimpleNamespace(opam_root=lambda: older_complete)),
              patch.object(provision, "_say", return_value=opam_client.OPAM_VERSION),
              patch.object(provision.opam_client, "install") as installer,
              patch.object(provision.subprocess, "run") as launched,
              redirect_stdout(io.StringIO()) as out):
            ensure(provision.install_opam(target) == 0
                   and "already stands complete" in out.getvalue()
                   and not installer.called and not launched.called,
                   f"the reviewed client over a complete older root is left alone: "
                   f"{out.getvalue()}")
        _creation_failures(Path(td), target)
        selected[0] = None
        absent = SimpleNamespace(opam_root=lambda: Path(td) / "absent")
        with (patch.dict(os.environ, searched),
              patch.object(provision, "shutil", SimpleNamespace(which=lambda name: None)),
              patch.object(provision, "env", absent),
              patch.object(provision.opam_client, "install",
                           side_effect=ValueError("downloaded SHA256 does not match")),
              redirect_stderr(io.StringIO()) as said):
            ensure(provision.install_opam(target) == 1
                   and "does not match" in said.getvalue(),
                   f"a refused download is the command's failure: {said.getvalue()}")
        # A destination whose directory PATH does not search is refused before the
        # client is installed, and one PATH still does not find once installed is the
        # backstop's failure.
        elsewhere = {"PATH": str(Path(td) / "elsewhere")}
        for environment, installs, fragment in (
                (elsewhere, False, "would be at"), (searched, True, "is at")):
            with (patch.dict(os.environ, environment),
                  patch.object(provision, "shutil", SimpleNamespace(which=lambda name: None)),
                  patch.object(provision, "env", absent),
                  patch.object(provision.opam_client, "install") as installer,
                  patch.object(provision.subprocess, "run") as launched,
                  redirect_stderr(io.StringIO()) as said):
                ensure(provision.install_opam(target) == 1
                       and f"{fragment} {target}, which is not on PATH" in said.getvalue()
                       and installer.called is installs and not launched.called,
                       f"a client no switch recipe can run is a failure, installed="
                       f"{installs}: {said.getvalue()}")


def _creation_failures(scratch: Path, target: Path) -> None:
    """A root the route did not finish, or finished as another client's, fails the
    command: a failed step stops the route, and the created root is held as bootstrap
    holds its own."""
    for name, code, layout, fragment in (("failed", 2, "", "exited 2"),
                                         ("foreign", 0, "nested", "is not the owner's")):
        root = scratch / name
        ran: list[tuple[str, ...]] = []

        def run(argv: list[str], *, check: bool, env: dict[str, str],
                root: Path = root, code: int = code, layout: str = layout,
                ran: list[tuple[str, ...]] = ran) -> subprocess.CompletedProcess[str]:
            del check, env
            ran.append(tuple(argv))
            if layout and tuple(argv) == opam_client.CREATE_ROOT[-1]:
                opam_root(root, layout)
            return subprocess.CompletedProcess(argv, code)

        with (patch.object(provision, "shutil",
                           SimpleNamespace(which=lambda name: "/usr/bin/opam")),
              patch.object(provision, "env", SimpleNamespace(opam_root=lambda at=root: at)),
              patch.object(provision, "_say", return_value=opam_client.OPAM_VERSION),
              patch.object(provision.subprocess, "run", side_effect=run),
              redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as said):
            ensure(provision.install_opam(target) == 1 and fragment in said.getvalue(),
                   f"a {name} root creation fails the command: {said.getvalue()}")
        ensure(ran == list(opam_client.CREATE_ROOT[:1] if code else opam_client.CREATE_ROOT),
               f"a failed step stops the route, ran {ran}")


def _stopped_route_is_finished() -> None:
    """A route that fails after `opam init` made the root reports what stands and what
    remains of the route, and the next run finishes that root by the route's remaining
    steps alone, adding and fetching each repository the root lacks, and never runs
    `opam init` over the root that stands."""
    (default, url), *_ = opam_client.OPAM_REPOSITORIES
    reviewed = opam_client.OPAM_VERSION
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        target, root = Path(td) / "bin" / "opam", Path(td) / "opam"
        ran: list[tuple[str, ...]] = []

        def failing(argv: list[str], *, check: bool,
                    env: dict[str, str]) -> subprocess.CompletedProcess[str]:
            del check, env
            ran.append(tuple(argv))
            if tuple(argv) != opam_client.CREATE_ROOT[0]:
                return subprocess.CompletedProcess(argv, 2)
            opam_root(root, "flat", configured=opam_client.OPAM_REPOSITORIES[:1])
            return subprocess.CompletedProcess(argv, 0)

        def finishing(argv: list[str], *, check: bool,
                      env: dict[str, str]) -> subprocess.CompletedProcess[str]:
            del check, env
            ran.append(tuple(argv))
            if tuple(argv) == opam_client.CREATE_ROOT[-1]:
                shutil.rmtree(root)
                opam_root(root, "flat")
            return subprocess.CompletedProcess(argv, 0)

        def machine(run: Callable[..., subprocess.CompletedProcess[str]]) -> ExitStack:
            stack = ExitStack()
            stack.enter_context(patch.object(
                provision, "shutil", SimpleNamespace(which=lambda name: "/usr/bin/opam")))
            stack.enter_context(patch.object(
                provision, "env", SimpleNamespace(opam_root=lambda: root)))
            stack.enter_context(patch.object(provision, "_say", return_value=reviewed))
            stack.enter_context(patch.object(provision, "_dpkg",
                                             side_effect=_dpkg_reports()))
            stack.enter_context(patch.object(provision.subprocess, "run", side_effect=run))
            return stack

        with (machine(failing), redirect_stdout(io.StringIO()),
              redirect_stderr(io.StringIO()) as said):
            code = provision.install_opam(target)
        remaining = "; ".join(" ".join(argv) for argv in opam_client.CREATE_ROOT[1:])
        for fragment in (f"`{' '.join(opam_client.CREATE_ROOT[1])}` exited 2",
                         f"so the opam root at {root} stands in format "
                         f"{opam_client.OPAM_ROOT_FORMAT} with {default} {url} at stamp "
                         f"{default}-stamp",
                         f"what remains of the route is {remaining}, and a later run of this "
                         "command finishes it"):
            ensure(code == 1 and fragment in said.getvalue(),
                   f"a failure at the second step says {fragment!r}: {said.getvalue()}")
        ensure(ran == list(opam_client.CREATE_ROOT[:2]), f"the route stopped there: {ran}")
        found = _opam_probe(root, "/usr/bin/opam", reviewed)
        ensure(not found.present and found.repairable,
               f"the row plans the command over what the route left: {found.saw}")
        ran.clear()
        with machine(finishing), redirect_stdout(io.StringIO()) as out:
            code = provision.install_opam(target)
        ensure(code == 0 and ran == list(opam_client.CREATE_ROOT[1:])
               and opam_client.CREATE_ROOT[0] not in ran
               and f"finished the opam root at {root} in format "
                   f"{opam_client.OPAM_ROOT_FORMAT}" in out.getvalue(),
               f"the next run finishes the root by the remaining steps alone: {ran} "
               f"{out.getvalue()}")
        ensure(_opam_probe(root, "/usr/bin/opam", reviewed).present,
               "the finished root holds the row")


def _stopped_fetch_is_finished() -> None:
    """A root whose last addition was stopped during its fetch, that repository
    configured and unread, is finished by running the addition again, which fetches it,
    and never by `opam init`."""
    (default, _), *_ = opam_client.OPAM_REPOSITORIES
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        target, root = Path(td) / "bin" / "opam", Path(td) / "opam"
        opam_root(root, "flat", stamps={default: f"{default}-stamp"})
        ran: list[tuple[str, ...]] = []

        def run(argv: list[str], *, check: bool,
                env: dict[str, str]) -> subprocess.CompletedProcess[str]:
            del check, env
            ran.append(tuple(argv))
            if tuple(argv) == opam_client.CREATE_ROOT[-1]:
                shutil.rmtree(root)
                opam_root(root, "flat")
            return subprocess.CompletedProcess(argv, 0)

        with (patch.object(provision, "shutil",
                           SimpleNamespace(which=lambda name: "/usr/bin/opam")),
              patch.object(provision, "env", SimpleNamespace(opam_root=lambda: root)),
              patch.object(provision, "_say", return_value=opam_client.OPAM_VERSION),
              patch.object(provision, "_dpkg", side_effect=_dpkg_reports()),
              patch.object(provision.subprocess, "run", side_effect=run),
              redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as said):
            code = provision.install_opam(target)
        ensure(code == 0 and ran == list(opam_client.CREATE_ROOT[1:])
               and f"finished the opam root at {root}" in out.getvalue(),
               f"the stopped addition runs again and alone: {ran} {out.getvalue()} "
               f"{said.getvalue()}")
        ensure(_opam_probe(root, "/usr/bin/opam", opam_client.OPAM_VERSION).present,
               "the finished root holds the row")


# The shell-hook scripts opam 2.6.0 writes under a root's `opam-init` directory, one
# per shell it supports a hook for.
_HOOKS = ("env_hook.sh", "env_hook.zsh", "env_hook.csh", "env_hook.fish")


def _resume_keeps_the_shell_hook() -> None:
    """A developer's root made by an interactive `opam init` on the first repository
    alone, its shell hook enabled, is in the shape the route leaves after its leading
    steps, and completing it leaves its shell setup as it stands. The fake client here
    does to a standing root what 2.6.0's `opam init --no-setup` does, rewriting its
    init scripts and removing its hook scripts, so a resume that ran it would fail."""
    reviewed = opam_client.OPAM_VERSION
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        target, root = Path(td) / "bin" / "opam", Path(td) / "opam"
        opam_root(root, "flat", configured=opam_client.OPAM_REPOSITORIES[:1])
        scripts = root / "opam-init"
        scripts.mkdir()
        for name in ("init.sh", *_HOOKS):
            (scripts / name).write_text(f"# the developer's {name}\n", encoding="utf-8")
        before = {path.name: path.read_bytes() for path in scripts.iterdir()}
        ran: list[tuple[str, ...]] = []

        def run(argv: list[str], *, check: bool,
                env: dict[str, str]) -> subprocess.CompletedProcess[str]:
            del check, env
            ran.append(tuple(argv))
            if tuple(argv) == opam_client.CREATE_ROOT[0]:
                (scripts / "init.sh").write_text("# rewritten\n", encoding="utf-8")
                for name in _HOOKS:
                    (scripts / name).unlink(missing_ok=True)
            elif tuple(argv) == opam_client.CREATE_ROOT[-1]:
                shutil.rmtree(root / "repo")
                (root / "config").unlink()
                opam_root(root, "flat")
            return subprocess.CompletedProcess(argv, 0)

        ensure(opam_client.root_resumable(root),
               "a stock developer root on the first repository is resumable")
        with (patch.object(provision, "shutil",
                           SimpleNamespace(which=lambda name: "/usr/bin/opam")),
              patch.object(provision, "env", SimpleNamespace(opam_root=lambda: root)),
              patch.object(provision, "_say", return_value=reviewed),
              patch.object(provision, "_dpkg", side_effect=_dpkg_reports()),
              patch.object(provision.subprocess, "run", side_effect=run),
              redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as said):
            code = provision.install_opam(target)
        after = {path.name: path.read_bytes() for path in scripts.iterdir()}
        ensure(code == 0 and ran == list(opam_client.CREATE_ROOT[1:]),
               f"the resume runs the remaining steps alone: {ran} {out.getvalue()} "
               f"{said.getvalue()}")
        ensure(after == before,
               f"the developer's init and hook scripts stand as they were: {sorted(after)}")


def _failed_import_can_retry() -> None:
    registered: set[str] = set()
    seen: list[tuple[str, ...]] = []
    create = ("opam", "switch", "create", "verifiedos-fixture", "--empty")
    restore = ("opam", "switch", "import", "fixture.lock", "--switch=verifiedos-fixture")
    fact = _fact("fixture", present=False, install=(create, restore))

    def run(argv: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        del check
        seen.append(tuple(argv))
        if tuple(argv) == create:
            registered.add("verifiedos-fixture")
        return subprocess.CompletedProcess(argv, 1 if tuple(argv) == restore else 0)

    with (patch.object(provision, "switches", side_effect=lambda: tuple(registered)),
          patch.object(provision.subprocess, "run", side_effect=run)):
        provision._apply(Reporter(), [(fact, fact.install)])
        provision._apply(Reporter(), [(fact, fact.install)])
    ensure(seen == [create, restore, restore],
           f"a failed import must retry in its existing switch, ran {seen}")
    with (patch.object(provision, "switches", return_value=()),
          patch.object(provision.subprocess, "run",
                       return_value=subprocess.CompletedProcess(create, 1)) as invoked):
        provision._apply(Reporter(), [(fact, fact.install)])
        ensure(invoked.call_count == 1, "an unrelated create failure must stop before import")


def _machine(types: dict[str, str]) -> Callable[[Path | str], str]:
    """A mount table a case chose, keyed by the POSIX spelling of each path."""
    return lambda path: types.get(Path(path).as_posix(), "")


def _placement_probe_decides_by_filesystem() -> None:
    """The placement rule as a probe, over machines the case describes: the two roots
    a guest loop writes under must be on the guest's own persistent filesystem, and
    the checkout is reported beside them and never counted."""
    build, logs = env.build_root().as_posix(), env.log_root().as_posix()
    checkout = "/mnt/c/repo"
    with patch.object(provision, "find_root", return_value=Path(checkout)):
        with patch.object(env, "filesystem", side_effect=_machine(
                {build: "ext4", logs: "ext4", checkout: "9p"})):
            found = provision._outputs_on_the_guest()
            ensure(found.present and "ext4" in found.saw and "over 9p" in found.saw,
                   f"the split layout is the lane, and the checkout's crossing is "
                   f"reported rather than counted, got {found}")
        with patch.object(env, "filesystem", side_effect=_machine(
                {build: "9p", logs: "ext4", checkout: "9p"})):
            found = provision._outputs_on_the_guest()
            ensure(not found.present and "crosses the boundary" in found.saw,
                   f"a build root on the Windows mount fails the lane, got {found}")
        with patch.object(env, "filesystem", side_effect=_machine(
                {build: "ext4", logs: "tmpfs", checkout: "ext4"})):
            found = provision._outputs_on_the_guest()
            ensure(not found.present and "outlive" in found.saw
                   and "beside them" in found.saw,
                   f"a log root on tmpfs fails the lane, and a checkout on the guest's "
                   f"own filesystem is reported as beside it, got {found}")
        with patch.object(env, "filesystem", return_value=""):
            found = provision._outputs_on_the_guest()
            ensure(not found.present and "undecided" in found.saw,
                   f"an unreadable mount table decides nothing and says so, got {found}")


def _run(*argv: str) -> tuple[int, str, str]:
    done = subprocess.run(list(argv), capture_output=True, encoding="utf-8",
                          errors="replace", check=False, timeout=300, cwd=_ROOT)
    return done.returncode, done.stdout, done.stderr


def _git(*argv: str) -> tuple[int, str, str]:
    """git over this checkout, from whichever lane is asking.

    A linked worktree made by the host's git holds a *Windows* path in its `.git`
    file, so inside the guest a bare `git` in a lane exits 128 with `not a git
    repository`, which is I7's own finding and is a property of the lane rather than
    of anything here. `env.git_env` is the overlay that act landed and I13 completed,
    and it is reached rather than repeated; it is empty on the primary worktree and on
    the host, where nothing needs translating.
    """
    overlay = env.git_env(_ROOT)
    done = subprocess.run(["git", *argv], capture_output=True, encoding="utf-8",
                          errors="replace", check=False, timeout=300, cwd=_ROOT,
                          env={**os.environ, **overlay} if overlay else None)
    return done.returncode, done.stdout, done.stderr


@dataclass
class _Flow:
    porcelain: str | None = None


_FLOW = _Flow()


def _check_is_read_only() -> None:
    """The guest's acceptance case: `--check` twice, identical, over an unmoved tree.

    Bracketed rather than asserted empty, because the suite may run on a tree with
    untracked work in flight and what is owed is that these two runs added none of it.

    The tree is this repository's and never a populated submodule's, which is the
    reading the working rules state for `upstream/`: the tools read what the index
    conveys, one gitlink per submodule, and a populated one is a checkout-dependent
    thing the host's git may have written pointer files into that the guest cannot
    resolve. Left to recurse, `git status` spawns a child in every populated submodule,
    so on a checkout where a nested submodule's `.git` file names a Windows path the
    read exits 128 about that pointer and decides nothing about the provisioner, which
    has no path into `upstream/` at all. Ignoring submodules is what makes the case
    answer the same over a populated checkout and over the bare one CI reads.
    """
    code, before, err = _git("status", "--porcelain", "--ignore-submodules=all")
    ensure(code == 0, f"git status failed: {err!r}")
    _FLOW.porcelain = before

    first = _run(sys.executable, str(TOOLS / "run.py"), "provision", "--check")
    second = _run(sys.executable, str(TOOLS / "run.py"), "provision", "--check")
    ensure(first == second,
           f"provision --check answered differently on its second run:\n"
           f"first:  {first!r}\nsecond: {second!r}")

    code, after, err = _git("status", "--porcelain", "--ignore-submodules=all")
    ensure(code == 0, f"git status failed: {err!r}")
    ensure(after == before,
           f"a --check run moved the tree:\nbefore: {before!r}\nafter: {after!r}")


def cases() -> list[Case]:
    return [
        Case("satisfied-plans-nothing", _satisfied_plans_nothing),
        Case("absent-plans-its-own-command", _absent_plans_its_own_command),
        Case("absent-without-a-command-reports-only",
             _absent_without_a_command_reports_only),
        Case("verdict-is-the-exit-code", _verdict_is_the_exit_code),
        Case("report-is-deterministic", _report_is_deterministic),
        Case("only-narrows-and-says-what-it-skipped",
             _only_narrows_and_says_what_it_skipped),
        Case("every-row-is-actionable", _every_row_is_actionable),
        Case("versions-are-read-and-not-typed", _versions_are_read_and_not_typed),
        Case("number-reads-the-banners", _number_reads_the_banners),
        Case("probes-answer-no-question", _probes_answer_no_question),
        Case("opam-probe-preserves-build-suffix", _opam_probe_preserves_build_suffix),
        Case("opam-probe-holds-the-reviewed-client", _opam_probe_holds_the_reviewed_client),
        Case("opam-probe-holds-the-root", _opam_probe_holds_the_root),
        Case("opam-row-plans-only-what-is-absent", _opam_row_plans_only_what_is_absent),
        Case("switch-rows-wait-on-an-older-root", _switch_rows_wait_on_an_older_root),
        Case("unread-switch-is-not-absent", _unread_switch_is_not_absent),
        Case("hard-upgrade-is-read-from-the-root", _hard_upgrade_is_read_from_the_root),
        Case("client-is-asked-once-per-run", _client_is_asked_once_per_run),
        Case("prerelease-client-is-not-reviewed", _prerelease_client_is_not_reviewed),
        Case("root-prerequisites-precede-the-opam-row",
             _root_prerequisites_precede_the_opam_row),
        Case("install-opam-refuses-without-root-prerequisites",
             _install_opam_refuses_without_root_prerequisites),
        Case("install-opam-installs-only-what-is-absent",
             _install_opam_installs_only_what_is_absent),
        Case("stopped-route-is-finished", _stopped_route_is_finished),
        Case("stopped-fetch-is-finished", _stopped_fetch_is_finished),
        Case("resume-keeps-the-shell-hook", _resume_keeps_the_shell_hook),
        Case("failed-import-can-retry", _failed_import_can_retry),
        Case("placement-probe-decides-by-filesystem",
             _placement_probe_decides_by_filesystem),
        # guest-only: the command hops there, so on the host this case would pay for a
        # WSL launch to decide about a lane the host is not
        Case("check-is-read-only", _check_is_read_only, lane="guest"),
    ]
