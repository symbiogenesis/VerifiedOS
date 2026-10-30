# SPDX-License-Identifier: Apache-2.0
"""The artifact inventory is computed from a tree, and its completeness is decided there.

Every mutating case runs in a copied tree holding exactly the files the manifest
inventories, so a temporary module, document, test or proof is the only difference
between a complete artifact and the finding it must produce.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import static_memory_manifest as manifest
from vos.cli import static_memory as cli

# Each case writes only to a sandbox copy of this tree it creates, and patches only
# inside a `with`, so the cases share no state, and a sharded run spreads them over
# every shard (vos/cli/test.py).
INDEPENDENT_CASES = True

ROOT = Path(__file__).resolve().parents[2]

SPDX = "# SPDX-License-Identifier: Apache-2.0\n"


def _report(root: Path, *, replay: bool = False) -> dict[str, Any]:
    return manifest.report(root, cli.registration(), digest_sources=cli.digests,
                           run=cli.replay, replay=replay)


def _replay_action(action: str) -> manifest.ReplayEntry:
    return manifest.replay_action(action, cli.registration(), cli.replay)


def _artifact_files() -> dict[str, str]:
    """The artifact's own inventory, as the contents of a throwaway tree."""
    items = manifest.inventory(ROOT, cli.registration(), cli.digests)
    return {entry["path"]: (ROOT / entry["path"]).read_text(encoding="utf-8")
            for entry in items["files"] if entry["present"]}


def _git(root: Path, *args: str) -> None:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          encoding="utf-8", errors="replace", check=False, timeout=60)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} exited {done.returncode}: {done.stderr}")


def _commit(root: Path) -> None:
    """One commit, because the shared identity reads HEAD.

    The identity is passed per command because a runner with no global `user.email`
    cannot commit at all, and this tree's own configuration is not the subject.
    """
    _git(root, "-c", "user.name=vos", "-c", "user.email=vos@example.invalid",
         "commit", "-q", "-m", "fixture")


def _place(root: Path, rel: str, text: str, *, track: bool = True) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    if track:
        _git(root, "add", rel)


def _append(root: Path, rel: str, text: str) -> None:
    _place(root, rel, (root / rel).read_text(encoding="utf-8") + text)


def _named(errors: list[str], path: str, phrase: str) -> bool:
    return any(error.startswith(f"{path}:") and phrase in error for error in errors)


def _inventory_is_computed_and_complete() -> None:
    items = manifest.inventory(ROOT, cli.registration(), cli.digests)
    paths = {entry["path"]: entry for entry in items["files"]}
    for rel in (manifest.GENERATOR, manifest.ARTIFACT_DOC, manifest.AGENDA, manifest.PLAN,
                manifest.COMMAND_MODULE, *manifest.GENERATED):
        ensure(rel in paths, f"the inventory must carry {rel}")
    bound = cli.identity(ROOT, (manifest.GENERATOR,))["sources_sha256"]
    ensure(paths[manifest.GENERATOR]["sha256"] == bound[manifest.GENERATOR],
           "the manifest and the action receipts must hash bytes the same way")
    registered = {entry["action"] for entry in items["actions"]}
    ensure(registered == set(cli.registration()["choices"]) and manifest.ACTION in registered,
           "every accepted action is inventoried, read from the parser")
    ensure(all(entry["replay"].endswith("--json") for entry in items["actions"]),
           "each action carries its exact replay command")
    action = next(entry for entry in items["actions"] if entry["action"] == manifest.ACTION)
    ensure(manifest.PLAN in action["declared_sources"],
           "the manifest binds the root plan that owns the research tasks")
    scale = next(entry for entry in items["actions"] if entry["action"] == "scale")
    ensure("--q5-max-leaves 1" in scale["replay"], "a budgeted action states its budget")
    ensure("tools/vos/static_memory_scale.py" in scale["declared_sources"]
           and "tools/vos/static_memory.py" in scale["declared_sources"],
           "an action's declared source set is its own plus the shared identity")
    errors = _report(ROOT)["errors"]
    ensure(not errors, f"this tree's artifact is incomplete: {errors}")


