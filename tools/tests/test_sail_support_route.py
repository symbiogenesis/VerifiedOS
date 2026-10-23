# SPDX-License-Identifier: Apache-2.0
"""Source-carriage guards; fixture checks never build a switch or support package."""

import hashlib
import io
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
import weakref
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


def canonical_json_streaming() -> None:
    payload = {"z": [None, True, 3, {"unicode": "λ雪", "escaped": "line\n\"\\"}], "a": {"value": -0.25}}
    expected = (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="vos-canonical-json-") as directory:
        path = Path(directory) / "audit.json"
        route.write(path, payload)
        ensure(path.read_bytes() == expected, "incremental JSON writer preserves the exact prior canonical encoding")
        route.require_canonical_json(path, payload)
        mutations = [expected[:-1], expected.replace(b'"value": -0.25', b'"value": 0.25'),
                     expected.replace(b'"value": -0.25', b'"value": -0.25, "value": -0.25'),
                     json.dumps(payload, sort_keys=True).encode("utf-8") + b"\n"]
        for changed in mutations:
            path.write_bytes(changed)
            refuses(lambda: route.require_canonical_json(path, payload))


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
    refuses(lambda: route.same_closure([*actual, *actual], {"rocq-core": "9.3.0"}))
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
                output = Path(campaign.environment[route.OUTPUT_VARIABLE])
                record = campaign.report["commands"][-1]
                record.update(status="completed", exit=0, process_completed=True, timed_out=False, expected_refusal=False,
                    native_environment={route.OUTPUT_VARIABLE: str(output)},
                    output_file_before=route.output_intent(campaign.environment, campaign.root))
                output.write_text('{ "schema": "' + route.CENSUS_SCHEMA + '" }\n', encoding="utf-8")
                record["output_file_after"] = route.output_identity(output)
                stdout = json.dumps({"schema": route.OUTPUT_SCHEMA, "census_schema": route.CENSUS_SCHEMA,
                    **{key: record["output_file_after"][key] for key in ("path", "bytes", "blake2b_256")}})
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
        ensure(route.OUTPUT_VARIABLE not in campaign.environment, "census output destination does not reach later queries")
        for command in campaign.report["commands"][-2:]:
            ensure((campaign.upload / command["frozen_query_source"]).read_bytes() == query_text.encode("utf-8")
                   and command["query_sha256"] == hashlib.sha256(query_text.encode("utf-8")).hexdigest(),
                   "frozen queries retain exact source bytes and bind both native invocations")


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


def native_control_census_bindings() -> None:
    sealed, alias = "CensusControls.HiddenSealed.witness", "CensusControls.HiddenAlias.witness"
    canonical = "CensusControls.HiddenImplementation.witness"
    required = ["CensusControls.HiddenSealed", "CensusControls.HiddenAlias", "SailStdpp.TypeCasts.ZEqdep"]
    spec = {"root": "CensusControls", "required_modules": required,
            "hidden_assumptions": {"symbols": [{"name": sealed}, {"name": alias}]}}
    classified: dict[str, dict[str, Any]] = {"CensusControls": {"modules": [
        {"id": name, "query": {"target": name, "target_module_id": name, "coverage_path": []}}
        for name in required[:2]], "symbols": [{"name": canonical}],
        "declarations": [{"classification": "owned", "exported_name": sealed,
            "native_reference": {"exported_name": sealed, "canonical_name": canonical},
            "implementation_connection": {"audit_query_name": canonical}}],
        "alias_audits": [{"exported_spelling": alias, "audit_query_name": canonical}]},
        "SailStdpp.TypeCasts": {"modules": [{"id": required[2], "query": {
            "target": required[2], "target_module_id": required[2], "coverage_path": []}}]}}
    route.control_census_join(classified, spec)
    missing_alias = deepcopy(classified)
    missing_alias["CensusControls"]["modules"].pop()
    refuses(lambda: route.control_census_join(missing_alias, spec))
    unbound_alias = deepcopy(classified)
    unbound_alias["CensusControls"]["alias_audits"] = []
    refuses(lambda: route.control_census_join(unbound_alias, spec))
    unbound_owned = deepcopy(classified)
    unbound_owned["CensusControls"]["declarations"][0]["classification"] = "interface"
    refuses(lambda: route.control_census_join(unbound_owned, spec))
    wrong_guard = deepcopy(classified)
    wrong_guard["CensusControls"]["symbols"][0]["name"] = "Foreign.witness"
    refuses(lambda: route.control_census_join(wrong_guard, spec))
    audit_binding = deepcopy(classified)
    audit_binding["CensusControls"]["alias_audits"] = [{"exported_spelling": "CensusControls.other",
                                                      "audit_query_name": alias}]
    route.control_census_join(audit_binding, spec)


