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
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import cast


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def population(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): digest(p)
            for p in sorted(root.rglob("*"))
            if p.is_file() and p.suffix in {".vo", ".glob"}}


def api_population(root: Path) -> dict[str, str]:
    """Bind installed native APIs and link/compiler inputs, including membership."""
    extensions = {".ml", ".mli", ".cmi", ".cmx", ".cmxs", ".cma", ".cmxa", ".a", ".so"}
    return {str(path.relative_to(root)): digest(path) for path in sorted(root.rglob("*"))
            if path.is_file() and path.suffix in extensions}


def source_population(root: Path) -> dict[str, str]:
    return {str(path.relative_to(root)): digest(path) for path in sorted(root.rglob("*.v")) if path.is_file()}


def query_inputs(out: Path) -> dict[str, str]:
    """Exactly the copied semantic inputs, excluding the query's new output objects."""
    found: dict[str, str] = {}
    for name in ("support", "stdpp", "controls"):
        root = out / name
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in {".vo", ".glob", ".v"}:
                found[str(path.relative_to(out))] = digest(path)
    for path in (out / "vos_rocq_census/vos_rocq_census.cmxs", out / "vos_rocq_census/vos_rocq_census.ml", out / "NativeControls.v"):
        if not path.is_file():
            raise ValueError(f"missing built/copied query input: {path}")
        found[str(path.relative_to(out))] = digest(path)
    requests = out / "resolution-requests.json"
    if requests.is_file():
        found[requests.name] = digest(requests)
    for path in sorted((*out.glob("Search*.v"), *out.glob("native-search-*.log"))):
        found[path.name] = digest(path)
    return found


def request_bytes(path: Path) -> bytes:
    if not path.is_absolute() or not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("resolution input must be an absolute regular file at most 64 MiB")
    data = path.read_bytes()
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("resolution input exceeds 64 MiB")
    return data


def search_semantic_inputs(out: Path) -> dict[str, str]:
    return {name: value for name, value in query_inputs(out).items()
            if name != "resolution-requests.json" and not name.startswith(("Search", "native-search-"))}


def no_diagnostic(out: Path, label: str, *, permit_stdout: bool = False) -> None:
    if (out / (label + ".stderr.log")).read_bytes().strip() or (
            not permit_stdout and (out / (label + ".stdout.log")).read_bytes().strip()):
        raise ValueError(f"strict native command printed a diagnostic: {label}")


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


def control_verdict(native_exit: int | None, identities_unchanged: bool, *,
                    query_completed: bool, metadata_validated: bool,
                    execution_finished: bool) -> tuple[int, str]:
    if not identities_unchanged:
        return 1, "identity-refused"
    if native_exit == 0 and query_completed and metadata_validated and execution_finished:
        return 0, "native-metadata-control-only"
    return native_exit if native_exit is not None and native_exit != 0 else 1, "refused"

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


def output_identity(path: Path) -> dict[str, object]:
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), "native census output is not a regular absolute file")
    sha256, blake = hashlib.sha256(), hashlib.blake2b(digest_size=32)
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha256.update(chunk)
            blake.update(chunk)
            size += len(chunk)
    return {"path": str(path), "bytes": size, "sha256": sha256.hexdigest(), "blake2b_256": blake.hexdigest()}


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate native JSON object key: {key}")
        result[key] = value
    return result


