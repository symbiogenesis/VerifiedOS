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
REPLAY = EVIDENCE / "q35-holdfast-canonical-20261124"
FROZEN = EVIDENCE / "q35o-holdfast-main-20261125"
REFRESH = EVIDENCE / "q35o-holdfast-refresh-20261125"
BUILD_TARGET = "src/sail_coq_backend/sail_plugin_coq.cmxs"
BACKEND_SOURCE = "src/sail_coq_backend/pretty_print_coq.ml"
PLUGIN = Path(BUILD_TARGET).name


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def exact(path: Path, expected: str) -> str:
    observed = receipts.digest(path)
    if observed != expected:
        raise ValueError(f"unexpected SHA-256 for {path}")
    return observed


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


def _locked_sail_source(checkout: Path) -> tuple[Path, dict[str, Any]]:
    source_lock = checkout / "tools/sail-lsp/sources.lock.json"
    sail_rows = [row for row in load(source_lock)["sources"] if row["name"] == "sail"]
    if len(sail_rows) != 1:
        raise ValueError("tools/sail-lsp/sources.lock.json must name exactly one sail source")
    sail_source = sail_rows[0]
    if sail_source["version"] != env.SAIL_VERSION:
        raise ValueError("the checked release source differs from the locked Sail version")
    return source_lock, sail_source


def _retained_source_inputs(checkout: Path) -> tuple[Path, Path, Path]:
    license_path = evidence_input(checkout / SCOPED, "LICENSE.sail")
    patch = evidence_input(checkout / SCOPED, "sail-emission-syntax.patch")
    dune_project = evidence_input(checkout / INITIAL, "backend-dune-project.txt")
    return license_path, patch, dune_project


def source_candidate(checkout: Path, root: Path, upload: Path,
                     environment: dict[str, str]) -> tuple[Path, dict[str, object]]:
    source_lock, sail_source = _locked_sail_source(checkout)
    license_path, patch, dune_project = _retained_source_inputs(checkout)
    archive = root / "sail.tbz"
    receipts.download(sail_source["url"], archive, sail_source["sha256"])
    destination = root / "source"
    destination.mkdir()
    with tarfile.open(archive) as source:
        source.extractall(destination, filter="data")
    checkout_source = destination / sail_source["directory"]
    if list(destination.iterdir()) != [checkout_source]:
        raise ValueError("Sail source archive has an unexpected root")
    exact(checkout_source / "LICENSE", receipts.digest(license_path))

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
                     revision: str, original_plugin: str, patched_plugin: str,
                     provisioned: dict[str, rocqterm.Named]) -> None:
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
    invoked = Path(stock["command"][0])
    if not invoked.is_absolute() or str(invoked.resolve()) != provisioned["sail"]["path"]:
        raise ValueError("canonical target command did not invoke the bootstrapped Sail")
    for name in ("sail", "z3"):
        observed = stock_tools[name]
        if {"path": observed["path"], "sha256": observed["sha256"]} != provisioned[name]:
            raise ValueError(f"canonical emission did not use the bootstrapped {name} executable")
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


def _verified_retained_readings(
    checkout: Path,
) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    """Verify frozen Q35o readings and refreshed receipts against retained manifests."""
    directory = checkout / FROZEN
    comparison = evidence_input(directory, "comparison.json")
    inputs = evidence_input(directory, "inputs.json")
    result = load(comparison)
    if result["status"] != "identical":
        raise ValueError("the retained canonical comparison did not match")
    if result["library_inputs_unchanged"] is not True:
        raise ValueError("the Rocq library inputs changed during the frozen comparison")
    frozen_inputs = load(inputs)
    handwritten = exact(checkout / "model/handwritten_support/riscv_extras.v",
                        frozen_inputs["handwritten_source"])
    library_path = evidence_input(directory, "library-inputs-before.json")
    library_inputs = exact(library_path, frozen_inputs["library_inputs"]["sha256"])
    bound = {"comparison": receipts.digest(comparison), "inputs": receipts.digest(inputs),
             "handwritten_source": handwritten, "library_inputs": library_inputs}
    generation = frozen_inputs["generation_receipts"]
    unchanged = ("format", "target", "outputs", "axioms")
    refreshed_pair: dict[str, dict[str, Any]] = {}
    for label in ("original", "candidate"):
        member = f"{label}-generation.json"
        path = evidence_input(checkout / REPLAY, member)
        bound[label] = receipts.digest(path)
        if bound[label] != generation[label]:
            raise ValueError(f"the retained comparison names a different {label} generation receipt")
        frozen = load(path)
        refreshed_path = evidence_input(checkout / REFRESH, member)
        refreshed = load(refreshed_path)
        bound[f"refreshed_{label}"] = receipts.digest(refreshed_path)
        for key in unchanged:
            if refreshed[key] != frozen[key]:
                raise ValueError(
                    f"refreshed {label} {key} differ from the frozen canonical comparison",
                )
        if refreshed["toolchain"]["library"] != frozen["toolchain"]["library"]:
            raise ValueError(f"{label} Sail library differs from the frozen canonical comparison")
        # The launcher replaces tree/checkout paths. The installed Sail path is host-specific.
        if refreshed["command"][1:] != frozen["command"][1:]:
            raise ValueError(
                f"refreshed {label} arguments differ from the frozen canonical comparison",
            )
        refreshed_pair[label] = refreshed
    return bound, refreshed_pair