def command_intent_and_interruption() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-command-intent-") as directory:
        root = Path(directory)
        side = root / "side"
        (side / "tools/opam").mkdir(parents=True)
        (side / route.RECIPE).write_text('{}', encoding="utf-8")
        with patch.dict(route.os.environ, {"TESTED_REVISION": "a" * 40, "GITHUB_SHA": "a" * 40}):
            campaign = route.Campaign(root / "campaign", side, "build")

            def failed_launch(*_args: object, **_kwargs: object) -> None:
                command = route.load(campaign.upload / "receipt.json")["commands"][-1]
                ensure(command["status"] == "pending" and command["exit"] is None
                       and command["process_completed"] is False, "intent reaches disk before Popen")
                raise OSError("mocked launcher failure")

            with patch.object(subprocess, "Popen", side_effect=failed_launch):
                refuses(lambda: campaign.run("launch-failure", ["fixture"], root))
            command = route.load(campaign.upload / "receipt.json")["commands"][-1]
            ensure(command["status"] == "launch-error" and command["exit"] is None
                   and command["process_completed"] is False, "failed launch supplies no successful exit")
            with patch.object(subprocess, "Popen") as launched:
                launched.return_value.__enter__.return_value.communicate.side_effect = KeyboardInterrupt
                try:
                    campaign.run("interrupted", ["fixture"], root)
                except KeyboardInterrupt:
                    pass
                else:
                    raise AssertionError("interruption was swallowed")
            command = route.load(campaign.upload / "receipt.json")["commands"][-1]
            ensure(command["status"] == "interrupted" and command["exit"] is None
                   and command["process_completed"] is False, "interrupted command cannot inherit passing evidence")
            inputs = campaign.root / "native-request-inputs"
            inputs.mkdir()
            source = inputs / "support-requests.json"
            source.write_bytes(b"[]")
            route.select_requests(campaign.environment, source=source)

            def changed_request(*_args: object, **_kwargs: object) -> tuple[str, str]:
                source.write_bytes(b"[{}]")
                return "", ""

            with patch.object(subprocess, "Popen") as launched:
                process = launched.return_value.__enter__.return_value
                process.returncode = 0
                process.communicate.side_effect = changed_request
                refuses(lambda: campaign.run("changed-request", ["fixture"], root))
            command = route.load(campaign.upload / "receipt.json")["commands"][-1]
            ensure(command["request_source_before"] != command["request_source_after"],
                   "a successful process cannot hide changed request input bytes")


def request_file_protocol() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-request-files-") as directory:
        root = Path(directory)
        private = root / "native"
        inputs = private / "native-request-inputs"
        inputs.mkdir(parents=True)
        source = inputs / "support-requests.json"
        source.write_bytes(b"[]")
        environment: dict[str, str] = {}
        route.select_requests(environment, direct="[]")
        direct = route.request_source(environment, private)
        ensure(direct is not None and direct["kind"] == "environment", "direct control input bound")
        route.select_requests(environment, source=source)
        ensure("VOS_CENSUS_RESOLVE" not in environment, "file transition clears the unused direct variable")
        original = route.request_source(environment, private)
        ensure(original is not None and original["sha256"] == hashlib.sha256(b"[]").hexdigest(), "exact file bytes bound")
        source.write_bytes(b"[{}]")
        ensure(route.request_source(environment, private) != original, "request byte changes visible")
        environment["VOS_CENSUS_RESOLVE"] = "[]"
        refuses(lambda: route.request_source(environment, private))
        route.select_requests(environment, direct="[]")
        ensure("VOS_CENSUS_RESOLVE_FILE" not in environment, "unsupported-refusal transition clears the prior file variable")
        route.select_requests(environment, source=source)
        source.unlink()
        refuses(lambda: route.request_source(environment, private))
        source.mkdir()
        refuses(lambda: route.request_source(environment, private))
        source.rmdir()
        with source.open("wb") as stream:
            stream.truncate(route.MAX_REQUEST_BYTES + 1)
        refuses(lambda: route.request_source(environment, private))
        source.write_bytes(b"[]")
        with patch.object(Path, "open", side_effect=PermissionError("mocked unreadable request file")):
            refuses(lambda: route.request_source(environment, private))
        outside = root / "outside.json"
        outside.write_bytes(b"[]")
        route.select_requests(environment, source=outside)
        refuses(lambda: route.request_source(environment, private))
        route.select_requests(environment, source=Path("relative.json"))
        refuses(lambda: route.request_source(environment, private))
        refuses(lambda: route.select_requests(environment, direct="[]", source=source))


