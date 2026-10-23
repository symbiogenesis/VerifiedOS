# SPDX-License-Identifier: Apache-2.0
"""Source-carriage guards; fixture checks never build a switch or support package."""

import hashlib
import io
import json
import re
import subprocess
import tarfile
import tempfile
from collections.abc import Callable
from copy import deepcopy
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from ci import sail_support_route as route
from tests.harness import Case, ensure


def refuses(call: Callable[[], object]) -> None:
    try:
        call()
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        return
    raise AssertionError("unsupported source-carriage input accepted")


def revision_guards() -> None:
    revision = "a" * 40
    with patch.object(subprocess, "check_output", return_value=revision + "\n"), \
            patch.object(subprocess, "run") as executed:
        route.guarded_revision(Path(), revision, revision, "refs/heads/main")
        ensure(executed.call_count == 1, "main ancestry checked")
        refuses(lambda: route.guarded_revision(Path(), revision, revision, "refs/heads/work/test"))
        refuses(lambda: route.guarded_revision(Path(), "main", revision, "refs/heads/main"))
        refuses(lambda: route.guarded_revision(Path(), "b" * 40, revision, "refs/heads/main"))
        ensure(executed.call_count == 1, "invalid framing never reached ancestry check")


def asset_guards() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-route-") as directory:
        root = Path(directory)
        (root / "file").write_bytes(b"reviewed")
        entry = {"path": "file", "sha256": hashlib.sha256(b"reviewed").hexdigest()}
        ensure(route.asset(root, entry).read_bytes() == b"reviewed", "exact bytes loaded")
        refuses(lambda: route.asset(root, entry | {"path": "../file"}))
        refuses(lambda: route.asset(root, entry | {"sha256": "0" * 64}))


def archive_guards() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-archive-") as directory:
        root = Path(directory)
        for number, target in enumerate(("../src/file.v", "../../../outside")):
            archive = root / (str(number) + ".tar")
            with tarfile.open(archive, "w") as stream:
                member = tarfile.TarInfo("source/src/file.v")
                member.size = 1
                stream.addfile(member, io.BytesIO(b"x"))
                member = tarfile.TarInfo("source/src-stdpp/file.v")
                member.type, member.linkname = tarfile.SYMTYPE, target
                stream.addfile(member)
            if number == 0:
                extracted = route.extract(archive, root / "safe")
                ensure((extracted / "src-stdpp/file.v").is_symlink(), "source symlink preserved")
            else:
                refuses(partial(route.extract, archive, root / "escaping"))


def closure_and_portability() -> None:
    actual = [{"name": "rocq-core", "version": "9.3.0", "pin": ""}]
    route.same_closure(actual, {"rocq-core": "9.3.0"})
    refuses(lambda: route.same_closure(actual, {"rocq-core": "9.2.0"}))
    refuses(lambda: route.same_closure([actual[0] | {"pin": "main"}], {"rocq-core": "9.3.0"}))
    patch_bytes = b"immutable patch"
    sha = hashlib.sha256(patch_bytes).hexdigest()
    metadata = 'extra-files: [["source.patch" "sha256=' + sha + '"]] source ' + "a" * 64
    route.snapshot_metadata(metadata, {"source.patch": patch_bytes}, "a" * 64)
    refuses(lambda: route.snapshot_metadata(metadata + " file:///tmp/source", {"source.patch": patch_bytes}, "a" * 64))
    refuses(lambda: route.snapshot_metadata(metadata.replace(sha, "b" * 64), {"source.patch": patch_bytes}, "a" * 64))
    refuses(lambda: route.snapshot_metadata(metadata.replace("extra-files:", "missing:"), {"source.patch": patch_bytes}, "a" * 64))


def exact_kernel_context() -> None:
    with patch.object(route.proofaudit, "kernel_context", return_value=["Stdlib.expected"]):
        ensure(route.kernel_reading(0, "", "summary", ["Stdlib.expected"]) == ["Stdlib.expected"], "exact set accepted")
        refuses(lambda: route.kernel_reading(0, "", "summary", []))
        refuses(lambda: route.kernel_reading(1, "", "summary", ["Stdlib.expected"]))
        refuses(lambda: route.kernel_reading(0, "diagnostic", "summary", ["Stdlib.expected"]))
    refuses(lambda: route.kernel_reading(0, "", "missing summary", []))


