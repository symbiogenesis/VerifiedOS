# SPDX-License-Identifier: Apache-2.0
"""Select Host CI before allocating shard runners; no third-party imports."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vos.ci_scope import select_changes


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    event = cast("dict[str, object]", json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8")))
    event_name = os.environ["GITHUB_EVENT_NAME"]
    revision = os.environ.get("CI_REVISION") or os.environ["GITHUB_SHA"]
    base: str | None = None
    force_full = event_name not in {"push", "pull_request"} or os.environ.get("GITHUB_RUN_ATTEMPT", "1") != "1"
    comparison = select_changes(root, None, revision, force_full=force_full)
    if event_name == "push":
        value = event.get("before")
        base = value if isinstance(value, str) else None
    elif event_name == "pull_request":
        pull = cast("dict[str, object]", event.get("pull_request", {}))
        before, after = pull.get("base"), pull.get("head")
        if isinstance(before, dict) and isinstance(after, dict):
            before_sha, after_sha = before.get("sha"), after.get("sha")
            if (isinstance(before_sha, str) and re.fullmatch(r"[0-9a-f]{40}", before_sha)
                    and isinstance(after_sha, str) and re.fullmatch(r"[0-9a-f]{40}", after_sha)):
                try:
                    # PRs compare their head against the merge base; GITHUB_SHA
                    # remains the tested merge commit recorded in the selection.
                    result = subprocess.run(["git", "-C", str(root), "merge-base", before_sha, after_sha],
                                            capture_output=True, text=True, check=True, timeout=30)
                    base = result.stdout.strip()
                    comparison = select_changes(root, base, after_sha, force_full=force_full)
                    comparison["revision"] = revision
                except (OSError, subprocess.SubprocessError):
                    comparison = select_changes(root, None, revision, force_full=force_full)
            else:
                comparison = select_changes(root, None, revision, force_full=force_full)
        else:
            comparison = select_changes(root, None, revision, force_full=force_full)
    if event_name != "pull_request":
        comparison = select_changes(root, base, revision, force_full=force_full)
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8", newline="") as output:
        output.writelines(f"{key}={json.dumps(comparison[key])}\n" for key in ("host_full", "model_hooks"))
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8", newline="") as summary:
        summary.write("### CI selection\n\n```json\n" + json.dumps(comparison, indent=2) + "\n```\n")
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
