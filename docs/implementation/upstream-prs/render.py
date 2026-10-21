#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Render the upstream PR review snapshot; optionally refresh public GitHub state."""

import argparse
import json
import subprocess
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, cast


class Check(TypedDict, total=False):
    name: str
    context: str
    status: str
    state: str
    conclusion: str
    detailsUrl: str
    targetUrl: str


class Run(TypedDict):
    name: str
    status: str
    conclusion: str | None
    html_url: str


class Pull(TypedDict):
    number: int
    title: str
    url: str
    state: str
    isDraft: bool
    headRefOid: str
    updatedAt: str
    mergedAt: str | None
    statusCheckRollup: list[Check]
    workflow_runs: list[Run]


class Item(TypedDict):
    id: str
    repository: str
    topic: str
    issue: str | None
    pr: str | None
    benefit: str
    reviewed_head: str | None
    review: str
    next_action: str
    evidence: list[str]
    kind: NotRequired[Literal["backport"]]
    proposed_on: NotRequired[str]


class Snapshot(TypedDict):
    version: int
    author: str
    created_since: str
    reviewed_on: str
    observed_at: str
    items: list[Item]
    pulls: list[Pull]


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "snapshot.json"
OUTPUT = HERE.parent / "upstream-prs.md"
FIELDS = ("number,title,url,state,isDraft,headRefOid,updatedAt,mergedAt,statusCheckRollup")


def github(*args: str) -> str:
    """Keep native process working directories outside the checkout."""
    with tempfile.TemporaryDirectory(prefix="vos-upstream-prs-") as directory:
        result = subprocess.run(
            ["gh", *args], cwd=directory, capture_output=True, text=True,
            encoding="utf-8", check=True,
        )
    return result.stdout


def validate(snapshot: Snapshot) -> None:
    if snapshot["version"] != 1:
        raise ValueError("unsupported snapshot version")
    ids = [item["id"] for item in snapshot["items"]]
    if len(ids) != len(set(ids)) or not {str(i) for i in range(1, 16)}.issubset(ids):
        raise ValueError("preserve every original candidate ID exactly once")
    urls = [pull["url"] for pull in snapshot["pulls"]]
    mapped = [item["pr"] for item in snapshot["items"] if item["pr"] is not None]
    if len(urls) != len(set(urls)) or Counter(mapped) != Counter(urls):
        raise ValueError("every captured PR must map to exactly one item")
    for pull in snapshot["pulls"]:
        if pull["state"] not in {"OPEN", "CLOSED", "MERGED"}:
            raise ValueError(f"unknown PR state: {pull['url']}")
    for item in snapshot["items"]:
        if item.get("kind") not in {None, "backport"}:
            raise ValueError(f"unknown work item kind: {item['id']}")
        if item.get("kind") == "backport" and item["pr"] is not None:
            raise ValueError("map a submitted backport PR as a separate candidate")


def refresh(snapshot: Snapshot) -> None:
    """Refresh facts, retaining the human review of each explicitly named head."""
    discovered = cast(list[dict[str, object]], json.loads(github(
        "search", "prs", "--author", snapshot["author"], "--created",
        f">={snapshot['created_since']}", "--limit", "100", "--json", "url,repository",
    )))
    if len(discovered) >= 100:
        raise ValueError("discovery reached its limit; narrow or paginate the search")
    repositories = {item["repository"].casefold() for item in snapshot["items"]}
    known = {pull["url"] for pull in snapshot["pulls"]}
    for record in discovered:
        repository = cast(dict[str, str], record["repository"])["nameWithOwner"]
        if repository.casefold() in repositories and record["url"] not in known:
            raise ValueError(f"map this newly discovered upstream PR first: {record['url']}")
    pulls: list[Pull] = []
    for previous in snapshot["pulls"]:
        pull = cast(Pull, json.loads(github("pr", "view", previous["url"], "--json", FIELDS)))
        repository = "/".join(pull["url"].split("/")[3:5])
        response = cast(dict[str, list[dict[str, object]]], json.loads(github(
            "api", f"repos/{repository}/actions/runs", "--method", "GET",
            "-f", f"head_sha={pull['headRefOid']}", "-f", "per_page=100",
        )))
        runs = response["workflow_runs"]
        if len(runs) >= 100:
            raise ValueError(f"workflow discovery reached its limit: {pull['url']}")
        pull["workflow_runs"] = [cast(Run, {
            key: run[key] for key in ("name", "status", "conclusion", "html_url")
        }) for run in runs if run["head_sha"] == pull["headRefOid"]]
        pulls.append(pull)
    snapshot["pulls"] = pulls
    snapshot["observed_at"] = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    validate(snapshot)


def cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render(snapshot: Snapshot) -> str:
    validate(snapshot)
    pulls = {pull["url"]: pull for pull in snapshot["pulls"]}
    counts = Counter(pull["state"].lower() for pull in pulls.values())
    pending = sum(item["pr"] is None and item.get("kind") != "backport"
                  for item in snapshot["items"])
    backports = sum(item.get("kind") == "backport" for item in snapshot["items"])
    lines = [
        "# Upstream pull request tracker", "",
        "<!-- Generated by upstream-prs/render.py from upstream-prs/snapshot.json. -->", "",
        f"Submitted PR review dated **{snapshot['reviewed_on']} (America/Chicago)**. "
        f"GitHub status observed **{snapshot['observed_at']}**, for `{snapshot['author']}`.", "",
        "This tracker preserves the original candidate numbers and includes the related "
        "CertiRocq Docker CI repair. **TBD** means no matching authored PR is recorded. "
        "Additional recommendations carry their own proposal dates; the GitHub facts "
        "retain the observation time above. Backport follow-ups are counted separately.", "",
        f"Submitted PRs: **{len(pulls)}**; open: **{counts['open']}**; "
        f"merged: **{counts['merged']}**; closed without merge: **{counts['closed']}**; "
        f"candidates marked TBD: **{pending}**; backport follow-ups: **{backports}**.", "",
        "The review inspected diffs, PR descriptions, public checks and discussion. "
        "It ran no independent upstream builds or tests. An upstream merge does not "
        "establish adoption or qualification of the change in VerifiedOS. "
        "An absent check result, action-required run, or neutral result is not a passing gate.", "",
        "## Candidate status", "",
        "| ID | Upstream / work item | PR | Status | Next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in snapshot["items"]:
        pull = pulls.get(item["pr"] or "")
        link = (f"[#{pull['number']}]({pull['url']})" if pull else
                f"[Reference]({item['issue']})" if item["issue"] is not None else "n/a")
        status = ("Draft" if pull["isDraft"] else pull["state"].capitalize()) if pull else "**TBD**"
        if item.get("kind") == "backport":
            status = "Backport follow-up"
        lines.append(f"| {item['id']} | `{item['repository']}` — {cell(item['topic'])} | "
                     f"{link} | {status} | {cell(item['next_action'])} |")
    lines.extend(["", "## Unsubmitted candidates and follow-ups", "",
                  "Proposed PRs remain unsubmitted until an authored PR is mapped. "
                  "Backport follow-ups use the upstream release-management process. "
                  "The records below identify project benefit, scope, evidence and next action; "
                  "they supply no implementation or qualification verdict.", ""])
    for item in snapshot["items"]:
        if item["pr"] is not None:
            continue
        lines.extend([f"### {item['id']}. {item['repository']} — {item['topic']}", ""])
        if "proposed_on" in item:
            lines.extend([f"**Proposed:** {item['proposed_on']} (America/Chicago).", ""])
        lines.extend([f"**Project benefit:** {item['benefit']}", "",
                      f"**Scope and readiness:** {item['review']}", ""])
        if item["evidence"]:
            lines.extend(["**Evidence and acceptance:**", ""])
            lines.extend(f"- {entry}" for entry in item["evidence"])
            lines.append("")
        lines.extend([f"**Next action:** {item['next_action']}", ""])
    lines.extend(["## Submitted PR review", ""])
    for item in snapshot["items"]:
        if item["pr"] is None:
            continue
        pull = pulls[item["pr"]]
        lines.extend([
            f"### {item['id']}. {item['repository']} #{pull['number']}", "",
            f"[{pull['title']}]({pull['url']}) — **{pull['state'].capitalize()}**.", "",
            f"Current head: `{pull['headRefOid']}`. PR updated: `{pull['updatedAt']}`.", "",
            f"**Project benefit:** {item['benefit']}", "",
            f"**Static review:** {item['review']}", "",
        ])
        if item["reviewed_head"] != pull["headRefOid"]:
            lines.extend(["**Review stale:** the current head differs from the reviewed "
                          f"head `{item['reviewed_head']}`. Re-review the new diff.", ""])
        if pull["mergedAt"] is not None:
            lines.extend([f"Merged: `{pull['mergedAt']}`.", ""])
        lines.extend(["**Public checks:**", ""])
        for check in pull["statusCheckRollup"]:
            name = check.get("name") or check.get("context") or "Unnamed check"
            verdict = check.get("conclusion") or check.get("state") or check.get("status")
            url = check.get("detailsUrl") or check.get("targetUrl")
            label = f"[{cell(name)}]({url})" if url is not None and url else cell(name)
            lines.append(f"- {label}: **{verdict or 'UNKNOWN'}**.")
        if not pull["statusCheckRollup"]:
            lines.append("- No check-run or commit-status result is displayed on the PR.")
        lines.extend(["", "**Actions runs for this head:**", ""])
        for run in pull["workflow_runs"]:
            verdict = run["conclusion"] or run["status"]
            lines.append(f"- [{cell(run['name'])}]({run['html_url']}): **{verdict}**.")
        if not pull["workflow_runs"]:
            lines.append("- No Actions workflow run was found for this head.")
        if item["evidence"]:
            lines.extend(["", "**Additional evidence:**", ""])
            lines.extend(f"- {entry}" for entry in item["evidence"])
        lines.extend(["", f"**Next action:** {item['next_action']}", ""])
    lines.extend([
        "## Maintenance", "",
        "[snapshot.json](upstream-prs/snapshot.json) owns the candidate mapping, "
        "captured GitHub facts and human review notes. Refresh public status with the "
        "configured read-only GitHub CLI queries, then regenerate and check:", "",
        "```powershell", "python docs/implementation/upstream-prs/render.py --refresh",
        "python docs/implementation/upstream-prs/render.py --check", "```", "",
        "Refresh preserves review notes and flags changed PR heads. New authored PRs "
        "in a listed upstream stop refresh until their mapping is reviewed. Update the "
        "human review and next action when discussion or evidence changes; "
        "`--check` checks agreement with the captured snapshot, not live GitHub freshness.", "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="compare without writing or network")
    mode.add_argument("--refresh", action="store_true", help="refresh public GitHub state first")
    args = parser.parse_args()
    snapshot = cast(Snapshot, json.loads(SOURCE.read_text(encoding="utf-8")))
    if args.refresh:
        refresh(snapshot)
        SOURCE.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8", newline="\n")
    expected = render(snapshot)
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != expected:
            print("FAIL upstream-prs: regenerate the Markdown from snapshot.json")
            return 1
        print("ok upstream-prs: Markdown matches the captured snapshot")
    else:
        OUTPUT.write_text(expected, encoding="utf-8", newline="\n")
        print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