def cold_and_snapshot_guards() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-cold-") as directory:
        root = Path(directory)
        refuses(lambda: route.Campaign(root, root, "build"))
        snapshot = root / "snapshot"
        snapshot.write_bytes(b"reviewed export")
        route.checked_import(snapshot, hashlib.sha256(snapshot.read_bytes()).hexdigest())
        refuses(lambda: route.checked_import(snapshot, "a" * 64))
        refuses(lambda: route.checked_import(None, None))
        refuses(lambda: route.join(None, root, "a" * 40, root))


def failed_and_skipped_join() -> None:
    with patch.dict(route.os.environ, {"CAMPAIGN_NEEDS": json.dumps({"plan": {"result": "success"},
                    "build": {"result": "failure"}, "import": {"result": "skipped"}})}):
        refuses(lambda: route.join(Path(), Path(), "a" * 40, Path()))


def timeout_preserves_diagnostics() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-timeout-") as directory:
        root = Path(directory)
        side = root / "side"
        (side / "tools/opam").mkdir(parents=True)
        (side / route.RECIPE).write_text('{}', encoding="utf-8")
        with patch.dict(route.os.environ, {"TESTED_REVISION": "a" * 40, "GITHUB_SHA": "a" * 40}), \
                patch.object(subprocess, "Popen") as launched, \
                patch.object(route.os, "killpg", create=True):
            process = launched.return_value.__enter__.return_value
            process.communicate.side_effect = [subprocess.TimeoutExpired(["fixture"], 1),
                                               ("retained stdout", "retained stderr")]
            campaign = route.Campaign(root / "fresh", side, "build")
            refuses(lambda: campaign.run("bounded", ["fixture"], root, timeout=1))
            command = campaign.report["commands"][-1]
            ensure(command["timed_out"] and command["exit"] == 124, "deadline supplies no passing exit")
            ensure((campaign.upload / "bounded.log").read_text() == "retained stdoutretained stderr",
                   "timed-out operation preserves diagnostic bytes")


