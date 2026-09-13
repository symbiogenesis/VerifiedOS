# SPDX-License-Identifier: Apache-2.0
"""The artifact inventory is computed from a tree, and its completeness is decided there.

Every mutating case runs in a copied tree holding exactly the files the manifest
inventories, so a temporary module, document, test or proof is the only difference
between a complete artifact and the finding it must produce.
"""

import argparse
import subprocess
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import static_memory_manifest as manifest
from vos.cli import static_memory as cli

ROOT = Path(__file__).resolve().parents[2]

SPDX = "# SPDX-License-Identifier: Apache-2.0\n"


def _artifact_files() -> dict[str, str]:
    """The artifact's own inventory, as the contents of a throwaway tree."""
    items = manifest.inventory(ROOT, manifest.registration())
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


def _named(errors: list[str], path: str, phrase: str) -> bool:
    return any(error.startswith(f"{path}:") and phrase in error for error in errors)


def _inventory_is_computed_and_complete() -> None:
    items = manifest.inventory(ROOT, manifest.registration())
    paths = {entry["path"]: entry for entry in items["files"]}
    for rel in (manifest.GENERATOR, manifest.ARTIFACT_DOC, manifest.AGENDA,
                manifest.COMMAND_MODULE, *manifest.GENERATED):
        ensure(rel in paths, f"the inventory must carry {rel}")
    bound = cli.identity(ROOT, (manifest.GENERATOR,))["sources_sha256"]
    ensure(paths[manifest.GENERATOR]["sha256"] == bound[manifest.GENERATOR],
           "the manifest and the action receipts must hash bytes the same way")
    registered = {entry["action"] for entry in items["actions"]}
    ensure(registered == set(manifest.registration()["choices"]) and manifest.ACTION in registered,
           "every accepted action is inventoried, read from the parser")
    ensure(all(entry["replay"].endswith("--json") for entry in items["actions"]),
           "each action carries its exact replay command")
    scale = next(entry for entry in items["actions"] if entry["action"] == "scale")
    ensure("--q5-max-leaves 1" in scale["replay"], "a budgeted action states its budget")
    ensure("tools/vos/static_memory_scale.py" in scale["declared_sources"]
           and "tools/vos/static_memory.py" in scale["declared_sources"],
           "an action's declared source set is its own plus the shared identity")
    errors = manifest.report(ROOT)["errors"]
    ensure(not errors, f"this tree's artifact is incomplete: {errors}")


def _copied_tree_reports_each_incompleteness() -> None:
    with sandbox_tree(_artifact_files()) as root:
        _commit(root)
        ensure(not manifest.report(root)["errors"], "the copied artifact must be complete")
        _place(root, "tools/vos/static_memory_orphan.py", SPDX)
        _place(root, "docs/implementation/static-memory-orphan.md", "# Orphan\n")
        _place(root, "tools/tests/test_static_memory_ghost.py", SPDX)
        _place(root, "proofs/StaticMemoryOrphan.v", "(* fixture *)\n")
        errors = manifest.report(root)["errors"]
        for path, phrase in (
                ("tools/vos/static_memory_orphan.py", "registered action"),
                ("docs/implementation/static-memory-orphan.md", "links to this document"),
                ("docs/implementation/static-memory-orphan.md", "carries no row"),
                ("tools/tests/test_static_memory_ghost.py", "'ghost'"),
                ("proofs/StaticMemoryOrphan.v", manifest.PROOF_LEDGER)):
            ensure(_named(errors, path, phrase),
                   f"no finding for {path} naming {phrase}: {errors}")
        _place(root, "docs/implementation/static-memory-experiments.md",
               (root / "docs/implementation/static-memory-experiments.md").read_text(
                   encoding="utf-8") + "\n[Orphan](static-memory-orphan.md) is reachable.\n")
        ensure(not _named(manifest.report(root)["errors"],
                          "docs/implementation/static-memory-orphan.md",
                          "links to this document"),
               "one inbound link from another document clears the reachability finding")


def _index_membership_decides_as_the_checker_reads_it() -> None:
    with sandbox_tree(_artifact_files()) as root:
        _commit(root)
        _place(root, "tools/vos/static_memory_ghost.py", SPDX, track=False)
        errors = manifest.report(root)["errors"]
        ensure(_named(errors, "tools/vos/static_memory_ghost.py", "git index does not carry"),
               f"an untracked module is a finding: {errors}")
        gone = "docs/implementation/static-memory-scaling.md"
        (root / gone).unlink()
        errors = manifest.report(root)["errors"]
        ensure(_named(errors, gone, "working tree does not carry it"),
               f"a tracked file the tree has lost is a finding: {errors}")


