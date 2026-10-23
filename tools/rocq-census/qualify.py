#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build/query original native metadata in one explicit private lane.

This focused control never compiles installed or supplied dependency sources.
It supplies no proof, assumption-audit, or complete-census acceptance verdict.
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def population(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): digest(p)
            for p in sorted(root.rglob("*"))
            if p.is_file() and p.suffix in {".vo", ".glob"}}


def changes(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
    return {"added": sorted(after.keys() - before.keys()),
            "deleted": sorted(before.keys() - after.keys()),
            "changed": sorted(k for k in before.keys() & after.keys()
                              if before[k] != after[k])}


def validate_output(out: Path, protected: tuple[Path, ...]) -> Path:
    """Resolve aliases before checking overlap, before creating any output."""
    if not out.is_absolute() or out.exists() or out.is_symlink():
        raise ValueError("--out must be a fresh absolute directory in the assigned native lane")
    resolved = out.resolve()
    for owner in protected:
        canonical_owner = owner.resolve(strict=True)
        if resolved.is_relative_to(canonical_owner) or canonical_owner.is_relative_to(resolved):
            raise ValueError(f"--out overlaps protected input directory: {canonical_owner}")
    return resolved


def control_verdict(native_exit: int, identities_unchanged: bool) -> tuple[int, str]:
    if not identities_unchanged:
        return 1, "identity-refused"
    return native_exit, "native-metadata-control-only" if native_exit == 0 else "refused"

def metadata_output(stdout: bytes, targets: list[str]) -> None:
    """Refuse missing, duplicate or foreign output without claiming census completeness."""
    try:
        value = json.loads(stdout)
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("expected exactly one metadata JSON emission") from error
    if not isinstance(value, dict) or value.get("schema") != "verifiedos-rocq-native-metadata/1" or value.get("acceptance") != "metadata-only":
        raise ValueError("unexpected metadata schema or acceptance boundary")
    roots = value.get("roots")
    if not isinstance(roots, list) or not targets or len(set(targets)) != len(targets):
        raise ValueError("missing roots or duplicate requested targets")
    if any(not isinstance(root, dict) or not isinstance(root.get("module"), dict)
           or not isinstance(root.get("native_path"), dict) for root in roots):
        raise ValueError("malformed metadata root")
    if [root.get("requested") for root in roots] != targets:
        raise ValueError("metadata target population differs from requested targets")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--switch-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--support-source", required=True, type=Path)
    parser.add_argument("--targets", default="CensusControls,SailStdpp.MachineWordInterface")
    args = parser.parse_args()
    switch = args.switch_root.resolve(strict=True)
    support = args.support_source.resolve(strict=True)
    source = Path(__file__).resolve().parent
    try:
        out = validate_output(args.out, (switch, support, source))
    except ValueError as error:
        parser.error(str(error))
    out.mkdir(parents=True)
    installed = switch / "lib/coq"
    before = population(installed)
    identity = {str(p): digest(p) for p in (source / "vos_rocq_census.ml",
                                            source / "NativeControls.v",
                                            switch / "bin/rocq")}
    dependency_before = population(support)
    command_records: list[dict[str, object]] = []
    receipt: dict[str, object] = {"schema": "verifiedos-native-metadata-control/1",
               "started_utc": datetime.datetime.now(datetime.UTC).isoformat(),
               "scope": "metadata-only; no proof or complete census acceptance",
               "input_sha256": identity, "installed_before": before,
               "support_before": dependency_before, "commands": command_records}
    (out / "checkpoint.json").write_text(json.dumps(receipt, indent=2) + "\n")
    shutil.copytree(support, out / "support")
    plugin = out / "vos_rocq_census"
    plugin.mkdir()
    shutil.copy2(source / "vos_rocq_census.ml", plugin)
    (plugin / "META").write_text('description = "Original Q35q native metadata producer"\n'
        'requires = "rocq-runtime.vernac"\nplugin(native) = "vos_rocq_census.cmxs"\n')
    env = os.environ.copy()
    env["PATH"] = str(switch / "bin") + os.pathsep + env.get("PATH", "")
    env["OCAMLPATH"] = str(out) + os.pathsep + str(switch / "lib") + os.pathsep + env.get("OCAMLPATH", "")
    env["VOS_CENSUS_TARGETS"] = args.targets
    start = time.monotonic()
    code = 1
    try:
        with tempfile.TemporaryDirectory(prefix="vos-native-census-") as work:
            receipt["native_process_cwd"] = work
            def run(label: str, command: list[str]) -> int:
                process = subprocess.run(command, cwd=work, env=env, capture_output=True,
                                         timeout=180, check=False)
                (out / (label + ".stdout.log")).write_bytes(process.stdout)
                (out / (label + ".stderr.log")).write_bytes(process.stderr)
                command_records.append({"label": label, "argv": list(map(str, command)),
                                           "cwd": work, "exit": process.returncode})
                return process.returncode
            code = run("plugin-build", [str(switch / "bin/ocamlfind"), "ocamlopt", "-rectypes",
                "-thread", "-shared", "-package", "rocq-runtime.vernac", "-w", "+8", "-warn-error", "+8",
                "-o", str(plugin / "vos_rocq_census.cmxs"), str(plugin / "vos_rocq_census.ml")])
            if code == 0:
                query = out / "NativeControls.v"
                shutil.copy2(source / "NativeControls.v", query)
                code = run("native-query", [str(switch / "bin/rocq"), "c", "-boot", "-R",
                    str(installed / "theories"), "Corelib", "-Q",
                    str(installed / "user-contrib/Stdlib"), "Stdlib", "-Q",
                    str(installed / "user-contrib/stdpp"), "stdpp", "-R", str(out / "support"), "SailStdpp",
                    "-q", "-w", "+default,-abstract-large-number", "-set", "Default Goal Selector=!",
                    "-disallow-sprop", "-o", str(out / "NativeControls.vo"), str(query)])
                receipt["native_exit"] = code
                if code == 0:
                    try:
                        metadata_output((out / "native-query.stdout.log").read_bytes(), args.targets.split(","))
                    except ValueError as error:
                        receipt["output_refusal"] = str(error)
                        code = 1
    finally:
        receipt["elapsed_seconds"] = time.monotonic() - start
        installed_after = population(installed)
        receipt["installed_after"] = installed_after
        receipt["installed_changes"] = changes(before, installed_after)
        support_after = population(support)
        receipt["support_after"] = support_after
        receipt["support_changes"] = changes(dependency_before, support_after)
        receipt["input_sha256_after"] = {p: digest(Path(p)) for p in identity}
        receipt.setdefault("native_exit", code)
        receipt["installed_unchanged"] = not any(changes(before, installed_after).values())
        receipt["support_unchanged"] = not any(changes(dependency_before, support_after).values())
        receipt["inputs_unchanged"] = receipt["input_sha256_after"] == identity
        code, verdict = control_verdict(code, all(receipt[k] for k in ("installed_unchanged", "support_unchanged", "inputs_unchanged")))
        receipt["exit"] = code
        receipt["verdict"] = verdict
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({k: receipt[k] for k in ("verdict", "exit", "installed_unchanged", "support_unchanged", "inputs_unchanged")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
