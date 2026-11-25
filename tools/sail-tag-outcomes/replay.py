# SPDX-License-Identifier: Apache-2.0
"""Replay the isolated canonical V1 tag candidate; supplies no production verdict."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import time
from pathlib import Path
from typing import cast


def sha(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def tree_sha(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha(path)
        for path in sorted(root.rglob("*")) if path.is_file() and path.suffix != ".glob"
    }


def absolute(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or "%" in value:
        raise argparse.ArgumentTypeError("an expanded absolute native path is required")
    return path.resolve(strict=True)


def output_path(value: str, protected: tuple[Path, ...]) -> Path:
    """Refuse canonical input overlap and aliases before any output mutation."""
    path = Path(value)
    if not path.is_absolute() or "%" in value or path.exists() or path.is_symlink():
        raise ValueError("output must be an expanded absolute, new directory")
    if any(p.is_symlink() for p in path.parents):
        raise ValueError("output ancestors must not be symlinks")
    path = path.resolve()
    for entry in protected:
        canonical = entry.resolve(strict=True)
        if path.is_relative_to(canonical) or canonical.is_relative_to(path):
            raise ValueError(f"output overlaps protected input: {canonical}")
    return path


def require_sha(path: Path, expected: str) -> None:
    if sha(path) != expected:
        raise ValueError(f"input digest mismatch: {path}")


def retained_emission_inputs(
    evidence: Path, plugin: Path, sail: Path, z3: Path,
) -> tuple[dict[Path, str], dict[str, str]]:
    reading = json.loads(evidence.read_text(encoding="utf-8"))
    if reading["checks"] != {"matched_retained_outputs": True, "unchanged_inputs": True}:
        raise ValueError("retained emission did not match the frozen inputs and outputs")
    recorded_hashes = cast(dict[str, str], reading["input_hashes"])
    input_hashes = {Path(name).name: digest for name, digest in recorded_hashes.items()}
    require_sha(plugin, input_hashes["sail_plugin_coq.cmxs"])
    require_sha(sail, input_hashes["sail"])
    require_sha(z3, input_hashes["z3"])
    plugins = {
        plugin.parent / name: digest for name, digest in input_hashes.items()
        if name.endswith(".cmxs")
    }
    for path, digest in plugins.items():
        require_sha(path, digest)
    return plugins, cast(dict[str, str], reading["expected"])


def retained_stdpp(evidence: Path) -> dict[str, str]:
    libraries = cast(dict[str, dict[str, str]], json.loads(evidence.read_text(encoding="utf-8")))
    stdpp, = (reading for path, reading in libraries.items() if Path(path).name == "stdpp")
    return stdpp


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-archive", required=True, type=absolute)
    parser.add_argument("--stdpp", required=True, type=absolute)
    parser.add_argument("--plugin", required=True, type=absolute)
    parser.add_argument("--rocq-prefix", required=True, type=absolute)
    parser.add_argument("--sail-prefix", required=True, type=absolute)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    recipe_path = repo / "tools/sail-tag-outcomes/candidate.json"
    support_recipe = repo / "tools/opam/sail-support-qualification.json"
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    q = json.loads(support_recipe.read_text(encoding="utf-8"))
    try:
        out = output_path(args.out, (repo, args.source_archive, args.stdpp, args.plugin,
                                    args.rocq_prefix, args.sail_prefix))
    except ValueError as error:
        parser.error(str(error))
    native = Path("/root/build")
    if not out.is_relative_to(native) or not any(p.name.startswith("lane-") for p in out.parents):
        parser.error("--out must be below the assigned /root/build/lane-* root")
    require_sha(args.source_archive, q["source"]["sha256"])
    plugin_digest = sha(args.plugin)
    expected_outputs = None
    expected_stdpp = None
    solver = None
    if plugin_digest == recipe["syntax_plugin_sha256"]:
        plugin_inputs = {args.plugin: plugin_digest}
    else:
        z3 = shutil.which("z3", path=str(args.sail_prefix / "bin") + os.pathsep + os.environ["PATH"])
        if z3 is None:
            parser.error("the retained plugin population requires the recorded z3 on PATH")
        solver = Path(z3).resolve(strict=True)
        plugin_inputs, expected_outputs = retained_emission_inputs(
            repo / recipe["retained_replay_evidence"], args.plugin,
            args.sail_prefix / "bin/sail", solver,
        )
        expected_stdpp = retained_stdpp(repo / recipe["retained_library_evidence"])
    if out.is_relative_to(args.stdpp):
        parser.error("output may not be inside the dependency input")
    if any(p.is_symlink() and p.is_dir() for p in args.stdpp.rglob("*")):
        parser.error("dependency input may not contain directory symlinks")
    out.mkdir(parents=True)
    commands = []
    switches = [args.rocq_prefix, args.sail_prefix]
    solver_digest = sha(solver) if solver is not None else None
    inputs = {
        "replay_driver_sha256": sha(Path(__file__)),
        "candidate_recipe_sha256": sha(recipe_path),
        "support_recipe_sha256": sha(support_recipe),
        "source_archive_sha256": q["source"]["sha256"],
        "rocq_sha256": sha(args.rocq_prefix / "bin/rocq"),
        "sail_sha256": sha(args.sail_prefix / "bin/sail"),
        "plugins_sha256": {path.name: digest for path, digest in plugin_inputs.items()},
        "z3_sha256": solver_digest,
    }

    def inventory() -> dict[str, dict[str, str]]:
        return {str(prefix): {str(p.relative_to(prefix)): sha(p)
                for tree in [prefix / "bin", prefix / "lib"]
                for p in sorted(tree.rglob("*")) if p.is_file()}
                for prefix in switches}

    before = inventory()
    (out / "installed-before.json").write_text(json.dumps(before, indent=2) + "\n")

    def run(label: str, argv: list[str | Path], env: dict[str, str] | None = None,
            *, cwd: Path = out) -> subprocess.CompletedProcess[str]:
        started = time.monotonic()
        result = subprocess.run(list(map(str, argv)), cwd=cwd, env=env,
                                capture_output=True, text=True, timeout=180, check=False)
        log = out / (label + ".log")
        log.write_text(result.stdout + result.stderr)
        commands.append({"label": label, "argv": list(map(str, argv)), "cwd": str(cwd),
                         "exit": result.returncode, "seconds": time.monotonic() - started,
                         "log": log.name, "sha256": sha(log)})
        if result.returncode:
            raise RuntimeError(f"{label} refused; see {log}")
        return result

    try:
        with tarfile.open(args.source_archive) as archive:
            archive.extractall(out / "source", filter="data")
        source = out / "source/coq-sail-0.20.3"
        if sha(source / "LICENSE") != q["source_license_sha256"]:
            raise RuntimeError("source license identity mismatch")
        for index, entry in enumerate(q["patches"]):
            patch = repo / entry["path"]
            if sha(patch) != entry["sha256"]:
                raise RuntimeError("base support patch digest mismatch")
            run(f"base-patch-{index}", ["patch", "-p1", "-d", source, "-i", patch])
        patch = repo / recipe["patch"]["path"]
        if sha(patch) != recipe["patch"]["sha256"]:
            raise RuntimeError("semantic patch digest mismatch")
        shutil.copytree(args.stdpp, out / "stdpp", symlinks=False)
        stdpp = tree_sha(out / "stdpp")
        if expected_stdpp is not None and stdpp != expected_stdpp:
            raise RuntimeError("private stdpp files do not match the retained library identities")
        (out / "inputs.json").write_text(json.dumps({**inputs, "stdpp_sha256": stdpp}, indent=2) + "\n")
        for mode in ["baseline", "candidate"]:
            lane = out / mode
            lane.mkdir()
            for item in (source / "src-stdpp").glob("*.v"):
                shutil.copy2(item, lane / item.name)
        run("semantic-patch", ["patch", "-p2", "-d", out / "candidate", "-i", patch])
        flags = ["-q", "-boot", "-R", args.rocq_prefix / "lib/coq/theories", "Corelib",
                 "-Q", args.rocq_prefix / "lib/coq/user-contrib/Stdlib", "Stdlib",
                 "-Q", out / "stdpp", "stdpp"]
        for mode in ["baseline", "candidate"]:
            lane = out / mode
            maps = [*flags, "-R", lane, "SailStdpp"]
            selected = [lane / (name + ".v") for name in q["support_modules"]]
            result = run(mode + "-deps", [args.rocq_prefix / "bin/rocq", "dep", "-sort", *maps, *selected])
            order = [Path(p) for p in result.stdout.split() if Path(p) in selected]
            if len(order) != len(selected) or set(order) != set(selected):
                raise RuntimeError("dependency sort did not enumerate the exact selected closure")
            for item in order:
                if item.resolve().parent != lane:
                    raise RuntimeError("selected source escaped owned lane")
                result = run(mode + "-" + item.stem, [args.rocq_prefix / "bin/rocq", "c", *maps,
                             *q["strict_flags"][1:], item])
                if result.stdout or result.stderr:
                    raise RuntimeError("strict selected compile emitted a diagnostic")
        plugins = out / "plugins"
        plugins.mkdir()
        for plugin_input, digest in plugin_inputs.items():
            name = "sail_plugin_coq.cmxs" if plugin_input == args.plugin else plugin_input.name
            staged = plugins / name
            shutil.copy2(plugin_input, staged)
            require_sha(staged, digest)
        reproducer = repo / recipe["reproducer"]
        require_sha(reproducer, recipe["reproducer_sha256"])
        env = os.environ.copy()
        env["SAIL_PLUGIN_DIR"] = str(plugins)
        env["PATH"] = str(args.sail_prefix / "bin") + os.pathsep + env["PATH"]
        outputs = []
        for name in ["emitted", "repeat"]:
            lane = out / name
            lane.mkdir()
            # Sail includes this input name verbatim in the emitted refusals.
            shutil.copy2(reproducer, lane / "bindings.sail")
            run(name + "-emit", [args.sail_prefix / "bin/sail", "--rocq", "-D", "CONCURRENCY_INTERFACE",
                "--rocq-lib-style", "stdpp", "--rocq-alt-modules",
                "SailStdpp.Base SailStdpp.ConcurrencyInterfaceTypes SailStdpp.ConcurrencyInterface SailStdpp.ConcurrencyInterfaceBuiltins",
                "--rocq-output-dir", lane, "-o", "bindings", "bindings.sail"], env, cwd=lane)
            outputs.append({p.name: sha(p) for p in lane.glob("bindings*.v")})
        if outputs[0] != outputs[1] or len(outputs[0]) != 2:
            raise RuntimeError("repeat emission changed or omitted an output")
        if expected_outputs is not None and outputs[0] != expected_outputs:
            raise RuntimeError("repeat emission does not match the retained output identities")
        authored_modules = ("TagInterpreter", "TagControls", "TagConservativity", "PhysicalCallerBridge")
        for name in authored_modules:
            proof_source = repo / "tools/sail-tag-outcomes" / (name + ".v")
            shutil.copy2(proof_source, out / "emitted" / proof_source.name)
        maps = [*flags, "-R", out / "candidate", "SailStdpp", "-R", out / "emitted", ""]
        for name in ("bindings_types", "bindings", *authored_modules):
            result = run("strict-" + name, [args.rocq_prefix / "bin/rocq", "c", *maps,
                         *q["strict_flags"][1:], out / "emitted" / (name + ".v")])
            if result.stdout or result.stderr:
                raise RuntimeError("strict probe compile emitted a diagnostic")
        (out / "repeat-output-identities.json").write_text(json.dumps(outputs, indent=2) + "\n")
    finally:
        after = inventory()
        changes = {prefix: sorted(k for k in before[prefix].keys() | after[prefix].keys()
                                 if before[prefix].get(k) != after[prefix].get(k)) for prefix in before}
        (out / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        (out / "installed-after.json").write_text(json.dumps(after, indent=2) + "\n")
        (out / "installed-comparison.json").write_text(json.dumps(changes, indent=2) + "\n")
        if any(changes.values()):
            raise RuntimeError("installed paths changed; report them and do not self-restore")
        if solver is not None and sha(solver) != solver_digest:
            raise RuntimeError("recorded z3 changed during replay")
    print(f"PASS isolated tag candidate: {out}; production acceptance remains open")


if __name__ == "__main__":
    main()