def _classification_join_holds_both_directions() -> None:
    files = _artifact_files()
    document = files[manifest.ARTIFACT_DOC]
    row = next(line for line in document.splitlines()
               if line.startswith("| [") and "static-memory-baseline.md)" in line)
    last = next(line for line in document.splitlines()
                if line.startswith("| [") and "static-memory-artifact.md)" in line)
    with sandbox_tree(files) as root:
        _commit(root)
        path = root / manifest.ARTIFACT_DOC
        path.write_text(document.replace(f"{row}\n", ""), encoding="utf-8", newline="")
        ensure(_named(manifest.report(root)["errors"],
                      "docs/implementation/static-memory-baseline.md", "carries no row"),
               "a document with no classification row is a finding")
        ghost = "| [Ghost](static-memory-ghost.md) | new conjecture | nowhere |"
        path.write_text(document.replace(last, f"{last}\n{ghost}"), encoding="utf-8",
                        newline="")
        ensure(_named(manifest.report(root)["errors"],
                      "docs/implementation/static-memory-ghost.md",
                      "names a document the artifact does not carry"),
               "a row naming no document is a finding")
        path.write_text(document.replace("elementary argument in prose", "folklore"),
                        encoding="utf-8", newline="")
        ensure(any("'folklore' is not one of the declared result classes" in error
                   for error in manifest.report(root)["errors"]),
               "a class outside the declared vocabulary is a finding")
        path.write_text(document.replace(manifest.CLASSIFICATION_HEADING, "## Elsewhere"),
                        encoding="utf-8", newline="")
        ensure(_named(manifest.report(root)["errors"], manifest.ARTIFACT_DOC,
                      "no classification table"),
               "a missing table is a finding rather than a vacuous pass")


def _replay_runs_every_other_action_and_the_default_runs_none() -> None:
    calls: list[str] = []

    def _record(action: str) -> manifest.ReplayEntry:
        calls.append(action)
        return manifest.ReplayEntry(action=action, argv=[action], exit_code=0,
                                    schema="fixture", scope="fixture", errors=[],
                                    receipt_sha256="fixture")

    with patch.object(manifest, "replay_action", _record):
        quiet = manifest.report(ROOT)
        ensure(not calls and quiet["replays"] == [],
               "the default manifest executes no experiment")
        ran = manifest.report(ROOT, replay=True)
    expected = set(manifest.registration()["choices"]) - {manifest.ACTION}
    ensure(set(calls) == expected and len(calls) == len(expected),
           f"--replay runs every other accepted action exactly once: {calls}")
    ensure(len(ran["replays"]) == len(expected), "each replay is recorded")


def _replayed_receipt_is_read_and_a_refusal_is_a_finding() -> None:
    entry = manifest.replay_action("structure")
    ensure(entry["argv"] == ["structure", "--json"] and entry["exit_code"] == 0,
           f"the structural action must replay: {entry}")
    ensure(entry["schema"] == "static-memory-experiment-v1" and entry["scope"] != "n/a"
           and not entry["errors"], f"the receipt's own schema and scope are read: {entry}")
    ensure(len(entry["receipt_sha256"]) == 64, "the receipt digest binds its bytes")
    with patch.object(cli.structure, "report",
                      return_value={"scope": "fixture", "errors": ["bad replay"]}):
        refused = manifest.replay_action("structure")
    ensure(refused["exit_code"] == 1 and "bad replay" in refused["errors"],
           f"a refusing action is recorded rather than aborting the sweep: {refused}")
    def _refuse(action: str) -> manifest.ReplayEntry:
        return manifest.ReplayEntry(action=action, argv=[action], exit_code=1,
                                    schema=refused["schema"], scope=refused["scope"],
                                    errors=list(refused["errors"]), receipt_sha256="fixture")

    with patch.object(manifest, "replay_action", _refuse):
        errors = manifest.report(ROOT, replay=True)["errors"]
    ensure(any("exited 1" in error and "bad replay" in error for error in errors),
           f"a replay that refused is a finding: {errors}")


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
        Case("manifest index membership decides", _index_membership_decides_as_the_checker_reads_it),
        Case("manifest classification join holds both directions",
             _classification_join_holds_both_directions),
        Case("manifest replay flag runs the minimal budgets",
             _replay_runs_every_other_action_and_the_default_runs_none),
        Case("manifest replayed receipt and refusal",
             _replayed_receipt_is_read_and_a_refusal_is_a_finding),
        Case("manifest readers fail closed", _readers_fail_closed_on_an_unreadable_subject),
    ]