def _copied_tree_reports_each_incompleteness() -> None:
    with sandbox_tree(_artifact_files()) as root:
        _commit(root)
        ensure(not _report(root)["errors"], "the copied artifact must be complete")
        _place(root, "tools/vos/static_memory_orphan.py", SPDX)
        _place(root, "docs/implementation/static-memory/orphan.md", "# Orphan\n")
        _place(root, "tools/tests/test_static_memory_ghost.py", SPDX)
        _place(root, "proofs/StaticMemoryOrphan.v", "(* fixture *)\n")
        errors = _report(root)["errors"]
        for path, phrase in (
                ("tools/vos/static_memory_orphan.py", "registered action"),
                ("docs/implementation/static-memory/orphan.md", "links to this document"),
                ("docs/implementation/static-memory/orphan.md", "carries no row"),
                ("tools/tests/test_static_memory_ghost.py", "'ghost'"),
                ("proofs/StaticMemoryOrphan.v", manifest.PROOF_LEDGER)):
            ensure(_named(errors, path, phrase),
                   f"no finding for {path} naming {phrase}: {errors}")
        _place(root, "docs/implementation/static-memory/experiments.md",
               (root / "docs/implementation/static-memory/experiments.md").read_text(
                   encoding="utf-8") + "\n[Orphan](orphan.md) is reachable.\n")
        ensure(not _named(_report(root)["errors"],
                          "docs/implementation/static-memory/orphan.md",
                          "links to this document"),
               "one inbound link from another document clears the reachability finding")


def _a_mention_is_not_a_link_and_the_index_is_not_a_witness() -> None:
    experiments = "docs/implementation/static-memory/experiments.md"
    with sandbox_tree(_artifact_files()) as root:
        _commit(root)
        _place(root, "tools/vos/static_memory_orphan.py", SPDX)
        _place(root, "docs/implementation/static-memory/orphan.md", "# Orphan\n")
        _append(root, experiments, "\n```console\nrm orphan.md\n```\n")
        _append(root, manifest.ARTIFACT_DOC,
                "\nstatic_memory_orphan.py is one of the artifact's modules.\n")
        errors = _report(root)["errors"]
        ensure(_named(errors, "docs/implementation/static-memory/orphan.md",
                      "links to this document"),
               f"a basename inside a fenced block is a mention and not a link: {errors}")
        ensure(_named(errors, "tools/vos/static_memory_orphan.py", "registered action"),
               f"the index naming a module is not a witness of its reachability: {errors}")
        original = (root / experiments).read_text(encoding="utf-8")
        for displayed in ("The orphan is named here (orphan.md).\n",
                          "```markdown\n[Orphan](orphan.md#results)\n```\n",
                          "~~~markdown\n[Orphan](orphan.md)\n~~~\n",
                          "![Orphan](orphan.md)\n"):
            _place(root, experiments, original + "\n" + displayed)
            errors = _report(root)["errors"]
            ensure(_named(errors, "docs/implementation/static-memory/orphan.md",
                          "links to this document"),
                   f"displayed or parenthesized text cannot supply a link: {displayed}, {errors}")
        _place(root, experiments, original)
        plan = (root / manifest.PLAN).read_text(encoding="utf-8")
        _append(root, manifest.PLAN,
                "\n[Orphan research task](docs/implementation/static-memory/orphan.md#results)\n")
        ensure(not _named(_report(root)["errors"],
                          "docs/implementation/static-memory/orphan.md", "links to this document"),
               "a research task's root-plan link makes its artifact reachable")
        _place(root, manifest.PLAN, plan)
        _append(root, experiments, "\n[Orphan](orphan.md#results) says so.\n")
        _append(root, "docs/implementation/static-memory/transformations.md",
                "\nstatic_memory_orphan.py carries the orphan experiment.\n")
        errors = _report(root)["errors"]
        ensure(not _named(errors, "docs/implementation/static-memory/orphan.md",
                          "links to this document"),
               f"an anchored link from another document is a link: {errors}")
        ensure(not _named(errors, "tools/vos/static_memory_orphan.py", "registered action"),
               f"a document outside the index naming the module clears it: {errors}")


def _index_membership_decides_as_the_checker_reads_it() -> None:
    with sandbox_tree(_artifact_files()) as root:
        _commit(root)
        _place(root, "tools/vos/static_memory_ghost.py", SPDX, track=False)
        errors = _report(root)["errors"]
        ensure(_named(errors, "tools/vos/static_memory_ghost.py", "git index does not carry"),
               f"an untracked module is a finding: {errors}")
        gone = "docs/implementation/static-memory/scaling.md"
        (root / gone).unlink()
        errors = _report(root)["errors"]
        ensure(_named(errors, gone, "working tree does not carry it"),
               f"a tracked file the tree has lost is a finding: {errors}")


