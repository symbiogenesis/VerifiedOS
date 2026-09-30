# SPDX-License-Identifier: Apache-2.0
"""Strict witness/replay accounting and control classification without native tools."""

import io
import json
import tarfile
import tomllib
from collections.abc import Callable
from contextlib import nullcontext, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from jsonschema import Draft202012Validator

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from vos import env, sailisla
from vos.cli import sail_isla


def _reject(call: Callable[[], object]) -> None:
    try:
        call()
    except sailisla.IslaError:
        return
    raise AssertionError("incomplete or ambiguous evidence must be refused")


def _witnesses() -> None:
    local = "\n".join(f"Result: #b{code << 12 | code:017b}" for code in reversed(range(16)))
    found = sailisla.parse_symbolic(local, 0)
    ensure(found == {code: code for code in range(16)}, "witness values and inputs must survive parsing")
    global_rows = "\n".join(f"Result: #b{code << 12 | code:017b}" for code in range(16, 32))
    ensure(len(sailisla.parse_symbolic(global_rows, 1)) == 16, "global half is a distinct domain")
    for malformed in (local.rsplit("\n", 1)[0], local + "\n" + local.splitlines()[0],
                      local.replace("Result: #b", "Result: #x", 1),
                      local + "\nError: assertion failed", global_rows):
        _reject(lambda text=malformed: sailisla.parse_symbolic(text, 0))


def _replay_roster() -> None:
    ensure(sailisla.parse_cases("case 2 6 2\ncase 1 2 1\n", {1, 2}) == [
        {"code": 1, "expanded": 2, "narrowed": 1}, {"code": 2, "expanded": 6, "narrowed": 2}],
        "replay must return deterministic numeric ordering")
    for invalid in ("case 1 2 1\n", "case 1 2 1\ncase 1 2 1",
                    "case 1 4096 1\ncase 2 6 2", "case 1 2 32\ncase 2 6 2",
                    "case 1 -1 1\ncase 2 6 2", "case 1 2 1\ncase 3 6 2",
                    "case 1 2 1\ncase 2 6 2\nhelper failed"):
        _reject(lambda text=invalid: sailisla.parse_cases(text, {1, 2}))


def _controls() -> None:
    baseline: list[sailisla.Case] = [{"code": 1, "expanded": 2, "narrowed": 1}]
    defect: list[sailisla.Case] = [{"code": 1, "expanded": 6, "narrowed": 1}]
    log = Path("control.log")
    killed = sailisla.control_result("semantic-defect", baseline, defect, log)
    ensure(killed["status"] == "killed" and killed["mismatches"] == [1],
           "compiled semantic differences are kills")
    survivor = sailisla.control_result("outside-scope", baseline, baseline, log)
    ensure(survivor["status"] == "survived" and not survivor["mismatches"],
           "an undetected compiled defect is a survivor")
    rejected = sailisla.control_result("rejected-build", baseline, None, log)
    ensure(rejected["status"] == "build_rejected" and not rejected["mismatches"],
           "a failed build must not improve the kill count")
    _reject(lambda: sailisla.control_result("partial", baseline, [], log))


def _mutation_anchors() -> None:
    ensure(sailisla._mutate("prefix OLD suffix", "OLD", "NEW") == "prefix NEW suffix",
           "control staging must preserve unrelated source text")
    _reject(lambda: sailisla._mutate("absent", "OLD", "NEW"))
    _reject(lambda: sailisla._mutate("OLD OLD", "OLD", "NEW"))


def _download_digest() -> None:
    with sandbox_tree({}) as root:
        destination = root / "tool.tar"
        with patch.object(sailisla.urllib.request, "urlopen", return_value=io.BytesIO(b"wrong")):
            _reject(lambda: sailisla._download("https://example.invalid/tool", "0" * 64, destination))
        ensure(not destination.exists() and not destination.with_suffix(".tar.part").exists(),
               "a mismatched download must not become an installable archive")


_UPSTREAM_LOCK = """version = 3

[[package]]
name = "crossbeam-channel"
version = "0.5.12"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "aa"
dependencies = [
 "crossbeam-utils",
]

[[package]]
name = "crossbeam-utils"
version = "0.8.19"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "bb"
"""


def _refusal(call: Callable[[], object]) -> str:
    try:
        call()
    except sailisla.IslaError as exc:
        return str(exc)
    raise AssertionError("incomplete or ambiguous evidence must be refused")


