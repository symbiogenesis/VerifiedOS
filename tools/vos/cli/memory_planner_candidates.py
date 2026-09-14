# SPDX-License-Identifier: Apache-2.0
"""Build and compare the optional pinned idealloc candidate behind checked fallback."""

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from vos import env
from vos import memory_planner as planner
from vos import memory_planner_candidates as candidates
from vos.cli.memory_planner import read_json
from vos.corpus import find_root


def run(args: argparse.Namespace, root: Path, output: Path) -> dict[str, Any]:
    if not 0 < args.timeout <= 300 or not 1 <= args.iterations <= 100:
        raise ValueError("invalid candidate process limits")
    if args.action != "plan" and (args.instance is not None or args.baseline is not None):
        raise ValueError("instance and baseline inputs are accepted only by plan")
    if args.action == "logs":
        return {"logs": {name: "\n".join((output / name).read_text(encoding="utf-8").splitlines()[-60:])
                         for name in ("rust-install.log", "compile.log") if (output / name).is_file()}}
    inputs: dict[str, str] = {}
    result: dict[str, Any]
    if args.action == "plan":
        if args.instance is None or args.baseline is None:
            raise ValueError("plan requires --instance and --baseline")
        instance = planner.parse_instance(read_json(args.instance, inputs))
        baseline = read_json(args.baseline, inputs)
        result = planner.plan(instance, baseline)
        if result["placement"] is None:
            raise ValueError("invalid baseline; optional build and search not started")
        # Build is also optional candidate work: failure retains the checked baseline.
        try:
            candidates.supported(instance)
            build = candidates.build_idealloc(root, output)
            candidate = candidates.IdeallocCandidate(Path(build["executable"]), build["executable_sha256"],
                                                     output, timeout=args.timeout, iterations=args.iterations)
            result = planner.plan(instance, baseline, candidates=(candidate,))
            result.update(build=build, candidate=candidate.last_evidence)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            result["candidate"] = {"status": "rejected/unsupported", "reason": str(error)}
    else:
        build = candidates.build_idealloc(root, output)
        result = candidates.compare(Path(build["executable"]), build["executable_sha256"], output,
                                    timeout=args.timeout, iterations=args.iterations)
        result["build"] = build
    result["input_sha256"] = inputs
    result["sources_sha256"] = {name: candidates.digest(root / name) for name in
                                (candidates.PIN_PATH, candidates.BRIDGE_PATH,
                                 "tools/vos/memory_planner_candidates.py", "tools/vos/memory_planner.py",
                                 "tools/vos/cli/memory_planner_candidates.py")}
    output.mkdir(parents=True, exist_ok=True)
    (output / "latest-evidence.json").write_text(json.dumps(result, indent=2), encoding="utf-8", newline="")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("demo", "plan", "logs"))
    parser.add_argument("--instance", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = find_root()
    output = env.lane_root(env.lane_of(root)) / "memory-planner-idealloc"
    try:
        result = run(args, root, output)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "failed", "reason": str(error)}))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else f"{result.get('status', 'checked plan')}: {output / 'latest-evidence.json'}")
    return 1 if result.get("status") == "failed" else 0