def complete_join_and_missing_steps() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-join-") as directory:
        root = Path(directory)
        side, artifacts = root / "side", root / "artifacts"
        (side / "tools/opam").mkdir(parents=True)
        frozen = side / "frozen.json"
        frozen.write_text('{"queries":[{}]}', encoding="utf-8")
        license_bytes = b"reviewed BSD license fixture"
        recipe = {"frozen_inventory": {"path": "frozen.json", "sha256": route.receipts.digest(frozen)},
                  "source_license_sha256": hashlib.sha256(license_bytes).hexdigest(),
                  "support_axioms": [], "probes": {name: {"expected_axioms": []}
                                                      for name in ("term", "eqdep", "real", "notation")}}
        route.write(side / route.RECIPE, recipe)
        environment = {"CAMPAIGN_NEEDS": json.dumps({name: {"result": "success"}
                       for name in ("plan", "build", "import")}), "GITHUB_SHA": "a" * 40,
                       "GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "2"}
        for phase in ("build", "import"):
            lane = artifacts / phase
            lane.mkdir(parents=True)
            (lane / "sail-support.lock").write_bytes(b"same reviewed export")
            (lane / "native-census-qualified.json").write_bytes(b"separately qualified native fixture")
            (lane / "Sail-Support-LICENSE").write_bytes(license_bytes)
            route.write(lane / "input-identities.json", {"/fixture/source.v": "a" * 64})
            route.write(lane / "native-assumptions.json", {"fixture": []})
            (lane / "package-metadata.txt").write_text("package metadata fixture", encoding="utf-8")
            evidence = {name: {"sha256": route.receipts.digest(lane / name), "bytes": (lane / name).stat().st_size}
                        for name in ("input-identities.json", "native-assumptions.json", "package-metadata.txt",
                                     "Sail-Support-LICENSE", "sail-support.lock", "native-census-qualified.json")}
            commands = []
            for label in sorted(route.required_labels(phase, 1)):
                log = lane / (label + ".log")
                log.write_bytes(b"kernel fixture" if label.startswith("kernel-") else b"")
                commands.append({"label": label, "log": log.name, "log_sha256": route.receipts.digest(log),
                                 "exit": 0, "strict": label.startswith("strict-")})
            receipt = {"phase": phase, "status": "passed", "cold": True, "revision": "a" * 40,
                       "dispatch_revision": "a" * 40, "run_id": "1", "run_attempt": "2",
                       "recipe_sha256": route.receipts.digest(side / route.RECIPE), "commands": commands,
                       "export_sha256": route.receipts.digest(lane / "sail-support.lock"),
                       "reexport_identical": phase == "import", "evidence": evidence}
            route.write(lane / "receipt.json", receipt)
        with patch.dict(route.os.environ, environment), patch.object(route, "kernel_reading", return_value=[]), \
                patch.object(route, "validate_native_qualification", return_value={"commands": []}):
            route.join(artifacts, side, "a" * 40, root / "result")
            ensure(route.load(root / "result/report.json")["status"] == "passed", "complete independent pair accepted")
            for phase in ("build", "import"):
                path = artifacts / phase / "receipt.json"
                original = route.load(path)
                for label in route.required_labels(phase, 1):
                    route.write(path, original | {"commands": [row for row in original["commands"] if row["label"] != label]})
                    refuses(partial(route.join, artifacts, side, "a" * 40, root / "result"))
                route.write(path, original | {"cold": False})
                refuses(partial(route.join, artifacts, side, "a" * 40, root / "result"))
                route.write(path, original)
                for name in original["evidence"]:
                    member = path.parent / name
                    data = member.read_bytes()
                    member.unlink()
                    refuses(partial(route.join, artifacts, side, "a" * 40, root / "result"))
                    member.write_bytes(data)


def temporary_query_compiler_argv() -> None:
    """Exercise the actual query-loop argv without invoking a native compiler."""
    with tempfile.TemporaryDirectory(prefix="vos-sail-query-argv-") as directory:
        root = Path(directory)
        side = root / "side"
        (side / "tools/opam").mkdir(parents=True)
        (side / route.RECIPE).write_text('{}', encoding="utf-8")
        query_text, reading = "Require Import SailStdpp.Base.\n", "frozen reading\n"
        frozen = side / "frozen.json"
        route.write(frozen, {"queries": [{"query": query_text,
            "query_sha256": hashlib.sha256(query_text.encode()).hexdigest(),
            "baseline_sha256": hashlib.sha256(reading.encode()).hexdigest()}]})
        found = {"support_axioms": [], "frozen_inventory": {
            "path": "frozen.json", "sha256": route.receipts.digest(frozen)}}
        calls: list[tuple[str, list[str]]] = []

        def capture(label: str, argv: list[str], cwd: Path, *, strict: bool = False,
                    timeout: int = 10800, refusal: bool = False) -> subprocess.CompletedProcess[str]:
            source = Path(argv[-1])
            ensure(source.is_file(), "actual compiler input was written")
            ensure(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", source.stem) is not None,
                   "compiler argv contains an invalid Rocq module identifier: " + source.name)
            calls.append((label, argv))
            campaign.report["commands"].append({"label": label})
            if label.startswith("inventory-"):
                stdout = route.proofaudit.EMPTY_BLACKLIST + "\nSailStdpp.Base.fixture_symbol: unit\n"
            elif label.startswith("assumptions-"):
                stdout = route.proofaudit.MARKER + "SailStdpp.Base.fixture_symbol\nClosed under the global context\n"
            elif label.startswith("alias-assumptions-"):
                stdout = ""
            elif label == "support-native-census":
                stdout = '{}'
            else:
                ensure(source.read_text() == query_text, "frozen declaration query remains unchanged")
                stdout = reading
            return subprocess.CompletedProcess(argv, 0, stdout, "")

        with patch.dict(route.os.environ, {"TESTED_REVISION": "a" * 40, "GITHUB_SHA": "a" * 40}):
            campaign = route.Campaign(root / "campaign", side, "build")
            api = SimpleNamespace(parse_search_requests=lambda *_args, **_kwargs: [],
                reading_targets=lambda _metadata: [], census=lambda *_args, **_kwargs: {
                    "SailStdpp.Base": {"symbols": [{"name": "SailStdpp.Base.fixture_symbol", "type": "unit",
                        "assumptions": [], "claims": []}], "alias_audits": []}})
            with patch.object(campaign, "run", side_effect=capture), patch.object(route, "census_api", return_value=api):
                route.audit_sources(campaign, found, [side / "Base.v"], [])
                route.freeze_sources(campaign, found, side / "baseline", side / "candidate", [])
        ensure([label for label, _ in calls] == ["inventory-0", "support-native-census", "assumptions-0", "alias-assumptions-0",
                "frozen-0-baseline", "frozen-0-candidate"], "both temporary query families reach compiler argv")
        for _, argv in calls[:4]:
            ensure(argv[-len(route.STRICT)-1:-1] == route.STRICT, "strict inventory/audit flags unchanged")


def native_identity_population() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-identities-") as directory:
        root = Path(directory)
        source = root / "protected"
        source.mkdir()
        (source / "empty").mkdir()
        (source / "source.v").write_bytes(b"immutable")
        baseline = route.identity_tree([source])
        ensure(str((source / "empty").resolve()) + "/." in baseline, "empty-directory membership retained")
        refuses(lambda: route.identity_tree([source, root / "absent"]))
        (source / "new.v").write_bytes(b"added")
        ensure(route.identity_tree([source]) != baseline, "added population refused by equality")
        (source / "new.v").unlink()
        (source / "source.v").write_bytes(b"changed")
        ensure(route.identity_tree([source]) != baseline, "byte changes visible")
        (source / "source.v").unlink()
        ensure(route.identity_tree([source]) != baseline, "deleted population visible")
    ensure(route.native_path("/home/runner/native/protected") == "/home/runner/native/protected",
           "hosted POSIX roots replay on Windows without local filesystem resolution")
    for value in ("relative", "/home/runner/../other", "/home//runner", "C:\\native", "/home/./runner"):
        refuses(lambda value=value: route.native_path(value))


def duplicate_json_and_streams() -> None:
    refuses(lambda: route.decode('{"root":1,"root":2}'))
    refuses(lambda: route.decode('{"root":{"field":1,"field":2}}'))
    with tempfile.TemporaryDirectory(prefix="vos-sail-streams-") as directory:
        root = Path(directory)
        for name, contents in (("stdout", "native output"), ("stderr", "diagnostic"), ("combined", "native outputdiagnostic")):
            (root / name).write_text(contents, encoding="utf-8")
        command = {"log": "combined", "log_sha256": route.receipts.digest(root / "combined"),
            "streams": {name: {"path": name, "sha256": route.receipts.digest(root / name)}
                for name in ("stdout", "stderr")}}
        ensure(route.command_streams(root, command) == ("native output", "diagnostic"), "streams replay separately")
        (root / "stderr").write_text("altered", encoding="utf-8")
        refuses(lambda: route.command_streams(root, command))
        refuses(lambda: route.retained_member(root, "../outside"))
        refuses(lambda: route.retained_member(root, "a\\b"))


def expected_native_refusal_exits() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-refusal-exits-") as directory:
        root = Path(directory)
        side = root / "side"
        (side / "tools/opam").mkdir(parents=True)
        (side / route.RECIPE).write_text('{}', encoding="utf-8")
        with patch.dict(route.os.environ, {"TESTED_REVISION": "a" * 40, "GITHUB_SHA": "a" * 40}), \
                patch.object(subprocess, "Popen") as launched:
            process = launched.return_value.__enter__.return_value
            process.communicate.return_value = ("", "expected prover refusal")
            campaign = route.Campaign(root / "native", side, "build")
            for code in (0, -9, 2, 124, 137):
                process.returncode = code
                refuses(lambda code=code: campaign.run("refused-" + str(abs(code)), ["fixture"], root, refusal=True))
            process.returncode = 1
            campaign.run("accepted-refusal", ["fixture"], root, refusal=True)
            command = campaign.report["commands"][-1]
            ensure(command["expected_refusal"] and command["exit"] == 1, "normal expected prover error retained")
            ensure(route.command_streams(campaign.upload, command) == ("", "expected prover refusal"),
                   "expected refusal retains both original streams")


def hidden_alias_control_contexts() -> None:
    expected = [{"name": "CensusControls." + kind + ".witness",
                 "expected_axioms": ["CensusControls.HiddenImplementation.hidden_control_axiom"]}
                for kind in ("HiddenSealed", "HiddenAlias")]
    blocks = [route.proofaudit.MARKER + cast("str", entry["name"]) + "\nAxioms:\n" + entry["expected_axioms"][0] + " : Prop\n"
              for entry in expected]
    ensure(len(route.hidden_assumption_audit("".join(blocks), expected)) == 2,
           "sealed implementation and its alias both expose the exact hidden control axiom")
    refuses(lambda: route.hidden_assumption_audit(blocks[0], expected))
    refuses(lambda: route.hidden_assumption_audit("".join(blocks).replace("hidden_control_axiom", "foreign_axiom"), expected))
    refuses(lambda: route.hidden_assumption_audit("".join([*blocks, blocks[1]]), expected))


def standalone_native_replay() -> None:
    """Exercise complete route joins over fixtures; this supplies no native qualification."""
    with tempfile.TemporaryDirectory(prefix="vos-native-replay-") as directory:
        root = Path(directory)
        side, artifact = root / "side", root / "artifact"
        (side / "tools/opam").mkdir(parents=True)
        (side / "tools/rocq-census").mkdir()
        artifact.mkdir()
        route.write(side / route.RECIPE, {})
        control_source = side / "tools/rocq-census"
        for name in ("SignatureFieldRefusal.v", "UnsupportedShapeRefusal.v", "HiddenAssumptions.v"):
            (control_source / name).write_text("(* " + name + " fixture *)\n", encoding="utf-8")
        modules = ["SailStdpp." + name for name in ["TypeCasts", "State_monad", *["M" + str(i) for i in range(27)]]]
        targets = ["CensusControls", "SailStdpp.TypeCasts", "SailStdpp.State_monad"]
        support_map = ["-boot", "-R", "/host/lib/coq/theories", "Corelib", "-Q", "/host/lib/coq/Stdlib",
            "Stdlib", "-Q", "/host/lib/coq/stdpp", "stdpp", "-R", "/host/support", "SailStdpp"]
        paths = {"support": support_map, "probes": ["-Q", "/host/probes", "Qualification"],
                 "controls": ["-Q", "/host/controls", ""]}
        protected = ["/host/bin", "/host/lib", "/host/support", "/host/probes", "/host/controls", "/host/plugin"]
        before = {name + "/.": "a" * 64 for name in [*protected, *[support_map[i] for i in (2, 5, 8)]]}
        before.update({"/host/bin/opam": "a" * 64, "/host/plugin/native.cmxs": "d" * 64,
            "/host/plugin/vos_rocq_census.ml": "b" * 64, "/host/controls/CensusControls.v": "c" * 64})
        runtime = {name: {"path": "/host/bin/" + name, "resolved_path": "/host/bin/" + name, "sha256": "a" * 64}
                   for name in ("opam", "rocq", "rocqchk", "ocamlfind", "ocamlopt")}
        before.update({entry["path"]: entry["sha256"] for entry in runtime.values()})
        runtime["python"] = {"path": "/host/python", "resolved_path": "/host/python", "sha256": "e" * 64}
        before.update({"/host/support/" + module.rsplit(".", 1)[-1] + ".v": "a" * 64 for module in modules})
        sources = {"tools/rocq-census/vos_rocq_census.ml": "b" * 64, "tools/rocq-census/CensusControls.v": "c" * 64}
        spec: dict[str, Any] = {"schema": "verifiedos-rocq-census-controls/1", "root": "CensusControls", "targets": targets,
            "refusals": {"signature": {"source": "SignatureFieldRefusal.v", "diagnostic": "expected signature refusal"},
                "unsupported": {"source": "UnsupportedShapeRefusal.v", "diagnostic": "expected unsupported refusal",
                    "environment": {"VOS_CENSUS_MODE": "census", "VOS_CENSUS_TARGETS": "UnsupportedShapeRefusal.Unsupported",
                        "VOS_CENSUS_RESOLVE": "[]"}}},
            "hidden_assumptions": {"source": "HiddenAssumptions.v", "symbols": [
                {"name": "CensusControls." + kind + ".witness", "expected_axioms": ["CensusControls.HiddenImplementation.hidden_control_axiom"]}
                for kind in ("HiddenSealed", "HiddenAlias")]}}
        found = {"support_modules": [module.removeprefix("SailStdpp.") for module in modules], "support_axioms": [],
                 "probes": {}}
        for name in ("term", "eqdep", "real", "notation"):
            source = side / (name + ".v")
            source.write_text("(* " + name + " *)", encoding="utf-8")
            found["probes"][name] = {"path": source.name, "expected_axioms": []}
            before["/host/probes/" + name + ".v"] = route.receipts.digest(source)
        commands: list[dict[str, Any]] = []

        def add(label: str, tail: list[str], stdout: str = "", stderr: str = "", *,
                text: str | None = None, environment: dict[str, str] | None = None,
                refusal: bool = False, strict: bool = False) -> None:
            command: dict[str, object] = {"label": label, "argv": ["/host/bin/opam", "exec", "--switch=" + route.SWITCH,
                "--", *tail], "exit": 1 if refusal else 0, "timed_out": False, "expected_refusal": refusal,
                "strict": strict, "native_environment": {"OCAMLPATH": "/host/plugin:/host/lib:", **(environment or {})}}
            for name, value in (("stdout", stdout), ("stderr", stderr), ("combined", stdout + stderr)):
                (artifact / (label + "." + name + ".log")).write_text(value, encoding="utf-8")
            command["log"] = label + ".combined.log"
            command["log_sha256"] = route.receipts.digest(artifact / str(command["log"]))
            command["streams"] = {name: {"path": label + "." + name + ".log",
                "sha256": route.receipts.digest(artifact / (label + "." + name + ".log"))} for name in ("stdout", "stderr")}
            if text is not None:
                source = artifact / ("query-" + label + ".v")
                source.write_text(text, encoding="utf-8")
                command.update(query_source=source.name, query_sha256=route.receipts.digest(source), native_source_name=tail[-1].rsplit("/", 1)[-1])
            commands.append(command)

        def add_query(label: str, text: str, mappings: list[str], stdout: str = "", stderr: str = "", *,
                      environment: dict[str, str] | None = None, refusal: bool = False) -> None:
            add(label, ["rocq", "c", *mappings, *route.STRICT, "/host/queries/" + label.replace("-", "_") + ".v"],
                stdout, stderr, text=text, environment=environment, refusal=refusal)

        def classify(metadata: object, searches: dict[str, str], readings: dict[str, str], *,
                     expected_modules: list[str]) -> dict[str, dict[str, Any]]:
            ensure(set(searches) == set(expected_modules), "fixture adapter exact roots")
            return {module: {"symbols": route.proofaudit.inventory(searches[module], module),
                "alias_audits": ([{"source_kind": "declaration-alias", "source_id": "native-alias",
                    "exported_spelling": module + ".alias", "audit_query_name": "Foreign.hidden_alias",
                    "native_reference": {"canonical_name": "Foreign.hidden_alias"}}] if module == "SailStdpp.M0" else [])}
                for module in expected_modules}

        def requests(searches: dict[str, str], *, expected_modules: list[str]) -> list[dict[str, object]]:
            return [{"id": module + ":" + str(index), "requested_root": module, "row_index": index, "spelling": symbol["name"]}
                for module in expected_modules for index, symbol in enumerate(route.proofaudit.inventory(searches[module], module))]

        control_report = {"scope": "adapter-over-native-emitted-evidence", "status": "fixture"}
        api = SimpleNamespace(census=classify, parse_search_requests=requests,
            reading_targets=lambda metadata: [("module", module) for module in metadata["requested_roots"]],
            qualify_controls=lambda *_args: deepcopy(control_report))
        add("native-plugin-build", ["ocamlfind", "ocamlopt", "-rectypes", "-thread", "-shared", "-package",
            "rocq-runtime.vernac", "-w", "+8", "-warn-error", "+8", "-o", "/host/plugin/native.cmxs", "/host/plugin/vos_rocq_census.ml"])
        add("native-control-compile", ["rocq", "c", *support_map, *paths["controls"], *route.STRICT, "/host/controls/CensusControls.v"], strict=True)
        for index, module in enumerate(modules):
            add("strict-" + str(index), ["rocq", "c", *support_map, *route.STRICT,
                "/host/support/" + module.rsplit(".", 1)[-1] + ".v"], strict=True)
        for prefix, requested in (("support", modules), ("control", targets)):
            mapping = [*support_map, *(paths["controls"] if prefix == "control" else [])]
            metadata = {"requested_roots": requested}
            searches = {module: route.proofaudit.EMPTY_BLACKLIST + "\n" + module + ".fixture: unit\n" for module in requested}
            readings = {"module:" + module: "native module fixture " + module for module in requested}
            for suffix, value in (("census", metadata), ("search", searches), ("readings", readings)):
                route.write(artifact / (prefix + "-" + suffix + ".json"), value)
            classified = classify(metadata, searches, readings, expected_modules=requested)
            if prefix == "support":
                route.write(artifact / "support-census-audit.json", classified)
                route.write(artifact / "native-assumptions.json", {module: data["symbols"] for module, data in classified.items()})
                route.write(artifact / "native-alias-assumptions.json", {module: {"bindings": data["alias_audits"],
                    "audits": route.alias_symbols(data["alias_audits"])} for module, data in classified.items()})
            for index, module in enumerate(requested):
                label = ("inventory-" if prefix == "support" else "control-inventory-") + str(index)
                add_query(label, route.proofaudit.inventory_query(module), mapping, searches[module])
                add_query(prefix + "-reading-" + str(index), "Require " + " ".join(requested) + ".\n" + route.proofaudit.SETTINGS
                    + "Print Module " + module + ".\n", mapping, readings["module:" + module])
                if prefix == "support":
                    symbols = classified[module]["symbols"]
                    add_query("assumptions-" + str(index), route.proofaudit.assumption_query(module, symbols), mapping,
                        route.proofaudit.MARKER + module + ".fixture\nClosed under the global context\n")
                    aliases = route.alias_symbols(classified[module]["alias_audits"])
                    alias_output = "".join(route.proofaudit.MARKER + symbol["name"] + "\nClosed under the global context\n"
                                           for symbol in aliases)
                    add_query("alias-assumptions-" + str(index), route.proofaudit.assumption_query(module, aliases), mapping, alias_output)
            add_query(prefix + "-native-census", "Require " + " ".join(requested) + '.\nDeclare ML Module "vos_rocq_census".\n',
                mapping, json.dumps(metadata), environment={"VOS_CENSUS_MODE": "census", "VOS_CENSUS_TARGETS": ",".join(requested),
                    "VOS_CENSUS_RESOLVE": json.dumps(requests(searches, expected_modules=requested))})
        for name, entry in cast("dict[str, dict[str, Any]]", spec["refusals"]).items():
            add_query("native-" + name + "-refusal", (control_source / entry["source"]).read_text(),
                [*support_map, *paths["controls"]], stderr=entry["diagnostic"], environment=entry.get("environment"), refusal=True)
        hidden = cast("dict[str, Any]", spec["hidden_assumptions"])
        hidden_symbols = [{"name": entry["name"], "type": "control", "claims": [],
            "assumptions": [entry["expected_axioms"][0] + " : Prop"]} for entry in hidden["symbols"]]
        add_query("native-hidden-assumptions", (control_source / hidden["source"]).read_text(), [*support_map, *paths["controls"]],
            "".join(route.proofaudit.MARKER + entry["name"] + "\nAxioms:\n" + entry["expected_axioms"][0] + " : Prop\n"
                    for entry in hidden["symbols"]))
        route.write(artifact / "control-adapter-verdicts.json", control_report)
        route.write(artifact / "native-control-verdicts.json", {"schema": spec["schema"], "status": "passed", "adapter": control_report,
            "hidden_assumptions": hidden_symbols, "native_refusals": sorted(spec["refusals"])})
        for name in ("support", "term", "eqdep", "real", "notation"):
            kernel_roots = modules if name == "support" else ["Qualification." + name]
            add("kernel-" + name, ["rocqchk", "-silent", "-o", *support_map, *paths["probes"], *kernel_roots], stderr="kernel fixture")
            if name != "support":
                add("probe-compile-" + name, ["rocq", "c", *support_map, *paths["probes"], *route.STRICT,
                    "/host/probes/" + name + ".v"], strict=True)
        route.write(artifact / "input-identities-before.json", before)
        route.write(artifact / "input-identities.json", before)
        record: dict[str, Any] = {"schema": route.NATIVE_SCHEMA, "status": "passed", "cold": True, "revision": "a" * 40,
            "dispatch_revision": "a" * 40, "run_id": "1", "run_attempt": "2", "recipe_sha256": route.receipts.digest(side / route.RECIPE),
            "sources": sources, "modules": modules, "protected_roots": protected, "load_paths": paths, "commands": commands,
            "runtime_before": runtime, "runtime_after": deepcopy(runtime),
            "runner": {"platform": "fixture", "machine": "fixture", "python": "fixture"},
            "environment_boundary": route.ENVIRONMENT_BOUNDARY,
            "evidence": {path.name: {"sha256": route.receipts.digest(path), "bytes": path.stat().st_size} for path in artifact.iterdir()}}
        target = artifact / "native-census-qualified.json"
        route.write(target, record)
        with patch.object(route, "recipe", return_value=found), patch.object(route, "native_sources", return_value=sources), \
                patch.object(route, "control_spec", return_value=spec), patch.object(route, "census_api", return_value=api), \
                patch.object(route, "kernel_reading", return_value=[]):
            route.validate_native_qualification(artifact, side, "a" * 40, run_id="1", run_attempt="2")
            mutations = [lambda row: row["modules"].pop(), lambda row: row["commands"].pop(),
                lambda row: row.update(run_id="3"), lambda row: row["sources"].update(foreign="a" * 64),
                lambda row: row["runtime_after"]["python"].update(sha256="f" * 64),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "kernel-support")["argv"].pop(),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "support-native-census")["native_environment"].update(VOS_CENSUS_TARGETS="foreign"),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "inventory-0").pop("query_source"),
                lambda row: row.update(commands=[cmd for cmd in row["commands"] if cmd["label"] != "alias-assumptions-2"]),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "native-signature-refusal").update(exit=137)]
            for mutation in mutations:
                altered = deepcopy(record)
                mutation(altered)
                route.write(target, altered)
                refuses(lambda: route.validate_native_qualification(artifact, side, "a" * 40, run_id="1", run_attempt="2"))
            altered = deepcopy(record)
            alias_command = next(cmd for cmd in altered["commands"] if cmd["label"] == "alias-assumptions-2")
            alias_files = [alias_command["streams"]["stdout"]["path"], alias_command["log"], "native-alias-assumptions.json"]
            original_bytes = {name: (artifact / name).read_bytes() for name in alias_files}
            hidden_output = route.proofaudit.MARKER + "Foreign.hidden_alias\nAxioms:\nForbidden.control_axiom : Prop\n"
            for name in alias_files[:2]:
                (artifact / name).write_text(hidden_output, encoding="utf-8")
            alias_result = route.load(artifact / "native-alias-assumptions.json")
            alias_result["SailStdpp.M0"]["audits"][0]["assumptions"] = ["Forbidden.control_axiom : Prop"]
            route.write(artifact / "native-alias-assumptions.json", alias_result)
            alias_command["streams"]["stdout"]["sha256"] = route.receipts.digest(artifact / alias_files[0])
            alias_command["log_sha256"] = route.receipts.digest(artifact / alias_files[1])
            for name in alias_files:
                altered["evidence"][name] = {"sha256": route.receipts.digest(artifact / name), "bytes": (artifact / name).stat().st_size}
            route.write(target, altered)
            refuses(lambda: route.validate_native_qualification(artifact, side, "a" * 40))
            for name, data in original_bytes.items():
                (artifact / name).write_bytes(data)
            route.write(target, record)
            (artifact / "input-identities.json").write_text('{"changed":"' + "b" * 64 + '"}', encoding="utf-8")
            changed = deepcopy(record)
            changed["evidence"]["input-identities.json"] = {"sha256": route.receipts.digest(artifact / "input-identities.json"),
                "bytes": (artifact / "input-identities.json").stat().st_size}
            route.write(target, changed)
            refuses(lambda: route.validate_native_qualification(artifact, side, "a" * 40))


def cases() -> list[Case]:
    return [Case("main-revision-guards", revision_guards), Case("immutable-assets", asset_guards),
            Case("contained-source-symlinks", archive_guards), Case("closure-and-portability", closure_and_portability),
            Case("exact-kernel-context", exact_kernel_context), Case("cold-and-snapshot", cold_and_snapshot_guards),
            Case("failed-skipped-join", failed_and_skipped_join),
            Case("timeout-retains-diagnostics", timeout_preserves_diagnostics),
            Case("complete-join-required-steps", complete_join_and_missing_steps),
            Case("valid-temporary-query-compiler-argv", temporary_query_compiler_argv),
            Case("native-complete-identity-population", native_identity_population),
            Case("native-duplicate-json-and-streams", duplicate_json_and_streams),
            Case("native-expected-refusal-exits", expected_native_refusal_exits),
            Case("native-hidden-alias-control-contexts", hidden_alias_control_contexts),
            Case("native-standalone-replay", standalone_native_replay)]