def _lock_override() -> None:
    declared = {"crossbeam-channel": "0.5.17"}
    override = _UPSTREAM_LOCK.replace('"0.5.12"', '"0.5.17"').replace('"aa"', '"cc"')
    sailisla.check_lock_override(_UPSTREAM_LOCK, override, declared)
    metadata = '\n[metadata]\nnote = "{}"\n'
    sailisla.check_lock_override(_UPSTREAM_LOCK + metadata.format("a"), override + metadata.format("a"),
                                 declared)
    for changed in (override.replace('"0.8.19"', '"0.8.23"'),
                    override.replace('"0.5.17"', '"0.5.16"'),
                    override.replace(' "crossbeam-utils",\n', ""),
                    override.replace('checksum = "cc"\n', ""),
                    override.replace('checksum = "cc"', 'checksum = "cc"\nreplace = "x"'),
                    override.replace("version = 3", "version = 4"),
                    override + metadata.format("b"),
                    override + '\n[[package]]\nname = "extra"\nversion = "1.0.0"\n'):
        _reject(lambda text=changed: sailisla.check_lock_override(_UPSTREAM_LOCK, text, declared))
    _reject(lambda: sailisla.check_lock_override(_UPSTREAM_LOCK + metadata.format("a"),
                                                 override + metadata.format("b"), declared))
    _reject(lambda: sailisla.check_lock_override(_UPSTREAM_LOCK, override, {"crossbeam-epoch": "0.9.21"}))
    suffixed = override.replace('"0.5.17"', '"0.5.17-rc.1"')
    ensure("not a plain major.minor.patch release" in _refusal(
        lambda: sailisla.check_lock_override(_UPSTREAM_LOCK, suffixed, {"crossbeam-channel": "0.5.17-rc.1"})),
        "a pre-release override must be refused rather than ordered")


def _lock_override_upstream_caught_up() -> None:
    declared = {"crossbeam-channel": "0.5.17"}
    override = _UPSTREAM_LOCK.replace('"0.5.12"', '"0.5.17"').replace('"aa"', '"cc"')
    newer = _UPSTREAM_LOCK.replace('"0.5.12"', '"0.5.18"').replace('"aa"', '"dd"')
    message = _refusal(lambda: sailisla.check_lock_override(newer, override, declared))
    ensure("upstream already carries crossbeam-channel 0.5.18" in message
           and "retire or regenerate the override" in message,
           "an override older than upstream's release would silently downgrade it")
    message = _refusal(lambda: sailisla.check_lock_override(override, override, declared))
    ensure("upstream already carries crossbeam-channel 0.5.17" in message,
           "an override equal to upstream's release is no longer an override")
    # Ordering is numeric per component, not lexical over the version string.
    sailisla.check_lock_override(_UPSTREAM_LOCK.replace('"0.5.12"', '"0.5.9"'), override, declared)
    ensure("upstream already carries crossbeam-channel 0.10.0" in _refusal(
        lambda: sailisla.check_lock_override(_UPSTREAM_LOCK.replace('"0.5.12"', '"0.10.0"'), override,
                                             declared)),
        "a later minor release must order above every patch of an earlier minor")


def _tracked_lock_override() -> None:
    lock = json.loads((TOOLS / "sail-isla/lock.json").read_text(encoding="utf-8"))
    override = (TOOLS / "sail-isla" / lock["isla"]["cargo_lock"]).read_text(encoding="utf-8")
    rows = {(row["name"], row["version"]) for row in tomllib.loads(override)["package"]}
    ensure(all((name, version) in rows for name, version in lock["isla"]["cargo_lock_overrides"].items()),
           "the tracked Isla lock override must carry every declared version")


