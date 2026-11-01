# SPDX-License-Identifier: Apache-2.0
"""Changed-file selection preserves consumers and treats uncertainty conservatively."""

import copy
import io
import json
import os
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from typing import cast
from unittest.mock import patch

from ci import select_changes as hosted
from tests.harness import Case, ensure, sandbox_tree
from vos import ci_scope as scope

INDEPENDENT_CASES = True


def _classifications() -> None:
    for path in ("README.md", "AGENTS.md", "PLAN.md", "docs/background/critique.md",
                 "docs/assurance/proof-assistance.md", "tools/README.md", "firmware/README.md"):
        decision = scope.classify([path])
        ensure(decision == {"host_full": False, "model_hooks": False, "guest_lanes": []},
               f"ordinary prose keeps document checks alone: {path}: {decision}")
    ensure(scope.classify(["model/doc/README.md"])
           == {"host_full": False, "model_hooks": True, "guest_lanes": []},
           "the curated model's Markdown still runs its hooks")
    for path in ("docs/spec.md", "docs/requirements-register.md", "docs/hardware/new.md",
                 "docs/languages/new.md", "docs/implementation/contracts/new.md",
                 "docs/implementation/phase-service/new.md", "docs/implementation/placement-search.md",
                 "docs/assurance/field-bindings.md", "interfaces/README.md",
                 "docs/implementation/compute-feature-map.md", "docs/background/math-evidence.md",
                 "docs/background/static-memory-research.md", "docs/implementation/static-memory/new.md",
                 "docs/assurance/differential-corpus.md", "docs/assurance/crown-jewels.md",
                 "docs/assurance/wire-format-inventory.md",
                 "rtl/synthesis-provenance.md", "tools/tests/fixtures/input.md",
                 "tools/ci/bootstrap_guest.py", ".github/workflows/host-gates.yml",
                 ".github/actions/setup-target-sail/action.yml",
                 "unknown/new.file", "../README.md", "/README.md", "docs//README.md"):
        decision = scope.classify([path])
        ensure(decision == scope.classify([]), f"executable or unknown input keeps all CI: {path}")
    for paths, lanes, hooks in ((["model/core.sail"], ["model", "rtl"], True),
                                (["rtl/core.sv"], ["rtl"], False),
                                (["proofs/Core.v"], ["proofs"], False),
                                (["README.md", "rtl/core.sv", "proofs/Core.v"], ["rtl", "proofs"], False),
                                (["model/core.sail", "proofs/Core.v"], list(scope.ALL_GUEST_LANES), True)):
        ensure(scope.classify(paths)
               == {"host_full": True, "model_hooks": hooks, "guest_lanes": lanes},
               f"source selection is the union of consuming lanes: {paths}")


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, check=True, timeout=30)
    return done.stdout.strip()


def _commit(root: Path) -> str:
    _git(root, "-c", "user.name=CI test", "-c", "user.email=ci@example.invalid",
         "-c", "commit.gpgsign=false", "commit", "-qm", "fixture")
    return _git(root, "rev-parse", "HEAD")


def _comparisons() -> None:
    with sandbox_tree({"model/source.sail": "source\n", "docs/old.md": "prose\n"}) as root:
        base = _commit(root)
        _git(root, "mv", "model/source.sail", "docs/moved.md")
        _git(root, "rm", "docs/old.md")
        revision = _commit(root)
        selected = scope.select_changes(root, base, revision)
        ensure(selected["paths"] == ["docs/moved.md", "docs/old.md", "model/source.sail"]
               and selected["guest_lanes"] == ["model", "rtl"],
               "renaming source into docs cannot conceal the deleted source dependency")
        ensure(scope.validate_selection(selected, revision) == selected,
               "a frozen complete comparison round trips without changing scope")
        for missing in (None, "0" * 40, "f" * 40, "HEAD", revision):
            broad = scope.select_changes(root, missing, revision)
            ensure(broad["host_full"] and broad["model_hooks"]
                   and broad["guest_lanes"] == list(scope.ALL_GUEST_LANES),
                   f"missing history or an empty comparison cannot skip CI: {missing}")
        forced = scope.select_changes(root, base, revision, force_full=True)
        ensure(forced["guest_lanes"] == list(scope.ALL_GUEST_LANES)
               and forced["reason"] == "full override" and forced["paths"] == selected["paths"],
               "explicit full acceptance preserves the compared paths and broadens every gate")
        for broken in (dict(selected, guest_lanes=[]), dict(selected, revision=base),
                       dict(selected, reason="not needed"), dict(selected, host_full=1),
                       dict(selected, paths=list(reversed(selected["paths"]))),
                       dict(selected, extra=True)):
            try:
                scope.validate_selection(broken, revision)
            except ValueError:
                pass
            else:
                raise AssertionError(f"malformed or narrowed selection was accepted: {broken}")


