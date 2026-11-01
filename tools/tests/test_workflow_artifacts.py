# SPDX-License-Identifier: Apache-2.0
"""Standalone evidence routes retain usable artifact identities after reruns."""

import re

from tests import test_fanout_ci as workflows
from tests.harness import TOOLS, Case, ensure


def stable_uploads_replace() -> None:
    for name in ("model-snapshot", "openssl-qualification"):
        contents = (TOOLS.parent / f".github/workflows/{name}.yml").read_text(encoding="utf-8")
        uploads = [step for job in workflows._workflow_jobs(contents).values()
                   for step in workflows._step_texts(job) if "uses: actions/upload-artifact@" in step]
        ensure(bool(uploads), f"{name} retains its evidence artifact")
        for step in uploads:
            settings = workflows._step_block(step, "with")
            ensure(any(re.fullmatch(r"          overwrite: true", line) for line in settings),
                   f"{name}'s stable artifact name otherwise collides on rerun")
            ensure(any(line.startswith(f"          name: {name}-") for line in settings)
                   and not any("github.run_attempt" in line for line in settings if "name:" in line),
                   f"{name} keeps the artifact name its consumers use")


def cases() -> list[Case]:
    return [Case("stable-artifact-rerun-replacement", stable_uploads_replace)]