def census_output(stdout: bytes, targets: list[str], requests: list[object], *, output: Path) -> dict[str, object]:
    """Check the invocation envelope; the independent adapter owns census acceptance."""
    envelope = json.loads(stdout, object_pairs_hook=unique_object)
    require(isinstance(envelope, dict) and set(envelope) == {"schema", "census_schema", "path", "bytes", "blake2b_256"},
            "unexpected native census output envelope fields")
    require(envelope["schema"] == "verifiedos-native-census-output/1"
            and envelope["census_schema"] == "verifiedos-sail-support-census/1"
            and envelope["path"] == str(output)
            and type(envelope["bytes"]) is int and envelope["bytes"] > 0,
            "native census output envelope differs from exact requested output")
    before = output_identity(output)
    require(envelope["bytes"] == before["bytes"] and envelope["blake2b_256"] == before["blake2b_256"],
            "native census output bytes or digest differ from envelope")
    with output.open(encoding="utf-8") as stream:
        value = json.load(stream, object_pairs_hook=unique_object)
    if not isinstance(value, dict) or value.get("schema") != "verifiedos-sail-support-census/1":
        raise ValueError("unexpected census schema")
    if "acceptance" in value or value.get("requested_roots") != targets:
        raise ValueError("census target population or acceptance boundary changed")
    if value.get("resolution_requests") != requests:
        raise ValueError("census resolution request population changed")
    roots = value.get("roots")
    if not isinstance(roots, list) or any(not isinstance(root, dict) for root in roots) or [root.get("requested") for root in roots] != targets:
        raise ValueError("census native roots differ from the requested population")
    after = output_identity(output)
    require(before == after, "native census output changed during parsing")
    return {"envelope": envelope, "before": before, "after": after}

def captured_bytes(value: bytes | str | None) -> bytes:
    return value.encode() if isinstance(value, str) else value or b""