def _hosted_events() -> None:
    with sandbox_tree({"README.md": "base\n", "model/core.sail": "source\n"}) as root:
        base = _commit(root)
        (root / "README.md").write_text("new prose\n", encoding="utf-8")
        _git(root, "add", "--", "README.md")
        prose = _commit(root)
        # Main advances independently while the PR's source head remains prose-only.
        _git(root, "checkout", "--detach", base)
        (root / "model/core.sail").write_text("main advance\n", encoding="utf-8")
        _git(root, "add", "--", "model/core.sail")
        main = _commit(root)

        def run(event_name: str, event: dict[str, object], attempt: str = "1") -> dict[str, object]:
            event_path, output, summary = root / "event.json", root / "output", root / "summary"
            event_path.write_text(json.dumps(event), encoding="utf-8")
            output.write_text("", encoding="utf-8")
            environment = {"GITHUB_EVENT_NAME": event_name, "GITHUB_EVENT_PATH": str(event_path),
                           "GITHUB_SHA": prose, "GITHUB_OUTPUT": str(output),
                           "GITHUB_STEP_SUMMARY": str(summary), "GITHUB_RUN_ATTEMPT": attempt}
            captured = io.StringIO()
            with patch.dict(os.environ, environment), patch.object(
                    hosted, "__file__", str(root / "tools/ci/select_changes.py")), redirect_stdout(captured):
                hosted.main()
            return cast("dict[str, object]", json.loads(captured.getvalue()))

        ensure(run("push", {"before": base})["host_full"] is False,
               "a push selects its complete before/after comparison")
        ensure(run("pull_request", {"pull_request": {"base": {"sha": main}, "head": {"sha": prose}}})
               ["host_full"] is False,
               "a PR selects its head against the merge base, excluding main's independent changes")
        ensure(run("pull_request", {"pull_request": {"base": {}, "head": {}}})["host_full"] is True,
               "unavailable PR history keeps full CI")
        with patch.object(hosted.subprocess, "run", side_effect=AssertionError("unvalidated Git input")):
            ensure(run("pull_request", {"pull_request": {"base": {"sha": "--help"}, "head": {"sha": prose}}})
                   ["host_full"] is True, "malformed PR revisions never reach Git")
        ensure(run("workflow_dispatch", {})["host_full"] is True
               and run("push", {"before": base}, "2")["host_full"] is True,
               "manual dispatch and explicit reruns request complete Host CI")
        with patch.dict(os.environ, {"CI_REVISION": base}):
            ensure(run("workflow_dispatch", {})["revision"] == base,
                   "a dispatch pinned behind main reports the checked-out revision")


def _guest_overrides() -> None:
    with sandbox_tree({"README.md": "base\n"}) as root:
        base = _commit(root)
        (root / "README.md").write_text("updated prose\n", encoding="utf-8")
        _git(root, "add", "--", "README.md")
        revision = _commit(root)
        selected = scope.select_changes(root, base, revision, force_guest=True)
        ensure(not selected["host_full"] and not selected["model_hooks"]
               and selected["guest_lanes"] == list(scope.ALL_GUEST_LANES)
               and selected["reason"] == "guest override",
               "guest acceptance expands guest lanes while preserving prose's Host scope")
        ensure(scope.validate_selection(selected, revision) == selected,
               "the narrower override round trips through its journal validator")
        for broken in (dict(selected, host_full=True), dict(selected, model_hooks=True),
                       dict(selected, guest_lanes=["proofs"]), dict(selected, base=None),
                       dict(selected, paths=[])):
            try:
                scope.validate_selection(broken, revision)
            except ValueError:
                pass
            else:
                raise AssertionError(f"noncanonical guest override was accepted: {broken}")
        forced = scope.select_changes(root, base, revision, force_guest=True, force_full=True)
        ensure(forced["host_full"] and forced["model_hooks"] and forced["reason"] == "full override",
               "explicit full CI takes precedence over a guest-only override")
        for missing in (None, revision):
            fallback = scope.select_changes(root, missing, revision, force_guest=True)
            ensure(fallback["host_full"] and fallback["model_hooks"]
                   and fallback["reason"] in {"comparison unavailable", "empty comparison"},
                   "guest overrides never narrow unavailable or empty comparisons")


def _malformed_journal() -> None:
    paths = ["README.md"]
    selected: scope.Selection = {**scope.classify(paths), "base": "b" * 40,
                                 "revision": "a" * 40, "paths": paths, "reason": "changed paths"}
    for field, value in (("paths", ["../README.md"]), ("base", "HEAD"),
                         ("paths", ["README.md", "README.md"]), ("guest_lanes", ["unknown"]),
                         ("paths", []), ("base", None)):
        broken: dict[str, object] = copy.deepcopy(dict(selected))
        broken[field] = value
        try:
            scope.validate_selection(broken, selected["revision"])
        except ValueError:
            pass
        else:
            raise AssertionError(f"malformed frozen CI selection was accepted: {broken}")


def cases() -> list[Case]:
    return [Case("known-prose-and-source-consumers", _classifications),
            Case("complete-git-comparisons-and-full-fallbacks", _comparisons),
            Case("hosted-push-pr-and-manual-selection", _hosted_events),
            Case("guest-overrides-preserve-host-scope", _guest_overrides),
            Case("frozen-selection-refuses-malformed-records", _malformed_journal)]
