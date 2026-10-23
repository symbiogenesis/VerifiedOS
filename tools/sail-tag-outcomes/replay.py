# SPDX-License-Identifier: Apache-2.0
"""Replay the isolated canonical V1 tag candidate; supplies no production verdict."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    recipe = json.loads((repo / "tools/sail-tag-outcomes/candidate.json").read_text())
    q = json.loads((repo / "tools/opam/sail-support-qualification.json").read_text())
    try:
        out = output_path(args.out, (repo, args.source_archive, args.stdpp, args.plugin,
                                    args.rocq_prefix, args.sail_prefix))
    except ValueError as error:
        parser.error(str(error))
    native = Path("/root/build")
    if not out.is_relative_to(native) or not any(p.name.startswith("lane-") for p in out.parents):
        parser.error("--out must be below the assigned /root/build/lane-* root")
    for path, expected in [(args.source_archive, q["source"]["sha256"]),
                           (args.plugin, recipe["syntax_plugin_sha256"])]:
        require_sha(path, expected)
    if out.is_relative_to(args.stdpp):
        parser.error("output may not be inside the dependency input")
    if any(p.is_symlink() and p.is_dir() for p in args.stdpp.rglob("*")):
        parser.error("dependency input may not contain directory symlinks")
    out.mkdir(parents=True)
    work = Path(tempfile.mkdtemp(prefix="vos-tag-replay-"))
    commands = []
    switches = [args.rocq_prefix, args.sail_prefix]

    def inventory() -> dict[str, dict[str, str]]:
        return {str(prefix): {str(p.relative_to(prefix)): sha(p)
                for tree in [prefix / "bin", prefix / "lib"]
                for p in sorted(tree.rglob("*")) if p.is_file()}
                for prefix in switches}

    before = inventory()
    (out / "installed-before.json").write_text(json.dumps(before, indent=2) + "\n")

    def run(label: str, argv: list[str | Path],
            env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        started = time.monotonic()
        result = subprocess.run(list(map(str, argv)), cwd=work, env=env,
                                capture_output=True, text=True, timeout=180, check=False)
        log = out / (label + ".log")
        log.write_text(result.stdout + result.stderr)
        commands.append({"label": label, "argv": list(map(str, argv)), "cwd": str(work),
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
        shutil.copy2(args.plugin, plugins / "sail_plugin_coq.cmxs")
        require_sha(repo / recipe["reproducer"], recipe["reproducer_sha256"])
        shutil.copy2(repo / recipe["reproducer"], out / "bindings.sail")
        env = os.environ.copy()
        env["SAIL_PLUGIN_DIR"] = str(plugins)
        env["PATH"] = str(args.sail_prefix / "bin") + os.pathsep + env["PATH"]
        outputs = []
        for name in ["emitted", "repeat"]:
            lane = out / name
            lane.mkdir()
            run(name + "-emit", [args.sail_prefix / "bin/sail", "--rocq", "-D", "CONCURRENCY_INTERFACE",
                "--rocq-lib-style", "stdpp", "--rocq-alt-modules",
                "SailStdpp.Base SailStdpp.ConcurrencyInterfaceTypes SailStdpp.ConcurrencyInterface SailStdpp.ConcurrencyInterfaceBuiltins",
                "--rocq-output-dir", lane, "-o", "bindings", out / "bindings.sail"], env)
            outputs.append({p.name: sha(p) for p in lane.glob("bindings*.v")})
        if outputs[0] != outputs[1] or len(outputs[0]) != 2:
            raise RuntimeError("repeat emission changed or omitted an output")
        for name in ["TagInterpreter.v", "TagControls.v"]:
            shutil.copy2(repo / "tools/sail-tag-outcomes" / name, out / "emitted" / name)
        maps = [*flags, "-R", out / "candidate", "SailStdpp", "-R", out / "emitted", ""]
        for name in ["bindings_types", "bindings", "TagInterpreter", "TagControls"]:
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
    print(f"PASS isolated tag candidate: {out}; production acceptance remains open")


if __name__ == "__main__":
    main()