def check_frozen_pair(checkout: Path, stock: dict[str, Any],
                      candidate: dict[str, Any]) -> dict[str, str]:
    """Join hosted inputs to the refreshed receipts and output bytes to the frozen readings."""
    bound, refreshed_pair = _verified_retained_readings(checkout)
    unchanged = ("format", "target", "outputs", "axioms")
    for label, observed in (("original", stock), ("candidate", candidate)):
        refreshed = refreshed_pair[label]
        if observed["toolchain"]["library"] != refreshed["toolchain"]["library"]:
            raise ValueError(f"{label} Sail library differs from the frozen canonical comparison")
        if observed["inputs"] != refreshed["inputs"]:
            raise ValueError(f"hosted {label} inputs differ from the refreshed generation receipt")
        for key in unchanged:
            if observed[key] != refreshed[key]:
                raise ValueError(f"hosted {label} {key} differ from the frozen canonical comparison")
        if observed["command"][1:] != refreshed["command"][1:]:
            raise ValueError(f"hosted {label} arguments differ from the frozen canonical comparison")
    return bound


def _verify_live_model_inputs(checkout: Path, label: str,
                              receipt: dict[str, Any]) -> dict[str, object]:
    receipt_inputs = receipt["inputs"]
    configuration = receipt_inputs["configuration"]
    if configuration["path"] != "model/config/verifiedos.json":
        raise ValueError(f"refreshed {label} receipt names unexpected configuration path")
    config_sha = exact(checkout / configuration["path"], configuration["sha256"])

    project_file = receipt_inputs["project_file"]
    if project_file["path"] != "model/model/riscv.sail_project":
        raise ValueError(f"refreshed {label} receipt names unexpected project file path")
    project_sha = exact(checkout / project_file["path"], project_file["sha256"])

    target_cmake = receipt_inputs["target_cmake"]
    if target_cmake["path"] != "model/model/CMakeLists.txt":
        raise ValueError(f"refreshed {label} receipt names unexpected CMakeLists path")
    cmake_sha = exact(checkout / target_cmake["path"], target_cmake["sha256"])

    expected_sources = receipt_inputs["sources"]
    expected_digests = expected_sources["sha256"]
    if (not isinstance(expected_digests, dict) or not expected_digests
            or expected_sources["files"] != len(expected_digests)
            or rocqterm.aggregate(expected_digests) != expected_sources["aggregate"]):
        raise ValueError(f"refreshed {label} sources manifest is internally inconsistent")

    prefix = f"{rocqterm.MODEL_SOURCES}/"
    observed_digests: dict[str, str] = {}
    for rel, expected_sha in expected_digests.items():
        if not isinstance(rel, str) or not rel.startswith(prefix) or not rel.endswith(".sail"):
            raise ValueError(f"refreshed {label} sources manifest names unexpected path {rel!r}")
        observed_digests[rel] = exact(checkout / rel, expected_sha)
    observed_sources = rocqterm.manifest(observed_digests)
    if observed_sources != expected_sources:
        raise ValueError(f"live Sail sources differ from refreshed {label} generation receipt")
    return {
        "configuration_sha256": config_sha,
        "project_file_sha256": project_sha,
        "target_cmake_sha256": cmake_sha,
        "sources_files": observed_sources["files"],
        "sources_aggregate": observed_sources["aggregate"],
    }