def _classification_join_holds_both_directions() -> None:
    files = _artifact_files()
    document = files[manifest.ARTIFACT_DOC]
    row = next(line for line in document.splitlines()
               if line.startswith("| [") and "baseline.md)" in line)
    last = next(line for line in document.splitlines()
                if line.startswith("| [") and "artifact.md)" in line)
    with sandbox_tree(files) as root:
        _commit(root)
        path = root / manifest.ARTIFACT_DOC
        path.write_text(document.replace(f"{row}\n", ""), encoding="utf-8", newline="")
        ensure(_named(_report(root)["errors"],
                      "docs/implementation/static-memory/baseline.md", "carries no row"),
               "a document with no classification row is a finding")
        twice = ("| [Mathematical baseline](baseline.md) "
                 "| peer-reviewed result cited | elsewhere |")
        path.write_text(document.replace(row, f"{row}\n{twice}"), encoding="utf-8",
                        newline="")
        ensure(_named(_report(root)["errors"],
                      "docs/implementation/static-memory/baseline.md", "carries 2 rows"),
               "a second row claiming other classes for the same document is a finding")
        ghost = "| [Ghost](ghost.md) | new conjecture | nowhere |"
        path.write_text(document.replace(last, f"{last}\n{ghost}"), encoding="utf-8",
                        newline="")
        ensure(_named(_report(root)["errors"],
                      "docs/implementation/static-memory/ghost.md",
                      "names a document the artifact does not carry"),
               "a row naming no document is a finding")
        path.write_text(document.replace("elementary argument in prose", "folklore"),
                        encoding="utf-8", newline="")
        ensure(any("'folklore' is not one of the declared result classes" in error
                   for error in _report(root)["errors"]),
               "a class outside the declared vocabulary is a finding")
        path.write_text(document.replace(manifest.CLASSIFICATION_HEADING, "## Elsewhere"),
                        encoding="utf-8", newline="")
        ensure(_named(_report(root)["errors"], manifest.ARTIFACT_DOC,
                      "no classification table"),
               "a missing table is a finding rather than a vacuous pass")


def _replay_runs_every_other_action_and_the_default_runs_none() -> None:
    calls: list[str] = []

    def _record(action: str, reg: manifest.Registration,
                run: manifest.Replay) -> manifest.ReplayEntry:
        calls.append(action)
        return manifest.ReplayEntry(action=action, argv=[action], exit_code=0,
                                    schema="fixture", scope="fixture", errors=[],
                                    receipt_sha256="fixture")

    with patch.object(manifest, "replay_action", _record):
        quiet = _report(ROOT)
        ensure(not calls and quiet["replays"] == [],
               "the default manifest executes no experiment")
        ran = _report(ROOT, replay=True)
    expected = set(cli.registration()["choices"]) - {manifest.ACTION}
    ensure(set(calls) == expected and len(calls) == len(expected),
           f"--replay runs every other accepted action exactly once: {calls}")
    ensure(len(ran["replays"]) == len(expected), "each replay is recorded")


def _replayed_receipt_is_read_and_a_refusal_is_a_finding() -> None:
    entry = _replay_action("structure")
    ensure(entry["argv"] == ["structure", "--json"] and entry["exit_code"] == 0,
           f"the structural action must replay: {entry}")
    ensure(entry["schema"] == "static-memory-experiment-v1" and entry["scope"] != "n/a"
           and not entry["errors"], f"the receipt's own schema and scope are read: {entry}")
    ensure(len(entry["receipt_sha256"]) == 64, "the receipt digest binds its bytes")
    with patch.object(cli.structure, "report",
                      return_value={"scope": "fixture", "errors": ["bad replay"]}):
        refused = _replay_action("structure")
    ensure(refused["exit_code"] == 1 and "bad replay" in refused["errors"],
           f"a refusing action is recorded rather than aborting the sweep: {refused}")
    def _refuse(action: str, reg: manifest.Registration,
                run: manifest.Replay) -> manifest.ReplayEntry:
        return manifest.ReplayEntry(action=action, argv=[action], exit_code=1,
                                    schema=refused["schema"], scope=refused["scope"],
                                    errors=list(refused["errors"]), receipt_sha256="fixture")

    with patch.object(manifest, "replay_action", _refuse):
        errors = _report(ROOT, replay=True)["errors"]
    ensure(any("exited 1" in error and "bad replay" in error for error in errors),
           f"a replay that refused is a finding: {errors}")


