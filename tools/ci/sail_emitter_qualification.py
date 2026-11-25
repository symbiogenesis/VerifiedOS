#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Rebuild the immutable Q35o emitter and qualify its canonical emission on GitHub Actions."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vos import env, receipts, rocqterm

EVIDENCE = Path("docs/implementation/retained-evidence")
SCOPED = EVIDENCE / "q35o-scope-20261023"
INITIAL = EVIDENCE / "close3-q35o-20261013"
BUILD_TARGET = "src/sail_coq_backend/sail_plugin_coq.cmxs"
BACKEND_SOURCE = "src/sail_coq_backend/pretty_print_coq.ml"
PLUGIN = Path(BUILD_TARGET).name


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def exact(path: Path, expected: str) -> None:
    if receipts.digest(path) != expected:
        raise ValueError(f"unexpected SHA-256 for {path}")


def evidence_input(directory: Path, name: str) -> Path:
    path = directory / name
    exact(path, load(directory / "manifest.json")["files"][name]["sha256"])
    return path


def command(argv: list[str], checkout: Path, log: Path, *, timeout: int,
            environment: dict[str, str]) -> None:
    with log.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps(argv) + "\n")
        stream.flush()
        subprocess.run(["timeout", "--kill-after=30s", str(timeout), *argv],
                       cwd=checkout, env=environment, check=True, timeout=timeout + 40,
                       stdout=stream, stderr=subprocess.STDOUT)


def source_candidate(checkout: Path, root: Path, upload: Path,
                     environment: dict[str, str]) -> tuple[Path, dict[str, object]]:
    source_lock = checkout / "tools/sail-lsp/sources.lock.json"
    sail_source, = [row for row in load(source_lock)["sources"] if row["name"] == "sail"]
    if sail_source["version"] != env.SAIL_VERSION:
        raise ValueError("the checked release source differs from the locked Sail version")
    archive = root / "sail.tbz"
    receipts.download(sail_source["url"], archive, sail_source["sha256"])
    destination = root / "source"
    destination.mkdir()
    with tarfile.open(archive) as source:
        source.extractall(destination, filter="data")
    checkout_source = destination / sail_source["directory"]
    if list(destination.iterdir()) != [checkout_source]:
        raise ValueError("Sail source archive has an unexpected root")
    license_path = evidence_input(checkout / SCOPED, "LICENSE.sail")
    exact(checkout_source / "LICENSE", receipts.digest(license_path))
    patch = evidence_input(checkout / SCOPED, "sail-emission-syntax.patch")
    dune_project = evidence_input(checkout / INITIAL, "backend-dune-project.txt")

    backend = root / "backend"
    (backend / "src").mkdir(parents=True)
    shutil.copytree(checkout_source / "src/sail_coq_backend", backend / "src/sail_coq_backend")
    shutil.copyfile(dune_project, backend / "dune-project")
    original = receipts.snapshot(backend, (path for path in backend.rglob("*") if path.is_file()))
    command(["patch", "--batch", "--forward", "--fuzz=0", "-p1", "-i", str(patch)],
            backend, upload / "patch.log", timeout=60, environment=environment)
    candidate = receipts.snapshot(backend, (path for path in backend.rglob("*") if path.is_file()))
    if original.keys() != candidate.keys() or {
        path for path in candidate if original[path] != candidate[path]
    } != {BACKEND_SOURCE}:
        raise ValueError("patch did not change exactly the reviewed Rocq backend source")
    command(["opam", "exec", f"--switch={env.SAIL_SWITCH}", "--",
             "dune", "build", "--root", str(backend), BUILD_TARGET],
            backend, upload / "build.log", timeout=600, environment=environment)
    plugin = backend / "_build/default" / BUILD_TARGET
    return plugin, {
        "release": sail_source,
        "release_source_lock_sha256": receipts.digest(source_lock),
        "license_sha256": receipts.digest(license_path),
        "patch_sha256": receipts.digest(patch),
        "original_sources": original,
        "candidate_sources": candidate,
        "candidate_plugin_sha256": receipts.digest(plugin),
    }


def check_comparison(stock: dict[str, Any], candidate: dict[str, Any], repeat: dict[str, Any], *,
                     revision: str, original_plugin: str, patched_plugin: str) -> None:
    """Check scope, exact paired inputs and repeat output identities from the native launcher."""
    expected = {"revision": revision, "model_dirty": False}
    for emission in (stock, candidate, repeat):
        if (emission["checkout"] != expected or emission["format"] != rocqterm.FORMAT
                or emission["target"] != rocqterm.TARGET
                or emission["command"].count("--rocq") != 1
                or set(emission["outputs"]) != set(rocqterm.OUTPUTS)):
            raise ValueError("emission receipt differs from the selected clean canonical target")
    for key in ("inputs", "command", "axioms"):
        if stock[key] != candidate[key] or candidate[key] != repeat[key]:
            raise ValueError(f"canonical emission changed the paired {key}")
    if candidate["outputs"] != repeat["outputs"]:
        raise ValueError("repeated candidate canonical emission changed output bytes")
    if stock["outputs"] == candidate["outputs"]:
        raise ValueError("the syntax candidate did not change either stock emission")
    stock_tools = stock["toolchain"]
    candidate_tools = candidate["toolchain"]
    if candidate_tools != repeat["toolchain"]:
        raise ValueError("candidate toolchain changed between emissions")
    if (original_plugin == patched_plugin
            or stock_tools["rocq_plugin"]["sha256"] != original_plugin
            or candidate_tools["rocq_plugin"] != {**stock_tools["rocq_plugin"], "sha256": patched_plugin}):
        raise ValueError("canonical emission did not select both expected Rocq plugins")
    for key in ("sail", "z3", "library", "plugin_directories"):
        if stock_tools[key] != candidate_tools[key]:
            raise ValueError(f"the paired emissions changed the {key} input")
    expected_plugins = [
        {**plugin, "sha256": patched_plugin} if Path(plugin["path"]).name == PLUGIN else plugin
        for plugin in stock_tools["loaded_plugins"]
    ]
    if (sum(Path(plugin["path"]).name == PLUGIN for plugin in expected_plugins) != 1
            or candidate_tools["loaded_plugins"] != expected_plugins):
        raise ValueError("native plugin population or load order differs beyond the Rocq plugin")


