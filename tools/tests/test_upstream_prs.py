# SPDX-License-Identifier: Apache-2.0
"""Upstream watches stay separate from authored work and retain review freshness."""

import copy
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure

type Record = dict[str, Any]


def _renderer() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "docs/implementation/upstream-prs/render.py"
    spec = importlib.util.spec_from_file_location("upstream_prs_render", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load upstream PR renderer: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RENDERER = _renderer()


def _item(identifier: str, pr: str | None = None) -> Record:
    return {
        "id": identifier, "repository": "owner/project", "topic": f"Work {identifier}",
        "issue": None, "pr": pr, "benefit": f"Benefit {identifier}",
        "reviewed_head": "a" * 40 if pr is not None else None,
        "review": f"Human review {identifier}", "next_action": f"Action {identifier}",
        "evidence": [f"Evidence {identifier}"],
    }


def _pull(number: int, state: str = "OPEN") -> Record:
    return {
        "number": number, "title": f"Fix {number}",
        "url": f"https://github.com/owner/project/pull/{number}", "state": state,
        "isDraft": False, "headRefOid": "a" * 40, "updatedAt": "2026-10-22T10:00:00Z",
        "mergedAt": "2026-10-21T10:00:00Z" if state == "MERGED" else None,
        "statusCheckRollup": [], "workflow_runs": [],
    }


def _snapshot() -> Record:
    return {
        "version": 1, "author": "fixture-author", "created_since": "2026-10-19",
        "reviewed_on": "2026-10-22", "observed_at": "2026-10-22 11:00:00 UTC",
        "items": [_item(str(i)) for i in range(1, 16)], "pulls": [],
    }


def _rejected(snapshot: Record, message: str) -> None:
    try:
        RENDERER.validate(snapshot)
    except ValueError as exc:
        ensure(message in str(exc), f"unexpected refusal: {exc}")
    else:
        raise AssertionError(f"invalid snapshot accepted; expected {message}")


def _authored_and_watched_counts() -> None:
    snapshot = _snapshot()
    for number, state in enumerate(("OPEN", "MERGED", "CLOSED"), 1):
        authored = _pull(number, state)
        snapshot["pulls"].append(authored)
        snapshot["items"][number - 1]["pr"] = authored["url"]
        watched = _pull(number + 20, state)
        snapshot["pulls"].append(watched)
        snapshot["items"].append({**_item(f"W-{number}", watched["url"]),
                                  "kind": "watch", "priority": "high"})
    snapshot["items"].extend([
        {**_item("R-1"), "kind": "backport"},
        {**_item("I-1"), "kind": "proposal", "priority": "highest"},
    ])
    output = RENDERER.render(snapshot)
    ensure("Submitted PRs: **3**; open: **1**; merged: **1**; closed without merge: **1**"
           in output, "upstream-owned work inflated authored submission counts")
    ensure("Upstream PR watches: **3**; open: **1**; merged: **1**; "
           "closed without merge: **1**" in output,
           "watched states were omitted or counted as authored work")
    ensure("candidates marked TBD: **12**; backport follow-ups: **1**; "
           "issue proposals marked TBD: **1**" in output,
           "ordinary candidates, issue proposals and backports need distinct counts")
    submitted, watched = output.split("## Submitted PR review\n", 1)[1].split(
        "## Upstream PR watchlist\n", 1)
    ensure("### 1. " in submitted and "### W-1. " not in submitted,
           "the authored review section included a watched PR")
    ensure("### W-1. " in watched and "### 1. " not in watched,
           "the watchlist lost its distinct classification")
    ensure("**Priority:** High." in watched and "**Priority:** Highest." in output,
           "priorities need to be visible in detail entries")
    ensure("| Priority |" in output and "| 4 | `owner/project` — Work 4 | n/a |" in output,
           "the status table needs priorities and an explicit absent value")
    ensure("| n/a | **TBD** | Action 4 |" in output
           and "**TBD — issue proposal**" in output and "Backport follow-up" in output,
           "the three forms of unsubmitted work became indistinguishable")


def _old_schema_remains_valid() -> None:
    snapshot = _snapshot()
    pull = _pull(1)
    snapshot["pulls"].append(pull)
    snapshot["items"][0]["pr"] = pull["url"]
    snapshot["items"][0]["reviewed_head"] = pull["headRefOid"]
    output = RENDERER.render(snapshot)
    ensure("Submitted PRs: **1**" in output and "candidates marked TBD: **14**" in output,
           "version 1 snapshots without new optional fields changed classification")
    ensure("**Review stale:**" not in output, "an unchanged reviewed head was made stale")


def _classification_validation() -> None:
    base = _snapshot()
    for kind in (None, "unknown"):
        snapshot = copy.deepcopy(base)
        snapshot["items"].append({**_item("X"), "kind": kind})
        _rejected(snapshot, "unknown work item kind")
    for priority in (None, "low", "", 1):
        snapshot = copy.deepcopy(base)
        snapshot["items"][0]["priority"] = priority
        _rejected(snapshot, "unknown work item priority")
    for priority in ("highest", "high", "medium"):
        snapshot = copy.deepcopy(base)
        snapshot["items"][0]["priority"] = priority
        RENDERER.validate(snapshot)
    for kind in ("watch", "proposal", "backport"):
        snapshot = copy.deepcopy(base)
        snapshot["items"][0]["kind"] = kind
        _rejected(snapshot, "original candidate's authored classification")
    snapshot = copy.deepcopy(base)
    snapshot["items"].append({**_item("W"), "kind": "watch"})
    _rejected(snapshot, "watch item requires a mapped PR")
    for kind, message in (("proposal", "issue proposal cannot have a mapped PR"),
                          ("backport", "submitted backport PR")):
        snapshot = copy.deepcopy(base)
        pull = _pull(30)
        snapshot["items"].append({**_item("X", pull["url"]), "kind": kind})
        snapshot["pulls"].append(pull)
        _rejected(snapshot, message)


def _capture_mapping_remains_bijective() -> None:
    snapshot = _snapshot()
    pull = _pull(30)
    snapshot["items"].append({**_item("W", pull["url"]), "kind": "watch"})
    snapshot["pulls"].append(pull)
    RENDERER.validate(snapshot)
    for change in ("duplicate-mapping", "uncaptured", "unmapped", "duplicate-capture"):
        invalid = copy.deepcopy(snapshot)
        if change == "duplicate-mapping":
            invalid["items"][0]["pr"] = pull["url"]
        elif change == "uncaptured":
            invalid["pulls"] = []
        elif change == "unmapped":
            invalid["pulls"].append(_pull(31))
        else:
            invalid["pulls"].append(copy.deepcopy(pull))
        _rejected(invalid, "every captured PR must map to exactly one item")
    invalid = copy.deepcopy(snapshot)
    invalid["items"].pop(0)
    _rejected(invalid, "preserve every original candidate ID")


def _refresh_reads_watches_and_preserves_human_review() -> None:
    snapshot = _snapshot()
    authored, watched = _pull(1), _pull(30)
    snapshot["items"][0].update(pr=authored["url"], reviewed_head=authored["headRefOid"])
    snapshot["items"].append({**_item("W", watched["url"]), "kind": "watch"})
    snapshot["pulls"] = [authored, watched]
    updated = copy.deepcopy(watched)
    updated.update(headRefOid="b" * 40, state="MERGED", mergedAt="2026-10-22T12:00:00Z")
    updated["statusCheckRollup"] = [{"name": "Upstream validation", "conclusion": "NEUTRAL",
                                     "detailsUrl": "https://example.com/check"}]
    calls: list[tuple[str, ...]] = []

    def github(*args: str) -> str:
        calls.append(args)
        if args[:2] == ("search", "prs"):
            return "[]"
        if args[:2] == ("pr", "view"):
            return json.dumps(updated if args[2] == watched["url"] else authored)
        if args[0] == "api":
            head = args[args.index("-f") + 1].removeprefix("head_sha=")
            return json.dumps({"workflow_runs": [
                {"name": "Current workflow", "status": "completed", "conclusion": "success",
                 "html_url": "https://example.com/current", "head_sha": head},
                {"name": "Other head", "status": "completed", "conclusion": "failure",
                 "html_url": "https://example.com/old", "head_sha": "c" * 40},
            ]})
        raise AssertionError(f"unexpected GitHub request: {args}")

    with patch.object(RENDERER, "github", side_effect=github):
        RENDERER.refresh(snapshot)
    ensure(any(call[:3] == ("pr", "view", watched["url"]) for call in calls),
           "refresh skipped an explicitly mapped upstream-owned PR")
    ensure(any("head_sha=" + "b" * 40 in call for call in calls),
           "workflow capture did not follow the watched PR's new head")
    ensure(snapshot["items"][-1]["reviewed_head"] == "a" * 40
           and snapshot["items"][-1]["review"] == "Human review W",
           "refresh rewrote a human review to bless an unseen head")
    output = RENDERER.render(snapshot)
    submitted, watchlist = output.split("## Submitted PR review\n", 1)[1].split(
        "## Upstream PR watchlist\n", 1)
    ensure("**Review stale:**" not in submitted and "**Review stale:**" in watchlist,
           "the watched head changed without an attributed stale-review warning")
    ensure("**Merged**" in watchlist and "**NEUTRAL**" in watchlist
           and "https://example.com/check" in watchlist
           and "https://example.com/current" in watchlist
           and "Other head" not in output,
           "watch rendering dropped upstream status or mixed workflow heads")


def _authored_discovery_still_requires_mapping() -> None:
    snapshot = _snapshot()
    newly_found = [{"url": "https://github.com/owner/project/pull/80",
                    "repository": {"nameWithOwner": "Owner/Project"}}]
    with patch.object(RENDERER, "github", return_value=json.dumps(newly_found)) as github:
        try:
            RENDERER.refresh(snapshot)
        except ValueError as exc:
            ensure("map this newly discovered upstream PR first" in str(exc),
                   f"unexpected discovery refusal: {exc}")
        else:
            raise AssertionError("new authored work was silently absent from the tracker")
    ensure(github.call_count == 1 and "--author" in github.call_args.args
           and "fixture-author" in github.call_args.args,
           "discovery must remain author-bounded and refuse before refreshing captured facts")


def cases() -> list[Case]:
    return [
        Case("authored submissions, watches and unsubmitted work stay distinct",
             _authored_and_watched_counts),
        Case("existing version 1 snapshots retain authored classification", _old_schema_remains_valid),
        Case("classifications, priorities and original IDs are validated", _classification_validation),
        Case("every captured PR still maps to one item", _capture_mapping_remains_bijective),
        Case("refresh captures watches without blessing changed heads",
             _refresh_reads_watches_and_preserves_human_review),
        Case("new authored discovery still requires human mapping",
             _authored_discovery_still_requires_mapping),
    ]