def native_output_file_protocol() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-native-output-") as directory:
        root = Path(directory)
        private, retained = root / "private", root / "retained"
        private.mkdir()
        retained.mkdir()
        source = private / "support-census.json"
        environment = {route.OUTPUT_VARIABLE: str(source)}
        intent = route.output_intent(environment, private)
        raw = ('{ "schema": "' + route.CENSUS_SCHEMA + '", "retained": [1, 2] }\n').encode()
        source.write_bytes(raw)
        identity = route.output_identity(source)
        envelope = {"schema": route.OUTPUT_SCHEMA, "census_schema": route.CENSUS_SCHEMA,
                    **{key: identity[key] for key in ("path", "bytes", "blake2b_256")}}
        command: dict[str, Any] = {"status": "completed", "exit": 0, "process_completed": True,
            "timed_out": False, "expected_refusal": False, "native_environment": environment,
            "output_file_before": intent, "output_file_after": identity}
        route.retain_census_output(json.dumps(envelope), source, retained / source.name, command)
        ensure((retained / source.name).read_bytes() == raw, "native JSON bytes copied without reserialization")
        ensure(identity["blake2b_256"] == hashlib.blake2b(raw, digest_size=32).hexdigest(), "independent BLAKE2b-256")
        for mutation in (lambda row: row.update(path="/foreign/census.json"), lambda row: row.update(bytes=0),
                         lambda row: row.update(bytes=True), lambda row: row.update(blake2b_256="F" * 64),
                         lambda row: row.update(extra="unreviewed"), lambda row: row.pop("census_schema")):
            altered = deepcopy(envelope)
            mutation(altered)
            refuses(lambda altered=altered: route.output_envelope(json.dumps(altered), str(source)))
        for stdout in (json.dumps(envelope)[:-1], "diagnostic\n" + json.dumps(envelope),
                       json.dumps(envelope) + json.dumps(envelope),
                       json.dumps(envelope).replace('"schema":', '"schema":"duplicate","schema":', 1)):
            refuses(lambda stdout=stdout: route.output_envelope(stdout, str(source)))
        altered = deepcopy(envelope)
        altered["blake2b_256"] = "f" * 64
        refuses(lambda: route.retain_census_output(json.dumps(altered), source, retained / "bad.json", command))
        source.write_bytes(raw[:-3])
        refuses(lambda: route.retain_census_output(json.dumps(envelope), source, retained / "bad.json", command))
        source.write_bytes(raw)
        command["output_file_after"] = route.output_identity(source)
        for changes in ({"exit": -9}, {"status": "pending"}, {"output_file_before": {"path": str(source), "absent": False}}):
            refused_command = command | changes
            refuses(lambda refused_command=refused_command:
                    route.retain_census_output(json.dumps(envelope), source, retained / "bad.json", refused_command))
        duplicate = ('{"schema":"' + route.CENSUS_SCHEMA + '","x":1,"x":2}').encode()
        source.write_bytes(duplicate)
        command["output_file_after"] = route.output_identity(source)
        duplicate_envelope = envelope | {key: command["output_file_after"][key] for key in ("bytes", "blake2b_256")}
        refuses(lambda: route.retain_census_output(json.dumps(duplicate_envelope), source, retained / "bad.json", command))
        source.write_bytes(raw)
        command["output_file_after"] = route.output_identity(source)
        copy = shutil.copyfile

        def changed_copy(src: Path, dst: Path) -> None:
            copy(src, dst)
            source.write_bytes(raw + b" ")

        with patch.object(route.shutil, "copyfile", side_effect=changed_copy):
            refuses(lambda: route.retain_census_output(json.dumps(envelope), source, retained / "copy-drift.json", command))
        source.unlink()
        refuses(lambda: route.retain_census_output(json.dumps(envelope), source, retained / "missing.json", command))
        source.mkdir()
        refuses(lambda: route.output_identity(source))
        refuses(lambda: route.output_intent(environment, private))
        refuses(lambda: route.output_intent({route.OUTPUT_VARIABLE: "relative.json"}, private))
        refuses(lambda: route.output_intent({route.OUTPUT_VARIABLE: str(root / "outside.json")}, private))

        side = root / "side"
        (side / "tools/opam").mkdir(parents=True)
        (side / route.RECIPE).write_text('{}', encoding="utf-8")
        with patch.dict(route.os.environ, {"TESTED_REVISION": "a" * 40, "GITHUB_SHA": "a" * 40,
                route.OUTPUT_VARIABLE: str(source), route.PROGRESS_VARIABLE: str(source)}), \
                patch.object(subprocess, "Popen") as launched:
            campaign = route.Campaign(root / "campaign", side, "build")
            ensure(route.OUTPUT_VARIABLE not in campaign.environment and route.PROGRESS_VARIABLE not in campaign.environment,
                   "campaign clears inherited output and unselected progress destinations")
            partial = campaign.root / "support-census.json"

            def killed(*_args: object, **_kwargs: object) -> tuple[str, str]:
                before = route.load(campaign.upload / "receipt.json")["commands"][-1]
                ensure(before["output_file_before"] == {"path": str(partial), "absent": True},
                       "expected output absence is persisted before the native launch")
                ensure(route.PROGRESS_VARIABLE not in before["native_environment"], "query clears stale progress before launch")
                campaign.environment[route.PROGRESS_VARIABLE] = str(partial)
                partial.write_bytes(b'{"schema":')
                return "", "killed native producer"

            process = launched.return_value.__enter__.return_value
            process.communicate.side_effect = killed
            process.returncode = -9
            campaign.environment[route.PROGRESS_VARIABLE] = str(partial)
            refuses(lambda: route.query(campaign, "support-native-census", "", [], census_output=partial))
            failed = campaign.report["commands"][-1]
            ensure((campaign.upload / failed["output_partial"]).read_bytes() == b'{"schema":',
                   "failed native partial bytes remain diagnostic evidence")
            ensure("output_file_verified" not in failed and route.OUTPUT_VARIABLE not in campaign.environment
                   and route.PROGRESS_VARIABLE not in campaign.environment,
                   "killed output supplies no verified census and output setting is cleared")
            process.communicate.side_effect = None
            process.communicate.return_value = ("", "expected refusal")
            process.returncode = 1
            campaign.environment[route.OUTPUT_VARIABLE] = str(partial)
            campaign.environment[route.PROGRESS_VARIABLE] = str(partial)
            route.query(campaign, "native-unsupported-refusal", "", [], refusal=True)
            ensure(not {route.OUTPUT_VARIABLE, route.PROGRESS_VARIABLE}
                   & campaign.report["commands"][-1]["native_environment"].keys(),
                   "refusal query clears inherited census output and progress destinations")