def qualify(checkout: Path, root: Path, upload: Path) -> None:
    revision = os.environ["TESTED_REVISION"]
    build = load(Path(os.environ["VOS_LOG_DIR"]) / "bootstrap.json")
    if (build["source_revision"] != revision or build["exit_code"] != 0
            or build["toolchains"] != ["sail"]
            or build["snapshots"]["sail"] != receipts.digest(checkout / "tools/opam/sail.lock")):
        raise ValueError("Sail bootstrap did not accept the selected locked inputs")
    environment = {name: value for name, value in os.environ.items()
                   if name not in {"SAIL_PLUGIN_DIR", "SAIL_NO_PLUGINS", "SAIL_DIR",
                                   "DUNE_DIR_LOCATIONS", "GH_TOKEN", "GITHUB_TOKEN"}}
    candidate, source = source_candidate(checkout, root, upload, environment)
    receipts.write(upload / "source.json", source)

    sail = Path(environment["OPAMROOT"]) / env.SAIL_SWITCH / "bin/sail"
    share = Path(subprocess.check_output([str(sail), "--dir"], cwd=checkout, env=environment,
                                       text=True, timeout=60).strip())
    if not share.is_absolute():
        raise ValueError("Sail did not identify an absolute installed library")
    plugins = (share / rocqterm.PLUGIN).parent.resolve()
    installed = receipts.snapshot(plugins, (path for path in plugins.iterdir() if path.is_file()))
    if PLUGIN not in installed:
        raise FileNotFoundError("the stock Rocq backend is absent from the locked Sail installation")
    private = root / "plugins"
    shutil.copytree(plugins, private)
    if receipts.snapshot(private, (path for path in private.iterdir() if path.is_file())) != installed:
        raise ValueError("private stock plugin copy differs from the locked Sail installation")
    records = []
    for run in ("stock", "candidate", "repeat"):
        if run == "candidate":
            shutil.copyfile(candidate, private / PLUGIN)
        build_root = root / run
        tree = build_root / "model-tree"
        command([sys.executable, "tools/run.py", "model", "rocq"], checkout, upload / f"{run}.log",
                timeout=900, environment={**environment, "VOS_BUILD_ROOT": str(build_root),
                                          "VOS_BUILD_DIR": str(tree), "SAIL_PLUGIN_DIR": str(private)})
        outputs = rocqterm.output_dir(tree)
        receipt = outputs / rocqterm.RECEIPT
        record = load(receipt)
        if record["outputs"] != {name: rocqterm.file_identity(outputs / name) for name in rocqterm.OUTPUTS}:
            raise ValueError(f"{run} canonical files do not match their generation receipt")
        shutil.copyfile(receipt, upload / f"{run}-receipt.json")
        records.append(record)
    check_comparison(*records, revision=revision, original_plugin=installed[PLUGIN],
                     patched_plugin=receipts.digest(candidate))
    if receipts.snapshot(plugins, (path for path in plugins.iterdir() if path.is_file())) != installed:
        raise ValueError("installed Sail plugins changed during the emission qualification")
    receipts.write(upload / "result.json", {
        "schema": "verifiedos-sail-emitter-qualification/1",
        "status": "pass",
        "scope": "immutable source rebuild and paired canonical Rocq emission",
        "revision": revision,
        "run_id": os.environ["GITHUB_RUN_ID"],
        "run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
        "source_sha256": receipts.digest(upload / "source.json"),
        "sail_bootstrap_sha256": receipts.digest(Path(os.environ["VOS_LOG_DIR"]) / "bootstrap.json"),
        "emission_receipts": receipts.snapshot(upload, upload.glob("*-receipt.json")),
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_REF") != "refs/heads/main":
        parser.error("canonical emitter qualification runs on GitHub Actions from main")
    root = args.root
    if not root.is_absolute() or not root.resolve().is_relative_to(Path(os.environ["RUNNER_TEMP"]).resolve()):
        parser.error("qualification output must be inside the runner's temporary directory")
    root.mkdir()
    upload = root / "upload"
    upload.mkdir()
    try:
        qualify(Path(__file__).resolve().parents[2], root, upload)
    except (KeyError, OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as error:
        receipts.write(upload / "result.json", {"status": "refused", "diagnostic": str(error)})
        print(f"FAIL canonical emitter qualification: {error}", file=sys.stderr)
        return 1
    print("PASS immutable source rebuild and paired canonical Rocq emission")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