def _sail_pin_is_locked_release() -> None:
    lock = json.loads((TOOLS / "sail-isla/lock.json").read_text(encoding="utf-8"))

    def pin(version: str) -> sailisla.SailPin:
        return cast(sailisla.SailPin, {**lock["sail"], "version": version})

    installed = 'installed: [\n  "ocaml.5.4.1"\n  "sail.0.20.3"\n  "sail_maker.0.20.3"\n]\n'
    with sandbox_tree({"tools/opam/sail.lock": installed}) as root:
        ensure(sailisla.baseline_packages(root, pin("0.20.3"))
               == {"ocaml.5.4.1", "sail.0.20.3", "sail_maker.0.20.3"},
               "the complete locked inventory must be returned")
        for version in ("0.20.4", "0.20", "maker.0.20.3"):
            _reject(lambda v=version: sailisla.baseline_packages(root, pin(v)))
        environment = env.Environment(root=root, model=root / "model", build_root=root / "native",
                                      log_root=root / "logs", lane="", cpus=1, mem_available_mb=1024,
                                      jobs=1, test_jobs=1)
        runner = sailisla.Runner(environment, "test")
        with patch.object(sailisla.Runner, "run") as run:
            _reject(lambda: sailisla._prerequisites(environment, runner, pin("0.20.4")))
        ensure(not run.called, "the Sail pin must be refused before the baseline switch is inspected")


def _provision_uses_fresh_prefix() -> None:
    lock = (TOOLS / "sail-isla/lock.json").read_text(encoding="utf-8")
    files = {"tools/sail-isla/lock.json": lock, "tools/sail-isla/isla.Cargo.lock": "override",
             "tools/sail-isla/driver/Cargo.toml": "[package]\n"}
    with sandbox_tree(files) as root:
        environment = env.Environment(root=root, model=root / "model", build_root=root / "native",
                                      log_root=root / "logs", lane="", cpus=1, mem_available_mb=1024,
                                      jobs=1, test_jobs=1)
        base = environment.lane_root / "sail-isla"
        stale = base / "sail-prefix/lib/superseded/META"
        stale_plugin = base / "sail-prefix/share/libsail/plugins/superseded.cmxs"
        stamp = base / "provision.json"

        def plant() -> None:
            for path in (stale, stale_plugin, stamp):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("superseded", encoding="utf-8")

        def fetch(pin: sailisla.SourcePin, destination: Path, runner: sailisla.Runner) -> None:
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "Cargo.lock").write_text("upstream", encoding="utf-8")

        def download(url: str, expected: str, destination: Path) -> None:
            member = tarfile.TarInfo(json.loads(lock)["sail"]["directory"] + "/dune-project")
            member.size = 4
            with tarfile.open(destination, "w") as archive:
                archive.addfile(member, io.BytesIO(b"sail"))

        def run(self: sailisla.Runner, argv: list[str], cwd: Path,
                process_env: dict[str, str] | None = None, timeout: int = 1800) -> str:
            if "install" in argv and "--prefix" in argv:
                installed = Path(argv[argv.index("--prefix") + 1]) / "lib/libsail/META"
                installed.parent.mkdir(parents=True, exist_ok=True)
                installed.write_text("current", encoding="utf-8")
            return "/switch\n" if argv[:2] == ["opam", "var"] else ""

        def provision(build: Callable[..., str] = run) -> None:
            with (patch.object(sailisla.env, "hold_lock", side_effect=lambda *_: nullcontext()),
                  patch.object(sailisla, "_prerequisites", return_value=root / "z3"),
                  patch.object(sailisla.platform, "system", return_value="Linux"),
                  patch.object(sailisla.platform, "machine", return_value="x86_64"),
                  patch.object(sailisla, "_fetch", side_effect=fetch),
                  patch.object(sailisla, "check_lock_override"),
                  patch.object(sailisla, "_install_rust"),
                  patch.object(sailisla, "_download", side_effect=download),
                  patch.object(sailisla.Runner, "run", autospec=True, side_effect=build),
                  patch.object(sailisla, "asset_digest", return_value="a" * 64),
                  patch.object(sailisla, "_binaries", return_value=[])):
                sailisla.provision(environment)

        plant()
        provision()
        ensure((base / "sail-prefix/lib/libsail/META").read_text(encoding="utf-8") == "current"
               and (base / "sail-prefix/share/libsail/plugins").is_dir(),
               "provisioning must install the current Sail into its prefix")
        ensure(not stale.exists() and not stale_plugin.exists(),
               "nothing a superseded build installed may stay on OCAMLPATH or in the plugin site")
        ensure(json.loads(stamp.read_text(encoding="utf-8"))["assets_sha256"] == "a" * 64,
               "the stamp must describe the rebuilt prefix")
        plant()
        with patch.object(sailisla, "_fresh_prefix", side_effect=lambda lane: lane / "sail-prefix"):
            provision()
        ensure(stale.exists() and stale_plugin.exists(),
               "control: the superseded recipe's reused prefix keeps a superseded build's files")

        def interrupted(self: sailisla.Runner, argv: list[str], cwd: Path,
                        process_env: dict[str, str] | None = None, timeout: int = 1800) -> str:
            if "install" in argv and "--prefix" in argv:
                raise sailisla.IslaError("command exited 1")
            return run(self, argv, cwd, process_env, timeout)

        plant()
        _reject(lambda: provision(interrupted))
        ensure(not stamp.exists() and not stale.exists(),
               "an interrupted provisioning must leave no stamp describing a removed prefix")