def preflight_checkout(checkout: Path) -> dict[str, object]:
    """Verify live checkout inputs against retained Q35o evidence without invoking Sail."""
    source_lock, sail_source = _locked_sail_source(checkout)
    license_path, patch, dune_project = _retained_source_inputs(checkout)
    bound, refreshed_pair = _verified_retained_readings(checkout)
    if refreshed_pair["original"]["inputs"] != refreshed_pair["candidate"]["inputs"]:
        raise ValueError("refreshed original and candidate generation receipts disagree on inputs")
    verified_inputs: dict[str, object] = {}
    for label in ("original", "candidate"):
        verified_inputs = _verify_live_model_inputs(checkout, label, refreshed_pair[label])
    return {
        "schema": "verifiedos-sail-emitter-preflight/1",
        "status": "pass",
        "checkout": str(checkout),
        "sail_version": sail_source["version"],
        "source_lock_sha256": receipts.digest(source_lock),
        "retained_source_inputs": {
            "license_sha256": receipts.digest(license_path),
            "patch_sha256": receipts.digest(patch),
            "dune_project_sha256": receipts.digest(dune_project),
        },
        "frozen_comparison": bound,
        "model_inputs": verified_inputs,
    }


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
    z3 = Path(environment["VOS_Z3_BIN"]) / "z3"
    provisioned: dict[str, rocqterm.Named] = {
        name: {"path": str(path.resolve(strict=True)), "sha256": receipts.digest(path)}
        for name, path in (("sail", sail), ("z3", z3))
    }
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
                     patched_plugin=receipts.digest(candidate), provisioned=provisioned)
    frozen = check_frozen_pair(checkout, records[0], records[1])
    if receipts.snapshot(plugins, (path for path in plugins.iterdir() if path.is_file())) != installed:
        raise ValueError("installed Sail plugins changed during the emission qualification")
    receipts.write(upload / "result.json", {
        "schema": "verifiedos-sail-emitter-qualification/2",
        "status": "pass",
        "scope": "immutable source rebuild and paired canonical Rocq emission",
        "revision": revision,
        "run_id": os.environ["GITHUB_RUN_ID"],
        "run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
        "source_sha256": receipts.digest(upload / "source.json"),
        "sail_bootstrap_sha256": receipts.digest(Path(os.environ["VOS_LOG_DIR"]) / "bootstrap.json"),
        "bootstrapped_executables": provisioned,
        "frozen_comparison": frozen,
        "emission_receipts": receipts.snapshot(upload, upload.glob("*-receipt.json")),
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--preflight", action="store_true",
                        help="verify live checkout inputs against retained Q35o evidence")
    parser.add_argument("--checkout", type=Path,
                        help="checkout root to preflight (defaults to repository root)")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    if args.preflight:
        if args.root is not None:
            parser.error("--root cannot be combined with --preflight")
        checkout = (args.checkout if args.checkout is not None else repo_root).resolve()
        try:
            summary = preflight_checkout(checkout)
        except (KeyError, OSError, ValueError) as error:
            print(f"FAIL canonical emitter preflight: {error}", file=sys.stderr)
            return 1
        print(f"PASS canonical emitter preflight: {checkout} (sail {summary['sail_version']})")
        return 0
    if args.checkout is not None:
        parser.error("--checkout requires --preflight")
    if args.root is None:
        parser.error("the following arguments are required: --root")
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_REF") != "refs/heads/main":
        parser.error("canonical emitter qualification runs on GitHub Actions from main")
    root = args.root
    if not root.is_absolute() or not root.resolve().is_relative_to(Path(os.environ["RUNNER_TEMP"]).resolve()):
        parser.error("qualification output must be inside the runner's temporary directory")
    root.mkdir()
    upload = root / "upload"
    upload.mkdir()
    try:
        qualify(repo_root, root, upload)
    except (KeyError, OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as error:
        receipts.write(upload / "result.json", {"status": "refused", "diagnostic": str(error)})
        print(f"FAIL canonical emitter qualification: {error}", file=sys.stderr)
        return 1
    print("PASS immutable source rebuild and paired canonical Rocq emission")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