def _malformed_replay_receipts_are_findings_even_after_exit_zero() -> None:
    schema = "static-memory-experiment-v1"
    experiment: dict[str, object] = {"scope": "fixture", "errors": []}
    receipt = {"schema": schema, "action": "structure", "experiment": experiment}
    malformed: list[object] = [[], {}, {"schema": "unknown"}, {"schema": schema}]
    malformed += [{key: value for key, value in receipt.items() if key != missing}
                  for missing in ("action", "experiment")]
    malformed += [{**receipt, "action": value}
                  for value in (None, [], "", "reclaim", "corpus")]
    malformed += [{**receipt, "experiment": value} for value in (None, [], "", 0)]
    malformed += [{**receipt, "experiment": {key: value for key, value in experiment.items()
                                            if key != missing}}
                  for missing in ("scope", "errors")]
    malformed += [{**receipt, "experiment": {**experiment, "scope": value}}
                  for value in (None, 3, [], {}, "", " ", "\t\n")]
    malformed += [{**receipt, "experiment": {**experiment, "errors": value}}
                  for value in (None, {}, "", 0, [None], [3], [[]])]
    for broken in malformed:
        with patch.object(cli, "replay", return_value=(0, broken)):
            entry = _replay_action("structure")
        ensure(entry["exit_code"] == 0 and bool(entry["errors"]),
               f"an exit-zero malformed receipt must still be a finding: {broken}, {entry}")
        ensure(bool(manifest._replay_findings([entry])),
               f"a malformed row must reach the manifest findings: {entry}")
    for action in ("corpus", "check", "compare"):
        with patch.object(cli, "replay", return_value=(0, {**receipt, "action": action})):
            entry = _replay_action(action)
        ensure(bool(entry["errors"]) and bool(manifest._replay_findings([entry])),
               f"a research action cannot return an experiment receipt: {entry}")
    with patch.object(cli, "replay", return_value=(0, receipt)):
        entry = _replay_action("structure")
    ensure(entry["scope"] == "fixture" and not entry["errors"],
           f"a valid experiment receipt must remain accepted: {entry}")
    expected = hashlib.sha256(json.dumps(
        receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    ensure(entry["receipt_sha256"] == expected,
           "replay hashing retains the canonical JSON bytes")
    failed = {**receipt, "experiment": {**experiment, "errors": ["bad replay"]}}
    with patch.object(cli, "replay", return_value=(0, failed)):
        entry = _replay_action("structure")
    ensure(entry["errors"] == ["bad replay"],
           "a reported experiment error cannot be hidden behind exit zero")


def _research_replays_preserve_intentional_diagnostics() -> None:
    for action in ("corpus", "check", "compare"):
        argv = [action, *manifest.REPLAY_SETTINGS.get(action, ()), "--json"]
        code, receipt = cli.replay(argv)
        if action == "corpus":
            ensure(any(request["verdict"] == "refused"
                       for case in receipt["cases"] for request in case["requests"]),
                   "the corpus smoke replay must exercise intentional request refusals")
        if action == "compare":
            ensure(any(case["exact"]["status"] == "incomplete" for case in receipt["cases"]),
                   "the comparison smoke replay must exercise incomplete search")
        with patch.object(cli, "replay", return_value=(code, receipt)):
            entry = _replay_action(action)
        ensure(entry["schema"] == "static-memory-research-v1"
               and entry["exit_code"] == 0 and not entry["errors"],
               f"valid research diagnostics must leave the replay clean: {entry}")


def _malformed_research_receipts_are_findings_even_after_exit_zero() -> None:
    receipt: dict[str, object] = {
        "schema": "static-memory-research-v1", "action": "corpus",
        "scope": "fixture", "settings": {}, "cases": [{"contract": {}}],
    }
    malformed: list[dict[str, object]] = [{"schema": receipt["schema"]}]
    malformed += [{key: value for key, value in receipt.items() if key != missing}
                  for missing in ("action", "scope", "settings", "cases")]
    malformed += [{**receipt, "action": "check"}, {**receipt, "action": "structure"}]
    malformed += [{**receipt, "scope": value} for value in (None, 3, "", " ")]
    malformed += [{**receipt, "settings": value} for value in (None, 3, "", [])]
    malformed += [{**receipt, "cases": value}
                  for value in (None, {}, [], [None], [{}], [{"contract": []}])]
    for broken in malformed:
        with patch.object(cli, "replay", return_value=(0, broken)):
            entry = _replay_action("corpus")
        ensure(entry["exit_code"] == 0 and bool(entry["errors"]),
               f"an exit-zero malformed research receipt must be a finding: {broken}, {entry}")
        ensure(bool(manifest._replay_findings([entry])),
               f"a malformed research row must reach the manifest findings: {entry}")
    with patch.object(cli, "replay", return_value=(0, {**receipt, "action": "structure"})):
        entry = _replay_action("structure")
    ensure(bool(entry["errors"]), "an experiment action cannot return a research receipt")


def _explicit_inputs_keep_the_library_independent() -> None:
    script = """
import argparse
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from vos import static_memory_manifest as manifest

root = Path(sys.argv[2])
parser = argparse.ArgumentParser()
parser.add_argument("action", choices=("manifest", "structure"))
sources = {"structure": (manifest.GENERATOR,)}
reg = manifest.registration(parser, (), sources)
sources.clear()
if reg["choices"] != ("manifest", "structure") or "structure" not in reg["per_action"]:
    raise RuntimeError("registration must read the supplied parser and snapshot sources")
calls: list[list[str]] = []

def digests(root: Path, names: tuple[str, ...]) -> dict[str, str]:
    return {name: "fixture" for name in names}

def run(argv: list[str]) -> tuple[int, object]:
    calls.append(argv)
    return 0, {"schema": "static-memory-experiment-v1", "action": "structure",
               "experiment": {"scope": "fixture", "errors": []}}

report = manifest.report(root, reg, digest_sources=digests, run=run, replay=True)
if calls != [["structure", "--json"]] or report["replays"][0]["errors"]:
    raise RuntimeError("explicit replay callback or action registration was ignored")
if "vos.cli.static_memory" in sys.modules:
    raise RuntimeError("inventory or replay imported the command module")
"""
    done = subprocess.run([sys.executable, "-c", script, str(ROOT / "tools"), str(ROOT)],
                          capture_output=True, text=True, check=False, timeout=60)
    ensure(done.returncode == 0, f"library operations require no command import: {done.stderr}")


def _readers_fail_closed_on_an_unreadable_subject() -> None:
    optional = argparse.ArgumentParser()
    optional.add_argument("--only", action="store_true")
    positional = argparse.ArgumentParser()
    positional.add_argument("name")
    for empty in (argparse.ArgumentParser(), optional, positional):
        try:
            manifest.choices(empty)
        except ValueError:
            continue
        raise AssertionError("a parser with no action choices must not yield an empty set")
    for rel in ("tools/vos/memplan.py", "docs/implementation/placement-search.md"):
        try:
            manifest.topic(rel, manifest.MODULE_KIND)
        except ValueError:
            continue
        raise AssertionError(f"{rel} is not a topic module and must not be read as one")
    ensure(manifest.topic("tools/vos/static_memory.py", manifest.MODULE_KIND) == "",
           "the bare module has no topic")
    ensure(manifest.topic("tools/tests/test_static_memory_cli.py", manifest.TEST_KIND) == "cli",
           "a test's topic is the name after its prefix")


def cases() -> list[Case]:
    return [
        Case("manifest inventory is computed from this tree", _inventory_is_computed_and_complete),
        Case("manifest reports each incompleteness in a copied tree",
             _copied_tree_reports_each_incompleteness),
        Case("manifest reachability takes links and not mentions",
             _a_mention_is_not_a_link_and_the_index_is_not_a_witness),
        Case("manifest index membership decides", _index_membership_decides_as_the_checker_reads_it),
        Case("manifest classification join holds both directions",
             _classification_join_holds_both_directions),
        Case("manifest replay flag runs the minimal budgets",
             _replay_runs_every_other_action_and_the_default_runs_none),
        Case("manifest replayed receipt and refusal",
             _replayed_receipt_is_read_and_a_refusal_is_a_finding),
        Case("manifest rejects malformed exit-zero replay receipts",
             _malformed_replay_receipts_are_findings_even_after_exit_zero),
        Case("manifest research replays preserve diagnostic refusals and search cutoffs",
             _research_replays_preserve_intentional_diagnostics),
        Case("manifest rejects malformed exit-zero research receipts",
             _malformed_research_receipts_are_findings_even_after_exit_zero),
        Case("manifest readers fail closed", _readers_fail_closed_on_an_unreadable_subject),
        Case("manifest consumes explicit inputs without importing its command",
             _explicit_inputs_keep_the_library_independent),
    ]