def _report() -> dict[str, Any]:
    return {
        "version": 1, "advisory_only": True, "notice": sailisla.NOTICE, "passed": True,
        "source_sha256": {"model.sail": "a" * 64}, "tool_sha256": {"sail": "b" * 64},
        "assets_sha256": "c" * 64, "ir_sha256": "d" * 64,
        "cases": [{"code": code, "expanded": code, "narrowed": code} for code in range(32)],
        "symbolic_paths": [16, 16], "baseline_matches": 32, "testgen_matches": 32,
        "controls": [
            {"name": "semantic-defect", "status": "killed", "mismatches": [1], "log": "kill.log"},
            {"name": "outside-scope", "status": "survived", "mismatches": [], "log": "survive.log"},
            {"name": "rejected-build", "status": "build_rejected", "mismatches": [], "log": "reject.log"}],
        "invocations": [], "directory": "/native/campaign",
    }


def _schema() -> None:
    schema = json.loads((TOOLS / "sail-isla/report.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    report = _report()
    validator.validate(report)
    report["advisory_only"] = False
    ensure(bool(list(validator.iter_errors(report))), "report must retain the advisory boundary")
    report = _report()
    report["cases"].pop()
    ensure(bool(list(validator.iter_errors(report))), "partial case reports must fail the schema")
    report = _report()
    report["controls"][2]["status"] = "killed-by-compilation"
    ensure(bool(list(validator.iter_errors(report))), "schema must distinguish rejected builds")


def _cli() -> None:
    for error in (sailisla.IslaError("missing witnesses"), OSError("missing tools")):
        stdout, stderr = io.StringIO(), io.StringIO()
        with (patch.object(sail_isla.env, "load"),
              patch.object(sail_isla.sailisla, "qualify", side_effect=error),
              redirect_stdout(stdout), redirect_stderr(stderr)):
            code = sail_isla.main(["qualify", "--json"])
        ensure(code == 1 and not stdout.getvalue() and str(error) in stderr.getvalue(),
               "failed generation must not emit a partial JSON success")
    report = _report()
    report["passed"] = False
    stdout = io.StringIO()
    with (patch.object(sail_isla.env, "load"),
          patch.object(sail_isla.sailisla, "qualify", return_value=report),
          redirect_stdout(stdout)):
        code = sail_isla.main(["qualify", "--json"])
    ensure(code == 1 and json.loads(stdout.getvalue())["passed"] is False,
           "unexpected completed control outcomes need a nonzero status and explicit verdict")


def _harness_uses_model() -> None:
    text = sailisla.harness([3, 9])
    ensure("0b00011" in text and "0b01001" in text and "0b00000" not in text,
           "only generated witness inputs belong in the replay harness")
    ensure("perms_expand(code)" in text and "perms_narrow(expanded)" in text,
           "the harness must call curated functions rather than embed expected answers")


def cases() -> list[Case]:
    return [Case("symbolic-completeness-and-uniqueness", _witnesses),
            Case("replay-exact-roster", _replay_roster),
            Case("defect-control-classification", _controls),
            Case("mutation-unique-anchors", _mutation_anchors),
            Case("download-digest-refusal", _download_digest),
            Case("lock-override-declared-versions-only", _lock_override),
            Case("lock-override-refuses-upstream-equal-or-newer", _lock_override_upstream_caught_up),
            Case("tracked-lock-override-carries-declared-versions", _tracked_lock_override),
            Case("sail-pin-is-the-locked-release", _sail_pin_is_locked_release),
            Case("provisioning-installs-into-a-fresh-prefix", _provision_uses_fresh_prefix),
            Case("versioned-json-schema", _schema),
            Case("cli-refuses-partial-verdict", _cli),
            Case("oracle-replays-generated-inputs", _harness_uses_model)]