def run_command(label: str, command: list[str], *, out: Path, work: str,
                env: dict[str, str], receipt: dict[str, object],
                commands: list[dict[str, object]], timeout_seconds: int = 180) -> int:
    record: dict[str, object] = {"label": label, "argv": command, "cwd": work,
                                 "status": "pending", "process_completed": False, "exit": None,
                                 "timeout_seconds": timeout_seconds}
    sources = {argument: digest(Path(argument)) for argument in command
               if Path(argument).suffix in {".v", ".ml"} and Path(argument).is_file()}
    record["source_sha256_before"] = sources
    commands.append(record)
    # Persist intent before launch: an interrupted invocation cannot inherit success.
    (out / "checkpoint.json").write_text(json.dumps(receipt, indent=2) + "\n")
    try:
        process = subprocess.run(command, cwd=work, env=env, capture_output=True,
                                 timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired as error:
        record.update(status="timed-out", error_type=type(error).__name__, error=str(error))
        try:
            (out / (label + ".stdout.log")).write_bytes(captured_bytes(error.stdout))
            (out / (label + ".stderr.log")).write_bytes(captured_bytes(error.stderr))
        except OSError as log_error:
            record["log_error"] = str(log_error)
        raise
    except OSError as error:
        record.update(status="launch-error", error_type=type(error).__name__, error=str(error))
        raise
    record.update(status="completed", process_completed=True, exit=process.returncode)
    try:
        (out / (label + ".stdout.log")).write_bytes(process.stdout)
        (out / (label + ".stderr.log")).write_bytes(process.stderr)
        record["source_sha256_after"] = {name: digest(Path(name)) for name in sources}
        require(record["source_sha256_after"] == sources, f"executed native source changed: {label}")
    except OSError as error:
        record["log_error"] = str(error)
        raise
    return process.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--switch-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--support-source", required=True, type=Path)
    parser.add_argument("--stdpp-source", type=Path, help="Immutable complete prebuilt stdpp/bitvector prefix directory")
    parser.add_argument("--targets", default="CensusControls,SailStdpp.MachineWordInterface")
    parser.add_argument("--census", action="store_true", help="Emit the separate unqualified census provenance format")
    parser.add_argument("--requests", type=Path, help="Exact ordered native Search resolution requests as JSON")
    parser.add_argument("--search", action="store_true", help="Retain exact per-root native Search and derive ordered requests")
    parser.add_argument("--component-receipt", type=Path, help="Exact recipe-bound selected-support component build receipt")
    parser.add_argument("--query-timeout-seconds", type=int, default=180,
                        help="Callback timeout only, at most1800 seconds; compile/Search remain180 seconds")
    args = parser.parse_args()
    if not 0 < args.query_timeout_seconds <= 1800:
        parser.error("--query-timeout-seconds must be positive and at most1800")
    switch = args.switch_root.resolve(strict=True)
    support = args.support_source.resolve(strict=True)
    stdpp_source = args.stdpp_source.resolve(strict=True) if args.stdpp_source else None
    source = Path(__file__).resolve().parent
    if args.search and (not args.census or args.requests is not None):
        parser.error("--search requires --census and excludes --requests")
    component = None
    if args.component_receipt is not None:
        component = json.loads(args.component_receipt.read_text(encoding="utf-8"))
        recipe = json.loads((source.parent / "opam/sail-support-qualification.json").read_text(encoding="utf-8"))
        expected_patches = [{"path": entry["path"], "sha256": entry["sha256"]} for entry in recipe["patches"]]
        expected_sources = {name: digest(support / (name + ".v")) for name in recipe["support_modules"]}
        if (not args.census or component.get("verdict") != "component-build-only"
                or component.get("protected_unchanged") is not True
                or Path(component.get("support_root", "")).resolve() != support
                or component.get("archive_sha256") != recipe["source"]["sha256"]
                or component.get("patches") != expected_patches
                or component.get("selected_source_sha256") != expected_sources):
            parser.error("component receipt does not bind exact selected support source recipe")
    requests: list[object] = []
    supplied_requests = None
    if args.requests is not None:
        supplied_requests = request_bytes(args.requests)
        loaded = json.loads(supplied_requests)
        if not args.census or not isinstance(loaded, list):
            parser.error("--requests requires --census and a JSON array")
        requests = cast("list[object]", loaded)
    try:
        out = validate_output(args.out, (switch, support, source, *((stdpp_source,) if stdpp_source else ())))
    except ValueError as error:
        parser.error(str(error))
    out.mkdir(parents=True)
    installed = switch / "lib/coq"
    before = population(installed)
    api_before = api_population(switch / "lib") if args.census else {}
    identity = {str(p): digest(p) for p in (source / "vos_rocq_census.ml",
                                            source / "NativeControls.v",
                                            Path(__file__).resolve(),
                                            switch / "bin/rocq")}
    if args.census:
        for path in (source / "CensusControls.v", source / "census-schema.json", source / "control-spec.json"):
            identity[str(path)] = digest(path)
        if args.search:
            for path in (source / "census.py", source.parent / "vos/proofaudit.py"):
                identity[str(path)] = digest(path)
        if args.requests is not None:
            identity[str(args.requests.resolve(strict=True))] = digest(args.requests)
        for name in ("ocamlfind", "ocamlopt"):
            identity[str(switch / "bin" / name)] = digest(switch / "bin" / name)
        if args.component_receipt is not None:
            identity[str(args.component_receipt.resolve(strict=True))] = digest(args.component_receipt)
            recipe_path = source.parent / "opam/sail-support-qualification.json"
            identity[str(recipe_path)] = digest(recipe_path)
            if component is None:
                raise ValueError("missing component recipe")
            for entry in component["patches"]:
                path = source.parent.parent / entry["path"]
                identity[str(path)] = digest(path)
    dependency_before = population(support)
    stdpp_before = population(stdpp_source) if stdpp_source else {}
    source_before = source_population(support) if args.census else {}
    command_records: list[dict[str, object]] = []
    receipt: dict[str, object] = {"schema": "verifiedos-native-metadata-control/1",
               "started_utc": datetime.datetime.now(datetime.UTC).isoformat(),
               "scope": "metadata-only; no proof or complete census acceptance",
               "input_sha256": identity, "installed_before": before,
               "native_api_before": api_before,
               "support_before": dependency_before, "commands": command_records,
               "stdpp_source": str(stdpp_source) if stdpp_source else None, "stdpp_before": stdpp_before,
               "support_source_before": source_before, "component_recipe": component,
               "query_timeout_requested_seconds": args.query_timeout_seconds,
               "query_timeout_effective_seconds": args.query_timeout_seconds,
               "verdict": "pending", "exit": 1, "native_exit": None,
               "query_completed": False, "metadata_validated": False}
    start = time.monotonic()
    metadata_validated = False
    execution_finished = False
    loaded_before = None
    search_loaded_before = None
    validated_output = None
    output_file = out / "native-census.json"
    try:
        (out / "checkpoint.json").write_text(json.dumps(receipt, indent=2) + "\n")
        shutil.copytree(support, out / "support")
        stdpp = installed / "user-contrib/stdpp"
        if stdpp_source:
            stdpp = out / "stdpp"
            shutil.copytree(stdpp_source, stdpp)
        plugin = out / "vos_rocq_census"
        plugin.mkdir()
        shutil.copy2(source / "vos_rocq_census.ml", plugin)
        require(digest(plugin / "vos_rocq_census.ml") == identity[str(source / "vos_rocq_census.ml")],
                "copied authored plugin source changed before compilation")
        (plugin / "META").write_text('description = "Original Q35q native metadata producer"\n'
            'requires = "rocq-runtime.vernac"\nplugin(native) = "vos_rocq_census.cmxs"\n')
        env = os.environ.copy()
        env["PATH"] = str(switch / "bin") + os.pathsep + env.get("PATH", "")
        env["OCAMLPATH"] = str(out) + os.pathsep + str(switch / "lib") + os.pathsep + env.get("OCAMLPATH", "")
        env["VOS_CENSUS_TARGETS"] = args.targets
        if args.census:
            env["VOS_CENSUS_MODE"] = "census"
            env.pop("VOS_CENSUS_RESOLVE", None)
            env.pop("VOS_CENSUS_RESOLVE_FILE", None)
            require(not output_file.exists(), "native census output already exists before callback")
            env["VOS_CENSUS_OUTPUT_FILE"] = str(output_file)
            receipt["native_output_requested"] = {"path": str(output_file), "existed_before": False}
            env.pop("VOS_CENSUS_PROGRESS_FILE", None)
        else:
            env.pop("VOS_CENSUS_MODE", None)
            env.pop("VOS_CENSUS_RESOLVE", None)
            env.pop("VOS_CENSUS_RESOLVE_FILE", None)
            env.pop("VOS_CENSUS_OUTPUT_FILE", None)
            env.pop("VOS_CENSUS_PROGRESS_FILE", None)
        with tempfile.TemporaryDirectory(prefix="vos-native-census-") as work:
            receipt["native_process_cwd"] = work
            plugin_exit = run_command("plugin-build", [str(switch / "bin/ocamlfind"), "ocamlopt", "-rectypes",
                "-thread", "-shared", "-package", "rocq-runtime.vernac", "-w", "+8", "-warn-error", "+8",
                "-o", str(plugin / "vos_rocq_census.cmxs"), str(plugin / "vos_rocq_census.ml")],
                out=out, work=work, env=env, receipt=receipt, commands=command_records)
            if plugin_exit == 0:
                no_diagnostic(out, "plugin-build")
                require(digest(plugin / "vos_rocq_census.ml") == identity[str(source / "vos_rocq_census.ml")],
                        "copied authored plugin source changed during compilation")
                query = out / "NativeControls.v"
                if args.census:
                    targets = args.targets.split(",")
                    control_root = out / "controls"
                    control_root.mkdir()
                    controls = control_root / "CensusControls.v"
                    if "CensusControls" in targets:
                        shutil.copy2(source / "CensusControls.v", controls)
                        control_exit = run_command("native-control-source", [str(switch / "bin/rocq"), "c", "-boot", "-R",
                            str(installed / "theories"), "Corelib", "-Q", str(installed / "user-contrib/Stdlib"), "Stdlib",
                            "-Q", str(stdpp), "stdpp", "-R", str(out / "support"), "SailStdpp",
                            "-Q", str(control_root), "",
                            "-q", "-w", "+default,-abstract-large-number", "-set", "Default Goal Selector=!", "-disallow-sprop",
                            "-o", str(control_root / "CensusControls.vo"), str(controls)],
                            out=out, work=work, env=env, receipt=receipt, commands=command_records)
                        require(control_exit == 0, "native census control source did not compile")
                        no_diagnostic(out, "native-control-source")
                    query.write_text("".join(f"Require {target}.\n" for target in targets) +
                                     'Declare ML Module "vos_rocq_census".\n', encoding="utf-8", newline="")
                    if args.search:
                        sys.path.insert(0, str(source.parent))
                        adapter = runpy.run_path(str(source / "census.py"))
                        proofaudit = adapter["proofaudit"]
                        searches: dict[str, str] = {}
                        search_loaded_before = search_semantic_inputs(out)
                        receipt["search_loaded_before"] = search_loaded_before
                        for index, target in enumerate(targets):
                            search_source = out / (f"Search{index:02d}.v")
                            search_source.write_text(proofaudit.inventory_query(target), encoding="utf-8", newline="")
                            label = f"native-search-{index:02d}"
                            search_exit = run_command(label, [str(switch / "bin/rocq"), "c", "-boot", "-R",
                                str(installed / "theories"), "Corelib", "-Q", str(installed / "user-contrib/Stdlib"), "Stdlib",
                                "-Q", str(stdpp), "stdpp", "-R", str(out / "support"), "SailStdpp",
                                "-Q", str(control_root), "", "-q", "-w", "+default,-abstract-large-number",
                                "-set", "Default Goal Selector=!", "-disallow-sprop", "-o",
                                str(out / (f"Search{index:02d}.vo")), str(search_source)],
                                out=out, work=work, env=env, receipt=receipt, commands=command_records)
                            require(search_exit == 0, f"native Search refused: {target}")
                            no_diagnostic(out, label, permit_stdout=True)
                            searches[target] = (out / (label + ".stdout.log")).read_text(encoding="utf-8")
                        search_loaded_after = search_semantic_inputs(out)
                        receipt["search_loaded_after"] = search_loaded_after
                        require(search_loaded_after == search_loaded_before, "copied native inputs changed during Search")
                        requests = cast("list[object]", adapter["parse_search_requests"](searches, expected_modules=targets))
                        receipt["search_targets"] = targets
                        receipt["search_requests"] = len(requests)
                    request_path = out / "resolution-requests.json"
                    request_path.write_bytes(supplied_requests if supplied_requests is not None else
                                             (json.dumps(requests, ensure_ascii=False) + "\n").encode("utf-8"))
                    request_bytes(request_path)
                    receipt["resolution_input"] = {"path": str(request_path), "sha256": digest(request_path)}
                    env["VOS_CENSUS_RESOLVE_FILE"] = str(request_path)
                else:
                    shutil.copy2(source / "NativeControls.v", query)
                if args.census:
                    loaded_before = query_inputs(out)
                    receipt["loaded_before"] = loaded_before
                    require(source_population(out / "support") == source_before, "copied support source bytes differ before query")
                    require(population(out / "support") == dependency_before, "copied support object bytes differ before query")
                    require(not stdpp_source or population(out / "stdpp") == stdpp_before, "copied dependency object bytes differ before query")
                native_exit = run_command("native-query", [str(switch / "bin/rocq"), "c", "-boot", "-R",
                    str(installed / "theories"), "Corelib", "-Q",
                    str(installed / "user-contrib/Stdlib"), "Stdlib", "-Q",
                    str(stdpp), "stdpp", "-R", str(out / "support"), "SailStdpp",
                    *(["-Q", str(out / "controls"), ""] if args.census else []),
                    "-q", "-w", "+default,-abstract-large-number", "-set", "Default Goal Selector=!",
                    "-disallow-sprop", "-o", str(out / "NativeControls.vo"), str(query)],
                    out=out, work=work, env=env, receipt=receipt, commands=command_records,
                    timeout_seconds=args.query_timeout_seconds)
                if native_exit == 0:
                    no_diagnostic(out, "native-query", permit_stdout=True)
                    if args.census:
                        validated_output = census_output((out / "native-query.stdout.log").read_bytes(), args.targets.split(","), requests,
                                                         output=output_file)
                        receipt["native_output_validation"] = validated_output
                    else:
                        metadata_output((out / "native-query.stdout.log").read_bytes(), args.targets.split(","))
                    metadata_validated = True
        execution_finished = True
    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
        receipt["execution_refusal"] = {"error_type": type(error).__name__, "error": str(error)}
    finally:
        receipt["elapsed_seconds"] = time.monotonic() - start
        identities_unchanged = False
        try:
            installed_after = population(installed)
            receipt["installed_after"] = installed_after
            receipt["installed_changes"] = changes(before, installed_after)
            support_after = population(support)
            receipt["support_after"] = support_after
            receipt["support_changes"] = changes(dependency_before, support_after)
            receipt["input_sha256_after"] = {p: digest(Path(p)) for p in identity}
            api_after = api_population(switch / "lib") if args.census else {}
            receipt["native_api_after"] = api_after
            receipt["native_api_changes"] = changes(api_before, api_after)
            receipt["installed_unchanged"] = not any(changes(before, installed_after).values())
            receipt["support_unchanged"] = not any(changes(dependency_before, support_after).values())
            receipt["inputs_unchanged"] = receipt["input_sha256_after"] == identity
            stdpp_after = population(stdpp_source) if stdpp_source else {}
            receipt["stdpp_after"] = stdpp_after
            receipt["stdpp_changes"] = changes(stdpp_before, stdpp_after)
            receipt["stdpp_unchanged"] = stdpp_before == stdpp_after
            source_after = source_population(support) if args.census else {}
            receipt["support_source_after"] = source_after
            receipt["support_source_unchanged"] = source_before == source_after
            if loaded_before is not None:
                loaded_after = query_inputs(out)
                receipt["loaded_after"] = loaded_after
                receipt["loaded_changes"] = changes(loaded_before, loaded_after)
                receipt["loaded_unchanged"] = loaded_before == loaded_after
            else:
                receipt["loaded_unchanged"] = True
                receipt["loaded_freeze"] = "query-not-reached"
            receipt["native_api_unchanged"] = api_before == api_after
            if search_loaded_before is not None:
                search_loaded_after = search_semantic_inputs(out)
                receipt["search_loaded_after"] = search_loaded_after
                receipt["search_loaded_unchanged"] = search_loaded_before == search_loaded_after
            else:
                receipt["search_loaded_unchanged"] = True
            output_after = output_identity(output_file) if args.census and output_file.exists() else None
            receipt["native_output_after_execution"] = output_after
            receipt["native_output_unchanged"] = validated_output is None or validated_output["after"] == output_after
            identities_unchanged = all(receipt[k] for k in ("installed_unchanged", "support_unchanged", "inputs_unchanged", "native_api_unchanged", "stdpp_unchanged", "support_source_unchanged", "loaded_unchanged", "search_loaded_unchanged", "native_output_unchanged"))
        except (OSError, ValueError) as error:
            receipt["identity_refusal"] = {"error_type": type(error).__name__, "error": str(error)}
        query_record = next((record for record in command_records if record["label"] == "native-query"), {})
        raw_exit = query_record.get("exit")
        native_exit = raw_exit if isinstance(raw_exit, int) else None
        query_completed = query_record.get("process_completed") is True
        receipt["native_exit"] = native_exit
        receipt["query_completed"] = query_completed
        receipt["metadata_validated"] = metadata_validated
        receipt["execution_finished"] = execution_finished
        code, verdict = control_verdict(native_exit, identities_unchanged,
            query_completed=query_completed, metadata_validated=metadata_validated,
            execution_finished=execution_finished)
        if code == 0 and args.census:
            verdict = "native-census-provenance-only"
        receipt["exit"] = code
        receipt["verdict"] = verdict
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({k: receipt[k] for k in ("verdict", "exit", "native_exit", "query_completed", "metadata_validated")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