def standalone_native_replay() -> None:
    """Exercise complete route joins over fixtures; this supplies no native qualification."""
    with tempfile.TemporaryDirectory(prefix="vos-native-replay-") as directory:
        root = Path(directory)
        side, artifact = root / "side", root / "artifact"
        (side / "tools/opam").mkdir(parents=True)
        (side / "tools/rocq-census").mkdir()
        artifact.mkdir()
        route.write(side / route.RECIPE, {})
        shutil.copy2(route.TOOLS / "opam/rocq.lock", side / "tools/opam/rocq.lock")
        control_source = side / "tools/rocq-census"
        for name in ("SignatureFieldRefusal.v", "UnsupportedShapeRefusal.v", "HiddenAssumptions.v"):
            (control_source / name).write_text("(* " + name + " fixture *)\n", encoding="utf-8")
        modules = ["SailStdpp." + name for name in ["TypeCasts", "State_monad", *["M" + str(i) for i in range(27)]]]
        targets = ["CensusControls", "SailStdpp.TypeCasts", "SailStdpp.State_monad"]
        support_map = ["-boot", "-R", "/host/lib/coq/theories", "Corelib", "-Q", "/host/lib/coq/Stdlib",
            "Stdlib", "-Q", "/host/lib/coq/stdpp", "stdpp", "-R", "/host/support", "SailStdpp"]
        baseline_tree = "/host/baseline-source/upstream/_build/default/src-stdpp"
        paths = {"support": support_map, "probes": ["-Q", "/host/probes", "Qualification"],
                 "controls": ["-Q", "/host/controls", ""], "baseline": ["-R", baseline_tree, "SailStdpp"]}
        protected = ["/host/bin", "/host/lib", "/host/support", "/host/probes", "/host/controls", "/host/plugin", baseline_tree]
        before = {name + "/.": "a" * 64 for name in [*protected, *[support_map[i] for i in (2, 5, 8)]]}
        before.update({"/host/bin/opam": "a" * 64, "/host/plugin/native.cmxs": "d" * 64,
            "/host/plugin/vos_rocq_census.ml": "b" * 64, "/host/controls/CensusControls.v": "c" * 64})
        opam = {"root": "/host/opam", "switch": route.SWITCH, "prefix": "/host/opam/" + route.SWITCH}
        runtime = {name: {"path": opam["prefix"] + "/bin/" + name, "resolved_path": opam["prefix"] + "/bin/" + name, "sha256": "a" * 64}
                   for name in ("rocq", "rocqchk", "ocamlfind", "ocamlopt")}
        runtime["opam"] = {"path": "/host/bin/opam", "resolved_path": "/host/bin/opam", "sha256": "a" * 64}
        before.update({entry["path"]: entry["sha256"] for entry in runtime.values()})
        runtime["python"] = {"path": "/host/python", "resolved_path": "/host/python", "sha256": "e" * 64}
        before.update({"/host/support/" + module.rsplit(".", 1)[-1] + ".v": "a" * 64 for module in modules})
        sources = {"tools/rocq-census/vos_rocq_census.ml": "b" * 64, "tools/rocq-census/CensusControls.v": "c" * 64}
        spec: dict[str, Any] = {"schema": "verifiedos-rocq-census-controls/1", "root": "CensusControls", "targets": targets,
            "required_modules": ["CensusControls.HiddenSealed", "CensusControls.HiddenAlias", "SailStdpp.TypeCasts.ZEqdep"],
            "refusals": {"signature": {"source": "SignatureFieldRefusal.v", "diagnostic": "expected signature refusal"},
                "unsupported": {"source": "UnsupportedShapeRefusal.v", "diagnostic": "expected unsupported refusal",
                    "environment": {"VOS_CENSUS_MODE": "census", "VOS_CENSUS_TARGETS": "UnsupportedShapeRefusal.Unsupported",
                        "VOS_CENSUS_RESOLVE": "[]"}}},
            "hidden_assumptions": {"source": "HiddenAssumptions.v", "symbols": [
                {"name": "CensusControls." + kind + ".witness", "expected_axioms": ["CensusControls.HiddenImplementation.hidden_control_axiom"]}
                for kind in ("HiddenSealed", "HiddenAlias")]}}
        frozen_query, frozen_reading = "Require SailStdpp.TypeCasts.\nPrint SailStdpp.TypeCasts.fixture.\n", "frozen elaborated fixture\n"
        frozen_file = side / "frozen.json"
        route.write(frozen_file, {"queries": [{"module": "TypeCasts", "query": frozen_query,
            "query_sha256": hashlib.sha256(frozen_query.encode("utf-8")).hexdigest(),
            "baseline_sha256": hashlib.sha256(frozen_reading.encode("utf-8")).hexdigest()}]})
        before.update(dict.fromkeys((baseline_tree + "/TypeCasts.v", baseline_tree + "/TypeCasts.vo", "/host/support/TypeCasts.vo"), "a" * 64))
        found = {"support_modules": [module.removeprefix("SailStdpp.") for module in modules], "support_axioms": [],
                 "frozen_inventory": {"path": frozen_file.name, "sha256": route.receipts.digest(frozen_file)},
                 "probes": {}, "base_lock": {"path": "tools/opam/rocq.lock", "sha256": route.receipts.digest(side / "tools/opam/rocq.lock")}}
        for name in ("term", "eqdep", "real", "notation"):
            source = side / (name + ".v")
            source.write_text("(* " + name + " *)", encoding="utf-8")
            found["probes"][name] = {"path": source.name, "expected_axioms": []}
            before["/host/probes/" + name + ".v"] = route.receipts.digest(source)
        commands: list[dict[str, Any]] = []

        def add(label: str, tail: list[str], stdout: str = "", stderr: str = "", *,
                text: str | None = None, environment: dict[str, str] | None = None,
                refusal: bool = False, strict: bool = False, direct: bool = False, cwd: str = "/host") -> None:
            command: dict[str, object] = {"label": label, "argv": ["/host/bin/opam",
                *([] if direct else ["exec", "--switch=" + route.SWITCH, "--"]), *tail],
                "cwd": cwd,
                "exit": 1 if refusal else 0, "timed_out": False, "expected_refusal": refusal,
                "status": "completed", "process_completed": True,
                "strict": strict, "native_environment": {"OCAMLPATH": "/host/plugin:/host/lib:",
                    "OPAMROOT": opam["root"], "OPAMSWITCH": opam["switch"], "OPAM_SWITCH_PREFIX": opam["prefix"], **(environment or {})}}
            selected = cast("dict[str, str]", command["native_environment"])
            request_identity: dict[str, Any] | None = None
            if "VOS_CENSUS_RESOLVE_FILE" in selected:
                path = selected["VOS_CENSUS_RESOLVE_FILE"]
                retained = artifact / path.rsplit("/", 1)[-1]
                request_identity = {"kind": "file", "path": path, "bytes": retained.stat().st_size,
                                    "sha256": route.receipts.digest(retained)}
            elif "VOS_CENSUS_RESOLVE" in selected:
                data = selected["VOS_CENSUS_RESOLVE"].encode("utf-8")
                request_identity = {"kind": "environment", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            command.update(request_source_before=request_identity, request_source_after=deepcopy(request_identity))
            if route.OUTPUT_VARIABLE in selected:
                path = selected[route.OUTPUT_VARIABLE]
                identity = route.output_identity(artifact / path.rsplit("/", 1)[-1]) | {"path": path}
                command.update(output_file_before={"path": path, "absent": True}, output_file_after=identity,
                    output_file_verified=deepcopy(identity), output_retained=path.rsplit("/", 1)[-1])
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
            result: dict[str, dict[str, Any]] = {module: {"symbols": route.proofaudit.inventory(searches[module], module),
                "alias_audits": ([{"source_kind": "declaration-alias", "source_id": "native-alias",
                    "exported_spelling": module + ".alias", "audit_query_name": "Foreign.hidden_alias",
                    "native_reference": {"canonical_name": "Foreign.hidden_alias"}}] if module == "SailStdpp.M0" else [])}
                for module in expected_modules}
            if "CensusControls" in result:
                for module, value in result.items():
                    value["modules"] = [{"id": name, "query": {"target": name, "target_module_id": name, "coverage_path": []}}
                                        for name in spec["required_modules"] if name.startswith(module + ".")]
                value = result["CensusControls"]
                owned = "CensusControls.HiddenSealed.witness"
                value["symbols"].append({"name": owned, "type": "Prop", "claims": [], "assumptions": []})
                value["declarations"] = [{"classification": "owned", "exported_name": owned,
                    "native_reference": {"exported_name": owned, "canonical_name": owned},
                    "implementation_connection": {"audit_query_name": owned}}]
                value["alias_audits"] = [{"exported_spelling": "CensusControls.HiddenAlias.witness", "audit_query_name": owned}]
            return result

        def requests(searches: dict[str, str], *, expected_modules: list[str]) -> list[dict[str, object]]:
            return [{"id": module + ":" + str(index), "requested_root": module, "row_index": index, "spelling": symbol["name"]}
                for module in expected_modules for index, symbol in enumerate(route.proofaudit.inventory(searches[module], module))]

        control_report = {"scope": "adapter-over-native-emitted-evidence", "status": "fixture"}
        api = SimpleNamespace(census=classify, parse_search_requests=requests,
            reading_targets=lambda metadata: [("module", module) for module in metadata["requested_roots"]],
            qualify_controls=lambda *_args: deepcopy(control_report))
        closure_text = "".join(name + " " + version + "\n" for name, version in sorted(route.expected_closure(side, found).items()))
        add("closure", ["list", "--switch=" + route.SWITCH, "--installed", "--short", "--columns=name,version,pin", "--color=never"],
            stdout=closure_text, direct=True)
        add("baseline-build", ["dune", "build", "-p", "rocq-sail-stdpp", "-j", "2", "@install"],
            cwd="/host/baseline-source/upstream")
        retained_frozen = artifact / "query-frozen-0.v"
        retained_frozen.write_bytes(frozen_query.encode("utf-8"))
        for name, mapping in (("baseline", paths["baseline"]), ("candidate", support_map[-3:])):
            add("frozen-0-" + name, ["rocq", "c", *support_map[:-3], *mapping, "-q", "/host/Frozen_0.v"], stdout=frozen_reading)
            commands[-1].update(frozen_query_source=retained_frozen.name,
                query_sha256=route.receipts.digest(retained_frozen), native_source_name="Frozen_0.v")
        add("native-plugin-build", ["ocamlfind", "ocamlopt", "-rectypes", "-thread", "-shared", "-package",
            "rocq-runtime.vernac", "-w", "+8", "-warn-error", "+8", "-o", "/host/plugin/native.cmxs", "/host/plugin/vos_rocq_census.ml"], strict=True)
        add("native-control-compile", ["rocq", "c", *support_map, *paths["controls"], *route.STRICT, "/host/controls/CensusControls.v"], strict=True)
        for index, module in enumerate(modules):
            add("strict-" + str(index), ["rocq", "c", *support_map, *route.STRICT,
                "/host/support/" + module.rsplit(".", 1)[-1] + ".v"], strict=True)
        for prefix, requested in (("support", modules), ("control", targets)):
            mapping = [*support_map, *(paths["controls"] if prefix == "control" else [])]
            searches = {module: route.proofaudit.EMPTY_BLACKLIST + "\n" + module + ".fixture: unit\n" for module in requested}
            resolution_requests = requests(searches, expected_modules=requested)
            metadata = {"schema": route.CENSUS_SCHEMA, "requested_roots": requested, "resolution_requests": resolution_requests}
            readings = {"module:" + module: "native module fixture " + module for module in requested}
            for suffix, value in (("census", metadata), ("search", searches), ("readings", readings), ("requests", resolution_requests)):
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
            output = "/host/native-census-outputs/" + prefix + "-census.json"
            identity = route.output_identity(artifact / (prefix + "-census.json"))
            envelope = {"schema": route.OUTPUT_SCHEMA, "census_schema": route.CENSUS_SCHEMA,
                "path": output, "bytes": identity["bytes"], "blake2b_256": identity["blake2b_256"]}
            add_query(prefix + "-native-census", "Require " + " ".join(requested) + '.\nDeclare ML Module "vos_rocq_census".\n',
                mapping, json.dumps(envelope), environment={"VOS_CENSUS_MODE": "census", "VOS_CENSUS_TARGETS": ",".join(requested),
                    "VOS_CENSUS_RESOLVE_FILE": "/host/native-request-inputs/" + prefix + "-requests.json",
                    route.OUTPUT_VARIABLE: output})
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
            "opam_context": opam,
            "runner": {"platform": "fixture", "machine": "fixture", "python": "fixture"},
            "environment_boundary": route.ENVIRONMENT_BOUNDARY,
            "evidence": {path.name: {"sha256": route.receipts.digest(path), "bytes": path.stat().st_size} for path in artifact.iterdir()}}
        target = artifact / "native-census-qualified.json"
        route.write(target, record)
        with patch.object(route, "recipe", return_value=found), patch.object(route, "native_sources", return_value=sources), \
                patch.object(route, "control_spec", return_value=spec), patch.object(route, "census_api", return_value=api), \
                patch.object(route, "kernel_reading", return_value=[]):
            route.validate_native_qualification(artifact, side, "a" * 40, run_id="1", run_attempt="2")

            class OwnedGraph(dict[str, Any]):
                def __init__(self, contents: dict[str, Any], owner: object = None) -> None:
                    super().__init__(contents)
                    self.owner = owner

            class OwnedRows(list[Any]):
                def __init__(self, contents: list[Any], owner: object) -> None:
                    super().__init__(contents)
                    self.owner = owner

            watched: list[weakref.ReferenceType[OwnedGraph]] = []
            replayed: list[str] = []
            replay = route.replay_census_output

            def owned_replay(command: dict[str, Any], stdout: str, artifact_root: Path,
                             native_root: route.PurePosixPath, prefix: str) -> dict[str, Any]:
                ensure(all(reference() is None for reference in watched),
                       "the prior dataset and derived classifications die before the next native graph parse")
                graph = OwnedGraph(replay(command, stdout, artifact_root, native_root, prefix))
                watched.append(weakref.ref(graph))
                replayed.append(prefix)
                return graph

            def owned_classification(metadata: object, searches: dict[str, str], readings: dict[str, str], *,
                                     expected_modules: list[str]) -> dict[str, dict[str, Any]]:
                graph = OwnedGraph(classify(metadata, searches, readings, expected_modules=expected_modules), metadata)
                for value in graph.values():
                    value["symbols"] = OwnedRows(value["symbols"], metadata)
                    value["alias_audits"] = OwnedRows(value["alias_audits"], metadata)
                watched.append(weakref.ref(graph))
                return graph

            # Plain function replacements avoid mocks retaining argument graphs.
            with patch.object(route, "replay_census_output", new=owned_replay), \
                    patch.object(api, "census", new=owned_classification):
                route.validate_native_qualification(artifact, side, "a" * 40)
            ensure(replayed == ["support", "control"] and all(reference() is None for reference in watched),
                   "both complete replays release their graph, classification and loop-row owners")
            def missing_control(metadata: object, searches: dict[str, str], readings: dict[str, str], *,
                                expected_modules: list[str]) -> dict[str, dict[str, Any]]:
                result = classify(metadata, searches, readings, expected_modules=expected_modules)
                if "CensusControls" in result:
                    result["CensusControls"]["modules"].pop()
                return result
            with patch.object(api, "census", side_effect=missing_control):
                refuses(lambda: route.validate_native_qualification(artifact, side, "a" * 40))

            def unbound_control(metadata: object, searches: dict[str, str], readings: dict[str, str], *,
                                expected_modules: list[str]) -> dict[str, dict[str, Any]]:
                result = classify(metadata, searches, readings, expected_modules=expected_modules)
                if "CensusControls" in result:
                    result["CensusControls"]["alias_audits"] = []
                return result
            with patch.object(api, "census", side_effect=unbound_control):
                refuses(lambda: route.validate_native_qualification(artifact, side, "a" * 40))
            mutations = [lambda row: row["modules"].pop(), lambda row: row["commands"].pop(),
                lambda row: row.update(run_id="3"), lambda row: row["sources"].update(foreign="a" * 64),
                lambda row: row["runtime_after"]["python"].update(sha256="f" * 64),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "kernel-support").update(status="pending"),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "kernel-support").update(process_completed=False),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "kernel-support")["native_environment"].update(OPAMROOT="/foreign/opam"),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "kernel-support")["native_environment"].update(OPAMSWITCH="foreign"),
                lambda row: row.update(commands=[cmd for cmd in row["commands"] if cmd["label"] != "closure"]),
                lambda row: row.update(commands=[cmd for cmd in row["commands"] if cmd["label"] != "frozen-0-baseline"]),
                lambda row: row.update(commands=[cmd for cmd in row["commands"] if cmd["label"] != "frozen-0-candidate"]),
                lambda row: row.update(commands=[cmd for cmd in row["commands"] if cmd["label"] != "baseline-build"]),
                lambda row: row["load_paths"]["baseline"].__setitem__(1, "/host/support"),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "frozen-0-baseline")["argv"].__setitem__(-4, "/host/support"),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "frozen-0-candidate").pop("frozen_query_source"),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "baseline-build").update(cwd="/foreign/baseline-source/upstream"),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "native-plugin-build").update(strict=False),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "strict-0").update(strict=False),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "closure")["argv"].append("foreign"),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "kernel-support")["argv"].pop(),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "support-native-census")["native_environment"].update(VOS_CENSUS_TARGETS="foreign"),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "support-native-census")["request_source_after"].update(sha256="f" * 64),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "support-native-census")["output_file_before"].update(absent=False),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "support-native-census")["output_file_verified"].update(bytes=1),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "support-native-census")["native_environment"].pop(route.OUTPUT_VARIABLE),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "support-native-census")["native_environment"].update({route.PROGRESS_VARIABLE: "/host/progress.json"}),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "native-hidden-assumptions")["native_environment"].update({route.OUTPUT_VARIABLE: "/host/native-census-outputs/control-census.json"}),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "native-unsupported-refusal")["native_environment"].update(VOS_CENSUS_RESOLVE_FILE="/host/native-request-inputs/control-requests.json"),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "inventory-0").pop("query_source"),
                lambda row: row.update(commands=[cmd for cmd in row["commands"] if cmd["label"] != "alias-assumptions-2"]),
                lambda row: next(cmd for cmd in row["commands"] if cmd["label"] == "native-signature-refusal").update(exit=137)]
            for mutation in mutations:
                altered = deepcopy(record)
                mutation(altered)
                route.write(target, altered)
                refuses(lambda: route.validate_native_qualification(artifact, side, "a" * 40, run_id="1", run_attempt="2"))

            def refuses_rebound(replacements: dict[str, bytes], mutate: Callable[[dict[str, Any]], None] | None = None) -> None:
                original_bytes = {name: (artifact / name).read_bytes() for name in replacements}
                altered = deepcopy(record)
                try:
                    for name, contents in replacements.items():
                        (artifact / name).write_bytes(contents)
                        altered["evidence"][name] = {"sha256": route.receipts.digest(artifact / name), "bytes": len(contents)}
                    for command in altered["commands"]:
                        for stream in command["streams"].values():
                            if stream["path"] in replacements:
                                stream["sha256"] = route.receipts.digest(artifact / stream["path"])
                        if command["log"] in replacements:
                            command["log_sha256"] = route.receipts.digest(artifact / command["log"])
                        if command.get("frozen_query_source") in replacements:
                            command["query_sha256"] = route.receipts.digest(artifact / command["frozen_query_source"])
                    if mutate is not None:
                        mutate(altered)
                    route.write(target, altered)
                    refuses(lambda: route.validate_native_qualification(artifact, side, "a" * 40))
                finally:
                    for name, contents in original_bytes.items():
                        (artifact / name).write_bytes(contents)
                    route.write(target, record)

            for label in ("strict-0", "native-plugin-build", "native-control-compile", "probe-compile-term"):
                command = next(cmd for cmd in record["commands"] if cmd["label"] == label)
                refuses_rebound({command["streams"]["stderr"]["path"]: b"Warning: rebound diagnostics\n",
                                 command["log"]: b"Warning: rebound diagnostics\n"},
                    lambda row, label=label: next(cmd for cmd in row["commands"] if cmd["label"] == label).update(strict=False))
            changed_readings: dict[str, bytes] = {}
            for name in ("candidate", "baseline"):
                command = next(cmd for cmd in record["commands"] if cmd["label"] == "frozen-0-" + name)
                changed_readings[command["streams"]["stdout"]["path"]] = b"rebound frozen reading\n"
                changed_readings[command["log"]] = b"rebound frozen reading\n"
                refuses_rebound(changed_readings)
            refuses_rebound({retained_frozen.name: frozen_query.replace("fixture", "foreign").encode("utf-8")})
            missing_object = deepcopy(before)
            missing_object.pop(baseline_tree + "/TypeCasts.vo")
            missing_bytes = (json.dumps(missing_object, indent=2, sort_keys=True) + "\n").encode("utf-8")
            refuses_rebound(dict.fromkeys(("input-identities-before.json", "input-identities.json"), missing_bytes))
            census_output = artifact / "support-census.json"
            original_census = census_output.read_bytes()
            census_output.write_bytes(original_census + b"\n")
            altered = deepcopy(record)
            altered["evidence"][census_output.name] = {"sha256": route.receipts.digest(census_output), "bytes": census_output.stat().st_size}
            route.write(target, altered)
            refuses(lambda: route.validate_native_qualification(artifact, side, "a" * 40))
            census_output.write_bytes(original_census)
            request_file = artifact / "support-requests.json"
            original_request = request_file.read_bytes()
            request_file.unlink()
            route.write(target, record)
            refuses(lambda: route.validate_native_qualification(artifact, side, "a" * 40))
            request_file.write_bytes(original_request + b"\n")
            altered = deepcopy(record)
            altered["evidence"][request_file.name] = {"sha256": route.receipts.digest(request_file), "bytes": request_file.stat().st_size}
            route.write(target, altered)
            refuses(lambda: route.validate_native_qualification(artifact, side, "a" * 40))
            request_file.write_bytes(original_request)
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
            altered = deepcopy(record)
            closure_command = next(cmd for cmd in altered["commands"] if cmd["label"] == "closure")
            closure_files = [closure_command["streams"]["stdout"]["path"], closure_command["log"]]
            original_bytes = {name: (artifact / name).read_bytes() for name in closure_files}
            for name in closure_files:
                (artifact / name).write_text(closure_text.replace("rocq-sail-stdpp 0.20.3", "rocq-sail-stdpp 0.20.2"), encoding="utf-8")
                altered["evidence"][name] = {"sha256": route.receipts.digest(artifact / name), "bytes": (artifact / name).stat().st_size}
            closure_command["streams"]["stdout"]["sha256"] = route.receipts.digest(artifact / closure_files[0])
            closure_command["log_sha256"] = route.receipts.digest(artifact / closure_files[1])
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
    return [Case("canonical-json-streaming", canonical_json_streaming),
            Case("main-revision-guards", revision_guards), Case("immutable-assets", asset_guards),
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
            Case("native-control-census-bindings", native_control_census_bindings),
            Case("native-command-intent-interruption", command_intent_and_interruption),
            Case("native-request-file-protocol", request_file_protocol),
            Case("native-output-file-protocol", native_output_file_protocol),
            Case("native-standalone-replay", standalone_native_replay)]
